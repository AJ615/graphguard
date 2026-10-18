"""
Persistent investigation memory — stored in FalkorDB.
Retrieves historical investigations related to the current query.
"""
from __future__ import annotations
import logging
from backend.graph_db import get_graph

logger = logging.getLogger(__name__)


def get_related_investigations(
    alert_id: str,
    entity_ids: list[str],
    tenant_id: str = "",
    limit: int = 5,
) -> list[dict]:
    """
    Retrieve past investigations related by:
    - Same alert
    - Shared examined entity (Finding -> entity_id overlap)
    """
    g = get_graph()
    results: list[dict] = []
    seen: set[str] = set()

    # 1. Same alert
    try:
        cypher = (
            "MATCH (inv:Investigation {alert_id: $aid}) "
            "RETURN properties(inv) AS props "
            "ORDER BY inv.timestamp DESC "
            f"LIMIT {limit}"
        )
        params: dict = {"aid": alert_id}
        if tenant_id:
            cypher = (
                "MATCH (inv:Investigation {alert_id: $aid, tenant_id: $tid}) "
                "RETURN properties(inv) AS props "
                "ORDER BY inv.timestamp DESC "
                f"LIMIT {limit}"
            )
            params["tid"] = tenant_id
        res = g.query(cypher, params)
        for row in res.result_set:
            props = row[0]
            iid = props.get("entity_id", "")
            if iid and iid not in seen:
                seen.add(iid)
                results.append({**props, "match_reason": "Same alert"})
    except Exception as e:
        logger.warning("get_related_investigations (same alert) error: %s", e)

    # 2. Shared entities via findings
    for eid in entity_ids[:5]:
        if len(results) >= limit:
            break
        try:
            cypher2 = (
                "MATCH (inv:Investigation)-[:DISCOVERED]->(fn:Finding) "
                "WHERE $eid IN fn.entity_ids "
                "RETURN properties(inv) AS props "
                f"LIMIT {limit}"
            )
            res2 = g.query(cypher2, {"eid": eid})
            for row in res2.result_set:
                props = row[0]
                iid = props.get("entity_id", "")
                if iid and iid not in seen:
                    seen.add(iid)
                    results.append(
                        {**props, "match_reason": f"Shared entity: {eid}"}
                    )
        except Exception as e:
            logger.warning(
                "get_related_investigations (shared entity %s): %s", eid, e
            )

    return results[:limit]
