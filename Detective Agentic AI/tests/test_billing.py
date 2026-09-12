"""
tests/test_billing.py

Tests for agent/billing.py — UTR validation, payment submission,
duplicate prevention, approval/rejection, and status states.
"""
import os
import json
import tempfile
import sys

# Allow imports from the project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

# Redirect PAYMENTS_FILE to a temp file for all tests
import agent.billing as billing_module


@pytest.fixture(autouse=True)
def isolated_payments_file(tmp_path):
    """Redirect PAYMENTS_FILE to a temporary file for test isolation."""
    tmp_file = str(tmp_path / "payments.json")
    original = billing_module.PAYMENTS_FILE
    billing_module.PAYMENTS_FILE = tmp_file
    yield tmp_file
    billing_module.PAYMENTS_FILE = original


# ------------------------------------------------------------------ #
# UTR Format Validation
# ------------------------------------------------------------------ #

class TestValidateUtr:
    def test_valid_12_digit_utr(self):
        assert billing_module.validate_utr_format("426789012345") is True

    def test_too_short(self):
        assert billing_module.validate_utr_format("12345") is False

    def test_too_long(self):
        assert billing_module.validate_utr_format("4267890123456789") is False

    def test_contains_letters(self):
        assert billing_module.validate_utr_format("42678ABC2345") is False

    def test_empty_string(self):
        assert billing_module.validate_utr_format("") is False

    def test_with_spaces(self):
        assert billing_module.validate_utr_format(" 426789012345 ") is True  # strip is applied


# ------------------------------------------------------------------ #
# Payment Submission
# ------------------------------------------------------------------ #

class TestSubmitPayment:
    VALID_UTR = "111122223333"
    PLAN = "Pro Agency"
    REQUIRED = 1000.0
    EVALS = 500

    def test_invalid_utr_format(self):
        status, msg, remaining = billing_module.submit_payment(
            self.PLAN, self.REQUIRED, self.REQUIRED, self.EVALS, "short"
        )
        assert status == billing_module.STATUS_INVALID_UTR
        assert remaining == self.REQUIRED

    def test_full_payment_creates_pending(self):
        status, msg, remaining = billing_module.submit_payment(
            self.PLAN, self.REQUIRED, self.REQUIRED, self.EVALS, self.VALID_UTR
        )
        assert status == billing_module.STATUS_PENDING
        assert remaining == 0.0

    def test_partial_payment_creates_partial(self):
        status, msg, remaining = billing_module.submit_payment(
            self.PLAN, self.REQUIRED, 500.0, self.EVALS, self.VALID_UTR
        )
        assert status == billing_module.STATUS_PARTIAL
        assert remaining == 500.0

    def test_duplicate_utr_rejected(self):
        billing_module.submit_payment(
            self.PLAN, self.REQUIRED, self.REQUIRED, self.EVALS, self.VALID_UTR
        )
        status, msg, _ = billing_module.submit_payment(
            self.PLAN, self.REQUIRED, self.REQUIRED, self.EVALS, self.VALID_UTR
        )
        assert status == billing_module.STATUS_FLAGGED
        assert "already been submitted" in msg

    def test_zero_amount_rejected(self):
        status, msg, _ = billing_module.submit_payment(
            self.PLAN, self.REQUIRED, 0.0, self.EVALS, self.VALID_UTR
        )
        assert status == billing_module.STATUS_FLAGGED

    def test_negative_amount_rejected(self):
        status, msg, _ = billing_module.submit_payment(
            self.PLAN, self.REQUIRED, -500.0, self.EVALS, self.VALID_UTR
        )
        assert status == billing_module.STATUS_FLAGGED


# ------------------------------------------------------------------ #
# Payment Approval / Rejection
# ------------------------------------------------------------------ #

class TestApproveRejectPayment:
    VALID_UTR = "999988887777"
    PLAN = "Enterprise SaaS"
    REQUIRED = 2000.0
    EVALS = "Unlimited"

    def _submit(self):
        billing_module.submit_payment(
            self.PLAN, self.REQUIRED, self.REQUIRED, self.EVALS, self.VALID_UTR
        )

    def test_approve_sets_status_approved(self):
        self._submit()
        result = billing_module.approve_payment(self.VALID_UTR)
        assert result is True
        payments = billing_module.load_payments()
        pmt = next(p for p in payments if p["utr"] == self.VALID_UTR)
        assert pmt["status"] == billing_module.STATUS_APPROVED

    def test_reject_sets_status_rejected(self):
        self._submit()
        result = billing_module.reject_payment(self.VALID_UTR, "Not found in bank records.")
        assert result is True
        payments = billing_module.load_payments()
        pmt = next(p for p in payments if p["utr"] == self.VALID_UTR)
        assert pmt["status"] == billing_module.STATUS_REJECTED

    def test_approve_nonexistent_utr_returns_false(self):
        assert billing_module.approve_payment("000000000000") is False

    def test_reject_nonexistent_utr_returns_false(self):
        assert billing_module.reject_payment("000000000000") is False


# ------------------------------------------------------------------ #
# get_pending_payments — Only PENDING / PARTIAL / TOPUP_DONE
# ------------------------------------------------------------------ #

class TestGetPendingPayments:
    def test_approved_not_in_pending(self):
        billing_module.submit_payment("Plan", 500.0, 500.0, 100, "111111111111")
        billing_module.approve_payment("111111111111")
        pending = billing_module.get_pending_payments()
        utrs = [p["utr"] for p in pending]
        assert "111111111111" not in utrs

    def test_rejected_not_in_pending(self):
        billing_module.submit_payment("Plan", 500.0, 500.0, 100, "222222222222")
        billing_module.reject_payment("222222222222")
        pending = billing_module.get_pending_payments()
        utrs = [p["utr"] for p in pending]
        assert "222222222222" not in utrs

    def test_pending_included(self):
        billing_module.submit_payment("Plan", 500.0, 500.0, 100, "333333333333")
        pending = billing_module.get_pending_payments()
        utrs = [p["utr"] for p in pending]
        assert "333333333333" in utrs
