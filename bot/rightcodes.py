"""Right Codes provider client — async flow per https://docs.right.codes/docs/rc_draw/

- POST https://www.right.codes/draw/v1/images/generations {model, prompt, n, size, imageSize, image:[dataURLs], async:true}
- -> {"task_id": "..."}
- GET https://www.right.codes/v1/tasks/{task_id}
- statuses: queued/in_progress -> poll, completed -> data, failed -> error
"""
import asyncio
import base64
import httpx
from typing import Optional

REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DOWNLOAD_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
POLL_INTERVAL = 2.5
POLL_MAX = 300  # 5 min


class RightCodesError(Exception):
    pass


def _site_base(draw_base: str) -> str:
    b = draw_base.rstrip("/")
    if b.endswith("/draw"):
        return b[:-5]
    # if contains /draw somewhere, strip suffix from /draw onwards
    if "/draw" in b:
        return b.split("/draw")[0]
    return b


async def _resolve_task(api_key: str, task_id: str, site_base: str) -> dict:
    url = f"{site_base.rstrip('/')}/v1/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code != 200:
        raise RightCodesError(f"task poll {resp.status_code}: {resp.text[:400]}")
    try:
        return resp.json()
    except Exception as e:
        raise RightCodesError(f"poll json parse: {e}")


async def generate_image(
    api_key: str,
    base_url: str,
    model_id: str,
    prompt: str,
    size: str = "1:1",
    image_size: str | None = None,
    ref_images_b64: list[bytes] | None = None,
) -> bytes:
    """
    base_url: https://www.right.codes/draw  (draw-level)
    size: for Right Codes expected format: 1:1, 16:9, 9:16, 4:3 or 1024x1024 etc — we translate.
    image_size: optional 1K/2K/4K for nano-banana / gpt-image vip
    ref_images_b64: optional list of png bytes -> data URL array
    """
    draw_base = base_url.rstrip("/")
    if not draw_base.endswith("/draw") and "/draw" not in draw_base:
        draw_base = draw_base + "/draw"
    site_base = _site_base(draw_base)
    gen_url = f"{draw_base}/v1/images/generations"

    # size mapping: if bot uses 1024x1024 etc, keep as is OR map to ratio if requested.
    # Doc says supports both ratio and pixel string. We'll pass through as-is but map common:
    rc_size = size
    # If pixel like 1024x1024 -> keep, but some models prefer ratio. Keep pixel for compat.
    # If empty, default 1:1
    if not rc_size:
        rc_size = "1:1"

    payload: dict = {
        "model": model_id,
        "prompt": prompt,
        "n": 1,
        "size": rc_size,
        "async": True,
    }
    if image_size:
        payload["imageSize"] = image_size
    if ref_images_b64:
        data_urls = []
        for b in ref_images_b64:
            data_urls.append(f"data:image/png;base64,{base64.b64encode(b).decode()}")
        payload["image"] = data_urls

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # submit
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(gen_url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise RightCodesError("Right Codes timeout submit")
    except httpx.HTTPError as e:
        raise RightCodesError(f"Right Codes connect fail: {e}")

    if resp.status_code != 200:
        raise RightCodesError(f"Right Codes {resp.status_code}: {resp.text[:500]}")

    try:
        j = resp.json()
        task_id = j.get("task_id") or j.get("id")
        if not task_id:
            # maybe sync response already contains image
            if "data" in j and isinstance(j["data"], list) and len(j["data"]) > 0:
                first = j["data"][0]
                if "b64_json" in first:
                    return base64.b64decode(first["b64_json"])
                if "url" in first:
                    url = first["url"]
                    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as dl:
                        r = await dl.get(url)
                        return r.content
            raise RightCodesError(f"No task_id: {str(j)[:500]}")
    except RightCodesError:
        raise
    except Exception as e:
        raise RightCodesError(f"Submit parse fail {e}: {resp.text[:300]}")

    # poll
    start = asyncio.get_event_loop().time()
    poll_url = f"{site_base.rstrip('/')}/v1/tasks/{task_id}"
    poll_headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > POLL_MAX:
                raise RightCodesError(f"Timeout polling task {task_id} after {POLL_MAX}s")

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

            status = (pj.get("status") or "").lower()

            if status == "completed":
                # Try Images shape
                data = pj.get("data") or pj.get("result") or pj.get("output") or []
                # data can be list or dict
                if isinstance(data, dict):
                    # may contain images array or data
                    if "images" in data:
                        data = data["images"]
                    elif "data" in data:
                        data = data["data"]

                if isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    if isinstance(first, dict):
                        if "b64_json" in first:
                            return base64.b64decode(first["b64_json"])
                        if "url" in first and first["url"]:
                            url = first["url"]
                            async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as dl:
                                r = await dl.get(url)
                                if r.status_code == 200:
                                    return r.content
                        if "image_url" in first and first["image_url"]:
                            url = first["image_url"]
                            async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as dl:
                                r = await dl.get(url)
                                return r.content
                    elif isinstance(first, str) and first.startswith("http"):
                        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as dl:
                            r = await dl.get(first)
                            return r.content

                # also try direct url in top-level
                if pj.get("url"):
                    async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT) as dl:
                        r = await dl.get(pj["url"])
                        return r.content

                # try candidates path for gemini? But we are Images path
                candidates = pj.get("candidates") or []
                if candidates and isinstance(candidates, list):
                    for c in candidates:
                        # generic fallback
                        if isinstance(c, dict):
                            # check content parts
                            content = c.get("content", {})
                            parts = content.get("parts", []) if isinstance(content, dict) else []
                            for part in parts:
                                if isinstance(part, dict) and "inlineData" in part:
                                    inline = part["inlineData"]
                                    b64data = inline.get("data")
                                    if b64data:
                                        return base64.b64decode(b64data)

                raise RightCodesError(f"Completed but no image parseable: {str(pj)[:1200]}")

            elif status == "failed":
                err = pj.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                if not msg:
                    msg = pj.get("message") or str(pj)[:500]
                raise RightCodesError(f"Task failed: {msg}")

            # queued / in_progress
            await asyncio.sleep(POLL_INTERVAL)


async def list_models(api_key: str, base_url: str) -> list[dict]:
    """
    Try to list models — Right Codes may expose /v1/models at draw-level or site-level.
    Returns list of {id, display_name?}
    """
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
                # wrap
                return [j]
            last_err = f"{url} {resp.status_code} {resp.text[:200]}"
        except Exception as e:
            last_err = f"{url} {e}"
            continue
    raise RightCodesError(f"list_models failed: {last_err}")

