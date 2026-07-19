"""Batch generate handler — premium x4."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile
import asyncio

import db
import ui
import cubence
import styles as style_presets
import feature_flags as ff
from i18n import t
from handlers.generate import _size_of, _style_of, is_maintenance, check_and_consume
from gen_queue import QUEUE
from tgutil import ProgressAnimator
from states import GenerateStates

router = Router()


async def _do_batch(message: Message, prompt: str, count: int):
    lang = await db.get_lang(message.from_user.id)
    # queue guard (acquire once for batch)
    if not await QUEUE.acquire(message.from_user.id):
        await message.answer(t("busy_generating", lang), reply_markup=ui.back_menu(lang))
        return
    if await is_maintenance():
        await QUEUE.release(message.from_user.id)
        await message.answer(t("maintenance", lang))
        return

    # check quota for batch: need count quota
    # try consume count times atomically using try_checkin? For simplicity loop check_and_consume
    # But to avoid partial consume on failure, pre-check today count
    from config import DEFAULT_DAILY_LIMIT
    limit = await db.effective_daily_limit(message.from_user.id, DEFAULT_DAILY_LIMIT)
    used = await db.get_today_count(message.from_user.id)
    remaining = limit - used if limit != 0 else count
    bonus = await db.get_bonus_quota(message.from_user.id)
    total_avail = remaining + bonus if limit != 0 else 9999
    if limit != 0 and total_avail < count:
        await QUEUE.release(message.from_user.id)
        await message.answer(
            t("quota_exhausted", lang, used=used, limit=limit, bar=ui.quota_bar(used, limit)),
            reply_markup=ui.back_menu(lang))
        return

    # consume count quota (loop atomic already)
    for _ in range(count):
        await db.check_and_consume_atomic(message.from_user.id, DEFAULT_DAILY_LIMIT)

    size = await _size_of(message.from_user.id)
    style_id_raw = await _style_of(message.from_user.id)
    # apply style
    base_prompt = style_presets.apply_style(prompt, style_id_raw)

    status = await message.answer(t("batch_generating", lang, n=count, used=used+count, limit=limit) + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    animator = ProgressAnimator(message.bot, message.chat.id, status, t("batch_generating", lang, n=count, used=used+count, limit=limit))
    animator.start()

    wm_enabled = await ff.watermark_enabled()
    wm_text = await ff.watermark_text()
    wm_free_only = await ff.watermark_free_only()
    is_prem = await db.is_premium(message.from_user.id)

    def should_watermark():
        if not wm_enabled:
            return False
        if wm_free_only and is_prem:
            return False
        return True

    try:
        # parallel generate count images
        async def one(idx):
            try:
                var_prompt = base_prompt
                if idx > 0:
                    var_prompt = f"{base_prompt}, variation {idx+1}"
                img_bytes = await cubence.generate_image(var_prompt, size=size)
                return img_bytes, None
            except Exception as e:
                return None, str(e)

        results = await asyncio.gather(*[one(i) for i in range(count)])

        success = 0
        for img_bytes, err in results:
            if img_bytes:
                # optional watermark caption
                caption = ""
                if should_watermark():
                    caption = f"\n\n{wm_text}"
                try:
                    sent = await message.answer_photo(
                        BufferedInputFile(img_bytes, filename=f"batch_{success+1}.png"),
                        caption=t("batch_done_item", lang, prompt=prompt[:100], idx=success+1, total=count, size=size) + caption,
                        reply_markup=ui.result_menu(lang, gen_id=0) if success == count-1 else None,
                    )
                    # log each
                    try:
                        fid = sent.photo[-1].file_id
                    except Exception:
                        fid = None
                    await db.log_generation(message.from_user.id, "generate", prompt, size, True, result_file_id=fid, style_id=style_id_raw if style_id_raw != "none" else None)
                    success += 1
                except Exception:
                    await db.log_generation(message.from_user.id, "generate", prompt, size, False)
            else:
                await db.log_generation(message.from_user.id, "generate", prompt, size, False)

        if success == 0:
            await message.answer(t("gen_failed", lang, err="All batch failed"), reply_markup=ui.back_menu(lang))
    finally:
        await QUEUE.release(message.from_user.id)
        await animator.stop()
        try:
            await status.delete()
        except Exception:
            pass


@router.message(Command("batch"))
async def cmd_batch(message: Message):
    lang = await db.get_lang(message.from_user.id)
    if not await ff.batch_enabled():
        await message.answer(t("feature_disabled", lang), reply_markup=ui.back_menu(lang))
        return
    free_lim, prem_lim = await ff.batch_limits()
    is_prem = await db.is_premium(message.from_user.id)
    max_allowed = prem_lim if is_prem else free_lim
    parts = (message.text or "").partition(" ")[2].strip().split()
    if not parts or not parts[0].isdigit():
        await message.answer(t("batch_usage", lang, free=max_allowed, prem=prem_lim), reply_markup=ui.back_menu(lang))
        return
    try:
        n = int(parts[0])
    except Exception:
        n = 1
    n = max(1, min(max_allowed, n))
    prompt = " ".join(parts[1:]).strip()
    if not prompt:
        await message.answer(t("prompt_ask", lang))
        return
    await _do_batch(message, prompt, n)


@router.callback_query(F.data.startswith("batch:"))
async def cb_batch(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    if not await ff.batch_enabled():
        await callback.answer(t("feature_disabled", lang), show_alert=True)
        return
    try:
        # data: batch:{gen_id}:{count}
        _, gen_id_str, count_str = callback.data.split(":")
        gen_id = int(gen_id_str)
        count = int(count_str)
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("prompt"):
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    free_lim, prem_lim = await ff.batch_limits()
    is_prem = await db.is_premium(callback.from_user.id)
    max_allowed = prem_lim if is_prem else free_lim
    count = max(1, min(max_allowed, count))
    await callback.answer(t("batch_generating", lang, n=count, used=0, limit=0)[:30])
    await _do_batch(callback.message, gen["prompt"], count)
