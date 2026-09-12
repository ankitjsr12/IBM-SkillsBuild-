"""
tests/test_outreach.py

Tests for agent/outreach.py — lead persistence, duplicate detection,
email validation, and save/load operations.
"""
import os
import json
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import agent.outreach as outreach_module
from agent.outreach import load_leads, save_leads, _validate_email, _normalise_key


@pytest.fixture(autouse=True)
def isolated_leads_file(tmp_path):
    """Redirect LEADS_FILE to a temporary path for test isolation."""
    tmp_file = str(tmp_path / "leads.json")
    original = outreach_module.LEADS_FILE
    outreach_module.LEADS_FILE = tmp_file
    yield tmp_file
    outreach_module.LEADS_FILE = original


# ------------------------------------------------------------------ #
# Lead Persistence
# ------------------------------------------------------------------ #

class TestLeadPersistence:
    def test_load_returns_empty_list_when_no_file(self, tmp_path):
        result = load_leads()
        assert result == []

    def test_save_and_load_roundtrip(self):
        leads = [{"agency_name": "Test Agency", "location": "Delhi", "contact_email": "test@test.com"}]
        save_leads(leads)
        loaded = load_leads()
        assert loaded == leads

    def test_save_and_load_empty_list(self):
        save_leads([])
        assert load_leads() == []

    def test_load_returns_empty_on_corrupt_file(self, tmp_path):
        # Write invalid JSON to the leads file
        with open(outreach_module.LEADS_FILE, "w") as f:
            f.write("NOT VALID JSON")
        result = load_leads()
        assert result == []


# ------------------------------------------------------------------ #
# Email Validation
# ------------------------------------------------------------------ #

class TestEmailValidation:
    def test_valid_email(self):
        assert _validate_email("info@example.com") is True

    def test_valid_gmail(self):
        assert _validate_email("test.user+tag@gmail.com") is True

    def test_missing_at(self):
        assert _validate_email("notanemail.com") is False

    def test_missing_domain(self):
        assert _validate_email("user@") is False

    def test_empty_string(self):
        assert _validate_email("") is False

    def test_spaces(self):
        assert _validate_email("user @example.com") is False

    def test_multiple_at_signs(self):
        assert _validate_email("a@b@c.com") is False


# ------------------------------------------------------------------ #
# Duplicate detection in scrape_leads_sync
# ------------------------------------------------------------------ #

class TestScrapeLeadsDuplicateDetection:
    def test_existing_lead_not_duplicated(self, monkeypatch):
        """If a lead already exists in storage, scrape_leads_sync should not add it again."""
        existing = [{
            "agency_name": "Test Detective Agency",
            "location": "Delhi",
            "contact_email": "",
            "website": "",
            "phone": "",
            "source": "OpenStreetMap",
            "status": "Prospect",
            "confidence": 90,
            "profession": "Private Detective",
        }]
        save_leads(existing)

        # Return the same lead from the mocked source engines
        def mock_overpass(keyword, location, max_results):
            return [{
                "agency_name": "Test Detective Agency",
                "location": "Delhi",
                "contact_email": "",
                "website": "",
                "phone": "",
                "source": "OpenStreetMap",
                "status": "Prospect",
            }]

        monkeypatch.setattr(outreach_module, "_overpass_search", mock_overpass)
        monkeypatch.setattr(outreach_module, "_duckduckgo_search", lambda *a, **kw: [])
        monkeypatch.setattr(outreach_module, "_wikipedia_search", lambda *a, **kw: [])

        outreach_module.scrape_leads_sync("Detective", "Delhi", max_results=5)
        # Regardless of what was returned, the stored leads must not contain a duplicate
        all_leads = load_leads()
        names = [l["agency_name"] for l in all_leads]
        # The agency name should appear exactly once in storage
        assert names.count("Test Detective Agency") == 1


# ------------------------------------------------------------------ #
# send_cold_emails — no password
# ------------------------------------------------------------------ #

class TestSendColdEmailsValidation:
    def test_empty_leads_returns_empty(self):
        result = outreach_module.send_cold_emails([], "some_password")
        assert result == []

    def test_no_password_returns_init_fail(self):
        leads = [{"agency_name": "Test", "contact_email": "t@t.com", "location": "Delhi"}]
        result = outreach_module.send_cold_emails(leads, "")
        assert len(result) == 1
        assert result[0]["status"] == "INIT_FAIL"

    def test_lead_without_email_is_skipped(self, monkeypatch):
        """A lead with no email must be SKIPPED, not cause an exception."""
        # Simulate yagmail being importable but failing on SMTP (to avoid real connection)
        class MockYag:
            def __init__(self, *a, **kw): pass
            def send(self, **kw): pass
            def close(self): pass

        import types
        mock_yagmail = types.ModuleType("yagmail")
        mock_yagmail.SMTP = MockYag
        monkeypatch.setitem(sys.modules, "yagmail", mock_yagmail)

        leads = [{"agency_name": "No Email Agency", "contact_email": "", "location": "Delhi"}]
        result = outreach_module.send_cold_emails(leads, "fake_password_16chars")
        assert result[0]["status"] == "SKIPPED"
