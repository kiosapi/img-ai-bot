"""Inline mode: myworks gallery + switch_pm for new prompts. Subscription gate + ban check fixed."""
from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultCachedPhoto, InlineQueryResultArticle, InputTextMessageContent
import db
from config import REQUIRED_CHANNEL, ADMIN_IDS

router = Router()
PAGE_LIMIT = 20

async def _ok_user(bot, user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    try:
        maint = await db.get_setting("maintenance", "0")
        if maint=="1":
            return False
    except Exception:
        pass
    try:
        if await db.is_banned(user_id):
            return False
    except Exception:
        pass
    if REQUIRED_CHANNEL:
        try:
            member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
            if member.status not in {"member","administrator","creator"}:
                return False
        except Exception:
            pass
    return True

@router.inline_query()
async def handle_inline(inline: InlineQuery):
    if not await _ok_user(inline.bot, inline.from_user.id):
        await inline.answer([], cache_time=1, is_personal=True)
        return
    user_id = inline.from_user.id
    q = (inline.query or "").strip()

    if not q or q.lower() in ("recent", "my", "myworks", "karya"):
        gens = await db.get_user_generations(user_id, limit=PAGE_LIMIT, offset=0)
        results = []
        for g in gens:
            if g.get("user_id")!=user_id:
                continue
            fid = g.get("result_file_id")
            if not fid:
                continue
            prompt = (g.get("prompt") or "")[:80]
            results.append(InlineQueryResultCachedPhoto(
                id=str(g["id"]),
                photo_file_id=fid,
                title=f"#{g['id']}",
                description=prompt,
                caption=f"🖼️ {prompt}\nvia @{(await inline.bot.get_me()).username}",
            ))
        if not results:
            lang = await db.get_lang(user_id)
            from i18n import t
            await inline.answer([], switch_pm_text=t("inline_empty", lang)[:64], switch_pm_parameter="inline_empty")
            return
        await inline.answer(results, cache_time=5, is_personal=True)
        return

    bot_user = await inline.bot.get_me()
    prompt = q[:200]
    gens = await db.get_user_generations(user_id, limit=50, offset=0)
    filtered = [g for g in gens if g.get("user_id")==user_id and prompt.lower() in (g.get("prompt") or "").lower()][:10]

    results = []
    for g in filtered:
        fid = g.get("result_file_id")
        if not fid:
            continue
        p = (g.get("prompt") or "")[:80]
        results.append(InlineQueryResultCachedPhoto(
            id=f"hist_{g['id']}",
            photo_file_id=fid,
            title=f"#{g['id']}",
            description=p,
            caption=f"🖼️ {p}\nvia @{bot_user.username}",
        ))

    import re
    param = f"gen_{prompt[:40]}".replace(" ", "_")[:64]
    param = re.sub(r"[^A-Za-z0-9_-]", "_", param)[:64] or "inline_new"

    results.insert(0, InlineQueryResultArticle(
        id="create_new",
        title=f"🎨 Buat \"{prompt}\" di bot",
        description="Tap untuk generate gambar baru di PM",
        input_message_content=InputTextMessageContent(message_text=f"🎨 Prompt: {prompt}\n\nBuka @{bot_user.username} untuk generate gambar ini!"),
    ))

    await inline.answer(results, cache_time=2, is_personal=True, switch_pm_text=f"✨ Generate \"{prompt[:25]}...\"", switch_pm_parameter=param)
