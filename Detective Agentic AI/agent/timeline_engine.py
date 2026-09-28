"""
agent/timeline_engine.py

Case Chronology and Evidence Timeline Business Logic Engine.
Maintains verified temporal sequences of incidents, evidence additions, witness statements,
digital footprints, observed behaviors, RAG retrievals, and investigator reviews.

RULE (Part 7):
Never fabricate timeline events.
Each event must have timestamp, type, description, source, and optional evidence link.
"""

import logging
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from database.models import TimelineEvent
from database.repository import TimelineRepository, CaseRepository

logger = logging.getLogger(__name__)

EVENT_TYPES = [
    "INCIDENT",
    "EVIDENCE_ADDED",
    "WITNESS_STATEMENT",
    "DIGITAL_EVIDENCE",
    "OBSERVED_BEHAVIOR",
    "RAG_RETRIEVAL",
    "MODEL_ASSESSMENT",
    "INVESTIGATOR_REVIEW",
]


class TimelineEngine:
    """Coordinates chronological event tracking for active investigations."""

    def __init__(
        self,
        repository: Optional[TimelineRepository] = None,
        case_repo: Optional[CaseRepository] = None,
    ):
        self.repo = repository or TimelineRepository()
        self.case_repo = case_repo or CaseRepository()

    def generate_unique_event_id(self, prefix: str = "TL") -> str:
        """Generate a random collision-free Timeline Event ID."""
        year = time.strftime("%Y")
        for _ in range(10):
            token = secrets.token_hex(3).upper()
            candidate = f"{prefix}-{year}-{token}"
            if not self.repo.get_event(candidate):
                return candidate
        return f"{prefix}-{year}-{int(time.time() * 1000) % 1000000}"

    def record_event(
        self,
        case_id: str,
        timestamp: str,
        event_type: str,
        description: str,
        source: str = "Investigation Unit",
        linked_evidence_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[TimelineEvent]]:
        """Validate and record a verified chronological event."""
        clean_cid = str(case_id or "").strip()
        if not clean_cid:
            return False, "Case ID is required.", None

        case = self.case_repo.get_case(clean_cid)
        if not case:
            return False, f"Case '{clean_cid}' does not exist in the database.", None

        clean_type = str(event_type or "INCIDENT").upper().strip()
        if clean_type not in EVENT_TYPES:
            clean_type = "INCIDENT"

        clean_desc = str(description or "").strip()
        if not clean_desc:
            return False, "Event description is required.", None

        clean_ts = str(timestamp or "").strip()
        if not clean_ts:
            clean_ts = time.strftime("%Y-%m-%d %H:%M:%S")

        eid = event_id.strip() if event_id and event_id.strip() else self.generate_unique_event_id()

        event = TimelineEvent(
            event_id=eid,
            case_id=clean_cid,
            timestamp=clean_ts,
            event_type=clean_type,
            description=clean_desc,
            source=str(source or "Investigation Unit").strip(),
            linked_evidence_id=str(linked_evidence_id).strip() if linked_evidence_id else None,
            created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
        )

        try:
            created = self.repo.create_event(event)
            return True, f"Timeline event '{eid}' recorded successfully.", created
        except Exception as exc:
            logger.error("Failed to record timeline event: %s", exc)
            return False, f"Database error recording timeline event: {exc}", None

    def get_case_timeline(self, case_id: str) -> List[TimelineEvent]:
        """Fetch chronological sequence of events for a case."""
        if not case_id:
            return []
        return self.repo.list_events_for_case(case_id.strip())

    def delete_event(self, event_id: str) -> Tuple[bool, str]:
        """Delete timeline event."""
        if not event_id:
            return False, "Event ID is required."
        success = self.repo.delete_event(event_id.strip())
        if success:
            return True, f"Timeline event '{event_id}' deleted."
        return False, f"Event '{event_id}' not found or could not be deleted."
