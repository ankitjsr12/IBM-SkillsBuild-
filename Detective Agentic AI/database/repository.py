"""
database/repository.py

Repository pattern implementation for Cases and Investigation data access.
Abstracts all SQL queries and manages data model hydration.
"""

import csv
import io
import json
import logging
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

from database.models import Case, CaseStatus, CasePriority, Suspect, Evidence, TimelineEvent, AuditLog, User
from database.connection import get_db_connection



logger = logging.getLogger(__name__)


class CaseRepository:
    """Repository handling all CRUD and query operations for Cases."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def _row_to_case(self, row: sqlite3.Row) -> Case:
        d = dict(row)
        return Case.from_dict(d)

    def create_case(self, case: Case) -> Case:
        """Insert a new case record into the database."""
        conn = self._get_conn()
        try:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            tags_json = json.dumps(case.tags if isinstance(case.tags, list) else [])
            meta_json = json.dumps(case.extra_metadata if isinstance(case.extra_metadata, dict) else {})
            
            with conn:
                conn.execute("""
                    INSERT INTO cases (
                        case_id, title, case_type, description, location,
                        date_opened, status, priority, assigned_investigator,
                        tags, created_at, updated_at, extra_metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    case.case_id,
                    case.title,
                    case.case_type,
                    case.description,
                    case.location,
                    case.date_opened,
                    case.status,
                    case.priority,
                    case.assigned_investigator,
                    tags_json,
                    case.created_at or now,
                    now,
                    meta_json,
                ))
            return self.get_case(case.case_id) or case
        except sqlite3.IntegrityError as err:
            logger.error("Failed to create case: ID %s already exists (%s)", case.case_id, err)
            raise ValueError(f"Case with ID '{case.case_id}' already exists.") from err
        finally:
            conn.close()

    def get_case(self, case_id: str) -> Optional[Case]:
        """Retrieve a case by its unique Case ID."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM cases WHERE case_id = ?;", (case_id.strip(),)).fetchone()
            return self._row_to_case(row) if row else None
        finally:
            conn.close()

    def update_case(self, case_id: str, updates: Dict[str, Any]) -> Optional[Case]:
        """Update specific fields of an existing case."""
        existing = self.get_case(case_id)
        if not existing:
            return None

        allowed_fields = {
            "title", "case_type", "description", "location",
            "date_opened", "status", "priority", "assigned_investigator",
            "tags", "extra_metadata",
        }
        set_clauses = []
        params = []
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        for key, val in updates.items():
            if key in allowed_fields:
                if key in ("tags", "extra_metadata") and not isinstance(val, str):
                    val = json.dumps(val)
                elif key == "status":
                    val = str(val).upper().strip()
                elif key == "priority":
                    val = str(val).upper().strip()
                set_clauses.append(f"{key} = ?")
                params.append(val)

        if not set_clauses:
            return existing

        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(case_id.strip())

        query = f"UPDATE cases SET {', '.join(set_clauses)} WHERE case_id = ?;"
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(query, params)
            return self.get_case(case_id)
        finally:
            conn.close()

    def archive_case(self, case_id: str) -> bool:
        """Mark a case as ARCHIVED."""
        updated = self.update_case(case_id, {"status": CaseStatus.ARCHIVED.value})
        return updated is not None

    def delete_case(self, case_id: str) -> bool:
        """Permanently delete a case."""
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM cases WHERE case_id = ?;", (case_id.strip(),))
                return cursor.rowcount > 0
        finally:
            conn.close()

    def list_cases(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Case]:
        """List cases with optional status, priority, and keyword filtering."""
        query = "SELECT * FROM cases WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND UPPER(status) = ?"
            params.append(status.upper().strip())

        if priority:
            query += " AND UPPER(priority) = ?"
            params.append(priority.upper().strip())

        if search:
            s = f"%{search.strip().lower()}%"
            query += " AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(location) LIKE ? OR LOWER(case_id) LIKE ? OR LOWER(tags) LIKE ?)"
            params.extend([s, s, s, s, s])

        query += " ORDER BY updated_at DESC"

        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))
            if offset is not None:
                query += " OFFSET ?"
                params.append(int(offset))

        conn = self._get_conn()
        try:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_case(r) for r in rows]
        finally:
            conn.close()

    def count_cases(self) -> Dict[str, Any]:
        """Compute aggregate statistics on cases for dashboards."""
        conn = self._get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM cases;").fetchone()[0]
            status_rows = conn.execute("SELECT status, COUNT(*) FROM cases GROUP BY status;").fetchall()
            priority_rows = conn.execute("SELECT priority, COUNT(*) FROM cases GROUP BY priority;").fetchall()
            
            by_status = {row[0]: row[1] for row in status_rows}
            by_priority = {row[0]: row[1] for row in priority_rows}
            
            return {
                "total": total,
                "open": by_status.get("OPEN", 0),
                "under_review": by_status.get("UNDER_REVIEW", 0),
                "suspended": by_status.get("SUSPENDED", 0),
                "closed": by_status.get("CLOSED", 0),
                "archived": by_status.get("ARCHIVED", 0),
                "by_status": by_status,
                "by_priority": by_priority,
            }
        finally:
            conn.close()

    def export_cases_json(self, case_ids: Optional[List[str]] = None) -> str:
        """Export cases as a formatted JSON string with real stored data."""
        cases = self.list_cases()
        if case_ids:
            target_ids = set(case_ids)
            cases = [c for c in cases if c.case_id in target_ids]
        data = [c.to_dict() for c in cases]
        return json.dumps(data, indent=2, ensure_ascii=False)

    def export_cases_csv(self, case_ids: Optional[List[str]] = None) -> str:
        """Export cases as a standard CSV string with real stored data."""
        cases = self.list_cases()
        if case_ids:
            target_ids = set(case_ids)
            cases = [c for c in cases if c.case_id in target_ids]

        output = io.StringIO()
        fieldnames = [
            "case_id", "title", "case_type", "status", "priority",
            "location", "assigned_investigator", "date_opened",
            "tags", "created_at", "updated_at", "description",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for c in cases:
            d = c.to_dict()
            writer.writerow({
                "case_id": d["case_id"],
                "title": d["title"],
                "case_type": d["case_type"],
                "status": d["status"],
                "priority": d["priority"],
                "location": d["location"],
                "assigned_investigator": d["assigned_investigator"],
                "date_opened": d["date_opened"],
                "tags": ", ".join(d["tags"]) if isinstance(d["tags"], list) else str(d["tags"]),
                "created_at": d["created_at"],
                "updated_at": d["updated_at"],
                "description": d["description"],
            })
        return output.getvalue()


class SuspectRepository:
    """Repository handling all CRUD and query operations for Suspects."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def _row_to_suspect(self, row: sqlite3.Row) -> Suspect:
        d = dict(row)
        for list_col in ("traits", "case_connections", "evidence_links", "assessment_history"):
            if isinstance(d.get(list_col), str):
                try:
                    d[list_col] = json.loads(d[list_col])
                except Exception:
                    d[list_col] = []
        return Suspect.from_dict(d)

    def create_suspect(self, suspect: Suspect) -> Suspect:
        """Insert a new suspect record."""
        conn = self._get_conn()
        try:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            with conn:
                conn.execute("""
                    INSERT INTO suspects (
                        suspect_id, name, alias, age, location,
                        known_associations, observed_behaviors, modus_operandi,
                        traits, case_connections, notes, evidence_links,
                        assessment_history, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    suspect.suspect_id,
                    suspect.name,
                    suspect.alias or "Not provided",
                    suspect.age or "Not provided",
                    suspect.location or "Not provided",
                    suspect.known_associations or "Not provided",
                    suspect.observed_behaviors or "Not provided",
                    suspect.modus_operandi or "Not provided",
                    json.dumps(suspect.traits),
                    json.dumps(suspect.case_connections),
                    suspect.notes or "",
                    json.dumps(suspect.evidence_links),
                    json.dumps(suspect.assessment_history),
                    suspect.created_at or now,
                    now,
                ))
            return self.get_suspect(suspect.suspect_id) or suspect
        except sqlite3.IntegrityError as err:
            logger.error("Suspect ID %s already exists (%s)", suspect.suspect_id, err)
            raise ValueError(f"Suspect with ID '{suspect.suspect_id}' already exists.") from err
        finally:
            conn.close()

    def get_suspect(self, suspect_id: str) -> Optional[Suspect]:
        """Fetch suspect by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM suspects WHERE suspect_id = ?;", (suspect_id.strip(),)).fetchone()
            return self._row_to_suspect(row) if row else None
        finally:
            conn.close()

    def update_suspect(self, suspect_id: str, updates: Dict[str, Any]) -> Optional[Suspect]:
        """Update suspect fields."""
        existing = self.get_suspect(suspect_id)
        if not existing:
            return None

        allowed_fields = {
            "name", "alias", "age", "location", "known_associations",
            "observed_behaviors", "modus_operandi", "traits",
            "case_connections", "notes", "evidence_links", "assessment_history",
        }
        set_clauses = []
        params = []
        now = time.strftime("%Y-%m-%d %H:%M:%S")

        for key, val in updates.items():
            if key in allowed_fields:
                if key in ("traits", "case_connections", "evidence_links", "assessment_history") and not isinstance(val, str):
                    val = json.dumps(val)
                set_clauses.append(f"{key} = ?")
                params.append(val)

        if not set_clauses:
            return existing

        set_clauses.append("updated_at = ?")
        params.append(now)
        params.append(suspect_id.strip())

        query = f"UPDATE suspects SET {', '.join(set_clauses)} WHERE suspect_id = ?;"
        conn = self._get_conn()
        try:
            with conn:
                conn.execute(query, params)
            return self.get_suspect(suspect_id)
        finally:
            conn.close()

    def delete_suspect(self, suspect_id: str) -> bool:
        """Permanently delete a suspect."""
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM suspects WHERE suspect_id = ?;", (suspect_id.strip(),))
                return cursor.rowcount > 0
        finally:
            conn.close()

    def list_suspects(
        self,
        search: Optional[str] = None,
        case_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Suspect]:
        """List suspects with search filtering."""
        query = "SELECT * FROM suspects WHERE 1=1"
        params: List[Any] = []

        if search:
            s = f"%{search.strip().lower()}%"
            query += " AND (LOWER(name) LIKE ? OR LOWER(alias) LIKE ? OR LOWER(suspect_id) LIKE ? OR LOWER(observed_behaviors) LIKE ? OR LOWER(modus_operandi) LIKE ?)"
            params.extend([s, s, s, s, s])

        if case_id:
            query += " AND case_connections LIKE ?"
            params.append(f"%{case_id.strip()}%")

        query += " ORDER BY updated_at DESC"

        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))

        conn = self._get_conn()
        try:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_suspect(r) for r in rows]
        finally:
            conn.close()

    def add_assessment(self, suspect_id: str, assessment: Dict[str, Any]) -> Optional[Suspect]:
        """Append an AI model assessment to the suspect's assessment history."""
        suspect = self.get_suspect(suspect_id)
        if not suspect:
            return None
        history = list(suspect.assessment_history)
        history.append(assessment)
        return self.update_suspect(suspect_id, {"assessment_history": history})

    def count_suspects(self) -> int:
        conn = self._get_conn()
        try:
            return conn.execute("SELECT COUNT(*) FROM suspects;").fetchone()[0]
        finally:
            conn.close()


class EvidenceRepository:
    """Repository handling all CRUD and query operations for Evidence items."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def _row_to_evidence(self, row: sqlite3.Row) -> Evidence:
        d = dict(row)
        if isinstance(d.get("metadata"), str):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except Exception:
                d["metadata"] = {}
        return Evidence(
            evidence_id=d["evidence_id"],
            case_id=d["case_id"],
            file_type=d["file_type"],
            description=d.get("description", ""),
            source=d.get("source", "Field Officer"),
            uploaded_by=d.get("uploaded_by", "System"),
            timestamp=d.get("timestamp", ""),
            sha256_hash=d.get("sha256_hash", ""),
            file_size_bytes=d.get("file_size_bytes", 0),
            storage_path=d.get("storage_path", ""),
            status=d.get("status", "VERIFIED"),
            metadata=d.get("metadata", {}),
        )

    def create_evidence(self, ev: Evidence) -> Evidence:
        """Register a new evidence record."""
        conn = self._get_conn()
        try:
            meta_json = json.dumps(ev.metadata if isinstance(ev.metadata, dict) else {})
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            with conn:
                conn.execute("""
                    INSERT INTO evidence (
                        evidence_id, case_id, file_type, description,
                        source, uploaded_by, timestamp, sha256_hash,
                        file_size_bytes, storage_path, status, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    ev.evidence_id,
                    ev.case_id,
                    ev.file_type,
                    ev.description,
                    ev.source,
                    ev.uploaded_by,
                    ev.timestamp or now,
                    ev.sha256_hash,
                    ev.file_size_bytes,
                    ev.storage_path,
                    ev.status,
                    meta_json,
                ))
            return self.get_evidence(ev.evidence_id) or ev
        except sqlite3.IntegrityError as err:
            logger.error("Evidence ID %s already exists or foreign key violation (%s)", ev.evidence_id, err)
            raise ValueError(f"Evidence with ID '{ev.evidence_id}' already exists or Case '{ev.case_id}' does not exist.") from err
        finally:
            conn.close()

    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        """Retrieve evidence item by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM evidence WHERE evidence_id = ?;", (evidence_id.strip(),)).fetchone()
            return self._row_to_evidence(row) if row else None
        finally:
            conn.close()

    def get_by_hash(self, sha256_hash: str) -> Optional[Evidence]:
        """Find an evidence record matching an exact SHA-256 integrity hash."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM evidence WHERE sha256_hash = ?;", (sha256_hash.strip().lower(),)).fetchone()
            return self._row_to_evidence(row) if row else None
        finally:
            conn.close()

    def list_evidence(
        self,
        case_id: Optional[str] = None,
        file_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Evidence]:
        """List evidence records with optional case, type, or search filters."""
        query = "SELECT * FROM evidence WHERE 1=1"
        params: List[Any] = []

        if case_id:
            query += " AND case_id = ?"
            params.append(case_id.strip())

        if file_type:
            query += " AND LOWER(file_type) = ?"
            params.append(file_type.lower().strip())

        if search:
            s = f"%{search.strip().lower()}%"
            query += " AND (LOWER(description) LIKE ? OR LOWER(evidence_id) LIKE ? OR LOWER(source) LIKE ? OR LOWER(sha256_hash) LIKE ?)"
            params.extend([s, s, s, s])

        query += " ORDER BY timestamp DESC"

        conn = self._get_conn()
        try:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_evidence(r) for r in rows]
        finally:
            conn.close()

    def delete_evidence(self, evidence_id: str) -> bool:
        """Delete evidence record."""
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM evidence WHERE evidence_id = ?;", (evidence_id.strip(),))
                return cursor.rowcount > 0
        finally:
            conn.close()

    def count_evidence(self) -> Dict[str, Any]:
        """Return total and grouped evidence counts."""
        conn = self._get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM evidence;").fetchone()[0]
            type_rows = conn.execute("SELECT file_type, COUNT(*) FROM evidence GROUP BY file_type;").fetchall()
            return {
                "total": total,
                "by_type": {row[0]: row[1] for row in type_rows},
            }
        finally:
            conn.close()


class TimelineRepository:
    """Repository handling all operations for Case Timeline Events."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def _row_to_event(self, row: sqlite3.Row) -> TimelineEvent:
        d = dict(row)
        return TimelineEvent(
            event_id=d["event_id"],
            case_id=d["case_id"],
            timestamp=d["timestamp"],
            event_type=d["event_type"],
            description=d["description"],
            source=d.get("source", "Investigation Unit"),
            linked_evidence_id=d.get("linked_evidence_id"),
            created_at=d.get("created_at", ""),
        )

    def create_event(self, event: TimelineEvent) -> TimelineEvent:
        """Register a new verified timeline event."""
        conn = self._get_conn()
        try:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            with conn:
                conn.execute("""
                    INSERT INTO timeline_events (
                        event_id, case_id, timestamp, event_type,
                        description, source, linked_evidence_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    event.event_id,
                    event.case_id,
                    event.timestamp,
                    event.event_type,
                    event.description,
                    event.source,
                    event.linked_evidence_id,
                    event.created_at or now,
                ))
            return self.get_event(event.event_id) or event
        except sqlite3.IntegrityError as err:
            logger.error("Timeline event failed (%s): %s", event.event_id, err)
            raise ValueError(f"Timeline event '{event.event_id}' already exists or Case '{event.case_id}' does not exist.") from err
        finally:
            conn.close()

    def get_event(self, event_id: str) -> Optional[TimelineEvent]:
        """Fetch timeline event by ID."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM timeline_events WHERE event_id = ?;", (event_id.strip(),)).fetchone()
            return self._row_to_event(row) if row else None
        finally:
            conn.close()

    def list_events_for_case(self, case_id: str) -> List[TimelineEvent]:
        """Return all timeline events for a given case ordered chronologically."""
        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM timeline_events
                WHERE case_id = ?
                ORDER BY timestamp ASC, created_at ASC;
            """, (case_id.strip(),)).fetchall()
            return [self._row_to_event(r) for r in rows]
        finally:
            conn.close()

    def delete_event(self, event_id: str) -> bool:
        """Delete timeline event."""
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM timeline_events WHERE event_id = ?;", (event_id.strip(),))
                return cursor.rowcount > 0
        finally:
            conn.close()

    def count_events(self, case_id: Optional[str] = None) -> int:
        """Count events globally or for a case."""
        conn = self._get_conn()
        try:
            if case_id:
                return conn.execute("SELECT COUNT(*) FROM timeline_events WHERE case_id = ?;", (case_id.strip(),)).fetchone()[0]
            return conn.execute("SELECT COUNT(*) FROM timeline_events;").fetchone()[0]
        finally:
            conn.close()


class AuditRepository:
    """Repository handling immutable append-only operations for Audit Logs."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def _row_to_log(self, row: sqlite3.Row) -> AuditLog:
        d = dict(row)
        details_raw = d.get("details", {})
        if isinstance(details_raw, str):
            try:
                details = json.loads(details_raw)
            except Exception:
                details = {}
        else:
            details = details_raw or {}
        return AuditLog(
            log_id=d.get("log_id", ""),
            username=d.get("username", "system"),
            action=d.get("action", ""),
            timestamp=d.get("timestamp", ""),
            target_object=d.get("target_object", ""),
            result=d.get("result", "SUCCESS"),
            details=details,
        )

    def create_log(self, log: AuditLog) -> AuditLog:
        """Append an immutable audit log entry."""
        conn = self._get_conn()
        try:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            details_json = json.dumps(log.details if isinstance(log.details, dict) else {})
            with conn:
                conn.execute("""
                    INSERT INTO audit_logs (log_id, username, action, timestamp, target_object, result, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    log.log_id,
                    log.username,
                    log.action,
                    log.timestamp or now,
                    log.target_object,
                    log.result,
                    details_json,
                ))
            return log
        except sqlite3.IntegrityError as err:
            logger.error("Failed to append audit log %s: %s", log.log_id, err)
            raise ValueError(f"Audit log '{log.log_id}' already exists.") from err
        finally:
            conn.close()

    def list_logs(
        self,
        username: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[AuditLog]:
        """Fetch audit log records ordered from newest to oldest."""
        conn = self._get_conn()
        try:
            query = "SELECT * FROM audit_logs WHERE 1=1"
            params: List[Any] = []
            if username:
                query += " AND username = ?"
                params.append(username.strip())
            if action:
                query += " AND action = ?"
                params.append(action.strip())
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?;"
            params.extend([limit, offset])
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_log(r) for r in rows]
        finally:
            conn.close()

    def count_logs(self) -> int:
        """Total number of audit log entries recorded."""
        conn = self._get_conn()
        try:
            return conn.execute("SELECT COUNT(*) FROM audit_logs;").fetchone()[0]
        finally:
            conn.close()


class UserRepository:
    """Repository handling user credential and role storage."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def _row_to_user(self, row: sqlite3.Row) -> User:
        d = dict(row)
        return User(
            username=d.get("username", ""),
            password_hash=d.get("password_hash", ""),
            role=d.get("role", "INVESTIGATOR"),
            full_name=d.get("full_name", ""),
            email=d.get("email", ""),
            is_active=bool(d.get("is_active", 1)),
            created_at=d.get("created_at", ""),
        )

    def create_user(self, user: User) -> User:
        """Create a new user account."""
        conn = self._get_conn()
        try:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            with conn:
                conn.execute("""
                    INSERT INTO users (username, password_hash, role, full_name, email, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    user.username.strip().lower(),
                    user.password_hash,
                    user.role.upper().strip(),
                    user.full_name.strip(),
                    user.email.strip().lower(),
                    1 if user.is_active else 0,
                    user.created_at or now,
                ))
            return user
        except sqlite3.IntegrityError as err:
            logger.error("User creation failed for %s: %s", user.username, err)
            raise ValueError(f"User '{user.username}' already exists.") from err
        finally:
            conn.close()

    def get_user(self, username: str) -> Optional[User]:
        """Fetch user by username."""
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE username = ?;", (username.strip().lower(),)).fetchone()
            return self._row_to_user(row) if row else None
        finally:
            conn.close()

    def list_users(self) -> List[User]:
        """List all registered system users."""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM users ORDER BY username ASC;").fetchall()
            return [self._row_to_user(r) for r in rows]
        finally:
            conn.close()

    def update_user(self, username: str, updates: Dict[str, Any]) -> bool:
        """Update user record fields."""
        conn = self._get_conn()
        try:
            set_clauses = []
            params = []
            allowed = {"role", "full_name", "email", "is_active", "password_hash"}
            for k, v in updates.items():
                if k in allowed:
                    set_clauses.append(f"{k} = ?")
                    if k == "is_active":
                        params.append(1 if v else 0)
                    elif k == "role":
                        params.append(str(v).upper().strip())
                    else:
                        params.append(v)
            if not set_clauses:
                return False
            params.append(username.strip().lower())
            with conn:
                cursor = conn.execute(f"UPDATE users SET {', '.join(set_clauses)} WHERE username = ?;", params)
                return cursor.rowcount > 0
        finally:
            conn.close()

    def delete_user(self, username: str) -> bool:
        """Delete user account."""
        conn = self._get_conn()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM users WHERE username = ?;", (username.strip().lower(),))
                return cursor.rowcount > 0
        finally:
            conn.close()



