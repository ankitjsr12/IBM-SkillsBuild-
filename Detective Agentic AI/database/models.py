"""
database/models.py

Data models and type definitions for the Detective Agentic AI platform.
Supports serialization to/from dictionaries, JSON, and SQLite rows.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import time
from typing import Any, Dict, List, Optional


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class CasePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    INVESTIGATOR = "INVESTIGATOR"
    ANALYST = "ANALYST"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


@dataclass
class Case:
    case_id: str
    title: str
    case_type: str = "General Investigation"
    description: str = ""
    location: str = "Not provided"
    date_opened: str = field(default_factory=lambda: time.strftime("%Y-%m-%d"))
    status: str = CaseStatus.OPEN.value
    priority: str = CasePriority.MEDIUM.value
    assigned_investigator: str = "Unassigned"
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Case":
        tags_raw = data.get("tags", [])
        if isinstance(tags_raw, str):
            try:
                tags = json.loads(tags_raw)
            except Exception:
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        else:
            tags = list(tags_raw)

        meta_raw = data.get("extra_metadata", {})
        if isinstance(meta_raw, str):
            try:
                extra_metadata = json.loads(meta_raw)
            except Exception:
                extra_metadata = {}
        else:
            extra_metadata = dict(meta_raw) if isinstance(meta_raw, dict) else {}

        # Preserve legacy fields in extra_metadata if present
        for legacy_key in ("summary", "modus_operandi", "common_traits", "evidence", "suspects", "notes"):
            if legacy_key in data and legacy_key not in extra_metadata:
                extra_metadata[legacy_key] = data[legacy_key]

        return cls(
            case_id=str(data.get("case_id", "")).strip(),
            title=str(data.get("title") or data.get("case_title", "")).strip(),
            case_type=str(data.get("case_type") or data.get("crime_type", "General Investigation")).strip(),
            description=str(data.get("description") or data.get("summary", "")).strip(),
            location=str(data.get("location", "Not provided")).strip(),
            date_opened=str(data.get("date_opened") or time.strftime("%Y-%m-%d")).strip(),
            status=str(data.get("status", CaseStatus.OPEN.value)).upper().strip(),
            priority=str(data.get("priority", CasePriority.MEDIUM.value)).upper().strip(),
            assigned_investigator=str(data.get("assigned_investigator", "Unassigned")).strip(),
            tags=tags,
            created_at=str(data.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")).strip(),
            updated_at=str(data.get("updated_at") or time.strftime("%Y-%m-%d %H:%M:%S")).strip(),
            extra_metadata=extra_metadata,
        )


@dataclass
class Suspect:
    suspect_id: str
    name: str
    alias: str = "Not provided"
    age: str = "Not provided"
    location: str = "Not provided"
    known_associations: str = "Not provided"
    observed_behaviors: str = "Not provided"
    modus_operandi: str = "Not provided"
    traits: List[str] = field(default_factory=list)
    case_connections: List[str] = field(default_factory=list)
    notes: str = ""
    evidence_links: List[str] = field(default_factory=list)
    assessment_history: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Suspect":
        return cls(
            suspect_id=str(data.get("suspect_id", "")).strip(),
            name=str(data.get("name") or data.get("suspect_name", "Unnamed Suspect")).strip(),
            alias=str(data.get("alias", "Not provided")).strip(),
            age=str(data.get("age", "Not provided")).strip(),
            location=str(data.get("location", "Not provided")).strip(),
            known_associations=str(data.get("known_associations", "Not provided")).strip(),
            observed_behaviors=str(data.get("observed_behaviors") or data.get("behaviors", "Not provided")).strip(),
            modus_operandi=str(data.get("modus_operandi", "Not provided")).strip(),
            traits=list(data.get("traits", [])),
            case_connections=list(data.get("case_connections", [])),
            notes=str(data.get("notes", "")).strip(),
            evidence_links=list(data.get("evidence_links", [])),
            assessment_history=list(data.get("assessment_history", [])),
            created_at=str(data.get("created_at") or time.strftime("%Y-%m-%d %H:%M:%S")),
            updated_at=str(data.get("updated_at") or time.strftime("%Y-%m-%d %H:%M:%S")),
        )


@dataclass
class Evidence:
    evidence_id: str
    case_id: str
    file_type: str = "DOCUMENT"
    description: str = ""
    source: str = "Field Officer"
    uploaded_by: str = "Investigator"
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    sha256_hash: str = ""
    file_size_bytes: int = 0
    storage_path: str = ""
    status: str = "VERIFIED"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TimelineEvent:
    event_id: str
    case_id: str
    timestamp: str
    event_type: str
    description: str = ""
    source: str = "Investigation Unit"
    linked_evidence_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditLog:
    log_id: str
    username: str
    action: str
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))
    target_object: str = ""
    result: str = "SUCCESS"
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class User:
    username: str
    password_hash: str
    role: str = UserRole.INVESTIGATOR.value
    full_name: str = ""
    email: str = ""
    is_active: bool = True
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("password_hash", None)
        return d
