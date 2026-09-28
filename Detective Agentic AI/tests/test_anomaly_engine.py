"""
tests/test_anomaly_engine.py

Unit tests for agent/anomaly_engine.py:
- Detection of unusual timestamps
- Detection of duplicate events
- Detection of duplicate evidence hash collisions
- Burst frequency detection
- Strict "Potential anomaly detected" phrasing
"""

import os
import pytest

from agent.anomaly_engine import AnomalyEngine
from database.connection import init_db
from database.models import Case, Evidence, TimelineEvent
from database.repository import CaseRepository, EvidenceRepository, TimelineRepository


@pytest.fixture
def anomaly_eng(tmp_path):
    db_file = str(tmp_path / "test_anomalies.db")
    init_db(db_file)
    c_repo = CaseRepository(db_path=db_file)
    e_repo = EvidenceRepository(db_path=db_file)
    t_repo = TimelineRepository(db_path=db_file)

    test_case = Case(
        case_id="CASE-ANOM-01",
        title="Warehouse Arson",
        date_opened="2026-04-01",
        status="OPEN",
        updated_at="2026-04-02 12:00:00",
    )
    c_repo.create_case(test_case)

    return AnomalyEngine(case_repo=c_repo, evidence_repo=e_repo, timeline_repo=t_repo)


def test_detect_event_preceding_case_opened(anomaly_eng):
    # Event dated 2026-03-01 precedes case open date 2026-04-01
    anomaly_eng.timeline_repo.create_event(TimelineEvent(
        event_id="TL-BAD-TIME",
        case_id="CASE-ANOM-01",
        timestamp="2026-03-01 00:00:00",
        event_type="EVIDENCE_ADDED",
        description="Evidence logged before case was registered",
    ))

    anomalies = anomaly_eng.scan_case_anomalies("CASE-ANOM-01")
    assert len(anomalies) > 0
    flag = anomalies[0]
    assert flag["anomaly"].startswith("Potential anomaly detected")
    assert "precedes Case Open Date" in flag["anomaly"]
    assert flag["severity"] == "MEDIUM"


def test_detect_repeated_timeline_event(anomaly_eng):
    desc = "Identical security guard witness interview transcription text"
    anomaly_eng.timeline_repo.create_event(TimelineEvent(
        event_id="TL-REP-1",
        case_id="CASE-ANOM-01",
        timestamp="2026-04-02 10:00:00",
        event_type="WITNESS_STATEMENT",
        description=desc,
    ))
    anomaly_eng.timeline_repo.create_event(TimelineEvent(
        event_id="TL-REP-2",
        case_id="CASE-ANOM-01",
        timestamp="2026-04-02 11:00:00",
        event_type="WITNESS_STATEMENT",
        description=desc,
    ))

    anomalies = anomaly_eng.scan_case_anomalies("CASE-ANOM-01")
    rep_flags = [a for a in anomalies if "Repeated Timeline Event" in a["anomaly"]]
    assert len(rep_flags) == 1
    assert "Identical event description" in rep_flags[0]["reason"]


def test_detect_duplicate_evidence_collision(anomaly_eng):
    mock_hash = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    ev1 = Evidence(
        evidence_id="EV-ANOM-1",
        case_id="CASE-ANOM-01",
        file_type="PNG",
        description="First CCTV capture",
        source="Camera 1",
        uploaded_by="Officer A",
        timestamp="2026-04-02 10:00:00",
        sha256_hash=mock_hash,
    )
    anomaly_eng.evidence_repo.create_evidence(ev1)

    # Directly insert second item with identical hash to simulate accidental duplicate record
    conn = anomaly_eng.evidence_repo._get_conn()
    with conn:
        conn.execute("""
            INSERT INTO evidence (
                evidence_id, case_id, file_type, description, source, uploaded_by, timestamp, sha256_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, ("EV-ANOM-2", "CASE-ANOM-01", "PNG", "Second duplicate CCTV capture", "Camera 2", "Officer B", "2026-04-02 11:00:00", mock_hash))
    conn.close()

    anomalies = anomaly_eng.scan_case_anomalies("CASE-ANOM-01")
    dup_flags = [a for a in anomalies if "Cryptographic Evidence Collision" in a["anomaly"]]
    assert len(dup_flags) == 1
    assert dup_flags[0]["severity"] == "HIGH"
