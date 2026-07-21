"""Text-to-image generation: production batch 1/2/4, negative, seed, ref photo, gallery — atomic quota fix."""
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
import io, uuid, random, asyncio

import db
import ui
import styles as style_presets
import feature_flags as ff
import texts as dyn_texts
from i18n import t
from config import DEFAULT_DAILY_LIMIT, ALLOWED_SIZES, DEFAULT_SIZE, ALLOWED_BATCHES, DEFAULT_BATCH
from tgutil import safe_edit, ProgressAnimator
from states import GenerateStates
from gen_queue import QUEUE

router = Router()

async def is_maintenance() -> bool:
    return (await db.get_setting("maintenance", "0")) == "1"

async def _size_of(uid: int) -> str:
    return await db.get_pref_size(uid, DEFAULT_SIZE)

async def _style_of(uid: int) -> str:
    return await db.get_pref_style(uid, "none") or "none"

async def _batch_of(uid: int) -> int:
    return await db.get_pref_batch(uid, DEFAULT_BATCH)

async def _neg_of(uid: int) -> str:
    return await db.get_pref_negative(uid)

async def _seed_of(uid: int) -> str | None:
    return await db.get_pref_seed(uid)

async def _ref_file_id_of(uid: int) -> str | None:
    return await db.get_pref_ref_file_id(uid)

async def _apply_user_style(uid: int, prompt: str) -> tuple[str, str]:
    sid = await _style_of(uid)
    try:
        # TODO: prefer DB custom_styles if available
        # try DB apply, fallback to hardcoded
        applied = await db.apply_custom_style(prompt, sid)
        return applied, sid
    except Exception:
        return style_presets.apply_style(prompt, sid), sid

async def check_and_consume_multi(uid: int, n: int) -> tuple[bool,int,int]:
    ok, used, limit, _ = await db.check_and_consume_multi(uid, DEFAULT_DAILY_LIMIT, n)
    return ok, used, limit

async def check_and_consume(uid: int) -> tuple[bool,int,int]:
    ok, used, limit, _ = await db.check_and_consume_atomic(uid, DEFAULT_DAILY_LIMIT)
    return ok, used, limit

@router.message(Command("size"))
async def cmd_size(message: Message):
    lang = await db.get_lang(message.from_user.id)
    cur = await _size_of(message.from_user.id)
    await message.answer(t("size_pick", lang), reply_markup=ui.size_menu(cur, lang))

@router.callback_query(F.data.startswith("size:"))
async def set_size(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    size = callback.data.split(":",1)[1]
    if size in ALLOWED_SIZES:
        await db.set_pref_size(callback.from_user.id, size)
        await safe_edit(callback.message, t("size_set", lang, size=size), reply_markup=ui.back_menu(lang))
    await callback.answer(t("saved", lang))

@router.message(Command("batch"))
async def cmd_batch(message: Message):
    lang = await db.get_lang(message.from_user.id)
    parts = message.text.split(maxsplit=2)
    if len(parts)>=2 and parts[1].isdigit() and int(parts[1]) in ALLOWED_BATCHES:
        if len(parts)==3 and parts[2].strip():
            await db.set_pref_batch(message.from_user.id, int(parts[1]))
            await _do_generate(message, parts[2].strip(), batch_override=int(parts[1]))
            return
        await db.set_pref_batch(message.from_user.id, int(parts[1]))
        cur = await _batch_of(message.from_user.id)
        await message.answer(t("batch_set", lang, n=cur), reply_markup=ui.back_menu(lang))
        return
    cur = await _batch_of(message.from_user.id)
    await message.answer(t("batch_pick", lang), reply_markup=ui.batch_menu(cur, lang))

@router.callback_query(F.data.regexp(r"^batch:[12]$|^batch:4$"))
async def set_batch(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    try:
        b = int(callback.data.split(":")[1])
    except Exception:
        b = DEFAULT_BATCH
    if b in ALLOWED_BATCHES:
        await db.set_pref_batch(callback.from_user.id, b)
        await safe_edit(callback.message, t("batch_set", lang, n=b), reply_markup=ui.back_menu(lang))
    await callback.answer(t("saved", lang))

@router.callback_query(F.data=="menu:batch")
async def menu_batch(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    cur = await _batch_of(callback.from_user.id)
    await safe_edit(callback.message, t("batch_pick", lang), reply_markup=ui.batch_menu(cur, lang))
    await callback.answer()

@router.callback_query(F.data=="menu:adv")
async def menu_adv(callback: CallbackQuery):
    lang = await db.get_lang(callback.from_user.id)
    neg = await _neg_of(callback.from_user.id)
    seed = await _seed_of(callback.from_user.id)
    ref = await _ref_file_id_of(callback.from_user.id)
    text = t("adv_title", lang)
    await safe_edit(callback.message, text, reply_markup=ui.adv_menu(lang, has_negative=bool(neg), has_seed=bool(seed), has_ref=bool(ref)))
    await callback.answer()

@router.callback_query(F.data.startswith("adv:"))
async def cb_adv(callback: CallbackQuery, state: FSMContext):
    lang = await db.get_lang(callback.from_user.id)
    action = callback.data.split(":",1)[1]
    if action=="neg":
        await state.set_state(GenerateStates.waiting_negative)
        await callback.message.answer(t("adv_neg_ask", lang))
        await callback.answer()
    elif action=="seed":
        await state.set_state(GenerateStates.waiting_seed)
        await callback.message.answer(t("adv_seed_ask", lang))
        await callback.answer()
    elif action=="ref":
        await state.set_state(GenerateStates.waiting_ref_photo)
        await callback.message.answer(t("adv_ref_ask", lang))
        await callback.answer()
    elif action=="clear":
        await db.set_pref_negative(callback.from_user.id, "")
        await db.set_pref_seed(callback.from_user.id, None)
        await db.set_pref_ref_file_id(callback.from_user.id, None)
        await safe_edit(callback.message, t("adv_cleared", lang), reply_markup=ui.back_menu(lang))
        await callback.answer(t("cleared", lang))

async def _do_generate(message: Message, prompt: str, variation: bool=False, force_size: str | None=None, enhance: bool=False, batch_override: int | None=None):
    lang = await db.get_lang(message.from_user.id)
    queue_status_msg = None
    if (await db.get_setting("feat_queue_enabled","1"))=="1":
        if QUEUE.is_busy(message.from_user.id):
            busy_dyn = await dyn_texts.get_dynamic_text_or_none("busy_msg")
            msg_busy = busy_dyn if busy_dyn else t("busy_generating", lang)
            await message.answer(msg_busy, reply_markup=ui.back_menu(lang))
            return
        queue_status_msg = await message.answer(t("queue_joining", lang))

        async def _on_wait(pos: int, eta: int):
            if not queue_status_msg:
                return
            try:
                if pos <= 0:
                    txt = t("queue_running", lang, eta=eta)
                else:
                    txt = t("queue_pos", lang, pos=pos, eta=eta)
                await queue_status_msg.edit_text(txt)
            except Exception:
                pass

        ok_q = await QUEUE.acquire(message.from_user.id, on_wait=_on_wait)
        if not ok_q:
            try:
                await queue_status_msg.edit_text(t("queue_timeout", lang), reply_markup=ui.back_menu(lang))
            except Exception:
                await message.answer(t("queue_timeout", lang), reply_markup=ui.back_menu(lang))
            return
        try:
            await queue_status_msg.edit_text(t("queue_running", lang, eta=QUEUE.eta_sec(message.from_user.id)))
        except Exception:
            pass
    if await is_maintenance():
        if (await db.get_setting("feat_queue_enabled","1"))=="1":
            await QUEUE.release(message.from_user.id)
        maint_dyn = await dyn_texts.get_dynamic_text_or_none("maintenance_msg")
        await message.answer(maint_dyn if maint_dyn else t("maintenance", lang))
        return

    batch = batch_override or await _batch_of(message.from_user.id)
    if batch not in ALLOWED_BATCHES:
        batch = 1
    size = force_size or await _size_of(message.from_user.id)
    negative = await _neg_of(message.from_user.id)
    seed = await _seed_of(message.from_user.id)
    ref_file_id = await _ref_file_id_of(message.from_user.id)

    try:
        active_model = await db.get_active_model_for_user(message.from_user.id)
    except Exception:
        active_model = None

    final_prompt = prompt
    if enhance:
        if not await ff.enhance_enabled():
            enhance=False
        else:
            try:
                from enhancer import enhance_prompt
                en = await enhance_prompt(prompt)
                if en and len(en.strip())>5:
                    final_prompt=en
            except Exception:
                pass

    styled_prompt, style_id = await _apply_user_style(message.from_user.id, final_prompt)
    if variation:
        hints=["different angle","different lighting","slightly different composition","alternative perspective","with slight variation"]
        styled_prompt=f"{styled_prompt}, {random.choice(hints)}"

    try:
        from watermark import should_watermark, apply_watermark_image
        wm_on, wm_text = await should_watermark(message.from_user.id)
        # force modern text only
        if wm_text and "Buat di" in wm_text:
            wm_text="@imgaai_bot"
    except Exception:
        wm_on, wm_text=False, ""

    ref_bytes: bytes | None = None
    if ref_file_id:
        try:
            buf=io.BytesIO()
            await message.bot.download(ref_file_id, destination=buf)
            ref_bytes=buf.getvalue()
        except Exception:
            ref_bytes=None

    batch_id = str(uuid.uuid4()) if batch>1 else None

        # --- moderation check (Phase3-7) ---
    try:
        import moderation as mod_checker
        blocked, rule, severity, matched = await mod_checker.check_prompt(final_prompt)
        sev_lower = (severity or "").lower() if severity else ""
        if blocked and rule:
            dyn_nsfw = await dyn_texts.get_dynamic_text_or_none("nsfw_msg")
            dyn_banned = await dyn_texts.get_dynamic_text_or_none("banned_msg")
            if dyn_nsfw and sev_lower in ("nsfw","block","high"):
                msg_text = dyn_nsfw
            elif dyn_banned:
                msg_text = dyn_banned
            else:
                msg_text = t(
                    "moderation_blocked",
                    lang,
                    severity=severity or "block",
                    matched=(matched or "")[:80],
                )
            try:
                await mod_checker.log_block(message.from_user.id, final_prompt, rule, matched or "", severity or "block")
            except Exception:
                pass
            await message.answer(msg_text, reply_markup=ui.back_menu(lang))
            if (await db.get_setting("feat_queue_enabled","1"))=="1":
                await QUEUE.release(message.from_user.id)
            return
        if rule and matched:
            try:
                await mod_checker.log_block(message.from_user.id, final_prompt, rule, matched or "", severity or "warn")
            except Exception:
                pass
    except Exception:
        pass

    # ATOMIC reservation upfront
    ok_batch, used_batch, limit_batch = await check_and_consume_multi(message.from_user.id, batch)
    if not ok_batch:
        # dynamic quota_exhausted_msg override
        q_dyn = await dyn_texts.get_dynamic_text_or_none("quota_exhausted_msg")
        if q_dyn:
            try:
                q_text = q_dyn.format(used=used_batch, limit=limit_batch, bar=ui.quota_bar(used_batch, limit_batch))
            except Exception:
                q_text = q_dyn
        else:
            q_text = t("quota_exhausted", lang, used=used_batch, limit=limit_batch, bar=ui.quota_bar(used_batch, limit_batch))
        await message.answer(q_text, reply_markup=ui.back_menu(lang))
        if (await db.get_setting("feat_queue_enabled","1"))=="1":
            await QUEUE.release(message.from_user.id)
        return

    gen_base = t("generating", lang, used=used_batch, limit=limit_batch)
    if queue_status_msg is not None:
        status = queue_status_msg
        try:
            await status.edit_text(gen_base + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
        except Exception:
            status = await message.answer(gen_base + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    else:
        status = await message.answer(gen_base + "\n▱▱▱▱▱▱▱▱▱▱  ⏱️ 0s")
    animator = ProgressAnimator(message.bot, message.chat.id, status, gen_base)
    animator.start()
    produced=0
    try:
        from providers import generate_image as provider_generate
        for idx in range(batch):
            cur_seed=seed
            if batch>1 and seed:
                try:
                    cur_seed=str(int(seed)+idx)
                except Exception:
                    pass
            p_prompt=styled_prompt
            if batch>1 and not seed:
                p_prompt=f"{styled_prompt} -- variation {idx+1}"
            try:
                img_bytes = await provider_generate(
                    active_model, p_prompt, size=size, user_id=message.from_user.id,
                    negative=negative, seed=cur_seed,
                    ref_images_b64=[ref_bytes] if ref_bytes else None
                )
            except Exception as e:
                err=str(e)[:500]
                try:
                    async with db._pool.acquire() as con:
                        await con.execute("INSERT INTO generations (user_id,kind,prompt,size,success,style_id,model_id,batch_id,negative_prompt,seed,ref_file_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id",
                                          message.from_user.id,"generate",final_prompt,size,False,style_id if style_id!="none" else None, active_model["id"] if active_model else None, batch_id, negative or None, cur_seed, ref_file_id)
                except Exception:
                    await db.log_generation(message.from_user.id,"generate",final_prompt,size,False)
                if idx==0:
                    await message.answer(t("gen_failed", lang, err=err), reply_markup=ui.back_menu(lang))
                    return
                continue

            if wm_on and wm_text:
                try:
                    img_bytes=apply_watermark_image(img_bytes, wm_text)
                except Exception:
                    pass

            model_label=""
            if active_model:
                try:
                    from model_display import format_model_label
                    model_label=format_model_label(active_model.get("provider_id",""), active_model.get("external_id") or active_model.get("id",""), active_model.get("display_name"))
                except Exception:
                    model_label=active_model.get("display_name") or ""

            if batch==1:
                cap=t("gen_done", lang, prompt=final_prompt[:200], size=size, left=ui.sisa_text(used_batch, limit_batch, lang))
                if negative:
                    cap += "\nNeg: " + negative[:80]
                if seed:
                    cap += "\nSeed: " + str(seed)
                if ref_file_id:
                    cap += "\nRef: ON"
                if model_label:
                    cap += "\nModel: " + model_label
                # watermark only on image pixels — never duplicate in caption
                sent=await message.answer_photo(BufferedInputFile(img_bytes, filename="image.png"), caption=cap, reply_markup=ui.result_menu(lang, gen_id=0))
            else:
                cap=t("batch_done_item", lang, idx=idx+1, total=batch, prompt=final_prompt[:120], size=size) + "\n" + ui.sisa_text(used_batch, limit_batch, lang)
                if model_label:
                    cap += "\nModel: " + model_label
                sent=await message.answer_photo(BufferedInputFile(img_bytes, filename=f"image_{idx+1}.png"), caption=cap, reply_markup=ui.result_menu(lang, gen_id=0))

            try:
                rfid=sent.photo[-1].file_id
            except Exception:
                rfid=None
            try:
                async with db._pool.acquire() as con:
                    gen_id=await con.fetchval("INSERT INTO generations (user_id,kind,prompt,size,success,result_file_id,style_id,model_id,batch_id,negative_prompt,seed,ref_file_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING id",
                                              message.from_user.id,"generate",final_prompt,size,True,rfid,style_id if style_id!="none" else None, active_model["id"] if active_model else None, batch_id, negative or None, cur_seed, ref_file_id)
            except Exception:
                gen_id=await db.log_generation(message.from_user.id,"generate",final_prompt,size,True,result_file_id=rfid, style_id=style_id if style_id!="none" else None)
            if rfid and gen_id:
                try:
                    await sent.edit_caption(caption=cap, reply_markup=ui.result_menu(lang, gen_id=gen_id, file_id=rfid))
                except Exception:
                    pass
            produced+=1
            if batch>1 and idx<batch-1:
                await asyncio.sleep(1.2)
        if batch>1 and produced>0:
            await message.answer(t("batch_done", lang, n=produced), reply_markup=ui.back_menu(lang))
    except Exception as e:
        try:
            await db.log_generation(message.from_user.id,"generate",final_prompt,size,False)
        except Exception:
            pass
        await message.answer(t("gen_failed", lang, err=str(e)[:500]), reply_markup=ui.back_menu(lang))
    finally:
        if (await db.get_setting("feat_queue_enabled","1"))=="1":
            await QUEUE.release(message.from_user.id)
        try:
            await animator.stop()
            await status.delete()
        except Exception:
            pass

@router.message(Command("generate"))
async def cmd_generate(message: Message):
    prompt=message.text.partition(" ")[2].strip()
    if not prompt:
        await message.answer(ui.prompt_ask(await db.get_lang(message.from_user.id)))
        return
    enhance=False
    if prompt.startswith("✨ "):
        enhance=True
        prompt=prompt[2:].strip()
    await _do_generate(message, prompt, enhance=enhance)

@router.message(Command("enhance"))
async def cmd_enhance(message: Message):
    lang=await db.get_lang(message.from_user.id)
    if not await ff.enhance_enabled():
        await message.answer(t("feature_disabled", lang), reply_markup=ui.back_menu(lang))
        return
    prompt=message.text.partition(" ")[2].strip()
    if not prompt:
        await message.answer(t("enhance_doing", lang)+"\n\n"+ui.prompt_ask(lang))
        return
    await _do_generate(message, prompt, enhance=True)

@router.callback_query(F.data.startswith("enhance:"))
async def cb_enhance(callback: CallbackQuery):
    lang=await db.get_lang(callback.from_user.id)
    if not await ff.enhance_enabled():
        await callback.answer(t("feature_disabled", lang), show_alert=True)
        return
    try:
        gen_id=int(callback.data.split(":")[1])
    except Exception:
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    gen=await db.get_generation_by_id(gen_id)
    if not gen or not gen.get("prompt"):
        await callback.answer(t("invalid_data", lang), show_alert=True)
        return
    await callback.answer("Enhancing...")
    await _do_generate(callback.message, gen["prompt"], enhance=True)

@router.message(GenerateStates.waiting_prompt, F.text, ~F.text.startswith("/"))
async def fsm_prompt(message: Message, state: FSMContext):
    data=await state.get_data()
    await state.clear()
    await _do_generate(message, message.text.strip(), enhance=data.get("enhance", False))

@router.message(GenerateStates.waiting_negative, F.text)
async def fsm_negative(message: Message, state: FSMContext):
    lang=await db.get_lang(message.from_user.id)
    txt=message.text.strip()
    if txt in ("/clear","/hapus","clear"):
        await db.set_pref_negative(message.from_user.id, "")
        await state.clear()
        await message.answer(t("adv_cleared", lang), reply_markup=ui.back_menu(lang))
        return
    # sanitize negative: strip html tags
    import re
    txt=re.sub(r"<[^>]+>", "", txt)[:500]
    await db.set_pref_negative(message.from_user.id, txt)
    await state.clear()
    await message.answer(t("adv_neg_saved", lang, val=txt[:100] if "val" in t("adv_neg_saved", lang) else txt[:100]), reply_markup=ui.back_menu(lang))

@router.message(GenerateStates.waiting_seed, F.text)
async def fsm_seed(message: Message, state: FSMContext):
    lang=await db.get_lang(message.from_user.id)
    txt=message.text.strip()
    if txt.lower() in ("/clear","/random","/hapus","random","clear"):
        await db.set_pref_seed(message.from_user.id, None)
        await state.clear()
        await message.answer(t("adv_seed_cleared", lang), reply_markup=ui.back_menu(lang))
        return
    seed_val="".join([c for c in txt if c.isdigit()])[:16] or txt[:32]
    await db.set_pref_seed(message.from_user.id, seed_val)
    await state.clear()
    await message.answer(t("adv_seed_saved", lang, seed=seed_val), reply_markup=ui.back_menu(lang))

@router.message(GenerateStates.waiting_ref_photo, F.photo)
async def fsm_ref_photo(message: Message, state: FSMContext):
    lang=await db.get_lang(message.from_user.id)
    fid=message.photo[-1].file_id
    await db.set_pref_ref_file_id(message.from_user.id, fid)
    await state.clear()
    await message.answer(t("adv_ref_saved", lang), reply_markup=ui.back_menu(lang))

@router.message(GenerateStates.waiting_ref_photo, F.text)
async def fsm_ref_clear(message: Message, state: FSMContext):
    lang=await db.get_lang(message.from_user.id)
    if message.text.strip().lower() in ("/clear","/hapus","clear","hapus"):
        await db.set_pref_ref_file_id(message.from_user.id, None)
        await state.clear()
        await message.answer(t("adv_ref_cleared", lang), reply_markup=ui.back_menu(lang))
        return
    await message.answer(t("adv_ref_ask", lang))

@router.message(StateFilter(None), F.text, ~F.text.startswith("/"))
async def free_text_prompt(message: Message):
    # Avoid responding in groups for random chat
    if message.chat.type!="private":
        return
    await _do_generate(message, message.text.strip())
