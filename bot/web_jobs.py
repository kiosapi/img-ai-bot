"""Process web_gen_jobs from public imgaai web-app — shares GenQueue with Telegram."""
from __future__ import annotations

import asyncio
import base64
import logging
import uuid

import db
from gen_queue import QUEUE
from config import DEFAULT_DAILY_LIMIT, DEFAULT_SIZE, ALLOWED_SIZES

log = logging.getLogger(__name__)

_POLL = 1.5
_task: asyncio.Task | None = None


async def ensure_web_jobs_table():
    async with db._pool.acquire() as con:
        await con.execute(
            """
            CREATE TABLE IF NOT EXISTS web_gen_jobs (
                id TEXT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                prompt TEXT NOT NULL,
                size TEXT NOT NULL DEFAULT '1024x1024',
                style_code TEXT,
                status TEXT NOT NULL DEFAULT 'queued',
                position INT DEFAULT 0,
                eta_sec INT DEFAULT 0,
                error TEXT,
                result_b64 TEXT,
                gen_id BIGINT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                started_at TIMESTAMPTZ,
                finished_at TIMESTAMPTZ
            )
            """
        )
        await con.execute(
            "CREATE INDEX IF NOT EXISTS idx_web_gen_jobs_user ON web_gen_jobs(user_id, created_at DESC)"
        )
        await con.execute(
            "CREATE INDEX IF NOT EXISTS idx_web_gen_jobs_status ON web_gen_jobs(status) WHERE status IN ('queued','running')"
        )


async def _claim_next() -> dict | None:
    async with db._pool.acquire() as con:
        row = await con.fetchrow(
            """
            UPDATE web_gen_jobs j
            SET status = 'running', started_at = now()
            WHERE j.id = (
                SELECT id FROM web_gen_jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING id, user_id, prompt, size, style_code
            """
        )
        return dict(row) if row else None


async def _set_job(job_id: str, **fields):
    cols = []
    vals = []
    i = 1
    for k, v in fields.items():
        cols.append(f"{k}=${i}")
        vals.append(v)
        i += 1
    vals.append(job_id)
    sql = f"UPDATE web_gen_jobs SET {', '.join(cols)} WHERE id=${i}"
    async with db._pool.acquire() as con:
        await con.execute(sql, *vals)


async def _process_job(job: dict):
    job_id = job["id"]
    uid = int(job["user_id"])
    prompt = (job["prompt"] or "").strip()
    size = job["size"] if job["size"] in ALLOWED_SIZES else DEFAULT_SIZE
    style_code = job.get("style_code") or "none"

    if await db.get_setting("maintenance", "0") == "1":
        async with db._pool.acquire() as con:
            await con.execute(
                "UPDATE web_gen_jobs SET status='failed', error='maintenance', finished_at=now() WHERE id=$1",
                job_id,
            )
        return

    if await db.is_banned(uid):
        async with db._pool.acquire() as con:
            await con.execute(
                "UPDATE web_gen_jobs SET status='failed', error='banned', finished_at=now() WHERE id=$1",
                job_id,
            )
        return

    queue_on = (await db.get_setting("feat_queue_enabled", "1")) == "1"
    acquired = False
    if queue_on:
        if QUEUE.is_busy(uid):
            # re-queue later — put back to queued
            await _set_job(job_id, status="queued", started_at=None)
            return
        ok_q = await QUEUE.acquire(uid, timeout=600.0)
        if not ok_q:
            await _set_job(job_id, status="failed", error="queue_timeout")
            async with db._pool.acquire() as con:
                await con.execute(
                    "UPDATE web_gen_jobs SET finished_at=now() WHERE id=$1", job_id
                )
            return
        acquired = True
        await _set_job(
            job_id,
            position=0,
            eta_sec=QUEUE.eta_sec(uid),
            status="running",
        )

    try:
        # moderation
        try:
            import moderation as mod_checker

            blocked, rule, severity, matched = await mod_checker.check_prompt(prompt)
            if blocked and rule:
                await _set_job(
                    job_id,
                    status="failed",
                    error="moderation",
                )
                async with db._pool.acquire() as con:
                    await con.execute(
                        "UPDATE web_gen_jobs SET finished_at=now() WHERE id=$1", job_id
                    )
                return
        except Exception:
            pass

        ok, used, limit, _ = await db.check_and_consume_atomic(uid, DEFAULT_DAILY_LIMIT)
        if not ok:
            await _set_job(job_id, status="failed", error="quota")
            async with db._pool.acquire() as con:
                await con.execute(
                    "UPDATE web_gen_jobs SET finished_at=now() WHERE id=$1", job_id
                )
            return

        styled = prompt
        try:
            styled = await db.apply_custom_style(prompt, style_code)
        except Exception:
            try:
                import styles as style_presets

                styled = style_presets.apply_style(prompt, style_code)
            except Exception:
                styled = prompt

        try:
            active_model = await db.get_active_model_for_user(uid)
        except Exception:
            active_model = None

        from providers import generate_image as provider_generate

        img_bytes = await provider_generate(
            active_model, styled, size=size, user_id=uid
        )

        try:
            from watermark import should_watermark, apply_watermark_image

            wm_on, wm_text = await should_watermark(uid)
            if wm_text and "Buat di" in wm_text:
                wm_text = "@imgaai_bot"
            if wm_on and wm_text:
                img_bytes = apply_watermark_image(img_bytes, wm_text)
        except Exception:
            pass

        b64 = base64.b64encode(img_bytes).decode("ascii")
        gen_id = None
        try:
            gen_id = await db.log_generation(
                uid, "generate", prompt, size, True, style_id=style_code if style_code != "none" else None
            )
        except Exception:
            try:
                gen_id = await db.log_generation(uid, "generate", prompt, size, True)
            except Exception:
                pass

        # optional: push photo to user TG so file_id exists
        try:
            from aiogram import Bot
            from aiogram.types import BufferedInputFile
            import config

            bot = Bot(token=config.BOT_TOKEN)
            try:
                sent = await bot.send_photo(
                    uid,
                    BufferedInputFile(img_bytes, filename="imgaai.png"),
                    caption=f"Web generate\n{prompt[:180]}",
                )
                rfid = sent.photo[-1].file_id if sent.photo else None
                if rfid and gen_id:
                    await db.save_generation_result(gen_id, rfid)
            finally:
                await bot.session.close()
        except Exception as e:
            log.info("web job TG deliver skip: %s", e)

        async with db._pool.acquire() as con:
            await con.execute(
                """
                UPDATE web_gen_jobs
                SET status='done', result_b64=$2, gen_id=$3, finished_at=now(),
                    position=0, eta_sec=0, error=NULL
                WHERE id=$1
                """,
                job_id,
                b64,
                gen_id,
            )
        log.info("web job %s done user=%s", job_id, uid)
    except Exception as e:
        log.exception("web job %s fail", job_id)
        try:
            await db.log_generation(uid, "generate", prompt, size, False)
        except Exception:
            pass
        err = str(e)[:400]
        # never leak provider names
        for bad in ("cubence", "rightcodes", "apikey", "unity2", "openai"):
            if bad in err.lower():
                err = "generate_failed"
                break
        async with db._pool.acquire() as con:
            await con.execute(
                """
                UPDATE web_gen_jobs
                SET status='failed', error=$2, finished_at=now()
                WHERE id=$1
                """,
                job_id,
                err,
            )
    finally:
        if acquired:
            try:
                await QUEUE.release(uid)
            except Exception:
                pass


async def _loop():
    await ensure_web_jobs_table()
    log.info("web_jobs worker started")
    while True:
        try:
            job = await _claim_next()
            if job:
                await _process_job(job)
            else:
                await asyncio.sleep(_POLL)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.warning("web_jobs loop: %s", e)
            await asyncio.sleep(3)


def start_worker() -> asyncio.Task:
    global _task
    _task = asyncio.create_task(_loop())
    return _task


async def stop_worker():
    global _task
    if _task:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
