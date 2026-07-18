"""Text-to-image generation: /generate, ForceReply prompt flow, size selection."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile

import db
import ui
import cubence
from config import DEFAULT_DAILY_LIMIT, ALLOWED_SIZES, DEFAULT_SIZE

router = Router()


async def is_maintenance() -> bool:
    return (await db.get_setting("maintenance", "0")) == "1"


async def _size_of(user_id: int) -> str:
    return await db.get_pref_size(user_id, DEFAULT_SIZE)


async def check_and_consume(user_id: int) -> tuple[bool, int, int]:
    """Returns (allowed, used_after, limit). Does NOT consume if not allowed."""
    limit = await db.get_daily_limit(DEFAULT_DAILY_LIMIT)
    used = await db.get_today_count(user_id)
    if used >= limit:
        return False, used, limit
    new_count = await db.increment_usage(user_id)
    return True, new_count, limit


# ---------------- Size selection ----------------
@router.message(Command("size"))
async def cmd_size(message: Message):
    current = await db.get_pref_size(message.from_user.id, DEFAULT_SIZE)
    await message.answer("📐 <b>Pilih Ukuran Gambar</b>", reply_markup=ui.size_menu(current))


@router.callback_query(F.data.startswith("size:"))
async def set_size(callback: CallbackQuery):
    size = callback.data.split(":", 1)[1]
    if size in ALLOWED_SIZES:
        await db.set_pref_size(callback.from_user.id, size)
        await callback.message.edit_text(
            f"✅ Ukuran diset ke <b>{size}</b>", reply_markup=ui.back_menu())
    await callback.answer("Ukuran tersimpan ✓")


# ---------------- Core generation ----------------
async def _do_generate(message: Message, prompt: str):
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
    status = await message.answer(f"🎨 <b>Membuat gambar...</b>\n⏳ Mohon tunggu sebentar ({used}/{limit})")
    try:
        img = await cubence.generate_image(prompt, size=size)
        await message.answer_photo(
            BufferedInputFile(img, filename="image.png"),
            caption=(
                f"✅ <b>Gambar selesai!</b>\n\n"
                f"📝 <i>{prompt[:200]}</i>\n"
                f"📐 {size}  ·  📊 Sisa {limit - used} gambar"
            ),
            reply_markup=ui.result_menu(),
        )
        await db.log_generation(message.from_user.id, "generate", prompt, size, True)
    except cubence.CubenceError as e:
        await db.log_generation(message.from_user.id, "generate", prompt, size, False)
        await message.answer(f"❌ <b>Gagal membuat gambar</b>\n<code>{e}</code>", reply_markup=ui.back_menu())
    finally:
        try:
            await status.delete()
        except Exception:
            pass


@router.message(Command("generate"))
async def cmd_generate(message: Message):
    prompt = message.text.partition(" ")[2].strip()
    if not prompt:
        await message.answer(ui.prompt_ask())
        return
    await _do_generate(message, prompt)


# Reply to the ForceReply "ketik prompt" message => treat as a generate request.
@router.message(F.reply_to_message, F.text, ~F.text.startswith("/"))
async def reply_prompt(message: Message):
    rt = message.reply_to_message
    if rt and rt.from_user and rt.from_user.is_bot and "Buat Gambar" in (rt.text or ""):
        await _do_generate(message, message.text.strip())
