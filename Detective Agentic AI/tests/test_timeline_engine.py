"""
tests/test_timeline_engine.py

Unit tests for agent/timeline_engine.py and TimelineRepository.
"""

import os
import pytest

from agent.timeline_engine import TimelineEngine, EVENT_TYPES
from database.connection import init_db
from database.models import Case
from database.repository import TimelineRepository, CaseRepository


@pytest.fixture
def timeline_eng(tmp_path):
    db_file = str(tmp_path / "test_timeline.db")
    init_db(db_file)
    c_repo = CaseRepository(db_path=db_file)
    t_repo = TimelineRepository(db_path=db_file)

    test_case = Case(
        case_id="CASE-TL-001",
        title="Night Heist Investigation",
        description="Alarm triggered at depot",
    )
    c_repo.create_case(test_case)

    return TimelineEngine(repository=t_repo, case_repo=c_repo)


def test_record_timeline_event_success(timeline_eng):
    ok, msg, ev = timeline_eng.record_event(
        case_id="CASE-TL-001",
        timestamp="2026-03-15 01:23:00",
        event_type="INCIDENT",
        description="Depot perimeter alarm breached",
        source="Central Dispatch",
    )
    assert ok
    assert ev is not None
    assert ev.event_id.startswith("TL-")
    assert ev.case_id == "CASE-TL-001"
    assert ev.event_type == "INCIDENT"


def test_chronological_ordering(timeline_eng):
    timeline_eng.record_event(
        case_id="CASE-TL-001",
        timestamp="2026-03-15 03:00:00",
        event_type="EVIDENCE_ADDED",
        description="Crowbar recovered near gate",
    )
    timeline_eng.record_event(
        case_id="CASE-TL-001",
        timestamp="2026-03-15 01:00:00",
        event_type="INCIDENT",
        description="Break-in occurred",
    )
    timeline_eng.record_event(
        case_id="CASE-TL-001",
        timestamp="2026-03-15 02:00:00",
        event_type="WITNESS_STATEMENT",
        description="Security guard interviewed",
    )

    events = timeline_eng.get_case_timeline("CASE-TL-001")
    assert len(events) == 3
    # Check strict chronological order
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)
    assert events[0].event_type == "INCIDENT"
    assert events[1].event_type == "WITNESS_STATEMENT"
    assert events[2].event_type == "EVIDENCE_ADDED"


def test_record_event_validation(timeline_eng):
    # Missing description
    ok, msg, _ = timeline_eng.record_event(
        case_id="CASE-TL-001",
        timestamp="2026-03-15 01:00:00",
        event_type="INCIDENT",
        description="",
    )
    assert not ok
    assert "description is required" in msg.lower()

    # Non-existent case
    ok_bad_case, msg_bad, _ = timeline_eng.record_event(
        case_id="NON-EXISTENT-CASE",
        timestamp="2026-03-15 01:00:00",
        event_type="INCIDENT",
        description="Some event",
    )
    assert not ok_bad_case
    assert "does not exist" in msg_bad


def test_delete_timeline_event(timeline_eng):
    ok, _, ev = timeline_eng.record_event(
        case_id="CASE-TL-001",
        timestamp="2026-03-15 01:00:00",
        event_type="INCIDENT",
        description="Temporary log",
    )
    assert ok
    del_ok, _ = timeline_eng.delete_event(ev.event_id)
    assert del_ok
    events = timeline_eng.get_case_timeline("CASE-TL-001")
    assert all(e.event_id != ev.event_id for e in events)
