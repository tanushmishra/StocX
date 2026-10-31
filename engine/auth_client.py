"""
Authentication and User Session Management for Market-Neutral Hedge Builder.
Stage 2: Supabase Auth integration, session management, and run limits.

Security principles:
- Uses ONLY Supabase Anon Key and user JWT tokens.
- NEVER reads or uses service-role administrative credentials.
- Generic error messages for sign-in to prevent account enumeration.
- Enforces Row Level Security (RLS) context via user access tokens.
- Enforces free tier daily run limit (default 3 runs/day).
"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from supabase import Client, create_client

import config

logger = logging.getLogger(__name__)

# Fallback store for session runs if remote table migrations have not been run in Supabase SQL editor
_IN_MEMORY_RUNS: list[dict[str, Any]] = []
_IN_MEMORY_PROFILES: dict[str, str] = {}  # user_id -> plan ('free' | 'premium')


def get_supabase_client(access_token: str | None = None) -> Client | None:
    """
    Initialize a Supabase client using SUPABASE_URL and SUPABASE_ANON_KEY.
    Optionally sets the postgrest auth token to the user's JWT.
    """
    if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
        logger.warning("Supabase credentials not fully configured.")
        return None

    try:
        client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        if access_token:
            client.postgrest.auth(access_token)
        return client
    except Exception as exc:
        logger.error(f"Failed to initialize Supabase client: {exc}")
        return None


def sign_in_user(email: str, password: str) -> dict[str, Any]:
    """
    Authenticate user with email and password via Supabase Auth.
    Returns standard auth payload with generic failure messages.
    """
    if not email or not password:
        return {"success": False, "message": "Email and password are required."}

    client = get_supabase_client()
    if client is None:
        # Fallback offline demo login for resilience
        if email.endswith("@hedgebuilder.test") or email == "demo@hedgebuilder.test":
            user_id = f"demo-{abs(hash(email)) % 100000}"
            return {
                "success": True,
                "user_id": user_id,
                "email": email,
                "access_token": f"mock-token-{user_id}",
                "plan": _IN_MEMORY_PROFILES.get(user_id, "free"),
            }
        return {"success": False, "message": "Authentication service unavailable."}

    try:
        res = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
        if res and res.user and res.session:
            user_id = str(res.user.id)
            token = res.session.access_token
            plan = get_user_plan(user_id, access_token=token)
            return {
                "success": True,
                "user_id": user_id,
                "email": res.user.email,
                "access_token": token,
                "plan": plan,
            }
        return {"success": False, "message": "Invalid email or password."}
    except Exception as exc:
        logger.warning(f"Sign-in failed for {email}: {exc}")
        # Always return generic message to prevent account enumeration
        return {"success": False, "message": "Invalid email or password."}


def sign_up_user(email: str, password: str) -> dict[str, Any]:
    """
    Register a new user via Supabase Auth.
    """
    if not email or not password:
        return {"success": False, "message": "Email and password are required."}

    if len(password) < 6:
        return {"success": False, "message": "Password must be at least 6 characters long."}

    client = get_supabase_client()
    if client is None:
        user_id = f"local-{abs(hash(email)) % 100000}"
        _IN_MEMORY_PROFILES[user_id] = "free"
        return {
            "success": True,
            "message": "Account created in local demo mode.",
            "user_id": user_id,
            "email": email,
            "access_token": f"mock-token-{user_id}",
            "plan": "free",
            "needs_verification": False,
        }

    try:
        res = client.auth.sign_up({"email": email.strip(), "password": password})
        if res and res.user:
            user_id = str(res.user.id)
            has_session = res.session is not None
            access_token = res.session.access_token if res.session else None
            return {
                "success": True,
                "message": "Account created. Check your email for the confirmation link or 6-digit OTP code.",
                "user_id": user_id,
                "email": res.user.email,
                "access_token": access_token,
                "plan": "free",
                "needs_verification": not has_session,
            }
        return {"success": False, "message": "Signup could not be completed."}
    except Exception as exc:
        logger.warning(f"Signup error: {exc}")
        return {"success": False, "message": f"Signup failed: {str(exc)}"}


def verify_email_otp(email: str, token: str) -> dict[str, Any]:
    """
    Verify 6-digit email OTP for user confirmation.
    """
    client = get_supabase_client()
    if client is None:
        return {"success": False, "message": "Auth service unavailable."}

    try:
        res = client.auth.verify_otp({"email": email.strip(), "token": token.strip(), "type": "signup"})
        if res and res.user and res.session:
            user_id = str(res.user.id)
            return {
                "success": True,
                "message": "Email verified successfully.",
                "user_id": user_id,
                "email": res.user.email,
                "access_token": res.session.access_token,
                "plan": get_user_plan(user_id, res.session.access_token),
            }
        return {"success": False, "message": "Invalid or expired OTP code."}
    except Exception as exc:
        logger.warning(f"OTP verification error: {exc}")
        return {"success": False, "message": "Invalid or expired OTP code."}


def reset_password_request(email: str) -> dict[str, Any]:
    """
    Request password reset email.
    """
    client = get_supabase_client()
    if client is not None:
        try:
            client.auth.reset_password_for_email(email.strip())
        except Exception as exc:
            logger.warning(f"Password reset error: {exc}")
    # Always return generic message
    return {
        "success": True,
        "message": "If an account exists for this email, password reset instructions have been sent.",
    }


def sign_out_user(access_token: str | None = None) -> dict[str, Any]:
    """
    Sign out user from Supabase session.
    """
    client = get_supabase_client(access_token)
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception as exc:
            logger.debug(f"Sign out call returned: {exc}")
    return {"success": True, "message": "Signed out successfully."}


def get_user_plan(user_id: str, access_token: str | None = None) -> str:
    """
    Fetch user subscription plan ('free' or 'premium').
    Falls back to 'free' if profile table is not yet provisioned.
    """
    if user_id in _IN_MEMORY_PROFILES:
        return _IN_MEMORY_PROFILES[user_id]

    client = get_supabase_client(access_token)
    if client is not None:
        try:
            res = client.table("profiles").select("plan").eq("user_id", user_id).execute()
            if res.data and len(res.data) > 0:
                plan = res.data[0].get("plan", "free")
                _IN_MEMORY_PROFILES[user_id] = plan
                return plan
        except Exception as exc:
            logger.debug(f"Could not read profiles table: {exc}")

    return "free"


def get_daily_run_count(user_id: str, access_token: str | None = None) -> int:
    """
    Count runs performed by this user today (UTC).
    """
    today_start = datetime.datetime.now(datetime.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    client = get_supabase_client(access_token)
    if client is not None:
        try:
            res = (
                client.table("runs")
                .select("id", count="exact")
                .eq("user_id", user_id)
                .gte("created_at", today_start)
                .execute()
            )
            if hasattr(res, "count") and res.count is not None:
                return int(res.count)
        except Exception as exc:
            logger.debug(f"Could not read runs count from DB: {exc}")

    # Fallback to memory store count
    today_date = datetime.date.today()
    count = sum(
        1
        for r in _IN_MEMORY_RUNS
        if r.get("user_id") == user_id and r.get("date") == today_date
    )
    return count


def record_run(
    user_id: str,
    thesis: str,
    result_json: dict[str, Any] | None = None,
    access_token: str | None = None,
) -> bool:
    """
    Record a completed hedge builder run in the database and audit ledger.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    _IN_MEMORY_RUNS.append({
        "user_id": user_id,
        "thesis": thesis,
        "date": datetime.date.today(),
        "created_at": now.isoformat(),
    })

    client = get_supabase_client(access_token)
    if client is not None:
        try:
            client.table("runs").insert({
                "user_id": user_id,
                "thesis": thesis,
                "result_json": result_json or {},
            }).execute()
            return True
        except Exception as exc:
            logger.debug(f"Could not persist run to runs table: {exc}")
            return False
    return True


def check_run_limit(user_id: str, plan: str, access_token: str | None = None) -> dict[str, Any]:
    """
    Check if the user has remaining runs for the day based on their plan.
    Free tier: 3 runs/day. Premium tier: unlimited.
    """
    if plan == "premium":
        return {
            "allowed": True,
            "plan": "premium",
            "count": get_daily_run_count(user_id, access_token),
            "limit": "unlimited",
            "remaining": "unlimited",
            "message": "Premium plan: unlimited daily runs.",
        }

    count = get_daily_run_count(user_id, access_token)
    limit = config.FREE_TIER_DAILY_RUNS
    remaining = max(0, limit - count)
    allowed = count < limit

    return {
        "allowed": allowed,
        "plan": "free",
        "count": count,
        "limit": limit,
        "remaining": remaining,
        "message": (
            f"Daily run allowance: {count}/{limit} used."
            if allowed
            else f"Daily run limit reached ({limit}/{limit}). Upgrade to Premium for unlimited runs."
        ),
    }
