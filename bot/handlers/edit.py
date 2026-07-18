"""Image-to-image / edit: user sends a photo with a caption prompt."""
import io
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile

import db
import ui
import cubence
from handlers.generate import check_and_consume, _size_of, is_maintenance

router = Router()


@router.message(F.photo)
async def handle_photo(message: Message):
    prompt = (message.caption or "").strip()
    if not prompt:
        await message.answer(ui.edit_ask())
        return

    if await is_maintenance():
        await message.answer("🛠️ <b>Bot sedang maintenance</b>\nCoba lagi beberapa saat ya.")
        return

    allowed, used, limit = await check_and_consume(message.from_user.id)
    if not allowed:
        await message.answer(
            f"🚫 <b>Kuota harian habis</b> ({used}/{limit})\n{ui.quota_bar(used, limit)}\n\nReset otomatis besok 🔄",
            reply_markup=ui.back_menu())
        return

    size = await _size_of(message.from_user.id)
    status = await message.answer(f"🖌️ <b>Mengedit gambar...</b>\n⏳ Mohon tunggu sebentar ({used}/{limit})")
    try:
        photo = message.photo[-1]  # highest resolution
        buf = io.BytesIO()
        await message.bot.download(photo, destination=buf)
        image_bytes = buf.getvalue()

        img = await cubence.edit_image(image_bytes, prompt, size=size)
        await message.answer_photo(
            BufferedInputFile(img, filename="edited.png"),
            caption=(
                f"✅ <b>Edit selesai!</b>\n\n"
                f"📝 <i>{prompt[:200]}</i>\n"
                f"📐 {size}  ·  📊 Sisa {limit - used} gambar"
            ),
            reply_markup=ui.result_menu(),
        )
        await db.log_generation(message.from_user.id, "edit", prompt, size, True)
    except cubence.CubenceError as e:
        await db.log_generation(message.from_user.id, "edit", prompt, size, False)
        await message.answer(f"❌ <b>Gagal mengedit gambar</b>\n<code>{e}</code>", reply_markup=ui.back_menu())
    finally:
        try:
            await status.delete()
        except Exception:
            pass
