"""
GraphGuard investigation agent.
Supports two modes:
  - demo: deterministic workflow using real FalkorDB queries, no LLM call.
  - llm:  LLM tool-calling with Anthropic or OpenAI, bounded to MAX_TOOL_CALLS.
"""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.config import settings
from backend.graph_tools import (
    find_entity,
    find_related_entities,
    find_similar_incidents,
    save_investigation,
)
from backend.memory import get_related_investigations
from backend.schemas import Finding, InvestigationReport

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 8

SYSTEM_PROMPT = """You are GraphGuard, an evidence-driven security investigation agent.
Use FalkorDB as your persistent context layer.
Investigate alerts by following actual graph relationships, exploring relevant multi-hop connections, and retrieving historical investigations.
You must use graph tools before making conclusions.
Never invent entities, edges, incidents, evidence IDs, or query results.
Distinguish verified facts, inferred risks, and recommendations.
Treat historical hypotheses as unverified until supported by appropriate evidence.
Cite actual entity IDs, relationship types, and evidence IDs.
Explain the relationship path that supports each important conclusion.
Identify missing information and uncertainty.
Respect tenant boundaries.
Never claim that an investigation was saved unless the database operation succeeded.
Never modify production security systems. Provide recommendations only.
Stop when sufficient evidence has been gathered or the investigation reaches its tool-call limit."""

# Tool definitions for Anthropic tool-calling
TOOL_DEFINITIONS = [
    {
        "name": "find_entity",
        "description": "Retrieve a node by entity_id from FalkorDB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "tenant_id": {"type": "string", "default": ""},
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "find_related_entities",
        "description": "Explore connected nodes via graph traversal (bounded depth).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "rel_types": {"type": "array", "items": {"type": "string"}},
                "direction": {"type": "string", "default": "both"},
                "max_depth": {"type": "integer", "default": 2},
                "tenant_id": {"type": "string", "default": ""},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["entity_id"],
        },
    },
    {
        "name": "find_similar_incidents",
        "description": "Retrieve historical incidents connected through shared entities.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_ids": {"type": "array", "items": {"type": "string"}},
                "tenant_id": {"type": "string", "default": ""},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["entity_ids"],
        },
    },
]

# ── Tool dispatcher ────────────────────────────────────────────────────────────

def _dispatch_tool(name: str, inputs: dict) -> Any:
    if name == "find_entity":
        return find_entity(**inputs)
    elif name == "find_related_entities":
        return find_related_entities(**inputs)
    elif name == "find_similar_incidents":
        return find_similar_incidents(**inputs)
    else:
        return {"error": f"Unknown tool: {name}"}


# ── Deterministic demo workflow ────────────────────────────────────────────────

def _demo_investigate(
    alert_id: str,
    tenant_id: str,
    session_id: str,
    investigation_id: str,
) -> InvestigationReport:
    """
    Deterministic investigation using real FalkorDB queries.
    Labeled clearly as demo mode — not an LLM output.
    """
    tool_calls: list[str] = []
    findings: list[Finding] = []
    recommended_actions: list[str] = []
    missing_evidence: list[str] = []
    related_incidents: list[dict] = []
    all_entity_ids: list[str] = []

    # Step 1: Fetch the alert
    alert = find_entity(alert_id, tenant_id)
    tool_calls.append(f"find_entity({alert_id})")

    if not alert.get("found"):
        return InvestigationReport(
            investigation_id=investigation_id,
            session_id=session_id,
            tenant_id=tenant_id,
            alert_id=alert_id,
            risk_level="unknown",
            risk_score=0.0,
            summary=f"Alert {alert_id} not found in graph.",
            findings=[],
            recommended_actions=["Verify alert ID and re-seed the database."],
            missing_evidence=["Alert entity not in graph"],
            tool_calls_made=tool_calls,
            mode="demo",
        )

    all_entity_ids.append(alert_id)
    alert_props = alert.get("properties", {})
    severity = alert_props.get("severity", "unknown")

    findings.append(
        Finding(
            statement=f"Alert {alert_id} found: severity={severity}, "
            f"type={alert_props.get('alert_type', 'unknown')}",
            finding_type="observed",
            confidence=1.0,
            verification_status="verified",
            evidence_ids=alert_props.get("evidence_ids", []),
            entity_ids=[alert_id],
            graph_path=[alert_id],
        )
    )

    # Step 2: Explore alert neighbors (depth 2)
    neighbors = find_related_entities(
        alert_id, max_depth=2, tenant_id=tenant_id, limit=30
    )
    tool_calls.append(f"find_related_entities({alert_id}, depth=2)")
    neighbor_list = neighbors.get("neighbors", [])
    devices = []
    users = []
    ips = []
    evidence_ids: list[str] = []

    for n in neighbor_list:
        nid = n.get("entity_id", "")
        lbl = n.get("label", "")
        all_entity_ids.append(nid)
        if lbl == "Device":
            devices.append(n)
        elif lbl == "User":
            users.append(n)
        elif lbl == "IPAddress":
            ips.append(n)
        elif lbl == "Evidence":
            evidence_ids.append(nid)

    if neighbor_list:
        findings.append(
            Finding(
                statement=f"Found {len(neighbor_list)} connected entities: "
                f"{len(devices)} devices, {len(users)} users, {len(ips)} IPs.",
                finding_type="observed",
                confidence=1.0,
                verification_status="verified",
                entity_ids=[n.get("entity_id", "") for n in neighbor_list],
                graph_path=[alert_id] + [n.get("entity_id", "") for n in neighbor_list[:5]],
            )
        )
    else:
        missing_evidence.append("No connected entities found within 2 hops of alert.")

    # Step 3: Find similar incidents via connected entities
    if all_entity_ids:
        sim = find_similar_incidents(all_entity_ids[:5], tenant_id=tenant_id)
        tool_calls.append(f"find_similar_incidents({all_entity_ids[:3]})")
        related_incidents = sim.get("similar_incidents", [])
        if related_incidents:
            confirmed = [i for i in related_incidents if i.get("verified")]
            findings.append(
                Finding(
                    statement=f"Found {len(related_incidents)} historical incidents "
                    f"({len(confirmed)} confirmed) sharing entities with this alert.",
                    finding_type="inferred",
                    confidence=0.75,
                    verification_status="unverified",
                    entity_ids=all_entity_ids[:5],
                    historical_investigation_ids=[
                        i.get("incident_id", "") for i in related_incidents[:3]
                    ],
                )
            )
        else:
            missing_evidence.append("No historical incidents found sharing entities with this alert.")

    # Step 4: Retrieve persistent memory
    past = get_related_investigations(alert_id, all_entity_ids, tenant_id=tenant_id)
    tool_calls.append(f"get_related_investigations({alert_id})")
    if past:
        findings.append(
            Finding(
                statement=f"Found {len(past)} prior investigation(s) for this alert. "
                f"Most recent: {past[0].get('summary', 'N/A')[:100]}",
                finding_type="observed",
                confidence=1.0,
                verification_status="verified",
                historical_investigation_ids=[p.get("entity_id", "") for p in past[:3]],
            )
        )

    # Step 5: Compute heuristic risk score
    risk_score = _compute_risk(severity, devices, related_incidents, evidence_ids, past)
    risk_level = _risk_level(risk_score)

    # Step 6: Recommendations
    recommended_actions = _build_recommendations(
        risk_level, devices, users, related_incidents, missing_evidence
    )

    summary = (
        f"[DEMO MODE] Alert {alert_id} (severity={severity}) investigated. "
        f"Risk: {risk_level} (score={risk_score:.2f}). "
        f"{len(related_incidents)} historical incident(s) connected. "
        f"{len(neighbor_list)} graph neighbors found."
    )

    # Add recommendation finding
    if recommended_actions:
        findings.append(
            Finding(
                statement="; ".join(recommended_actions[:3]),
                finding_type="recommendation",
                confidence=0.8,
                verification_status="unverified",
                entity_ids=all_entity_ids[:3],
            )
        )

    return InvestigationReport(
        investigation_id=investigation_id,
        session_id=session_id,
        tenant_id=tenant_id,
        alert_id=alert_id,
        risk_level=risk_level,
        risk_score=risk_score,
        summary=summary,
        findings=findings,
        recommended_actions=recommended_actions,
        missing_evidence=missing_evidence,
        related_incidents=related_incidents,
        tool_calls_made=tool_calls,
        mode="demo",
    )


def _compute_risk(
    severity: str,
    devices: list,
    incidents: list,
    evidence_ids: list,
    past_investigations: list,
) -> float:
    """
    Heuristic risk score (0.0–1.0).
    Labeled as heuristic — not a calibrated security score.
    """
    score = 0.0
    sev_map = {"critical": 0.5, "high": 0.35, "medium": 0.2, "low": 0.1}
    score += sev_map.get(severity.lower(), 0.15)
    confirmed_incidents = [i for i in incidents if i.get("verified")]
    score += min(len(confirmed_incidents) * 0.15, 0.3)
    score += min(len(devices) * 0.05, 0.1)
    score += min(len(evidence_ids) * 0.03, 0.09)
    score += min(len(past_investigations) * 0.03, 0.06)
    return min(round(score, 2), 1.0)


def _risk_level(score: float) -> str:
    if score >= 0.7:
        return "critical"
    elif score >= 0.5:
        return "high"
    elif score >= 0.3:
        return "medium"
    elif score >= 0.1:
        return "low"
    return "unknown"


def _build_recommendations(
    risk_level: str,
    devices: list,
    users: list,
    incidents: list,
    missing: list,
) -> list[str]:
    actions = []
    if risk_level in ("critical", "high"):
        actions.append("Escalate to Tier 2 security analyst for immediate review.")
        if devices:
            actions.append(f"Isolate device(s): {', '.join(d.get('entity_id','?') for d in devices[:2])}")
        if users:
            actions.append(f"Review user activity: {', '.join(u.get('entity_id','?') for u in users[:2])}")
    elif risk_level == "medium":
        actions.append("Monitor related entities for further suspicious activity.")
        if incidents:
            actions.append("Cross-reference with confirmed incident response playbooks.")
    else:
        actions.append("Log for low-priority review. No immediate action required.")
    if missing:
        actions.append(f"Collect missing evidence: {'; '.join(missing[:2])}")
    return actions


# ── LLM workflow ───────────────────────────────────────────────────────────────

def _llm_investigate_anthropic(
    alert_id: str,
    query: str,
    tenant_id: str,
    session_id: str,
    investigation_id: str,
) -> InvestigationReport:
    """LLM tool-calling investigation via Anthropic."""
    try:
        import anthropic
    except ImportError:
        logger.error("anthropic package not installed")
        return _demo_investigate(alert_id, tenant_id, session_id, investigation_id)

    client = anthropic.Anthropic(api_key=settings.llm_api_key)
    messages = [
        {
            "role": "user",
            "content": (
                f"Investigate alert {alert_id} for tenant {tenant_id}. "
                f"Additional context: {query or 'None'}. "
                "Use graph tools to discover relationships, retrieve historical incidents, "
                "and provide an evidence-backed risk assessment."
            ),
        }
    ]

    tool_calls_made: list[str] = []
    tool_results_log: list[dict] = []
    call_count = 0

    while call_count < MAX_TOOL_CALLS:
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason != "tool_use":
            break

        # Process tool calls
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_use_blocks:
            break

        messages.append({"role": "assistant", "content": response.content})

        tool_result_content = []
        for block in tool_use_blocks:
            tool_name = block.name
            tool_input = {**block.input, "tenant_id": tenant_id}
            result = _dispatch_tool(tool_name, tool_input)
            tool_calls_made.append(f"{tool_name}({list(block.input.keys())})")
            tool_results_log.append({"tool": tool_name, "result": result})
            tool_result_content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                }
            )
            call_count += 1
            if call_count >= MAX_TOOL_CALLS:
                break

        messages.append({"role": "user", "content": tool_result_content})

    # Extract final text from LLM
    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text = block.text
            break

    # Build structured report from LLM output + tool results
    return _build_report_from_llm(
        alert_id=alert_id,
        investigation_id=investigation_id,
        session_id=session_id,
        tenant_id=tenant_id,
        tool_calls_made=tool_calls_made,
        tool_results_log=tool_results_log,
        llm_summary=final_text,
    )


def _build_report_from_llm(
    alert_id: str,
    investigation_id: str,
    session_id: str,
    tenant_id: str,
    tool_calls_made: list[str],
    tool_results_log: list[dict],
    llm_summary: str,
) -> InvestigationReport:
    """Build a structured report from LLM tool results and final text."""
    findings: list[Finding] = []
    related_incidents: list[dict] = []
    missing_evidence: list[str] = []
    all_entity_ids: list[str] = []

    for entry in tool_results_log:
        result = entry["result"]
        tool = entry["tool"]

        if tool == "find_entity" and result.get("found"):
            props = result.get("properties", {})
            findings.append(
                Finding(
                    statement=f"Entity {result.get('entity_id')} ({result.get('label')}): "
                    f"severity={props.get('severity', 'N/A')}",
                    finding_type="observed",
                    confidence=1.0,
                    verification_status="verified",
                    entity_ids=[result.get("entity_id", "")],
                )
            )
            all_entity_ids.append(result.get("entity_id", ""))

        elif tool == "find_related_entities":
            neighbors = result.get("neighbors", [])
            if neighbors:
                for n in neighbors:
                    all_entity_ids.append(n.get("entity_id", ""))
                findings.append(
                    Finding(
                        statement=f"Graph traversal found {len(neighbors)} neighbors.",
                        finding_type="observed",
                        confidence=1.0,
                        verification_status="verified",
                        entity_ids=[n.get("entity_id", "") for n in neighbors[:10]],
                    )
                )
            else:
                missing_evidence.append("No graph neighbors found.")

        elif tool == "find_similar_incidents":
            incidents = result.get("similar_incidents", [])
            related_incidents.extend(incidents)
            if incidents:
                findings.append(
                    Finding(
                        statement=f"Found {len(incidents)} historically related incident(s).",
                        finding_type="inferred",
                        confidence=0.75,
                        verification_status="unverified",
                        historical_investigation_ids=[i.get("incident_id", "") for i in incidents[:3]],
                    )
                )

    # LLM summary as a finding
    if llm_summary:
        findings.append(
            Finding(
                statement=llm_summary[:500],
                finding_type="recommendation",
                confidence=0.7,
                verification_status="unverified",
                entity_ids=all_entity_ids[:5],
            )
        )

    # Derive risk from same heuristic
    severity = "medium"
    for f in findings:
        if "critical" in f.statement.lower():
            severity = "critical"
        elif "high" in f.statement.lower() and severity != "critical":
            severity = "high"

    risk_score = _compute_risk(severity, [], related_incidents, [], [])
    risk_level = _risk_level(risk_score)

    return InvestigationReport(
        investigation_id=investigation_id,
        session_id=session_id,
        tenant_id=tenant_id,
        alert_id=alert_id,
        risk_level=risk_level,
        risk_score=risk_score,
        summary=llm_summary[:300] if llm_summary else f"LLM investigation of {alert_id}.",
        findings=findings,
        recommended_actions=["Review LLM findings and verify with SOC analyst."],
        missing_evidence=missing_evidence,
        related_incidents=related_incidents,
        tool_calls_made=tool_calls_made,
        mode="llm",
    )


# ── Public entry point ─────────────────────────────────────────────────────────

def run_investigation(
    alert_id: str,
    query: str = "",
    tenant_id: str = "tenant_default",
    session_id: str = "",
) -> InvestigationReport:
    """
    Main entry. Routes to demo or LLM mode.
    Always calls real graph tools.
    Persists the investigation to FalkorDB on completion.
    """
    investigation_id = f"inv_{uuid.uuid4().hex[:12]}"
    session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"
    timestamp = datetime.now(timezone.utc).isoformat()

    if settings.is_llm_enabled and settings.llm_provider == "anthropic":
        report = _llm_investigate_anthropic(
            alert_id, query, tenant_id, session_id, investigation_id
        )
    else:
        if not settings.is_llm_enabled and not settings.demo_mode:
            logger.warning(
                "LLM not configured and DEMO_MODE=false — falling back to demo mode."
            )
        report = _demo_investigate(alert_id, tenant_id, session_id, investigation_id)

    # Persist regardless of mode
    save_result = save_investigation(
        investigation_id=investigation_id,
        session_id=session_id,
        tenant_id=tenant_id,
        alert_id=alert_id,
        risk_level=report.risk_level,
        risk_score=report.risk_score,
        summary=report.summary,
        findings=[f.model_dump() for f in report.findings],
        recommended_actions=report.recommended_actions,
        missing_evidence=report.missing_evidence,
        timestamp=timestamp,
        mode=report.mode,
    )
    report.saved = save_result.get("saved", False)
    if not report.saved:
        logger.error(
            "Investigation %s could not be persisted: %s",
            investigation_id,
            save_result.get("error"),
        )

    return report
