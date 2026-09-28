"""
tests/test_explainability_engine.py

Unit tests for agent/explainability_engine.py:
- Explainable AI assessment breakdown (Part 9)
- Language sanitization (preventing autonomous guilt declarations)
- Case summary synthesis (Part 11)
"""

import pytest
from agent.explainability_engine import ExplainabilityEngine
from database.models import Case


def test_sanitize_assessment_language():
    dangerous_text = "The subject is guilty and definitely dangerous, a convicted criminal."
    clean_text = ExplainabilityEngine.sanitize_assessment_language(dangerous_text)
    assert "guilty" not in clean_text.lower()
    assert "definitely dangerous" not in clean_text.lower()
    assert "criminal" not in clean_text.lower()
    assert "pattern match" in clean_text.lower()


def test_generate_explainable_assessment_structure():
    mock_precedents = [
        {
            "case_id": "PREC-01",
            "case_title": "Commercial Vault Break-in",
            "similarity": 0.72,
            "crime_type": "Burglary",
        }
    ]

    assessment = ExplainabilityEngine.generate_explainable_assessment(
        suspect_name="Test Subject",
        observed_behaviors="Disabling alarm circuits and prying back doors at night",
        modus_operandi="Lock-picking and bypass tools",
        retrieved_cases=mock_precedents,
    )

    required_keys = [
        "model_assessment_title",
        "subject_name",
        "similarity_score",
        "risk_indicator",
        "assessment",
        "confidence_indicator",
        "input_factors",
        "observed_indicators",
        "matched_historical_patterns",
        "scoring_breakdown",
        "limitations",
        "statutory_caveat",
    ]
    for k in required_keys:
        assert k in assessment, f"Missing required key: {k}"

    assert assessment["similarity_score"].endswith("%")
    assert assessment["risk_indicator"] == "HIGH RISK"
    assert "High Confidence" in assessment["confidence_indicator"]
    assert len(assessment["scoring_breakdown"]) >= 2
    assert len(assessment["limitations"]) >= 3


def test_generate_case_summary():
    test_case = Case(
        case_id="CASE-SUM-01",
        title="Art Gallery Theft",
        case_type="Larceny",
        description="Famous painting cut from frame during midnight power cut",
        location="National Gallery",
    )

    summary = ExplainabilityEngine.generate_case_summary(
        case=test_case,
        evidence_items=[],
        timeline_events=[],
        matched_precedents=[{"case_id": "P-1", "case_title": "Museum Theft", "similarity_pct": "68%"}],
    )

    required_sections = [
        "case_id",
        "case_title",
        "case_overview",
        "known_facts",
        "evidence_summary",
        "historical_similarities",
        "unresolved_questions",
        "information_gaps",
        "recommended_human_review_areas",
        "disclaimer",
    ]
    for s in required_sections:
        assert s in summary, f"Missing summary section: {s}"

    assert len(summary["known_facts"]) >= 2
    assert len(summary["unresolved_questions"]) >= 2
    assert "NOT contain autonomous legal conclusions" in summary["disclaimer"]
