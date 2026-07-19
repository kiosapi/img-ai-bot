"""Client for the Cubence image API (OpenAI-compatible)."""
import base64
import httpx

from config import CUBENCE_API_KEY, CUBENCE_BASE_URL, IMAGE_MODEL


class CubenceError(Exception):
    pass


# Generation/edit calls to the upstream model can legitimately take 1-3+
# minutes. Give it a generous ceiling, and make sure any network failure
# (timeout, connection reset, etc.) is turned into a CubenceError instead of
# an unhandled exception that would crash the update silently (user sees
# nothing and the bot looks "stuck").
REQUEST_TIMEOUT = httpx.Timeout(280.0, connect=20.0)


async def generate_image(prompt: str, size: str = "1024x1024") -> bytes:
    """Text-to-image. Returns raw PNG bytes."""
    url = f"{CUBENCE_BASE_URL}/v1/images/generations"
    payload = {"model": IMAGE_MODEL, "prompt": prompt, "n": 1, "size": size}
    headers = {
        "Authorization": f"Bearer {CUBENCE_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        raise CubenceError("Server AI kelamaan merespons (timeout). Coba lagi ya.")
    except httpx.HTTPError as e:
        raise CubenceError(f"Gagal menghubungi server AI: {e}")
    return _parse_image_response(resp)


async def edit_image(image_bytes: bytes, prompt: str, size: str = "1024x1024",
                     filename: str = "image.png") -> bytes:
    """Image-to-image / edit. Returns raw PNG bytes."""
    url = f"{CUBENCE_BASE_URL}/v1/images/edits"
    headers = {"Authorization": f"Bearer {CUBENCE_API_KEY}"}
    files = {"image": (filename, image_bytes, "image/png")}
    data = {"model": IMAGE_MODEL, "prompt": prompt, "n": "1", "size": size}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, data=data, files=files)
    except httpx.TimeoutException:
        raise CubenceError("Server AI kelamaan merespons (timeout). Coba lagi ya.")
    except httpx.HTTPError as e:
        raise CubenceError(f"Gagal menghubungi server AI: {e}")
    return _parse_image_response(resp)


def _parse_image_response(resp: httpx.Response) -> bytes:
    if resp.status_code != 200:
        text = resp.text[:400]
        raise CubenceError(f"API {resp.status_code}: {text}")
    try:
        data = resp.json()
        b64 = data["data"][0]["b64_json"]
    except Exception as e:
        raise CubenceError(f"Unexpected response: {e}")
    return base64.b64decode(b64)
