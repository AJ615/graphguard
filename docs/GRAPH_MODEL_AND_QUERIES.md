# GraphGuard — Graph Model & Cypher Queries

All node labels, relationship types, properties, and Cypher queries listed here correspond exactly to the code in `backend/seed.py` and `backend/graph_tools.py`. Nothing is invented.

---

## Node Labels

| Label | Role in the Graph | Key Properties |
|---|---|---|
| `User` | Employee or contractor whose account activity is tracked | `entity_id`, `email`, `name`, `role`, `tenant_id` |
| `Device` | Endpoint: workstation, server, laptop, mobile | `entity_id`, `hostname`, `os`, `owner`, `tenant_id` |
| `IPAddress` | Source IP of network activity | `entity_id`, `address`, `ip_type` (internal/external), `location`, `tenant_id` |
| `Service` | Internal system accessed by users | `entity_id`, `name`, `service_type`, `sensitivity`, `tenant_id` |
| `Alert` | Security detection event requiring investigation | `entity_id`, `name`, `severity` (critical/high/medium/low), `alert_type`, `device_id`, `user_id`, `status`, `tenant_id` |
| `Incident` | Confirmed or suspected security incident grouping alerts | `entity_id`, `name`, `description`, `status` (confirmed/suspected), `confidence`, `tenant_id` |
| `Evidence` | Individual log entry or artifact supporting a finding | `entity_id`, `evidence_type`, `description`, `status` (confirmed/suspected), `tenant_id` |
| `Investigation` | Persisted result of one agent investigation run | `entity_id`, `session_id`, `tenant_id`, `alert_id`, `risk_level`, `risk_score`, `summary`, `mode`, `timestamp` |
| `Finding` | Atomic conclusion within an investigation | `entity_id`, `statement`, `finding_type`, `confidence`, `verification_status`, `evidence_ids`, `entity_ids`, `investigation_id` |

> **Note:** The `Decision` node mentioned in early design notes was **not implemented**. There is no `Decision` node in the seed or query code. `Finding` nodes serve this function.

---

## Relationship Types

| Relationship | From → To | Meaning |
|---|---|---|
| `USED` | `User → Device` | User operated this device |
| `CONNECTED_FROM` | `Device → IPAddress` | Device communicated from this IP |
| `ACCESSED` | `User → Service` | User accessed this service |
| `TRIGGERED` | `User → Alert` | User activity that triggered the alert |
| `INVOLVED_IN` | `Device → Alert` | Device involved in the alert event |
| `INVOLVED_IN` | `Device → Incident` | Device involved in the broader incident |
| `ASSOCIATED_WITH` | `Alert → Incident` | Alert is part of this confirmed incident |
| `SUPPORTED_BY` | `Incident → Evidence` | Incident is backed by this evidence |
| `SUPPORTED_BY` | `Alert → Evidence` | Alert is directly backed by this evidence |
| `TARGETED` | `Incident → Service` | Incident targeted a sensitive service |
| `RELATED_TO` | `Alert → Alert` | Alerts sharing the same attack chain |
| `EXAMINED` | `Investigation → Alert` | Investigation examined this alert |
| `DISCOVERED` | `Investigation → Finding` | Investigation produced this finding |

---

## Why a Graph Database is Essential

A relational database would require multi-table joins with unpredictable depth. The key investigation question is:

> *"Is this alert connected — directly or through 2 hops — to a known confirmed incident, and if so, via which entities?"*

This requires traversing heterogeneous paths like:

```
Alert → Device → Incident
Alert → User → Device → Incident
Alert → Evidence → Incident
```

The graph makes these multi-hop, multi-type traversals natural and efficient. **Removing FalkorDB eliminates the ability to traverse the incident chain**, which is the core investigation mechanism.

---

## Actual Cypher Queries Used by the Product

### 1. `find_entity` — Retrieve a node by ID with tenant enforcement

```cypher
MATCH (n {entity_id: $eid, tenant_id: $tid})
RETURN labels(n) AS lbl, properties(n) AS props LIMIT 1
```

Called in `backend/graph_tools.py:find_entity()`. Enforces tenant isolation at the query layer.

### 2. `find_related_entities` — Depth-1 neighbors

```cypher
MATCH (start {entity_id: $eid})-[r]-(end)
WHERE start <> end
RETURN labels(end) AS lbl, properties(end) AS props,
       {} AS rel_props, type(r) AS rel_type
LIMIT 30
```

### 3. `find_related_entities` — Depth-2 neighbors

```cypher
MATCH (start {entity_id: $eid})-[r]-(mid)-[r2]-(end)
WHERE start <> end AND start <> mid AND mid <> end
RETURN labels(end) AS lbl, properties(end) AS props,
       {} AS rel_props, type(r2) AS rel_type
LIMIT 30
```

> **Implementation note:** FalkorDB 1.0.10 does not support `last(r)` on variable-length path results (`-[r*1..2]-`). The query was rewritten using explicit depth-1 and depth-2 patterns. Results are deduplicated by `entity_id` in the application layer.

### 4. `find_similar_incidents` — Historical incidents via shared entities

```cypher
MATCH (e {entity_id: $eid})-[*1..2]-(inc:Incident)
RETURN properties(inc) AS inc_props, $eid AS via_entity
LIMIT 5
```

Called once per entity from the input list (up to 10 entities). This query uses variable-length traversal without `last(r)` — compatible with FalkorDB.

### 5. `save_investigation` — Persist investigation node (MERGE upsert)

```cypher
MERGE (inv:Investigation {entity_id: $iid})
SET inv.session_id = $sid,
    inv.tenant_id = $tid,
    inv.alert_id = $aid,
    inv.risk_level = $rl,
    inv.risk_score = $rs,
    inv.summary = $summary,
    inv.recommended_actions = $actions,
    inv.missing_evidence = $missing,
    inv.timestamp = $ts,
    inv.mode = $mode
RETURN inv
```

Then links to Alert:
```cypher
MATCH (inv:Investigation {entity_id: $iid})
MATCH (a:Alert {entity_id: $aid})
MERGE (inv)-[:EXAMINED]->(a)
```

And creates Finding nodes:
```cypher
MERGE (fn:Finding {entity_id: $fid})
SET fn.statement = $stmt, fn.finding_type = $ftype, ...
WITH fn
MATCH (inv:Investigation {entity_id: $iid})
MERGE (inv)-[:DISCOVERED]->(fn)
```

### 6. `get_related_investigations` — Cross-session memory retrieval

By same alert:
```cypher
MATCH (inv:Investigation {alert_id: $aid, tenant_id: $tid})
RETURN properties(inv) AS props
ORDER BY inv.timestamp DESC LIMIT 5
```

By shared entities via findings:
```cypher
MATCH (inv:Investigation)-[:DISCOVERED]->(fn:Finding)
WHERE $eid IN fn.entity_ids
RETURN properties(inv) AS props LIMIT 5
```

---

## Example Synthetic Investigation Paths

### Scenario A — Connected Risk (alert_001)

```
alert_001 (TOR Exit, critical)
  → [TRIGGERED]  → user_eve (contractor)
  → [INVOLVED_IN] → dev_w005 (WORKSTATION-005)
  → [ASSOCIATED_WITH] → inc_001 (Credential Theft, confirmed, 0.95)
  → [SUPPORTED_BY] → ev_003 (Mimikatz execution)
  → [TARGETED] → svc_fin (Finance-API, sensitive)
```

**Effect:** Multi-hop traversal finds confirmed incident. Risk computed as CRITICAL (score ≥ 0.7). Recommended action: isolate dev_w005.

### Scenario B — Insufficient Evidence (alert_003)

```
alert_003 (Off-Hours Login, medium)
  → [TRIGGERED]  → user_carol (admin)
  → [INVOLVED_IN] → dev_w003 (WORKSTATION-003, linux)
  [No path to any Incident node]
```

**Effect:** `find_similar_incidents` for `dev_w003` returns 0 incidents. Missing evidence is recorded. Risk scored as LOW/MEDIUM. No incident link means reduced escalation recommendation.

### Scenario C — Cross-Session Memory (alert_004)

```
alert_004 (SMB Lateral Movement)
  → [INVOLVED_IN] → dev_w005
                     [shared with alert_001]
  → memory lookup: Investigation for alert_001 retrieved from FalkorDB
```

**Effect:** Prior investigation note ("Session A: TOR exit connection confirmed with lateral movement") surfaces in the new investigation as historical context.

---

## How Graph Traversal Affects Investigation Conclusions

The investigation conclusion **changes based on actual graph content**:

| State | `find_similar_incidents` result | Computed risk |
|---|---|---|
| `dev_w005 → inc_001` present (Scenario A) | Returns `inc_001` (confirmed) | CRITICAL / HIGH |
| Link removed (Scenario B analog) | Returns 0 incidents | LOW / MEDIUM |
| Link restored | Returns `inc_001` again | CRITICAL / HIGH |

This is not hard-coded by alert ID. The risk scoring function (`_compute_risk` in `agent.py`) uses the count of confirmed incidents returned by graph queries. The graph result drives the conclusion.

---

## Known Query Limitations

1. **`last(r)` incompatibility**: FalkorDB 1.0.10 does not support `last(r)` on variable-length path results. Resolved by explicit depth-1 / depth-2 queries.
2. **Depth cap at 3**: `MAX_DEPTH = 3` in `graph_tools.py`. Prevents runaway traversals.
3. **Variable-length in `find_similar_incidents`**: Uses `[*1..2]` without `last(r)` — this works correctly in FalkorDB.
4. **Tenant filtering on depth-2**: Tenant filter is applied post-query at depth-2. The intermediate node (`mid`) may belong to any tenant; only the terminal `end` node is filtered. This is an acceptable limitation for a local demo with one tenant.
5. **No property indexes**: FalkorDB creates indexes on labels automatically, but `entity_id` lookups cross all labels without an explicit index. Acceptable at demo scale.
