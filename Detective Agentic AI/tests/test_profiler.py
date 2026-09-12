"""
tests/test_profiler.py

Tests for agent/analyzer.py — scoring breakdown, risk levels,
explainability, and disclaimer.
"""
import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from agent.analyzer import DetectiveAgent


@pytest.fixture
def agent_with_cases(tmp_path):
    """Create a DetectiveAgent backed by a temporary cases directory with one test case."""
    case = {
        "case_id": "PROF-001",
        "title": "Night Burglary Case",
        "crime_type": "Burglary",
        "location": "Test City",
        "status": "Solved",
        "modus_operandi": "Breaking into residential houses at night, forcing locks.",
        "common_traits": ["night entry", "forced entry", "residential"],
        "summary": "Serial burglar targeted residential buildings during late-night hours.",
    }
    (tmp_path / "case_prof_001.json").write_text(json.dumps(case), encoding="utf-8")

    # Patch cases_dir for the retriever
    from rag.retriever import CaseRetriever
    agent = DetectiveAgent.__new__(DetectiveAgent)
    agent.retriever = CaseRetriever(cases_dir=str(tmp_path))
    return agent


class TestDetectiveAgentEvaluate:
    def test_returns_all_required_fields(self, agent_with_cases):
        result = agent_with_cases.evaluate_suspect(
            name="Test Suspect",
            behavior="Breaking into locked houses at night",
            mo_suspected="Forced entry residential buildings",
            personality_notes="",
        )
        required_fields = [
            "suspect_name", "tendency_score", "risk_level",
            "match_quality", "scoring_breakdown", "summary",
            "similar_cases", "disclaimer",
        ]
        for field in required_fields:
            assert field in result, f"Missing field: {field}"

    def test_tendency_score_format(self, agent_with_cases):
        result = agent_with_cases.evaluate_suspect(
            name="X", behavior="robbery theft assault", mo_suspected="", personality_notes="",
        )
        assert result["tendency_score"].endswith("%")
        score_int = int(result["tendency_score"].rstrip("%"))
        assert 0 <= score_int <= 100

    def test_risk_level_valid_categories(self, agent_with_cases):
        result = agent_with_cases.evaluate_suspect(
            name="X", behavior="robbery", mo_suspected="", personality_notes="",
        )
        assert result["risk_level"] in ("LOW RISK", "MEDIUM RISK", "HIGH RISK")

    def test_scoring_breakdown_is_list(self, agent_with_cases):
        result = agent_with_cases.evaluate_suspect(
            name="X", behavior="theft", mo_suspected="", personality_notes="",
        )
        assert isinstance(result["scoring_breakdown"], list)
        assert len(result["scoring_breakdown"]) >= 1

    def test_scoring_breakdown_has_required_keys(self, agent_with_cases):
        result = agent_with_cases.evaluate_suspect(
            name="X", behavior="breaking into houses at night", mo_suspected="", personality_notes="",
        )
        for item in result["scoring_breakdown"]:
            assert "factor" in item
            assert "contribution" in item
            assert "explanation" in item

    def test_disclaimer_present(self, agent_with_cases):
        result = agent_with_cases.evaluate_suspect(
            name="X", behavior="something", mo_suspected="", personality_notes="",
        )
        assert result["disclaimer"]
        # Must not claim certainty
        disclaimer_lower = result["disclaimer"].lower()
        assert "not" in disclaimer_lower or "model" in disclaimer_lower

    def test_no_match_with_unrelated_query(self, agent_with_cases):
        result = agent_with_cases.evaluate_suspect(
            name="X",
            behavior="loves gardening and cooking peaceful activities",
            mo_suspected="",
            personality_notes="",
        )
        # May or may not find a match, but should always return valid structure
        assert result["risk_level"] in ("LOW RISK", "MEDIUM RISK", "HIGH RISK")
        assert isinstance(result["similar_cases"], list)

    def test_severe_keywords_increase_score_when_no_rag_match(self, tmp_path):
        """When no case is indexed, keyword heuristic should raise score above baseline."""
        from rag.retriever import CaseRetriever
        from agent.analyzer import DetectiveAgent
        agent = DetectiveAgent.__new__(DetectiveAgent)
        agent.retriever = CaseRetriever(cases_dir=str(tmp_path))  # empty — no docs
        result = agent.evaluate_suspect(
            name="X", behavior="murder weapon robbery assault", mo_suspected="", personality_notes="",
        )
        score_int = int(result["tendency_score"].rstrip("%"))
        assert score_int > 15  # should be above baseline

    def test_baseline_score_when_no_indicators(self, tmp_path):
        """When nothing is found, score should be at baseline (15)."""
        from rag.retriever import CaseRetriever
        from agent.analyzer import DetectiveAgent
        agent = DetectiveAgent.__new__(DetectiveAgent)
        agent.retriever = CaseRetriever(cases_dir=str(tmp_path))
        result = agent.evaluate_suspect(
            name="X", behavior="friendly helpful calm", mo_suspected="", personality_notes="",
        )
        score_int = int(result["tendency_score"].rstrip("%"))
        assert score_int == 15
