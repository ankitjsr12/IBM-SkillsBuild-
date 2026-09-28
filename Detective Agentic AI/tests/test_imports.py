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


def test_import_agent_profiler():
    import agent.profiler  # noqa: F401
    from agent.profiler import DetectiveAgent
    assert callable(DetectiveAgent)



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


def test_import_utils():
    import utils.logging_utils
    import utils.text_utils
    import utils.validators
    import utils.pdf_utils
    from utils.pdf_utils import generate_pdf_report, generate_investigation_dossier_pdf
    assert callable(generate_pdf_report)
    assert callable(generate_investigation_dossier_pdf)


def test_import_database_and_case_engine():
    import database.models
    import database.connection
    import database.repository
    import agent.case_engine
    from database.models import Case, CaseStatus, CasePriority
    from database.repository import CaseRepository
    from agent.case_engine import CaseEngine
    assert callable(CaseRepository)
    assert callable(CaseEngine)


def test_import_suspect_and_evidence_engines():
    import agent.suspect_engine
    import agent.evidence_engine
    from database.repository import SuspectRepository, EvidenceRepository
    from agent.suspect_engine import SuspectEngine
    from agent.evidence_engine import EvidenceEngine
    assert callable(SuspectRepository)
    assert callable(EvidenceRepository)
    assert callable(SuspectEngine)
    assert callable(EvidenceEngine)


def test_import_timeline_and_rag_engines():
    import agent.timeline_engine
    import agent.rag_engine
    from database.repository import TimelineRepository
    from agent.timeline_engine import TimelineEngine
    from agent.rag_engine import RAGEngine
    assert callable(TimelineRepository)
    assert callable(TimelineEngine)
    assert callable(RAGEngine)


def test_import_explainability_anomaly_and_graph_engines():
    import agent.explainability_engine
    import agent.anomaly_engine
    import agent.graph_engine
    from agent.explainability_engine import ExplainabilityEngine
    from agent.anomaly_engine import AnomalyEngine
    from agent.graph_engine import RelationshipGraphEngine
    assert callable(ExplainabilityEngine)
    assert callable(AnomalyEngine)
    assert callable(RelationshipGraphEngine)


def test_import_analytics_and_document_engines():
    import agent.analytics_engine
    import agent.document_engine
    from agent.analytics_engine import AnalyticsEngine
    from agent.document_engine import DocumentEngine
    assert callable(AnalyticsEngine)
    assert callable(DocumentEngine)


def test_import_auth_and_audit_services():
    import services.auth_service
    import services.audit_service
    from services.auth_service import AuthService
    from services.audit_service import AuditService
    assert callable(AuthService)
    assert callable(AuditService)






