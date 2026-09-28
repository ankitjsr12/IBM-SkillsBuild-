"""
services/audit_service.py

Audit Trail Service.
Provides immutable, structured audit logging across authentication, case management,
evidence custody, RAG queries, AI profiling evaluations, and billing transactions.
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from database.connection import DEFAULT_DB_PATH
from database.models import AuditLog
from database.repository import AuditRepository

logger = logging.getLogger(__name__)


class AuditService:
    """Service for recording and querying the immutable audit log."""

    def __init__(self, audit_repo: Optional[AuditRepository] = None, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.repo = audit_repo or AuditRepository(self.db_path)

    def log(
        self,
        username: str,
        action: str,
        target_object: str = "",
        result: str = "SUCCESS",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Record an immutable audit log entry.
        Guaranteed not to raise an exception to the caller.
        """
        log_id = f"AUD-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        entry = AuditLog(
            log_id=log_id,
            username=username or "system",
            action=action.upper().strip(),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            target_object=target_object or "",
            result=result.upper().strip(),
            details=details or {},
        )
        try:
            return self.repo.create_log(entry)
        except Exception as err:
            logger.error("Failed to persist audit log entry %s: %s", log_id, err)
            return entry

    def query_logs(
        self,
        username: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> List[AuditLog]:
        """Fetch audit records with optional filters."""
        return self.repo.list_logs(username=username, action=action, limit=limit, offset=offset)

    def get_total_count(self) -> int:
        """Return total number of recorded audit logs."""
        return self.repo.count_logs()


# Global singleton instance
_audit_service_instance: Optional[AuditService] = None


def get_audit_service() -> AuditService:
    global _audit_service_instance
    if _audit_service_instance is None:
        _audit_service_instance = AuditService()
    return _audit_service_instance


def log_audit_event(
    username: str,
    action: str,
    target_object: str = "",
    result: str = "SUCCESS",
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Helper function to record an audit log event easily."""
    return get_audit_service().log(
        username=username,
        action=action,
        target_object=target_object,
        result=result,
        details=details,
    )
