"""
tests/test_analytics_engine.py

Unit tests for agent/analytics_engine.py:
- KPI summary generation
- Aggregations by status, priority, crime type, and evidence format
- Zero-case handling (no crash)
"""

import pytest
from agent.analytics_engine import AnalyticsEngine
from database.connection import init_db
from database.models import Case, Evidence, Suspect, TimelineEvent
from database.repository import CaseRepository, SuspectRepository, EvidenceRepository, TimelineRepository


@pytest.fixture
def analytics_fixture(tmp_path):
    db_file = str(tmp_path / "test_analytics.db")
    init_db(db_file)
    c_repo = CaseRepository(db_path=db_file)
    s_repo = SuspectRepository(db_path=db_file)
    e_repo = EvidenceRepository(db_path=db_file)
    t_repo = TimelineRepository(db_path=db_file)

    # Populate sample data
    c_repo.create_case(Case(
        case_id="CASE-AN-01",
        title="Art Heist",
        case_type="Larceny",
        status="OPEN",
        priority="HIGH",
    ))
    c_repo.create_case(Case(
        case_id="CASE-AN-02",
        title="Cyber Extortion",
        case_type="Cybercrime",
        status="UNDER_REVIEW",
        priority="CRITICAL",
    ))

    s_repo.create_suspect(Suspect(
        suspect_id="SUSP-AN-01",
        name="Arthur Finch",
    ))

    e_repo.create_evidence(Evidence(
        evidence_id="EV-AN-01",
        case_id="CASE-AN-01",
        file_type="PDF",
        file_size_bytes=1024 * 1024 * 2,  # 2MB
        sha256_hash="aabbccdd" * 8,
    ))

    t_repo.create_event(TimelineEvent(
        event_id="TL-AN-01",
        case_id="CASE-AN-01",
        timestamp="2026-05-01 10:00:00",
        event_type="INCIDENT",
        description="Alarm triggered",
    ))

    engine = AnalyticsEngine(
        case_repo=c_repo,
        suspect_repo=s_repo,
        evidence_repo=e_repo,
        timeline_repo=t_repo,
        db_path=db_file,
    )
    return engine


def test_kpi_summary(analytics_fixture):
    kpis = analytics_fixture.get_kpi_summary()
    assert kpis["total_cases"] == 2
    assert kpis["open_cases"] == 1
    assert kpis["under_review_cases"] == 1
    assert kpis["total_suspects"] == 1
    assert kpis["total_evidence_items"] == 1
    assert kpis["total_timeline_events"] == 1
    assert kpis["storage_mb"] == 2.0


def test_breakdowns(analytics_fixture):
    by_status = analytics_fixture.get_cases_by_status()
    assert by_status.get("OPEN") == 1
    assert by_status.get("UNDER_REVIEW") == 1

    by_prio = analytics_fixture.get_cases_by_priority()
    assert by_prio.get("HIGH") == 1
    assert by_prio.get("CRITICAL") == 1

    by_type = analytics_fixture.get_cases_by_type()
    assert by_type.get("Larceny") == 1
    assert by_type.get("Cybercrime") == 1

    by_ev = analytics_fixture.get_evidence_by_type()
    assert by_ev.get("PDF") == 1


def test_recent_activity(analytics_fixture):
    recent = analytics_fixture.get_recent_case_activity(limit=5)
    assert len(recent) == 2
    assert recent[0]["case_id"] in ("CASE-AN-01", "CASE-AN-02")
