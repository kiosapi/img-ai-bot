"""Dynamic Texts helper — reads from settings table via db.get_setting (no direct asyncpg).
No cache for instant admin updates. Fallback to hardcoded default if empty.
"""
from __future__ import annotations
from typing import Any
import db

# Default fallbacks — keep empty so that i18n layer / hardcoded can be used if not set
# For keys where we have strong default, put minimal placeholder
_DEFAULTS: dict[str, str] = {
    "welcome_text": "",
    "welcome_back_text": "",
    "help_text": "",
    "menu_hint": "",
    "maintenance_msg": "",
    "quota_exhausted_msg": "",
    "daily_limit_msg": "",
    "nsfw_msg": "",
    "banned_msg": "",
    "busy_msg": "",
    "gen_failed_msg": "",
    "edit_failed_msg": "",
    "checkin_msg": "",
    "checkin_success_msg": "",
    "checkin_already_msg": "",
    "referral_invite_text": "",
    "referral_reward_balance_text": "",
    "referral_reward_quota_text": "",
    "premium_expired_msg": "",
    "upgrade_no_plans_msg": "",
    "upgrade_intro_msg": "",
    "deposit_disabled_msg": "",
    "deposit_success_msg": "",
    "deposit_pending_msg": "",
    "join_required_msg": "",
    "join_success_msg": "",
    "join_not_detected_msg": "",
    "inline_empty_msg": "",
    "feat_disabled_msg": "",
}

async def get_dynamic_text(key: str, fallback: str = "") -> str:
    """Fetch dynamic text from settings. Return fallback if empty.
    Uses db.get_setting which already handles pool + query.
    No cache — admin expects instant apply.
    """
    key = (key or "").strip()[:100]
    if not key:
        return fallback
    try:
        val = await db.get_setting(key, None)
        if val is None:
            # also try defaults map
            return _DEFAULTS.get(key, fallback) or fallback
        val = val.strip() if isinstance(val, str) else str(val)
        if not val:
            return _DEFAULTS.get(key, fallback) or fallback
        return val
    except Exception:
        return _DEFAULTS.get(key, fallback) or fallback

async def get_dynamic_text_formatted(key: str, fallback: str = "", **kwargs: Any) -> str:
    """Like get_dynamic_text but does safe .format(**kwargs) if placeholders present.
    If formatting fails, returns raw text.
    """
    raw = await get_dynamic_text(key, fallback)
    if not kwargs:
        return raw
    try:
        return raw.format(**kwargs)
    except Exception:
        # try also handle double braces or missing keys — return raw
        return raw

async def get_dynamic_text_or_none(key: str) -> str | None:
    """Return None if not set, else value. Useful when caller wants to fallback to i18n.py itself."""
    try:
        val = await db.get_setting(key, None)
        if val and str(val).strip():
            return str(val).strip()
        return None
    except Exception:
        return None

# Convenience wrappers for common groups — optional but helpful for handlers
async def maintenance_text(fallback: str) -> str:
    return await get_dynamic_text("maintenance_msg", fallback)

async def quota_exhausted_text(fallback: str) -> str:
    return await get_dynamic_text("quota_exhausted_msg", fallback)

async def welcome_text_dynamic(fallback: str) -> str:
    return await get_dynamic_text("welcome_text", fallback)

async def help_text_dynamic(fallback: str) -> str:
    return await get_dynamic_text("help_text", fallback)

async def banned_text(fallback: str) -> str:
    return await get_dynamic_text("banned_msg", fallback)
