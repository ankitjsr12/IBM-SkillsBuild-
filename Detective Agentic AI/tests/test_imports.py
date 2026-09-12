"""
tests/test_imports.py

Import and syntax validation tests.
Ensures all production modules can be imported without errors.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_import_agent_billing():
    import agent.billing  # noqa: F401


def test_import_agent_outreach():
    import agent.outreach  # noqa: F401


def test_import_agent_analyzer():
    import agent.analyzer  # noqa: F401


def test_import_rag_retriever():
    import rag.retriever  # noqa: F401


def test_import_rag_vector_search():
    import rag.vector_search  # noqa: F401


def test_import_case_parser():
    import case_parser.parser  # noqa: F401


def test_import_agent_engine():
    import agent.agent_engine  # noqa: F401


def test_billing_constants_present():
    from agent.billing import (
        STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED,
        STATUS_PARTIAL, STATUS_TOPUP_DONE, STATUS_FLAGGED, STATUS_INVALID_UTR,
    )
    assert STATUS_PENDING == "PENDING"
    assert STATUS_APPROVED == "APPROVED"
    assert STATUS_REJECTED == "REJECTED"


def test_outreach_exports_present():
    from agent.outreach import (
        scrape_leads_sync, send_cold_emails, load_leads, save_leads,
        COLD_EMAIL_SUBJECT, COLD_EMAIL_BODY, LEADS_FILE,
    )
    assert callable(scrape_leads_sync)
    assert callable(send_cold_emails)
    assert callable(load_leads)
    assert callable(save_leads)
    assert isinstance(COLD_EMAIL_SUBJECT, str)
    assert isinstance(COLD_EMAIL_BODY, str)


def test_retriever_constants_present():
    from rag.retriever import SIMILARITY_THRESHOLD, RESULT_SOURCE_LABEL, NO_MATCH_SENTINEL
    assert 0.0 <= SIMILARITY_THRESHOLD <= 1.0
    assert isinstance(RESULT_SOURCE_LABEL, str)
    assert isinstance(NO_MATCH_SENTINEL, str)
