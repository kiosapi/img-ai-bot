"""Watermark helpers — premium @imgaai_bot pill."""
from __future__ import annotations
import io

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter  # type: ignore
    PIL_OK = True
except ImportError:
    PIL_OK = False

import db
import feature_flags as ff

WATERMARK_DEFAULT = "@imgaai_bot"

async def should_watermark(user_id: int) -> tuple[bool, str]:
    enabled = await ff.watermark_enabled()
    if not enabled:
        return False, ""
    # Force @imgaai_bot only — ignore stored text setting if contains "Buat di" etc.
    # User request: text hanya @imgaai_bot
    stored = await ff.watermark_text()
    text = WATERMARK_DEFAULT
    # If stored explicitly set to something else but user wants clean, still use @imgaai_bot
    # Except keep if admin typed different handle intentionally? Enforce @imgaai_bot as per request.
    if stored and stored.strip() and stored.strip().lower() == "@imgaai_bot":
        text = stored.strip()
    free_only = await ff.watermark_free_only()
    if free_only:
        try:
            is_prem = await db.is_premium(user_id)
            if is_prem:
                return False, ""
        except Exception:
            pass
    return True, text


def _load_premium_font(size: int):
    """Premium rare font stack — try modern geometric grotesk + clean fallback.

    Preferred (in order):
    - Space Grotesk Bold (geometric, premium, widely used by modern brands)
    - Manrope ExtraBold (rare, premium, used by Linear/Stripe style)
    - Satoshi Bold / General Sans (modern)
    - Inter Tight Bold
    Falls back to bundled DejaVu if none available, still renders clean.
    """
    candidates = [
        "SpaceGrotesk-Bold.ttf",
        "SpaceGrotesk-SemiBold.ttf",
        "Manrope-Bold.ttf",
        "Manrope-ExtraBold.ttf",
        "Satoshi-Bold.ttf",
        "GeneralSans-Bold.ttf",
        "Geist-Bold.ttf",
        "InterTight-Bold.ttf",
        "Inter-Bold.ttf",
        "DejaVuSans-Bold.ttf",
        "NotoSans-Bold.ttf",
        "DejaVuSans.ttf",
        "Arial_Bold.ttf",
        "Arial.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)  # type: ignore
    except Exception:
        return ImageFont.load_default()


def apply_watermark_image(image_bytes: bytes, watermark_text: str) -> bytes:
    """Modern premium watermark — text only @imgaai_bot.

    Design:
    - Bottom-right modern glass pill, no icon/emoji
    - Font: Space Grotesk / Manrope-style geometric bold (premium rare)
    - Background: frosted blur + radial gradient dark pill with soft white stroke
    - Text pure: @imgaai_bot — mono-ish tight tracking
    - Letter-spacing slightly tightened for premium feel via manual char gap
    - Responsive: base = max(w,h), font base/33
    - Safe fallback returns original on error
    """
    if not PIL_OK or not watermark_text:
        return image_bytes
    text = watermark_text.strip()
    if not text:
        return image_bytes
    # Enforce requested @imgaai_bot — no "Buat di", no icon
    # If admin saved different, override to clean for image overlay (caption still may differ if needed)
    if "imgaai_bot" not in text.lower():
        text = WATERMARK_DEFAULT
    else:
        # Normalize casing — user wants exactly @imgaai_bot
        text = WATERMARK_DEFAULT

    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        w, h = im.size
        base = max(w, h)

        # Responsive sizing
        font_size = max(18, int(base / 33))
        pad_x = max(16, int(base / 52))
        pad_y = max(9, int(base / 92))
        radius = max(12, int(font_size * 0.95))
        margin = max(16, int(base / 48))
        # letter spacing premium tight
        letter_gap = max(0, int(font_size * 0.02))

        font = _load_premium_font(font_size)

        tmp = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
        tmp_draw = ImageDraw.Draw(tmp)

        # Measure with optional tracking
        def text_width(s: str) -> int:
            try:
                bb = tmp_draw.textbbox((0, 0), s, font=font)
                return bb[2] - bb[0] + (len(s) - 1) * letter_gap
            except Exception:
                return int(len(s) * font_size * 0.60 + (len(s)-1)*letter_gap)

        tw = text_width(text)
        # height measurement
        try:
            tb = tmp_draw.textbbox((0, 0), text, font=font)
            th = tb[3] - tb[1]
        except Exception:
            th = font_size

        pill_w = tw + pad_x * 2
        pill_h = th + pad_y * 2 + 2
        # Cap max 58% width
        max_w = int(w * 0.58)
        if pill_w > max_w:
            # reduce font
            font_size = max(14, int(font_size * max_w / pill_w))
            font = _load_premium_font(font_size)
            tw = text_width(text)
            try:
                tb = tmp_draw.textbbox((0, 0), text, font=font)
                th = tb[3] - tb[1]
            except Exception:
                th = font_size
            pill_w = tw + pad_x * 2
            pill_h = th + pad_y * 2 + 2

        x1 = w - pill_w - margin
        y1 = h - pill_h - margin
        x2 = w - margin
        y2 = h - margin

        # Clamp
        x1 = max(margin, x1)
        y1 = max(margin, y1)

        # Frosted blur under pill
        try:
            box = (int(x1), int(y1), int(x2), int(y2))
            crop = im.crop(box)
            blur_r = max(3, int(base / 260))
            blurred = crop.filter(ImageFilter.GaussianBlur(radius=blur_r))
            im.paste(blurred, box)
        except Exception:
            pass

        overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Pill background: modern deep charcoal 88% opacity + subtle gradient via two rects
        # Layer 1: base
        base_col = (18, 18, 19, 196)
        try:
            draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=base_col)
        except AttributeError:
            draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=base_col)
            draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=base_col)
            draw.ellipse([x1, y1, x1 + radius*2, y1 + radius*2], fill=base_col)
            draw.ellipse([x2 - radius*2, y1, x2, y1 + radius*2], fill=base_col)
            draw.ellipse([x1, y2 - radius*2, x1 + radius*2, y2], fill=base_col)
            draw.ellipse([x2 - radius*2, y2 - radius*2, x2, y2], fill=base_col)

        # Layer 2: subtle top highlight inner (premium glass)
        hi_h = max(2, pill_h // 3)
        hi_col = (255, 255, 255, 22)
        try:
            # inner highlight rounded top only effect
            draw.rounded_rectangle([x1+1, y1+1, x2-1, y1+hi_h], radius=radius//1.2, fill=hi_col)
        except Exception:
            pass

        # Stroke: soft white 9%
        try:
            draw.rounded_rectangle([x1+0.5, y1+0.5, x2-0.5, y2-0.5], radius=radius, outline=(255,255,255,28), width=1)
        except Exception:
            pass

        # Text: centered vertically, slight shadow for depth
        text_x = x1 + pad_x
        # Build string with tracking manually if gap >0
        if letter_gap > 0:
            # draw char by char
            cur_x = text_x
            # shadow first pass
            for ch in text:
                try:
                    draw.text((cur_x+1, y1 + pad_y + 2), ch, font=font, fill=(0,0,0,110))
                except Exception:
                    pass
                cur_x += tmp_draw.textlength(ch, font=font) + letter_gap if hasattr(tmp_draw, 'textlength') else font_size*0.6 + letter_gap
            cur_x = text_x
            for ch in text:
                draw.text((cur_x, y1 + pad_y + 1), ch, font=font, fill=(255,255,255,240))
                try:
                    cw = tmp_draw.textlength(ch, font=font)
                except Exception:
                    cw = font_size * 0.60
                cur_x += cw + letter_gap
        else:
            draw.text((text_x+1, y1 + pad_y + 2), text, font=font, fill=(0,0,0,110))
            draw.text((text_x, y1 + pad_y + 1), text, font=font, fill=(255,255,255,240))

        combined = Image.alpha_composite(im, overlay)
        out = io.BytesIO()
        combined.convert("RGB").save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return image_bytes
