"""Phase 7 — Focus ring visibility verification.

The focus-ring color `--ring` in `frontend/src/index.css` must provide
sufficient contrast against every background surface where focus
lands. Per WCAG 2.2, non-text UI component indicators need 3:1
contrast against adjacent colors.

We verify against:
  - Pure white page background (#FFFFFF)
  - Each of the 6 space-accent-light chip backdrops

If a new accent is added with a backdrop that fails this test, either
darken the accent-light OR introduce a compensating ring treatment.
"""

from __future__ import annotations


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def _channel(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    lf = _relative_luminance(_hex_to_rgb(fg_hex))
    lb = _relative_luminance(_hex_to_rgb(bg_hex))
    lighter, darker = max(lf, lb), min(lf, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _oklch_to_hex_approx(lightness: float) -> str:
    """Approximate neutral oklch(L 0 0) → hex for contrast math.

    oklch lightness L in range [0,1] maps to sRGB gray via the
    standard OKLAB → sRGB transform. For neutral gray (chroma=0) it
    simplifies to roughly `round((L ** 1.1) * 255)` — good enough
    for contrast verification (not pixel-accurate).
    """
    srgb = round((lightness ** 1.1) * 255)
    srgb = max(0, min(255, srgb))
    return f"#{srgb:02x}{srgb:02x}{srgb:02x}"


# Matches the `--ring` value in frontend/src/index.css (light mode).
# Phase 7: bumped from oklch(0.708) to oklch(0.48) to pass WCAG 3:1
# focus-indicator contrast against white + all 6 accent-light chips.
FOCUS_RING_LIGHTNESS: float = 0.48
WCAG_UI_CONTRAST = 3.0


ACCENT_LIGHT_BACKDROPS = {
    "warm": "#FEF3C7",
    "crisp": "#DBEAFE",
    "industrial": "#FFEDD5",
    "forward": "#EDE9FE",
    "neutral": "#F1F5F9",
    "muted": "#F5F5F4",
}


def test_focus_ring_meets_contrast_against_white():
    """Focus indicator must have at least 3:1 contrast against white."""
    ring_hex = _oklch_to_hex_approx(FOCUS_RING_LIGHTNESS)
    ratio = _contrast_ratio(ring_hex, "#FFFFFF")
    assert ratio >= WCAG_UI_CONTRAST, (
        f"Focus ring {ring_hex} (oklch L={FOCUS_RING_LIGHTNESS}) on white "
        f"= {ratio:.2f} (< {WCAG_UI_CONTRAST})"
    )


def test_focus_ring_meets_contrast_against_each_accent_light():
    """Focus indicator must still be visible when a focused element
    sits on a space-accent-light backdrop."""
    ring_hex = _oklch_to_hex_approx(FOCUS_RING_LIGHTNESS)
    failures: list[str] = []
    for name, bg in ACCENT_LIGHT_BACKDROPS.items():
        ratio = _contrast_ratio(ring_hex, bg)
        if ratio < WCAG_UI_CONTRAST:
            failures.append(
                f"{name} (bg={bg}): {ratio:.2f} (< {WCAG_UI_CONTRAST})"
            )
    assert not failures, (
        f"Focus ring {ring_hex} fails WCAG 3:1 against accent-light:\n  - "
        + "\n  - ".join(failures)
    )


def test_focus_ring_lightness_matches_index_css():
    """Guard against drift: if someone changes `--ring` in
    `frontend/src/index.css` without updating this test, the two
    sources are now inconsistent. Read the CSS file + assert the
    `--ring: oklch(<L> 0 0)` value matches the constant we test
    against."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    css_path = root / "frontend" / "src" / "index.css"
    assert css_path.exists(), f"index.css not found at {css_path}"
    content = css_path.read_text()
    # Find the FIRST --ring: definition inside :root (light mode).
    # The dark-mode override is in a .dark { ... } block and comes later.
    root_block = re.search(r":root\s*\{([^}]*)\}", content, re.DOTALL)
    assert root_block, "No :root block found in index.css"
    match = re.search(
        r"--ring:\s*oklch\(([\d.]+)\s+", root_block.group(1)
    )
    assert match, (
        ":root must define --ring: oklch(<lightness> 0 0); — not found"
    )
    css_lightness = float(match.group(1))
    assert abs(css_lightness - FOCUS_RING_LIGHTNESS) < 0.001, (
        f"index.css --ring lightness = {css_lightness} but test "
        f"asserts {FOCUS_RING_LIGHTNESS}. Update both sides."
    )
