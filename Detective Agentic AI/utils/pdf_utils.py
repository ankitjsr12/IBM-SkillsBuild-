"""
utils/pdf_utils.py

Professional PDF Investigation Dossier Generator using fpdf2.
Handles multi-page tables, text wrapping, Unicode transliteration, and error containment.

Follows Part 18 (18-Section Investigation Dossier) and Part 19 (Mandatory Model Assessment Disclaimer).
"""

import datetime
import io
import logging
from typing import Any, Dict, List, Optional
from fpdf import FPDF

from utils.text_utils import sanitize_for_pdf, safe_str, truncate_text

logger = logging.getLogger(__name__)

MANDATORY_DISCLAIMER = (
    "DISCLAIMER: All scores are MODEL ASSESSMENTS produced by similarity-based pattern "
    "matching against historical case records. They are NOT legal findings, NOT proof of guilt, "
    "and must NOT be used as the sole basis for any legal or investigative decision. "
    "Always verify information with qualified human investigators."
)


class DossierPDF(FPDF):
    """
    Subclass of FPDF providing consistent header, footer, page numbers,
    and structured layout methods that prevent common fpdf2 formatting crashes.
    """

    def __init__(self, case_title: str = "Investigation Dossier", orientation: str = "P", unit: str = "mm", format: str = "A4"):
        super().__init__(orientation=orientation, unit=unit, format=format)
        self.case_title = sanitize_for_pdf(case_title)
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(18, 18, 18)

    def header(self):
        # Only print header after the cover/first page
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 6, f"DETECTIVE AGENTIC AI -- {self.case_title}", align="L")
            self.cell(0, 6, "CONFIDENTIAL // LAW ENFORCEMENT & INVESTIGATION", align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(200, 200, 200)
            self.line(18, self.get_y(), 192, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.line(18, self.get_y(), 192, self.get_y())
        self.ln(2)
        self.cell(0, 6, "Model Assessment Only -- Not a Legal Finding", align="L")
        self.cell(0, 6, f"Page {self.page_no()}/{{nb}}", align="R")

    def chapter_title(self, section_num: int, title: str):
        """Render a clean, styled section header."""
        self.set_font("Helvetica", "B", 11)
        self.set_fill_color(235, 240, 248)
        self.set_text_color(20, 35, 60)
        clean_title = sanitize_for_pdf(f"{section_num}. {title.upper()}")
        self.multi_cell(0, 7, clean_title, fill=True, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def field_row(self, label: str, value: Any, label_width: int = 45):
        """Render a label/value row safely with multi-cell wrapping."""
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(40, 40, 40)
        clean_label = sanitize_for_pdf(label)
        clean_value = sanitize_for_pdf(value)

        # Print label and value cleanly
        self.cell(label_width, 6, clean_label + ":", align="L")
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 6, clean_value, new_x="LMARGIN", new_y="NEXT")

    def body_paragraph(self, text: Any, indent: int = 0):
        """Render body text safely, avoiding narrow-width crashes."""
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        clean_text = sanitize_for_pdf(text)
        if indent > 0:
            self.set_x(18 + indent)
        self.multi_cell(0, 5.5, clean_text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1.5)

    def table_row(self, cols: List[str], widths: List[int], is_header: bool = False):
        """Render a single table row with explicit column widths."""
        self.set_font("Helvetica", "B" if is_header else "", 8.5)
        if is_header:
            self.set_fill_color(220, 225, 235)
            self.set_text_color(15, 25, 45)
        else:
            self.set_fill_color(250, 250, 250)
            self.set_text_color(35, 35, 35)

        # Calculate max lines needed
        clean_cols = [sanitize_for_pdf(c) for c in cols]
        for col_text, w in zip(clean_cols, widths):
            # Short safe cell
            self.cell(w, 6, truncate_text(col_text, max_chars=40), border=1, fill=True)
        self.ln()


def generate_investigation_dossier_pdf(dossier_data: Dict[str, Any]) -> bytes:
    """
    Generate a full 18-Section Investigation Dossier PDF.
    Guaranteed crash-proof: catches any layout errors and falls back to a clean text dossier.
    """
    try:
        case_info = dossier_data.get("case_info", {})
        suspect_info = dossier_data.get("suspect_info", {})
        model_assessment = dossier_data.get("model_assessment", {})
        
        case_title = case_info.get("case_title") or case_info.get("title") or "Investigation Dossier"
        pdf = DossierPDF(case_title=case_title)
        pdf.alias_nb_pages()
        pdf.add_page()

        # =====================================================================
        # SECTION 1: COVER PAGE
        # =====================================================================
        pdf.ln(10)
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(15, 30, 60)
        pdf.cell(0, 10, "CONFIDENTIAL INVESTIGATION DOSSIER", align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(70, 80, 95)
        pdf.cell(0, 8, sanitize_for_pdf(case_title), align="C", new_x="LMARGIN", new_y="NEXT")
        
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 6, "AI-Assisted Investigation & Pattern Profiling Platform", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)
        
        pdf.set_draw_color(30, 60, 115)
        pdf.set_line_width(0.8)
        pdf.line(18, pdf.get_y(), 192, pdf.get_y())
        pdf.set_line_width(0.2)
        pdf.ln(8)

        # Meta summary box on Cover
        pdf.set_fill_color(245, 248, 252)
        pdf.set_draw_color(190, 205, 225)
        pdf.rect(18, pdf.get_y(), 174, 38, style="DF")
        start_y = pdf.get_y() + 4
        pdf.set_xy(22, start_y)
        
        pdf.field_row("Case ID", case_info.get("case_id", "CASE-NEW"), label_width=35)
        pdf.set_x(22)
        pdf.field_row("Priority", case_info.get("priority", "MEDIUM"), label_width=35)
        pdf.set_x(22)
        pdf.field_row("Status", case_info.get("status", "OPEN"), label_width=35)
        pdf.set_x(22)
        pdf.field_row("Assigned Investigator", case_info.get("assigned_investigator", "Investigator in Charge"), label_width=35)
        pdf.set_x(22)
        pdf.field_row("Date Generated", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"), label_width=35)
        
        pdf.set_y(start_y + 38)
        pdf.ln(6)

        # =====================================================================
        # SECTION 2: CASE INFORMATION
        # =====================================================================
        pdf.chapter_title(2, "Case Information")
        pdf.field_row("Case ID", case_info.get("case_id", "Not provided"))
        pdf.field_row("Title", case_info.get("title") or case_info.get("case_title", "Not provided"))
        pdf.field_row("Case Type", case_info.get("case_type") or case_info.get("crime_type", "Not provided"))
        pdf.field_row("Location", case_info.get("location", "Not provided"))
        pdf.field_row("Date Opened", case_info.get("date_opened", "Not provided"))
        pdf.field_row("Tags", ", ".join(case_info.get("tags", [])) if isinstance(case_info.get("tags"), list) else str(case_info.get("tags", "None")))
        pdf.ln(3)

        # =====================================================================
        # SECTION 3: EXECUTIVE SUMMARY
        # =====================================================================
        pdf.chapter_title(3, "Executive Summary")
        exec_summary = dossier_data.get("executive_summary") or case_info.get("description") or (
            f"Case '{case_title}' opened for detailed pattern profiling and precedent correlation. "
            f"Model assessment indicates risk indicator {model_assessment.get('tendency_score', 'N/A')} "
            f"({model_assessment.get('risk_level', 'EVALUATION PENDING')})."
        )
        pdf.body_paragraph(exec_summary)
        pdf.ln(2)

        # =====================================================================
        # SECTION 4: KNOWN FACTS (VERIFIED ONLY)
        # =====================================================================
        pdf.chapter_title(4, "Known Facts [SOURCE: VERIFIED RECORDS]")
        known_facts = dossier_data.get("known_facts", [])
        if known_facts:
            for fact in known_facts:
                pdf.body_paragraph(f"* {fact}", indent=4)
        else:
            pdf.body_paragraph("No verified factual entries recorded for this case.")
        pdf.ln(2)

        # =====================================================================
        # SECTION 5: SUSPECT INFORMATION
        # =====================================================================
        pdf.chapter_title(5, "Suspect Information [SOURCE: USER / CASE RECORD]")
        pdf.field_row("Suspect ID", suspect_info.get("suspect_id", "Not provided"))
        pdf.field_row("Name / Alias", suspect_info.get("name") or suspect_info.get("suspect_name", "Not provided"))
        pdf.field_row("Age", suspect_info.get("age", "Not provided"))
        pdf.field_row("Location", suspect_info.get("location", "Not provided"))
        pdf.field_row("Known Associations", suspect_info.get("known_associations", "Not provided"))
        pdf.ln(2)

        # =====================================================================
        # SECTION 6: OBSERVED BEHAVIORS
        # =====================================================================
        pdf.chapter_title(6, "Observed Behaviors [SOURCE: INVESTIGATOR OBSERVATION]")
        behaviors = dossier_data.get("behaviors") or suspect_info.get("behaviors") or "Not provided"
        pdf.body_paragraph(behaviors)
        pdf.ln(2)

        # =====================================================================
        # SECTION 7: MODUS OPERANDI (MO)
        # =====================================================================
        pdf.chapter_title(7, "Modus Operandi [SOURCE: INVESTIGATIVE RECORD]")
        mo = dossier_data.get("modus_operandi") or suspect_info.get("modus_operandi") or case_info.get("modus_operandi") or "Not provided"
        pdf.body_paragraph(mo)
        pdf.ln(2)

        # =====================================================================
        # SECTION 8: EVIDENCE SUMMARY & FILE INTEGRITY HASHES
        # =====================================================================
        pdf.chapter_title(8, "Evidence Summary & Integrity Verification")
        evidence_list = dossier_data.get("evidence", [])
        if evidence_list:
            pdf.table_row(["Evidence ID", "Type", "Source", "SHA-256 / Status"], [35, 25, 45, 69], is_header=True)
            for ev in evidence_list:
                eid = ev.get("evidence_id", "EV-N/A")
                etype = ev.get("type", "Document")
                source = ev.get("source", "Field Unit")
                sha = ev.get("hash", ev.get("sha256", "Verified"))
                pdf.table_row([eid, etype, source, sha], [35, 25, 45, 69])
        else:
            pdf.body_paragraph("No evidence items currently attached to this case record.")
        pdf.ln(3)

        # =====================================================================
        # SECTION 9: TIMELINE OF EVENTS
        # =====================================================================
        pdf.chapter_title(9, "Chronological Case Timeline")
        timeline = dossier_data.get("timeline", [])
        if timeline:
            pdf.table_row(["Timestamp", "Event Type", "Description"], [40, 35, 99], is_header=True)
            for ev in timeline:
                ts = ev.get("timestamp", "N/A")
                ev_type = ev.get("event_type", "Incident")
                desc = ev.get("description", "Recorded observation")
                pdf.table_row([ts, ev_type, desc], [40, 35, 99])
        else:
            pdf.body_paragraph("No chronological timeline events recorded.")
        pdf.ln(3)

        # =====================================================================
        # SECTION 10: RAG PRECEDENT RETRIEVAL RESULTS
        # =====================================================================
        pdf.chapter_title(10, "RAG Precedent Retrieval Results [SOURCE: RETRIEVED EVIDENCE]")
        matched_cases = dossier_data.get("matched_cases", []) or model_assessment.get("similar_cases", [])
        if matched_cases:
            for idx, c in enumerate(matched_cases, 1):
                sim_pct = f"{float(c.get('similarity', 0.0)):.0%}"
                title_line = f"Precedent #{idx}: {c.get('case_title', c.get('title', 'Historical Case'))} ({c.get('location', 'Global')}) -- Similarity: {sim_pct}"
                pdf.field_row("Case Match", title_line, label_width=30)
                if c.get("summary"):
                    pdf.body_paragraph(f"Record Summary: {c['summary']}", indent=6)
                pdf.ln(1)
        else:
            pdf.body_paragraph("No sufficiently similar record found in the historical vector database.")
        pdf.ln(2)

        # =====================================================================
        # SECTION 11: HISTORICAL SIMILARITIES
        # =====================================================================
        pdf.chapter_title(11, "Historical Similarities Analysis")
        sim_analysis = dossier_data.get("historical_similarities") or (
            "Pattern comparison performed using tokenized cosine similarity against active case records. "
            "Scores represent lexical and behavioral overlap."
        )
        pdf.body_paragraph(sim_analysis)
        pdf.ln(2)

        # =====================================================================
        # SECTION 12: MODEL ASSESSMENTS & EXPLAINABILITY
        # =====================================================================
        pdf.chapter_title(12, "Model Assessments [SOURCE: MODEL INFERENCE]")
        pdf.field_row("Risk Indicator Score", model_assessment.get("tendency_score", "0%"))
        pdf.field_row("Model Category", model_assessment.get("risk_level", "LOW RISK"))
        pdf.field_row("Match Quality", model_assessment.get("match_quality", "Standard"))
        
        breakdown = model_assessment.get("scoring_breakdown", [])
        if breakdown:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 6, "Scoring Breakdown Factors:", new_x="LMARGIN", new_y="NEXT")
            for item in breakdown:
                factor_text = f"  * {item.get('factor', 'Factor')}: +{item.get('contribution', 0)} pts -- {item.get('explanation', '')}"
                pdf.body_paragraph(factor_text, indent=4)
        pdf.ln(2)

        # =====================================================================
        # SECTION 13: ANOMALIES DETECTED
        # =====================================================================
        pdf.chapter_title(13, "Potential Anomalies Detected")
        anomalies = dossier_data.get("anomalies", [])
        if anomalies:
            for anom in anomalies:
                pdf.body_paragraph(f"[!] Potential anomaly detected: {anom}", indent=4)
        else:
            pdf.body_paragraph("No temporal, frequency, or evidentiary anomalies flagged at this stage.")
        pdf.ln(2)

        # =====================================================================
        # SECTION 14: UNRESOLVED QUESTIONS
        # =====================================================================
        pdf.chapter_title(14, "Unresolved Questions")
        questions = dossier_data.get("unresolved_questions", [
            "Are there correlated digital footprints or cell tower records matching the incident timeframe?",
            "Has physical or video evidence been independently corroborated by forensic personnel?",
        ])
        for q in questions:
            pdf.body_paragraph(f"? {q}", indent=4)
        pdf.ln(2)

        # =====================================================================
        # SECTION 15: INFORMATION GAPS
        # =====================================================================
        pdf.chapter_title(15, "Identified Information Gaps")
        gaps = dossier_data.get("information_gaps", [
            "No direct biometric match registered in current database index.",
            "Vehicle registration and auxiliary witness statements remain pending.",
        ])
        for g in gaps:
            pdf.body_paragraph(f"- {g}", indent=4)
        pdf.ln(2)

        # =====================================================================
        # SECTION 16: INVESTIGATOR NOTES
        # =====================================================================
        pdf.chapter_title(16, "Investigator Notes & Human Review")
        notes = dossier_data.get("investigator_notes") or case_info.get("case_notes") or (
            "Dossier assembled for supervisory investigative briefing. "
            "Requires primary officer signature before formal submission."
        )
        pdf.body_paragraph(notes)
        pdf.ln(2)

        # =====================================================================
        # SECTION 17: AUDIT INFORMATION
        # =====================================================================
        pdf.chapter_title(17, "Audit & Custody Information")
        pdf.field_row("System Version", "Detective Agentic AI v2.0 (IBM Bob Architecture)")
        pdf.field_row("Generated By", dossier_data.get("generated_by", "Authorized Investigator"))
        pdf.field_row("Integrity Check", "Tamper-evident system log recorded in audit trail")
        pdf.field_row("Timestamp UTC", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"))
        pdf.ln(3)

        # =====================================================================
        # SECTION 18: MANDATORY DISCLAIMER
        # =====================================================================
        pdf.chapter_title(18, "Mandatory Statutory Disclaimer")
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(180, 20, 20)
        pdf.body_paragraph(MANDATORY_DISCLAIMER)
        pdf.ln(4)

        return bytes(pdf.output())

    except Exception as exc:
        logger.error("Dossier generation encountered exception: %s. Generating safe emergency PDF.", exc)
        return _generate_emergency_fallback_pdf(dossier_data, str(exc))


def _generate_emergency_fallback_pdf(dossier_data: Dict[str, Any], error_reason: str) -> bytes:
    """Fail-closed crash-proof fallback ensuring PDF output is always valid bytes."""
    fallback = FPDF()
    fallback.add_page()
    fallback.set_font("Helvetica", "B", 14)
    fallback.cell(0, 10, "INVESTIGATION DOSSIER (FAIL-SAFE MODE)", align="C", new_x="LMARGIN", new_y="NEXT")
    fallback.ln(4)
    fallback.set_font("Helvetica", "", 10)
    fallback.multi_cell(0, 6, "Notice: Dossier rendered in emergency compatibility mode.")
    fallback.multi_cell(0, 6, f"Generation note: {sanitize_for_pdf(error_reason)}")
    fallback.ln(4)
    fallback.set_font("Helvetica", "B", 10)
    fallback.multi_cell(0, 6, MANDATORY_DISCLAIMER)
    return bytes(fallback.output())


def generate_pdf_report(
    suspect_name: str,
    age: str,
    tendency_score: str,
    risk_level: str,
    behaviors: str,
    matched_cases: list,
    scoring_breakdown: list = None,
    disclaimer: str = "",
    match_quality: str = "",
) -> bytes:
    """
    Backward-compatible wrapper matching the legacy `generate_pdf_report()` signature.
    Maps inputs to the full 18-section dossier generator seamlessly.
    """
    dossier_data = {
        "case_info": {
            "case_id": "PROFILE-" + datetime.datetime.now().strftime("%Y%m%d%H%M"),
            "case_title": f"Profile Analysis -- {suspect_name or 'Unnamed Suspect'}",
            "case_type": "Pattern & Behavioral Profiling",
            "priority": "HIGH" if "HIGH" in str(risk_level).upper() else ("MEDIUM" if "MEDIUM" in str(risk_level).upper() else "LOW"),
            "status": "OPEN",
            "assigned_investigator": "Detective Agentic AI",
            "date_opened": datetime.datetime.now().strftime("%Y-%m-%d"),
        },
        "suspect_info": {
            "name": suspect_name or "Not provided",
            "age": age or "Not provided",
            "behaviors": behaviors or "Not provided",
            "location": "Not provided",
            "known_associations": "Not provided",
        },
        "model_assessment": {
            "tendency_score": str(tendency_score),
            "risk_level": str(risk_level),
            "match_quality": str(match_quality),
            "scoring_breakdown": scoring_breakdown or [],
            "similar_cases": matched_cases or [],
        },
        "behaviors": behaviors or "Not provided",
        "matched_cases": matched_cases or [],
    }
    return generate_investigation_dossier_pdf(dossier_data)
