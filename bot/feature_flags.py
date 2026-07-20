"""Feature flag helpers wrapping db.get_setting.
All flags default to enabled except watermark (off by default).
Async wrappers so handlers can await directly without caring about setting keys.
Also generic command toggle helpers (feat_command_{name}_enabled).
"""
from __future__ import annotations

import db
from functools import wraps
from typing import Callable

# Map feature key -> setting key + default
_FEAT_MAP: dict = {
    "ENHANCE": ("feat_enhance_enabled", "1"),
    "BATCH": ("feat_batch_enabled", "1"),
    "WATERMARK": ("feat_watermark_enabled", "0"),
    "STICKER": ("feat_sticker_enabled", "1"),
    "CHECKIN": ("feat_checkin_enabled", "1"),
}

# ---- Command map: used for COMMAND MANAGER (toggle commands on/off without code) ----
# Each key corresponds to a bot command. Storage key is feat_command_{name}_enabled
# Keep canonical lowercase command names.
_COMMAND_FEAT_DEFAULTS: dict[str, str] = {
    "generate": "1",
    "edit": "1",
    "style": "1",
    "myworks": "1",
    "checkin": "1",
    "sticker": "1",
    "premium": "1",
    "balance": "1",
    "referral": "1",
    "model": "1",
    "enhance": "1",
    "batch": "1",
    "batchold": "1",
    "quota": "1",
    "lang": "1",
    "size": "1",
}

# Human-readable definition shared with API (also used for defaults)
COMMAND_DEFS: dict[str, dict] = {
    "generate": {"group": "core", "icon": "Sparkles", "description_id": "Generate image (core)", "description_en": "Generate image from text"},
    "edit": {"group": "core", "icon": "ImagePlus", "description_id": "Edit foto", "description_en": "Edit photo with AI"},
    "style": {"group": "core", "icon": "Palette", "description_id": "Style presets", "description_en": "Style presets"},
    "size": {"group": "core", "icon": "Ruler", "description_id": "Ukuran gambar", "description_en": "Image size"},
    "quota": {"group": "core", "icon": "BarChart3", "description_id": "Kuota harian", "description_en": "Daily quota"},
    "myworks": {"group": "core", "icon": "Images", "description_id": "Karya Saya", "description_en": "My works history"},
    "batch": {"group": "core", "icon": "Layers", "description_id": "Batch generate", "description_en": "Batch generate (new)"},
    "batchold": {"group": "core", "icon": "Layers3", "description_id": "Batch old command", "description_en": "Legacy batch command"},
    "checkin": {"group": "social", "icon": "CalendarCheck", "description_id": "Check-in harian", "description_en": "Daily check-in streak"},
    "referral": {"group": "social", "icon": "Gift", "description_id": "Ajak teman referral", "description_en": "Referral invite friends"},
    "sticker": {"group": "premium", "icon": "Sticker", "description_id": "Sticker pack", "description_en": "Sticker pack from works"},
    "model": {"group": "core", "icon": "Bot", "description_id": "Pilih model AI", "description_en": "Select AI model"},
    "enhance": {"group": "core", "icon": "Wand2", "description_id": "Prompt enhance", "description_en": "Prompt enhance"},
    "premium": {"group": "premium", "icon": "Crown", "description_id": "Upgrade premium", "description_en": "Premium upgrade"},
    "balance": {"group": "premium", "icon": "Wallet", "description_id": "Saldo & deposit", "description_en": "Balance & deposits"},
    "lang": {"group": "core", "icon": "Languages", "description_id": "Ganti bahasa", "description_en": "Change language"},
}

ENHANCE = "ENHANCE"
BATCH = "BATCH"
WATERMARK = "WATERMARK"
STICKER = "STICKER"
CHECKIN = "CHECKIN"


async def is_feat_enabled(key: str) -> bool:
    """Generic check: ENHANCE, BATCH, WATERMARK, STICKER, CHECKIN etc."""
    setting_key, default = _FEAT_MAP.get(key.upper(), (f"feat_{key.lower()}_enabled", "1"))
    v = await db.get_setting(setting_key, default)
    return v == "1"


# ---- specific async wrappers (task requires these names) ----

async def enhance_enabled() -> bool:
    return await db.feat_prompt_enhance_enabled()


async def batch_enabled() -> bool:
    return await db.feat_batch_enabled()


async def watermark_enabled() -> bool:
    return await db.feat_watermark_enabled()


async def sticker_enabled() -> bool:
    return await db.feat_sticker_enabled()


async def checkin_enabled() -> bool:
    return await db.feat_checkin_enabled()


async def watermark_text() -> str:
    return await db.get_watermark_text()


async def watermark_free_only() -> bool:
    return await db.get_watermark_free_only()


async def enhance_model() -> str:
    return await db.get_enhance_model()


async def batch_limits() -> tuple[int, int]:
    return await db.get_batch_limits()


async def batch_limit_free() -> int:
    return await db.get_batch_limit_free()


async def batch_limit_premium() -> int:
    return await db.get_batch_limit_premium()


async def sticker_max() -> int:
    return await db.get_sticker_max_per_pack()


# aliases matching task wording
async def sticker_max_per_pack() -> int:
    return await db.get_sticker_max_per_pack()


async def enhance_model_name() -> str:
    return await db.get_enhance_model()


# ---------- Command Manager (generic feat_command_{name}_enabled) ----------
def _cmd_key(name: str) -> str:
    return f"feat_command_{name.lower()}_enabled"


async def is_command_enabled(cmd_name: str) -> bool:
    """Generic get_setting feat_command_{name}_enabled, default enabled."""
    k = _cmd_key(cmd_name)
    default = _COMMAND_FEAT_DEFAULTS.get(cmd_name.lower(), "1")
    v = await db.get_setting(k, default)
    return (v or default) == "1"


async def set_command_enabled(cmd_name: str, enabled: bool) -> None:
    await db.set_setting(_cmd_key(cmd_name), "1" if enabled else "0")


async def list_command_statuses() -> list[dict]:
    """Return list of dicts with name, enabled, group, icon, descriptions."""
    out = []
    for name, def_info in COMMAND_DEFS.items():
        en = await is_command_enabled(name)
        out.append({
            "name": name,
            "is_enabled": en,
            "setting_key": _cmd_key(name),
            "group": def_info.get("group", "core"),
            "icon": def_info.get("icon", "Command"),
            "description_id": def_info.get("description_id", name),
            "description_en": def_info.get("description_en", name),
        })
    return out


def require_command_enabled(cmd_name: str):
    """Decorator-like wrapper for aiogram handlers. Use as helper inside handler or as actual decorator for message handlers that receive Message as first arg."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # resolve lang and answer if disabled
            from aiogram.types import Message, CallbackQuery
            # find Message or CallbackQuery in args
            target = None
            for a in args:
                if isinstance(a, (Message, CallbackQuery)):
                    target = a
                    break
            if target is None:
                # try kwargs
                target = kwargs.get("message") or kwargs.get("callback") or kwargs.get("event")
            # check enabled
            if not await is_command_enabled(cmd_name):
                # try to reply maintenance message
                try:
                    if target is not None:
                        # get lang if possible
                        try:
                            uid = target.from_user.id if hasattr(target, "from_user") else 0
                            lang = await db.get_lang(uid) if uid else "id"
                        except Exception:
                            lang = "id"
                        # import i18n lazily to avoid circular
                        try:
                            from i18n import t as _t
                            msg_text = _t("feature_disabled", lang) if _t("feature_disabled", lang) != "feature_disabled" else f"Fitur /{cmd_name} sedang nonaktif sementara (maintenance). Coba lagi nanti."
                        except Exception:
                            msg_text = f"Command /{cmd_name} is temporarily disabled for maintenance."
                        if isinstance(target, Message):
                            await target.answer(msg_text)
                        elif isinstance(target, CallbackQuery):
                            await target.answer(msg_text, show_alert=True)
                except Exception:
                    pass
                return None
            return await func(*args, **kwargs)
        return wrapper
    return decorator


async def check_command_or_reply(cmd_name: str, message_or_callback) -> bool:
    """Inline helper: returns True if enabled, else replies with maintenance and returns False."""
    if await is_command_enabled(cmd_name):
        return True
    try:
        from aiogram.types import Message, CallbackQuery
        # try lang
        try:
            uid = message_or_callback.from_user.id if hasattr(message_or_callback, "from_user") else 0
            lang = await db.get_lang(uid) if uid else "id"
        except Exception:
            lang = "id"
        try:
            from i18n import t as _t
            txt = _t("feature_disabled", lang)
            if txt == "feature_disabled":
                txt = f"Fitur /{cmd_name} sedang dimatikan admin untuk maintenance." if lang == "id" else f"Command /{cmd_name} is disabled for maintenance."
            txt += f"\n\n/{cmd_name} in maintenance." if lang == "id" else f"\n\nTry again later."
        except Exception:
            txt = f"Command /{cmd_name} disabled."
        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(txt)
        elif isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.answer(txt, show_alert=True)
    except Exception:
        pass
    return False
