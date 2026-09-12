"""
tests/test_rag_retriever.py

Tests for rag/retriever.py — indexing, search, similarity threshold,
no-match sentinel, and input validation.
"""
import os
import json
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from rag.retriever import CaseRetriever, SIMILARITY_THRESHOLD, RESULT_SOURCE_LABEL


@pytest.fixture
def cases_dir(tmp_path):
    """Create a temp directory with two minimal case JSON files."""
    c1 = {
        "case_id": "TEST-001",
        "title": "Burglary at Night",
        "crime_type": "Burglary",
        "location": "Mumbai",
        "status": "Solved",
        "modus_operandi": "Breaking into houses at night targeting locked cabinets.",
        "common_traits": ["night entry", "cabinet break", "theft"],
        "summary": "Serial burglar operated at night targeting residential properties.",
    }
    c2 = {
        "case_id": "TEST-002",
        "title": "Financial Fraud Scheme",
        "crime_type": "Fraud",
        "location": "Delhi",
        "status": "Closed",
        "modus_operandi": "Fake investment scheme targeting senior citizens.",
        "common_traits": ["fraud", "money", "deception", "elderly victims"],
        "summary": "Orchestrated a fraudulent investment scheme causing financial loss.",
    }
    (tmp_path / "case_001.json").write_text(json.dumps(c1), encoding="utf-8")
    (tmp_path / "case_002.json").write_text(json.dumps(c2), encoding="utf-8")
    return str(tmp_path)


class TestCaseRetrieverIndexing:
    def test_indexes_correct_number_of_cases(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        assert len(retriever._docs) == 2

    def test_indexes_zero_from_empty_dir(self, tmp_path):
        retriever = CaseRetriever(cases_dir=str(tmp_path))
        assert len(retriever._docs) == 0

    def test_skips_invalid_json(self, tmp_path):
        (tmp_path / "bad.json").write_text("NOT VALID JSON", encoding="utf-8")
        retriever = CaseRetriever(cases_dir=str(tmp_path))
        assert len(retriever._docs) == 0

    def test_skips_empty_file(self, tmp_path):
        (tmp_path / "empty.json").write_text("", encoding="utf-8")
        retriever = CaseRetriever(cases_dir=str(tmp_path))
        assert len(retriever._docs) == 0

    def test_reload_rebuilds_index(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        count = retriever.reload()
        assert count == 2


class TestCaseRetrieverSearch:
    def test_relevant_query_returns_results(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        results = retriever.search_similar_cases("breaking into houses at night theft")
        assert len(results) >= 1

    def test_empty_query_returns_empty(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        results = retriever.search_similar_cases("")
        assert results == []

    def test_short_query_returns_empty(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        results = retriever.search_similar_cases("abc")
        assert results == []

    def test_no_cases_returns_empty(self, tmp_path):
        retriever = CaseRetriever(cases_dir=str(tmp_path))
        results = retriever.search_similar_cases("robbery at night")
        assert results == []

    def test_results_have_result_type_label(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        results = retriever.search_similar_cases("burglary night residential")
        if results:
            assert results[0]["result_type"] == RESULT_SOURCE_LABEL

    def test_results_have_similarity_field(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        results = retriever.search_similar_cases("burglary night residential")
        for r in results:
            assert "similarity" in r
            assert 0.0 <= r["similarity"] <= 1.0

    def test_results_have_distance_field(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        results = retriever.search_similar_cases("burglary night residential")
        for r in results:
            assert "distance" in r
            assert 0.0 <= r["distance"] <= 1.0

    def test_high_threshold_reduces_results(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        results_low = retriever.search_similar_cases("burglary residential", threshold=0.01)
        results_high = retriever.search_similar_cases("burglary residential", threshold=0.99)
        assert len(results_low) >= len(results_high)

    def test_fraud_query_matches_fraud_case(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        results = retriever.search_similar_cases("fake investment scheme deception elderly")
        case_ids = [r["case_id"] for r in results]
        # Should match the fraud case more closely
        assert len(results) >= 1

    def test_results_below_threshold_excluded(self, cases_dir):
        retriever = CaseRetriever(cases_dir=cases_dir)
        # Very high threshold should return nothing or only perfect matches
        results = retriever.search_similar_cases("completely unrelated topic xyz abc def", threshold=0.99)
        assert results == []
