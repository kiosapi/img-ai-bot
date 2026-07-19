"""Text-to-image generation: /generate, FSM prompt flow, size selection + queue limit."""
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile

import db
import ui
import cubence
import styles as style_presets
from i18n import t
from config import DEFAULT_DAILY_LIMIT, ALLOWED_SIZES, DEFAULT_SIZE
from tgutil import safe_edit, ProgressAnimator
from states import GenerateStates
from gen_queue import QUEUE

router = Router()


async def is_maintenance() -> bool:
    return (await db.get_setting("maintenance", "0")) == "1"


async def _size_of(user_id: int) -> str:
    return await db.get_pref_size(user_id, DEFAULT_SIZE)


async def _style_of(user_id: int) -> str:
    return await db.get_pref_style(user_id, "none") or "none"


async def _apply_user_style(user_id: int, prompt: str) -> tuple[str, str]:
    sid = await _style_of(user_id)
    styled = style_presets.apply_style(prompt, sid)
    return styled, sid


async def check_and_consume(user_id: int) -> tuple[bool, int, int]:
    from config import DEFAULT_DAILY_LIMIT as _fallback
    allowed, used, limit, _bonus = await db.check_and_consume_atomic(user_id, _fallback)
    return allowed, used, limit


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


async def _do_generate(message: Message, prompt: str, variation: bool = False, force_size: str | None = None):
    lang = await db.get_lang(message.from_user.id)
    # queue 1/user guard
    if not await QUEUE.acquire(message.from_user.id):
        await message.answer(t("busy_generating", lang), reply_markup=ui.back_menu(lang))
        return

    if await is_maintenance():
        await QUEUE.release(message.from_user.id)
        await message.answer(t("maintenance", lang))
        return

    allowed, used, limit = await check_and_consume(message.from_user.id)
    if not allowed:
        await QUEUE.release(message.from_user.id)
        await message.answer(
            t("quota_exhausted", lang, used=used, limit=limit, bar=ui.quota_bar(used, limit)),
            reply_markup=ui.back_menu(lang))
        return

    size = force_size or await _size_of(message.from_user.id)
    styled_prompt, style_id = await _apply_user_style(message.from_user.id, prompt)
    if variation:
        import random
        var_hints = ["different angle", "different lighting", "slightly different composition", "alternative perspective", "with slight variation"]
        styled_prompt = f"{styled_prompt}, {random.choice(var_hints)}"

    status = await message.answer(t("generating", lang, used=used, limit=limit) + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    animator = ProgressAnimator(message.bot, message.chat.id, status, t("generating", lang, used=used, limit=limit))
    animator.start()
    try:
        img = await cubence.generate_image(styled_prompt, size=size)
        sent = await message.answer_photo(
            BufferedInputFile(img, filename="image.png"),
            caption=t("gen_done", lang, prompt=prompt[:200], size=size, left=ui.sisa_text(used, limit, lang)),
            reply_markup=ui.result_menu(lang, gen_id=0, file_id=None),
        )
        try:
            result_file_id = sent.photo[-1].file_id
        except Exception:
            result_file_id = None
        gen_id = await db.log_generation(
            message.from_user.id, "generate", prompt, size, True,
            result_file_id=result_file_id, style_id=style_id if style_id != "none" else None
        )
        if result_file_id and gen_id:
            try:
                await sent.edit_caption(
                    caption=t("gen_done", lang, prompt=prompt[:200], size=size, left=ui.sisa_text(used, limit, lang)),
                    reply_markup=ui.result_menu(lang, gen_id=gen_id, file_id=result_file_id)
                )
            except Exception:
                pass
    except cubence.CubenceError as e:
        await db.log_generation(message.from_user.id, "generate", prompt, size, False, style_id=style_id if style_id != "none" else None)
        await message.answer(t("gen_failed", lang, err=e), reply_markup=ui.back_menu(lang))
    except Exception as e:
        await db.log_generation(message.from_user.id, "generate", prompt, size, False, style_id=style_id if style_id != "none" else None)
        await message.answer(t("gen_failed", lang, err=f"Unexpected error: {e}"), reply_markup=ui.back_menu(lang))
    finally:
        await QUEUE.release(message.from_user.id)
        await animator.stop()
        try:
            await status.delete()
        except Exception:
            pass


@router.message(Command("generate"))
async def cmd_generate(message: Message):
    prompt = message.text.partition(" ")[2].strip()
    if not prompt:
        await message.answer(ui.prompt_ask(await db.get_lang(message.from_user.id)))
        return
    await _do_generate(message, prompt)


@router.message(GenerateStates.waiting_prompt, F.text, ~F.text.startswith("/"))
async def fsm_prompt(message: Message, state: FSMContext):
    await state.clear()
    await _do_generate(message, message.text.strip())


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def free_text_prompt(message: Message):
    await _do_generate(message, message.text.strip())
