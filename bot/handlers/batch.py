"""Batch generate handler — legacy /batchold + batchgen IDOR fixed + quota atomic."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.filters import Command
import asyncio

import db
import ui
import styles as style_presets
import feature_flags as ff
from i18n import t
from gen_queue import QUEUE
from tgutil import ProgressAnimator
from config import DEFAULT_DAILY_LIMIT

router = Router()

async def _size_of(uid: int):
    from config import DEFAULT_SIZE
    return await db.get_pref_size(uid, DEFAULT_SIZE)

async def _style_of(uid: int):
    return await db.get_pref_style(uid, "none") or "none"

@router.message(Command("batchold"))
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

async def _do_batch(message: Message, prompt: str, count: int):
    lang = await db.get_lang(message.from_user.id)
    acquired=False
    queue_status_msg = None
    if (await db.get_setting("feat_queue_enabled", "1")) == "1":
        if QUEUE.is_busy(message.from_user.id):
            await message.answer(t("busy_generating", lang), reply_markup=ui.back_menu(lang))
            return
        queue_status_msg = await message.answer(t("queue_joining", lang))

        async def _on_wait(pos: int, eta: int):
            if not queue_status_msg:
                return
            try:
                txt = t("queue_running", lang, eta=eta) if pos <= 0 else t("queue_pos", lang, pos=pos, eta=eta)
                await queue_status_msg.edit_text(txt)
            except Exception:
                pass

        if not await QUEUE.acquire(message.from_user.id, on_wait=_on_wait):
            try:
                await queue_status_msg.edit_text(t("queue_timeout", lang), reply_markup=ui.back_menu(lang))
            except Exception:
                await message.answer(t("queue_timeout", lang), reply_markup=ui.back_menu(lang))
            return
        acquired=True
    from config import DEFAULT_DAILY_LIMIT
    # atomic multi consume
    ok, used, limit, _b = await db.check_and_consume_multi(message.from_user.id, DEFAULT_DAILY_LIMIT, count)
    if not ok:
        if acquired:
            await QUEUE.release(message.from_user.id)
        await message.answer(t("quota_exhausted", lang, used=used, limit=limit, bar=ui.quota_bar(used, limit)), reply_markup=ui.back_menu(lang))
        return

    size = await _size_of(message.from_user.id)
    style_id_raw = await _style_of(message.from_user.id)
    base_prompt = style_presets.apply_style(prompt, style_id_raw)

    batch_base = t("batch_generating", lang, n=count, used=used, limit=limit)
    if queue_status_msg is not None:
        status = queue_status_msg
        try:
            await status.edit_text(batch_base + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
        except Exception:
            status = await message.answer(batch_base + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    else:
        status = await message.answer(batch_base + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    animator = ProgressAnimator(message.bot, message.chat.id, status, batch_base)
    animator.start()

    try:
        from watermark import should_watermark, apply_watermark_image
        wm_on, wm_text = await should_watermark(message.from_user.id)
    except Exception:
        wm_on, wm_text = False, ""

    try:
        active_model = await db.get_active_model_for_user(message.from_user.id)
    except Exception:
        active_model = None

    try:
        from providers import generate_image as provider_generate
        async def one(idx):
            try:
                var_prompt = base_prompt if idx == 0 else f"{base_prompt}, variation {idx+1}"
                b = await provider_generate(active_model, var_prompt, size=size, user_id=message.from_user.id)
                if wm_on and wm_text:
                    try:
                        b = apply_watermark_image(b, wm_text)
                    except Exception:
                        pass
                return b, None
            except Exception as e:
                return None, str(e)

        results = await asyncio.gather(*[one(i) for i in range(count)])
        success = 0
        for img_bytes, err in results:
            if img_bytes:
                caption = t("batch_done_item", lang, prompt=prompt[:100], idx=success+1, total=count, size=size)
                if active_model:
                    try:
                        from model_display import format_model_label
                        _ml = format_model_label(active_model.get("provider_id",""), active_model.get("external_id") or active_model.get("id",""), active_model.get("display_name"))
                    except Exception:
                        _ml = active_model.get("display_name") or active_model.get("external_id") or ""
                    caption += f"\nModel: {_ml}"
                # watermark only on image — no caption double
                try:
                    sent = await message.answer_photo(BufferedInputFile(img_bytes, filename=f"batch_{success+1}.png"), caption=caption, reply_markup=ui.result_menu(lang, gen_id=0) if success == count-1 else None)
                    try:
                        fid = sent.photo[-1].file_id
                    except Exception:
                        fid = None
                    gid = await db.log_generation(message.from_user.id, "generate", prompt, size, True, result_file_id=fid, style_id=style_id_raw if style_id_raw != "none" else None)
                    if gid and active_model:
                        try:
                            async with db._pool.acquire() as con:
                                await con.execute("UPDATE generations SET model_id=$2 WHERE id=$1", gid, active_model["id"])
                        except Exception:
                            pass
                    success += 1
                except Exception:
                    await db.log_generation(message.from_user.id, "generate", prompt, size, False)
            else:
                await db.log_generation(message.from_user.id, "generate", prompt, size, False)

        if success == 0:
            await message.answer(t("gen_failed", lang, err="All batch failed"), reply_markup=ui.back_menu(lang))
    finally:
        if acquired:
            await QUEUE.release(message.from_user.id)
        await animator.stop()
        try:
            await status.delete()
        except Exception:
            pass

@router.callback_query(F.data.startswith("batchgen:"))
async def cb_batch(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    if not await ff.batch_enabled():
        await callback.answer(t("feature_disabled", lang), show_alert=True)
        return
    try:
        _, gen_id_str, count_str = callback.data.split(":")
        gen_id = int(gen_id_str)
        count = int(count_str)
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    gen = await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("prompt") or gen.get("user_id")!=callback.from_user.id:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    free_lim, prem_lim = await ff.batch_limits()
    is_prem = await db.is_premium(callback.from_user.id)
    max_allowed = prem_lim if is_prem else free_lim
    count = max(1, min(max_allowed, count))
    await callback.answer(t("batch_generating", lang, n=count, used=0, limit=0)[:30])
    await _do_batch(callback.message, gen["prompt"], count)
