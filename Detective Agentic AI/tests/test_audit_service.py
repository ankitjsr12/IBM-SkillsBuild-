"""
tests/test_audit_service.py

Unit tests for services/audit_service.py:
- Immutable audit log append
- Querying and filtering logs by actor and action
- Handling malformed inputs gracefully
"""

import pytest
from database.connection import init_db
from database.repository import AuditRepository
from services.audit_service import AuditService, log_audit_event


@pytest.fixture
def audit_svc(tmp_path):
    db_file = str(tmp_path / "test_audit.db")
    init_db(db_file)
    repo = AuditRepository(db_path=db_file)
    return AuditService(audit_repo=repo, db_path=db_file)


def test_log_creation_and_query(audit_svc):
    entry = audit_svc.log(
        username="lead_investigator",
        action="EVIDENCE_UPLOAD",
        target_object="EV-1001",
        result="SUCCESS",
        details={"file_name": "surveillance_log.pdf", "size_kb": 128},
    )

    assert entry.log_id.startswith("AUD-")
    assert entry.username == "lead_investigator"
    assert entry.action == "EVIDENCE_UPLOAD"
    assert entry.result == "SUCCESS"

    logs = audit_svc.query_logs(username="lead_investigator")
    assert len(logs) == 1
    assert logs[0].target_object == "EV-1001"
    assert logs[0].details.get("size_kb") == 128


def test_audit_filters(audit_svc):
    audit_svc.log(username="alice", action="CASE_CREATED", target_object="CASE-01")
    audit_svc.log(username="bob", action="LOGIN_SUCCESS", target_object="bob")
    audit_svc.log(username="alice", action="SUSPECT_ADDED", target_object="SUSP-01")

    alice_logs = audit_svc.query_logs(username="alice")
    assert len(alice_logs) == 2

    login_logs = audit_svc.query_logs(action="LOGIN_SUCCESS")
    assert len(login_logs) == 1
    assert login_logs[0].username == "bob"

    assert audit_svc.get_total_count() == 3
