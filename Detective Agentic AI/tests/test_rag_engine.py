"""
tests/test_rag_engine.py

Unit tests for agent/rag_engine.py:
- Cleaning and tokenization
- Overlapping chunking
- Indexing cases
- Top-k retrieval with relevance threshold
- Source attribution (case_id, similarity, timestamp)
- Zero fabrication on irrelevant queries
"""

import json
import os
import pytest

from agent.rag_engine import RAGEngine


@pytest.fixture
def rag_eng(tmp_path):
    cases_dir = str(tmp_path / "rag_cases")
    os.makedirs(cases_dir, exist_ok=True)

    c1 = {
        "case_id": "RAG-CASE-01",
        "title": "Diamond Showroom Tunneling",
        "crime_type": "Burglary",
        "location": "Antwerp District",
        "summary": "Perpetrators excavated an underground tunnel into the vault basement, disarming seismic sensors.",
        "modus_operandi": "Tunneling through sewer network, laser sensor bypass, targeting diamonds and high-value gems.",
        "common_traits": ["tunneling", "sewer", "seismic", "lasers", "diamonds"],
    }
    c2 = {
        "case_id": "RAG-CASE-02",
        "title": "ATM Cash Box Gas Explosion",
        "crime_type": "Robbery",
        "location": "Suburban Highway",
        "summary": "Combustible gas mixture pumped into ATM slot and ignited using remote detonation wire.",
        "modus_operandi": "Gas explosion technique, stolen getaway sedan, nighttime operation.",
        "common_traits": ["gas explosion", "acetylene", "atm", "detonator"],
    }

    with open(os.path.join(cases_dir, "case_01.json"), "w", encoding="utf-8") as f:
        json.dump(c1, f)
    with open(os.path.join(cases_dir, "case_02.json"), "w", encoding="utf-8") as f:
        json.dump(c2, f)

    return RAGEngine(cases_dir=cases_dir, threshold=0.15)


def test_clean_text_and_tokenization():
    raw = "  Tunneling \n\t Through   Sewer   SYSTEM! "
    cleaned = RAGEngine.clean_text(raw)
    assert cleaned == "Tunneling Through Sewer SYSTEM!"

    tokens = RAGEngine.tokenize(cleaned)
    assert tokens == ["tunneling", "through", "sewer", "system"]


def test_chunking_with_overlap():
    long_text = "word " * 300
    chunks = RAGEngine.chunk_text(long_text, chunk_size=100, overlap=20)
    assert len(chunks) > 1
    # Check that chunks have content
    assert all(len(c.split()) > 0 for c in chunks)


def test_rag_retrieval_matching(rag_eng):
    query = "excavating underground tunnel sewer to bypass seismic sensors"
    results = rag_eng.search(query, top_k=2)
    assert len(results) > 0
    top = results[0]
    assert top["case_id"] == "RAG-CASE-01"
    assert "Diamond" in top["case_title"]
    assert top["similarity"] >= 0.15
    assert top["similarity_pct"].endswith("%")
    assert "Case Precedent Record [RAG-CASE-01]" in top["source"]
    assert top["retrieval_timestamp"] is not None
    assert top["result_type"] == "RETRIEVED EVIDENCE"


def test_rag_irrelevant_query_returns_empty(rag_eng):
    # Completely unrelated query about outer space astrophysics
    irrelevant_query = "astrophysics black hole event horizon quantum gravity cosmic radiation"
    results = rag_eng.search(irrelevant_query, top_k=3, threshold=0.40)
    # Never fabricate a precedent
    assert len(results) == 0
