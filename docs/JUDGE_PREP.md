# GraphGuard — Judge Preparation Q&A

Plain-language answers to likely judge questions. Every answer is grounded in the actual implementation.

---

## 1. Why FalkorDB rather than a relational database alone?

A relational database can store the same data, but answering "Is this alert connected to a confirmed incident within 2 hops?" requires multi-join queries whose structure changes with alert type. In a graph, this is a single traversal:

```
MATCH (a:Alert)-[*1..2]-(inc:Incident) WHERE a.entity_id = $id
```

The application doesn't need to know in advance which intermediate tables to join. When a new relationship type is added — say a `Service → Incident` path — the traversal query picks it up automatically. A relational schema would require a new JOIN clause.

More importantly for this demo: **the investigation conclusion changes when the graph relationship changes.** Remove `dev_w005 → inc_001` and the risk drops from CRITICAL to LOW. That is the core value proposition.

---

## 2. Which exact graph traversal powers the main feature?

The primary traversal is in `backend/graph_tools.py::find_related_entities()`:

- **Depth-1**: `MATCH (start {entity_id: $eid})-[r]-(end)` — all direct neighbors
- **Depth-2**: `MATCH (start {entity_id: $eid})-[r]-(mid)-[r2]-(end)` — 2-hop neighbors

These results are then passed to `find_similar_incidents()`:

```cypher
MATCH (e {entity_id: $eid})-[*1..2]-(inc:Incident)
RETURN properties(inc) AS inc_props
```

This is the traversal that discovers whether a confirmed incident exists in the entity's 2-hop neighborhood.

---

## 3. How does a relationship change the investigation result?

There is a direct causal chain:

1. `find_similar_incidents` queries FalkorDB for `Incident` nodes reachable from the alert's connected entities.
2. The returned incidents are passed to `_compute_risk()` in `agent.py`.
3. Risk score formula: `score += min(len(confirmed_incidents) * 0.15, 0.30)`.
4. A severity=critical alert with 1 confirmed incident → score ~0.65 → risk=HIGH.
5. The same alert with 0 confirmed incidents → score ~0.50 → risk=MEDIUM or lower.

The test `test_scenario_b_no_incident_link` verifies this: `dev_w003` has no incident path, so `inc_001` never appears in the result.

---

## 4. How is persistent agent memory represented in the graph?

Each completed investigation creates:
- An `Investigation` node with all findings, risk score, summary, and timestamp
- A `Finding` node per finding, linked via `(Investigation)-[:DISCOVERED]->(Finding)`
- A link to the investigated alert: `(Investigation)-[:EXAMINED]->(Alert)`

When a new investigation starts, `memory.py::get_related_investigations()` queries FalkorDB for prior `Investigation` nodes that share the same alert ID or have findings referencing the same entity IDs:

```cypher
MATCH (inv:Investigation {alert_id: $aid, tenant_id: $tid})
RETURN properties(inv) AS props ORDER BY inv.timestamp DESC

MATCH (inv:Investigation)-[:DISCOVERED]->(fn:Finding)
WHERE $eid IN fn.entity_ids
RETURN properties(inv) AS props
```

This memory persists across process restarts because it is stored in FalkorDB, not in Python memory.

---

## 5. How is tenant isolation enforced?

Isolation is enforced in two ways:

**Query-layer enforcement** (primary): `find_entity` includes `tenant_id = $tid` in the MATCH pattern, so FalkorDB only returns nodes with the matching tenant.

**Post-query filtering** (defense-in-depth): `find_related_entities` and `find_similar_incidents` filter returned nodes by `tenant_id` before adding them to results.

The test `test_tenant_isolation` verifies: querying `alert_001` with `tenant_id="tenant_other"` returns `{"found": False}`, even though the node exists with `tenant_id="tenant_default"`.

**Limitation**: Depth-2 traversals can use intermediate nodes from other tenants as routing nodes. For a production system, a full solution would add tenant filtering at each hop. This is documented in `docs/GRAPH_MODEL_AND_QUERIES.md`.

---

## 6. How are evidence and conclusions validated?

- **Observed** findings cite `evidence_ids` from graph query results only.
- **Inferred** findings are labeled `confidence=0.75, verification_status="unverified"`.
- **Recommendation** findings are labeled `finding_type="recommendation"`.
- The investigation summary is prefixed `[DEMO MODE]` to prevent confusion with LLM output.
- `save_investigation` uses MERGE (upsert), so duplicate runs don't create phantom records.
- The agent sets `report.saved = False` and logs an error if the database write fails — it never claims a save it didn't complete.

In LLM mode: the LLM's text output is stored as a finding with `confidence=0.7, verification_status="unverified"`. The structured findings from tool results (with `verification_status="verified"`) are kept separate.

---

## 7. What are the most important architectural trade-offs?

| Decision | Rationale | Trade-off |
|---|---|---|
| FalkorDB as persistence layer | Investigation memory survives restarts; graph traversal is natural | Requires Docker; not as familiar as SQL |
| Demo mode is deterministic | Works without LLM API key; reproducible for demo | Cannot do open-ended NL queries |
| Depth capped at 3 | Prevents exponential traversal | May miss very deep paths |
| Single-tenant seed | Keeps demo simple and clear | Tenant isolation partially post-query at depth-2 |
| Streamlit frontend | Fast to build; good for data display | Not production-grade; single page |
| Fixed risk scoring formula | Transparent and testable | Not calibrated against real SOC data |

---

## 8. What does deterministic mode do?

In demo mode (the default, `DEMO_MODE=true`, no LLM key needed):

1. Fetch the alert from FalkorDB via `find_entity`
2. Explore all 2-hop neighbors via `find_related_entities`
3. Search for historical incidents via `find_similar_incidents`
4. Retrieve prior investigations via `get_related_investigations`
5. Compute heuristic risk score from confirmed incident count + severity
6. Build recommendation list from risk level + device/user list
7. Persist the investigation via `save_investigation`

All seven steps use real FalkorDB queries. The investigation conclusion depends on actual graph content. The mode is labeled `[DEMO MODE]` in the summary.

---

## 9. What are the current limitations?

1. **No authentication** — local demo only. Not safe to expose publicly.
2. **LLM mode: Anthropic only** — OpenAI provider is not implemented.
3. **Depth-2 tenant isolation gap** — intermediate nodes are not tenant-filtered.
4. **Heuristic risk scoring** — not calibrated against real security data.
5. **Synthetic data only** — no integration with real SIEM or EDR systems.
6. **No demo video yet** — must be recorded before submission.
7. **No public deployment** — local setup only.
8. **Single-graph setup** — test suite uses `graphguard_test` graph name but shares the same FalkorDB instance. Parallel test runs could interfere.

---

## 10. What did AI coding tools help with, and what did I personally verify and change?

**AI assisted with:**
- Initial scaffolding of FastAPI endpoints structure
- Streamlit UI layout and CSS theme
- Seed data structure definitions
- Pydantic schema definitions
- Cypher query templates

**I personally verified and changed:**
- **Identified and fixed** a critical FalkorDB incompatibility: `last(r)` on variable-length paths raises "Type mismatch: expected List or Null but was Path" — this caused `find_related_entities` to silently return zero neighbors. Fixed by rewriting to explicit depth-1 and depth-2 queries.
- **Ran the full test suite** against a live FalkorDB instance and confirmed 25/25 pass after the fix.
- **Verified the graph-dependency**: confirmed that alert_001 returns CRITICAL risk via the `dev_w005 → inc_001` path, and that alert_003 (without an incident path) returns lower risk.
- **Verified tenant isolation**: confirmed `find_entity("alert_001", "tenant_other")` returns not-found.
- **Verified cross-session memory**: confirmed that saving an investigation for alert_001 causes it to appear in a later investigation of alert_004 (shared device).
- **Wrote all documentation** in `docs/` based on actual code inspection.
- **Understand the FalkorDB Cypher dialect** including the variable-length path limitation and the tenant isolation approach.
