"""
agent/case_engine.py

Case Management Business Logic Engine.
Coordinates case lifecycle, ID validation, file synchronization with cases/*.json
for RAG retrieval compatibility, and export generation.
"""

import json
import logging
import os
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from database.models import Case, CaseStatus, CasePriority
from database.repository import CaseRepository
from database.connection import CASES_DIR
from utils.validators import validate_case_id

logger = logging.getLogger(__name__)


class CaseEngine:
    """Manages case operations, validation, and RAG index synchronization."""

    def __init__(self, repository: Optional[CaseRepository] = None, sync_cases_dir: bool = True):
        self.repo = repository or CaseRepository()
        self.sync_cases_dir = sync_cases_dir
        self.cases_dir = CASES_DIR

    def generate_unique_case_id(self, prefix: str = "CASE") -> str:
        """Generate a random unique, collisions-free Case ID."""
        year = time.strftime("%Y")
        for _ in range(10):
            token = secrets.token_hex(3).upper()
            candidate = f"{prefix}-{year}-{token}"
            if not self.repo.get_case(candidate):
                return candidate
        # Fallback with timestamp
        return f"{prefix}-{year}-{int(time.time() * 1000) % 1000000}"

    def create_case(
        self,
        title: str,
        case_id: Optional[str] = None,
        case_type: str = "General Investigation",
        description: str = "",
        location: str = "Not provided",
        date_opened: Optional[str] = None,
        priority: str = CasePriority.MEDIUM.value,
        assigned_investigator: str = "Unassigned",
        tags: Optional[List[str]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Optional[Case]]:
        """Validate, generate ID if needed, and create a new investigation case."""
        clean_title = str(title or "").strip()
        if not clean_title:
            return False, "Case title is required and cannot be empty.", None

        if case_id and case_id.strip():
            cid = case_id.strip()
            valid, msg = validate_case_id(cid)
            if not valid:
                return False, f"Invalid Case ID: {msg}", None
            if self.repo.get_case(cid):
                return False, f"A case with ID '{cid}' already exists. Please use a unique ID.", None
        else:
            cid = self.generate_unique_case_id()

        clean_status = CaseStatus.OPEN.value
        clean_priority = priority.upper().strip() if priority else CasePriority.MEDIUM.value
        if clean_priority not in [p.value for p in CasePriority]:
            clean_priority = CasePriority.MEDIUM.value

        case_obj = Case(
            case_id=cid,
            title=clean_title,
            case_type=case_type.strip() or "General Investigation",
            description=str(description or "").strip(),
            location=str(location or "Not provided").strip(),
            date_opened=date_opened.strip() if date_opened else time.strftime("%Y-%m-%d"),
            status=clean_status,
            priority=clean_priority,
            assigned_investigator=str(assigned_investigator or "Unassigned").strip(),
            tags=tags or [],
            extra_metadata=extra_metadata or {},
        )

        try:
            created = self.repo.create_case(case_obj)
            if self.sync_cases_dir:
                self._sync_case_to_json(created)
            return True, f"Case '{cid}' successfully created.", created
        except Exception as exc:
            logger.error("Failed to create case: %s", exc)
            return False, f"Database error creating case: {exc}", None

    def get_case(self, case_id: str) -> Optional[Case]:
        """Fetch a case by its ID."""
        if not case_id:
            return None
        return self.repo.get_case(case_id.strip())

    def update_case(self, case_id: str, updates: Dict[str, Any]) -> Tuple[bool, str, Optional[Case]]:
        """Update fields of an existing case and synchronize with RAG files."""
        if not case_id:
            return False, "Case ID is required.", None
        existing = self.repo.get_case(case_id.strip())
        if not existing:
            return False, f"Case with ID '{case_id}' not found.", None

        try:
            updated = self.repo.update_case(case_id.strip(), updates)
            if updated and self.sync_cases_dir:
                self._sync_case_to_json(updated)
            return True, f"Case '{case_id}' successfully updated.", updated
        except Exception as exc:
            logger.error("Failed to update case %s: %s", case_id, exc)
            return False, f"Database error updating case: {exc}", None

    def archive_case(self, case_id: str) -> Tuple[bool, str]:
        """Archive a case."""
        if not case_id:
            return False, "Case ID is required."
        success = self.repo.archive_case(case_id.strip())
        if success:
            c = self.repo.get_case(case_id.strip())
            if c and self.sync_cases_dir:
                self._sync_case_to_json(c)
            return True, f"Case '{case_id}' has been archived."
        return False, f"Case '{case_id}' could not be archived or does not exist."

    def delete_case(self, case_id: str) -> Tuple[bool, str]:
        """Permanently delete a case."""
        if not case_id:
            return False, "Case ID is required."
        success = self.repo.delete_case(case_id.strip())
        if success:
            if self.sync_cases_dir:
                self._remove_case_json(case_id.strip())
            return True, f"Case '{case_id}' has been deleted."
        return False, f"Case '{case_id}' could not be deleted or does not exist."

    def list_cases(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Case]:
        """Query cases with filters and search keywords."""
        return self.repo.list_cases(status=status, priority=priority, search=search, limit=limit, offset=offset)

    def get_statistics(self) -> Dict[str, Any]:
        """Aggregate case statistics for investigation dashboards."""
        return self.repo.count_cases()

    def export_cases(self, export_format: str = "json", case_ids: Optional[List[str]] = None) -> Tuple[str, str, str]:
        """
        Export cases in JSON or CSV format.
        Returns (content, mime_type, file_name).
        """
        fmt = export_format.lower().strip()
        ts = time.strftime("%Y%m%d_%H%M%S")
        if fmt == "csv":
            content = self.repo.export_cases_csv(case_ids)
            return content, "text/csv", f"Cases_Export_{ts}.csv"
        else:
            content = self.repo.export_cases_json(case_ids)
            return content, "application/json", f"Cases_Export_{ts}.json"

    def _sync_case_to_json(self, case: Case) -> None:
        """Write case to cases/<case_id>.json so CaseRetriever RAG can vectorize it immediately."""
        try:
            os.makedirs(self.cases_dir, exist_ok=True)
            fname = f"{case.case_id}.json"
            fpath = os.path.join(self.cases_dir, fname)
            
            # Format compatible with existing case_001.json structure
            data = {
                "case_id": case.case_id,
                "title": case.title,
                "case_title": case.title,
                "crime_type": case.case_type,
                "case_type": case.case_type,
                "status": case.status,
                "priority": case.priority,
                "location": case.location,
                "date_opened": case.date_opened,
                "assigned_investigator": case.assigned_investigator,
                "summary": case.description,
                "description": case.description,
                "tags": case.tags,
                "common_traits": case.tags,
                "created_at": case.created_at,
                "updated_at": case.updated_at,
            }
            if case.extra_metadata:
                data.update(case.extra_metadata)

            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("Synchronized case %s to RAG cases directory: %s", case.case_id, fpath)
        except Exception as exc:
            logger.warning("Could not sync case %s to JSON: %s", case.case_id, exc)

    def _remove_case_json(self, case_id: str) -> None:
        """Remove JSON file if case was deleted."""
        try:
            fname = f"{case_id}.json"
            fpath = os.path.join(self.cases_dir, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
        except Exception as exc:
            logger.warning("Could not remove case JSON file %s: %s", case_id, exc)
