import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import json
import time
import re
import io
import secrets
import shutil
import datetime
import pandas as pd
from fpdf import FPDF
from agent.analyzer import DetectiveAgent
from agent.outreach import (
    scrape_leads_sync,
    send_cold_emails,
    load_leads,
    save_leads,
    COLD_EMAIL_SUBJECT,
    COLD_EMAIL_BODY,
    LEADS_FILE,
)
from agent.billing import (
    submit_payment,
    submit_topup,
    approve_payment,
    reject_payment,
    flag_partial,
    get_pending_payments,
    get_partial_by_utr,
    load_payments,
    save_payments,
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_PARTIAL,
    STATUS_TOPUP_DONE,
    STATUS_FLAGGED,
    STATUS_INVALID_UTR,
)
from database.connection import init_db, migrate_existing_cases
from frontend.cases_view import render_case_management
from frontend.suspects_view import render_suspect_management
from frontend.evidence_view import render_evidence_management
from frontend.timeline_view import render_timeline_management
from frontend.anomaly_view import render_anomaly_dashboard
from frontend.graph_view import render_relationship_graph
from frontend.dashboard_view import render_analytics_dashboard
from frontend.audit_view import render_audit_trail_view




# Initialize database schema and migrate existing JSON cases on startup
try:
    init_db()
    migrate_existing_cases()
except Exception as _db_err:
    pass


st.set_page_config(
    page_title="Detective Agentic AI - Criminal Profiler",
    page_icon="🕵️‍♂️",
    layout="wide"
)

def _get_platform_url() -> str:
    for source in (
        lambda: str(st.secrets["PLATFORM_URL"]).strip(),
        lambda: str(os.environ.get("PLATFORM_URL", "")).strip(),
    ):
        try:
            v = source()
            if v:
                return v
        except Exception:
            pass
    return "https://skilluphackathon2026-crvfgw9pkgzk3bzrmhwmfq.streamlit.app"

PLATFORM_URL = _get_platform_url()

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
TRIAL_USAGE_FILE = os.path.join(DATA_DIR, "trial_usage.json")
TRIAL_LIMIT = 25

def _ensure_data():
    os.makedirs(DATA_DIR, exist_ok=True)

def _get_trial_user_id() -> str:
    """Keep a stable browser identifier across Streamlit reruns and refreshes."""
    try:
        current_id = str(st.query_params.get("trial_user", "")).strip()
    except Exception:
        current_id = ""

    if current_id and re.fullmatch(r"[A-Za-z0-9_-]{20,100}", current_id):
        return current_id

    new_id = secrets.token_urlsafe(24)
    st.query_params["trial_user"] = new_id
    st.rerun()
    return new_id

def _load_trial_usage():
    _ensure_data()
    if not os.path.exists(TRIAL_USAGE_FILE):
        return {}
    try:
        with open(TRIAL_USAGE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}

def _save_trial_usage(usage):
    _ensure_data()
    with open(TRIAL_USAGE_FILE, "w", encoding="utf-8") as f:
        json.dump(usage, f, indent=2, ensure_ascii=False)

def _trial_remaining(user_id: str) -> int:
    record = _load_trial_usage().get(user_id, {})
    try:
        used = max(0, int(record.get("used", 0)))
    except (AttributeError, TypeError, ValueError):
        used = 0
    return max(0, TRIAL_LIMIT - min(TRIAL_LIMIT, used))

def _consume_trial(user_id: str) -> int:
    usage = _load_trial_usage()
    record = usage.get(user_id, {})
    try:
        used = max(0, int(record.get("used", 0)))
    except (AttributeError, TypeError, ValueError):
        used = 0

    if used >= TRIAL_LIMIT:
        return 0

    usage[user_id] = {
        "used": used + 1,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_trial_usage(usage)
    return TRIAL_LIMIT - used - 1

_ADMIN_PIN_DEFAULT = "739"  # overridden by ADMIN_PIN secret/env var

def _get_admin_pin() -> str:
    """Read admin PIN from Streamlit secrets, env var, or fall back to default."""
    for source in (
        lambda: str(st.secrets["ADMIN_PIN"]).strip(),
        lambda: str(os.environ.get("ADMIN_PIN", "")).strip(),
    ):
        try:
            pin = source()
            if re.fullmatch(r"\d{3,8}", pin):
                return pin
        except Exception:
            pass
    return _ADMIN_PIN_DEFAULT

def _get_upi_vpa() -> str:
    for source in (
        lambda: str(st.secrets["UPI_VPA"]).strip(),
        lambda: str(os.environ.get("UPI_VPA", "")).strip(),
    ):
        try:
            v = source()
            if v:
                return v
        except Exception:
            pass
    return "ankitjsr12345@okaxis"

def _get_upi_name() -> str:
    for source in (
        lambda: str(st.secrets["UPI_NAME"]).strip(),
        lambda: str(os.environ.get("UPI_NAME", "")).strip(),
    ):
        try:
            v = source()
            if v:
                return v
        except Exception:
            pass
    return "Mr Ankit Kumar"

def _get_gmail_app_password() -> str:
    """Read the Gmail App Password from Streamlit secrets or env vars."""
    for key in ("GMAIL_APP_PASSWORD", "EMAIL_APP_PASSWORD", "GMAIL_PASSWORD"):
        for source in (
            lambda k=key: str(st.secrets[k]).strip(),
            lambda k=key: str(os.environ.get(k, "")).strip(),
        ):
            try:
                value = source()
                if value:
                    return value
            except Exception:
                pass
    return ""

_ss_defaults = {
    "evals_left": 25,
    "max_evals": 25,
    "quota_source": "trial",
    "current_tier": "Pro Agency Trial",
    "latest_results": None,
    "pending_plan": None,
    "pending_amount": None,
    "pending_evals": None,
    "is_admin": False,
    "admin_open": False,
    "show_billing_portal": False,
    "partial_utr": None,
    "analysis_history": [],
    "_admin_fail_count": 0,
    "_admin_lockout_until": 0.0,
}
for k, v in _ss_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

TRIAL_USER_ID = _get_trial_user_id()
if "trial_quota_loaded" not in st.session_state:
    st.session_state.evals_left = _trial_remaining(TRIAL_USER_ID)
    st.session_state.max_evals = TRIAL_LIMIT
    st.session_state.quota_source = "trial"
    st.session_state.trial_quota_loaded = True

@st.cache_resource
def load_agent():
    return DetectiveAgent()

agent = load_agent()

UPI_VPA = _get_upi_vpa()
UPI_NAME = _get_upi_name()

def make_upi_qr(amount: int, plan_ref: str) -> bytes:
    upi_uri = (
        f"upi://pay?pa={UPI_VPA}&pn={UPI_NAME.replace(' ', '%20')}"
        f"&am={amount}&cu=INR&tn={plan_ref.replace(' ', '_')}"
    )
    try:
        import segno
        buf = io.BytesIO()
        qr = segno.make(upi_uri, error="H")
        qr.save(buf, kind="png", scale=8, border=4, dark="black", light="white")
        buf.seek(0)
        return buf.getvalue()
    except ImportError:
        pass

    import qrcode as _qr
    import qrcode.constants as _qrc
    q = _qr.QRCode(error_correction=_qrc.ERROR_CORRECT_H, box_size=8, border=4)
    q.add_data(upi_uri)
    q.make(fit=True)
    pil_img = q.make_image(fill_color="black", back_color="white").get_image()
    buf = io.BytesIO()
    pil_img.save(buf, "PNG")
    buf.seek(0)
    return buf.getvalue()

import re as _re

def _safe_pdf_text(value, default: str = "Not provided") -> str:
    """Sanitise text for fpdf2 (Helvetica / Latin-1 core font).

    Steps applied in order:
    1. Coerce to str and strip leading/trailing whitespace.
    2. Strip Markdown bold/italic markers (**text**, *text*, __text__).
    3. Map known Unicode characters to ASCII equivalents.
    4. Wrap any single whitespace-free token longer than 80 chars so it
       cannot trigger fpdf2's "Not enough horizontal space" error.
    5. Encode to Latin-1, replacing any remaining unmapped characters
       with '?' rather than raising an exception.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return default

    text = str(value).strip()

    # 2. Strip Markdown bold/italic (**, *, __)
    text = _re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = _re.sub(r'__(.+?)__',     r'\1', text)
    text = _re.sub(r'\*(.+?)\*',     r'\1', text)

    # 3. Map known Unicode → ASCII
    replacements = {
        "\u20b9": "Rs.",   # ₹
        "\u2019": "'",     # right single quotation mark
        "\u2018": "'",     # left single quotation mark
        "\u201c": '"',     # left double quotation mark
        "\u201d": '"',     # right double quotation mark
        "\u2013": "-",     # en dash
        "\u2014": "--",    # em dash
        "\u2022": "*",     # bullet
        "\u2026": "...",   # ellipsis
        "\u2192": "->",    # rightwards arrow →
        "\u2190": "<-",    # leftwards arrow ←
        "\u00b0": "deg",   # degree sign
        "\u00a9": "(c)",   # copyright
        "\u00ae": "(R)",   # registered
        "\u2122": "(TM)",  # trade mark
        # emoji: warning sign and common variations
        "\u26a0": "[!]",
        "\ufe0f": "",      # variation selector (attached to emoji)
    }
    for uni, ascii_equiv in replacements.items():
        text = text.replace(uni, ascii_equiv)

    # 4. Wrap unbreakably long tokens (no whitespace > 80 chars)
    def _wrap_long_token(token: str, max_len: int = 80) -> str:
        if len(token) <= max_len:
            return token
        # Insert a soft newline every max_len characters
        return "\n".join(token[i:i + max_len] for i in range(0, len(token), max_len))

    text = " ".join(_wrap_long_token(tok) for tok in text.split(" "))

    # 5. Encode to Latin-1, replacing unmapped chars with '?'
    return text.encode("latin-1", errors="replace").decode("latin-1")


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
    """Generate a structured professional PDF dossier.

    Section structure:
      1. Executive Summary
      2. Input Information (USER INPUT)
      3. Risk Indicators (MODEL INFERENCE)
      4. Scoring Breakdown (MODEL INFERENCE — explainable)
      5. Behavioural Analysis (USER INPUT)
      6. RAG Retrieved Precedents (RETRIEVED EVIDENCE)
      7. Similarity Scores (RETRIEVED EVIDENCE)
      8. Model Assessment
      9. Limitations
     10. Timestamp & Disclaimer
    """
    if scoring_breakdown is None:
        scoring_breakdown = []

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # ---- Header ----
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "DETECTIVE AGENTIC AI - SUSPECT PROFILE DOSSIER", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 6, "Confidential - For Authorised Investigative Use Only", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)
    pdf.set_draw_color(50, 50, 50)
    pdf.line(20, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(6)

    def section_heading(title: str) -> None:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_fill_color(230, 230, 230)
        # Use multi_cell so long titles wrap; _safe_pdf_text sanitises em-dashes etc.
        pdf.multi_cell(0, 8, _safe_pdf_text(title), new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.ln(2)

    def body_line(label: str, value: str, label_prefix: str = "") -> None:
        # Render label and value on separate lines to avoid narrow-width multi_cell
        # crash that occurs when cursor is already 50 pt into the line.
        pdf.set_font("Helvetica", "B", 10)
        display_label = f"[{label_prefix}] {label}: " if label_prefix else f"{label}: "
        pdf.multi_cell(0, 7, _safe_pdf_text(display_label), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.set_x(30)  # indent value slightly under the label
        pdf.multi_cell(0, 7, _safe_pdf_text(value), new_x="LMARGIN", new_y="NEXT")

    def body_para(text: str, indent: int = 0) -> None:
        pdf.set_font("Helvetica", "", 10)
        if indent:
            pdf.set_x(20 + indent)
        pdf.multi_cell(0, 6, _safe_pdf_text(text), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    # ---- 1. Executive Summary ----
    section_heading("1. EXECUTIVE SUMMARY")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 6, _safe_pdf_text(
        f"This dossier presents a similarity-based risk assessment for suspect "
        f"'{_safe_pdf_text(suspect_name)}'. The risk indicator score of {tendency_score} "
        f"places this suspect in the '{risk_level}' category based on pattern matching "
        f"against {len(matched_cases)} historical case(s) in the case index. "
        f"Match quality: {match_quality or 'N/A'}. "
        "All scores are model assessments - not legal findings."
    ), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ---- 2. Input Information ----
    section_heading("2. INPUT INFORMATION  [SOURCE: USER INPUT]")
    body_line("Suspect Name / Alias", suspect_name or "Not provided", "USER INPUT")
    body_line("Age", age or "Not provided", "USER INPUT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "[USER INPUT] Observed Behaviors & MO:", new_x="LMARGIN", new_y="NEXT")
    body_para(behaviors or "Not provided")
    pdf.ln(2)

    # ---- 3. Risk Indicators ----
    section_heading("3. RISK INDICATORS  [SOURCE: MODEL INFERENCE]")
    body_line("Risk Indicator Score", tendency_score, "MODEL INFERENCE")
    body_line("Risk Category", risk_level, "MODEL INFERENCE")
    if match_quality:
        body_line("Match Quality", match_quality, "MODEL INFERENCE")
    pdf.ln(2)

    # ---- 4. Scoring Breakdown ----
    section_heading("4. SCORING BREAKDOWN  [SOURCE: MODEL INFERENCE - EXPLAINABLE]")
    if scoring_breakdown:
        for item in scoring_breakdown:
            pdf.set_font("Helvetica", "B", 10)
            # multi_cell instead of cell: factor names can be long
            pdf.multi_cell(0, 6, _safe_pdf_text(
                f"  Factor: {item.get('factor','?')}  -- {item.get('contribution',0)} pt(s)"
            ), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, _safe_pdf_text(f"    {item.get('explanation','')}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
    else:
        body_para("Scoring breakdown not available.")
    pdf.ln(2)

    # ---- 5. Behavioural Analysis ----
    section_heading("5. BEHAVIOURAL ANALYSIS  [SOURCE: USER INPUT]")
    body_para(
        "The following is a verbatim record of the observed behaviours submitted "
        "by the investigator. This is USER INPUT and has not been independently verified."
    )
    body_para(behaviors or "Not provided")
    pdf.ln(2)

    # ---- 6. RAG Retrieved Precedents ----
    section_heading("6. RAG RETRIEVED PRECEDENTS  [SOURCE: RETRIEVED EVIDENCE]")
    if matched_cases:
        for idx, case in enumerate(matched_cases, 1):
            sim_pct = f"{float(case.get('similarity', 0.0)):.0%}"
            pdf.set_font("Helvetica", "B", 10)
            # multi_cell: case titles can exceed page width
            pdf.multi_cell(0, 7,
                _safe_pdf_text(f"  {idx}. [RETRIEVED EVIDENCE] {case.get('case_title','Unknown Case')} ({case.get('location','N/A')})"),
                new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, _safe_pdf_text(f"     Case ID: {case.get('case_id','N/A')} | Crime Type: {case.get('crime_type','N/A')}"), new_x="LMARGIN", new_y="NEXT")
            if case.get("summary"):
                pdf.multi_cell(0, 5, _safe_pdf_text(f"     [FACT - Case Record]: {case['summary'][:200]}"), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
    else:
        body_para(
            "No sufficiently similar precedent found. No historical case in the index "
            "met the similarity threshold for this input."
        )
    pdf.ln(2)

    # ---- 7. Similarity Scores ----
    section_heading("7. SIMILARITY SCORES  [SOURCE: RETRIEVED EVIDENCE]")
    if matched_cases:
        for idx, case in enumerate(matched_cases, 1):
            sim_pct = f"{float(case.get('similarity', 0.0)):.0%}"
            dist = case.get("distance", "N/A")
            pdf.set_font("Helvetica", "", 10)
            # multi_cell: titles + metrics can exceed a single line
            pdf.multi_cell(0, 6,
                _safe_pdf_text(f"  {idx}. {case.get('case_title','Case')} -- Cosine Similarity: {sim_pct}  |  Distance: {dist}"),
                new_x="LMARGIN", new_y="NEXT")
    else:
        body_para("No similarity scores available - no cases met the retrieval threshold.")
    pdf.ln(4)

    # ---- 8. Model Assessment ----
    section_heading("8. MODEL ASSESSMENT  [SOURCE: MODEL INFERENCE]")
    body_para(
        f"Risk indicator score {tendency_score} corresponds to risk category: {risk_level}. "
        "This score is produced by cosine similarity matching against historical case records "
        "and/or a keyword severity heuristic. It is a SIMILARITY-BASED RESULT, not a legal "
        "determination. The absence of a match does NOT confirm innocence."
    )
    pdf.ln(2)

    # ---- 9. Limitations ----
    section_heading("9. LIMITATIONS")
    body_para(
        "1. The case index is limited to the cases manually uploaded to the system. "
        "Patterns outside this index will not be matched.\n"
        "2. TF/cosine similarity is a lexical (word-overlap) method — it does not "
        "understand context, intent, or nuance.\n"
        "3. A high similarity score does NOT mean the suspect committed a crime. "
        "It means their described behaviour shares textual overlap with historical records.\n"
        "4. This system must never replace qualified human investigative judgment.\n"
        "5. Results are only as good as the input provided."
    )
    pdf.ln(2)

    # ---- 10. Timestamp & Disclaimer ----
    section_heading("10. TIMESTAMP & DISCLAIMER")
    pdf.set_font("Helvetica", "", 9)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.multi_cell(0, 6, _safe_pdf_text(f"Report generated: {ts}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    # Build disclaimer: always use a safe ASCII fallback; _safe_pdf_text handles
    # any emoji (⚠️), Markdown, or Unicode passed in from the analyzer.
    disc = disclaimer or (
        "WARNING: All scores are MODEL ASSESSMENTS produced by similarity-based pattern "
        "matching. They are NOT legal findings, NOT proof of guilt, and must NOT be used "
        "as the sole basis for any legal or investigative decision. Always verify with "
        "qualified human investigators."
    )
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(0, 5, "DISCLAIMER", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(0, 5, _safe_pdf_text(disc), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())

# Sidebar
st.sidebar.header("⚙️ Case Indexer")
uploaded_file = st.sidebar.file_uploader("Upload Case JSON to Vector DB", type=["json"])
if uploaded_file is not None:
    try:
        case_data = json.load(uploaded_file)
        cases_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cases"))
        os.makedirs(cases_dir, exist_ok=True)
        save_path = os.path.join(cases_dir, uploaded_file.name)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(case_data, f, indent=4)
        indexed_count = agent.reload_cases()
        st.sidebar.success(
            f"Indexed '{uploaded_file.name}'! The active case index now contains "
            f"{indexed_count} cases."
        )
    except Exception as e:
        st.sidebar.error(f"Upload failed: {e}")

st.sidebar.divider()
st.sidebar.markdown("### B2B Agency Plan")
_max = st.session_state.max_evals
_left = st.session_state.evals_left
quota_display = "Unlimited" if _max == "Unlimited" else f"{min(_left, _max)}/{_max}"

st.sidebar.info(
    f"**Current Tier:** {st.session_state.current_tier}\n\n"
    f"**Evaluations Remaining:** {quota_display}"
)
if _max != "Unlimited" and isinstance(_left, int) and _left <= 0:
    st.sidebar.error("⚠️ Trial Limit Reached")

if st.sidebar.button("💳 Upgrade / Billing Portal", use_container_width=True, key="sb_upgrade"):
    st.session_state.show_billing_portal = not st.session_state.show_billing_portal
    if not st.session_state.show_billing_portal:
        st.session_state.pending_plan = None
        st.session_state.pending_amount = None
        st.session_state.pending_evals = None
    st.rerun()

if st.session_state.show_billing_portal:
    PLANS_SIDEBAR = {
        "🥉 Starter": {"amount": 500, "evals": 100, "label": "₹500/mo — 100 Evals"},
        "🥈 Pro": {"amount": 1000, "evals": 500, "label": "₹1,000/mo — 500 Evals"},
        "🥇 Enterprise": {"amount": 2000, "evals": "Unlimited", "label": "₹2,000/mo — Unlimited"},
    }
    st.sidebar.markdown("#### 📋 Choose a Plan")
    for pname, pinfo in PLANS_SIDEBAR.items():
        sb_key = f"sb_plan_{pname.replace(' ','_').replace('/','_')}"
        if st.sidebar.button(f"{pname} — {pinfo['label']}", key=sb_key, use_container_width=True):
            st.session_state.pending_plan = pname
            st.session_state.pending_amount = pinfo["amount"]
            st.session_state.pending_evals = pinfo["evals"]
            st.rerun()

    if st.session_state.pending_plan:
        _plan = st.session_state.pending_plan
        _amount = st.session_state.pending_amount
        _evals = st.session_state.pending_evals
        st.sidebar.markdown(f"---\n**💳 Pay for {_plan}**")
        st.sidebar.markdown(f"Amount: **₹{_amount:,}** · UPI: `{UPI_VPA}`")
        try:
            _qr_bytes = make_upi_qr(_amount, f"Plan_Upgrade_{_plan.split()[-1]}")
            st.sidebar.image(_qr_bytes, caption=f"Scan to Pay ₹{_amount:,}", width=200)
        except Exception:
            st.sidebar.code(
                f"upi://pay?pa={UPI_VPA}&pn={UPI_NAME.replace(' ', '%20')}"
                f"&am={_amount}&cu=INR&tn=Plan_Upgrade",
                language="text"
            )
        with st.sidebar.form(key="sb_utr_form"):
            _utr = st.text_input("UTR / Transaction Ref No.", placeholder="e.g. 426789012345", max_chars=30)
            _paid_str = st.text_input("Amount You Paid (₹)", placeholder=f"e.g. {_amount}", max_chars=10)
            _sub = st.form_submit_button("📨 Submit Payment Proof", use_container_width=True)
        if _sub:
            if not _utr.strip():
                st.sidebar.error("Please enter your UTR number.")
            elif not _paid_str.strip():
                st.sidebar.error("Please enter the amount you paid.")
            else:
                try:
                    _paid_val = float(_paid_str.replace(",", "").strip())
                except ValueError:
                    st.sidebar.error("Invalid amount — enter a number.")
                    _paid_val = None
                if _paid_val is not None:
                    _status, _msg, _remaining = submit_payment(
                        plan=_plan, required_amount=float(_amount),
                        amount_paid=_paid_val, evals=_evals, utr=_utr.strip()
                    )
                    if _status in (STATUS_FLAGGED, STATUS_INVALID_UTR):
                        st.sidebar.error(_msg)
                    elif _status == STATUS_PARTIAL:
                        st.sidebar.warning(_msg)
                        st.session_state.partial_utr = _utr.strip()
                        st.session_state.show_billing_portal = False
                        st.rerun()
                    else:
                        st.sidebar.success("✅ Submitted! Quota will be unlocked after admin verification.")
                        st.session_state.pending_plan = None
                        st.session_state.pending_amount = None
                        st.session_state.pending_evals = None
                        st.session_state.show_billing_portal = False
                        st.rerun()

if st.session_state.is_admin:
    if st.sidebar.button("🔄 Reset Demo & Clear Cache", use_container_width=True, key="sb_reset"):
        for k, v in _ss_defaults.items():
            st.session_state[k] = v
        st.session_state.evals_left = _trial_remaining(TRIAL_USER_ID)
        st.session_state.max_evals = TRIAL_LIMIT
        st.session_state.quota_source = "trial"
        st.session_state.trial_quota_loaded = True
        st.rerun()

st.sidebar.divider()
with st.sidebar.expander("🔐 Admin Portal", expanded=False):
    if st.session_state.is_admin:
        st.success("✅ Logged in as Admin")
        if st.button("🔓 Logout Admin", use_container_width=True, key="btn_admin_logout"):
            st.session_state.is_admin = False
            st.session_state.admin_open = False
            st.session_state.evals_left = _trial_remaining(TRIAL_USER_ID)
            st.session_state.max_evals = TRIAL_LIMIT
            st.session_state.quota_source = "trial"
            st.rerun()
    else:
        _MAX_ADMIN_ATTEMPTS = 5
        _LOCKOUT_SECONDS = 300  # 5 minutes
        _now = time.time()
        _locked_until = float(st.session_state.get("_admin_lockout_until", 0.0))
        _fail_count = int(st.session_state.get("_admin_fail_count", 0))

        if _now < _locked_until:
            _remaining_lock = int(_locked_until - _now)
            st.error(f"🔒 Too many failed attempts. Try again in {_remaining_lock}s.")
        else:
            admin_pw = st.text_input(
                "Admin PIN", type="password",
                placeholder="Enter admin PIN…", max_chars=8,
                key="admin_pw_input"
            )
            if st.button("🔑 Login", use_container_width=True, key="btn_admin_login"):
                if admin_pw and admin_pw == _get_admin_pin():
                    st.session_state.is_admin = True
                    st.session_state._admin_fail_count = 0
                    st.session_state._admin_lockout_until = 0.0
                    st.session_state.evals_left = "Unlimited"
                    st.session_state.max_evals = "Unlimited"
                    st.session_state.quota_source = "admin"
                    st.rerun()
                else:
                    _fail_count += 1
                    st.session_state._admin_fail_count = _fail_count
                    if _fail_count >= _MAX_ADMIN_ATTEMPTS:
                        st.session_state._admin_lockout_until = _now + _LOCKOUT_SECONDS
                        st.error(f"🔒 Too many failed attempts. Locked for {_LOCKOUT_SECONDS // 60} minutes.")
                    else:
                        _remaining = _MAX_ADMIN_ATTEMPTS - _fail_count
                        st.error(f"❌ Incorrect PIN. {_remaining} attempt(s) remaining.")

if st.session_state.is_admin:
    st.sidebar.divider()
    if st.sidebar.button("🛠️ Admin Payment Approvals", use_container_width=True, key="sb_admin"):
        st.session_state.admin_open = not st.session_state.admin_open
        st.rerun()

    if st.session_state.admin_open:
        st.sidebar.markdown("#### 🧾 All Pending Submissions")
        st.sidebar.warning(
            "UTRs and amounts are user claims until checked in your UPI/bank app. "
            "Approve only after the transaction, amount, and payee match."
        )
        _all_pending = get_pending_payments()
        if not _all_pending:
            st.sidebar.info("No pending submissions.")
        else:
            for i, pmt in enumerate(_all_pending):
                _putr = pmt.get("utr", "")
                _preq = pmt.get("required_amount", pmt.get("amount", 0))
                _ppaid = pmt.get("amount_paid", pmt.get("amount", 0))
                _premain = pmt.get("remaining_balance", 0)
                _pstatus = pmt.get("status", "")
                _pevals = pmt.get("evals", "?")
                _pplan = pmt.get("plan", "?")
                _label = f"#{i+1} {_pplan} — UTR: {_putr}"
                with st.sidebar.expander(_label):
                    st.write(f"**Plan:** {_pplan}")
                    st.write(f"**Required:** ₹{_preq:,}")
                    st.write(f"**Paid:** ₹{_ppaid:,}")
                    if _premain:
                        st.write(f"**Deficit:** ₹{_premain:,}")
                    st.write(f"**Status:** {_pstatus}")
                    st.write(f"**UTR:** `{_putr}`")
                    st.write(f"**Submitted:** {pmt.get('timestamp','')}")
                    if pmt.get("topup_utrs"):
                        st.write(f"**Top-up UTRs:** {', '.join(pmt['topup_utrs'])}")
                    _acol, _rcol, _fcol = st.columns(3)
                    if _acol.button("✅ Approve", key=f"pay_verify_{_putr}_approve"):
                        if approve_payment(_putr):
                            evals = _pevals
                            if evals == "Unlimited":
                                st.session_state.evals_left = "Unlimited"
                                st.session_state.max_evals = "Unlimited"
                                st.session_state.quota_source = "paid"
                            else:
                                try:
                                    st.session_state.evals_left = int(evals)
                                    st.session_state.max_evals = int(evals)
                                    st.session_state.quota_source = "paid"
                                except Exception:
                                    pass
                            st.session_state.current_tier = _pplan
                            st.sidebar.success(f"✅ Quota unlocked — {_putr}")
                            st.rerun()
                    if _rcol.button("❌ Reject", key=f"pay_verify_{_putr}_reject"):
                        if reject_payment(_putr, "Payment not found in bank records."):
                            st.sidebar.error(f"Rejected — {_putr}")
                            st.rerun()
                    if _fcol.button("⚠️ Flag Partial", key=f"pay_verify_{_putr}_flag"):
                        if flag_partial(_putr):
                            st.session_state.partial_utr = _putr
                            st.sidebar.warning("Flagged as partial — user will be prompted for top-up.")
                            st.rerun()

st.sidebar.divider()
st.sidebar.markdown(
    "**💬 Feedback & Suggestions**\n\n"
    "Found a bug? Want a new feature?\n\n"
    "📧 [ankitjsr12345@gmail.com](mailto:ankitjsr12345@gmail.com)  \n"
    "📧 [subhadeepbag571@gmail.com](mailto:subhadeepbag571@gmail.com)"
)

st.title("🕵️‍♂️ Detective AI")
st.markdown("Detective Agentic AI & RAG Profiling System : Automated criminal pattern recognition, risk evaluation, and precedent retrieval engine.")
st.divider()

if st.session_state.partial_utr:
    _prec = get_partial_by_utr(st.session_state.partial_utr)
    if _prec:
        _p_paid = _prec.get("amount_paid", 0)
        _p_req = _prec.get("required_amount", 0)
        _p_remain = _prec.get("remaining_balance", 0)
        _p_plan = _prec.get("plan", "")
        _p_utr = _prec.get("utr", "")
        st.warning(
            f"⚠️ **Payment Incomplete** — You paid ₹{_p_paid:,.0f} out of "
            f"₹{_p_req:,.0f} for the **{_p_plan}** plan. "
            f"Please pay the remaining balance of **₹{_p_remain:,.0f}** to unlock your evaluations."
        )
        _tp_qr_col, _tp_inst_col = st.columns([1, 2])
        with _tp_qr_col:
            try:
                _tp_qr = make_upi_qr(int(_p_remain), f"TopUp_{_p_plan.split()[-1]}")
                st.image(_tp_qr, caption=f"Scan to Pay ₹{_p_remain:,.0f} (balance)", width=200)
            except Exception:
                st.code(
             f"upi://pay?pa={UPI_VPA}&pn=Ankit%20SUBHADEEP"
             f"&am={int(_p_remain)}&cu=INR&tn=TopUp_Balance",
             language="text"
)
        with _tp_inst_col:
            st.markdown(
                f"**UPI ID:** `{UPI_VPA}`  \n"
                f"**Amount:** ₹{_p_remain:,.0f}  \n"
                f"**Payee:** ANKITKUMAR"
            )
            with st.form(key=f"topup_form_{_p_utr}"):
                _topup_utr = st.text_input("Enter Top-Up UTR / Transaction Ref", placeholder="New 12-digit UTR after paying balance", max_chars=30)
                _topup_sub = st.form_submit_button("📨 Submit Top-Up Proof", use_container_width=True, type="primary")
            if _topup_sub:
                if not _topup_utr.strip():
                    st.error("Please enter your top-up UTR.")
                else:
                    _ts, _tm, _tr = submit_topup(
                        _topup_utr.strip(), _p_utr, float(_p_remain)
                    )
                    if "✅" in _tm:
                        st.success(_tm)
                        st.session_state.partial_utr = None
                        st.rerun()
                    else:
                        st.error(_tm)
        st.divider()
    else:
        st.session_state.partial_utr = None

_tab_labels = ["📊 Executive Analytics", "🔍 Profiling Analysis", "📁 Case Management", "👤 Suspects", "🔬 Evidence", "⏱️ Case Timeline", "⚠️ Anomaly Analysis", "🕸️ Relationship Graph", "💳 Billing & Plans", "📬 Contact & Feedback"]
if st.session_state.is_admin:
    _tab_labels.append("🛡️ Audit Trail")
    _tab_labels.append("📢 B2B Agency Acquisition")
_tabs = st.tabs(_tab_labels)
tab_dashboard = _tabs[0]
tab_profile = _tabs[1]
tab_cases = _tabs[2]
tab_suspects = _tabs[3]
tab_evidence = _tabs[4]
tab_timeline = _tabs[5]
tab_anomalies = _tabs[6]
tab_graph = _tabs[7]
tab_billing = _tabs[8]
tab_contact = _tabs[9]
tab_audit = _tabs[10] if st.session_state.is_admin else None
tab_outreach = _tabs[11] if st.session_state.is_admin else None

with tab_dashboard:
    render_analytics_dashboard()

with tab_profile:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("Suspect Information & Observations")

        # Quick Presets for Real Indian Landmark Precedents
        st.markdown("**⚡ Quick Precedent Test Scenarios (1-Click Fill):**")
        p_c1, p_c2, p_c3 = st.columns(3)
        if p_c1.button("💊 Cyanide Mohan", use_container_width=True, key="quick_preset_cyanide"):
            st.session_state["suspect_name_input"] = "Mohan K. @ Cyanide Mohan"
            st.session_state["age_input"] = "45"
            st.session_state["behaviors_input"] = "Befriends women under false pretext of marriage proposal. Takes victims to lodge rooms distant from their home. Convinces victims to consume cyanide disguised as contraceptive medicine near bus stations or hotel washrooms. Takes deceased's jewelry and cash before departing scene."
            st.rerun()
        if p_c2.button("🐍 Uthra Snakebite", use_container_width=True, key="quick_preset_snakebite"):
            st.session_state["suspect_name_input"] = "Sooraj S. Kumar"
            st.session_state["age_input"] = "28"
            st.session_state["behaviors_input"] = "Procuring venomous viper and cobra snakes from snake handlers. Releasing lethal serpent into bedroom while victim is sedated or sleeping to stage accidental snakebite, targeting insurance payout and gold jewelry."
            st.rerun()
        if p_c3.button("🧪 Preeti Rathi Acid", use_container_width=True, key="quick_preset_acid"):
            st.session_state["suspect_name_input"] = "Ankur Panwar"
            st.session_state["age_input"] = "25"
            st.session_state["behaviors_input"] = "Stalking female victim after marriage proposal rejected. Followed victim across state transit lines to railway station platform. Threw concentrated sulfuric acid from can, causing fatal chemical burn injuries."
            st.rerun()

        p_c4, p_c5, p_c6 = st.columns(3)
        if p_c4.button("🔨 Raman Raghav", use_container_width=True, key="quick_preset_raman"):
            st.session_state["suspect_name_input"] = "Raman Raghav"
            st.session_state["age_input"] = "40"
            st.session_state["behaviors_input"] = "Attacking homeless and impoverished pavement dwellers sleeping along railway tracks and suburban shanties during midnight hours using a blunt iron rod, stealing trivial food items and small change."
            st.rerun()
        if p_c5.button("🚌 Nirbhaya Assault", use_container_width=True, key="quick_preset_nirbhaya"):
            st.session_state["suspect_name_input"] = "Mukesh Singh & Co."
            st.session_state["age_input"] = "32"
            st.session_state["behaviors_input"] = "Operating chartered private bus after hours. Luring passengers under pretext of transit route. Systematic violent assault and grievous hurt using rusted iron rod, destroying evidence and dumping victim on airport road."
            st.rerun()
        if p_c6.button("🪚 Chandrakant Jha", use_container_width=True, key="quick_preset_chandrakant"):
            st.session_state["suspect_name_input"] = "Chandrakant Jha"
            st.session_state["age_input"] = "39"
            st.session_state["behaviors_input"] = "Befriending migrant laborers, binding and strangling victims, followed by methodical decapitation and anatomical dismemberment. Dumping severed torso in plastic sacks outside central prison gates with taunting handwritten notes."
            st.rerun()

        with st.form(key="suspect_profiling_form"):
            suspect_name = st.text_input("Suspect Name / Alias", value=st.session_state.get("suspect_name_input", ""), placeholder="e.g. John Doe / Suspect Alpha")
            age = st.text_input("Age", value=st.session_state.get("age_input", ""), placeholder="e.g. 34")
            behaviors = st.text_area("Observed Behaviors, MO, & Traits", value=st.session_state.get("behaviors_input", ""), height=180,
                                     placeholder="Entering residential premises during late hours, targeting locked cabinets...")
            submit_btn = st.form_submit_button("Run Intelligence Analysis", type="primary", use_container_width=True)
    with col2:
        st.subheader("Analysis & Precedent Results")
        if submit_btn:
            if not behaviors.strip():
                st.warning("Please enter observed behaviors to analyze.")
            elif st.session_state.max_evals != "Unlimited" and st.session_state.evals_left <= 0:
                st.error("🚫 Evaluation Quota Exceeded! Please upgrade via the Billing tab.")
            else:
                with st.spinner("Analyzing traits against ChromaDB precedent vectors..."):
                    try:
                        name_str = suspect_name.strip() if suspect_name.strip() else "Unnamed Suspect"
                        res = agent.evaluate_suspect(
                            name=name_str, behavior=behaviors,
                            mo_suspected=behaviors, personality_notes=behaviors
                        )
                        if st.session_state.max_evals != "Unlimited":
                            if st.session_state.quota_source == "trial":
                                st.session_state.evals_left = _consume_trial(TRIAL_USER_ID)
                            else:
                                st.session_state.evals_left = max(
                                    0, st.session_state.evals_left - 1
                                )
                        matched_cases = res.get("similar_cases", [])
                        risk_lbl = res.get("risk_level", "UNKNOWN")
                        # Cap analysis_history at 50 entries to avoid unbounded growth
                        if len(st.session_state.analysis_history) >= 50:
                            st.session_state.analysis_history = st.session_state.analysis_history[-49:]
                        st.session_state.latest_results = {
                            "name": res.get("suspect_name", name_str),
                            "age": age,
                            "behaviors": behaviors,
                            "tendency_score": res.get("tendency_score", "0%"),
                            "risk_level": risk_lbl,
                            "risk_explanation": res.get("risk_explanation", ""),
                            "match_quality": res.get("match_quality", ""),
                            "matched_cases": matched_cases,
                            "summary_text": res.get("summary", f"Suspect pattern evaluated for behavior traits: {behaviors[:60]}..."),
                            "scoring_breakdown": res.get("scoring_breakdown", []),
                            "disclaimer": res.get("disclaimer", ""),
                            "timestamp": time.time(),
                        }
                        st.session_state.analysis_history.append(st.session_state.latest_results.copy())
                        try:
                            from agent.suspect_engine import SuspectEngine
                            _s_eng = SuspectEngine()
                            _matches = _s_eng.list_suspects(search=name_str)
                            _t_susp = next((_s for _s in _matches if _s.name.lower() == name_str.lower()), None)
                            if not _t_susp:
                                _, _, _t_susp = _s_eng.register_suspect(
                                    name=name_str,
                                    age=age.strip() if age and age.strip() else None,
                                    observed_behaviors=behaviors.strip() if behaviors else None,
                                )
                            if _t_susp:
                                _s_eng.record_assessment(_t_susp.suspect_id, res)
                        except Exception:
                            pass
                    except Exception as err:
                        st.error(f"Analysis error. Please try again. (Details: {err})")

        if st.session_state.latest_results:
            res = st.session_state.latest_results
            st.markdown(f"### Profile: **{res['name']}**")
            m_col1, m_col2, m_col3 = st.columns(3)
            m_col1.metric("Risk Indicator Score", str(res["tendency_score"]))
            m_col2.metric("Risk Category", res["risk_level"])
            m_col3.metric("Match Quality", res.get("match_quality", "—"))
            st.info(f"**Model Assessment:** {res['summary_text']}")

            # Scoring breakdown (explainable)
            if res.get("scoring_breakdown"):
                with st.expander("📊 Scoring Breakdown (how the score was calculated)"):
                    for item in res["scoring_breakdown"]:
                        st.markdown(
                            f"**{item['factor']}** — contribution: `{item['contribution']}` pt(s)  \n"
                            f"{item['explanation']}"
                        )

            # Disclaimer
            if res.get("disclaimer"):
                st.warning(res["disclaimer"])

            st.markdown("#### ⚖️ Retrieved Indian Legal Case Precedents")
            st.caption("SOURCE TYPE: VERIFIED INDIAN LEGAL RECORDS — Retrieved via ChromaDB/Vector Similarity. Never present as proof of guilt.")
            if res["matched_cases"]:
                top_case = res["matched_cases"][0]
                top_sim_pct = f"{float(top_case.get('similarity', 0.0)):.0%}"
                top_court = top_case.get("court_or_authority") or top_case.get("metadata", {}).get("court_or_authority", "Supreme Court / High Court")
                top_cite = top_case.get("legal_citation") or top_case.get("metadata", {}).get("legal_citation", "Public Legal Record")
                top_source = top_case.get("source") or top_case.get("metadata", {}).get("source", "Indian Kanoon / Judicial Records")
                top_url = top_case.get("source_url") or top_case.get("metadata", {}).get("source_url", "")
                top_ipc = top_case.get("ipc_sections") or top_case.get("metadata", {}).get("ipc_sections", [])
                top_ipc_str = ", ".join(top_ipc) if isinstance(top_ipc, list) else str(top_ipc)

                st.success(
                    f"🎯 **TOP MATCHED INDIAN PRECEDENT ({top_sim_pct} ALIGNMENT):**  \n"
                    f"**{top_case.get('case_title', 'Landmark Precedent')}** [`{top_case.get('case_id')}`]  \n"
                    f"🏛️ **Authority:** {top_court} | 📖 **Citation:** {top_cite}  \n"
                    f"⚖️ **Statutory Sections:** {top_ipc_str or 'Indian Penal Code'}"
                )
                if top_url:
                    st.markdown(f"🔗 **Primary Source Verification:** [{top_source}]({top_url})")

                for idx, case in enumerate(res["matched_cases"]):
                    sim_pct = f"{float(case.get('similarity', 0.0)):.0%}"
                    result_type = case.get("result_type", "RETRIEVED EVIDENCE")
                    court = case.get("court_or_authority") or case.get("metadata", {}).get("court_or_authority", "Supreme Court / High Court")
                    cite = case.get("legal_citation") or case.get("metadata", {}).get("legal_citation", "Public Legal Record")
                    source_desc = case.get("source") or case.get("metadata", {}).get("source", "Indian Kanoon / Judicial Records")
                    source_url = case.get("source_url") or case.get("metadata", {}).get("source_url", "")
                    ipc_secs = case.get("ipc_sections") or case.get("metadata", {}).get("ipc_sections", [])
                    ipc_str = ", ".join(ipc_secs) if isinstance(ipc_secs, list) else str(ipc_secs)

                    with st.expander(
                        f"📌 #{idx+1} [{result_type}] {case.get('case_title','Historical Precedent')} "
                        f"({case.get('location','India')}) — Similarity: {sim_pct}",
                        expanded=(idx == 0)
                    ):
                        st.info(
                            f"**EXPLAINABLE CORRELATION PIPELINE:**  \n"
                            f"**SOURCE DATA:** {court} [{cite}]  \n"
                            f"**→ MATCHED PATTERN:** {case.get('crime_type', 'Offence')} ({case.get('location', 'India')})  \n"
                            f"**→ SIMILARITY:** `{sim_pct}`  \n"
                            f"**→ AI ANALYSIS:** Statistical behavioral pattern match under {ipc_str or 'Indian Penal Code'}. Non-legal finding."
                        )
                        c_m1, c_m2 = st.columns(2)
                        with c_m1:
                            st.write(f"**Case Reference ID:** `{case.get('case_id','N/A')}`")
                            st.write(f"**Judicial Court / Authority:** {court}")
                            st.write(f"**Legal Citation:** {cite}")
                        with c_m2:
                            st.write(f"**IPC / Statutory Sections:** {ipc_str or 'General Criminal Law'}")
                            if source_url:
                                st.write(f"**Official Legal Source:** [{source_desc}]({source_url})")
                            else:
                                st.write(f"**Official Legal Source:** {source_desc}")

                        # Show summary (factual case record) separately from snippet (extracted text)
                        if case.get("summary"):
                            st.write(f"**Case Summary (FACT — Judicial Record):** {case['summary']}")
                        if case.get("snippet"):
                            st.write(f"**Extracted Context (RETRIEVED):** {case['snippet'][:350]}...")
                        st.caption(
                            f"Cosine similarity: {sim_pct} | Distance: {case.get('distance', 'N/A')}"
                        )
            else:
                st.info("ℹ️ No sufficiently similar Indian record found in the precedent index.")
            try:
                pdf_bytes = generate_pdf_report(
                    res["name"], res["age"], res["tendency_score"],
                    res["risk_level"], res["behaviors"], res["matched_cases"],
                    scoring_breakdown=res.get("scoring_breakdown", []),
                    disclaimer=res.get("disclaimer", ""),
                    match_quality=res.get("match_quality", ""),
                )
                # Use microseconds to guarantee a unique key even within the same second
                dynamic_key = f"dl_pdf_{int(res.get('timestamp', time.time()) * 1e6)}"
                st.download_button(
                    label="📥 Download Executive PDF Report", data=pdf_bytes,
                    file_name=f"Profile_Report_{res['name'].replace(' ', '_')}.pdf",
                    mime="application/pdf", use_container_width=True, key=dynamic_key
                )
            except Exception as pdf_err:
                st.warning(f"PDF generation failed: {pdf_err}")

with tab_cases:
    render_case_management()

with tab_suspects:
    render_suspect_management()

with tab_evidence:
    render_evidence_management()

with tab_timeline:
    render_timeline_management()

with tab_anomalies:
    render_anomaly_dashboard()

with tab_graph:
    render_relationship_graph()

with tab_billing:
    PLANS = {
        "🥉 Starter Agency": {"amount": 500, "evals": 100, "label": "₹500 / mo — 100 Evaluations"},
        "🥈 Pro Agency": {"amount": 1000, "evals": 500, "label": "₹1,000 / mo — 500 Evaluations"},
        "🥇 Enterprise SaaS": {"amount": 2000, "evals": "Unlimited", "label": "₹2,000 / mo — Unlimited Evaluations"},
    }
    st.subheader("Select Your Subscription Plan")
    st.caption("Quota is unlocked by the admin after UPI payment is verified.")
    p_col1, p_col2, p_col3 = st.columns(3)
    for col, (plan_name, plan_info) in zip([p_col1, p_col2, p_col3], PLANS.items()):
        with col:
            st.markdown(f"### {plan_name}")
            st.markdown(f"**{plan_info['label']}**")
            if plan_name == "🥉 Starter Agency":
                st.markdown("* 100 Evaluations / mo\n* Standard RAG Precedent Search\n* Basic PDF Export")
            elif plan_name == "🥈 Pro Agency":
                st.markdown("* 500 Evaluations / mo\n* Fast ChromaDB Vector Search\n* Custom JSON File Indexer")
            else:
                st.markdown("* Unlimited Evaluations\n* Private Vector Database\n* Dedicated API & Priority Support")
            btn_key = f"plan_select_{plan_name.replace(' ','_').replace('/','_').replace('🥉','').replace('🥈','').replace('🥇','')}"
            if st.button(f"Select {plan_name}", key=btn_key, use_container_width=True):
                st.session_state.pending_plan = plan_name
                st.session_state.pending_amount = plan_info["amount"]
                st.session_state.pending_evals = plan_info["evals"]
                st.rerun()

    if st.session_state.pending_plan:
        st.divider()
        plan = st.session_state.pending_plan
        amount = st.session_state.pending_amount
        evals = st.session_state.pending_evals
        st.subheader(f"💳 Complete Payment for {plan}")
        qr_col, inst_col = st.columns([1, 2])
        with qr_col:
            try:
                qr_bytes = make_upi_qr(amount, f"Detective_AI_{plan.split()[-1]}")
                st.image(qr_bytes, caption=f"Scan to Pay ₹{amount:,}", width=220)
            except Exception as e:
                st.warning(f"QR could not be generated: {e}")
                st.code(
                    f"upi://pay?pa={UPI_VPA}&pn={UPI_NAME.replace(' ', '%20')}"
                    f"&am={amount}&cu=INR&tn=Detective_AI_{plan.split()[-1]}",
                    language="text"
                )
        with inst_col:
            st.markdown(f"""
**Amount Payable:** ₹{amount:,}
**UPI ID:** `{UPI_VPA}`
**Payee Name:** {UPI_NAME}

**Steps:**
1. Open PhonePe / Google Pay / Paytm
2. Scan the QR code or pay to UPI ID above
3. Note the **12-digit UTR / Transaction Reference** shown in your payment app
4. Enter it below and click **Submit Proof**
            """)
            with st.form(key=f"utr_form_{plan.replace(' ','_').replace('/','_')}"):
                utr_input = st.text_input("Enter UTR / Transaction Reference ID", placeholder="e.g. 426789012345", max_chars=30)
                paid_input = st.text_input("Amount You Paid (₹)", placeholder=f"e.g. {amount}", max_chars=10)
                submit_utr = st.form_submit_button("📨 Submit Payment Proof", use_container_width=True)
            if submit_utr:
                if not utr_input.strip():
                    st.error("Please enter your UTR / Transaction Reference.")
                elif not paid_input.strip():
                    st.error("Please enter the amount you paid.")
                else:
                    try:
                        paid_val = float(paid_input.replace(",", "").strip())
                    except ValueError:
                        st.error("Invalid amount — enter a number.")
                        paid_val = None
                    if paid_val is not None:
                        _s, _m, _r = submit_payment(
                            plan=plan, required_amount=float(amount),
                            amount_paid=paid_val, evals=evals, utr=utr_input.strip()
                        )
                        if _s in (STATUS_FLAGGED, STATUS_INVALID_UTR):
                            st.error(_m)
                        elif _s == STATUS_PARTIAL:
                            st.warning(_m)
                            st.session_state.partial_utr = utr_input.strip()
                            st.session_state.pending_plan = None
                            st.session_state.pending_amount = None
                            st.session_state.pending_evals = None
                            st.rerun()
                        else:
                            st.success("✅ Payment proof submitted! Your quota will be unlocked after admin verification.")
                            st.session_state.pending_plan = None
                            st.session_state.pending_amount = None
                            st.session_state.pending_evals = None
                            st.rerun()

with tab_contact:
    st.subheader("📬 Contact, Feedback & Feature Requests")
    st.markdown("Have a question, found a bug, or want to suggest a new feature? Reach out directly — every message is read personally.")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 📧 Founders — Direct Contact")
        st.markdown("**Ankit kumar** \n[Founder]  \n📩 [ankitjsr12345@gmail.com](mailto:ankitjsr12345@gmail.com)")
        st.markdown("**Subhadeep bag** \n[Partner]  \n📩 [subhadeepbag571@gmail.com](mailto:subhadeepbag571@gmail.com)")
        st.markdown("---")
        st.markdown("### 🐛 Bug Reports")
        st.markdown("Please include:  \n- What you were doing  \n- What error / unexpected behaviour appeared  \n- Screenshot if possible  \n\nSend to **[ankitjsr12345@gmail.com](mailto:ankitjsr12345@gmail.com)** or **[subhadeepbag571@gmail.com](mailto:subhadeepbag571@gmail.com)** with subject line: `[BUG] Detective AI — <short description>`")
    with c2:
        st.markdown("### 💡 Suggest a Feature")
        st.markdown("Ideas for new capabilities are welcome:  \n- New case-matching algorithms  \n- Additional report formats  \n- Integrations (WhatsApp alerts, CRM sync, etc.)  \n\nSend to **[ankitjsr12345@gmail.com](mailto:ankitjsr12345@gmail.com)** or **[subhadeepbag571@gmail.com](mailto:subhadeepbag571@gmail.com)** with subject line: `[FEATURE REQUEST] <your idea>`")
        st.markdown("---")
        st.markdown("### 🔒 Privacy & Data")
        st.markdown("All suspect profiling data is processed locally in your session.  \nNo case data is stored on our servers without your explicit upload.  \nPayments are verified manually — we never store card details.")
    st.divider()
    st.info(
        "⏱️ **Response time:** Typically within 24 hours on weekdays.  \n"
        #f"🌐 **Platform:** {PLATFORM_URL}"
    )

if st.session_state.is_admin:
    if tab_audit:
        with tab_audit:
            render_audit_trail_view()

    with tab_outreach:
        st.subheader("📢 B2B Lead Scraper & Cold Email Outreach")
        st.caption("Scrape target agency/detective contact information, select specific prospects, preview emails, and dispatch only after approval.")

        col_kw, col_loc = st.columns(2)
        with col_kw:
            target_keyword = st.text_input("Target Keyword / Niche", value="Detective Agency", key="outreach_kw")
        with col_loc:
            target_location = st.text_input("Location", value="Delhi", key="outreach_loc")

        # Option to allow generated placeholder leads (disabled by default)
        allow_generated = st.checkbox("Allow generated placeholder leads when public data is sparse (verify manually)", value=False, key="chk_allow_generated")
        # Minimum confidence filter for displayed leads (0-100). Default 60 hides low-confidence/generated leads.
        min_conf = st.slider("Minimum confidence to display leads", 0, 100, 60, key="lead_min_confidence")
        if st.button("🔎 Scrape Leads", type="primary", use_container_width=True, key="btn_scrape_leads"):
            with st.spinner("Scraping leads across web sources..."):
                try:
                    scraped_data = scrape_leads_sync(target_keyword, target_location, max_results=20, allow_generated=allow_generated)
                    if scraped_data:
                        # Show scraped results (restore original behaviour: display all scraped leads)
                        displayed = scraped_data
                        try:
                            # still compute confidence column for info if present
                            scraped_df = pd.DataFrame(scraped_data)
                            scraped_df['confidence'] = scraped_df.get('confidence', 50).fillna(50)
                        except Exception:
                            pass

                        st.success(f"Successfully scraped {len(scraped_data)} leads!")
                        st.dataframe(pd.DataFrame(displayed), use_container_width=True)
                    else:
                        st.info("No leads found matching your criteria.")
                except Exception as e:
                    st.error(f"Scraping failed: {e}")

        st.divider()
        st.markdown("### 📧 Email Dispatcher")
        saved_leads = load_leads()


        if saved_leads:
            # Apply confidence filter to saved_leads for display/selection (non-destructive)
            min_conf_local = st.session_state.get("lead_min_confidence", 60)
            saved_leads_display = []
            for lead in saved_leads:
                if not isinstance(lead, dict):
                    continue
                try:
                    conf = int(lead.get('confidence', 50))
                except Exception:
                    conf = 50
                verified = str(lead.get('verification_status', '')).strip().lower() == 'verified'
                if conf >= int(min_conf_local) or verified:
                    saved_leads_display.append(lead)

            filtered_out = len(saved_leads) - len(saved_leads_display)
            if filtered_out > 0:
                st.info(f"{filtered_out} leads hidden by confidence filter (min {min_conf_local}). Uncheck the filter to view all.")

            email_ready_count = sum(
                1 for lead in saved_leads_display
                if isinstance(lead, dict) and re.fullmatch(
                    r"[^\s@]+@[^\s@]+\.[^\s@]+",
                    str(
                        lead.get("contact_email")
                        or lead.get("email")
                        or lead.get("email_address")
                        or ""
                    ).strip(),
                )
            )
            st.write(
                f"Loaded **{len(saved_leads)}** prospects — **{len(saved_leads_display)}** shown (min confidence {min_conf_local}) — "
                f"**{email_ready_count}** have a valid email address."
            )
            if email_ready_count == 0:
                st.warning(
                    "No verified email addresses are available yet. "
                    "Prospects without a published email are kept for manual "
                    "enrichment and will not be emailed."
                )

            def _lead_label(lead, index):
                if not isinstance(lead, dict):
                    return f"Prospect {index + 1}"
                name = (
                    lead.get("agency_name") or lead.get("company_name") or
                    lead.get("company") or lead.get("business_name") or
                    lead.get("name") or lead.get("title") or f"Prospect {index + 1}"
                )
                email = lead.get("email") or lead.get("email_address") or lead.get("contact_email") or ""
                name, email = str(name).strip(), str(email).strip()
                return f"{name} — {email}" if email else name

            lead_labels = [_lead_label(lead, index) for index, lead in enumerate(saved_leads_display)]

            st.markdown("#### 🎯 Choose Recipients")
            st.caption("Use a command such as `send to Delhi Inquiry Bureau`, `send to ABC and XYZ`, or `send to all`.")

            selection_command = st.text_input(
                "Recipient Selection Command",
                placeholder="e.g. send to Delhi Inquiry Bureau and ABC Agency",
                key="outreach_selection_command"
            )

            command_matches, command_not_found = [], []
            if selection_command.strip():
                command_lower = selection_command.lower().strip()
                if command_lower in {"all", "send all", "send to all", "email all", "email everyone", "send to everyone"}:
                    command_matches = list(lead_labels)
                else:
                    cleaned = re.sub(r"^(please\s+)?(send|email|mail)(\s+to)?\s*", "", command_lower, flags=re.I)
                    cleaned = re.sub(r"^(agencies|leads|recipients)\s*[:=-]?\s*", "", cleaned, flags=re.I)
                    requested_names = [p.strip() for p in re.split(r"\s*,\s*|\s+and\s+", cleaned) if p.strip()]
                    normalized_labels = [re.sub(r"[^a-z0-9@.]+", " ", label.lower()).strip() for label in lead_labels]
                    for requested in requested_names:
                        req = re.sub(r"[^a-z0-9@.]+", " ", requested.lower()).strip()
                        found = False
                        for label, norm in zip(lead_labels, normalized_labels):
                            if req in norm or norm in req:
                                if label not in command_matches:
                                    command_matches.append(label)
                                found = True
                        if not found:
                            command_not_found.append(requested)

            if command_matches:
                st.success(f"Command matched **{len(command_matches)}** recipient(s).")
            if command_not_found:
                st.warning("No matching recipient found for: " + ", ".join(command_not_found))

            if selection_command.strip():
                last_command = st.session_state.get("_outreach_last_selection_command")
                if last_command != selection_command:
                    st.session_state["outreach_selected_labels"] = list(command_matches)
                    st.session_state["_outreach_last_selection_command"] = selection_command

            selected_labels = st.multiselect(
                "Select recipients to email",
                options=lead_labels,
                key="outreach_selected_labels"
            )
            selected_indices = [i for i, label in enumerate(lead_labels) if label in selected_labels]
            selected_leads = [saved_leads_display[i] for i in selected_indices]
            st.info(f"Selected **{len(selected_leads)}** of **{len(saved_leads_display)}** prospects.")

            st.markdown("#### 🔐 Gmail Authentication")
            st.caption(
                "Enter the Gmail App Password for the sending account. "
                "It is used only for this session and is not saved to your project files."
            )
            gmail_session_password = st.text_input(
                "Gmail App Password",
                type="password",
                placeholder="Enter your 16-character Google App Password",
                key="b2b_gmail_session_password",
            )

            st.markdown("#### 👁️ Email Preview")

            def _render_email(template, lead):
                if not isinstance(lead, dict):
                    return str(template)
                recipient_name = (
                    lead.get("agency_name") or lead.get("company_name") or
                    lead.get("company") or lead.get("business_name") or
                    lead.get("name") or "Agency"
                )
                recipient_email = lead.get("email") or lead.get("email_address") or lead.get("contact_email") or ""
                rendered = str(template)
                replacements = {
                    "{agency_name}": str(recipient_name),
                    "{company_name}": str(recipient_name),
                    "{company}": str(recipient_name),
                    "{business_name}": str(recipient_name),
                    "{recipient}": str(recipient_name),
                    "{name}": str(recipient_name),
                    "{email}": str(recipient_email),
                    "{location}": str(lead.get("location", "")),
                }
                for placeholder, value in replacements.items():
                    rendered = rendered.replace(placeholder, value)

                # Only preview-link fix: ensure the live platform URL is used.
                rendered = rendered.replace(
                    "https://detective-ai.streamlit.app",
                    PLATFORM_URL.rstrip("/")
                )
                return rendered

            if selected_leads:
                preview_options = [_lead_label(lead, i) for i, lead in enumerate(selected_leads)]
                preview_label = st.selectbox("Preview email for", options=preview_options, key="outreach_preview_agency_label")
                preview_index = preview_options.index(preview_label)
                preview_lead = selected_leads[preview_index]
                preview_email = preview_lead.get("email") or preview_lead.get("email_address") or preview_lead.get("contact_email") or ""
                st.text_input("To", value=str(preview_email), disabled=True, key="outreach_preview_to")
                st.text_input("Agency / Recipient", value=preview_label, disabled=True, key="outreach_preview_agency")
                st.text_input("Subject", value=_render_email(COLD_EMAIL_SUBJECT, preview_lead), disabled=True, key="outreach_preview_subject")
                st.text_area("Email Body", value=_render_email(COLD_EMAIL_BODY, preview_lead), height=300, disabled=True, key="outreach_preview_body")
                st.caption("Nothing is sent until you click the dispatch button below.")

            st.divider()
            if selected_leads:
                if st.button(f"🚀 Dispatch Cold Emails to {len(selected_leads)} Selected Recipients", use_container_width=True, key="btn_dispatch_selected_emails"):
                    app_password = str(gmail_session_password or "").strip()
                    if not app_password:
                        st.error("Enter the Gmail App Password above, then try again.")
                    else:
                        progress_box = st.empty()
                        with st.spinner(f"Sending emails to {len(selected_leads)} selected recipients..."):
                            try:
                                dispatch_result = send_cold_emails(
                                    selected_leads,
                                    app_password,
                                    COLD_EMAIL_SUBJECT,
                                    COLD_EMAIL_BODY,
                                    delay_seconds=5,
                                    progress_callback=lambda i, total, agency, status, error="": progress_box.info(
                                        f"Sending {i}/{total}: {agency} — {status}"
                                        + (f" — {error}" if error else "")
                                    ),
                                )
                                successful = [x for x in dispatch_result if str(x.get("status", "")).upper() in {"SENT", "SUCCESS", "SUCCESSFUL"}]
                                failed = [x for x in dispatch_result if str(x.get("status", "")).upper() not in {"SENT", "SUCCESS", "SUCCESSFUL"}]
                                if successful:
                                    st.success(f"Successfully sent **{len(successful)}** email(s).")
                                if failed:
                                    st.warning(f"**{len(failed)}** email(s) were not sent.")
                                    for item in failed:
                                        st.error(f"{item.get('agency_name', item.get('recipient', 'Unknown'))}: {item.get('error', 'Unknown error')}")
                                if not successful and not failed:
                                    st.info("No emails were dispatched.")

                                # Persist dispatch results so the admin can see
                                # which prospects have already been contacted.
                                result_by_email = {
                                    str(item.get("recipient", "")).strip().lower(): item
                                    for item in dispatch_result
                                    if item.get("recipient")
                                }
                                changed = False
                                for lead in saved_leads:
                                    if not isinstance(lead, dict):
                                        continue
                                    lead_email = str(
                                        lead.get("contact_email")
                                        or lead.get("email")
                                        or lead.get("email_address")
                                        or ""
                                    ).strip().lower()
                                    item = result_by_email.get(lead_email)
                                    if not item:
                                        continue

                                    new_status = str(item.get("status", "Prospect"))
                                    if lead.get("status") != new_status:
                                        lead["status"] = new_status
                                        changed = True

                                    if new_status == "SENT":
                                        lead["last_contacted_at"] = time.strftime(
                                            "%Y-%m-%d %H:%M:%S"
                                        )
                                        changed = True

                                if changed:
                                    save_leads(saved_leads)

                            except Exception as e:
                                st.error(f"Email dispatch failed: {e}")
            else:
                st.button("🚀 Dispatch Cold Emails", use_container_width=True, key="btn_dispatch_disabled", disabled=True)
        else:
            st.info("No saved leads available to email. Perform a lead scrape first.") 
