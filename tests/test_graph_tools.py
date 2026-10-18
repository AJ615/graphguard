"""
Integration tests for graph tools.
Requires a running FalkorDB instance and seeded data.
Skip automatically if FalkorDB is unavailable.
"""
import pytest
import os

# Point tests to local FalkorDB
os.environ.setdefault("FALKORDB_HOST", "localhost")
os.environ.setdefault("FALKORDB_GRAPH", "graphguard_test")
os.environ.setdefault("LLM_PROVIDER", "demo")
os.environ.setdefault("DEMO_MODE", "true")

try:
    from backend.graph_db import get_graph, health_check
    from backend.graph_tools import (
        find_entity,
        find_related_entities,
        find_similar_incidents,
        save_investigation,
        get_graph_stats,
    )
    from backend.seed import seed, reset_and_seed
    FALKOR_AVAILABLE = health_check()["status"] == "ok"
except Exception:
    FALKOR_AVAILABLE = False

skip_if_no_db = pytest.mark.skipif(
    not FALKOR_AVAILABLE, reason="FalkorDB not available"
)


@skip_if_no_db
def test_db_connectivity():
    result = health_check()
    assert result["status"] == "ok"


@skip_if_no_db
def test_seed_idempotent():
    """Seed twice — should not raise and node counts should be stable."""
    g = get_graph()
    seed(g)
    stats1 = get_graph_stats()
    seed(g)  # second seed — MERGE = no duplicates
    stats2 = get_graph_stats()
    assert stats1["node_count"] == stats2["node_count"], (
        f"Node count changed after re-seed: {stats1} vs {stats2}"
    )


@skip_if_no_db
def test_find_entity_found():
    g = get_graph()
    seed(g)
    result = find_entity("alert_001", "tenant_default")
    assert result["found"] is True
    assert result["label"] == "Alert"
    assert result["properties"]["severity"] == "critical"


@skip_if_no_db
def test_find_entity_not_found():
    result = find_entity("nonexistent_xyz_999")
    assert result["found"] is False


@skip_if_no_db
def test_find_related_entities_has_neighbors():
    g = get_graph()
    seed(g)
    result = find_related_entities("alert_001", max_depth=2, tenant_id="tenant_default")
    neighbors = result.get("neighbors", [])
    assert len(neighbors) > 0, "Expected alert_001 to have neighbors"


@skip_if_no_db
def test_find_related_entities_depth_bound():
    result = find_related_entities("alert_001", max_depth=10)
    assert result.get("depth", 0) <= 3  # MAX_DEPTH cap


@skip_if_no_db
def test_find_similar_incidents_returns_results():
    g = get_graph()
    seed(g)
    # dev_w005 is connected to inc_001
    result = find_similar_incidents(["dev_w005"], tenant_id="tenant_default")
    incidents = result.get("similar_incidents", [])
    assert any(i["incident_id"] == "inc_001" for i in incidents), (
        "Expected inc_001 to appear via dev_w005"
    )


@skip_if_no_db
def test_find_similar_incidents_no_path():
    """Alert from scenario B (alert_003) should not find inc_001."""
    result = find_similar_incidents(["dev_w003"], tenant_id="tenant_default")
    incidents = result.get("similar_incidents", [])
    inc_ids = [i["incident_id"] for i in incidents]
    assert "inc_001" not in inc_ids, (
        "dev_w003 should not link to inc_001 (Scenario B)"
    )


@skip_if_no_db
def test_save_investigation_and_retrieve():
    from backend.graph_tools import find_entity
    iid = "test_inv_001"
    result = save_investigation(
        investigation_id=iid,
        session_id="test_sess",
        tenant_id="tenant_default",
        alert_id="alert_001",
        risk_level="high",
        risk_score=0.72,
        summary="Test investigation for pytest",
        findings=[{"statement": "Test finding", "finding_type": "observed",
                   "confidence": 0.9, "verification_status": "verified",
                   "evidence_ids": [], "entity_ids": ["alert_001"]}],
        recommended_actions=["Monitor closely"],
        missing_evidence=[],
        timestamp="2024-01-15T10:30:00Z",
        mode="demo",
    )
    assert result["saved"] is True
    # Retrieve and verify
    entity = find_entity(iid)
    assert entity["found"] is True
    assert entity["properties"]["risk_level"] == "high"


@skip_if_no_db
def test_tenant_isolation():
    """Entities from a different tenant should not appear in filtered queries."""
    result = find_entity("alert_001", tenant_id="tenant_other")
    # alert_001 has tenant_id = tenant_default, so should NOT be found
    # when tenant filter is enforced
    # Note: find_entity enforces tenant match when tenant_id is provided
    assert result["found"] is False


@skip_if_no_db
def test_graph_stats_has_nodes():
    g = get_graph()
    seed(g)
    stats = get_graph_stats()
    assert stats["node_count"] > 0
    assert stats["alert_count"] >= 12
    assert stats["incident_count"] >= 6


@skip_if_no_db
def test_scenario_a_connected_risk():
    """
    Scenario A: alert_001 → dev_w005 → inc_001 (confirmed incident).
    The graph must return inc_001 when traversing from alert_001's entities.
    """
    g = get_graph()
    seed(g)
    # Get alert entity IDs
    neighbors = find_related_entities("alert_001", max_depth=2)
    neighbor_ids = [n["entity_id"] for n in neighbors.get("neighbors", [])]
    # Find incidents via connected entities
    similar = find_similar_incidents(["alert_001"] + neighbor_ids[:4])
    inc_ids = [i["incident_id"] for i in similar.get("similar_incidents", [])]
    assert "inc_001" in inc_ids, (
        f"Scenario A: inc_001 not found via graph traversal. Got: {inc_ids}"
    )


@skip_if_no_db
def test_scenario_b_no_incident_link():
    """
    Scenario B: alert_003 (Carol/dev_w003) has no incident link.
    Must not return inc_001.
    """
    g = get_graph()
    seed(g)
    neighbors = find_related_entities("alert_003", max_depth=2)
    neighbor_ids = [n["entity_id"] for n in neighbors.get("neighbors", [])]
    similar = find_similar_incidents(["alert_003"] + neighbor_ids[:4])
    inc_ids = [i["incident_id"] for i in similar.get("similar_incidents", [])]
    assert "inc_001" not in inc_ids, (
        f"Scenario B: inc_001 should NOT appear for alert_003. Got: {inc_ids}"
    )
