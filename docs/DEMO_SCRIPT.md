# GraphGuard — Demo Script (90–120 seconds)

**Purpose**: Hackathon demo for Graph Hacks by WeMakeDevs × FalkorDB  
**Mode**: Demo mode (no LLM API key required)  
**All data is synthetic** — no real security incidents, users, or production systems.

---

## Prerequisites (do before recording)

```powershell
# From i:\WeMakeDevs_Hackathon\graphguard\
docker compose up -d                          # FalkorDB running
.venv\Scripts\Activate.ps1
python -m backend.seed --reset                # Clean slate
uvicorn backend.main:app --port 8000          # Backend in terminal 1
streamlit run frontend/app.py                 # Frontend in terminal 2
```

Open browser: **http://localhost:8501**  
Open second browser tab: **http://localhost:8000/docs** (optional — to show API)

---

## Timed Narration

### [00:00–00:10] — Introduction

> "GraphGuard is an AI-powered security investigation assistant that uses FalkorDB — a graph database — as its reasoning layer. Instead of keyword matching, it traverses actual relationships to build evidence chains."

**Action**: Show Dashboard page. Point out: 76 nodes, 81 relationships, 12 alerts, 6 incidents.

---

### [00:10–00:30] — Scenario A: Connected Risk Alert

> "Let's investigate alert_001 — a TOR exit node connection. In demo mode, the agent runs real FalkorDB graph queries — no LLM required."

**Action**:
1. Click **Investigate** in sidebar
2. Select **"A — Connected Risk (alert_001)"** from dropdown
3. Click **🔍 Investigate**

**Expected output** (verified actual — from real FalkorDB):
- Risk: **CRITICAL** (score ≈ 0.80)
- Summary: *"Alert alert_001 (severity=critical) investigated. 1 historical incident(s) connected. 15 graph neighbors found."*
- Finding 1 (OBSERVED): "Alert alert_001 found: severity=critical, type=network_anomaly"
- Finding 2 (OBSERVED): "Found 15 connected entities: 2 devices, 1 users, 1 IPs."
- Finding 3 (INFERRED): "Found 2 historical incidents (1 confirmed) sharing entities"
- Related Incident: `inc_001` — "Credential Theft Campaign" (status: confirmed)
- Tool Execution Trace: `find_entity(alert_001)`, `find_related_entities(alert_001, depth=2)`, `find_similar_incidents(...)`, `get_related_investigations(...)`

> "The graph traversal found the 2-hop path: alert → dev_w005 → inc_001. That confirmed credential theft incident escalates the risk to CRITICAL. This is real FalkorDB data, not hard-coded output."

---

### [00:30–00:50] — Scenario B: Insufficient Evidence

> "Now let's investigate alert_003 — an off-hours admin login with the same investigation logic but a fundamentally different graph structure."

**Action**:
1. Select **"B — Insufficient Evidence (alert_003)"** from dropdown
2. Click **🔍 Investigate**

**Expected output**:
- Risk: **LOW or MEDIUM** (score ≈ 0.20)
- Summary: *"0 historical incident(s) connected. N graph neighbors found."*
- Missing Evidence: *"No historical incidents found sharing entities with this alert."*
- No related incidents listed
- Recommendation: "Monitor related entities..." (not escalate)

> "The graph for alert_003 — Carol's device WORKSTATION-003 — has no path to any known incident. The same algorithm, the same code — but a different graph structure produces a different risk conclusion. This proves FalkorDB is doing real work."

---

### [00:50–01:10] — Scenario C: Cross-Session Memory

> "Now let's show persistent memory. We investigate alert_004 — SMB lateral movement — and watch GraphGuard retrieve the prior investigation from FalkorDB."

**Action**:
1. Select **"C — Cross-Session Memory (alert_004)"** from dropdown
2. Click **🔍 Investigate**

**Expected output**:
- Finding (OBSERVED): "Found N prior investigation(s) for this alert. Most recent: [DEMO MODE] Alert alert_001..."
- Summary will reference previous investigation
- `get_related_investigations(alert_004)` appears in tool trace

> "alert_004 shares dev_w005 with alert_001. GraphGuard retrieved the prior investigation from FalkorDB memory — not from RAM, not from a local variable, but from the actual graph database."

---

### [01:10–01:20] — Graph Explorer (optional, if time permits)

> "We can also explore the raw graph structure."

**Action**:
1. Click **Graph Explorer**
2. Type `alert_001`, click Explore
3. Show the Plotly graph: alert at center, dev_w005, user_eve, inc_001, ev_001 surrounding it

---

### [01:20–01:30] — Closing

> "GraphGuard proves that FalkorDB is essential — not decorative. The relationship structure directly determines the investigation outcome. All data is synthetic. Full setup takes three commands. Thank you."

**Action**: Show the sidebar with 🟢 FalkorDB: ok.

---

## Fallback Plan

If FalkorDB is unavailable during the demo:

1. Show the pre-recorded test run output: `pytest tests/ -v` with all 25 passing
2. Show the backend code in `graph_tools.py` — the real Cypher queries
3. Show the `docs/GRAPH_MODEL_AND_QUERIES.md` — the schema
4. Manually walk the graph path in the documentation: `alert_001 → dev_w005 → inc_001`

If the backend crashes:
1. Navigate to `http://localhost:8000/docs` to show the API is live
2. Demonstrate via curl: `curl -X POST http://localhost:8000/api/investigations -H "Content-Type: application/json" -d "{\"alert_id\": \"alert_001\", \"tenant_id\": \"tenant_default\"}"`

---

## Reset Instructions (between demo takes)

```powershell
# Reset the graph to clean synthetic state without investigations
curl -X POST http://localhost:8000/api/seed -H "Content-Type: application/json" -d "{\"confirm\": true}"
# Or from Streamlit sidebar: click "Reset"
```

---

## What is Synthetic

ALL data in GraphGuard is synthetic:
- Users: Alice, Bob, Carol etc. — fictional employees
- Devices: WORKSTATION-001 through SERVER-DB-01 — fictional endpoints
- IP addresses: including 185.220.101.1 labeled "TOR-Exit" — fictional
- Incidents: e.g., "Credential Theft Campaign" — illustrative scenario only
- Evidence descriptions: e.g., "Mimikatz execution detected" — example log entries

No real persons, organizations, or security incidents are described.
