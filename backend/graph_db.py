"""FalkorDB connection management."""
from __future__ import annotations
import logging
from typing import Optional
import falkordb
from backend.config import settings

logger = logging.getLogger(__name__)

_db_instance: Optional[falkordb.FalkorDB] = None
_graph_instance = None


def get_db() -> falkordb.FalkorDB:
    global _db_instance
    if _db_instance is None:
        kwargs: dict = {
            "host": settings.falkordb_host,
            "port": settings.falkordb_port,
        }
        if settings.falkordb_password:
            kwargs["password"] = settings.falkordb_password
        _db_instance = falkordb.FalkorDB(**kwargs)
        logger.info(
            "Connected to FalkorDB at %s:%s",
            settings.falkordb_host,
            settings.falkordb_port,
        )
    return _db_instance


def get_graph():
    global _graph_instance
    if _graph_instance is None:
        db = get_db()
        _graph_instance = db.select_graph(settings.falkordb_graph)
    return _graph_instance


def reset_connection():
    """Force reconnect (use after reset)."""
    global _db_instance, _graph_instance
    _db_instance = None
    _graph_instance = None


def health_check() -> dict:
    try:
        g = get_graph()
        result = g.query("RETURN 1 AS ok")
        return {"status": "ok", "graph": settings.falkordb_graph}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
