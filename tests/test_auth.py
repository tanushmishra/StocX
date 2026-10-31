"""
Unit and Integration Tests for Stage 2: Supabase Auth & Multi-User Accounting.
"""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock, patch
import pytest

import config
from engine.auth_client import (
    _IN_MEMORY_PROFILES,
    _IN_MEMORY_RUNS,
    check_run_limit,
    get_daily_run_count,
    get_user_plan,
    record_run,
    sign_in_user,
    sign_up_user,
)


@pytest.fixture(autouse=True)
def reset_in_memory_state():
    """Reset in-memory runs and profiles before each test."""
    _IN_MEMORY_RUNS.clear()
    _IN_MEMORY_PROFILES.clear()
    yield
    _IN_MEMORY_RUNS.clear()
    _IN_MEMORY_PROFILES.clear()


class TestServiceRoleKeySecurity:
    """Security Gate: Ensure service role key is NEVER referenced in client code."""

    def test_service_role_key_never_in_client_or_ui_code(self):
        project_root = pathlib.Path(__file__).parent.parent
        checked_files = [
            project_root / "engine" / "auth_client.py",
            project_root / "ui" / "auth.py",
            project_root / "app.py",
            project_root / "config.py",
        ]
        for fpath in checked_files:
            if fpath.exists():
                content = fpath.read_text(encoding="utf-8")
                assert "SERVICE_ROLE_KEY" not in content, (
                    f"Forbidden SERVICE_ROLE_KEY reference found in client file {fpath.name}"
                )


class TestAuthenticationFlows:
    """Authentication behavior tests."""

    def test_sign_in_generic_error_on_invalid_credentials(self):
        result = sign_in_user("fake_user_test@example.com", "wrong_password_123")
        assert result["success"] is False
        # Must be generic, preventing account enumeration
        assert result["message"] == "Invalid email or password."

    def test_sign_in_empty_fields_rejected(self):
        result = sign_in_user("", "")
        assert result["success"] is False
        assert "required" in result["message"].lower()

    def test_sign_up_short_password_rejected(self):
        result = sign_up_user("test@example.com", "123")
        assert result["success"] is False
        assert "at least 6 characters" in result["message"]


class TestRunLimitsAndUserIsolation:
    """Plan limits and isolation tests."""

    def test_free_tier_enforces_three_runs_limit(self):
        user_id = "test-free-user-001"
        _IN_MEMORY_PROFILES[user_id] = "free"

        # Initially 0 runs used
        limits0 = check_run_limit(user_id, plan="free")
        assert limits0["allowed"] is True
        assert limits0["count"] == 0
        assert limits0["remaining"] == 3

        # Run 1
        record_run(user_id, "Thesis 1")
        limits1 = check_run_limit(user_id, plan="free")
        assert limits1["allowed"] is True
        assert limits1["count"] == 1
        assert limits1["remaining"] == 2

        # Run 2
        record_run(user_id, "Thesis 2")
        limits2 = check_run_limit(user_id, plan="free")
        assert limits2["allowed"] is True
        assert limits2["count"] == 2
        assert limits2["remaining"] == 1

        # Run 3
        record_run(user_id, "Thesis 3")
        limits3 = check_run_limit(user_id, plan="free")
        assert limits3["allowed"] is False
        assert limits3["count"] == 3
        assert limits3["remaining"] == 0
        assert "Daily run limit reached" in limits3["message"]

        # Run 4 blocked
        assert check_run_limit(user_id, plan="free")["allowed"] is False

    def test_premium_tier_unlimited_runs(self):
        user_id = "test-premium-user-001"
        _IN_MEMORY_PROFILES[user_id] = "premium"

        # Record 10 runs
        for i in range(10):
            record_run(user_id, f"Thesis {i}")

        limits = check_run_limit(user_id, plan="premium")
        assert limits["allowed"] is True
        assert limits["remaining"] == "unlimited"
        assert limits["limit"] == "unlimited"
        assert limits["count"] == 10

    def test_two_user_isolation(self):
        user_a = "user-alice-001"
        user_b = "user-bob-002"

        # User A performs 3 runs
        for i in range(3):
            record_run(user_a, f"Alice Thesis {i}")

        # User B performs 1 run
        record_run(user_b, "Bob Thesis 1")

        assert get_daily_run_count(user_a) == 3
        assert get_daily_run_count(user_b) == 1

        limits_a = check_run_limit(user_a, plan="free")
        limits_b = check_run_limit(user_b, plan="free")

        assert limits_a["allowed"] is False  # 3/3 used
        assert limits_b["allowed"] is True   # 1/3 used
        assert limits_b["remaining"] == 2
