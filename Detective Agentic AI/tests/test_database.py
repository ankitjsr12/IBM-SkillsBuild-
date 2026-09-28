"""
tests/test_database.py

Unit tests for database/connection.py, database/models.py, and database/repository.py.
"""

import json
import os
import tempfile
import pytest

from database.models import Case, CaseStatus, CasePriority
from database.connection import init_db, migrate_existing_cases, get_db_connection
from database.repository import CaseRepository


@pytest.fixture
def temp_db_and_cases(tmp_path):
    """Fixture providing a clean temporary SQLite database and a test cases directory."""
    db_file = str(tmp_path / "test_investigation.db")
    cases_dir = str(tmp_path / "cases")
    os.makedirs(cases_dir, exist_ok=True)

    # Create 2 sample JSON case files
    c1 = {
        "case_id": "CASE-TEST-001",
        "title": "Jewelry Store Heist",
        "crime_type": "Robbery",
        "location": "Downtown",
        "date_opened": "2026-02-10",
        "status": "OPEN",
        "priority": "HIGH",
        "assigned_investigator": "Agent Carter",
        "summary": "Display cases smashed with sledgehammer.",
        "common_traits": ["sledgehammer", "night", "getaway motorcycle"],
    }
    c2 = {
        "case_id": "CASE-TEST-002",
        "title": "Cyber Extortion Incident",
        "crime_type": "Cybercrime",
        "location": "Financial District",
        "date_opened": "2026-03-01",
        "status": "UNDER_REVIEW",
        "priority": "CRITICAL",
        "assigned_investigator": "Agent Zhao",
        "summary": "Ransomware deployed across corporate workstations.",
        "common_traits": ["ransomware", "bitcoin", "phishing"],
    }
    with open(os.path.join(cases_dir, "case_001.json"), "w", encoding="utf-8") as f:
        json.dump(c1, f)
    with open(os.path.join(cases_dir, "case_002.json"), "w", encoding="utf-8") as f:
        json.dump(c2, f)

    init_db(db_file)
    return db_file, cases_dir


def test_init_db_creates_tables(temp_db_and_cases):
    db_file, _ = temp_db_and_cases
    conn = get_db_connection(db_file)
    try:
        tables = [
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table';"
            ).fetchall()
        ]
        assert "cases" in tables
        assert "suspects" in tables
        assert "evidence" in tables
        assert "timeline_events" in tables
        assert "audit_logs" in tables
        assert "users" in tables
    finally:
        conn.close()


def test_migrate_existing_cases(temp_db_and_cases):
    db_file, cases_dir = temp_db_and_cases
    imported = migrate_existing_cases(db_path=db_file, cases_dir=cases_dir)
    assert imported == 2

    # Second migration must be idempotent (0 newly imported)
    second_run = migrate_existing_cases(db_path=db_file, cases_dir=cases_dir)
    assert second_run == 0

    repo = CaseRepository(db_path=db_file)
    cases = repo.list_cases()
    assert len(cases) == 2
    assert any(c.case_id == "CASE-TEST-001" for c in cases)
    assert any(c.case_id == "CASE-TEST-002" for c in cases)


def test_case_crud_operations(temp_db_and_cases):
    db_file, _ = temp_db_and_cases
    repo = CaseRepository(db_path=db_file)

    # 1. Create
    new_case = Case(
        case_id="CASE-2026-X01",
        title="Industrial Espionage",
        case_type="Espionage",
        description="Proprietary blueprints exfiltrated.",
        location="Research Park",
        status=CaseStatus.OPEN.value,
        priority=CasePriority.HIGH.value,
        assigned_investigator="Lead Det. Ray",
        tags=["insider", "usb", "blueprints"],
    )
    created = repo.create_case(new_case)
    assert created.case_id == "CASE-2026-X01"
    assert created.title == "Industrial Espionage"

    # 2. Read
    fetched = repo.get_case("CASE-2026-X01")
    assert fetched is not None
    assert fetched.priority == "HIGH"
    assert "usb" in fetched.tags

    # 3. Duplicate ID rejection
    with pytest.raises(ValueError):
        repo.create_case(new_case)

    # 4. Update
    updated = repo.update_case("CASE-2026-X01", {
        "status": CaseStatus.UNDER_REVIEW.value,
        "priority": CasePriority.CRITICAL.value,
        "description": "Updated exfiltration details.",
    })
    assert updated.status == "UNDER_REVIEW"
    assert updated.priority == "CRITICAL"
    assert "Updated" in updated.description

    # 5. Archive
    archived_ok = repo.archive_case("CASE-2026-X01")
    assert archived_ok
    assert repo.get_case("CASE-2026-X01").status == CaseStatus.ARCHIVED.value

    # 6. Delete
    deleted_ok = repo.delete_case("CASE-2026-X01")
    assert deleted_ok
    assert repo.get_case("CASE-2026-X01") is None


def test_case_filtering_and_search(temp_db_and_cases):
    db_file, cases_dir = temp_db_and_cases
    migrate_existing_cases(db_path=db_file, cases_dir=cases_dir)
    repo = CaseRepository(db_path=db_file)

    # Filter by status
    open_cases = repo.list_cases(status="OPEN")
    assert len(open_cases) == 1
    assert open_cases[0].case_id == "CASE-TEST-001"

    # Filter by priority
    crit_cases = repo.list_cases(priority="CRITICAL")
    assert len(crit_cases) == 1
    assert crit_cases[0].case_id == "CASE-TEST-002"

    # Search keyword in description/summary
    sledge_results = repo.list_cases(search="sledgehammer")
    assert len(sledge_results) == 1
    assert sledge_results[0].case_id == "CASE-TEST-001"

    # Search keyword in title
    ransom_results = repo.list_cases(search="Cyber")
    assert len(ransom_results) == 1
    assert ransom_results[0].case_id == "CASE-TEST-002"


def test_case_statistics(temp_db_and_cases):
    db_file, cases_dir = temp_db_and_cases
    migrate_existing_cases(db_path=db_file, cases_dir=cases_dir)
    repo = CaseRepository(db_path=db_file)

    stats = repo.count_cases()
    assert stats["total"] == 2
    assert stats["open"] == 1
    assert stats["under_review"] == 1


def test_case_exports(temp_db_and_cases):
    db_file, cases_dir = temp_db_and_cases
    migrate_existing_cases(db_path=db_file, cases_dir=cases_dir)
    repo = CaseRepository(db_path=db_file)

    # JSON export
    json_str = repo.export_cases_json()
    exported_data = json.loads(json_str)
    assert isinstance(exported_data, list)
    assert len(exported_data) == 2
    assert exported_data[0]["case_id"].startswith("CASE-TEST-")

    # CSV export
    csv_str = repo.export_cases_csv()
    assert "case_id,title,case_type" in csv_str
    assert "CASE-TEST-001" in csv_str
    assert "CASE-TEST-002" in csv_str
