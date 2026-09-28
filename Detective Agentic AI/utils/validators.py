"""
utils/validators.py

Input validation and sanitization routines for the Detective Agentic AI platform.
Ensures strong typing, bounds checking, and security boundary enforcement.
"""

import re
from typing import Tuple, Optional, Set

# Allowed file extensions for evidence & case documents
ALLOWED_EVIDENCE_EXTENSIONS: Set[str] = {
    "pdf", "txt", "csv", "json", "docx",
    "png", "jpg", "jpeg", "webp",
    "mp4", "mp3", "wav",
}

# Max file size: 25 MB default
MAX_EVIDENCE_FILE_SIZE_BYTES = 25 * 1024 * 1024

# ID patterns
CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{3,64}$")
SUSPECT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{3,64}$")
EVIDENCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{3,64}$")
EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
UTR_PATTERN = re.compile(r"^\d{12}$")


def validate_case_id(case_id: str) -> Tuple[bool, str]:
    """Validate that a Case ID is non-empty, alphanumeric, and of valid length."""
    if not case_id or not isinstance(case_id, str):
        return False, "Case ID must be a non-empty string."
    cid = case_id.strip()
    if not CASE_ID_PATTERN.match(cid):
        return False, "Case ID must be 3-64 characters alphanumeric, dashes, or underscores."
    return True, cid


def validate_suspect_id(suspect_id: str) -> Tuple[bool, str]:
    """Validate suspect ID format."""
    if not suspect_id or not isinstance(suspect_id, str):
        return False, "Suspect ID must be a non-empty string."
    sid = suspect_id.strip()
    if not SUSPECT_ID_PATTERN.match(sid):
        return False, "Suspect ID must be 3-64 characters alphanumeric, dashes, or underscores."
    return True, sid


def validate_evidence_id(evidence_id: str) -> Tuple[bool, str]:
    """Validate evidence ID format."""
    if not evidence_id or not isinstance(evidence_id, str):
        return False, "Evidence ID must be a non-empty string."
    eid = evidence_id.strip()
    if not EVIDENCE_ID_PATTERN.match(eid):
        return False, "Evidence ID must be 3-64 characters alphanumeric, dashes, or underscores."
    return True, eid


def validate_email_address(email: str) -> Tuple[bool, str]:
    """Validate standard email address syntax."""
    if not email or not isinstance(email, str):
        return False, "Email address is required."
    clean_email = email.strip()
    if not EMAIL_PATTERN.match(clean_email):
        return False, "Invalid email address format."
    return True, clean_email


def validate_utr(utr: str) -> Tuple[bool, str]:
    """Validate Indian standard 12-digit UPI UTR / RRN."""
    if not utr or not isinstance(utr, str):
        return False, "UTR number is required."
    clean_utr = utr.strip()
    if not UTR_PATTERN.match(clean_utr):
        return False, "UTR must be strictly 12 numerical digits."
    return True, clean_utr


def validate_file_size(size_bytes: int, max_bytes: int = MAX_EVIDENCE_FILE_SIZE_BYTES) -> Tuple[bool, str]:
    """Verify file does not exceed maximum allowable payload size."""
    if size_bytes <= 0:
        return False, "File is empty (0 bytes)."
    if size_bytes > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        return False, f"File size exceeds the maximum allowed limit of {max_mb:.1f} MB."
    return True, "File size is acceptable."


def validate_allowed_file_type(filename: str, allowed_exts: Set[str] = ALLOWED_EVIDENCE_EXTENSIONS) -> Tuple[bool, str]:
    """Check file extension against permitted investigative file formats."""
    if not filename or "." not in filename:
        return False, "Filename must include a valid extension."
    ext = filename.rsplit(".", 1)[-1].lower().strip()
    if ext not in allowed_exts:
        return False, f"Unsupported file type (.{ext}). Supported types: {', '.join(sorted(allowed_exts))}."
    return True, ext
