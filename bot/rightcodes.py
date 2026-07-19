"""Right Codes provider client — async flow per https://docs.right.codes/docs/rc_draw/

- POST https://www.right.codes/draw/v1/images/generations {model, prompt, n, size, imageSize, image:[dataURLs], async:true}
- -> {"task_id": "..."}
- GET https://www.right.codes/v1/tasks/{task_id}
- statuses: queued/in_progress -> poll, completed -> data (Images) or candidates (Gemini), failed -> error

Fixes:
- Gemini completed shape: candidates[].content.parts[].text = URL (not inlineData)
- Images completed shape: data:[{url: "https://cdn..."}] (not b64)
- robust download with retries
"""

import asyncio
import base64
import httpx
from typing import Optional

REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
DOWNLOAD_TIMEOUT = httpx.Timeout(90.0, connect=10.0)
POLL_INTERVAL = 3.0
POLL_MAX = 400  # 6.5 min to handle 46s+ queue per user report


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
    """Download with retries."""
    last_err = ""
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as dl:
                r = await dl.get(url)
                if r.status_code == 200 and len(r.content) > 1000:
                    return r.content
                last_err = f"HTTP {r.status_code} len {len(r.content)}"
        except Exception as e:
            last_err = str(e)
        await asyncio.sleep(1.0 * (attempt + 1))
    raise RightCodesError(f"Download failed {url[:80]}: {last_err}")


def _extract_url_from_text_maybe(text: str) -> str | None:
    if not text:
        return None
    t = text.strip()
    if t.startswith("http://") or t.startswith("https://"):
        # take first token if extra text
        return t.split()[0].strip().strip('"').strip("'")
    # maybe contains url inside markdown? try find https
    import re
    m = re.search(r"https?://[^\s\"']+\.(?:png|jpg|jpeg|webp|gif)", t, re.I)
    if m:
        return m.group(0)
    m = re.search(r"https?://\S+", t)
    if m:
        return m.group(0).strip().strip('"').strip("'").rstrip(".,)")
    return None


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
    gen_url = f"{draw_base}/v1/images/generations"

    rc_size = size or "1:1"

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

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(gen_url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise RightCodesError("Right Codes timeout submit")
    except httpx.HTTPError as e:
        raise RightCodesError(f"Right Codes connect fail: {e}")

    if resp.status_code != 200:
        raise RightCodesError(f"Right Codes {resp.status_code}: {resp.text[:800]}")

    try:
        j = resp.json()
        task_id = j.get("task_id") or j.get("id")
        if not task_id:
            # sync fallback maybe already contains image
            if "data" in j and isinstance(j["data"], list) and len(j["data"]) > 0:
                first = j["data"][0]
                if isinstance(first, dict):
                    if "b64_json" in first:
                        return base64.b64decode(first["b64_json"])
                    if "url" in first and first["url"]:
                        return await _download_image(first["url"])
            raise RightCodesError(f"No task_id: {str(j)[:800]}")
    except RightCodesError:
        raise
    except Exception as e:
        raise RightCodesError(f"Submit parse fail {e}: {resp.text[:400]}")

    # poll
    start = asyncio.get_event_loop().time()
    poll_url = f"{site_base.rstrip('/')}/v1/tasks/{task_id}"
    poll_headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        while True:
            elapsed = asyncio.get_event_loop().time() - start
            if elapsed > POLL_MAX:
                raise RightCodesError(f"Timeout polling task {task_id} after {POLL_MAX}s — Right Codes dashboard may show completed but bot timed out. Try again, may be queue high.")

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
                # 1) Images shape: data: [{url: "..."}] OR top-level data
                data = pj.get("data")
                if isinstance(data, list) and len(data) > 0:
                    first = data[0]
                    if isinstance(first, dict):
                        if "b64_json" in first:
                            return base64.b64decode(first["b64_json"])
                        url = first.get("url") or first.get("image_url")
                        if url:
                            return await _download_image(url)
                    elif isinstance(first, str):
                        if first.startswith("http"):
                            return await _download_image(first)

                # 2) top-level maybe data at root with created etc: {created, data:[{url}]}
                if isinstance(pj.get("data"), list):
                    dl = pj["data"]
                    if dl and isinstance(dl[0], dict) and dl[0].get("url"):
                        return await _download_image(dl[0]["url"])

                # 3) Gemini shape: candidates[0].content.parts[].text = URL  OR inlineData
                candidates = pj.get("candidates") or []
                if isinstance(candidates, list) and candidates:
                    for cand in candidates:
                        content = cand.get("content", {}) if isinstance(cand, dict) else {}
                        parts = content.get("parts", []) if isinstance(content, dict) else []
                        for part in parts:
                            if not isinstance(part, dict):
                                continue
                            # new shape: text contains URL
                            text = part.get("text")
                            if text:
                                url = _extract_url_from_text_maybe(text)
                                if url:
                                    return await _download_image(url)
                            # old shape: inlineData
                            inline = part.get("inlineData")
                            if inline and isinstance(inline, dict):
                                b64d = inline.get("data")
                                if b64d:
                                    try:
                                        return base64.b64decode(b64d)
                                    except Exception:
                                        pass
                            # also check inline_data snake
                            inline2 = part.get("inline_data")
                            if inline2 and isinstance(inline2, dict):
                                b64d = inline2.get("data")
                                if b64d:
                                    try:
                                        return base64.b64decode(b64d)
                                    except Exception:
                                        pass

                # 4) direct url at top level
                if pj.get("url"):
                    return await _download_image(pj["url"])

                # 5) result / output wrappers
                for key in ("result", "output", "response"):
                    val = pj.get(key)
                    if isinstance(val, dict):
                        # try data inside
                        if "url" in val and val["url"]:
                            return await _download_image(val["url"])
                        if "data" in val and isinstance(val["data"], list) and val["data"]:
                            first = val["data"][0]
                            if isinstance(first, dict) and first.get("url"):
                                return await _download_image(first["url"])
                    if isinstance(val, list) and val:
                        first = val[0]
                        if isinstance(first, dict) and first.get("url"):
                            return await _download_image(first["url"])
                        if isinstance(first, str) and first.startswith("http"):
                            return await _download_image(first)

                raise RightCodesError(f"Completed but no image parseable. Keys: {list(pj.keys())} Data preview: {str(pj)[:1500]}")

            elif status == "failed":
                err = pj.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                if not msg:
                    msg = pj.get("message") or str(pj)[:800]
                raise RightCodesError(f"Task failed: {msg}")

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
            last_err = f"{url} {resp.status_code} {resp.text[:200]}"
        except Exception as e:
            last_err = f"{url} {e}"
            continue
    raise RightCodesError(f"list_models failed: {last_err}")
