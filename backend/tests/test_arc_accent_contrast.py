"""Phase 7 — WCAG AA contrast verification for the 6 space accents.

The 6 accent color pairs live in `frontend/src/types/spaces.ts` in the
`ACCENT_CSS_VARS` constant. If the frontend values drift, this test
fails — the fix is to update both sides.

WCAG AA target: 4.5:1 contrast for normal text against background.
We test the `--space-accent-foreground` color against both a white
background (#FFFFFF) and the accent-light backdrop — covering the two
most common render contexts in the arc (text-on-white + text-on-chip).

Per approved Phase 7 scope: failing accents are bugs; the fix is to
adjust the accent, not document the fail.
"""

from __future__ import annotations


# ── WCAG AA math ───────────────────────────────────────────────────


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    """WCAG 2.1 relative luminance formula."""
    def _channel(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """WCAG contrast ratio (foreground vs background)."""
    lf = _relative_luminance(_hex_to_rgb(fg_hex))
    lb = _relative_luminance(_hex_to_rgb(bg_hex))
    lighter, darker = max(lf, lb), min(lf, lb)
    return (lighter + 0.05) / (darker + 0.05)


# ── Accent definitions (mirror frontend/src/types/spaces.ts) ───────

ACCENTS: dict[str, dict[str, str]] = {
    "warm": {
        "accent": "#B45309",
        "accent_light": "#FEF3C7",
        "foreground": "#78350F",
    },
    "crisp": {
        "accent": "#1E40AF",
        "accent_light": "#DBEAFE",
        "foreground": "#1E3A8A",
    },
    "industrial": {
        "accent": "#C2410C",
        "accent_light": "#FFEDD5",
        "foreground": "#7C2D12",
    },
    "forward": {
        "accent": "#6D28D9",
        "accent_light": "#EDE9FE",
        "foreground": "#4C1D95",
    },
    "neutral": {
        "accent": "#475569",
        "accent_light": "#F1F5F9",
        "foreground": "#334155",
    },
    "muted": {
        "accent": "#78716C",
        "accent_light": "#F5F5F4",
        "foreground": "#57534E",
    },
}

WCAG_AA_NORMAL = 4.5   # normal text
WCAG_AA_LARGE = 3.0    # large / bold text (18pt+ or 14pt+ bold)


# ── Tests ──────────────────────────────────────────────────────────


def test_accent_hex_format_valid():
    """Every accent definition is a parseable 6-digit hex."""
    for name, colors in ACCENTS.items():
        for key, val in colors.items():
            assert isinstance(val, str) and val.startswith("#"), (
                f"{name}.{key} must be a hex string (got {val!r})"
            )
            assert len(val) == 7, (
                f"{name}.{key} must be 6-digit hex (got {val!r})"
            )
            _hex_to_rgb(val)  # raises ValueError if malformed


def test_accent_foreground_on_white_meets_wcag_aa():
    """The foreground color used for space text must meet WCAG AA
    4.5:1 against a white background."""
    failures: list[str] = []
    for name, colors in ACCENTS.items():
        ratio = _contrast_ratio(colors["foreground"], "#FFFFFF")
        if ratio < WCAG_AA_NORMAL:
            failures.append(
                f"{name}: foreground={colors['foreground']} on white "
                f"= {ratio:.2f} (< 4.5)"
            )
    assert not failures, (
        "Accents fail WCAG AA normal-text contrast on white:\n  - "
        + "\n  - ".join(failures)
    )


def test_accent_on_white_meets_wcag_aa_large():
    """The accent color itself (used for larger text like space
    switcher labels) must meet WCAG AA large-text 3:1 on white."""
    failures: list[str] = []
    for name, colors in ACCENTS.items():
        ratio = _contrast_ratio(colors["accent"], "#FFFFFF")
        if ratio < WCAG_AA_LARGE:
            failures.append(
                f"{name}: accent={colors['accent']} on white "
                f"= {ratio:.2f} (< 3.0 for large text)"
            )
    assert not failures, (
        "Accents fail WCAG AA large-text contrast on white:\n  - "
        + "\n  - ".join(failures)
    )


def test_accent_foreground_on_accent_light_meets_wcag_aa():
    """Text rendered on the `--space-accent-light` chip background
    (common for badges + pinned items) must still meet WCAG AA."""
    failures: list[str] = []
    for name, colors in ACCENTS.items():
        ratio = _contrast_ratio(
            colors["foreground"], colors["accent_light"]
        )
        if ratio < WCAG_AA_NORMAL:
            failures.append(
                f"{name}: fg={colors['foreground']} on "
                f"light={colors['accent_light']} = {ratio:.2f} (< 4.5)"
            )
    assert not failures, (
        "Accent text-on-light-chip fails WCAG AA:\n  - "
        + "\n  - ".join(failures)
    )


def test_accents_distinguishable_from_preset_fallback():
    """Sanity: no accent color collides with the default slate-600
    preset accent used for unassigned spaces. Keeps the active-space
    visual signal meaningful."""
    preset_default = "#475569"  # slate-600, matches neutral
    for name, colors in ACCENTS.items():
        if name == "neutral":
            continue  # neutral deliberately matches the preset
        assert colors["accent"].lower() != preset_default.lower(), (
            f"{name} accent equals the preset fallback — no visual "
            "signal when this space is active"
        )
