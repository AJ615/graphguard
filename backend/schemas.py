"""Pydantic schemas for request/response validation."""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


# ── Request schemas ────────────────────────────────────────────────────────────

class InvestigationRequest(BaseModel):
    alert_id: str
    query: str = ""
    tenant_id: str = "tenant_default"
    session_id: str = ""


class ResetRequest(BaseModel):
    confirm: bool = False


# ── Response schemas ───────────────────────────────────────────────────────────

class Finding(BaseModel):
    statement: str
    finding_type: str  # observed | inferred | recommendation
    confidence: float = 0.0
    verification_status: str = "unverified"
    evidence_ids: list[str] = []
    entity_ids: list[str] = []
    graph_path: list[str] = []
    historical_investigation_ids: list[str] = []


class InvestigationReport(BaseModel):
    investigation_id: str
    session_id: str
    tenant_id: str
    alert_id: str
    risk_level: str  # critical | high | medium | low | unknown
    risk_score: float
    summary: str
    findings: list[Finding] = []
    recommended_actions: list[str] = []
    missing_evidence: list[str] = []
    related_incidents: list[dict] = []
    tool_calls_made: list[str] = []
    mode: str  # llm | demo
    timestamp: datetime = Field(default_factory=_now_utc)
    saved: bool = False


class EntityResponse(BaseModel):
    entity_id: str
    label: str
    properties: dict[str, Any]
    tenant_id: str


class NeighborResponse(BaseModel):
    entity: EntityResponse
    relationship: str
    direction: str  # in | out
    rel_properties: dict[str, Any] = {}


class GraphStatsResponse(BaseModel):
    node_count: int
    relationship_count: int
    alert_count: int
    incident_count: int
    investigation_count: int
    db_status: str
    llm_status: str


class InvestigationSummary(BaseModel):
    investigation_id: str
    alert_id: str
    risk_level: str
    summary: str
    timestamp: str
    mode: str
    tenant_id: str
