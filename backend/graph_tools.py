"""
Four essential graph tools exposed to the investigation agent.
All functions query FalkorDB directly; no results are invented.
"""
from __future__ import annotations
import logging
from typing import Any, Optional
from backend.graph_db import get_graph

logger = logging.getLogger(__name__)

MAX_DEPTH = 3
MAX_RESULTS = 50


# ── Tool 1: find_entity ────────────────────────────────────────────────────────

def find_entity(entity_id: str, tenant_id: str = "") -> dict[str, Any]:
    """Retrieve a node by its stable entity_id property."""
    g = get_graph()
    params = {"eid": entity_id}
    if tenant_id:
        cypher = (
            "MATCH (n {entity_id: $eid, tenant_id: $tid}) "
            "RETURN labels(n) AS lbl, properties(n) AS props LIMIT 1"
        )
        params["tid"] = tenant_id
    else:
        cypher = (
            "MATCH (n {entity_id: $eid}) "
            "RETURN labels(n) AS lbl, properties(n) AS props LIMIT 1"
        )
    result = g.query(cypher, params)
    if not result.result_set:
        return {"found": False, "entity_id": entity_id}
    row = result.result_set[0]
    labels = row[0]
    props = row[1]
    label = labels[0] if labels else "Unknown"
    return {
        "found": True,
        "entity_id": entity_id,
        "label": label,
        "properties": props,
        "tenant_id": props.get("tenant_id", ""),
    }


def _process_neighbor_row(
    row: list,
    tenant_id: str,
    rel_types: Optional[list[str]],
    results_by_id: dict,
) -> None:
    """Extract one result row from a neighbor query and insert into results_by_id."""
    lbl = row[0]
    props = row[1]
    rel_props = row[2] or {}
    rel_type = row[3] or "RELATED"
    label = lbl[0] if lbl else "Unknown"
    nid = props.get("entity_id", "")
    if not nid:
        return
    if tenant_id and props.get("tenant_id", "") not in ("", tenant_id):
        return
    if rel_types and rel_type not in rel_types:
        return
    if nid not in results_by_id:
        results_by_id[nid] = {
            "entity_id": nid,
            "label": label,
            "properties": props,
            "relationship": rel_type,
            "rel_properties": rel_props,
        }


# ── Tool 2: find_related_entities ─────────────────────────────────────────────

def find_related_entities(
    entity_id: str,
    rel_types: Optional[list[str]] = None,
    direction: str = "both",
    max_depth: int = 2,
    tenant_id: str = "",
    limit: int = 30,
) -> dict[str, Any]:
    """Explore connected nodes via real graph traversal (bounded depth)."""
    g = get_graph()
    depth = min(max_depth, MAX_DEPTH)
    limit = min(limit, MAX_RESULTS)

    # FalkorDB does not support last(r) on variable-length path results.
    # Use explicit depth-1 and depth-2 queries and deduplicate by entity_id.
    results_by_id: dict[str, dict] = {}

    if direction == "out":
        arrow1, arrow2 = "-[r]->", "-[r2]->"
    elif direction == "in":
        arrow1, arrow2 = "<-[r]-", "<-[r2]-"
    else:
        arrow1, arrow2 = "-[r]-", "-[r2]-"

    # Depth-1 query (always run)
    cypher_d1 = (
        f"MATCH (start {{entity_id: $eid}}){arrow1}(end) "
        "WHERE start <> end "
        "RETURN labels(end) AS lbl, properties(end) AS props, "
        "{} AS rel_props, type(r) AS rel_type "
        f"LIMIT {limit}"
    )
    try:
        r1 = g.query(cypher_d1, {"eid": entity_id})
        for row in r1.result_set:
            _process_neighbor_row(row, tenant_id, rel_types, results_by_id)
    except Exception as e:
        logger.warning("find_related_entities depth-1 error: %s", e)

    # Depth-2 query (when max_depth >= 2)
    if depth >= 2:
        cypher_d2 = (
            f"MATCH (start {{entity_id: $eid}}){arrow1}(mid){arrow2}(end) "
            "WHERE start <> end AND start <> mid AND mid <> end "
            "RETURN labels(end) AS lbl, properties(end) AS props, "
            "{} AS rel_props, type(r2) AS rel_type "
            f"LIMIT {limit}"
        )
        try:
            r2 = g.query(cypher_d2, {"eid": entity_id})
            for row in r2.result_set:
                _process_neighbor_row(row, tenant_id, rel_types, results_by_id)
        except Exception as e:
            logger.warning("find_related_entities depth-2 error: %s", e)

    neighbors = list(results_by_id.values())[:limit]
    return {"entity_id": entity_id, "neighbors": neighbors, "depth": depth}


# ── Tool 3: find_similar_incidents ────────────────────────────────────────────

def find_similar_incidents(
    entity_ids: list[str],
    tenant_id: str = "",
    limit: int = 5,
) -> dict[str, Any]:
    """
    Retrieve historical incidents connected through shared entities.
    Returns why each matched (shared entity), not just that it matched.
    """
    g = get_graph()
    limit = min(limit, 20)
    results = []

    for eid in entity_ids[:10]:  # bound input size
        cypher = (
            "MATCH (e {entity_id: $eid})-[*1..2]-(inc:Incident) "
            "RETURN properties(inc) AS inc_props, $eid AS via_entity "
            f"LIMIT {limit}"
        )
        params = {"eid": eid}
        try:
            res = g.query(cypher, params)
        except Exception as e:
            logger.warning("find_similar_incidents error for %s: %s", eid, e)
            continue

        for row in res.result_set:
            inc_props = row[0]
            via_entity = row[1]
            if tenant_id and inc_props.get("tenant_id", "") not in (
                "",
                tenant_id,
            ):
                continue
            inc_id = inc_props.get("entity_id", "")
            # Avoid duplicates
            if any(r["incident_id"] == inc_id for r in results):
                continue
            results.append(
                {
                    "incident_id": inc_id,
                    "properties": inc_props,
                    "match_reason": f"Shared entity: {via_entity}",
                    "verified": inc_props.get("status") == "confirmed",
                }
            )

    return {"similar_incidents": results, "count": len(results)}


# ── Tool 4: save_investigation ────────────────────────────────────────────────

def save_investigation(
    investigation_id: str,
    session_id: str,
    tenant_id: str,
    alert_id: str,
    risk_level: str,
    risk_score: float,
    summary: str,
    findings: list[dict],
    recommended_actions: list[str],
    missing_evidence: list[str],
    timestamp: str,
    mode: str,
) -> dict[str, Any]:
    """
    Persist the investigation to FalkorDB using safe MERGE (upsert).
    Also creates EXAMINED relationships to the alert node.
    """
    g = get_graph()
    try:
        # Upsert Investigation node
        cypher_inv = (
            "MERGE (inv:Investigation {entity_id: $iid}) "
            "SET inv.session_id = $sid, "
            "    inv.tenant_id = $tid, "
            "    inv.alert_id = $aid, "
            "    inv.risk_level = $rl, "
            "    inv.risk_score = $rs, "
            "    inv.summary = $summary, "
            "    inv.recommended_actions = $actions, "
            "    inv.missing_evidence = $missing, "
            "    inv.timestamp = $ts, "
            "    inv.mode = $mode "
            "RETURN inv"
        )
        g.query(
            cypher_inv,
            {
                "iid": investigation_id,
                "sid": session_id,
                "tid": tenant_id,
                "aid": alert_id,
                "rl": risk_level,
                "rs": risk_score,
                "summary": summary,
                "actions": recommended_actions,
                "missing": missing_evidence,
                "ts": timestamp,
                "mode": mode,
            },
        )

        # Link to Alert
        cypher_link = (
            "MATCH (inv:Investigation {entity_id: $iid}) "
            "MATCH (a:Alert {entity_id: $aid}) "
            "MERGE (inv)-[:EXAMINED]->(a)"
        )
        g.query(cypher_link, {"iid": investigation_id, "aid": alert_id})

        # Upsert findings as Finding nodes
        for i, f in enumerate(findings):
            fid = f.get("finding_id", f"{investigation_id}_f{i}")
            cypher_f = (
                "MERGE (fn:Finding {entity_id: $fid}) "
                "SET fn.statement = $stmt, "
                "    fn.finding_type = $ftype, "
                "    fn.confidence = $conf, "
                "    fn.verification_status = $vs, "
                "    fn.evidence_ids = $evids, "
                "    fn.entity_ids = $eids, "
                "    fn.investigation_id = $iid "
                "WITH fn "
                "MATCH (inv:Investigation {entity_id: $iid}) "
                "MERGE (inv)-[:DISCOVERED]->(fn)"
            )
            g.query(
                cypher_f,
                {
                    "fid": fid,
                    "stmt": f.get("statement", ""),
                    "ftype": f.get("finding_type", "observed"),
                    "conf": float(f.get("confidence", 0.0)),
                    "vs": f.get("verification_status", "unverified"),
                    "evids": f.get("evidence_ids", []),
                    "eids": f.get("entity_ids", []),
                    "iid": investigation_id,
                },
            )

        return {"saved": True, "investigation_id": investigation_id}
    except Exception as e:
        logger.error("save_investigation failed: %s", e)
        return {"saved": False, "investigation_id": investigation_id, "error": str(e)}


# ── Helper: get graph stats ────────────────────────────────────────────────────

def get_graph_stats() -> dict[str, Any]:
    g = get_graph()
    stats: dict[str, Any] = {}
    try:
        r = g.query("MATCH (n) RETURN count(n) AS cnt")
        stats["node_count"] = r.result_set[0][0] if r.result_set else 0
    except Exception:
        stats["node_count"] = -1
    try:
        r = g.query("MATCH ()-[r]->() RETURN count(r) AS cnt")
        stats["relationship_count"] = r.result_set[0][0] if r.result_set else 0
    except Exception:
        stats["relationship_count"] = -1
    try:
        r = g.query("MATCH (a:Alert) RETURN count(a) AS cnt")
        stats["alert_count"] = r.result_set[0][0] if r.result_set else 0
    except Exception:
        stats["alert_count"] = -1
    try:
        r = g.query("MATCH (i:Incident) RETURN count(i) AS cnt")
        stats["incident_count"] = r.result_set[0][0] if r.result_set else 0
    except Exception:
        stats["incident_count"] = -1
    try:
        r = g.query("MATCH (i:Investigation) RETURN count(i) AS cnt")
        stats["investigation_count"] = r.result_set[0][0] if r.result_set else 0
    except Exception:
        stats["investigation_count"] = -1
    return stats


def get_recent_investigations(tenant_id: str = "", limit: int = 10) -> list[dict]:
    g = get_graph()
    try:
        if tenant_id:
            cypher = (
                "MATCH (inv:Investigation {tenant_id: $tid}) "
                "RETURN properties(inv) AS props "
                "ORDER BY inv.timestamp DESC "
                f"LIMIT {limit}"
            )
            res = g.query(cypher, {"tid": tenant_id})
        else:
            cypher = (
                "MATCH (inv:Investigation) "
                "RETURN properties(inv) AS props "
                "ORDER BY inv.timestamp DESC "
                f"LIMIT {limit}"
            )
            res = g.query(cypher)
        return [row[0] for row in res.result_set]
    except Exception as e:
        logger.warning("get_recent_investigations error: %s", e)
        return []


def get_entity_neighbors(entity_id: str, tenant_id: str = "") -> list[dict]:
    g = get_graph()
    try:
        cypher = (
            "MATCH (n {entity_id: $eid})-[r]-(m) "
            "RETURN type(r) AS rel, labels(m) AS lbl, "
            "properties(m) AS props, properties(r) AS rprops "
            "LIMIT 50"
        )
        res = g.query(cypher, {"eid": entity_id})
        out = []
        for row in res.result_set:
            props = row[2]
            if tenant_id and props.get("tenant_id", "") not in ("", tenant_id):
                continue
            out.append(
                {
                    "relationship": row[0],
                    "label": row[1][0] if row[1] else "Unknown",
                    "properties": props,
                    "rel_properties": row[3] or {},
                }
            )
        return out
    except Exception as e:
        logger.warning("get_entity_neighbors error: %s", e)
        return []
