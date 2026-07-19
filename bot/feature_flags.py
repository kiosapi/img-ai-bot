"""Feature flag helpers wrapping db.get_setting.

All flags default to enabled except watermark (off by default).
Async wrappers so handlers can await directly without caring about setting keys.
"""
from __future__ import annotations

import db


# Map feature key -> setting key + default
_FEAT_MAP: dict = {
    "ENHANCE": ("feat_enhance_enabled", "1"),
    "BATCH": ("feat_batch_enabled", "1"),
    "WATERMARK": ("feat_watermark_enabled", "0"),
    "STICKER": ("feat_sticker_enabled", "1"),
    "CHECKIN": ("feat_checkin_enabled", "1"),
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
