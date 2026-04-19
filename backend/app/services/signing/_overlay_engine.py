"""PDF overlay primitives — Phase D-5.

Built on PyMuPDF (fitz). Given a source PDF + a list of overlay specs
(anchor text, explicit page+xy, signature image bytes), produces a new
PDF byte stream with all overlays applied in a single pass.

Anchor resolution:
- `page.search_for(anchor)` returns a list of Rects wherever the
  anchor string appears on that page. We take the first hit (templates
  only have each anchor once).
- If the anchor isn't found on any page, the caller decides the
  fallback (explicit position, default position, or skip).

Coordinate system:
- PyMuPDF measures in points (1 pt = 1/72 in), origin at top-left.
- Overlay images are placed with their *top-left* at the anchor's
  top-left plus configured offsets. The default offsets (0, 0) put the
  signature image exactly over the anchor text — which is what we want
  because the template styles the anchor as invisible 1pt white text.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OverlaySpec:
    """One signature overlay to apply to the PDF."""

    # Signature image (PNG bytes)
    image_bytes: bytes
    # Either anchor-based OR explicit positioning
    anchor_string: str | None = None
    explicit_page: int | None = None  # 1-indexed, matches human language
    explicit_x_pt: float | None = None
    explicit_y_pt: float | None = None
    # Fine-tune placement (always applied, whether anchor or explicit)
    x_offset_pt: float = 0.0
    y_offset_pt: float = 0.0
    # Target dimensions in PDF points (1 pt = 1/72 inch)
    width_pt: float = 180.0
    height_pt: float = 44.0
    # Label for logging / diagnostics
    label: str = ""


@dataclass
class OverlayResult:
    applied: int  # count placed successfully
    missed_anchors: list[str]  # anchors that couldn't be resolved


def apply_overlays(source_pdf: bytes, overlays: list[OverlaySpec]) -> tuple[bytes, OverlayResult]:
    """Apply all overlays in a single PDF pass. Returns (new_pdf_bytes, result).

    Missed anchors are reported back so the caller can log signature_event
    entries for audit. We never raise for a missed anchor — the overlay
    is skipped and the result carries the info.
    """
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF (fitz) is required for PDF signature overlay"
        ) from exc

    doc = fitz.open(stream=source_pdf, filetype="pdf")
    missed: list[str] = []
    applied = 0

    # Pre-resolve anchor positions for the whole document so we don't
    # re-search the PDF per overlay when multiple fields use the same
    # anchor (shouldn't happen in practice but cheap insurance).
    anchor_cache: dict[str, tuple[int, "fitz.Rect"] | None] = {}

    def _find_anchor(anchor: str) -> tuple[int, "fitz.Rect"] | None:
        if anchor in anchor_cache:
            return anchor_cache[anchor]
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            rects = page.search_for(anchor)
            if rects:
                anchor_cache[anchor] = (page_num, rects[0])
                return anchor_cache[anchor]
        anchor_cache[anchor] = None
        return None

    for spec in overlays:
        # Resolve (page_index, origin_x, origin_y)
        target: tuple[int, float, float] | None = None

        if spec.anchor_string:
            found = _find_anchor(spec.anchor_string)
            if found is not None:
                page_idx, rect = found
                target = (page_idx, float(rect.x0), float(rect.y0))
            else:
                missed.append(spec.anchor_string)
                # Anchor missing — fall back to explicit if provided
                if (
                    spec.explicit_page is not None
                    and spec.explicit_x_pt is not None
                    and spec.explicit_y_pt is not None
                ):
                    target = (
                        spec.explicit_page - 1,
                        spec.explicit_x_pt,
                        spec.explicit_y_pt,
                    )
                else:
                    # Last-resort default: bottom of first page
                    logger.warning(
                        "Overlay anchor %r not found for %s; skipping",
                        spec.anchor_string,
                        spec.label,
                    )
                    continue
        elif (
            spec.explicit_page is not None
            and spec.explicit_x_pt is not None
            and spec.explicit_y_pt is not None
        ):
            target = (
                spec.explicit_page - 1,
                spec.explicit_x_pt,
                spec.explicit_y_pt,
            )
        else:
            logger.warning(
                "Overlay %s has no anchor or explicit position; skipping",
                spec.label,
            )
            continue

        page_idx, origin_x, origin_y = target
        if page_idx < 0 or page_idx >= doc.page_count:
            logger.warning(
                "Overlay %s target page %d out of range (0..%d); skipping",
                spec.label,
                page_idx,
                doc.page_count - 1,
            )
            continue

        x = origin_x + spec.x_offset_pt
        y = origin_y + spec.y_offset_pt
        rect = fitz.Rect(
            x, y, x + spec.width_pt, y + spec.height_pt
        )
        page = doc.load_page(page_idx)
        # keep_proportion=True avoids stretching if the image aspect
        # doesn't exactly match the rect.
        try:
            page.insert_image(
                rect,
                stream=spec.image_bytes,
                keep_proportion=True,
                overlay=True,
            )
            applied += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Overlay insert failed for %s: %s", spec.label, exc
            )
            continue

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue(), OverlayResult(applied=applied, missed_anchors=missed)


def find_anchor_positions(
    source_pdf: bytes, anchor_strings: list[str]
) -> dict[str, tuple[int, float, float, float, float] | None]:
    """Diagnostic helper — returns a map of anchor → (page_idx, x0, y0, x1, y1)
    or None if not found. Used by tests."""
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF (fitz) is required for anchor lookup"
        ) from exc

    doc = fitz.open(stream=source_pdf, filetype="pdf")
    out: dict[str, tuple[int, float, float, float, float] | None] = {}
    for anchor in anchor_strings:
        found = None
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            rects = page.search_for(anchor)
            if rects:
                r = rects[0]
                found = (page_num, float(r.x0), float(r.y0), float(r.x1), float(r.y1))
                break
        out[anchor] = found
    doc.close()
    return out
