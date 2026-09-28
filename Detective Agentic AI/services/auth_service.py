"""
services/auth_service.py

Authentication & Role-Based Access Control (RBAC) Service.
Manages user accounts, salted PBKDF2 password hashing, and role permissions.
Default roles supported:
  - SUPER_ADMIN
  - ADMIN
  - INVESTIGATOR
  - ANALYST
  - OPERATOR
  - VIEWER
"""

import hashlib
import logging
import os
import secrets
from typing import Any, Dict, List, Optional, Tuple
from database.connection import DEFAULT_DB_PATH
from database.models import User, UserRole
from database.repository import UserRepository
from services.audit_service import log_audit_event

logger = logging.getLogger(__name__)


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 iterations and salt."""
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
    )
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against salt$hash string."""
    try:
        parts = stored_hash.split("$")
        if len(parts) != 2:
            return False
        salt, _ = parts[0], parts[1]
        test_hash = hash_password(password, salt)
        return secrets.compare_digest(test_hash, stored_hash)
    except Exception:
        return False


class AuthService:
    """User authentication and Role-Based Access Control service."""

    def __init__(self, user_repo: Optional[UserRepository] = None, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.repo = user_repo or UserRepository(self.db_path)
        self._ensure_default_accounts()

    def _ensure_default_accounts(self) -> None:
        """Seed default operational accounts if no users exist."""
        try:
            existing = self.repo.list_users()
            if not existing:
                default_accounts = [
                    ("admin", "Admin@123", UserRole.ADMIN.value, "System Administrator", "admin@investigation.internal"),
                    ("investigator", "Investigator@123", UserRole.INVESTIGATOR.value, "Lead Det. Miller", "investigator@investigation.internal"),
                    ("analyst", "Analyst@123", UserRole.ANALYST.value, "Senior Case Analyst", "analyst@investigation.internal"),
                    ("viewer", "Viewer@123", UserRole.VIEWER.value, "Observer Account", "viewer@investigation.internal"),
                ]
                for uname, pwd, role, fname, email in default_accounts:
                    user = User(
                        username=uname,
                        password_hash=hash_password(pwd),
                        role=role,
                        full_name=fname,
                        email=email,
                        is_active=True,
                    )
                    self.repo.create_user(user)
                    log_audit_event(
                        username="system",
                        action="USER_PROVISION_DEFAULT",
                        target_object=uname,
                        result="SUCCESS",
                        details={"role": role},
                    )
                logger.info("Default RBAC accounts initialized successfully.")
        except Exception as err:
            logger.warning("Error seeding default accounts: %s", err)

    def authenticate(self, username: str, password: str) -> Tuple[bool, str, Optional[User]]:
        """
        Verify credentials.
        Returns: (success, message, user_object_without_password_hash)
        """
        user = self.repo.get_user(username)
        if not user:
            log_audit_event(
                username=username,
                action="LOGIN_FAILED",
                target_object=username,
                result="FAILURE",
                details={"reason": "User not found"},
            )
            return False, "Invalid username or password.", None

        if not user.is_active:
            log_audit_event(
                username=username,
                action="LOGIN_BLOCKED",
                target_object=username,
                result="FAILURE",
                details={"reason": "Account is deactivated"},
            )
            return False, "This account has been deactivated. Contact an administrator.", None

        if not verify_password(password, user.password_hash):
            log_audit_event(
                username=username,
                action="LOGIN_FAILED",
                target_object=username,
                result="FAILURE",
                details={"reason": "Invalid password"},
            )
            return False, "Invalid username or password.", None

        log_audit_event(
            username=user.username,
            action="LOGIN_SUCCESS",
            target_object=user.username,
            result="SUCCESS",
            details={"role": user.role},
        )
        return True, "Login successful.", user

    def create_user(
        self,
        actor_username: str,
        new_username: str,
        new_password: str,
        role: str,
        full_name: str = "",
        email: str = "",
    ) -> Tuple[bool, str, Optional[User]]:
        """Create a new user with verified role permissions."""
        if not new_username or len(new_username.strip()) < 3:
            return False, "Username must be at least 3 characters.", None
        if not new_password or len(new_password) < 6:
            return False, "Password must be at least 6 characters.", None

        valid_roles = [r.value for r in UserRole]
        if role.upper().strip() not in valid_roles:
            return False, f"Invalid role. Must be one of: {', '.join(valid_roles)}", None

        user = User(
            username=new_username.strip().lower(),
            password_hash=hash_password(new_password),
            role=role.upper().strip(),
            full_name=full_name.strip(),
            email=email.strip().lower(),
            is_active=True,
        )
        try:
            created = self.repo.create_user(user)
            log_audit_event(
                username=actor_username,
                action="USER_CREATED",
                target_object=created.username,
                result="SUCCESS",
                details={"role": created.role, "full_name": created.full_name},
            )
            return True, f"User '{created.username}' created successfully.", created
        except ValueError as err:
            return False, str(err), None

    def list_all_users(self) -> List[User]:
        """List all registered users."""
        return self.repo.list_users()

    def update_user_status(self, actor_username: str, target_username: str, is_active: bool) -> bool:
        """Activate or deactivate a user account."""
        success = self.repo.update_user(target_username, {"is_active": is_active})
        if success:
            log_audit_event(
                username=actor_username,
                action="USER_STATUS_UPDATED",
                target_object=target_username,
                result="SUCCESS",
                details={"is_active": is_active},
            )
        return success

    # --- Role Permission Gates ---
    @staticmethod
    def can_view_audit_trail(role: str) -> bool:
        return role.upper() in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value)

    @staticmethod
    def can_edit_case(role: str) -> bool:
        return role.upper() in (
            UserRole.SUPER_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.INVESTIGATOR.value,
        )

    @staticmethod
    def can_upload_evidence(role: str) -> bool:
        return role.upper() in (
            UserRole.SUPER_ADMIN.value,
            UserRole.ADMIN.value,
            UserRole.INVESTIGATOR.value,
            UserRole.OPERATOR.value,
        )

    @staticmethod
    def can_delete_records(role: str) -> bool:
        return role.upper() in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value)

    @staticmethod
    def can_manage_users(role: str) -> bool:
        return role.upper() in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value)

    @staticmethod
    def can_access_b2b_outreach(role: str) -> bool:
        return role.upper() in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value)
