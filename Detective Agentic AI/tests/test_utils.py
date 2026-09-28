"""
tests/test_utils.py

Unit tests for text_utils, validators, and logging_utils.
"""

import pytest
from utils.text_utils import sanitize_for_pdf, wrap_unbroken_tokens, strip_markdown, truncate_text
from utils.validators import (
    validate_case_id,
    validate_suspect_id,
    validate_evidence_id,
    validate_email_address,
    validate_utr,
    validate_file_size,
    validate_allowed_file_type,
)


def test_sanitize_for_pdf_unicode():
    # Rupee, em-dash, bullets, quotes
    raw = "Cost: ₹5000 — Suspect “John” • bullet"
    cleaned = sanitize_for_pdf(raw)
    assert "Rs.5000" in cleaned
    assert "--" in cleaned
    assert '"John"' in cleaned
    assert "*" in cleaned
    # Ensure it encodes cleanly to latin-1
    cleaned.encode("latin-1")


def test_wrap_unbroken_tokens():
    long_hash = "a" * 160
    wrapped = wrap_unbroken_tokens(long_hash, max_token_len=70)
    for part in wrapped.split(" "):
        assert len(part) <= 70


def test_strip_markdown():
    text = "This is **bold**, *italic*, and `code`."
    stripped = strip_markdown(text)
    assert "**" not in stripped
    assert "`" not in stripped
    assert "bold" in stripped


def test_truncate_text():
    text = "A quick brown fox jumps over the lazy dog"
    truncated = truncate_text(text, max_chars=20)
    assert len(truncated) <= 20
    assert truncated.endswith("...")


def test_validate_case_id():
    ok, cid = validate_case_id("CASE_2026-001")
    assert ok
    assert cid == "CASE_2026-001"

    ok, err = validate_case_id("bad id with spaces!")
    assert not ok


def test_validate_utr():
    ok, utr = validate_utr("123456789012")
    assert ok
    assert utr == "123456789012"

    ok, err = validate_utr("12345")
    assert not ok
    ok, err = validate_utr("12345678901a")
    assert not ok


def test_validate_email_address():
    ok, email = validate_email_address("agent@investigation.gov")
    assert ok
    assert email == "agent@investigation.gov"

    ok, err = validate_email_address("invalid-email")
    assert not ok


def test_validate_file_size_and_type():
    ok, ext = validate_allowed_file_type("evidence.pdf")
    assert ok
    assert ext == "pdf"

    ok, err = validate_allowed_file_type("malicious.exe")
    assert not ok

    ok, _ = validate_file_size(1024)
    assert ok
    ok, _ = validate_file_size(30 * 1024 * 1024)  # 30 MB > 25 MB limit
    assert not ok
