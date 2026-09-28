"""
agent/suspect_engine.py

Suspect Management Business Logic Engine.
Maintains persistent suspect profiles, case associations, evidence links,
and assessment history with strict data privacy boundaries.

CRITICAL PRIVACY RULE:
Does NOT infer sensitive personal characteristics or invent missing information.
Any unprovided field defaults strictly to "Not provided".
"""

import json
import logging
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from database.models import Suspect
from database.repository import SuspectRepository
from utils.validators import validate_suspect_id

logger = logging.getLogger(__name__)


class SuspectEngine:
    """Coordinates suspect profile management, assessment tracking, and case linking."""

    def __init__(self, repository: Optional[SuspectRepository] = None):
        self.repo = repository or SuspectRepository()

    def generate_unique_suspect_id(self, prefix: str = "SUSP") -> str:
        """Generate a unique random collision-free Suspect ID."""
        year = time.strftime("%Y")
        for _ in range(10):
            token = secrets.token_hex(3).upper()
            candidate = f"{prefix}-{year}-{token}"
            if not self.repo.get_suspect(candidate):
                return candidate
        return f"{prefix}-{year}-{int(time.time() * 1000) % 1000000}"

    def register_suspect(
        self,
        name: str,
        suspect_id: Optional[str] = None,
        alias: Optional[str] = None,
        age: Optional[str] = None,
        location: Optional[str] = None,
        known_associations: Optional[str] = None,
        observed_behaviors: Optional[str] = None,
        modus_operandi: Optional[str] = None,
        traits: Optional[List[str]] = None,
        case_connections: Optional[List[str]] = None,
        notes: Optional[str] = None,
        evidence_links: Optional[List[str]] = None,
    ) -> Tuple[bool, str, Optional[Suspect]]:
        """Register a new suspect profile with strict privacy boundaries."""
        clean_name = str(name or "").strip()
        if not clean_name:
            return False, "Suspect name or alias is required.", None

        if suspect_id and suspect_id.strip():
            sid = suspect_id.strip()
            valid, msg = validate_suspect_id(sid)
            if not valid:
                return False, f"Invalid Suspect ID: {msg}", None
            if self.repo.get_suspect(sid):
                return False, f"Suspect with ID '{sid}' already exists.", None
        else:
            sid = self.generate_unique_suspect_id()

        suspect = Suspect(
            suspect_id=sid,
            name=clean_name,
            alias=alias.strip() if alias and alias.strip() else "Not provided",
            age=age.strip() if age and age.strip() else "Not provided",
            location=location.strip() if location and location.strip() else "Not provided",
            known_associations=known_associations.strip() if known_associations and known_associations.strip() else "Not provided",
            observed_behaviors=observed_behaviors.strip() if observed_behaviors and observed_behaviors.strip() else "Not provided",
            modus_operandi=modus_operandi.strip() if modus_operandi and modus_operandi.strip() else "Not provided",
            traits=traits or [],
            case_connections=case_connections or [],
            notes=str(notes or "").strip(),
            evidence_links=evidence_links or [],
            assessment_history=[],
        )

        try:
            created = self.repo.create_suspect(suspect)
            return True, f"Suspect '{sid}' successfully registered.", created
        except Exception as exc:
            logger.error("Failed to register suspect: %s", exc)
            return False, f"Database error registering suspect: {exc}", None

    def get_suspect(self, suspect_id: str) -> Optional[Suspect]:
        """Fetch suspect profile by ID."""
        if not suspect_id:
            return None
        return self.repo.get_suspect(suspect_id.strip())

    def update_suspect(self, suspect_id: str, updates: Dict[str, Any]) -> Tuple[bool, str, Optional[Suspect]]:
        """Update suspect attributes."""
        if not suspect_id:
            return False, "Suspect ID is required.", None
        existing = self.repo.get_suspect(suspect_id.strip())
        if not existing:
            return False, f"Suspect with ID '{suspect_id}' not found.", None

        try:
            updated = self.repo.update_suspect(suspect_id.strip(), updates)
            return True, f"Suspect '{suspect_id}' successfully updated.", updated
        except Exception as exc:
            logger.error("Failed to update suspect %s: %s", suspect_id, exc)
            return False, f"Database error updating suspect: {exc}", None

    def delete_suspect(self, suspect_id: str) -> Tuple[bool, str]:
        """Delete suspect record."""
        if not suspect_id:
            return False, "Suspect ID is required."
        success = self.repo.delete_suspect(suspect_id.strip())
        if success:
            return True, f"Suspect '{suspect_id}' deleted."
        return False, f"Suspect '{suspect_id}' not found or could not be deleted."

    def list_suspects(
        self,
        search: Optional[str] = None,
        case_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Suspect]:
        """Query suspects with keyword and case filtering."""
        return self.repo.list_suspects(search=search, case_id=case_id, limit=limit)

    def record_assessment(self, suspect_id: str, assessment_data: Dict[str, Any]) -> Tuple[bool, str, Optional[Suspect]]:
        """Append an AI model profiling assessment to the suspect's audit trail."""
        if not suspect_id:
            return False, "Suspect ID is required.", None
        suspect = self.repo.get_suspect(suspect_id.strip())
        if not suspect:
            return False, f"Suspect '{suspect_id}' not found.", None

        # Format record
        record = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "tendency_score": str(assessment_data.get("tendency_score", "0%")),
            "risk_level": str(assessment_data.get("risk_level", "UNKNOWN")),
            "match_quality": str(assessment_data.get("match_quality", "N/A")),
            "summary": str(assessment_data.get("summary", "")),
            "scoring_breakdown": assessment_data.get("scoring_breakdown", []),
            "matched_cases_count": len(assessment_data.get("similar_cases", [])),
        }
        updated = self.repo.add_assessment(suspect_id.strip(), record)
        if updated:
            return True, f"Assessment recorded for suspect '{suspect_id}'.", updated
        return False, "Failed to record assessment.", None

    def link_case(self, suspect_id: str, case_id: str) -> Tuple[bool, str, Optional[Suspect]]:
        """Link a case to the suspect's case connections."""
        suspect = self.repo.get_suspect(suspect_id.strip())
        if not suspect:
            return False, f"Suspect '{suspect_id}' not found.", None
        connections = list(suspect.case_connections)
        clean_cid = case_id.strip()
        if clean_cid not in connections:
            connections.append(clean_cid)
            updated = self.repo.update_suspect(suspect_id.strip(), {"case_connections": connections})
            return True, f"Linked case '{clean_cid}' to suspect '{suspect_id}'.", updated
        return True, "Case already linked.", suspect
