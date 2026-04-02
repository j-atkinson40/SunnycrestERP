"""Legacy proof watermark service — applies PROOF watermark to proof JPEGs."""

import logging
import math
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

_FONT_PATHS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _get_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for p in _FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def apply_watermark(
    proof_jpeg_bytes: bytes,
    watermark_enabled: bool = False,
    watermark_text: str = "PROOF",
    watermark_opacity: float = 0.30,
    watermark_position: str = "center",
) -> bytes:
    """Apply watermark to proof JPEG. Returns original bytes if disabled."""
    if not watermark_enabled:
        return proof_jpeg_bytes

    try:
        img = Image.open(BytesIO(proof_jpeg_bytes)).convert("RGBA")
        w, h = img.size

        # Create transparent overlay
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        font_size = w // 8
        font = _get_font(font_size)
        alpha = int(255 * watermark_opacity)

        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        if watermark_position == "center":
            # Rotated diagonal watermark
            txt_img = Image.new("RGBA", (tw + 40, th + 40), (0, 0, 0, 0))
            txt_draw = ImageDraw.Draw(txt_img)
            txt_draw.text((20, 20), watermark_text, fill=(255, 255, 255, alpha), font=font)
            rotated = txt_img.rotate(30, expand=True, resample=Image.BICUBIC)
            rw, rh = rotated.size
            px = (w - rw) // 2
            py = (h - rh) // 2
            overlay.paste(rotated, (px, py), rotated)
        elif watermark_position == "bottom-right":
            x = w - tw - 40
            y = h - th - 40
            draw.text((x, y), watermark_text, fill=(255, 255, 255, alpha), font=font)
        elif watermark_position == "bottom-left":
            x = 40
            y = h - th - 40
            draw.text((x, y), watermark_text, fill=(255, 255, 255, alpha), font=font)
        elif watermark_position == "top-right":
            x = w - tw - 40
            y = 40
            draw.text((x, y), watermark_text, fill=(255, 255, 255, alpha), font=font)
        else:
            # Default center
            x = (w - tw) // 2
            y = (h - th) // 2
            draw.text((x, y), watermark_text, fill=(255, 255, 255, alpha), font=font)

        composite = Image.alpha_composite(img, overlay).convert("RGB")
        buf = BytesIO()
        composite.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    except Exception as e:
        logger.warning("Failed to apply watermark: %s", e)
        return proof_jpeg_bytes
