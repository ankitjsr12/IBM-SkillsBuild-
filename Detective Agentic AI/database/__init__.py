"""
database package for Detective Agentic AI.
Provides relational persistence (SQLite), models, repository layer, and migration helpers.
"""

from database.models import (
    Case,
    CaseStatus,
    CasePriority,
    Suspect,
    Evidence,
    TimelineEvent,
    AuditLog,
    User,
    UserRole,
)
from database.connection import get_db_connection, init_db, migrate_existing_cases
from database.repository import CaseRepository, SuspectRepository, EvidenceRepository, TimelineRepository

__all__ = [
    "Case",
    "CaseStatus",
    "CasePriority",
    "Suspect",
    "Evidence",
    "TimelineEvent",
    "AuditLog",
    "User",
    "UserRole",
    "get_db_connection",
    "init_db",
    "migrate_existing_cases",
    "CaseRepository",
    "SuspectRepository",
    "EvidenceRepository",
    "TimelineRepository",
]
