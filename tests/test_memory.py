"""Memory retrieval tests — integration (DB) and unit (mocked)."""
import os
import pytest
from unittest.mock import patch

os.environ.setdefault("FALKORDB_GRAPH", "graphguard_test")
os.environ.setdefault("LLM_PROVIDER", "demo")

try:
    from backend.graph_db import health_check
    FALKOR_AVAILABLE = health_check()["status"] == "ok"
except Exception:
    FALKOR_AVAILABLE = False

skip_if_no_db = pytest.mark.skipif(
    not FALKOR_AVAILABLE, reason="FalkorDB not available"
)


@skip_if_no_db
def test_cross_session_memory():
    """
    Scenario C: Save investigation for alert_001, then retrieve it
    when investigating alert_004 (same device dev_w005).
    """
    from backend.graph_tools import save_investigation
    from backend.memory import get_related_investigations
    from backend.seed import seed
    from backend.graph_db import get_graph

    g = get_graph()
    seed(g)

    # Session 1: save investigation for alert_001
    iid = "inv_memory_test_001"
    save_investigation(
        investigation_id=iid,
        session_id="session_A",
        tenant_id="tenant_default",
        alert_id="alert_001",
        risk_level="critical",
        risk_score=0.85,
        summary="Session A: TOR exit connection confirmed with lateral movement.",
        findings=[{
            "statement": "Confirmed credential theft path via dev_w005",
            "finding_type": "observed",
            "confidence": 0.95,
            "verification_status": "verified",
            "evidence_ids": ["ev_003"],
            "entity_ids": ["dev_w005", "inc_001"],
        }],
        recommended_actions=["Isolate dev_w005"],
        missing_evidence=[],
        timestamp="2024-01-15T10:00:00Z",
        mode="demo",
    )

    # Session 2: new investigation of alert_004 (shares dev_w005 with alert_001)
    related = get_related_investigations(
        alert_id="alert_004",
        entity_ids=["dev_w005", "user_eve"],
        tenant_id="tenant_default",
    )

    inv_ids = [r.get("entity_id", "") for r in related]
    assert iid in inv_ids, (
        f"Cross-session memory failed: {iid} not retrieved in session B. Got: {inv_ids}"
    )
