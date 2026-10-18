# TASKS.md

## Completed (Verified During Audit 2026-10-16)

- [x] Project structure, requirements, docker-compose, .gitignore, .env.example
- [x] `backend/config.py` — Pydantic settings with env support
- [x] `backend/graph_db.py` — FalkorDB connection + health check
- [x] `backend/schemas.py` — All request/response models
- [x] `backend/graph_tools.py` — 4 tools (find_entity, find_related_entities, find_similar_incidents, save_investigation)
  - [x] **CRITICAL FIX**: Replaced `last(r)` on variable-length paths with explicit depth-1/2 queries
- [x] `backend/memory.py` — Persistent memory retrieval from FalkorDB
- [x] `backend/agent.py` — Demo + Anthropic LLM agent
- [x] `backend/seed.py` — Deterministic seed (76 nodes, 81 relationships)
- [x] `backend/main.py` — FastAPI endpoints
- [x] `frontend/app.py` — Streamlit dark security UI (4 pages)
- [x] `tests/test_agent.py` — Unit tests (5 tests, all PASS)
- [x] `tests/test_api.py` — API unit tests (6 tests, all PASS)
- [x] `tests/test_graph_tools.py` — Integration tests (14 tests, all PASS)
- [x] `tests/test_memory.py` — Memory integration test (PASS)
- [x] FalkorDB connectivity verified (health check ok)
- [x] Seed idempotency verified
- [x] Scenario A: alert_001 → dev_w005 → inc_001 path verified
- [x] Scenario B: alert_003 no incident path verified
- [x] Scenario C: cross-session memory retrieval verified
- [x] Tenant isolation verified (`test_tenant_isolation` PASS)
- [x] README.md — submission-ready with all required sections
- [x] `docs/GRAPH_MODEL_AND_QUERIES.md` — schema + actual Cypher
- [x] `docs/TEST_REPORT.md` — full test audit results
- [x] `docs/DEMO_SCRIPT.md` — timestamped demo narration
- [x] `docs/JUDGE_PREP.md` — Q&A for judges
- [x] `docs/FINAL_AUDIT_REPORT.md` — PASS/FAIL status for all requirements
- [x] PROJECT_STATUS.md updated
- [x] TASKS.md updated

## Pending (Required for Submission)

- [ ] **P0**: Record demo video (90–120 seconds, follow `docs/DEMO_SCRIPT.md`)
- [ ] **P0**: Publish public GitHub repository — push code, verify README renders
- [ ] **P1**: Start full stack and manually verify UI (backend + frontend + Scenarios A/B/C)
- [ ] **P1**: Test graph-unavailable error (stop FalkorDB, run investigation, verify error)
- [ ] **P2**: Add repo URL + video URL to README

## Optional / Post-Submission

- [ ] OpenAI provider integration
- [ ] Dockerfile for backend
- [ ] Index on `entity_id` in FalkorDB for production scale
- [ ] Full tenant filtering at each depth-2 hop

## Blocked

- None currently
