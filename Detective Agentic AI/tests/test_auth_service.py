"""
tests/test_auth_service.py

Unit tests for services/auth_service.py:
- PBKDF2 password hashing & verification
- User authentication (success & failure)
- Default user account auto-seeding
- Role-based permissions checks
"""

import pytest
from database.connection import init_db
from database.repository import UserRepository
from database.models import UserRole
from services.auth_service import AuthService, hash_password, verify_password


@pytest.fixture
def auth_svc(tmp_path):
    db_file = str(tmp_path / "test_auth.db")
    init_db(db_file)
    repo = UserRepository(db_path=db_file)
    return AuthService(user_repo=repo, db_path=db_file)


def test_password_hashing():
    pwd = "SecretPassphrase!123"
    h1 = hash_password(pwd)
    assert verify_password(pwd, h1) is True
    assert verify_password("WrongPassword", h1) is False
    assert h1 != hash_password(pwd)  # Different random salt


def test_default_accounts_seeded(auth_svc):
    users = auth_svc.list_all_users()
    usernames = [u.username for u in users]
    assert "admin" in usernames
    assert "investigator" in usernames
    assert "analyst" in usernames
    assert "viewer" in usernames


def test_authentication_flow(auth_svc):
    # Valid login
    success, msg, user = auth_svc.authenticate("admin", "Admin@123")
    assert success is True
    assert user is not None
    assert user.role == UserRole.ADMIN.value

    # Bad password
    success, msg, user = auth_svc.authenticate("admin", "WrongPass")
    assert success is False
    assert user is None

    # Unknown user
    success, msg, user = auth_svc.authenticate("ghost_user", "Pass123")
    assert success is False


def test_create_user_and_permissions(auth_svc):
    success, msg, created = auth_svc.create_user(
        actor_username="admin",
        new_username="detective_clara",
        new_password="PasswordClara123",
        role="INVESTIGATOR",
        full_name="Clara Watson",
    )
    assert success is True
    assert created.username == "detective_clara"

    # Permission checks
    assert AuthService.can_edit_case("INVESTIGATOR") is True
    assert AuthService.can_edit_case("VIEWER") is False
    assert AuthService.can_view_audit_trail("ADMIN") is True
    assert AuthService.can_view_audit_trail("INVESTIGATOR") is False
    assert AuthService.can_access_b2b_outreach("ADMIN") is True
    assert AuthService.can_access_b2b_outreach("ANALYST") is False
