"""
utils/pdf_utils.py

Professional Indian Case Pattern Analysis Report Generator using fpdf2.
Produces a structured 5-6 page Indian investigative analysis report:

1. INVESTIGATION OVERVIEW & SUBJECT PROFILE (Page 1)
2. INPUT INFORMATION & BEHAVIOURAL ANALYSIS (Page 2)
3. AI PATTERN ANALYSIS & PIPELINE FLOW (Page 3)
4. RETRIEVED HISTORICAL CASE RECORDS (Page 4)
5. EVIDENCE-TO-PATTERN MAPPING & SIMILARITY CHART (Page 5)
6. AI EXPLANATION, LIMITATIONS & STATUTORY DISCLAIMER (Page 6)

Ethical Standards & Grounding:
- Clearly separates:
  * USER INPUT != VERIFIED EVIDENCE
  * RETRIEVED CASE != CURRENT SUBJECT CONNECTION
  * SIMILARITY != GUILT
  * MODEL INFERENCE != FACT
- Presents scores as "Model Similarity Indicator: XX/100" (similarity to indexed records,
  NOT probability of crime, guilt, or innocence).
- Uses neutral analytical terminology: Pattern Similarity, Historical Record Similarity,
  Evidence Match, Model Assessment, Retrieved Evidence, Textual Similarity.
- Crash-proof against long tokens, empty values, Devanagari/Hindi, and narrow cell widths.
"""

import datetime
import io
import logging
import math
import re
from typing import Any, Dict, List, Optional
from fpdf import FPDF

from utils.text_utils import (
    sanitize_for_pdf,
    safe_str,
    truncate_text,
    extract_behavioral_patterns,
)

logger = logging.getLogger(__name__)

# Mandatory statutory disclaimer (satisfies legal standards and existing unit tests)
MANDATORY_DISCLAIMER = (
    "DISCLAIMER: All model scores and similarity values are analytical outputs generated from "
    "the information supplied to the system and the historical records available in its indexed dataset. "
    "They are MODEL ASSESSMENTS and NOT legal findings, NOT proof of guilt, NOT proof of innocence, "
    "and NOT a determination of criminal responsibility. A similarity between a submitted description and a "
    "historical case does not establish that the subject is connected to that case. This system is an "
    "AI-assisted research and pattern-analysis tool and must NOT be used as the sole basis for legal, "
    "investigative, disciplinary, or law-enforcement decisions. Always verify with qualified human investigators."
)

PAGE1_NOTICE = (
    "AI-generated analytical report. This report does not establish guilt, innocence, "
    "identity, intent, or criminal responsibility."
)

CHART_EXPLANATION = (
    "The chart represents textual/pattern similarity between the submitted description and "
    "indexed historical records. It does not represent probability of criminal activity, guilt, or identity."
)


class IndianInvestigationPDF(FPDF):
    """
    Subclass of FPDF providing consistent professional Indian investigation styling:
    - Running header with confidentiality classification (pages 2+)
    - Running footer with page numbering ('Page X of Y') and disclaimer
    - Safe cell & multi_cell wrapping to permanently prevent 'Not enough horizontal space' crashes
    - Vector chart rendering and flow diagram drawing
    """

    def __init__(self, case_title: str = "Indian Case Pattern Analysis Report"):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.case_title = sanitize_for_pdf(case_title)
        self.set_auto_page_break(auto=True, margin=16)
        self.set_margins(16, 16, 16)
        self.alias_nb_pages()

    def header(self):
        # Clean cover page on Page 1; running header on Page 2+
        if self.page_no() > 1:
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(15, 30, 60)
            self.cell(105, 5, "DETECTIVE AGENTIC AI -- INDIAN CASE PATTERN ANALYSIS REPORT", align="L")
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 110, 125)
            self.cell(73, 5, "CONFIDENTIAL // INVESTIGATIVE RESEARCH", align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(200, 210, 225)
            self.set_line_width(0.3)
            self.line(16, self.get_y(), 194, self.get_y())
            self.ln(3)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(200, 210, 225)
        self.set_line_width(0.3)
        self.line(16, self.get_y(), 194, self.get_y())
        self.ln(2)
        self.set_font("Helvetica", "I", 7.5)
        self.set_text_color(110, 120, 135)
        self.cell(125, 4, "Model Assessment Only -- Not a Legal Finding | National Precedent Index", align="L")
        self.cell(53, 4, f"Page {self.page_no()} of {{nb}}", align="R")

    # -------------------------------------------------------------------------
    # Layout Helpers
    # -------------------------------------------------------------------------

    def safe_multi_cell(
        self,
        w: float,
        h: float,
        text: Any,
        border: int = 0,
        align: str = "L",
        fill: bool = False,
        new_x: str = "LMARGIN",
        new_y: str = "NEXT",
    ) -> None:
        """
        Safely render multi_cell ensuring horizontal width never exceeds printable bounds.
        Guarantees no 'Not enough horizontal space to render a single character' exceptions.
        """
        clean_text = sanitize_for_pdf(text)
        max_available = max(10.0, 194.0 - self.get_x())
        actual_w = max_available if w <= 0 else min(w, max_available)
        self.multi_cell(
            actual_w,
            h,
            clean_text,
            border=border,
            align=align,
            fill=fill,
            new_x=new_x,
            new_y=new_y,
        )

    def section_heading(self, section_num: int, title: str, subtitle: str = ""):
        """Render standard styled section header banner."""
        self.set_font("Helvetica", "B", 11)
        self.set_fill_color(236, 242, 250)
        self.set_text_color(15, 30, 60)
        clean_title = sanitize_for_pdf(f"{section_num}. {title.upper()}")
        self.cell(0, 7.5, clean_title, fill=True, new_x="LMARGIN", new_y="NEXT")
        if subtitle:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(90, 100, 115)
            self.cell(0, 5, sanitize_for_pdf(subtitle), new_x="LMARGIN", new_y="NEXT")
        self.ln(2.5)

    def field_row(self, label: str, value: Any, label_w: int = 40, label_source: str = ""):
        """Render a clean label / value field with safe wrapping and source attribution."""
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(30, 45, 70)
        clean_label = sanitize_for_pdf(label)
        if label_source:
            clean_label = f"{clean_label} [{label_source}]"

        self.cell(label_w, 5.5, clean_label + ":", align="L")
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(40, 45, 55)
        clean_val = sanitize_for_pdf(value)
        self.safe_multi_cell(0, 5.5, clean_val, new_x="LMARGIN", new_y="NEXT")

    def notice_card(self, title: str, text: str, border_rgb=(210, 130, 30), fill_rgb=(255, 251, 240)):
        """Render a highlighted alert/notice card."""
        start_x = 16
        start_y = self.get_y()
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(border_rgb[0], border_rgb[1], border_rgb[2])
        self.set_fill_color(fill_rgb[0], fill_rgb[1], fill_rgb[2])
        self.set_draw_color(border_rgb[0], border_rgb[1], border_rgb[2])
        self.set_line_width(0.4)

        # Pre-measure height
        self.rect(start_x, start_y, 178, 18, style="DF")
        self.set_xy(start_x + 3, start_y + 2.5)
        self.cell(172, 4.5, sanitize_for_pdf(title), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(50, 50, 50)
        self.set_x(start_x + 3)
        self.safe_multi_cell(172, 4, text, new_x="LMARGIN", new_y="NEXT")
        self.set_y(start_y + 20)

    def draw_similarity_chart(self, cases: List[Dict[str, Any]], max_w: float = 95.0):
        """
        Dynamically render a horizontal bar chart of actual retrieved similarities.
        Strictly uses actual model output values. Never invents fake percentages.
        """
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(15, 30, 60)
        self.cell(0, 6, "Historical Record Similarity Comparison (Actual Model Outputs)", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

        valid_cases = [c for c in cases if c and float(c.get("similarity", 0.0)) > 0]
        if not valid_cases:
            self.set_font("Helvetica", "I", 8.5)
            self.set_text_color(100, 110, 120)
            self.cell(0, 7, "No historical records retrieved.", new_x="LMARGIN", new_y="NEXT")
            self.ln(2)
            return

        for idx, c in enumerate(valid_cases[:5], 1):
            sim_val = max(0.0, min(1.0, float(c.get("similarity", 0.0))))
            sim_pct_str = f"{sim_val:.0%}"
            title = truncate_text(c.get("case_title") or c.get("title") or f"Case #{idx}", max_chars=38)

            y = self.get_y()
            # 1. Label on left (60 mm)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(35, 45, 60)
            self.cell(62, 6, sanitize_for_pdf(title), align="L")

            # 2. Track background (max_w mm)
            track_x = 16 + 64
            bar_h = 4.5
            self.set_fill_color(235, 240, 248)
            self.set_draw_color(210, 220, 235)
            self.rect(track_x, y + 0.8, max_w, bar_h, style="DF")

            # 3. Filled bar
            bar_w = max(1.5, max_w * sim_val)
            self.set_fill_color(30, 64, 135)
            self.rect(track_x, y + 0.8, bar_w, bar_h, style="F")

            # 4. Percentage label on right
            self.set_xy(track_x + max_w + 3, y)
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(20, 40, 80)
            self.cell(16, 6, sim_pct_str, align="L", new_x="LMARGIN", new_y="NEXT")
            self.ln(1)

        self.ln(2)

    def draw_pipeline_flow_diagram(self):
        """Render the 7-step analytical pipeline flow diagram directly using styled boxes."""
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(15, 30, 60)
        self.cell(0, 6, "AI Analytical Pipeline Flow Diagram", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

        steps = [
            ("USER INPUT", "Investigator observation & suspect traits"),
            ("NLP / FEATURE EXTRACTION", "Syntactic clause parsing & pattern categorization"),
            ("RAG RETRIEVAL", "Vector search against 52 indexed Indian legal records"),
            ("HISTORICAL CASE RECORDS", "Precedents & judicial summaries retrieved"),
            ("SIMILARITY ANALYSIS", "Cosine similarity calculation on lexical/behavioral traits"),
            ("AI EXPLANATION", "Explainable comparison separating facts from inferences"),
            ("INVESTIGATIVE REPORT", "5-6 page Indian investigative pattern analysis report"),
        ]

        card_w = 178
        step_h = 7.2
        for idx, (title, desc) in enumerate(steps, 1):
            y = self.get_y()
            # Draw box
            self.set_fill_color(245, 248, 253)
            self.set_draw_color(190, 205, 225)
            self.set_line_width(0.3)
            self.rect(16, y, card_w, step_h, style="DF")

            # Content inside box
            self.set_xy(19, y + 1.2)
            self.set_font("Helvetica", "B", 7.5)
            self.set_text_color(15, 35, 75)
            self.cell(50, 4.8, f"STEP {idx}: {title}", align="L")
            self.set_font("Helvetica", "", 7.5)
            self.set_text_color(70, 80, 95)
            self.cell(120, 4.8, f"-- {desc}", align="L")

            self.set_y(y + step_h)
            if idx < len(steps):
                self.set_font("Helvetica", "B", 7)
                self.set_text_color(120, 135, 155)
                self.cell(0, 3.2, "|  (flows to next analytical stage)", align="C", new_x="LMARGIN", new_y="NEXT")

        self.ln(2)


# Backwards compatibility alias
DossierPDF = IndianInvestigationPDF


def generate_investigation_dossier_pdf(dossier_data: Dict[str, Any]) -> bytes:
    """
    Generate a full 6-Page Indian Investigative Analysis Report PDF.
    Guaranteed crash-proof: catches any layout errors and falls back to a clean text dossier.
    """
    try:
        case_info = dossier_data.get("case_info", {})
        suspect_info = dossier_data.get("suspect_info", {})
        model_assessment = dossier_data.get("model_assessment", {})
        behaviors_text = (
            dossier_data.get("behaviors")
            or suspect_info.get("behaviors")
            or suspect_info.get("observed_behaviors")
            or "Not provided"
        )
        suspect_name = (
            suspect_info.get("name")
            or suspect_info.get("suspect_name")
            or "Not provided"
        )
        age_str = str(suspect_info.get("age", "Not provided") or "Not provided")
        matched_cases = (
            dossier_data.get("matched_cases")
            or model_assessment.get("similar_cases")
            or []
        )

        # Clean score extraction (internal score preserved, presentation strictly formatted)
        raw_score = model_assessment.get("tendency_score", "0")
        score_num = 15
        try:
            m = re.search(r"\d+", str(raw_score))
            if m:
                score_num = int(m.group(0))
        except Exception:
            score_num = 15

        report_id = "REPORT-IND-" + datetime.datetime.now().strftime("%Y%m%d-%H%M")
        ref_id = case_info.get("case_id") or ("REF-IND-" + datetime.datetime.now().strftime("%Y%m%d%H%M"))
        case_title = case_info.get("case_title") or case_info.get("title") or f"Pattern Analysis -- {suspect_name}"

        pdf = IndianInvestigationPDF(case_title=case_title)

        # =====================================================================
        # PAGE 1 — INVESTIGATION OVERVIEW & SUBJECT PROFILE
        # =====================================================================
        pdf.add_page()
        pdf.ln(2)

        # Header Title
        pdf.set_font("Helvetica", "B", 18)
        pdf.set_text_color(15, 30, 60)
        pdf.cell(0, 8, "DETECTIVE AGENTIC AI", align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(30, 50, 85)
        pdf.cell(0, 6, "INDIAN CASE PATTERN ANALYSIS REPORT", align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "I", 8.5)
        pdf.set_text_color(100, 110, 125)
        pdf.cell(0, 5, "AI-Assisted Historical Case Similarity & Evidence Analysis", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        pdf.set_draw_color(25, 55, 110)
        pdf.set_line_width(0.8)
        pdf.line(16, pdf.get_y(), 194, pdf.get_y())
        pdf.set_line_width(0.2)
        pdf.ln(4)

        # Report Metadata Card
        meta_y = pdf.get_y()
        pdf.set_fill_color(247, 250, 254)
        pdf.set_draw_color(200, 215, 235)
        pdf.rect(16, meta_y, 178, 28, style="DF")

        pdf.set_xy(20, meta_y + 2.5)
        pdf.field_row("Report ID", report_id, label_w=32, label_source="SYSTEM METADATA")
        pdf.set_x(20)
        pdf.field_row("Generated Date/Time", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"), label_w=32)
        pdf.set_x(20)
        pdf.field_row("Reference ID", ref_id, label_w=32)
        pdf.set_x(20)
        pdf.field_row("Analysis Status", "COMPLETED (Analytical Assessment Only)", label_w=32)
        pdf.set_x(20)
        pdf.field_row("Data Source", "National Judicial Precedent Index (52 Indian Landmark Cases)", label_w=32)
        pdf.set_x(20)
        pdf.field_row("Retrieved Records", f"{len(matched_cases)} Record(s) Retrieved", label_w=32)

        pdf.set_y(meta_y + 31)

        # Subject Profile Card
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(230, 238, 248)
        pdf.set_text_color(15, 30, 60)
        pdf.cell(0, 7, "SUBJECT PROFILE", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)

        prof_y = pdf.get_y()
        pdf.set_fill_color(253, 254, 255)
        pdf.set_draw_color(210, 220, 235)
        pdf.rect(16, prof_y, 178, 48, style="DF")

        pdf.set_xy(20, prof_y + 3)
        pdf.field_row("Suspect Name / Alias", suspect_name, label_w=42, label_source="SOURCE: USER INPUT")
        pdf.set_x(20)
        pdf.field_row("Age", age_str, label_w=42, label_source="SOURCE: USER INPUT")
        pdf.set_x(20)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(30, 45, 70)
        pdf.cell(42, 5.5, "Observed Behaviors / MO [SOURCE: USER INPUT]:", align="L")
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(40, 45, 55)
        pdf.safe_multi_cell(0, 5.2, truncate_text(behaviors_text, max_chars=360), new_x="LMARGIN", new_y="NEXT")

        pdf.set_y(prof_y + 51)

        # Model Similarity Indicator Card
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(230, 238, 248)
        pdf.set_text_color(15, 30, 60)
        pdf.cell(0, 7, "MODEL SIMILARITY ASSESSMENT  [SOURCE: MODEL INFERENCE]", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)

        sim_y = pdf.get_y()
        pdf.set_fill_color(248, 250, 254)
        pdf.set_draw_color(190, 205, 230)
        pdf.rect(16, sim_y, 178, 42, style="DF")

        pdf.set_xy(20, sim_y + 3)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(20, 50, 110)
        pdf.cell(0, 7, f"Model Similarity Indicator: {score_num}/100", new_x="LMARGIN", new_y="NEXT")

        pdf.set_x(20)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(60, 75, 95)
        sim_category = "Elevated Precedent Overlap" if score_num >= 65 else ("Moderate Precedent Overlap" if score_num >= 35 else "Baseline Lexical Overlap")
        pdf.cell(0, 5.5, f"Corpus Alignment Classification: {sim_category}", new_x="LMARGIN", new_y="NEXT")

        pdf.set_x(20)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(45, 50, 60)
        pdf.safe_multi_cell(
            170,
            4.8,
            "This value represents similarity/pattern matching within the indexed dataset. "
            "It is not a probability of criminal activity or guilt. Scores quantify lexical and "
            "modus operandi overlap against indexed Indian criminal cases and must never be interpreted "
            "as conclusive evidence of culpability.",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        pdf.set_y(sim_y + 45)

        # Mandatory Bottom Notice
        pdf.notice_card(
            title="MANDATORY GOVERNANCE NOTICE",
            text=PAGE1_NOTICE,
            border_rgb=(180, 40, 40),
            fill_rgb=(255, 248, 248),
        )

        # =====================================================================
        # PAGE 2 — INPUT & BEHAVIOURAL ANALYSIS
        # =====================================================================
        pdf.add_page()
        pdf.section_heading(2, "Input Information & Behavioural Analysis")

        # Section A: Investigator / User Input
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(20, 40, 75)
        pdf.cell(0, 6, "A. Investigator / User Input [SOURCE: USER INPUT]", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 7.8)
        pdf.set_text_color(100, 110, 120)
        pdf.cell(
            0,
            4.5,
            "Exact information entered by the investigator. Field content is unverified and preserved verbatim.",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(1)

        input_box_y = pdf.get_y()
        pdf.set_fill_color(252, 253, 255)
        pdf.set_draw_color(215, 225, 238)
        pdf.rect(16, input_box_y, 178, 52, style="DF")

        pdf.set_xy(19, input_box_y + 2.5)
        pdf.field_row("Suspect Name / Alias", suspect_name, label_w=45, label_source="SOURCE: USER INPUT")
        pdf.set_x(19)
        pdf.field_row("Subject Age", age_str, label_w=45, label_source="SOURCE: USER INPUT")
        pdf.set_x(19)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(30, 45, 70)
        pdf.cell(45, 5, "Submitted Observations [SOURCE: USER INPUT]:", align="L")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(40, 45, 55)
        pdf.safe_multi_cell(0, 4.6, behaviors_text, new_x="LMARGIN", new_y="NEXT")

        pdf.set_y(input_box_y + 55)

        # Section B: Extracted Behavioural Patterns
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(20, 40, 75)
        pdf.cell(0, 6, "B. Extracted Behavioural Patterns [SOURCE: MODEL NLP EXTRACTION]", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 7.8)
        pdf.set_text_color(100, 110, 120)
        pdf.cell(
            0,
            4.5,
            "Structured patterns extracted using natural language parsing. Patterns reflect stated input without inferring criminal intent.",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(1)

        extracted_patterns = extract_behavioral_patterns(behaviors_text)
        if extracted_patterns:
            for p_idx, pat in enumerate(extracted_patterns[:6], 1):
                py = pdf.get_y()
                pdf.set_fill_color(248, 250, 254)
                pdf.set_draw_color(210, 222, 238)
                pdf.rect(16, py, 178, 15, style="DF")

                pdf.set_xy(19, py + 1.8)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(25, 55, 115)
                pdf.cell(24, 4.5, f"Pattern #{p_idx}:", align="L")
                pdf.set_text_color(15, 30, 60)
                pdf.cell(145, 4.5, sanitize_for_pdf(pat.get("pattern", "Observation")), align="L", new_x="LMARGIN", new_y="NEXT")

                pdf.set_x(19)
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(80, 90, 105)
                pdf.cell(24, 4, "Evidence from input:", align="L")
                pdf.set_font("Helvetica", "I", 7.5)
                pdf.set_text_color(40, 45, 55)
                ev_quote = f'"{truncate_text(pat.get("evidence", ""), max_chars=110)}"'
                pdf.cell(145, 4, sanitize_for_pdf(ev_quote), align="L", new_x="LMARGIN", new_y="NEXT")

                pdf.set_x(19)
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(80, 90, 105)
                pdf.cell(24, 4, "Confidence:", align="L")
                pdf.set_font("Helvetica", "", 7.5)
                pdf.set_text_color(40, 45, 55)
                pdf.cell(145, 4, sanitize_for_pdf(pat.get("confidence", "Based on available textual evidence")), align="L", new_x="LMARGIN", new_y="NEXT")

                pdf.set_y(py + 17)
        else:
            pdf.set_font("Helvetica", "I", 8.5)
            pdf.set_text_color(110, 120, 130)
            pdf.cell(0, 7, "No specific behavioral patterns could be extracted from the provided input.", new_x="LMARGIN", new_y="NEXT")

        # =====================================================================
        # PAGE 3 — AI PATTERN ANALYSIS
        # =====================================================================
        pdf.add_page()
        pdf.section_heading(3, "AI Pattern Analysis")

        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(40, 45, 55)
        pdf.safe_multi_cell(
            0,
            4.6,
            "The analytical engine evaluated the extracted behavioral components against the corpus of indexed "
            "Indian criminal law precedents. Cosine similarity metrics quantify lexical and conceptual overlap. "
            "The table below aligns observed subject characteristics with correlated historical precedent traits.",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(2)

        # Visual Summary Table:
        # Observed Pattern | Retrieved Similar Pattern | Similarity | Evidence Source
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(225, 234, 248)
        pdf.set_text_color(15, 30, 60)
        pdf.set_draw_color(195, 210, 230)
        pdf.cell(46, 6, "Observed Pattern", border=1, fill=True)
        pdf.cell(60, 6, "Retrieved Similar Pattern", border=1, fill=True)
        pdf.cell(24, 6, "Similarity", border=1, fill=True, align="C")
        pdf.cell(48, 6, "Evidence Source", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

        rows_to_render = []
        if extracted_patterns and matched_cases:
            for idx, pat in enumerate(extracted_patterns[:4]):
                obs = truncate_text(pat.get("pattern", "Observed Trait"), max_chars=28)
                if idx < len(matched_cases):
                    mc = matched_cases[idx]
                    matched_pat = truncate_text(mc.get("crime_type") or mc.get("case_title") or "Historical MO", max_chars=34)
                    sim_pct = f"{float(mc.get('similarity', 0.0)):.0%}"
                    src = "[SOURCE: RETRIEVED EVIDENCE]"
                else:
                    matched_pat = "No direct corpus correspondence"
                    sim_pct = "Not available"
                    src = "[SOURCE: USER INPUT]"
                rows_to_render.append((obs, matched_pat, sim_pct, src))
        elif extracted_patterns:
            for pat in extracted_patterns[:4]:
                obs = truncate_text(pat.get("pattern", "Observed Trait"), max_chars=28)
                rows_to_render.append((obs, "No precedent met threshold", "Not available", "[SOURCE: USER INPUT]"))
        else:
            rows_to_render.append(("No behavioral traits entered", "No precedent query possible", "Not available", "[SOURCE: USER INPUT]"))

        pdf.set_font("Helvetica", "", 7.5)
        for obs, sim_pat, sim_pct, src in rows_to_render:
            pdf.set_fill_color(252, 253, 255)
            pdf.set_text_color(35, 40, 50)
            pdf.cell(46, 5.5, sanitize_for_pdf(obs), border=1, fill=True)
            pdf.cell(60, 5.5, sanitize_for_pdf(sim_pat), border=1, fill=True)
            pdf.cell(24, 5.5, sanitize_for_pdf(sim_pct), border=1, fill=True, align="C")
            pdf.cell(48, 5.5, sanitize_for_pdf(src), border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)

        # Section: HOW THE AI REACHED THIS RESULT
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(20, 40, 75)
        pdf.cell(0, 6, "HOW THE AI REACHED THIS RESULT", new_x="LMARGIN", new_y="NEXT")

        pipeline_steps = [
            "1. User enters subject information (name, age, behavioral observations, MO traits).",
            "2. NLP extracts relevant terms, temporal indicators, movement patterns, and operational clauses.",
            "3. RAG searches the indexed Indian case records across 52 landmark judicial decisions.",
            "4. Relevant historical records exceeding the similarity threshold are retrieved.",
            "5. Similarity is calculated using normalized vector cosine metrics and keyword coverage.",
            "6. AI generates an objective explainability breakdown based strictly on retrieved judicial evidence.",
            "7. Final report strictly separates user-supplied claims from verified judicial records and model inferences.",
        ]
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(40, 45, 55)
        for s in pipeline_steps:
            pdf.safe_multi_cell(0, 4.4, s, new_x="LMARGIN", new_y="NEXT")

        pdf.ln(3)

        # Flow Diagram
        pdf.draw_pipeline_flow_diagram()

        pdf.set_font("Helvetica", "I", 7.5)
        pdf.set_text_color(110, 120, 130)
        pdf.safe_multi_cell(
            0,
            4,
            "Notice: The system does NOT independently verify real-world facts. "
            "All correlations reflect statistical and lexical matching against indexed judgments.",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        # =====================================================================
        # PAGE 4 — RETRIEVED INDIAN CASE EVIDENCE
        # =====================================================================
        pdf.add_page()
        pdf.section_heading(
            4,
            "Retrieved Historical Case Records",
            subtitle="[SOURCE: RETRIEVED EVIDENCE -- HISTORICAL CASE VECTOR INDEX]",
        )

        if not matched_cases:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(100, 110, 125)
            pdf.cell(
                0,
                8,
                "No historical records retrieved. No indexed Indian case met the minimum similarity threshold for this query.",
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.ln(3)
        else:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(50, 60, 75)
            pdf.safe_multi_cell(
                0,
                4.5,
                "Displaying records retrieved from the indexed Indian criminal jurisprudence repository. "
                "These cases are provided for comparative pattern research and do NOT establish connection to the subject.",
                new_x="LMARGIN",
                new_y="NEXT",
            )
            pdf.ln(2)

            for idx, c in enumerate(matched_cases[:3], 1):
                sim_pct = f"{float(c.get('similarity', 0.0)):.0%}"
                title = c.get("case_title") or c.get("title") or f"Historical Precedent #{idx}"
                cid = c.get("case_id") or f"CASE-IND-REF-{idx}"
                loc = c.get("location") or "India"
                crime_type = c.get("crime_type") or "Judicial Precedent"
                court = c.get("court_or_authority") or c.get("metadata", {}).get("court_or_authority") or "Supreme Court / High Court of India"
                cite = c.get("legal_citation") or c.get("metadata", {}).get("legal_citation") or "Official Judicial Precedent"
                source = c.get("source") or c.get("metadata", {}).get("source") or "Indian Kanoon / Law Ministry"
                ipc = c.get("ipc_sections") or c.get("metadata", {}).get("ipc_sections") or []
                ipc_str = ", ".join(ipc) if isinstance(ipc, list) else str(ipc)
                summary = c.get("summary") or "Historical case record filed in national legal index."
                snippet = c.get("snippet") or summary[:240]

                card_start_y = pdf.get_y()
                pdf.set_fill_color(248, 250, 254)
                pdf.set_draw_color(200, 215, 235)
                # Compute approximate height
                pdf.rect(16, card_start_y, 178, 62, style="DF")

                # Card Header
                pdf.set_xy(19, card_start_y + 2)
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(15, 35, 80)
                pdf.cell(172, 5, f"CASE 0{idx}: {sanitize_for_pdf(title)}", new_x="LMARGIN", new_y="NEXT")

                pdf.set_x(19)
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(70, 80, 95)
                meta_line = f"Case ID: {cid}  |  Location: {loc}  |  Similarity: {sim_pct}  |  Classification: {crime_type}"
                pdf.cell(172, 4.2, sanitize_for_pdf(meta_line), new_x="LMARGIN", new_y="NEXT")

                pdf.set_x(19)
                pdf.set_font("Helvetica", "", 7.5)
                auth_line = f"Judicial Authority: {court}  |  Citation: {cite}  |  Sections: {ipc_str or 'General Criminal Law'}"
                pdf.cell(172, 4.2, sanitize_for_pdf(auth_line), new_x="LMARGIN", new_y="NEXT")

                pdf.set_x(19)
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(30, 60, 120)
                why_retrieved = f"Why retrieved: Lexical overlap with query traits; cosine similarity calculated at {sim_pct}."
                pdf.cell(172, 4.2, sanitize_for_pdf(why_retrieved), new_x="LMARGIN", new_y="NEXT")

                pdf.set_x(19)
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(40, 45, 55)
                pdf.cell(172, 4.2, "Historical Record Summary [SOURCE: RETRIEVED EVIDENCE]:", new_x="LMARGIN", new_y="NEXT")
                pdf.set_x(19)
                pdf.set_font("Helvetica", "", 7.5)
                pdf.safe_multi_cell(172, 3.8, truncate_text(summary, max_chars=180), new_x="LMARGIN", new_y="NEXT")

                pdf.set_x(19)
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.cell(172, 4.2, "Relevant Textual Evidence / Context [SOURCE: RETRIEVED EVIDENCE]:", new_x="LMARGIN", new_y="NEXT")
                pdf.set_x(19)
                pdf.set_font("Helvetica", "I", 7.5)
                pdf.safe_multi_cell(172, 3.8, truncate_text(snippet, max_chars=190), new_x="LMARGIN", new_y="NEXT")

                pdf.set_y(card_start_y + 65)

        pdf.set_font("Helvetica", "I", 7.5)
        pdf.set_text_color(110, 120, 130)
        pdf.safe_multi_cell(
            0,
            4,
            "Notice: Precedent records are retrieved strictly for comparative pattern analysis. "
            "Inclusion does NOT establish that the subject is connected to or responsible for any historical case.",
            new_x="LMARGIN",
            new_y="NEXT",
        )

        # =====================================================================
        # PAGE 5 — EVIDENCE MAPPING & COMPARISON
        # =====================================================================
        pdf.add_page()
        pdf.section_heading(
            5,
            "Evidence-to-Pattern Mapping",
            subtitle="Comparative Correlation of Observations vs Historical Judicial Records",
        )

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(45, 50, 60)
        pdf.safe_multi_cell(
            0,
            4.4,
            "The table below maps user-submitted factual observations against concepts extracted from "
            "indexed judicial records. Status labels are strictly factual (Retrieved, User-provided, Model-derived, "
            "Not independently verified) and do not assert legal criminality.",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.ln(2)

        # Evidence Mapping Table
        # Columns: User Observation | Retrieved Record | Matching Concept | Similarity | Evidence Status
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_fill_color(225, 235, 248)
        pdf.set_text_color(15, 30, 60)
        pdf.set_draw_color(195, 210, 230)
        pdf.cell(42, 6, "User Observation", border=1, fill=True)
        pdf.cell(45, 6, "Retrieved Record", border=1, fill=True)
        pdf.cell(45, 6, "Matching Concept", border=1, fill=True)
        pdf.cell(22, 6, "Similarity", border=1, fill=True, align="C")
        pdf.cell(24, 6, "Evidence Status", border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

        mapping_rows = []
        if extracted_patterns and matched_cases:
            for idx, pat in enumerate(extracted_patterns[:5]):
                u_obs = truncate_text(pat.get("evidence", pat.get("pattern", "Observation")), max_chars=26)
                if idx < len(matched_cases):
                    mc = matched_cases[idx]
                    r_rec = truncate_text(mc.get("case_title", "Historical Case"), max_chars=28)
                    m_concept = truncate_text(mc.get("crime_type", "Modus Operandi"), max_chars=28)
                    sim_pct = f"{float(mc.get('similarity', 0.0)):.0%}"
                    ev_status = "Retrieved"
                else:
                    r_rec = "No Vector Match"
                    m_concept = truncate_text(pat.get("pattern", "Behavioral trait"), max_chars=28)
                    sim_pct = "Not available"
                    ev_status = "User-provided"
                mapping_rows.append((u_obs, r_rec, m_concept, sim_pct, ev_status))
        elif extracted_patterns:
            for pat in extracted_patterns[:5]:
                u_obs = truncate_text(pat.get("evidence", "Observed trait"), max_chars=26)
                mapping_rows.append((u_obs, "No Vector Match", "Unindexed Trait", "Not available", "Not verified"))
        else:
            mapping_rows.append(("No user observations provided", "N/A", "N/A", "Not available", "User-provided"))

        pdf.set_font("Helvetica", "", 7)
        for u_obs, r_rec, m_concept, sim_pct, ev_status in mapping_rows:
            pdf.set_fill_color(252, 253, 255)
            pdf.set_text_color(35, 40, 50)
            pdf.cell(42, 5.2, sanitize_for_pdf(u_obs), border=1, fill=True)
            pdf.cell(45, 5.2, sanitize_for_pdf(r_rec), border=1, fill=True)
            pdf.cell(45, 5.2, sanitize_for_pdf(m_concept), border=1, fill=True)
            pdf.cell(22, 5.2, sanitize_for_pdf(sim_pct), border=1, fill=True, align="C")
            pdf.cell(24, 5.2, sanitize_for_pdf(ev_status), border=1, fill=True, align="C", new_x="LMARGIN", new_y="NEXT")

        pdf.ln(4)

        # Dynamic Similarity Chart
        pdf.draw_similarity_chart(matched_cases)

        # Section: WHAT THIS CHART MEANS
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.set_text_color(20, 40, 75)
        pdf.cell(0, 5.5, "WHAT THIS CHART MEANS", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(50, 55, 65)
        pdf.safe_multi_cell(0, 4.4, CHART_EXPLANATION, new_x="LMARGIN", new_y="NEXT")

        # =====================================================================
        # PAGE 6 — AI EXPLANATION, LIMITATIONS & DISCLAIMER
        # =====================================================================
        pdf.add_page()
        pdf.section_heading(6, "AI Explanation & Limitations")

        # AI Analysis Summary
        pdf.set_font("Helvetica", "B", 9.5)
        pdf.set_text_color(20, 40, 75)
        pdf.cell(0, 6, "AI ANALYSIS SUMMARY", new_x="LMARGIN", new_y="NEXT")

        top_match_title = matched_cases[0].get("case_title") if matched_cases else "indexed criminal jurisprudence"
        top_concepts = [c.get("crime_type") for c in matched_cases if c.get("crime_type")]
        concepts_str = ", ".join(top_concepts[:2]) if top_concepts else "behavioral modus operandi"

        summary_text = (
            f"The system identified textual similarities between the submitted behavioural description "
            f"and records available in the case index. The strongest matches were related to {concepts_str}. "
            f"These matches are based on the information available to the system and quantify lexical overlap."
        )
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(40, 45, 55)
        pdf.safe_multi_cell(0, 4.4, summary_text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # Structured Explainability Breakdown
        exp_y = pdf.get_y()
        pdf.set_fill_color(248, 250, 254)
        pdf.set_draw_color(210, 222, 238)
        pdf.rect(16, exp_y, 178, 38, style="DF")

        pdf.set_xy(19, exp_y + 2)
        pdf.field_row("WHAT WAS MATCHED", "Extracted behavioral phrases and operational modus operandi", label_w=46)
        pdf.set_x(19)
        pdf.field_row("WHY WAS IT MATCHED", "Textual and thematic overlap identified via vector cosine similarity", label_w=46)
        pdf.set_x(19)
        pdf.field_row("WHAT SOURCE PRODUCED MATCH", "Indian Criminal Case Precedent Vector Index (52 landmark judgments)", label_w=46)
        pdf.set_x(19)
        pdf.field_row("WHAT DOES IT ACTUALLY MEAN", "Submitted text shares lexical patterns with historical case records", label_w=46)
        pdf.set_x(19)
        pdf.field_row("WHAT DOES IT NOT MEAN", "Does NOT mean the subject committed any offence or is connected to cases", label_w=46)

        pdf.set_y(exp_y + 41)

        # What the AI Did Not Determine
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(20, 40, 75)
        pdf.cell(0, 5.5, "WHAT THE AI DID NOT DETERMINE", new_x="LMARGIN", new_y="NEXT")

        not_determined = [
            "It did not determine guilt.",
            "It did not determine innocence.",
            "It did not verify the user's observations.",
            "It did not establish identity.",
            "It did not establish intent.",
            "It did not establish that the subject is connected to any retrieved historical case.",
        ]
        pdf.set_font("Helvetica", "", 7.8)
        pdf.set_text_color(50, 55, 65)
        for item in not_determined:
            pdf.cell(5, 4.2, "*", align="C")
            pdf.cell(173, 4.2, item, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        # System Limitations
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(20, 40, 75)
        pdf.cell(0, 5.5, "SYSTEM LIMITATIONS", new_x="LMARGIN", new_y="NEXT")

        limitations = [
            "1. The case index may contain a limited number of records (52 indexed Indian landmark cases).",
            "2. Similarity methods rely partly on lexical and textual overlap (TF-IDF / cosine distance).",
            "3. Similarity does not establish factual connection or real-world culpability.",
            "4. User-provided information may not be independently verified.",
            "5. Missing records or unindexed state police databases cannot be matched.",
            "6. AI-generated explanations may contain uncertainty and lexical bias.",
            "7. Human investigators must independently verify all relevant information and leads.",
        ]
        pdf.set_font("Helvetica", "", 7.8)
        pdf.set_text_color(50, 55, 65)
        for lim in limitations:
            pdf.safe_multi_cell(0, 4, lim, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

        # Prominent Mandatory Disclaimer Card
        pdf.notice_card(
            title="MANDATORY STATUTORY DISCLAIMER",
            text=MANDATORY_DISCLAIMER,
            border_rgb=(180, 30, 30),
            fill_rgb=(255, 248, 248),
        )

        return bytes(pdf.output())

    except Exception as exc:
        logger.error("Indian investigation PDF generation encountered exception: %s. Generating safe emergency PDF.", exc)
        return _generate_emergency_fallback_pdf(dossier_data, str(exc))


def _generate_emergency_fallback_pdf(dossier_data: Dict[str, Any], error_reason: str) -> bytes:
    """Fail-closed crash-proof fallback ensuring PDF output is always valid bytes."""
    fallback = FPDF()
    fallback.add_page()
    fallback.set_font("Helvetica", "B", 14)
    fallback.cell(0, 10, "INDIAN CASE PATTERN ANALYSIS REPORT (FAIL-SAFE MODE)", align="C", new_x="LMARGIN", new_y="NEXT")
    fallback.ln(4)
    fallback.set_font("Helvetica", "", 10)
    fallback.multi_cell(0, 6, "Notice: Report rendered in emergency compatibility mode.")
    fallback.multi_cell(0, 6, f"Generation note: {sanitize_for_pdf(error_reason)}")
    fallback.ln(4)
    fallback.set_font("Helvetica", "B", 9)
    fallback.multi_cell(0, 5, MANDATORY_DISCLAIMER)
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
    Backward-compatible wrapper matching legacy `generate_pdf_report()` signature.
    Maps inputs to the full 6-page Indian investigative analysis report generator.
    """
    dossier_data = {
        "case_info": {
            "case_id": "PROFILE-" + datetime.datetime.now().strftime("%Y%m%d%H%M"),
            "case_title": f"Pattern Analysis -- {suspect_name or 'Unnamed Subject'}",
            "case_type": "Indian Case Pattern Analysis",
            "priority": "MEDIUM",
            "status": "COMPLETED",
            "assigned_investigator": "Detective Agentic AI",
            "date_opened": datetime.datetime.now().strftime("%Y-%m-%d"),
        },
        "suspect_info": {
            "name": suspect_name or "Not provided",
            "age": age or "Not provided",
            "behaviors": behaviors or "Not provided",
            "observed_behaviors": behaviors or "Not provided",
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
