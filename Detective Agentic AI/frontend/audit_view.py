"""
frontend/audit_view.py

Interactive Streamlit view for the Immutable Audit Trail.
Enables administrators to inspect system access, case modifications, evidence uploads,
RAG queries, and payment verifications with tamper-evident metadata.
"""

import json
import pandas as pd
import streamlit as st
from services.audit_service import get_audit_service

audit_service = get_audit_service()


def render_audit_trail_view():
    """Render the Immutable Audit Trail inspection interface."""
    st.subheader("🛡️ Immutable Audit Trail & Compliance Log")
    st.caption("Cryptographically sequenced, append-only activity log for forensic accountability and regulatory compliance.")

    total_logs = audit_service.get_total_count()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Recorded Events", total_logs)
    col2.metric("Storage Status", "Append-Only (WAL SQLite)")
    col3.metric("Integrity Guard", "Immutable / Non-Destructive")

    st.divider()

    f1, f2, f3 = st.columns([2, 2, 1])
    with f1:
        search_user = st.text_input("Filter by Actor / Username", placeholder="e.g. admin, investigator", key="audit_filter_user")
    with f2:
        search_action = st.text_input("Filter by Action Type", placeholder="e.g. LOGIN, CASE_CREATED, EVIDENCE_UPLOAD", key="audit_filter_action")
    with f3:
        max_rows = st.selectbox("Show Limit", options=[50, 100, 200, 500], index=1, key="audit_limit_select")

    logs = audit_service.query_logs(
        username=search_user.strip() if search_user else None,
        action=search_action.strip() if search_action else None,
        limit=max_rows,
    )

    if not logs:
        st.info("No audit logs matching the current filter criteria.")
        return

    st.write(f"Showing **{len(logs)}** most recent audit entries:")

    # Table format
    table_rows = [
        {
            "Timestamp": l.timestamp,
            "Log ID": l.log_id,
            "Actor": l.username,
            "Action": l.action,
            "Target Object": l.target_object,
            "Result": l.result,
        }
        for l in logs
    ]
    df_logs = pd.DataFrame(table_rows)
    st.dataframe(df_logs, use_container_width=True, hide_index=True)

    # Detailed expandable view
    with st.expander("🔍 Inspect Full Event Payloads (Metadata & Forensic JSON)"):
        selected_log_id = st.selectbox(
            "Select Event ID to view detailed payload",
            options=[l.log_id for l in logs],
            key="audit_sel_detail_log",
        )
        selected_log = next((l for l in logs if l.log_id == selected_log_id), None)
        if selected_log:
            c_d1, c_d2 = st.columns(2)
            with c_d1:
                st.markdown(f"**Log ID:** `{selected_log.log_id}`")
                st.markdown(f"**Actor:** `{selected_log.username}`")
                st.markdown(f"**Action:** `{selected_log.action}`")
                st.markdown(f"**Timestamp:** `{selected_log.timestamp}`")
                st.markdown(f"**Target:** `{selected_log.target_object}`")
                st.markdown(f"**Result Status:** `{selected_log.result}`")
            with c_d2:
                st.markdown("**Structured Details / Payload:**")
                st.json(selected_log.details)

    # Export CSV
    csv_bytes = df_logs.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Export Filtered Audit Trail (CSV)",
        data=csv_bytes,
        file_name=f"audit_trail_export_{len(logs)}_records.csv",
        mime="text/csv",
        key="btn_export_audit_csv",
    )
