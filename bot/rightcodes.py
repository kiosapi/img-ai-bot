"""Right Codes provider — Privacy: NEVER leak Right Codes / RC / provider name to user.

All user-facing errors must be generic Indonesian.
Internal task_id/log may still use provider but not returned to end user.
"""

import asyncio
import base64
import httpx
import re
from typing import Optional

REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DOWNLOAD_TIMEOUT = httpx.Timeout(90.0, connect=10.0)
POLL_INTERVAL = 2.5
POLL_MAX = 500


class RightCodesError(Exception):
    pass


def _site_base(draw_base: str) -> str:
    b = draw_base.rstrip("/")
    if b.endswith("/draw"):
        return b[:-5]
    if "/draw" in b:
        return b.split("/draw")[0]
    return b


async def _download_image(url: str) -> bytes:
    last_err = ""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as dl:
                r = await dl.get(url)
                if r.status_code == 200 and len(r.content) > 800:
                    return r.content
                last_err = f"HTTP {r.status_code}"
        except Exception as e:
            last_err = str(e)[:200]
        await asyncio.sleep(1.0 * (attempt + 1))
    raise RightCodesError(f"Gagal mengunduh hasil gambar, coba lagi ya. ({last_err})")


def _extract_url_from_text(text: str) -> str | None:
    if not text:
        return None
    t = text.strip()
    if t.startswith("http://") or t.startswith("https://"):
        return t.split()[0].strip().strip('"').strip("'").rstrip(".,)")
    m = re.search(r"https?://[^\s\"']+\.(?:png|jpg|jpeg|webp|gif)", t, re.I)
    if m:
        return m.group(0)
    m = re.search(r"https?://\S+", t)
    if m:
        return m.group(0).strip().strip('"').strip("'").rstrip(".,)")
    return None


def _try_parse_completed(pj: dict) -> str | None:
    data = pj.get("data")
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, dict):
            url = first.get("url") or first.get("image_url")
            if url:
                return url
            b64 = first.get("b64_json")
            if b64:
                return f"b64:{b64[:20]}"
        elif isinstance(first, str) and first.startswith("http"):
            return first

    candidates = pj.get("candidates")
    if isinstance(candidates, list) and candidates:
        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            content = cand.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else []
            for part in parts:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if text:
                    url = _extract_url_from_text(text)
                    if url:
                        return url
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and isinstance(inline, dict):
                    b64d = inline.get("data")
                    if b64d:
                        return f"b64inline:{b64d[:20]}"

    if pj.get("url"):
        u = pj["url"]
        if isinstance(u, str) and u.startswith("http"):
            return u

    for key in ("result", "output", "response"):
        val = pj.get(key)
        if isinstance(val, dict):
            if val.get("url"):
                return val["url"]
            if "data" in val and isinstance(val["data"], list) and val["data"]:
                first = val["data"][0]
                if isinstance(first, dict) and first.get("url"):
                    return first["url"]
        if isinstance(val, list) and val:
            first = val[0]
            if isinstance(first, dict) and first.get("url"):
                return first["url"]
            if isinstance(first, str) and first.startswith("http"):
                return first
    return None


async def _download_from_completed_payload(pj: dict) -> bytes | None:
    data = pj.get("data")
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        if isinstance(first, dict):
            if "b64_json" in first and first["b64_json"]:
                try:
                    return base64.b64decode(first["b64_json"])
                except Exception:
                    pass
            url = first.get("url") or first.get("image_url")
            if url:
                return await _download_image(url)
        elif isinstance(first, str) and first.startswith("http"):
            return await _download_image(first)

    candidates = pj.get("candidates") or []
    for cand in candidates:
        if not isinstance(cand, dict):
            continue
        content = cand.get("content", {})
        parts = content.get("parts", []) if isinstance(content, dict) else []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if text:
                url = _extract_url_from_text(text)
                if url:
                    return await _download_image(url)
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and isinstance(inline, dict):
                b64d = inline.get("data")
                if b64d:
                    try:
                        return base64.b64decode(b64d)
                    except Exception:
                        continue

    if pj.get("url") and isinstance(pj["url"], str) and pj["url"].startswith("http"):
        return await _download_image(pj["url"])

    return None


async def _submit_images(
    client: httpx.AsyncClient,
    gen_url: str,
    headers: dict,
    model_id: str,
    prompt: str,
    size: str,
    image_size: str | None,
    ref_images_b64: list[bytes] | None,
) -> str:
    payload: dict = {
        "model": model_id,
        "prompt": prompt,
        "n": 1,
        "size": size or "1:1",
        "async": True,
    }
    if image_size:
        payload["imageSize"] = image_size
    if ref_images_b64:
        payload["image"] = [f"data:image/png;base64,{base64.b64encode(b).decode()}" for b in ref_images_b64]

    resp = await client.post(gen_url, json=payload, headers=headers)
    if resp.status_code != 200:
        # Generic — never leak raw body which may contain provider name
        raise RightCodesError(f"Layanan AI sibuk ({resp.status_code}), coba lagi.")
    j = resp.json()
    task_id = j.get("task_id") or j.get("id")
    if not task_id:
        if "data" in j:
            maybe = await _download_from_completed_payload(j)
            if maybe:
                raise _ImmediateResult(maybe)
        raise RightCodesError("Gagal membuat tugas gambar, coba lagi.")
    return task_id


class _ImmediateResult(Exception):
    def __init__(self, img_bytes: bytes):
        self.img_bytes = img_bytes


async def _submit_gemini(
    client: httpx.AsyncClient,
    draw_base: str,
    headers: dict,
    model_id: str,
    prompt: str,
    size: str,
    image_size: str | None,
    ref_images_b64: list[bytes] | None,
) -> str:
    url = f"{draw_base.rstrip('/')}/v1beta/models/{model_id}:generateContent"

    aspect = size or "1:1"
    if "x" in aspect.lower():
        if "1024x1024" in aspect:
            aspect = "1:1"
        elif "1024x1536" in aspect or "9:16" in aspect:
            aspect = "9:16"
        elif "1536x1024" in aspect or "16:9" in aspect:
            aspect = "16:9"
        else:
            aspect = "1:1"

    parts: list[dict] = [{"text": prompt}]
    if ref_images_b64:
        for b in ref_images_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/png",
                    "data": base64.b64encode(b).decode()
                }
            })

    payload: dict = {
        "async": True,
        "contents": [{"role": "user", "parts": parts}],
    }
    gc: dict = {}
    ic: dict = {}
    if aspect:
        ic["aspectRatio"] = aspect
    if image_size:
        ic["imageSize"] = image_size
    if ic:
        gc["imageConfig"] = ic
    if gc:
        payload["generationConfig"] = gc

    resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code != 200:
        raise RightCodesError(f"Layanan AI sibuk ({resp.status_code}), coba lagi.")
    j = resp.json()
    task_id = j.get("task_id") or j.get("id")
    if not task_id:
        maybe = await _download_from_completed_payload(j)
        if maybe:
            raise _ImmediateResult(maybe)
        raise RightCodesError("Gagal membuat tugas gambar, coba lagi.")
    return task_id


async def generate_image(
    api_key: str,
    base_url: str,
    model_id: str,
    prompt: str,
    size: str = "1:1",
    image_size: str | None = None,
    ref_images_b64: list[bytes] | None = None,
) -> bytes:
    draw_base = base_url.rstrip("/")
    if not draw_base.endswith("/draw") and "/draw" not in draw_base:
        draw_base = draw_base + "/draw"
    site_base = _site_base(draw_base)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    is_gemini_family = model_id.lower().startswith("nano-banana") or "gemini" in model_id.lower()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        task_id: str | None = None
        try:
            if is_gemini_family:
                try:
                    task_id = await _submit_gemini(client, draw_base, headers, model_id, prompt, size, image_size, ref_images_b64)
                except RightCodesError as e:
                    if "404" in str(e) or "not found" in str(e).lower():
                        gen_url = f"{draw_base}/v1/images/generations"
                        task_id = await _submit_images(client, gen_url, headers, model_id, prompt, size, image_size, ref_images_b64)
                    else:
                        raise
            else:
                gen_url = f"{draw_base}/v1/images/generations"
                task_id = await _submit_images(client, gen_url, headers, model_id, prompt, size, image_size, ref_images_b64)
        except _ImmediateResult as imm:
            return imm.img_bytes

    # poll
    poll_url = f"{site_base.rstrip('/')}/v1/tasks/{task_id}"
    poll_headers = {"Authorization": f"Bearer {api_key}"}
    start = asyncio.get_event_loop().time()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > POLL_MAX:
                raise RightCodesError(f"Layanan AI timeout setelah {POLL_MAX}s, coba lagi. Gambar mungkin sudah jadi di dashboard provider.")

            try:
                pr = await client.get(poll_url, headers=poll_headers)
            except Exception:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            if pr.status_code != 200:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            try:
                pj = pr.json()
            except Exception:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            try:
                maybe = await _download_from_completed_payload(pj)
                if maybe:
                    return maybe
            except RightCodesError:
                raise
            except Exception:
                pass

            status = (pj.get("status") or "").lower()

            if status == "completed":
                img = await _download_from_completed_payload(pj)
                if img:
                    return img
                raise RightCodesError("Gambar selesai tapi gagal diparse, coba lagi.")

            if status == "failed":
                err = pj.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                if not msg:
                    msg = pj.get("message") or "Gagal"
                # Generic — strip provider detail
                raise RightCodesError(f"Gagal generate: {str(msg)[:300]}")

            await asyncio.sleep(POLL_INTERVAL)


async def list_models(api_key: str, base_url: str) -> list[dict]:
    draw_base = base_url.rstrip("/")
    if not draw_base.endswith("/draw") and "/draw" not in draw_base:
        draw_base = draw_base + "/draw"
    site_base = _site_base(draw_base)

    candidates = [
        f"{draw_base}/v1/models",
        f"{site_base}/v1/models",
        f"{draw_base}/models",
        f"{site_base}/models",
    ]
    headers = {"Authorization": f"Bearer {api_key}"}
    last_err = ""
    for url in candidates:
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                j = resp.json()
                if isinstance(j, dict) and "data" in j and isinstance(j["data"], list):
                    return j["data"]
                if isinstance(j, list):
                    return j
                return [j]
            last_err = f"{resp.status_code}"
        except Exception as e:
            last_err = str(e)[:200]
            continue
    raise RightCodesError(f"Gagal ambil daftar model: {last_err}")
