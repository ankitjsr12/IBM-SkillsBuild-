"""
frontend/anomaly_view.py

Interactive Streamlit view for the Anomaly Detection Module.
Detects temporal inconsistencies, evidence duplicate collisions, unexpected frequencies, and sequence gaps.

MANDATORY DIRECTIVE (Part 13):
Do NOT claim that an anomaly proves wrongdoing.
All detections must be framed as "Potential anomaly detected".
"""

import streamlit as st
from agent.anomaly_engine import AnomalyEngine
from agent.case_engine import CaseEngine

anomaly_engine = AnomalyEngine()
case_engine = CaseEngine()

SEVERITY_BADGES = {
    "CRITICAL": "🔴 CRITICAL",
    "HIGH": "🟠 HIGH",
    "MEDIUM": "🟡 MEDIUM",
    "LOW": "🔵 LOW",
}


def render_anomaly_dashboard():
    """Render the Anomaly Detection user interface."""
    st.subheader("⚠️ Investigative Anomaly Analysis")
    st.caption("Automated detection of temporal gaps, evidence collisions, burst frequencies, and sequence irregularities.")

    st.warning(
        "**INVESTIGATIVE DIRECTIVE:** The anomalies flagged below indicate structural, temporal, "
        "or evidentiary irregularities in the recorded data. They do NOT prove wrongdoing or bad faith. "
        "All detections require independent human investigator verification."
    )

    all_cases = case_engine.list_cases()
    case_choices = ["🌐 ALL CASES (Global Scan)"] + [f"{c.case_id} -- {c.title}" for c in all_cases]
    sel_scan = st.selectbox("Select Scope for Anomaly Analysis", options=case_choices, key="anom_scope_select")

    with st.spinner("Executing rule-based anomaly scans across records..."):
        if "ALL CASES" in sel_scan:
            anomalies = anomaly_engine.scan_global_anomalies()
        else:
            cid = sel_scan.split(" -- ")[0].strip()
            anomalies = anomaly_engine.scan_case_anomalies(cid)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Anomalies Flagged", len(anomalies))
    c2.metric("High / Critical Severity", sum(1 for a in anomalies if a.get("severity") in ("HIGH", "CRITICAL")))
    c3.metric("Medium Severity", sum(1 for a in anomalies if a.get("severity") == "MEDIUM"))
    c4.metric("Low Severity", sum(1 for a in anomalies if a.get("severity") == "LOW"))

    st.divider()

    if not anomalies:
        st.success("✅ No structural, temporal, or evidentiary anomalies detected for the selected scope.")
    else:
        st.write(f"Displaying **{len(anomalies)}** potential anomaly findings:")
        for idx, a in enumerate(anomalies, 1):
            sev = a.get("severity", "LOW")
            badge = SEVERITY_BADGES.get(sev, "⚪ INFO")
            
            with st.expander(f"{badge} | {a['anomaly']} (Target: {a['target']})", expanded=(sev in ("HIGH", "CRITICAL"))):
                st.markdown(f"**Anomaly Finding:** `{a['anomaly']}`")
                st.markdown(f"**Target Entity:** `{a['target']}`")
                st.markdown(f"**Assessed Severity:** `{sev}`")
                st.markdown(f"**Analytical Reason:**\n{a['reason']}")
                if "case_title" in a:
                    st.caption(f"Associated Case: [{a.get('case_id')}] {a.get('case_title')}")
                st.info("💡 **Recommended Action:** Review the underlying timeline timestamps or evidence custody logs with the primary investigating officer.")
