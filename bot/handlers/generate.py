"""Text-to-image generation: /generate, FSM prompt flow, size selection."""
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile

import db
import ui
import cubence
from i18n import t
from config import DEFAULT_DAILY_LIMIT, ALLOWED_SIZES, DEFAULT_SIZE
from tgutil import safe_edit, ProgressAnimator
from states import GenerateStates

router = Router()


async def is_maintenance() -> bool:
    return (await db.get_setting("maintenance", "0")) == "1"


async def _size_of(user_id: int) -> str:
    return await db.get_pref_size(user_id, DEFAULT_SIZE)


async def check_and_consume(user_id: int) -> tuple[bool, int, int]:
    """Returns (allowed, used_after, limit). Does NOT consume if not allowed. limit 0 = unlimited.
    If the daily limit is exhausted, falls back to consuming referral bonus quota
    (bonus images earned by inviting friends) before finally refusing.
    """
    limit = await db.effective_daily_limit(user_id, DEFAULT_DAILY_LIMIT)
    used = await db.get_today_count(user_id)
    if limit != 0 and used >= limit:
        if await db.consume_bonus_quota(user_id, 1):
            return True, used, limit  # used stays at the daily cap; bonus image granted separately
        return False, used, limit
    new_count = await db.increment_usage(user_id)
    return True, new_count, limit


# ---------------- Size selection ----------------
@router.message(Command("size"))
async def cmd_size(message: Message):
    lang = await db.get_lang(message.from_user.id)
    current = await db.get_pref_size(message.from_user.id, DEFAULT_SIZE)
    await message.answer(t("size_pick", lang), reply_markup=ui.size_menu(current, lang))


@router.callback_query(F.data.startswith("size:"))
async def set_size(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    size = callback.data.split(":", 1)[1]
    if size in ALLOWED_SIZES:
        await db.set_pref_size(callback.from_user.id, size)
        await safe_edit(callback.message, t("size_set", lang, size=size), reply_markup=ui.back_menu(lang))
    await callback.answer(t("size_saved", lang))


# ---------------- Core generation ----------------
async def _do_generate(message: Message, prompt: str):
    lang = await db.get_lang(message.from_user.id)
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
    status = await message.answer(t("generating", lang, used=used, limit=limit) + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    animator = ProgressAnimator(message.bot, message.chat.id, status, t("generating", lang, used=used, limit=limit))
    animator.start()
    try:
        img = await cubence.generate_image(prompt, size=size)
        await message.answer_photo(
            BufferedInputFile(img, filename="image.png"),
            caption=t("gen_done", lang, prompt=prompt[:200], size=size, left=ui.sisa_text(used, limit, lang)),
            reply_markup=ui.result_menu(lang),
        )
        await db.log_generation(message.from_user.id, "generate", prompt, size, True)
    except cubence.CubenceError as e:
        await db.log_generation(message.from_user.id, "generate", prompt, size, False)
        await message.answer(t("gen_failed", lang, err=e), reply_markup=ui.back_menu(lang))
    except Exception as e:
        # Catch-all so unexpected errors never leave the user without any
        # response at all (previously this could crash the update silently).
        await db.log_generation(message.from_user.id, "generate", prompt, size, False)
        await message.answer(t("gen_failed", lang, err=f"Unexpected error: {e}"), reply_markup=ui.back_menu(lang))
    finally:
        await animator.stop()
        try:
            await status.delete()
        except Exception:
            pass


@router.message(Command("generate"))
async def cmd_generate(message: Message):
    lang = await db.get_lang(message.from_user.id)
    prompt = message.text.partition(" ")[2].strip()
    if not prompt:
        await message.answer(ui.prompt_ask(lang))
        return
    await _do_generate(message, prompt)


# Reply while in the "type a prompt" state => treat as a generate request.
@router.message(GenerateStates.waiting_prompt, F.text, ~F.text.startswith("/"))
async def fsm_prompt(message: Message, state: FSMContext):
    await state.clear()
    await _do_generate(message, message.text.strip())


# Fallback: plain free-typed text (not a command, no active FSM state) is
# treated directly as a generate prompt. StateFilter(None) is critical — without
# it this catch-all would match even while the user is inside another flow's
# state (edit / custom top-up) and swallow the message before those handlers
# (registered in later routers) can run.
@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def free_text_prompt(message: Message):
    await _do_generate(message, message.text.strip())
