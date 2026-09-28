"""
frontend/timeline_view.py

Interactive Streamlit view for the Case Evidence Timeline.
Visualizes verified chronological sequences across investigations:
Incident -> Evidence Added -> Witness Statement -> Digital Evidence -> Observed Behavior -> RAG Retrieval -> Model Assessment -> Investigator Review

RULE (Part 7):
Never fabricates timeline events. Only displays verified entries recorded by investigators.
"""

import streamlit as st
import time
from typing import Optional
from agent.timeline_engine import TimelineEngine, EVENT_TYPES
from agent.case_engine import CaseEngine
from agent.evidence_engine import EvidenceEngine

timeline_engine = TimelineEngine()
case_engine = CaseEngine()
evidence_engine = EvidenceEngine()

EVENT_ICONS = {
    "INCIDENT": "🚨",
    "EVIDENCE_ADDED": "📦",
    "WITNESS_STATEMENT": "🗣️",
    "DIGITAL_EVIDENCE": "💻",
    "OBSERVED_BEHAVIOR": "👁️",
    "RAG_RETRIEVAL": "🔍",
    "MODEL_ASSESSMENT": "🧠",
    "INVESTIGATOR_REVIEW": "📋",
}


def render_timeline_management():
    """Render the Case Timeline user interface."""
    st.subheader("⏱️ Investigation Chronology & Evidence Timeline")
    st.caption("Visual chronological flow of verified case events. Never fabricates events.")

    all_cases = case_engine.list_cases()
    if not all_cases:
        st.info("No cases currently registered. Create a case in Case Management first.")
        return

    case_options = [f"{c.case_id} -- {c.title}" for c in all_cases]
    sel_case_str = st.selectbox("Select Case to Inspect Timeline", options=case_options, key="tl_case_select")
    selected_cid = sel_case_str.split(" -- ")[0].strip()

    timeline_tabs = st.tabs(["📊 Visual Chronology", "➕ Record Timeline Event"])

    # =========================================================================
    # TAB 1: VISUAL CHRONOLOGY
    # =========================================================================
    with timeline_tabs[0]:
        events = timeline_engine.get_case_timeline(selected_cid)
        if not events:
            st.info(f"No chronological timeline events recorded for Case '{selected_cid}'.")
        else:
            st.write(f"Showing **{len(events)}** verified event(s) for Case **{selected_cid}**:")

            # Stage summary bar
            st.markdown(
                "**Standard Investigative Progression:**  \n"
                "`Incident` ➔ `Evidence Added` ➔ `Witness Statement` ➔ `Digital Evidence` ➔ `Observed Behavior` ➔ `RAG Retrieval` ➔ `Model Assessment` ➔ `Investigator Review`"
            )
            st.divider()

            for idx, ev in enumerate(events, 1):
                icon = EVENT_ICONS.get(ev.event_type, "📌")
                with st.container():
                    t_col1, t_col2 = st.columns([1, 4])
                    with t_col1:
                        st.markdown(f"### {icon}")
                        st.caption(f"**Step #{idx}**")
                        st.markdown(f"**`{ev.event_type}`**")
                        st.caption(f"🕒 {ev.timestamp}")
                    with t_col2:
                        st.markdown(f"**Description:** {ev.description}")
                        st.markdown(f"**Source:** `{ev.source}`")
                        if ev.linked_evidence_id:
                            st.markdown(f"**Linked Evidence:** `{ev.linked_evidence_id}`")
                    st.divider()

    # =========================================================================
    # TAB 2: RECORD NEW EVENT
    # =========================================================================
    with timeline_tabs[1]:
        st.markdown(f"#### ➕ Add Verified Event to Case `{selected_cid}`")
        st.caption("Enter factual timestamps and verified sources. Never fabricate events.")

        # Get existing evidence items for this case to link
        case_ev_items = evidence_engine.list_evidence(case_id=selected_cid)
        ev_opts = ["None"] + [f"{e.evidence_id} -- {e.file_type} ({e.description[:25]}...)" for e in case_ev_items]

        with st.form(key=f"add_event_form_{selected_cid}"):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                ev_type = st.selectbox("Event Type *", options=EVENT_TYPES, key="form_ev_type")
                ev_ts = st.text_input("Event Timestamp (YYYY-MM-DD HH:MM:SS) *", value=time.strftime("%Y-%m-%d %H:%M:%S"))
                ev_source = st.text_input("Verification Source *", value="Lead Detective", placeholder="e.g. CCTV Gate 4 / Lab Ballistics")
            with f_col2:
                sel_ev_link = st.selectbox("Linked Evidence Item (Optional)", options=ev_opts, key="form_ev_link")
                custom_ev_id = st.text_input("Custom Event ID (Leave blank to auto-generate)", placeholder="e.g. TL-2026-001")

            ev_desc = st.text_area("Event Description *", height=90, placeholder="Describe verified incident, witness interview, or forensics find...")

            sub_event = st.form_submit_button("🔒 Record Verified Timeline Event", use_container_width=True, type="primary")

        if sub_event:
            if not ev_desc.strip():
                st.error("Event description is required.")
            else:
                linked_id = None
                if sel_ev_link != "None":
                    linked_id = sel_ev_link.split(" -- ")[0].strip()

                ok, msg, created = timeline_engine.record_event(
                    case_id=selected_cid,
                    timestamp=ev_ts.strip(),
                    event_type=ev_type,
                    description=ev_desc.strip(),
                    source=ev_source.strip(),
                    linked_evidence_id=linked_id,
                    event_id=custom_ev_id.strip() if custom_ev_id.strip() else None,
                )
                if ok:
                    st.success(f"✅ {msg}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
