"""
frontend/dashboard_view.py

Executive Indian Legal Investigation Analytics & Intelligence Dashboard.
Visualizes real-time metrics strictly from authentic Indian case records, evidence custody,
timeline events, and verified judicial sources without mock data.
"""

import pandas as pd
import streamlit as st
from agent.analytics_engine import AnalyticsEngine
from agent.indian_legal_connector import IndianLegalConnector

analytics_engine = AnalyticsEngine()


def render_analytics_dashboard():
    """Render the Executive Indian Investigation Dashboard."""
    st.subheader("📊 Executive Indian Investigation Analytics & Legal Intelligence")
    st.caption("Live operational intelligence aggregated strictly from authentic Indian judicial records, case files, and evidence custody.")

    kpis = analytics_engine.get_kpi_summary()

    # Headline KPI Cards
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("🇮🇳 Indian Cases", kpis["total_cases"])
    col2.metric("🟢 Active (Open)", kpis["open_cases"])
    col3.metric("🔬 Evidence Vault", f"{kpis['total_evidence_items']} items ({kpis['storage_mb']} MB)")
    col4.metric("🧠 AI Analyses Run", kpis.get("total_ai_evals", 0))
    col5.metric("⏱️ Timeline Events", kpis["total_timeline_events"])

    st.divider()

    # Section: Verified Indian Courts & Sources
    st.markdown("#### ⚖️ Verified Indian Judicial Precedent Sources")
    sources = analytics_engine.get_verified_sources_summary()
    if sources:
        df_src = pd.DataFrame(sources)
        df_src.rename(
            columns={
                "source": "Legal / Government Source",
                "court": "Judicial Authority",
                "cases_count": "Indexed Records",
                "source_url": "Primary Citation / URL",
            },
            inplace=True,
        )
        st.dataframe(df_src, use_container_width=True, hide_index=True)
    else:
        st.info("No external Indian source records cataloged yet.")

    st.divider()

    # Breakdown Charts
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("#### 🏛️ Precedents by Indian Court / Authority")
        court_data = analytics_engine.get_indian_courts_distribution()
        if court_data:
            df_court = pd.DataFrame(
                list(court_data.items()), columns=["Judicial Court", "Precedent Count"]
            ).set_index("Judicial Court")
            st.bar_chart(df_court)
        else:
            st.info("No judicial court records available.")

        st.markdown("#### 📌 Cases by Investigation Status")
        status_data = analytics_engine.get_cases_by_status()
        if status_data:
            df_status = pd.DataFrame(
                list(status_data.items()), columns=["Status", "Case Count"]
            ).set_index("Status")
            st.bar_chart(df_status)
        else:
            st.info("No cases registered yet.")

    with chart_col2:
        st.markdown("#### 🏷️ Cases by Crime Classification")
        type_data = analytics_engine.get_cases_by_type()
        if type_data:
            df_type = pd.DataFrame(
                list(type_data.items()), columns=["Crime Type", "Case Count"]
            ).set_index("Crime Type")
            st.bar_chart(df_type)
        else:
            st.info("No crime classification data available.")

        st.markdown("#### 📦 Evidence Custody Format Distribution")
        ev_data = analytics_engine.get_evidence_by_type()
        if ev_data:
            df_ev = pd.DataFrame(
                list(ev_data.items()), columns=["Format", "Item Count"]
            ).set_index("Format")
            st.bar_chart(df_ev)
        else:
            st.info("No evidence cataloged yet.")

    st.divider()

    # Public Legal Gateway Live Connectivity Check (Requirement 5)
    with st.expander("🌐 Indian Public Legal Gateway Status (Live Connectivity)"):
        st.caption("Checks real-time connectivity to public Indian legal repositories. Never fabricates records when unavailable.")
        search_kw = st.text_input("Test Indian Legal Gateway Query", placeholder="e.g. Section 302 IPC Cyanide, Nithari", key="dash_legal_kw")
        if st.button("Query Public Gateway", key="btn_dash_query_legal"):
            with st.spinner("Connecting to Indian legal public gateway..."):
                res = IndianLegalConnector.query_public_indian_legal_gateway(search_kw)
                if res.get("status") == "SUCCESS":
                    st.success(res.get("message"))
                    for r in res.get("records", []):
                        st.markdown(f"- **{r['title']}** [{r['court_or_authority']} | {r['legal_citation']}]")
                else:
                    st.warning(f"⚠️ {res.get('message', 'Data source unavailable.')}")

    st.divider()

    # Recent Case Activity Feed
    st.markdown("#### ⏱️ Recent Case Activity Log")
    recent_cases = analytics_engine.get_recent_case_activity(limit=10)
    if recent_cases:
        df_recent = pd.DataFrame(recent_cases)
        df_recent.rename(
            columns={
                "case_id": "Case ID",
                "title": "Case Title",
                "case_type": "Classification",
                "status": "Status",
                "priority": "Priority",
                "assigned_investigator": "Lead Investigator",
                "updated_at": "Last Updated",
            },
            inplace=True,
        )
        st.dataframe(df_recent, use_container_width=True, hide_index=True)
    else:
        st.info("No recent case activity.")
