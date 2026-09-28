"""
agent/evidence_engine.py

Evidence Management Business Logic Engine.
Handles multi-format evidence ingestion, SHA-256 integrity hash calculation,
duplicate detection, file storage, and metadata indexing.
"""

import hashlib
import json
import logging
import os
import re
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

from database.models import Evidence
from database.repository import EvidenceRepository, CaseRepository
from utils.validators import (
    validate_evidence_id,
    validate_allowed_file_type,
    validate_file_size,
    ALLOWED_EVIDENCE_EXTENSIONS,
)
from agent.document_engine import DocumentEngine
from services.audit_service import log_audit_event

logger = logging.getLogger(__name__)

EVIDENCE_STORAGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "evidence")
)


class EvidenceEngine:
    """Coordinates evidence ingestion, SHA-256 cryptographic verification, and retrieval."""

    def __init__(
        self,
        repository: Optional[EvidenceRepository] = None,
        case_repo: Optional[CaseRepository] = None,
        storage_dir: Optional[str] = None,
    ):
        self.repo = repository or EvidenceRepository()
        self.case_repo = case_repo or CaseRepository()
        self.storage_dir = storage_dir or EVIDENCE_STORAGE_DIR

    def generate_unique_evidence_id(self, prefix: str = "EV") -> str:
        """Generate a random collision-free Evidence ID."""
        year = time.strftime("%Y")
        for _ in range(10):
            token = secrets.token_hex(3).upper()
            candidate = f"{prefix}-{year}-{token}"
            if not self.repo.get_evidence(candidate):
                return candidate
        return f"{prefix}-{year}-{int(time.time() * 1000) % 1000000}"

    @staticmethod
    def calculate_sha256(data: bytes) -> str:
        """Calculate SHA-256 cryptographic hash of byte payload."""
        return hashlib.sha256(data).hexdigest()

    def ingest_evidence(
        self,
        case_id: str,
        filename: str,
        file_bytes: bytes,
        description: str = "",
        source: str = "Field Officer",
        uploaded_by: str = "Authorized Investigator",
        evidence_id: Optional[str] = None,
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str, Optional[Evidence]]:
        """
        Validate, hash, check for duplicate collision, store file, and index evidence.
        """
        clean_cid = str(case_id or "").strip()
        if not clean_cid:
            return False, "A valid Case ID is required to attach evidence.", None

        # Verify case exists
        case = self.case_repo.get_case(clean_cid)
        if not case:
            return False, f"Target case '{clean_cid}' does not exist in the database.", None

        # File validation
        size_bytes = len(file_bytes)
        size_ok, size_msg = validate_file_size(size_bytes)
        if not size_ok:
            return False, size_msg, None

        type_ok, ext_or_err = validate_allowed_file_type(filename)
        if not type_ok:
            return False, ext_or_err, None
        file_type = ext_or_err.upper()

        # 1. Calculate SHA-256 integrity hash
        sha256_hash = self.calculate_sha256(file_bytes)

        # 2. Prevent accidental duplicate uploads using file hashes
        existing_duplicate = self.repo.get_by_hash(sha256_hash)
        if existing_duplicate:
            return (
                False,
                f"Duplicate evidence rejected: An identical file was already registered as "
                f"Evidence '{existing_duplicate.evidence_id}' under Case '{existing_duplicate.case_id}' "
                f"(SHA-256: {sha256_hash[:16]}...).",
                existing_duplicate,
            )

        # 3. Evidence ID resolution
        if evidence_id and evidence_id.strip():
            eid = evidence_id.strip()
            v_ok, v_msg = validate_evidence_id(eid)
            if not v_ok:
                return False, f"Invalid Evidence ID: {v_msg}", None
            if self.repo.get_evidence(eid):
                return False, f"Evidence with ID '{eid}' already exists.", None
        else:
            eid = self.generate_unique_evidence_id()

        # 4. Save file to disk safely
        safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
        case_evidence_dir = os.path.join(self.storage_dir, clean_cid)
        os.makedirs(case_evidence_dir, exist_ok=True)
        stored_file_path = os.path.join(case_evidence_dir, f"{eid}_{safe_name}")

        try:
            with open(stored_file_path, "wb") as f:
                f.write(file_bytes)
        except Exception as io_err:
            logger.error("Failed to write evidence file to disk: %s", io_err)
            return False, f"Storage failure saving evidence file: {io_err}", None

        # 5. Extract document text, entities, and metadata
        try:
            doc_info = DocumentEngine.extract_text_from_bytes(file_bytes, filename)
            meta = custom_metadata or {}
            meta["original_filename"] = filename
            meta["file_size_human"] = self._format_size(size_bytes)
            if doc_info.get("text"):
                meta["extracted_text"] = doc_info["text"][:5000]  # Cap preview at 5000 chars
            if doc_info.get("entities"):
                meta["entities"] = doc_info["entities"]
            if doc_info.get("metadata"):
                meta.update(doc_info["metadata"])
        except Exception as doc_err:
            logger.warning("Document text extraction warning: %s", doc_err)
            meta = custom_metadata or {}
            meta["original_filename"] = filename
            meta["file_size_human"] = self._format_size(size_bytes)

        evidence_obj = Evidence(
            evidence_id=eid,
            case_id=clean_cid,
            file_type=file_type,
            description=str(description or "").strip(),
            source=str(source or "Field Officer").strip(),
            uploaded_by=str(uploaded_by or "Authorized Investigator").strip(),
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            sha256_hash=sha256_hash,
            file_size_bytes=size_bytes,
            storage_path=stored_file_path,
            status="VERIFIED",
            metadata=meta,
        )

        try:
            created = self.repo.create_evidence(evidence_obj)
            log_audit_event(
                username=evidence_obj.uploaded_by,
                action="EVIDENCE_INGESTED",
                target_object=eid,
                result="SUCCESS",
                details={
                    "case_id": clean_cid,
                    "file_type": file_type,
                    "sha256": sha256_hash,
                    "size_bytes": size_bytes,
                },
            )
            return True, f"Evidence '{eid}' successfully registered with SHA-256 integrity hash.", created
        except Exception as exc:
            logger.error("Failed to insert evidence record into database: %s", exc)
            return False, f"Database error indexing evidence: {exc}", None

    def get_evidence(self, evidence_id: str) -> Optional[Evidence]:
        """Retrieve evidence item by ID."""
        if not evidence_id:
            return None
        return self.repo.get_evidence(evidence_id.strip())

    def list_evidence(
        self,
        case_id: Optional[str] = None,
        file_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Evidence]:
        """List evidence records with filters."""
        return self.repo.list_evidence(case_id=case_id, file_type=file_type, search=search)

    def delete_evidence(self, evidence_id: str) -> Tuple[bool, str]:
        """Delete evidence item and its stored file payload."""
        if not evidence_id:
            return False, "Evidence ID is required."
        ev = self.repo.get_evidence(evidence_id.strip())
        if not ev:
            return False, f"Evidence '{evidence_id}' not found."

        # Remove physical file if exists
        if ev.storage_path and os.path.isfile(ev.storage_path):
            try:
                os.remove(ev.storage_path)
            except Exception as e:
                logger.warning("Could not delete file %s: %s", ev.storage_path, e)

        success = self.repo.delete_evidence(evidence_id.strip())
        if success:
            return True, f"Evidence '{evidence_id}' deleted."
        return False, f"Failed to delete evidence '{evidence_id}'."

    def get_statistics(self) -> Dict[str, Any]:
        """Return aggregate evidence counts."""
        return self.repo.count_evidence()

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format bytes into a human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"
