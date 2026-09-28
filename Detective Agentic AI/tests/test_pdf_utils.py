"""
tests/test_pdf_utils.py

Tests for utils/pdf_utils.py:
- Multi-section dossier generation
- Unicode and special character handling
- Long text resilience (preventing horizontal space crashes)
- Backward-compatible wrapper
"""

import pytest
from utils.pdf_utils import (
    generate_investigation_dossier_pdf,
    generate_pdf_report,
    MANDATORY_DISCLAIMER,
)


def test_generate_investigation_dossier_pdf_basic():
    dossier_data = {
        "case_info": {
            "case_id": "CASE-101",
            "title": "Warehouse Theft Investigation",
            "case_type": "Grand Larceny",
            "location": "Sector 4, Industrial Zone",
            "priority": "HIGH",
            "status": "OPEN",
            "assigned_investigator": "Lead Det. Miller",
            "date_opened": "2026-04-12",
            "tags": ["larceny", "night", "commercial"],
        },
        "suspect_info": {
            "suspect_id": "SUSP-007",
            "name": "Alex Vance",
            "age": "32",
            "location": "Metro Area",
            "known_associations": "Known to frequent docks",
            "behaviors": "Repeated nocturnal surveillance of loading docks.",
            "modus_operandi": "Lock-picking and disabling circuit breakers.",
        },
        "model_assessment": {
            "tendency_score": "78%",
            "risk_level": "HIGH RISK",
            "match_quality": "Strong case-index similarity",
            "scoring_breakdown": [
                {"factor": "Base score", "contribution": 15, "explanation": "Baseline score"},
                {"factor": "Strongest case similarity", "contribution": 45, "explanation": "75% match with Case 003"},
            ],
            "similar_cases": [
                {
                    "case_id": "CASE-003",
                    "case_title": "Portside Cargo Burglary",
                    "similarity": 0.75,
                    "location": "Seaport",
                    "summary": "Targeted commercial warehouses during midnight shift.",
                }
            ],
        },
        "evidence": [
            {
                "evidence_id": "EV-001",
                "type": "CCTV Footage",
                "source": "Dock Gate 3",
                "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            }
        ],
        "timeline": [
            {"timestamp": "2026-04-12 02:15", "event_type": "Incident", "description": "Breaker alarm triggered"}
        ],
    }

    pdf_bytes = generate_investigation_dossier_pdf(dossier_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_pdf_unicode_and_long_text_resilience():
    long_desc = "Word " * 2000  # 10,000+ characters of text
    ultra_long_token = "https://investigation.gov/cases/evidence/archive/search?q=" + "x" * 200

    dossier_data = {
        "case_info": {
            "case_id": "UNICODE-999",
            "title": "₹500,000 Fraud — Em-dash & “Quotes” • Bullets",
        },
        "behaviors": long_desc,
        "investigator_notes": f"Reference link: {ultra_long_token}",
    }

    # Must complete without throwing an unhandled exception or crashing
    pdf_bytes = generate_investigation_dossier_pdf(dossier_data)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-")


def test_legacy_generate_pdf_report_wrapper():
    matched = [
        {"case_id": "C-1", "case_title": "Test Case", "similarity": 0.65, "location": "Delhi", "summary": "Test summary"}
    ]
    pdf_bytes = generate_pdf_report(
        suspect_name="John Doe",
        age="40",
        tendency_score="65%",
        risk_level="MEDIUM RISK",
        behaviors="Entering locked residential units at night",
        matched_cases=matched,
        scoring_breakdown=[{"factor": "Similarity", "contribution": 30, "explanation": "Moderate overlap"}],
    )
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_mandatory_disclaimer_content():
    assert "MODEL ASSESSMENTS" in MANDATORY_DISCLAIMER
    assert "NOT legal findings" in MANDATORY_DISCLAIMER
    assert "NOT proof of guilt" in MANDATORY_DISCLAIMER
