"""
tests/test_evidence_engine.py

Unit tests for agent/evidence_engine.py, SHA-256 integrity calculation,
and duplicate upload prevention.
"""

import hashlib
import os
import pytest

from agent.evidence_engine import EvidenceEngine
from database.connection import init_db
from database.models import Case
from database.repository import EvidenceRepository, CaseRepository


@pytest.fixture
def evidence_eng(tmp_path):
    db_file = str(tmp_path / "test_evidence.db")
    storage_dir = str(tmp_path / "evidence_storage")
    os.makedirs(storage_dir, exist_ok=True)
    init_db(db_file)
    case_repo = CaseRepository(db_path=db_file)
    ev_repo = EvidenceRepository(db_path=db_file)

    # Register parent case
    test_case = Case(
        case_id="CASE-EV-TEST",
        title="Bank Vault Breach",
        description="Safe deposit boxes cracked",
    )
    case_repo.create_case(test_case)

    return EvidenceEngine(repository=ev_repo, case_repo=case_repo, storage_dir=storage_dir)


def test_sha256_calculation():
    payload = b"INVESTIGATIVE FORENSIC PAYLOAD 2026"
    expected = hashlib.sha256(payload).hexdigest()
    assert EvidenceEngine.calculate_sha256(payload) == expected


def test_ingest_evidence_success(evidence_eng):
    content = b"PDF mock byte stream for forensic report"
    ok, msg, ev = evidence_eng.ingest_evidence(
        case_id="CASE-EV-TEST",
        filename="forensic_report.pdf",
        file_bytes=content,
        description="Initial ballistics and toolmark report",
        source="State Forensic Lab",
    )
    assert ok
    assert ev is not None
    assert ev.evidence_id.startswith("EV-")
    assert ev.case_id == "CASE-EV-TEST"
    assert ev.file_type == "PDF"
    assert ev.sha256_hash == hashlib.sha256(content).hexdigest()
    assert os.path.isfile(ev.storage_path)


def test_duplicate_upload_prevention(evidence_eng):
    content = b"UNIQUE SURVEILLANCE STILL FRAME"
    ok, msg, ev1 = evidence_eng.ingest_evidence(
        case_id="CASE-EV-TEST",
        filename="frame_01.png",
        file_bytes=content,
        description="Gate 1 camera snapshot",
    )
    assert ok

    # Attempt to upload the identical file (even with a different filename)
    ok_dup, msg_dup, _ = evidence_eng.ingest_evidence(
        case_id="CASE-EV-TEST",
        filename="renamed_frame.png",
        file_bytes=content,
        description="Different description",
    )
    assert not ok_dup
    assert "Duplicate evidence rejected" in msg_dup


def test_file_type_and_size_validation(evidence_eng):
    # Disallowed executable
    ok, msg, _ = evidence_eng.ingest_evidence(
        case_id="CASE-EV-TEST",
        filename="virus.exe",
        file_bytes=b"MZ12345",
    )
    assert not ok
    assert "Unsupported file type" in msg

    # Empty file
    ok_empty, msg_empty, _ = evidence_eng.ingest_evidence(
        case_id="CASE-EV-TEST",
        filename="empty.txt",
        file_bytes=b"",
    )
    assert not ok_empty
    assert "empty" in msg_empty.lower()


def test_delete_evidence(evidence_eng):
    content = b"Audio wire recording excerpt"
    ok, _, ev = evidence_eng.ingest_evidence(
        case_id="CASE-EV-TEST",
        filename="wiretap.wav",
        file_bytes=content,
        description="Audio snippet",
    )
    assert ok
    stored_path = ev.storage_path
    assert os.path.isfile(stored_path)

    del_ok, del_msg = evidence_eng.delete_evidence(ev.evidence_id)
    assert del_ok
    assert evidence_eng.get_evidence(ev.evidence_id) is None
    assert not os.path.isfile(stored_path)
