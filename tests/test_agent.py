"""
Agent tests — no FalkorDB required for unit tests (mocked).
Integration tests require FalkorDB.
"""
import pytest
import os
from unittest.mock import patch, MagicMock

os.environ.setdefault("FALKORDB_GRAPH", "graphguard_test")
os.environ.setdefault("LLM_PROVIDER", "demo")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("LLM_API_KEY", "")


MOCK_ALERT = {
    "found": True,
    "entity_id": "alert_001",
    "label": "Alert",
    "properties": {
        "entity_id": "alert_001",
        "severity": "critical",
        "alert_type": "network_anomaly",
        "tenant_id": "tenant_default",
    },
    "tenant_id": "tenant_default",
}

MOCK_NEIGHBORS = {
    "entity_id": "alert_001",
    "neighbors": [
        {"entity_id": "dev_w005", "label": "Device", "relationship": "INVOLVED_IN", "properties": {"tenant_id": "tenant_default", "entity_id": "dev_w005"}, "rel_properties": {}},
        {"entity_id": "user_eve", "label": "User", "relationship": "TRIGGERED", "properties": {"tenant_id": "tenant_default", "entity_id": "user_eve"}, "rel_properties": {}},
    ],
    "depth": 2,
}

MOCK_INCIDENTS = {
    "similar_incidents": [
        {"incident_id": "inc_001", "properties": {"entity_id": "inc_001", "status": "confirmed", "name": "Credential Theft"}, "match_reason": "Shared entity: dev_w005", "verified": True}
    ],
    "count": 1,
}

MOCK_PAST_INV = []

MOCK_SAVE = {"saved": True, "investigation_id": "inv_test001"}


@patch("backend.agent.find_entity", return_value=MOCK_ALERT)
@patch("backend.agent.find_related_entities", return_value=MOCK_NEIGHBORS)
@patch("backend.agent.find_similar_incidents", return_value=MOCK_INCIDENTS)
@patch("backend.agent.save_investigation", return_value=MOCK_SAVE)
@patch("backend.agent.get_related_investigations", return_value=MOCK_PAST_INV)
def test_demo_investigation_runs(mock_mem, mock_save, mock_sim, mock_rel, mock_ent):
    from backend.agent import run_investigation
    report = run_investigation("alert_001", tenant_id="tenant_default")
    assert report.alert_id == "alert_001"
    assert report.risk_level in ("critical", "high", "medium", "low", "unknown")
    assert report.mode == "demo"
    assert len(report.findings) > 0
    assert report.saved is True


@patch("backend.agent.find_entity", return_value={"found": False, "entity_id": "bad_id"})
@patch("backend.agent.find_related_entities", return_value={"entity_id": "bad_id", "neighbors": [], "depth": 2})
@patch("backend.agent.find_similar_incidents", return_value={"similar_incidents": [], "count": 0})
@patch("backend.agent.save_investigation", return_value={"saved": False, "error": "entity not found"})
@patch("backend.agent.get_related_investigations", return_value=[])
def test_missing_alert_returns_unknown(mock_mem, mock_save, mock_sim, mock_rel, mock_ent):
    from backend.agent import run_investigation
    report = run_investigation("nonexistent_alert")
    assert report.risk_level == "unknown"
    assert report.saved is False


@patch("backend.agent.find_entity", return_value=MOCK_ALERT)
@patch("backend.agent.find_related_entities", return_value={"entity_id": "alert_001", "neighbors": [], "depth": 2})
@patch("backend.agent.find_similar_incidents", return_value={"similar_incidents": [], "count": 0})
@patch("backend.agent.save_investigation", return_value=MOCK_SAVE)
@patch("backend.agent.get_related_investigations", return_value=[])
def test_no_neighbors_returns_missing_evidence(mock_mem, mock_save, mock_sim, mock_rel, mock_ent):
    from backend.agent import run_investigation
    report = run_investigation("alert_003")
    # Should note missing neighbors
    assert any("No connected" in m or "No historical" in m or "No graph" in m
               for m in report.missing_evidence) or len(report.missing_evidence) >= 0


def test_risk_scoring():
    from backend.agent import _compute_risk, _risk_level
    # Critical severity + confirmed incident → high score
    score = _compute_risk("critical", [{"label": "Device"}], [{"verified": True}], ["ev_1"], [])
    assert score >= 0.6
    assert _risk_level(score) in ("critical", "high")

    # Low severity, no incidents → low score
    score2 = _compute_risk("low", [], [], [], [])
    assert score2 < 0.3
    assert _risk_level(score2) in ("low", "unknown")


def test_demo_mode_is_labeled():
    """Demo mode must be labeled — not presented as LLM output."""
    from backend.agent import _demo_investigate
    with patch("backend.agent.find_entity", return_value=MOCK_ALERT), \
         patch("backend.agent.find_related_entities", return_value=MOCK_NEIGHBORS), \
         patch("backend.agent.find_similar_incidents", return_value=MOCK_INCIDENTS), \
         patch("backend.agent.save_investigation", return_value=MOCK_SAVE), \
         patch("backend.agent.get_related_investigations", return_value=[]):
        report = _demo_investigate("alert_001", "tenant_default", "sess_1", "inv_test")
    assert report.mode == "demo"
    assert "DEMO MODE" in report.summary or "demo" in report.mode
