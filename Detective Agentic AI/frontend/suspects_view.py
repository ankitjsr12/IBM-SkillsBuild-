"""
frontend/suspects_view.py

Interactive Streamlit view for the Suspect Management Module.
Maintains persistent suspect profiles, case associations, and assessment history.

IMPORTANT PRIVACY DIRECTIVE:
Does NOT infer sensitive personal characteristics or invent missing information.
All unavailable attributes display strictly as "Not provided".
"""

import streamlit as st
import time
from typing import Optional
from agent.suspect_engine import SuspectEngine
from agent.case_engine import CaseEngine

suspect_engine = SuspectEngine()
case_engine = CaseEngine()


def render_suspect_management():
    """Render the Suspect Management user interface."""
    st.subheader("👤 Suspect Management & Historical Profiling")
    st.caption("Track observed behaviors, case associations, and AI assessment history. Personal data is never fabricated.")

    total_suspects = suspect_engine.repo.count_suspects()
    st.metric("Total Registered Suspects", total_suspects)

    suspect_tabs = st.tabs(["👥 Suspect Directory & Profiles", "➕ Register New Suspect"])

    # =========================================================================
    # TAB 1: SUSPECT DIRECTORY & PROFILES
    # =========================================================================
    with suspect_tabs[0]:
        c_search, c_case_filter = st.columns([2, 1])
        with c_search:
            search_query = st.text_input("🔎 Search Suspects", placeholder="Search by name, alias, ID, behavior...", key="susp_search_kw")
        with c_case_filter:
            all_cases = case_engine.list_cases()
            case_opts = ["ALL"] + [f"{c.case_id} -- {c.title[:20]}" for c in all_cases]
            sel_case_raw = st.selectbox("Linked Case Filter", options=case_opts, key="susp_filter_case")

        case_filter_id = None
        if sel_case_raw != "ALL":
            case_filter_id = sel_case_raw.split(" -- ")[0].strip()

        suspects = suspect_engine.list_suspects(
            search=search_query.strip() if search_query.strip() else None,
            case_id=case_filter_id,
        )

        if not suspects:
            st.info("No suspect records found matching your query.")
        else:
            st.write(f"Showing **{len(suspects)}** suspect profile(s):")
            for s in suspects:
                with st.expander(f"👤 **[{s.suspect_id}]** {s.name} (Alias: {s.alias})"):
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        st.markdown(f"**Name:** {s.name}")
                        st.markdown(f"**Alias:** {s.alias}")
                        st.markdown(f"**Age:** {s.age}")
                        st.markdown(f"**Location:** {s.location}")
                        st.markdown(f"**Known Associations:** {s.known_associations}")
                    with col2:
                        st.markdown(f"**Created:** {s.created_at}")
                        st.markdown(f"**Last Updated:** {s.updated_at}")
                        st.markdown(f"**Linked Cases:** {', '.join(s.case_connections) if s.case_connections else 'None'}")
                        st.markdown(f"**Evidence Links:** {', '.join(s.evidence_links) if s.evidence_links else 'None'}")

                    st.markdown("---")
                    st.markdown(f"**Observed Behaviors [INVESTIGATOR RECORD]:**\n{s.observed_behaviors}")
                    st.markdown(f"**Modus Operandi [INVESTIGATIVE RECORD]:**\n{s.modus_operandi}")
                    if s.notes:
                        st.markdown(f"**Investigator Notes:** {s.notes}")

                    # Assessment History
                    st.markdown("#### 🧠 Model Assessment History")
                    if not s.assessment_history:
                        st.caption("No prior AI model assessments logged for this suspect.")
                    else:
                        for idx, a in enumerate(reversed(s.assessment_history), 1):
                            st.info(
                                f"**Assessment #{len(s.assessment_history) - idx + 1}** ({a.get('timestamp', 'N/A')}):\n\n"
                                f"• **Risk Indicator Score:** `{a.get('tendency_score', 'N/A')}` | **Category:** `{a.get('risk_level', 'N/A')}`\n"
                                f"• **Match Quality:** {a.get('match_quality', 'N/A')}\n"
                                f"• **Assessment:** {a.get('summary', '')}"
                            )

                    # Quick link case form
                    st.markdown("#### 🔗 Link to Case")
                    with st.form(key=f"link_case_form_{s.suspect_id}"):
                        avail_cases = [f"{c.case_id} -- {c.title}" for c in all_cases if c.case_id not in s.case_connections]
                        if avail_cases:
                            c_to_link = st.selectbox("Select case to link", options=avail_cases, key=f"sel_link_{s.suspect_id}")
                            link_sub = st.form_submit_button("Link Case")
                            if link_sub:
                                cid = c_to_link.split(" -- ")[0].strip()
                                ok, msg, _ = suspect_engine.link_case(s.suspect_id, cid)
                                if ok:
                                    st.success(msg)
                                    time.sleep(0.5)
                                    st.rerun()
                        else:
                            st.caption("All existing cases are already linked or no cases exist.")
                            st.form_submit_button("Link Case", disabled=True)

    # =========================================================================
    # TAB 2: REGISTER NEW SUSPECT
    # =========================================================================
    with suspect_tabs[1]:
        st.markdown("#### 📝 Register Suspect Profile")
        st.caption("All missing attributes will default to 'Not provided'. Never infer or invent characteristics.")

        with st.form(key="reg_suspect_form"):
            r1, r2 = st.columns(2)
            with r1:
                ns_name = st.text_input("Name / Full Identifier *", placeholder="e.g. John Doe / Subject Alpha")
                ns_alias = st.text_input("Known Alias", placeholder="e.g. 'The Shadow' (leave blank if none)")
                ns_age = st.text_input("Age (if provided)", placeholder="e.g. 34 (leave blank if not provided)")
                ns_loc = st.text_input("Location (if provided)", placeholder="e.g. Metro Area")
            with r2:
                ns_id = st.text_input("Custom Suspect ID (Leave blank to auto-generate)", placeholder="e.g. SUSP-2026-001")
                ns_assoc = st.text_input("Known Associations", placeholder="e.g. Frequent associate of warehouse group")
                all_case_ids = [c.case_id for c in all_cases]
                ns_case_link = st.multiselect("Link to Existing Cases", options=all_case_ids)

            ns_behaviors = st.text_area(
                "Observed Behaviors (Verbatim Investigator Input)",
                placeholder="Observed casing residential premises during late hours, targeting locked cabinets...",
                height=90,
            )
            ns_mo = st.text_area(
                "Modus Operandi (Observed Operational Method)",
                placeholder="Disables rear window latches using glass cutter; avoids perimeter sensors...",
                height=90,
            )
            ns_notes = st.text_area("Investigator Notes & Verified References", height=60)

            sub_reg = st.form_submit_button("🚀 Register Suspect Profile", use_container_width=True, type="primary")

        if sub_reg:
            if not ns_name.strip():
                st.error("Suspect name or alias is required.")
            else:
                ok, msg, created = suspect_engine.register_suspect(
                    name=ns_name.strip(),
                    suspect_id=ns_id.strip() if ns_id.strip() else None,
                    alias=ns_alias.strip() if ns_alias.strip() else None,
                    age=ns_age.strip() if ns_age.strip() else None,
                    location=ns_loc.strip() if ns_loc.strip() else None,
                    known_associations=ns_assoc.strip() if ns_assoc.strip() else None,
                    observed_behaviors=ns_behaviors.strip() if ns_behaviors.strip() else None,
                    modus_operandi=ns_mo.strip() if ns_mo.strip() else None,
                    case_connections=ns_case_link,
                    notes=ns_notes.strip() if ns_notes.strip() else None,
                )
                if ok:
                    st.success(f"✅ {msg}")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
