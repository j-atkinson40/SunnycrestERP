"""Signature image generation — Phase D-5.

Produces PNG bytes for a signature suitable for PDF overlay:

- Drawn signatures: decode base64 PNG from the signer's canvas, normalize
  size preserving aspect ratio.
- Typed signatures: render the typed name in a cursive font via PIL.

Falls back gracefully when PIL / font assets are missing — a signature
image is still produced (plain text on transparent background) so the
PDF overlay never silently skips.
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# Signature target dimensions inside a PDF page. These are the default
# field bounds (in points, 1 pt = 1/72 inch) and can be overridden per
# field via the `width` / `height` columns on `signature_fields`.
DEFAULT_SIG_WIDTH_PT = 180.0
DEFAULT_SIG_HEIGHT_PT = 44.0

# Image pixel density — higher values give sharper rendering at the
# cost of bigger overlay PNGs. 3x points-per-inch-equivalent is a
# sensible balance for on-screen + on-paper output.
PNG_SCALE = 3


def _cursive_font_path() -> Path | None:
    """Return the Caveat-Regular.ttf path if present; otherwise None.

    Package-local font directory: `backend/app/services/signing/fonts/`.
    The font file is optional — when missing we fall back to a PIL
    default font so typed signatures still render (just without cursive
    styling).
    """
    here = Path(__file__).resolve().parent
    candidate = here / "fonts" / "Caveat-Regular.ttf"
    if candidate.exists():
        return candidate
    return None


def _load_typed_font(size_px: int):
    """Return a PIL font for typed-signature rendering. Falls back to
    PIL default if the Caveat TTF isn't bundled."""
    try:
        from PIL import ImageFont
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for typed signature rendering"
        ) from exc

    path = _cursive_font_path()
    if path is not None:
        try:
            return ImageFont.truetype(str(path), size=size_px)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Cursive font load failed: %s", exc)
    # Fall back to whatever italic-ish font PIL can find. If even that
    # fails, the default bitmap font is used (ugly but functional).
    try:
        return ImageFont.truetype("Helvetica-Oblique.ttf", size=size_px)
    except Exception:  # noqa: BLE001
        return ImageFont.load_default()


def render_drawn_signature(
    base64_png: str,
    *,
    width_pt: float = DEFAULT_SIG_WIDTH_PT,
    height_pt: float = DEFAULT_SIG_HEIGHT_PT,
) -> bytes:
    """Decode a base64 PNG from the signer's canvas and resize it to
    the target PDF field dimensions. Returns PNG bytes.

    Preserves aspect ratio: if the source is wider than the target
    aspect, we letterbox with transparent padding on top/bottom;
    if taller, we pillarbox left/right.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for signature rendering"
        ) from exc

    # Strip data URI prefix if present
    if base64_png.startswith("data:"):
        base64_png = base64_png.split(",", 1)[-1]

    raw = base64.b64decode(base64_png)
    src = Image.open(io.BytesIO(raw)).convert("RGBA")

    # Target canvas in pixels — scaled up for crispness
    target_w = int(round(width_pt * PNG_SCALE))
    target_h = int(round(height_pt * PNG_SCALE))

    # Scale to fit preserving aspect
    src_w, src_h = src.size
    if src_w == 0 or src_h == 0:
        src_w, src_h = 1, 1
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))
    resized = src.resize((new_w, new_h), Image.LANCZOS)

    # Center on transparent canvas
    canvas = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 0))
    canvas.paste(
        resized,
        ((target_w - new_w) // 2, (target_h - new_h) // 2),
        resized,
    )

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def render_typed_signature(
    typed_name: str,
    *,
    width_pt: float = DEFAULT_SIG_WIDTH_PT,
    height_pt: float = DEFAULT_SIG_HEIGHT_PT,
) -> bytes:
    """Render a typed name as a signature image. Uses Caveat-Regular.ttf
    if available, otherwise PIL default. Always returns a PNG."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError(
            "Pillow is required for typed signature rendering"
        ) from exc

    target_w = int(round(width_pt * PNG_SCALE))
    target_h = int(round(height_pt * PNG_SCALE))

    # Heuristic starting font size — auto-shrinks if the rendered text
    # overflows the target bounds.
    font_size = int(target_h * 0.75)
    while font_size > 10:
        font = _load_typed_font(font_size)
        canvas = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 0))
        draw = ImageDraw.Draw(canvas)
        try:
            bbox = draw.textbbox((0, 0), typed_name, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
        except Exception:
            text_w, text_h = draw.textsize(typed_name, font=font)  # type: ignore[attr-defined]
        if text_w <= target_w - 8 and text_h <= target_h - 4:
            break
        font_size = int(font_size * 0.9)

    canvas = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(canvas)
    font = _load_typed_font(font_size)
    try:
        bbox = draw.textbbox((0, 0), typed_name, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x = (target_w - text_w) // 2 - bbox[0]
        y = (target_h - text_h) // 2 - bbox[1]
    except Exception:
        text_w, text_h = draw.textsize(typed_name, font=font)  # type: ignore[attr-defined]
        x = (target_w - text_w) // 2
        y = (target_h - text_h) // 2
    draw.text((x, y), typed_name, fill=(20, 20, 20, 255), font=font)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def signature_image_for_party(
    *,
    signature_type: str | None,
    signature_data: str | None,
    typed_name: str | None,
    width_pt: float = DEFAULT_SIG_WIDTH_PT,
    height_pt: float = DEFAULT_SIG_HEIGHT_PT,
) -> bytes | None:
    """Resolve a party's stored signature data into a PNG overlay.
    Returns None if there's nothing to render."""
    if signature_type == "drawn" and signature_data:
        try:
            return render_drawn_signature(
                signature_data, width_pt=width_pt, height_pt=height_pt
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Drawn signature render failed: %s", exc)
            # Fall through — try typed fallback if available
    if typed_name or (signature_type == "typed" and signature_data):
        text = typed_name or signature_data or ""
        if not text:
            return None
        try:
            return render_typed_signature(
                text, width_pt=width_pt, height_pt=height_pt
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Typed signature render failed: %s", exc)
    return None
