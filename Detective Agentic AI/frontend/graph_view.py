"""
frontend/graph_view.py

Interactive Streamlit view for the Case Connection & Entity Relationship Graph.
Visualizes verified relationships between Cases, Persons, Evidence, Locations, Organizations, and Events.

RULE (Part 14):
Only displays relationships supported by stored information.
"""

import pandas as pd
import streamlit as st
from agent.graph_engine import RelationshipGraphEngine
from agent.case_engine import CaseEngine

graph_engine = RelationshipGraphEngine()
case_engine = CaseEngine()

NODE_ICONS = {
    "Case": "📁",
    "Person": "👤",
    "Evidence": "🔬",
    "Location": "📍",
    "Organization": "🏢",
    "Event": "⏱️",
}


def render_relationship_graph():
    """Render the Case Connection and Relationship Graph interface."""
    st.subheader("🕸️ Case Connection & Entity Relationship Network")
    st.caption("Visual correlation of verified links between Cases, Suspects, Evidence, Locations, and Organizations.")

    all_cases = case_engine.list_cases()
    if not all_cases:
        st.info("No cases registered yet to construct a connection graph.")
        return

    c_select_opts = ["🌐 Entire Repository Network"] + [f"{c.case_id} -- {c.title}" for c in all_cases]
    sel_scope = st.selectbox("Select Graph Focus", options=c_select_opts, key="graph_scope_select")

    if "Entire Repository" in sel_scope:
        graph_data = graph_engine.build_global_network()
        st.info(f"📊 **Global Network:** {graph_data.get('node_count', 0)} entities and {graph_data.get('edge_count', 0)} verified connections across all active cases.")
    else:
        cid = sel_scope.split(" -- ")[0].strip()
        graph_data = graph_engine.build_case_subgraph(cid)
        st.info(f"📊 **Case Subgraph:** {len(graph_data['nodes'])} connected entities and {len(graph_data['edges'])} relational edges.")

    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    g_col1, g_col2 = st.columns([1, 2])

    with g_col1:
        st.markdown("#### 🧩 Network Entities (Nodes)")
        if not nodes:
            st.caption("No entity nodes found.")
        else:
            node_types = sorted(list(set(n.get("type", "Unknown") for n in nodes)))
            sel_node_type = st.multiselect("Filter Entity Types", options=node_types, default=node_types, key="graph_filter_nodes")
            
            filtered_nodes = [n for n in nodes if n.get("type") in sel_node_type]
            for n in filtered_nodes:
                icon = NODE_ICONS.get(n.get("type"), "⚪")
                st.markdown(f"{icon} **{n.get('type')}:** {n.get('label')}")

    with g_col2:
        st.markdown("#### 🔗 Relational Connections (Edges)")
        if not edges:
            st.info("No connections mapped for the selected entities.")
        else:
            edge_rows = []
            for e in edges:
                edge_rows.append({
                    "Source Entity": e.get("source"),
                    "Relationship": f"== {e.get('relation')} ==>",
                    "Target Entity": e.get("target"),
                    "Context Label": e.get("label", ""),
                })
            df_edges = pd.DataFrame(edge_rows)
            st.dataframe(df_edges, use_container_width=True, hide_index=True)

            st.caption("All displayed relationships are ground-truth links extracted directly from active case files, registered evidence hashes, and suspect links.")
