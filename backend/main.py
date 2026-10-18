"""FastAPI backend for GraphGuard."""
from __future__ import annotations
import logging
from typing import Any
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.graph_db import health_check
from backend.graph_tools import (
    find_entity,
    get_graph_stats,
    get_recent_investigations,
    get_entity_neighbors,
)
from backend.agent import run_investigation
from backend.schemas import (
    GraphStatsResponse,
    InvestigationRequest,
    InvestigationReport,
    InvestigationSummary,
    ResetRequest,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="GraphGuard API",
    description="AI-powered security investigation assistant backed by FalkorDB",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    db = health_check()
    llm_status = "enabled" if settings.is_llm_enabled else "demo"
    return {
        "status": "ok",
        "db": db,
        "llm": llm_status,
        "version": "0.1.0",
    }


@app.get("/api/graph/stats", response_model=GraphStatsResponse)
def graph_stats():
    try:
        stats = get_graph_stats()
        llm_status = "enabled" if settings.is_llm_enabled else "demo"
        return GraphStatsResponse(
            **stats,
            db_status="ok",
            llm_status=llm_status,
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/graph/entity/{entity_id}")
def get_entity(entity_id: str, tenant_id: str = ""):
    result = find_entity(entity_id, tenant_id)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
    return result


@app.get("/api/graph/entity/{entity_id}/neighbors")
def get_neighbors(entity_id: str, tenant_id: str = ""):
    neighbors = get_entity_neighbors(entity_id, tenant_id)
    return {"entity_id": entity_id, "neighbors": neighbors}


@app.post("/api/investigations", response_model=InvestigationReport)
def create_investigation(req: InvestigationRequest):
    try:
        report = run_investigation(
            alert_id=req.alert_id,
            query=req.query,
            tenant_id=req.tenant_id,
            session_id=req.session_id,
        )
        return report
    except Exception as e:
        logger.error("Investigation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/investigations")
def list_investigations(tenant_id: str = "", limit: int = 20):
    investigations = get_recent_investigations(tenant_id=tenant_id, limit=limit)
    summaries = []
    for inv in investigations:
        summaries.append(
            InvestigationSummary(
                investigation_id=inv.get("entity_id", ""),
                alert_id=inv.get("alert_id", ""),
                risk_level=inv.get("risk_level", "unknown"),
                summary=inv.get("summary", "")[:150],
                timestamp=inv.get("timestamp", ""),
                mode=inv.get("mode", "demo"),
                tenant_id=inv.get("tenant_id", ""),
            )
        )
    return summaries


@app.get("/api/investigations/{investigation_id}")
def get_investigation(investigation_id: str):
    result = find_entity(investigation_id)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail="Investigation not found")
    return result


@app.post("/api/seed")
def seed_data(req: ResetRequest = ResetRequest()):
    from backend.seed import seed, reset_and_seed
    try:
        if req.confirm:
            reset_and_seed()
            return {"status": "reset_and_seeded"}
        else:
            seed()
            return {"status": "seeded"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
