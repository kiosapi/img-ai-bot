"""Watermark helpers — text overlay on image + caption logic."""
from __future__ import annotations
import io

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    PIL_OK = True
except ImportError:
    PIL_OK = False

import db
import feature_flags as ff


async def should_watermark(user_id: int) -> tuple[bool, str]:
    enabled = await ff.watermark_enabled()
    if not enabled:
        return False, ""
    text = await ff.watermark_text()
    free_only = await ff.watermark_free_only()
    if free_only:
        try:
            is_prem = await db.is_premium(user_id)
            if is_prem:
                return False, ""
        except Exception:
            pass
    return True, text


def apply_watermark_image(image_bytes: bytes, watermark_text: str) -> bytes:
    """Overlay semi-transparent watermark text at bottom-right of image."""
    if not PIL_OK or not watermark_text:
        return image_bytes
    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = im.size
        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # font size relative to image width
        font_size = max(18, w // 25)
        try:
            # try default font, Pillow may not have Arial in slim
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.load_default(size=font_size)
            except Exception:
                font = ImageFont.load_default()

        text = watermark_text.strip()
        # measure
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = len(text) * font_size // 2, font_size

        # padding
        pad = max(10, w // 50)
        x = w - tw - pad
        y = h - th - pad

        # Draw shadow + text for visibility
        # shadow
        shadow_color = (0, 0, 0, 160)
        draw.text((x + 2, y + 2), text, font=font, fill=shadow_color)
        # main semi-transparent white
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 200))

        combined = Image.alpha_composite(im, overlay)
        out = io.BytesIO()
        # save as PNG (keep quality)
        combined.convert("RGB").save(out, format="PNG")
        return out.getvalue()
    except Exception:
        # fail open — return original
        return image_bytes
