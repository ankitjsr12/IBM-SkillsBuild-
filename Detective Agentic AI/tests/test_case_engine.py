"""
tests/test_case_engine.py

Unit tests for agent/case_engine.py.
"""

import json
import os
import pytest

from agent.case_engine import CaseEngine
from database.connection import init_db
from database.repository import CaseRepository


@pytest.fixture
def engine(tmp_path):
    db_file = str(tmp_path / "engine_test.db")
    cases_dir = str(tmp_path / "engine_cases")
    os.makedirs(cases_dir, exist_ok=True)
    init_db(db_file)
    repo = CaseRepository(db_path=db_file)
    eng = CaseEngine(repository=repo, sync_cases_dir=True)
    eng.cases_dir = cases_dir
    return eng


def test_create_case_auto_id(engine):
    success, msg, case = engine.create_case(
        title="Dockside Cargo Tampering",
        case_type="Theft",
        description="Cargo seals severed on container #4812",
        priority="HIGH",
        location="Harbor Gate 4",
    )
    assert success
    assert case is not None
    assert case.case_id.startswith("CASE-")
    assert case.status == "OPEN"

    # Verify JSON sync file was created
    expected_json = os.path.join(engine.cases_dir, f"{case.case_id}.json")
    assert os.path.isfile(expected_json)
    with open(expected_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["case_id"] == case.case_id
        assert data["title"] == "Dockside Cargo Tampering"


def test_create_case_custom_id_and_validation(engine):
    # Invalid ID
    success, msg, _ = engine.create_case(title="Test", case_id="bad id with spaces!")
    assert not success
    assert "Invalid Case ID" in msg

    # Valid ID
    success, msg, case = engine.create_case(title="Counterfeit Currency", case_id="CASE-CC-001")
    assert success
    assert case.case_id == "CASE-CC-001"

    # Duplicate ID
    success2, msg2, _ = engine.create_case(title="Duplicate Test", case_id="CASE-CC-001")
    assert not success2
    assert "already exists" in msg2


def test_update_and_archive_case(engine):
    success, _, case = engine.create_case(title="Wire Fraud Syndicate", case_id="CASE-WF-001")
    assert success

    # Update
    up_ok, up_msg, up_case = engine.update_case("CASE-WF-001", {"priority": "CRITICAL", "location": "Offshore"})
    assert up_ok
    assert up_case.priority == "CRITICAL"
    assert up_case.location == "Offshore"

    # Archive
    arch_ok, arch_msg = engine.archive_case("CASE-WF-001")
    assert arch_ok
    assert engine.get_case("CASE-WF-001").status == "ARCHIVED"


def test_export_cases_engine(engine):
    engine.create_case(title="Export Case 1", case_id="CASE-EX-001")
    engine.create_case(title="Export Case 2", case_id="CASE-EX-002")

    content, mime, fname = engine.export_cases("json")
    assert mime == "application/json"
    assert "CASE-EX-001" in content
    assert fname.endswith(".json")

    content_csv, mime_csv, fname_csv = engine.export_cases("csv")
    assert mime_csv == "text/csv"
    assert "CASE-EX-002" in content_csv
    assert fname_csv.endswith(".csv")
