"""Image-to-image / edit: user sends a photo with a caption prompt."""
import io
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile

import db
import ui
import cubence
from i18n import t
from handlers.generate import check_and_consume, _size_of, is_maintenance

router = Router()


@router.message(F.photo)
async def handle_photo(message: Message):
    lang = await db.get_lang(message.from_user.id)
    prompt = (message.caption or "").strip()
    if not prompt:
        await message.answer(ui.edit_ask(lang))
        return

    if await is_maintenance():
        await message.answer(t("maintenance", lang))
        return

    allowed, used, limit = await check_and_consume(message.from_user.id)
    if not allowed:
        await message.answer(
            t("quota_exhausted", lang, used=used, limit=limit, bar=ui.quota_bar(used, limit)),
            reply_markup=ui.back_menu(lang))
        return

    size = await _size_of(message.from_user.id)
    status = await message.answer(t("editing", lang, used=used, limit=limit))
    try:
        photo = message.photo[-1]  # highest resolution
        buf = io.BytesIO()
        await message.bot.download(photo, destination=buf)
        image_bytes = buf.getvalue()

        img = await cubence.edit_image(image_bytes, prompt, size=size)
        await message.answer_photo(
            BufferedInputFile(img, filename="edited.png"),
            caption=t("edit_done", lang, prompt=prompt[:200], size=size, left=ui.sisa_text(used, limit, lang)),
            reply_markup=ui.result_menu(lang),
        )
        await db.log_generation(message.from_user.id, "edit", prompt, size, True)
    except cubence.CubenceError as e:
        await db.log_generation(message.from_user.id, "edit", prompt, size, False)
        await message.answer(t("edit_failed", lang, err=e), reply_markup=ui.back_menu(lang))
    finally:
        try:
            await status.delete()
        except Exception:
            pass
