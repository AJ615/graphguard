
# 🛡️ GraphGuard

**AI-powered security incident investigation assistant backed by FalkorDB.**

> **Graph Hacks by WeMakeDevs × FalkorDB**  
> **Track 01: Agents That Act on Connected Data**  
> **Track 02: Agent Memory and Coordination**

GraphGuard uses a native property graph database (FalkorDB) to investigate security alerts by traversing real entity relationships. The graph traversal directly determines the investigation outcome — removing FalkorDB eliminates multi-hop incident discovery, which is the core capability.

---

## Problem & Target User

Security analysts face alert fatigue: 100s of alerts per day, most uncontextualized. Was this failed login a coincidence or part of a broader attack chain involving a compromised device and confirmed credential theft?

**Target user**: Security operations center (SOC) analysts who need evidence-backed triage.

**GraphGuard answer**: Traverse the connected security graph — alert → device → incident → evidence — and surface confirmed incident paths automatically.

---

## Why FalkorDB is Essential

| Without FalkorDB | With FalkorDB |
|---|---|
| Alert metadata lookup only | Multi-hop traversal: alert → device → incident → evidence |
| Same risk for all alerts | Risk driven by confirmed incident proximity in graph |
| No historical context | Prior investigations retrieved from persisted graph memory |
| Manually specified relationships | Graph schema discovers paths automatically |

The investigation conclusion **changes** when the graph relationship changes. This is verified by the test suite (`test_scenario_a_connected_risk` vs `test_scenario_b_no_incident_link`).

---

## Architecture

```
Streamlit UI (port 8501)
     ↓
FastAPI Backend (port 8000)
     ↓
Investigation Agent (demo mode: deterministic / LLM mode: Anthropic)
     ↓
FalkorDB Graph Database (port 6379) ← source of truth for all entity data,
                                         relationships, and investigation memory
```

**Four graph tools** (in `backend/graph_tools.py`):
1. `find_entity` — retrieve any node by ID with tenant enforcement
2. `find_related_entities` — multi-hop traversal (depth 1–3)
3. `find_similar_incidents` — historical incidents via shared entities
4. `save_investigation` — persist investigation + findings as graph nodes

---

## Graph Schema

See [`docs/GRAPH_MODEL_AND_QUERIES.md`](./docs/GRAPH_MODEL_AND_QUERIES.md) for complete schema, actual Cypher queries, and example paths.

**Node labels**: `User`, `Device`, `IPAddress`, `Service`, `Alert`, `Incident`, `Evidence`, `Investigation`, `Finding`

**Key relationships**:
```
(User)-[:USED]->(Device)-[:CONNECTED_FROM]->(IPAddress)
(User)-[:TRIGGERED]->(Alert)-[:ASSOCIATED_WITH]->(Incident)
(Device)-[:INVOLVED_IN]->(Alert)
(Incident)-[:SUPPORTED_BY]->(Evidence)
(Investigation)-[:DISCOVERED]->(Finding)
(Investigation)-[:EXAMINED]->(Alert)
```

**Core investigation traversal**:
```cypher
-- Depth-1 neighbors
MATCH (start {entity_id: $eid})-[r]-(end)
WHERE start <> end
RETURN labels(end), properties(end), type(r) LIMIT 30

-- Historical incidents via shared entities
MATCH (e {entity_id: $eid})-[*1..2]-(inc:Incident)
RETURN properties(inc) LIMIT 5
```

---

## Demo Scenarios

| Scenario | Alert | What the Graph Shows |
|---|---|---|
| **A — Connected Risk** | `alert_001` | `alert → dev_w005 → inc_001` (confirmed credential theft) → CRITICAL risk |
| **B — Insufficient Evidence** | `alert_003` | `alert → dev_w003` — no incident path → LOW/MEDIUM risk |
| **C — Cross-Session Memory** | `alert_004` | Retrieves prior investigation of `alert_001` from FalkorDB via shared device |

**All data is synthetic** — fictional users, devices, and incidents for demonstration only.

---

## Verified Features

- ✅ FalkorDB connects and seeded (76 nodes, 81 relationships)
- ✅ Multi-hop entity traversal (depth 1–2 verified)
- ✅ Incident discovery via shared entities
- ✅ Tenant isolation enforced at query layer
- ✅ Investigation persistence in FalkorDB (MERGE upsert)
- ✅ Cross-session memory retrieval
- ✅ Risk score changes with graph connectivity
- ✅ Demo mode works without LLM API key
- ✅ 25/25 tests pass (11 unit + 14 integration)

---

## Prerequisites

- Python 3.11+
- Docker Desktop (for FalkorDB)
- Anthropic API key (optional — demo mode works without one)

---

## Setup & Run

### 1. Clone and set up

```powershell
cd graphguard/
python -m venv .venv
.venv\Scripts\Activate.ps1           # Windows PowerShell
# source .venv/bin/activate          # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure environment

```powershell
copy .env.example .env
# For LLM mode: set LLM_API_KEY=your_key and LLM_PROVIDER=anthropic in .env
# Demo mode works with no changes
```

### 3. Start FalkorDB

```powershell
docker compose up -d
```

### 4. Seed the graph

```powershell
python -m backend.seed
# To reset and re-seed: python -m backend.seed --reset
```

### 5. Start the backend

```powershell
uvicorn backend.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
# Health check: http://localhost:8000/health
```

### 6. Start the frontend (new terminal)

```powershell
streamlit run frontend/app.py
# Open: http://localhost:8501
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FALKORDB_HOST` | `localhost` | FalkorDB host |
| `FALKORDB_PORT` | `6379` | FalkorDB port |
| `FALKORDB_PASSWORD` | _(empty)_ | FalkorDB password (if set) |
| `FALKORDB_GRAPH` | `graphguard` | Graph name |
| `LLM_PROVIDER` | `demo` | `demo` or `anthropic` |
| `LLM_API_KEY` | _(empty)_ | API key for LLM provider |
| `LLM_MODEL` | `claude-3-5-haiku-20241022` | Model identifier |
| `DEMO_MODE` | `true` | `true` = no LLM calls |
| `DEFAULT_TENANT_ID` | `tenant_default` | Default tenant |

---

## Running Tests

```powershell
# Unit tests (no DB required — fast)
python -m pytest tests/test_agent.py tests/test_api.py -v

# All tests including integration (FalkorDB must be running)
python -m pytest tests/ -v
```

**Last run**: 25/25 PASS — see [`docs/TEST_REPORT.md`](./docs/TEST_REPORT.md)

---

## Known Limitations

- No authentication — local demo only, not production-ready
- LLM mode: Anthropic only (OpenAI not implemented)
- Depth-2 traversal: intermediate nodes not tenant-filtered (documented limitation)
- Risk scoring is heuristic, not calibrated against real security data
- No live deployment — local setup only

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Backend unreachable` in Streamlit | Start uvicorn first: `uvicorn backend.main:app --port 8000` |
| FalkorDB not connecting | Run `docker compose up -d`, wait 10s, retry |
| `Entity not found` errors | Run `python -m backend.seed` |
| All neighbors empty | Upgrade falkordb client or verify fix in `graph_tools.py` |
| Tests skip with "FalkorDB not available" | Start Docker and FalkorDB before running integration tests |

---

## Documentation

- [`docs/GRAPH_MODEL_AND_QUERIES.md`](./docs/GRAPH_MODEL_AND_QUERIES.md) — Schema, Cypher, examples
- [`docs/TEST_REPORT.md`](./docs/TEST_REPORT.md) — Full test results
- [`docs/DEMO_SCRIPT.md`](./docs/DEMO_SCRIPT.md) — Timestamped demo narration
- [`docs/JUDGE_PREP.md`](./docs/JUDGE_PREP.md) — Architecture Q&A
- [`MASTER_DOCUMENTATION.md`](./MASTER_DOCUMENTATION.md) — Full technical documentation

---

## AI Assistance Disclosure

This project was built with assistance from AI coding tools (Claude Sonnet). The AI helped with initial scaffolding, query templates, and UI layout. The developer personally:
- Identified and fixed a critical FalkorDB query incompatibility (`last(r)` on variable-length paths)
- Ran and validated all 25 tests against a live FalkorDB instance
- Verified graph-dependent conclusions (Scenarios A, B, C)
- Wrote all documentation based on actual code inspection

---

## Tracks Entered

- **Track 01: Agents That Act on Connected Data** — Investigation agent traverses FalkorDB graph to discover multi-hop incident paths
- **Track 02: Agent Memory and Coordination** — Investigation results persisted in FalkorDB and retrieved in later sessions for context

---

## Links

- Demo video: https://drive.google.com/file/d/1X8Ibsx8a7RHDlJ7wu0fKHkXBozvE-jJj/view?usp=sharing
- Repository: https://github.com/AJ615/graphguard
- Blog: https://dev.to/aj615/how-we-used-falkordb-to-make-a-security-alert-explain-itself-3dbd