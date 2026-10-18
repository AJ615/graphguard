"""
GraphGuard — Streamlit frontend.
Dark security-ops UI connecting to the FastAPI backend.
"""
from __future__ import annotations
import os
import requests
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="GraphGuard — AI Security Investigation",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #0a0e1a;
    color: #e2e8f0;
}

.stApp { background-color: #0a0e1a; }

.metric-card {
    background: linear-gradient(135deg, #1a2035 0%, #1e2a45 100%);
    border: 1px solid #2d3a55;
    border-radius: 12px;
    padding: 1.2rem;
    margin: 0.4rem 0;
}

.risk-critical { color: #ff4757; font-weight: 700; }
.risk-high     { color: #ff6b35; font-weight: 700; }
.risk-medium   { color: #ffa502; font-weight: 600; }
.risk-low      { color: #2ed573; font-weight: 600; }
.risk-unknown  { color: #747d8c; }

.finding-observed     { border-left: 3px solid #3498db; padding-left: 0.8rem; }
.finding-inferred     { border-left: 3px solid #f39c12; padding-left: 0.8rem; }
.finding-recommendation { border-left: 3px solid #2ecc71; padding-left: 0.8rem; }

.stButton>button {
    background: linear-gradient(135deg, #6c5ce7, #a855f7);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.6rem 1.5rem;
    transition: all 0.2s;
}
.stButton>button:hover { opacity: 0.9; transform: translateY(-1px); }

.tool-call-badge {
    display: inline-block;
    background: #1a2035;
    border: 1px solid #3d4f6e;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.75rem;
    font-family: 'JetBrains Mono', monospace;
    margin: 2px;
    color: #7ec8f5;
}

.mode-badge-demo { background: #1a3550; color: #7ec8f5; border: 1px solid #3a6b8a; 
                   border-radius: 6px; padding: 2px 10px; font-size: 0.8rem; }
.mode-badge-llm  { background: #1a3520; color: #7ef58c; border: 1px solid #3a8a50;
                   border-radius: 6px; padding: 2px 10px; font-size: 0.8rem; }

h1, h2, h3 { color: #e2e8f0 !important; }
.stSelectbox label, .stTextInput label, .stTextArea label { color: #a0aec0 !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def api_get(path: str, params: dict = {}) -> dict | list | None:
    try:
        r = requests.get(f"{BACKEND}{path}", params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error ({path}): {e}")
        return None


def api_post(path: str, body: dict) -> dict | None:
    try:
        r = requests.post(f"{BACKEND}{path}", json=body, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error ({path}): {e}")
        return None


def risk_color(level: str) -> str:
    return {
        "critical": "#ff4757",
        "high": "#ff6b35",
        "medium": "#ffa502",
        "low": "#2ed573",
    }.get(level, "#747d8c")


def risk_emoji(level: str) -> str:
    return {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }.get(level, "⚪")


def build_graph_figure(entity_id: str, neighbors: list[dict]) -> go.Figure:
    """Build a Plotly network graph from entity + neighbors."""
    import math

    nodes_x, nodes_y, node_labels, node_colors, node_text = [], [], [], [], []
    edge_x, edge_y = [], []

    color_map = {
        "Alert": "#ff4757", "Incident": "#ff6b35", "User": "#3498db",
        "Device": "#2ecc71", "IPAddress": "#f39c12", "Evidence": "#9b59b6",
        "Service": "#1abc9c", "Investigation": "#e74c3c", "Finding": "#16a085",
        "Decision": "#d35400",
    }

    # Center node
    nodes_x.append(0)
    nodes_y.append(0)
    node_labels.append(entity_id[:16])
    node_colors.append("#6c5ce7")
    node_text.append(f"<b>{entity_id}</b><br>Root entity")

    n = len(neighbors)
    for i, nb in enumerate(neighbors[:30]):
        angle = 2 * math.pi * i / max(n, 1)
        r = 1.5 + (i % 3) * 0.4
        nx = r * math.cos(angle)
        ny = r * math.sin(angle)
        nodes_x.append(nx)
        nodes_y.append(ny)
        lbl = nb.get("label", "?")
        nid = nb.get("entity_id", nb.get("properties", {}).get("entity_id", "?"))
        rel = nb.get("relationship", "")
        node_labels.append(nid[:14])
        node_colors.append(color_map.get(lbl, "#747d8c"))
        node_text.append(f"<b>{nid}</b><br>Type: {lbl}<br>Rel: {rel}")
        edge_x += [0, nx, None]
        edge_y += [0, ny, None]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=edge_x, y=edge_y, mode="lines",
            line=dict(width=1, color="#2d3a55"),
            hoverinfo="none",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=nodes_x, y=nodes_y, mode="markers+text",
            marker=dict(size=18, color=node_colors, line=dict(width=1.5, color="#1a2035")),
            text=node_labels,
            textposition="top center",
            textfont=dict(size=9, color="#e2e8f0"),
            hovertext=node_text,
            hoverinfo="text",
        )
    )
    fig.update_layout(
        showlegend=False,
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#0a0e1a",
        height=450,
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛡️ **GraphGuard**")
    st.markdown("*AI Security Investigation Assistant*")
    st.divider()

    health = api_get("/health")
    if health:
        db_status = health.get("db", {}).get("status", "unknown")
        llm_status = health.get("llm", "unknown")
        db_icon = "🟢" if db_status == "ok" else "🔴"
        llm_icon = "🟢" if llm_status == "enabled" else "🔵"
        st.markdown(f"{db_icon} **FalkorDB**: `{db_status}`")
        st.markdown(f"{llm_icon} **LLM**: `{llm_status}`")
    else:
        st.error("Backend unreachable")

    st.divider()
    page = st.radio(
        "Navigate",
        ["📊 Dashboard", "🔍 Investigate", "🗺️ Graph Explorer", "📜 History"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("**Quick Seed**")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("Seed", key="btn_seed", use_container_width=True):
            r = api_post("/api/seed", {})
            if r:
                st.success("Seeded!")
    with col_s2:
        if st.button("Reset", key="btn_reset", use_container_width=True):
            r = api_post("/api/seed", {"confirm": True})
            if r:
                st.success("Reset!")


# ── DASHBOARD ─────────────────────────────────────────────────────────────────
if page == "📊 Dashboard":
    st.markdown("# 📊 GraphGuard Dashboard")
    st.markdown("*Real-time security graph metrics from FalkorDB*")
    st.divider()

    stats = api_get("/api/graph/stats")
    if stats:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("🗂️ Total Nodes", stats.get("node_count", 0))
        c2.metric("🔗 Relationships", stats.get("relationship_count", 0))
        c3.metric("🚨 Alerts", stats.get("alert_count", 0))
        c4.metric("⚡ Incidents", stats.get("incident_count", 0))
        c5.metric("🔍 Investigations", stats.get("investigation_count", 0))

    st.divider()
    st.markdown("### 📋 Recent Investigations")
    recent = api_get("/api/investigations", {"limit": 10})
    if recent:
        for inv in recent:
            rl = inv.get("risk_level", "unknown")
            with st.container():
                col1, col2, col3, col4 = st.columns([2, 1, 1, 3])
                col1.markdown(f"`{inv.get('investigation_id', '')[:20]}`")
                col2.markdown(
                    f"<span class='risk-{rl}'>{risk_emoji(rl)} {rl.upper()}</span>",
                    unsafe_allow_html=True,
                )
                col3.markdown(f"`{inv.get('alert_id', '')}`")
                col4.markdown(inv.get("summary", "")[:100])
    else:
        st.info("No investigations yet. Run one from the Investigate page.")

    st.divider()
    st.markdown("### 🗺️ Demo Scenarios")
    st.markdown(
        """
| Scenario | Alert | Description |
|---|---|---|
| **A — Connected Risk** | `alert_001` | TOR connection → device → confirmed credential theft incident |
| **B — Insufficient Evidence** | `alert_003` | Off-hours login with no corroborating graph path |
| **C — Cross-Session Memory** | `alert_004` | SMB lateral movement; retrieves prior investigation of `alert_001` |
"""
    )


# ── INVESTIGATE ───────────────────────────────────────────────────────────────
elif page == "🔍 Investigate":
    st.markdown("# 🔍 Investigation Console")
    st.divider()

    col_a, col_b = st.columns([1, 2])
    with col_a:
        scenario = st.selectbox(
            "Demo Scenario",
            [
                "Custom",
                "A — Connected Risk (alert_001)",
                "B — Insufficient Evidence (alert_003)",
                "C — Cross-Session Memory (alert_004)",
            ],
        )
        demo_map = {
            "A — Connected Risk (alert_001)": ("alert_001", "Investigate this alert for multi-hop connected risk."),
            "B — Insufficient Evidence (alert_003)": ("alert_003", "Assess available evidence for this alert."),
            "C — Cross-Session Memory (alert_004)": ("alert_004", "Investigate, pulling in historical investigation context."),
        }
        if scenario != "Custom":
            default_alert, default_query = demo_map[scenario]
        else:
            default_alert, default_query = "", ""

        alert_id = st.text_input("Alert ID", value=default_alert)
        tenant_id = st.text_input("Tenant ID", value="tenant_default")

    with col_b:
        query = st.text_area(
            "Investigation Query (optional)",
            value=default_query,
            height=100,
        )

    if st.button("🔍 Investigate", key="btn_investigate"):
        if not alert_id:
            st.error("Please enter an Alert ID.")
        else:
            with st.spinner("Querying FalkorDB and running investigation..."):
                report = api_post(
                    "/api/investigations",
                    {"alert_id": alert_id, "query": query, "tenant_id": tenant_id, "session_id": ""},
                )

            if report:
                rl = report.get("risk_level", "unknown")
                rs = report.get("risk_score", 0.0)
                mode = report.get("mode", "demo")
                saved = report.get("saved", False)

                # Header
                st.divider()
                header_cols = st.columns([3, 1, 1, 1])
                header_cols[0].markdown(
                    f"### {risk_emoji(rl)} Investigation `{report.get('investigation_id', '')[:20]}`"
                )
                header_cols[1].markdown(
                    f"<span class='risk-{rl}'>{rl.upper()}</span>",
                    unsafe_allow_html=True,
                )
                header_cols[2].metric("Score", f"{rs:.2f}")
                header_cols[3].markdown(
                    f"{'✅ Saved' if saved else '❌ Not saved'}"
                )

                mode_label = "demo" if mode == "demo" else "llm"
                st.markdown(
                    f"<span class='mode-badge-{mode_label}'>{'🤖 DEMO MODE — Deterministic, no LLM' if mode == 'demo' else '✨ LLM MODE'}</span>",
                    unsafe_allow_html=True,
                )

                # Summary
                st.markdown("#### Summary")
                st.info(report.get("summary", ""))

                # Findings
                st.markdown("#### Findings")
                for f in report.get("findings", []):
                    ftype = f.get("finding_type", "observed")
                    conf = f.get("confidence", 0.0)
                    vs = f.get("verification_status", "")
                    with st.expander(
                        f"[{ftype.upper()}] {f.get('statement', '')[:80]}",
                        expanded=True,
                    ):
                        st.markdown(
                            f"<div class='finding-{ftype}'>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f.get("statement", ""))
                        cols = st.columns(3)
                        cols[0].metric("Confidence", f"{conf:.0%}")
                        cols[1].markdown(f"**Status**: {vs}")
                        eids = f.get("evidence_ids", [])
                        if eids:
                            cols[2].markdown(f"**Evidence**: {', '.join(eids[:3])}")
                        path = f.get("graph_path", [])
                        if path:
                            st.markdown(
                                f"**Graph path**: `{'→'.join(path[:6])}`"
                            )
                        hist = f.get("historical_investigation_ids", [])
                        if hist:
                            st.markdown(f"**Related investigations**: {', '.join(hist[:3])}")
                        st.markdown("</div>", unsafe_allow_html=True)

                # Actions & Missing
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    st.markdown("#### Recommended Actions")
                    for act in report.get("recommended_actions", []):
                        st.markdown(f"- {act}")
                with col_r2:
                    missing = report.get("missing_evidence", [])
                    if missing:
                        st.markdown("#### Missing Evidence")
                        for m in missing:
                            st.markdown(f"⚠️ {m}")

                # Related Incidents
                rel_inc = report.get("related_incidents", [])
                if rel_inc:
                    st.markdown("#### Related Historical Incidents")
                    for inc in rel_inc[:5]:
                        props = inc.get("properties", inc)
                        iid = inc.get("incident_id", props.get("entity_id", "?"))
                        iname = props.get("name", "Unknown")
                        istatus = props.get("status", "?")
                        ireason = inc.get("match_reason", "")
                        st.markdown(
                            f"- **{iname}** (`{iid}`) — *{istatus}* | {ireason}"
                        )

                # Tool calls
                tool_calls = report.get("tool_calls_made", [])
                if tool_calls:
                    st.markdown("#### Tool Execution Trace")
                    badges = " ".join(
                        f"<span class='tool-call-badge'>{tc}</span>"
                        for tc in tool_calls
                    )
                    st.markdown(badges, unsafe_allow_html=True)

                # Store for graph explorer
                st.session_state["last_alert_id"] = alert_id


# ── GRAPH EXPLORER ────────────────────────────────────────────────────────────
elif page == "🗺️ Graph Explorer":
    st.markdown("# 🗺️ Graph Explorer")
    st.markdown("*Explore the FalkorDB knowledge graph*")
    st.divider()

    default_eid = st.session_state.get("last_alert_id", "alert_001")
    entity_id = st.text_input("Entity ID to explore", value=default_eid)

    if st.button("Explore", key="btn_explore"):
        entity = api_get(f"/api/graph/entity/{entity_id}")
        neighbors_data = api_get(f"/api/graph/entity/{entity_id}/neighbors")

        if entity:
            st.markdown(f"### Entity: `{entity_id}`")
            props = entity.get("properties", {})
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Type**: {entity.get('label', 'Unknown')}")
                for k, v in list(props.items())[:8]:
                    if k != "tenant_id":
                        st.markdown(f"**{k}**: `{v}`")
            with col2:
                if neighbors_data:
                    neighbors = neighbors_data.get("neighbors", [])
                    st.markdown(f"**{len(neighbors)} direct neighbors**")
                    if neighbors:
                        fig = build_graph_figure(entity_id, neighbors)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No direct neighbors found.")
        else:
            st.warning(f"Entity `{entity_id}` not found. Try seeding the database first.")

    # Legend
    with st.expander("Node Type Legend"):
        legend = {
            "Alert": "#ff4757", "Incident": "#ff6b35", "User": "#3498db",
            "Device": "#2ecc71", "IPAddress": "#f39c12", "Evidence": "#9b59b6",
            "Service": "#1abc9c", "Investigation": "#e74c3c",
        }
        cols = st.columns(4)
        for i, (lbl, color) in enumerate(legend.items()):
            cols[i % 4].markdown(
                f"<span style='color:{color}'>●</span> {lbl}",
                unsafe_allow_html=True,
            )


# ── HISTORY ───────────────────────────────────────────────────────────────────
elif page == "📜 History":
    st.markdown("# 📜 Investigation History")
    st.markdown("*Persisted investigations retrieved from FalkorDB*")
    st.divider()

    tenant_id = st.text_input("Filter by Tenant ID (leave blank for all)", value="")
    history = api_get("/api/investigations", {"tenant_id": tenant_id, "limit": 50})

    if history:
        st.markdown(f"**{len(history)} investigations found**")
        selected = st.selectbox(
            "Select investigation to inspect",
            options=[h.get("investigation_id", "") for h in history],
            format_func=lambda x: f"{x[:20]} — {next((h.get('risk_level','?') for h in history if h.get('investigation_id') == x), '?')}",
        )
        if selected:
            inv = api_get(f"/api/investigations/{selected}")
            if inv:
                props = inv.get("properties", inv)
                rl = props.get("risk_level", "unknown")
                st.markdown(f"### {risk_emoji(rl)} `{selected}`")
                st.markdown(f"**Alert**: `{props.get('alert_id', '?')}`")
                st.markdown(f"**Risk**: {rl.upper()} (score: {props.get('risk_score', 0):.2f})")
                st.markdown(f"**Timestamp**: {props.get('timestamp', 'N/A')}")
                st.markdown(f"**Mode**: {props.get('mode', 'N/A')}")
                st.markdown("**Summary**")
                st.info(props.get("summary", "No summary available."))
                actions = props.get("recommended_actions", [])
                if actions:
                    st.markdown("**Recommended Actions**")
                    for a in actions:
                        st.markdown(f"- {a}")
    else:
        st.info("No history yet. Create some investigations first.")
