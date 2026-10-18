"""API endpoint tests using FastAPI TestClient. No DB required (mocked)."""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("FALKORDB_GRAPH", "graphguard_test")
os.environ.setdefault("LLM_PROVIDER", "demo")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("LLM_API_KEY", "")

from fastapi.testclient import TestClient

MOCK_REPORT = {
    "investigation_id": "inv_test001",
    "session_id": "sess_test",
    "tenant_id": "tenant_default",
    "alert_id": "alert_001",
    "risk_level": "high",
    "risk_score": 0.72,
    "summary": "Test summary",
    "findings": [],
    "recommended_actions": [],
    "missing_evidence": [],
    "related_incidents": [],
    "tool_calls_made": [],
    "mode": "demo",
    "timestamp": "2024-01-15T10:00:00Z",
    "saved": True,
}


@patch("backend.graph_db.health_check", return_value={"status": "ok", "graph": "graphguard_test"})
def test_health_endpoint(mock_hc):
    from backend.main import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


@patch("backend.main.get_graph_stats", return_value={"node_count": 100, "relationship_count": 200, "alert_count": 12, "incident_count": 6, "investigation_count": 3})
def test_graph_stats_endpoint(mock_stats):
    from backend.main import app
    client = TestClient(app)
    r = client.get("/api/graph/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["node_count"] == 100
    assert data["alert_count"] == 12


@patch("backend.main.find_entity", return_value={"found": True, "entity_id": "alert_001", "label": "Alert", "properties": {"severity": "critical"}, "tenant_id": "tenant_default"})
def test_get_entity_found(mock_find):
    from backend.main import app
    client = TestClient(app)
    r = client.get("/api/graph/entity/alert_001")
    assert r.status_code == 200
    assert r.json()["entity_id"] == "alert_001"


@patch("backend.main.find_entity", return_value={"found": False, "entity_id": "bad_id"})
def test_get_entity_not_found(mock_find):
    from backend.main import app
    client = TestClient(app)
    r = client.get("/api/graph/entity/bad_id")
    assert r.status_code == 404


@patch("backend.main.run_investigation")
def test_create_investigation(mock_run):
    from backend.schemas import InvestigationReport
    from datetime import datetime, timezone
    mock_run.return_value = InvestigationReport(**{**MOCK_REPORT, "timestamp": datetime.now(timezone.utc)})
    from backend.main import app
    client = TestClient(app)
    r = client.post("/api/investigations", json={"alert_id": "alert_001", "tenant_id": "tenant_default"})
    assert r.status_code == 200
    data = r.json()
    assert data["risk_level"] == "high"
    assert data["mode"] == "demo"


@patch("backend.main.get_recent_investigations", return_value=[])
def test_list_investigations_empty(mock_inv):
    from backend.main import app
    client = TestClient(app)
    r = client.get("/api/investigations")
    assert r.status_code == 200
    assert r.json() == []
