"""
frontend/evidence_view.py

Interactive Streamlit view for the Evidence Management Module.
Supports multi-format file ingestion, SHA-256 cryptographic integrity hash calculation,
duplicate detection, and case linkage.
"""

import streamlit as st
import time
from typing import Optional
from agent.evidence_engine import EvidenceEngine
from agent.case_engine import CaseEngine

evidence_engine = EvidenceEngine()
case_engine = CaseEngine()


def render_evidence_management():
    """Render the Evidence Management user interface."""
    st.subheader("🔬 Evidence Management & Chain of Custody")
    st.caption("Cryptographic integrity tracking, SHA-256 file hashing, duplicate upload prevention, and case repository attachment.")

    stats = evidence_engine.get_statistics()
    e1, e2 = st.columns([1, 2])
    with e1:
        st.metric("Total Evidence Items", stats.get("total", 0))
    with e2:
        type_breakdown = stats.get("by_type", {})
        if type_breakdown:
            type_str = " | ".join(f"**{k}:** {v}" for k, v in type_breakdown.items())
            st.info(f"📁 **Breakdown by Type:** {type_str}")
        else:
            st.info("No evidence registered yet.")

    ev_tabs = st.tabs(["📂 Evidence Repository & Verification", "📤 Upload & Hash New Evidence"])

    # =========================================================================
    # TAB 1: EVIDENCE REPOSITORY
    # =========================================================================
    with ev_tabs[0]:
        all_cases = case_engine.list_cases()
        c_filter_col, c_type_col, c_kw_col = st.columns([1, 1, 2])

        with c_filter_col:
            case_opts = ["ALL"] + [f"{c.case_id} -- {c.title[:20]}" for c in all_cases]
            sel_case_raw = st.selectbox("Case Filter", options=case_opts, key="ev_filter_case")
        with c_type_col:
            type_opts = ["ALL", "PDF", "TXT", "CSV", "JSON", "PNG", "JPG", "JPEG", "DOCX", "MP4", "MP3"]
            sel_type = st.selectbox("File Type", options=type_opts, key="ev_filter_type")
        with c_kw_col:
            search_query = st.text_input("🔎 Search Evidence", placeholder="Search by ID, description, source, or hash...", key="ev_search_kw")

        filter_cid = None if sel_case_raw == "ALL" else sel_case_raw.split(" -- ")[0].strip()
        filter_type = None if sel_type == "ALL" else sel_type
        filter_kw = search_query.strip() if search_query.strip() else None

        evidence_items = evidence_engine.list_evidence(
            case_id=filter_cid,
            file_type=filter_type,
            search=filter_kw,
        )

        if not evidence_items:
            st.info("No evidence items found matching your criteria.")
        else:
            st.write(f"Showing **{len(evidence_items)}** evidence item(s):")
            for ev in evidence_items:
                with st.expander(f"📁 **[{ev.evidence_id}]** {ev.file_type} -- Case: `{ev.case_id}` (Status: {ev.status})"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.markdown(f"**Evidence ID:** `{ev.evidence_id}`")
                        st.markdown(f"**Case Reference:** `{ev.case_id}`")
                        st.markdown(f"**File Type:** `{ev.file_type}`")
                        st.markdown(f"**Source:** {ev.source}")
                        st.markdown(f"**Uploaded By:** {ev.uploaded_by}")
                        st.markdown(f"**Description:**\n{ev.description or 'No description entered.'}")
                    with col2:
                        st.markdown(f"**Upload Timestamp:** {ev.timestamp}")
                        st.markdown(f"**File Size:** {evidence_engine._format_size(ev.file_size_bytes)}")
                        st.markdown(f"**Integrity Status:** `{ev.status}`")
                        st.caption(f"Storage: {ev.storage_path}")

                    if ev.metadata and ev.metadata.get("extracted_text"):
                        with st.expander("📄 Document Intelligence & Extracted Entities"):
                            st.caption("Automatically extracted from document bytes upon ingestion.")
                            ent = ev.metadata.get("entities", {})
                            if any(ent.values()):
                                st.markdown("**Identified Entities:**")
                                for k, vals in ent.items():
                                    if vals:
                                        st.markdown(f"- **{k.capitalize()}:** {', '.join(vals)}")
                            st.text_area("Document Content Preview", value=str(ev.metadata.get("extracted_text", ""))[:3000], height=120, disabled=True)

                    st.markdown("---")
                    st.markdown("🔒 **SHA-256 Cryptographic Integrity Hash:**")
                    st.code(ev.sha256_hash, language="text")

    # =========================================================================
    # TAB 2: UPLOAD & HASH NEW EVIDENCE
    # =========================================================================
    with ev_tabs[1]:
        st.markdown("#### 📤 Register Evidence Item")
        st.caption("Upload files (PDF, Images, TXT, CSV, JSON, Audio/Video). The system computes an immutable SHA-256 hash and blocks duplicates.")

        if not all_cases:
            st.warning("No cases exist yet. Please create a case in the Case Management tab before uploading evidence.")
        else:
            with st.form(key="upload_evidence_form", clear_on_submit=False):
                up_c1, up_c2 = st.columns(2)
                with up_c1:
                    case_choices = [f"{c.case_id} -- {c.title}" for c in all_cases]
                    chosen_case_str = st.selectbox("Assign to Case *", options=case_choices, key="ev_up_case")
                    ev_source = st.text_input("Evidence Source / Seizure Point", value="Field Investigation Unit", key="ev_up_source")
                    ev_officer = st.text_input("Uploaded By (Officer / Examiner)", value="Investigator in Charge", key="ev_up_officer")
                with up_c2:
                    custom_ev_id = st.text_input("Custom Evidence ID (Leave blank to auto-generate)", placeholder="e.g. EV-2026-004")
                    ev_desc = st.text_area("Evidence Description & Context *", placeholder="e.g. CCTV recording from Gate 4 during incident timeframe; hard drive mirror image...", height=105)

                uploaded_file = st.file_uploader(
                    "Select Evidence File * (Max 25 MB)",
                    type=["pdf", "txt", "csv", "json", "docx", "png", "jpg", "jpeg", "webp", "mp4", "mp3", "wav"],
                    key="ev_file_uploader",
                )

                submit_evidence = st.form_submit_button("🔒 Ingest, Hash & Attach Evidence", use_container_width=True, type="primary")

            if submit_evidence:
                if not uploaded_file:
                    st.error("Please select a file to upload.")
                elif not ev_desc.strip():
                    st.error("Evidence description is required.")
                else:
                    file_bytes = uploaded_file.getvalue()
                    cid = chosen_case_str.split(" -- ")[0].strip()

                    ok, msg, created_ev = evidence_engine.ingest_evidence(
                        case_id=cid,
                        filename=uploaded_file.name,
                        file_bytes=file_bytes,
                        description=ev_desc.strip(),
                        source=ev_source.strip(),
                        uploaded_by=ev_officer.strip(),
                        evidence_id=custom_ev_id.strip() if custom_ev_id.strip() else None,
                    )

                    if ok and created_ev:
                        st.success(f"✅ {msg}")
                        st.markdown(
                            f"**Registered ID:** `{created_ev.evidence_id}`  \n"
                            f"**File Integrity SHA-256 Hash:** `{created_ev.sha256_hash}`  \n"
                            f"**File Size:** {evidence_engine._format_size(created_ev.file_size_bytes)}  \n"
                            f"**Timestamp:** {created_ev.timestamp}"
                        )
                        time.sleep(1.0)
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
