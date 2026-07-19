"""Text-to-image generation: /generate, FSM prompt flow, size selection + queue + enhance + watermark + batch."""
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile

import db
import ui
import cubence
import styles as style_presets
import feature_flags as ff
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
    allowed, used, limit, _bonus = await db.check_and_consume_atomic(user_id, DEFAULT_DAILY_LIMIT)
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


async def _do_generate(message: Message, prompt: str, variation: bool = False, force_size: str | None = None, enhance: bool = False):
    lang = await db.get_lang(message.from_user.id)
    # queue gate
    if (await db.get_setting("feat_queue_enabled", "1")) == "1":
        if not await QUEUE.acquire(message.from_user.id):
            await message.answer(t("busy_generating", lang), reply_markup=ui.back_menu(lang))
            return

    if await is_maintenance():
        if (await db.get_setting("feat_queue_enabled", "1")) == "1":
            await QUEUE.release(message.from_user.id)
        await message.answer(t("maintenance", lang))
        return

    allowed, used, limit = await check_and_consume(message.from_user.id)
    if not allowed:
        if (await db.get_setting("feat_queue_enabled", "1")) == "1":
            await QUEUE.release(message.from_user.id)
        await message.answer(
            t("quota_exhausted", lang, used=used, limit=limit, bar=ui.quota_bar(used, limit)),
            reply_markup=ui.back_menu(lang))
        return

    size = force_size or await _size_of(message.from_user.id)
    final_prompt = prompt
    if enhance:
        if not await ff.enhance_enabled():
            enhance = False
        else:
            try:
                from enhancer import enhance_prompt
                enhanced = await enhance_prompt(prompt)
                if enhanced and len(enhanced.strip()) > 5:
                    final_prompt = enhanced
            except Exception:
                pass

    styled_prompt, style_id = await _apply_user_style(message.from_user.id, final_prompt)
    if variation:
        import random
        var_hints = ["different angle", "different lighting", "slightly different composition", "alternative perspective", "with slight variation"]
        styled_prompt = f"{styled_prompt}, {random.choice(var_hints)}"

    # watermark check (do after consume to not waste quota if disabled? we already consumed, so keep simple)
    try:
        from watermark import should_watermark, apply_watermark_image
        wm_on, wm_text = await should_watermark(message.from_user.id)
    except Exception:
        wm_on, wm_text = False, ""

    status = await message.answer(t("generating", lang, used=used, limit=limit) + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    animator = ProgressAnimator(message.bot, message.chat.id, status, t("generating", lang, used=used, limit=limit))
    animator.start()
    try:
        img = await cubence.generate_image(styled_prompt, size=size)
        # apply image watermark if enabled
        if wm_on and wm_text:
            try:
                img = apply_watermark_image(img, wm_text)
            except Exception:
                pass

        caption_base = t("gen_done", lang, prompt=final_prompt[:200], size=size, left=ui.sisa_text(used, limit, lang))
        if wm_on and wm_text:
            caption_base += f"\n\n{wm_text}"
        sent = await message.answer_photo(
            BufferedInputFile(img, filename="image.png"),
            caption=caption_base,
            reply_markup=ui.result_menu(lang, gen_id=0, file_id=None),
        )
        try:
            result_file_id = sent.photo[-1].file_id
        except Exception:
            result_file_id = None
        gen_id = await db.log_generation(
            message.from_user.id, "generate", final_prompt, size, True,
            result_file_id=result_file_id, style_id=style_id if style_id != "none" else None
        )
        if result_file_id and gen_id:
            try:
                await sent.edit_caption(
                    caption=caption_base,
                    reply_markup=ui.result_menu(lang, gen_id=gen_id, file_id=result_file_id)
                )
            except Exception:
                pass
    except cubence.CubenceError as e:
        await db.log_generation(message.from_user.id, "generate", final_prompt, size, False, style_id=style_id if style_id != "none" else None)
        await message.answer(t("gen_failed", lang, err=e), reply_markup=ui.back_menu(lang))
    except Exception as e:
        await db.log_generation(message.from_user.id, "generate", final_prompt, size, False, style_id=style_id if style_id != "none" else None)
        await message.answer(t("gen_failed", lang, err=f"Unexpected error: {e}"), reply_markup=ui.back_menu(lang))
    finally:
        if (await db.get_setting("feat_queue_enabled", "1")) == "1":
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
    enhance = False
    if prompt.startswith("✨ "):
        enhance = True
        prompt = prompt[2:].strip()
    await _do_generate(message, prompt, enhance=enhance)


@router.message(Command("enhance"))
async def cmd_enhance(message: Message):
    lang = await db.get_lang(message.from_user.id)
    if not await ff.enhance_enabled():
        await message.answer(t("feature_disabled", lang), reply_markup=ui.back_menu(lang))
        return
    prompt = message.text.partition(" ")[2].strip()
    if not prompt:
        await message.answer(t("enhance_doing", lang) + "\n\n" + ui.prompt_ask(lang))
        return
    await _do_generate(message, prompt, enhance=True)


@router.callback_query(F.data.startswith("enhance:"))
async def cb_enhance(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    if not await ff.enhance_enabled():
        await callback.answer(t("feature_disabled", lang), show_alert=True)
        return
    try:
        gen_id = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("prompt"):
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    await callback.answer("Enhancing...")
    await _do_generate(callback.message, gen["prompt"], enhance=True)


@router.message(GenerateStates.waiting_prompt, F.text, ~F.text.startswith("/"))
async def fsm_prompt(message: Message, state: FSMContext):
    data = await state.get_data()
    enhance = data.get("enhance", False)
    await state.clear()
    await _do_generate(message, message.text.strip(), enhance=enhance)


@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def free_text_prompt(message: Message):
    await _do_generate(message, message.text.strip())
