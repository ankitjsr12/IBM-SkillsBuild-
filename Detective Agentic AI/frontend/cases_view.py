"""
frontend/cases_view.py

Interactive Streamlit view for the Case Management System.
Supports Create, View, Edit, Archive, Filter, Search, and Export (JSON/CSV) of cases.
"""

import streamlit as st
import time
from typing import Optional
from database.models import CaseStatus, CasePriority
from agent.case_engine import CaseEngine
from agent.evidence_engine import EvidenceEngine
from agent.timeline_engine import TimelineEngine
from agent.explainability_engine import ExplainabilityEngine
from agent.rag_engine import RAGEngine
from agent.anomaly_engine import AnomalyEngine
from agent.suspect_engine import SuspectEngine
from utils.pdf_utils import generate_investigation_dossier_pdf, MANDATORY_DISCLAIMER

case_engine = CaseEngine()
evidence_engine = EvidenceEngine()
timeline_engine = TimelineEngine()
rag_engine = RAGEngine()
suspect_engine = SuspectEngine()
anomaly_engine = AnomalyEngine()


def render_case_management():
    """Render the Case Management user interface."""
    st.subheader("📁 Case Management System")
    st.caption("Organize, review, filter, and track investigation cases with immutable record integrity.")

    stats = case_engine.get_statistics()
    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("Total Cases", stats["total"])
    s2.metric("Open Cases", stats["open"])
    s3.metric("Under Review", stats["under_review"])
    s4.metric("Suspended", stats["suspended"])
    s5.metric("Closed / Archived", stats["closed"] + stats["archived"])

    case_tabs = st.tabs(["📋 Case Directory & Search", "➕ Create New Case", "📥 Export Cases"])

    # =========================================================================
    # TAB 1: DIRECTORY & SEARCH
    # =========================================================================
    with case_tabs[0]:
        col_search, col_status, col_prio = st.columns([2, 1, 1])
        with col_search:
            search_query = st.text_input("🔎 Search cases", placeholder="Search by title, ID, tag, location...", key="case_search_kw")
        with col_status:
            status_options = ["ALL"] + [s.value for s in CaseStatus]
            sel_status = st.selectbox("Status Filter", options=status_options, key="case_filter_status")
        with col_prio:
            priority_options = ["ALL"] + [p.value for p in CasePriority]
            sel_prio = st.selectbox("Priority Filter", options=priority_options, key="case_filter_prio")

        status_param = None if sel_status == "ALL" else sel_status
        prio_param = None if sel_prio == "ALL" else sel_prio
        query_param = search_query.strip() if search_query.strip() else None

        cases = case_engine.list_cases(status=status_param, priority=prio_param, search=query_param)

        if not cases:
            st.info("No cases found matching your search or filter criteria.")
        else:
            st.write(f"Showing **{len(cases)}** case(s):")
            for c in cases:
                prio_color = {
                    "CRITICAL": "🔴",
                    "HIGH": "🟠",
                    "MEDIUM": "🟡",
                    "LOW": "🔵",
                }.get(c.priority, "⚪")

                with st.expander(f"{prio_color} **[{c.case_id}]** {c.title} — `{c.status}` ({c.priority} Priority)"):
                    c_col1, c_col2 = st.columns([2, 1])
                    with c_col1:
                        st.markdown(f"**Case Type:** {c.case_type}")
                        st.markdown(f"**Location:** {c.location}")
                        st.markdown(f"**Date Opened:** {c.date_opened}")
                        st.markdown(f"**Assigned Investigator:** {c.assigned_investigator}")
                        if c.extra_metadata.get("court_or_authority"):
                            st.markdown(f"**Judicial Court:** {c.extra_metadata['court_or_authority']}")
                        if c.extra_metadata.get("legal_citation"):
                            st.markdown(f"**Legal Citation:** `{c.extra_metadata['legal_citation']}`")
                        if c.extra_metadata.get("ipc_sections"):
                            ipc_list = c.extra_metadata['ipc_sections']
                            st.markdown(f"**IPC / Statutes:** {', '.join(ipc_list) if isinstance(ipc_list, list) else ipc_list}")
                        st.markdown(f"**Description / Summary:**\n{c.description or 'No description provided.'}")
                        if c.tags:
                            st.caption(f"Tags: {', '.join(c.tags)}")
                    with c_col2:
                        st.markdown(f"**Created:** {c.created_at}")
                        st.markdown(f"**Last Updated:** {c.updated_at}")
                        if c.extra_metadata.get("source"):
                            src_url = c.extra_metadata.get("source_url", "")
                            if src_url:
                                st.markdown(f"**Source:** [{c.extra_metadata['source']}]({src_url})")
                            else:
                                st.markdown(f"**Source:** {c.extra_metadata['source']}")
                        if c.extra_metadata.get("modus_operandi"):
                            st.markdown(f"**MO Record:** {c.extra_metadata['modus_operandi']}")

                    st.divider()
                    with st.expander("🤖 Generate 7-Part AI Case Analysis & Indian Legal Correlation", expanded=False):
                        st.caption("Synthesizes known facts, evidence, timeline events, anomalies, and authentic Indian precedents.")
                        if st.button("Generate Case Analysis", key=f"btn_summary_{c.case_id}"):
                            with st.spinner("Analyzing case data and correlating Indian legal precedents..."):
                                ev_items = evidence_engine.list_evidence_for_case(c.case_id)
                                tl_events = timeline_engine.get_case_timeline(c.case_id)
                                precedents = rag_engine.retrieve(c.description, top_k=3) if c.description else []
                                case_anomalies = anomaly_engine.scan_case_anomalies(c.case_id)
                                summary = ExplainabilityEngine.generate_case_summary(
                                    c, ev_items, tl_events, precedents, anomalies=case_anomalies
                                )
                                st.session_state[f"ai_summary_{c.case_id}"] = summary

                        if st.session_state.get(f"ai_summary_{c.case_id}"):
                            s_data = st.session_state[f"ai_summary_{c.case_id}"]
                            st.info(f"**AI Case Summary:** {s_data.get('ai_case_summary', '')}")
                            
                            # Explainable Pipeline (SOURCE DATA → MATCHED PATTERN → SIMILARITY → AI ANALYSIS)
                            if s_data.get("explainable_results_pipeline"):
                                with st.expander("🔗 Explainable Precedent Pipeline (Audit Trail)"):
                                    for pipe_line in s_data["explainable_results_pipeline"]:
                                        st.code(pipe_line, language="text")

                            s_c1, s_c2 = st.columns(2)
                            with s_c1:
                                st.markdown("##### 🔍 Pattern Analysis")
                                st.markdown(s_data.get("pattern_analysis", "No pattern recorded."))
                                st.markdown("##### 🔬 Evidence Summary")
                                st.markdown(s_data.get("evidence_summary", "No evidence recorded."))
                                st.markdown("##### 📚 Historical Similarities (Indian Precedents)")
                                st.markdown(s_data.get("historical_similarities", "No matching precedent."))
                            with s_c2:
                                st.markdown("##### ⚠️ Anomalies")
                                for anom in s_data.get("anomalies", []):
                                    st.markdown(f"- {anom}")
                                st.markdown("##### ❓ Information Gaps")
                                for ig in s_data.get("information_gaps", []):
                                    st.markdown(f"- {ig}")
                                st.markdown("##### ⚖️ Human Review Points")
                                for hrp in s_data.get("human_review_points", []):
                                    st.markdown(f"- {hrp}")

                            st.warning(f"⚖️ {s_data.get('statutory_caveat', '')}")

                    with st.expander("📑 Official 18-Section Investigation Dossier (PDF)", expanded=False):
                        st.caption("Generates a comprehensive formal dossier adhering to legal disclaimers, chain-of-custody, timeline, and precedent analysis.")
                        if st.button("Generate Case Dossier PDF", key=f"btn_pdf_{c.case_id}"):
                            with st.spinner("Compiling 18-section investigation dossier..."):
                                ev_items = evidence_engine.list_evidence_for_case(c.case_id)
                                tl_events = timeline_engine.get_case_timeline(c.case_id)
                                susp_items = suspect_engine.list_suspects_for_case(c.case_id)
                                precedents = rag_engine.retrieve(c.description, top_k=3) if c.description else []
                                dossier_data = {
                                    "case_id": c.case_id,
                                    "case_title": c.title,
                                    "case_type": c.case_type,
                                    "status": c.status,
                                    "priority": c.priority,
                                    "location": c.location,
                                    "assigned_investigator": c.assigned_investigator,
                                    "case_summary": c.description,
                                    "suspects": [{"name": s.name, "alias": s.alias, "age": s.age, "behaviors": s.observed_behaviors, "mo": s.modus_operandi} for s in susp_items],
                                    "evidence": [{"evidence_id": e.evidence_id, "type": e.file_type, "source": e.source, "hash": e.sha256_hash} for e in ev_items],
                                    "timeline": [{"timestamp": t.timestamp, "event_type": t.event_type, "description": t.description} for t in tl_events],
                                    "matched_cases": precedents,
                                    "model_assessment": {
                                        "score": 65 if precedents else 25,
                                        "confidence": "Moderate Confidence",
                                        "breakdown": [
                                            {"factor": "Baseline Score", "contribution": 15, "explanation": "Starting baseline"},
                                            {"factor": "Corpus Similarity", "contribution": 50 if precedents else 10, "explanation": "Precedent match weight"},
                                        ],
                                    },
                                    "disclaimer": MANDATORY_DISCLAIMER,
                                }
                                pdf_bytes = generate_investigation_dossier_pdf(dossier_data)
                                st.session_state[f"pdf_bytes_{c.case_id}"] = pdf_bytes

                        if st.session_state.get(f"pdf_bytes_{c.case_id}"):
                            st.download_button(
                                "📥 Download Formal Investigation Dossier (PDF)",
                                data=st.session_state[f"pdf_bytes_{c.case_id}"],
                                file_name=f"Investigation_Dossier_{c.case_id}.pdf",
                                mime="application/pdf",
                                key=f"dl_dossier_{c.case_id}",
                                use_container_width=True,
                            )

                    st.divider()
                    st.markdown("#### ✏️ Edit or Update Case")
                    with st.form(key=f"edit_case_form_{c.case_id}"):
                        e_col1, e_col2 = st.columns(2)
                        with e_col1:
                            new_title = st.text_input("Title", value=c.title, key=f"et_{c.case_id}")
                            new_type = st.text_input("Case Type", value=c.case_type, key=f"ety_{c.case_id}")
                            new_loc = st.text_input("Location", value=c.location, key=f"el_{c.case_id}")
                            new_inv = st.text_input("Assigned Investigator", value=c.assigned_investigator, key=f"ei_{c.case_id}")
                        with e_col2:
                            new_status = st.selectbox(
                                "Status",
                                options=[s.value for s in CaseStatus],
                                index=[s.value for s in CaseStatus].index(c.status) if c.status in [s.value for s in CaseStatus] else 0,
                                key=f"es_{c.case_id}"
                            )
                            new_prio = st.selectbox(
                                "Priority",
                                options=[p.value for p in CasePriority],
                                index=[p.value for p in CasePriority].index(c.priority) if c.priority in [p.value for p in CasePriority] else 1,
                                key=f"ep_{c.case_id}"
                            )
                            new_tags = st.text_input("Tags (comma separated)", value=", ".join(c.tags), key=f"etag_{c.case_id}")
                        new_desc = st.text_area("Description", value=c.description, height=80, key=f"edesc_{c.case_id}")
                        
                        btn_col1, btn_col2 = st.columns([1, 1])
                        save_btn = btn_col1.form_submit_button("💾 Save Changes", use_container_width=True, type="primary")
                        archive_btn = btn_col2.form_submit_button("📦 Archive Case", use_container_width=True)

                    if save_btn:
                        updated_tags = [t.strip() for t in new_tags.split(",") if t.strip()]
                        success, msg, _ = case_engine.update_case(c.case_id, {
                            "title": new_title.strip(),
                            "case_type": new_type.strip(),
                            "location": new_loc.strip(),
                            "assigned_investigator": new_inv.strip(),
                            "status": new_status,
                            "priority": new_prio,
                            "tags": updated_tags,
                            "description": new_desc.strip(),
                        })
                        if success:
                            st.success(msg)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(msg)

                    if archive_btn:
                        success, msg = case_engine.archive_case(c.case_id)
                        if success:
                            st.success(msg)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(msg)

    # =========================================================================
    # TAB 2: CREATE NEW CASE
    # =========================================================================
    with case_tabs[1]:
        st.markdown("#### 📝 Register New Investigation Case")
        with st.form(key="create_case_form"):
            cc1, cc2 = st.columns(2)
            with cc1:
                nc_title = st.text_input("Case Title *", placeholder="e.g. Downtown Bank Robbery")
                nc_type = st.text_input("Case Type", placeholder="e.g. Armed Robbery / Cyber Fraud", value="General Investigation")
                nc_loc = st.text_input("Location", placeholder="e.g. Sector 18, Commercial Plaza")
                nc_inv = st.text_input("Assigned Investigator", placeholder="e.g. Det. Sarah Connor")
            with cc2:
                nc_id = st.text_input("Custom Case ID (Leave blank to auto-generate)", placeholder="e.g. CASE-2026-089")
                nc_prio = st.selectbox("Initial Priority", options=[p.value for p in CasePriority], index=1)
                nc_date = st.text_input("Date Opened (YYYY-MM-DD)", value=time.strftime("%Y-%m-%d"))
                nc_tags = st.text_input("Tags (comma separated)", placeholder="e.g. commercial, night, armed")

            nc_desc = st.text_area("Case Summary & Initial Observations *", height=120,
                                   placeholder="Describe known facts, scene details, entry points, or initial evidence...")

            create_submit = st.form_submit_button("🚀 Create & Register Case", use_container_width=True, type="primary")

        if create_submit:
            if not nc_title.strip():
                st.error("Case title is required.")
            elif not nc_desc.strip():
                st.error("Case summary / description is required.")
            else:
                tag_list = [t.strip() for t in nc_tags.split(",") if t.strip()]
                success, msg, created_case = case_engine.create_case(
                    title=nc_title.strip(),
                    case_id=nc_id.strip() if nc_id.strip() else None,
                    case_type=nc_type.strip(),
                    description=nc_desc.strip(),
                    location=nc_loc.strip(),
                    date_opened=nc_date.strip(),
                    priority=nc_prio,
                    assigned_investigator=nc_inv.strip(),
                    tags=tag_list,
                )
                if success:
                    st.success(f"✅ {msg}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")

    # =========================================================================
    # TAB 3: EXPORT CASES
    # =========================================================================
    with case_tabs[2]:
        st.markdown("#### 📥 Export Official Case Records")
        st.caption("Exports contain real application data from the relational case database.")

        exp_col1, exp_col2 = st.columns(2)
        with exp_col1:
            st.markdown("##### 📄 Export as JSON")
            json_content, json_mime, json_name = case_engine.export_cases("json")
            st.download_button(
                label="⬇️ Download Full JSON Archive",
                data=json_content,
                file_name=json_name,
                mime=json_mime,
                use_container_width=True,
                key="dl_cases_json",
            )
        with exp_col2:
            st.markdown("##### 📊 Export as CSV")
            csv_content, csv_mime, csv_name = case_engine.export_cases("csv")
            st.download_button(
                label="⬇️ Download Spreadsheet (CSV)",
                data=csv_content,
                file_name=csv_name,
                mime=csv_mime,
                use_container_width=True,
                key="dl_cases_csv",
            )
