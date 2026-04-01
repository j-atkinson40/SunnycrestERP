"""Legacy image compositor — PIL-based image processing for legacy prints.

All coordinates stored as 0.0-1.0 floats (percentage of canvas dimensions)
so they work regardless of final output resolution.
"""

import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# Common font search paths
_FONT_PATHS = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/LiberationSans-BoldItalic.ttf",
]


def get_font_path() -> str:
    """Find a usable bold font on the system."""
    for p in _FONT_PATHS:
        if Path(p).exists():
            return p
    # Fallback to PIL default
    return ""


def flatten_tif_to_jpeg(tif_bytes: bytes, output_width: int = 2400) -> bytes:
    """Load TIF, convert to RGB, resize, return as JPEG bytes."""
    img = Image.open(BytesIO(tif_bytes))
    if img.mode == "CMYK":
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize maintaining aspect ratio
    w, h = img.size
    ratio = output_width / w
    new_h = int(h * ratio)
    img = img.resize((output_width, new_h), Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def process_custom_background(
    photo_bytes: bytes, target_width: int = 2400, target_height: int = 1200
) -> bytes:
    """Create a blurred background from a custom photo. Returns JPEG bytes."""
    img = Image.open(BytesIO(photo_bytes)).convert("RGB")
    w, h = img.size

    # Cover-crop to target dimensions
    target_ratio = target_width / target_height
    img_ratio = w / h
    if img_ratio > target_ratio:
        # Wider than target — crop sides
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        # Taller than target — crop top/bottom
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    img = img.resize((target_width, target_height), Image.LANCZOS)

    # Heavy blur to hide quality issues
    blur_radius = max(target_width, target_height) // 20
    img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def apply_oval_fade(photo_bytes: bytes, fade_width: float = 0.15) -> bytes:
    """Apply elliptical soft-edge mask. Returns PNG bytes with alpha."""
    img = Image.open(BytesIO(photo_bytes)).convert("RGBA")
    w, h = img.size

    # Create elliptical mask
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    inset_x = int(w * fade_width)
    inset_y = int(h * fade_width)
    draw.ellipse(
        [inset_x, inset_y, w - inset_x, h - inset_y],
        fill=255,
    )

    # Blur the mask for soft edges
    blur = int(min(w, h) * fade_width * 0.8)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=max(blur, 5)))

    # Apply mask as alpha
    img.putalpha(mask)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def composite_layout(
    background_bytes: bytes,
    layout: dict,
    output_width: int = 2400,
    for_print: bool = False,
) -> bytes:
    """Composite photos and text onto a background image.

    layout structure:
    {
        "photos": [{
            "image_bytes": bytes,
            "x": 0.35, "y": 0.40,  # center position
            "scale": 0.45,  # fraction of canvas width
            "opacity": 1.0,
            "style": "soft_fade"  # or "hard_edge"
        }],
        "text": {
            "name": "Robert James Smith",
            "dates": "1942 — 2026",
            "additional": "Beloved Husband",
            "x": 0.75, "y": 0.50,
            "font_size": 0.06,  # fraction of canvas height
            "color": "white",
            "shadow": true
        }
    }
    """
    # Load and resize background
    bg = Image.open(BytesIO(background_bytes)).convert("RGBA")
    w, h = bg.size
    ratio = output_width / w
    canvas_h = int(h * ratio)
    bg = bg.resize((output_width, canvas_h), Image.LANCZOS)
    canvas = bg.copy()

    # Composite photos
    for photo_spec in layout.get("photos", []):
        img_bytes = photo_spec.get("image_bytes")
        if not img_bytes:
            continue

        if photo_spec.get("style") == "soft_fade":
            img_bytes = apply_oval_fade(img_bytes)

        photo = Image.open(BytesIO(img_bytes)).convert("RGBA")

        # Scale
        scale = photo_spec.get("scale", 0.3)
        photo_w = int(output_width * scale)
        pw, ph = photo.size
        photo_h = int(photo_w * (ph / pw))
        photo = photo.resize((photo_w, photo_h), Image.LANCZOS)

        # Apply opacity
        opacity = photo_spec.get("opacity", 1.0)
        if opacity < 1.0:
            alpha = photo.split()[3]
            alpha = alpha.point(lambda p: int(p * opacity))
            photo.putalpha(alpha)

        # Position (center-based)
        px = int(output_width * photo_spec.get("x", 0.5) - photo_w / 2)
        py = int(canvas_h * photo_spec.get("y", 0.5) - photo_h / 2)

        canvas.paste(photo, (px, py), photo)

    # Render text
    text_spec = layout.get("text", {})
    if text_spec.get("name") or text_spec.get("dates"):
        font_size_px = int(canvas_h * text_spec.get("font_size", 0.06))
        font_path = get_font_path()

        try:
            font_main = ImageFont.truetype(font_path, font_size_px) if font_path else ImageFont.load_default()
            font_small = ImageFont.truetype(font_path, int(font_size_px * 0.85)) if font_path else ImageFont.load_default()
        except Exception:
            font_main = ImageFont.load_default()
            font_small = font_main

        color = text_spec.get("color", "white")
        text_color = (255, 255, 255, 255) if color == "white" else (0, 0, 0, 255)
        shadow_color = (0, 0, 0, 150)

        lines = []
        if text_spec.get("name"):
            lines.append((text_spec["name"], font_main))
        if text_spec.get("dates"):
            lines.append((text_spec["dates"], font_main))
        if text_spec.get("additional"):
            lines.append((text_spec["additional"], font_small))

        center_x = int(output_width * text_spec.get("x", 0.75))
        center_y = int(canvas_h * text_spec.get("y", 0.5))
        line_spacing = int(font_size_px * 0.3)

        # Calculate total text block height
        total_h = sum(font_size_px for _ in lines) + line_spacing * (len(lines) - 1) if lines else 0
        start_y = center_y - total_h // 2

        txt_layer = Image.new("RGBA", (output_width, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)

        y = start_y
        for text, font in lines:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            tx = center_x - tw // 2

            if text_spec.get("shadow"):
                draw.text((tx + 2, y + 2), text, fill=shadow_color, font=font)

            draw.text((tx, y), text, fill=text_color, font=font)
            y += font_size_px + line_spacing

        canvas = Image.alpha_composite(canvas, txt_layer)

    # Output
    if for_print:
        out = canvas.convert("CMYK")
        buf = BytesIO()
        out.save(buf, format="TIFF", dpi=(400, 400), compression="none")
        return buf.getvalue()
    else:
        out = canvas.convert("RGB")
        buf = BytesIO()
        out.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
