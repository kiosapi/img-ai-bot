"""Inline mode: myworks gallery + switch_pm for new prompts."""
from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultCachedPhoto, InlineQueryResultArticle, InputTextMessageContent

import db

router = Router()

PAGE_LIMIT = 20


@router.inline_query()
async def handle_inline(inline: InlineQuery):
    user_id = inline.from_user.id
    q = (inline.query or "").strip()

    # If empty or 'recent' -> show myworks gallery (zero storage, file_id based)
    if not q or q.lower() in ("recent", "my", "myworks", "karya"):
        gens = await db.get_user_generations(user_id, limit=PAGE_LIMIT, offset=0)
        results = []
        for g in gens:
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
            # no history -> switch_pm prompt to create
            await inline.answer(
                [], switch_pm_text="🎨 Buat gambar pertama kamu", switch_pm_parameter="inline_empty"
            )
            return
        await inline.answer(results, cache_time=5, is_personal=True)
        return

    # Query with prompt -> cannot generate in inline (10s timeout), so offer switch_pm to create it
    bot_user = await inline.bot.get_me()
    prompt = q[:200]
    # Also show matching history if any (simple contains filter)
    gens = await db.get_user_generations(user_id, limit=50, offset=0)
    filtered = [g for g in gens if prompt.lower() in (g.get("prompt") or "").lower()][:10]

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

    # always add create-new article that switches to PM
    # encode prompt into start param: max 64 chars, base64url not safe, so truncate and pass raw with gen_ prefix
    # Telegram limits switch_pm_parameter to 64 chars, so trim
    param = f"gen_{prompt[:40]}".replace(" ", "_")[:64]
    # sanitize: only A-Z a-z 0-9 _ -
    import re
    param = re.sub(r"[^A-Za-z0-9_-]", "_", param)[:64] or "inline_new"

    results.insert(0, InlineQueryResultArticle(
        id="create_new",
        title=f"🎨 Buat \"{prompt}\" di bot",
        description="Tap untuk generate gambar baru di PM",
        input_message_content=InputTextMessageContent(
            message_text=f"🎨 Prompt: {prompt}\n\nBuka @{bot_user.username} untuk generate gambar ini!"
        ),
        # Note: switch_pm via answer switch_pm_text, not per-result
    ))

    await inline.answer(
        results,
        cache_time=2,
        is_personal=True,
        switch_pm_text=f"✨ Generate \"{prompt[:25]}...\"",
        switch_pm_parameter=param
    )
