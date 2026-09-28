"""
tests/test_suspect_engine.py

Unit tests for agent/suspect_engine.py and SuspectRepository.
"""

import os
import pytest

from agent.suspect_engine import SuspectEngine
from database.connection import init_db
from database.repository import SuspectRepository


@pytest.fixture
def suspect_eng(tmp_path):
    db_file = str(tmp_path / "test_suspects.db")
    init_db(db_file)
    repo = SuspectRepository(db_path=db_file)
    return SuspectEngine(repository=repo)


def test_register_suspect_with_defaults(suspect_eng):
    # Only name provided — all missing fields must strictly default to "Not provided"
    ok, msg, suspect = suspect_eng.register_suspect(name="Subject X")
    assert ok
    assert suspect is not None
    assert suspect.suspect_id.startswith("SUSP-")
    assert suspect.alias == "Not provided"
    assert suspect.age == "Not provided"
    assert suspect.location == "Not provided"
    assert suspect.known_associations == "Not provided"
    assert suspect.observed_behaviors == "Not provided"
    assert suspect.modus_operandi == "Not provided"
    assert suspect.assessment_history == []


def test_custom_suspect_id_and_validation(suspect_eng):
    # Invalid ID
    ok, msg, _ = suspect_eng.register_suspect(name="Test", suspect_id="bad id!")
    assert not ok
    assert "Invalid Suspect ID" in msg

    # Valid ID
    ok, msg, suspect = suspect_eng.register_suspect(name="Marcus Cole", suspect_id="SUSP-2026-099")
    assert ok
    assert suspect.suspect_id == "SUSP-2026-099"

    # Duplicate ID
    ok_dup, msg_dup, _ = suspect_eng.register_suspect(name="Another", suspect_id="SUSP-2026-099")
    assert not ok_dup
    assert "already exists" in msg_dup


def test_update_suspect_and_link_case(suspect_eng):
    ok, _, suspect = suspect_eng.register_suspect(name="Arthur Pendelton", suspect_id="SUSP-AP-01")
    assert ok

    # Update
    u_ok, u_msg, u_susp = suspect_eng.update_suspect("SUSP-AP-01", {
        "location": "Sector 9",
        "modus_operandi": "Lockpicking deadbolts during rainstorms",
    })
    assert u_ok
    assert u_susp.location == "Sector 9"
    assert "Lockpicking" in u_susp.modus_operandi

    # Link Case
    l_ok, l_msg, l_susp = suspect_eng.link_case("SUSP-AP-01", "CASE-2026-001")
    assert l_ok
    assert "CASE-2026-001" in l_susp.case_connections


def test_record_assessment_history(suspect_eng):
    ok, _, suspect = suspect_eng.register_suspect(name="Target Bravo", suspect_id="SUSP-TB-02")
    assert ok

    assessment_payload = {
        "tendency_score": "74%",
        "risk_level": "HIGH RISK",
        "match_quality": "Strong case-index similarity",
        "summary": "Observed traits align with historical burglary records.",
        "similar_cases": [{"case_id": "CASE-001"}, {"case_id": "CASE-002"}],
    }
    rec_ok, rec_msg, updated = suspect_eng.record_assessment("SUSP-TB-02", assessment_payload)
    assert rec_ok
    assert len(updated.assessment_history) == 1
    entry = updated.assessment_history[0]
    assert entry["tendency_score"] == "74%"
    assert entry["risk_level"] == "HIGH RISK"
    assert entry["matched_cases_count"] == 2
