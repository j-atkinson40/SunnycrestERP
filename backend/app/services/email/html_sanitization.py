"""HTML sanitization for inbound + outbound email body_html —
Phase W-4b Layer 1 Step 4c.

Per canon §3.26.15.5 + DESIGN_LANGUAGE §14.9.2: inbound HTML messages
render in a sandboxed iframe (no scripts + no top-level navigation +
no popups + sandboxed origin). Outbound HTML composer output sanitized
via DOMPurify-equivalent.

This module is the **server-side sanitization layer** — sanitizes at
RENDER time (not ingestion) per investigation. Two reasons:
  1. Inbound provider raw payloads stay byte-equal to what the provider
     delivered (audit fidelity + ability to re-render with updated
     allowlists post-rule-change).
  2. Outbound composer output is sanitized just before send, so
     operator-typed HTML never reaches the wire un-cleaned.

bleach is the canonical Python HTML sanitizer (used in production at
Mozilla / Google / etc). Added as a hard dep in requirements.txt.

**Allowlist canon:**
  - Tags: standard inline + block formatting; no script/iframe/object/
    embed/form; no style block. img + a allowed with attribute filtering.
  - Attributes: per-tag allowlist; href/src protocol whitelist
    (http/https/mailto/tel + cid: for inline images per §3.26.15.5)
  - on*= event handlers stripped wholesale
  - javascript: + data: + vbscript: protocols stripped
  - <style>...</style> blocks dropped (CSS-in-style is too complex
    to safely allow — Step 4c uses inline-style attribute on a
    safelist of properties)

**External image policy** per §14.9.2 / Step 4c discipline gate:
  - Default block external images at iframe-CSP level (not at
    sanitization level — sanitizer keeps img tags so the iframe can
    surface "blocked" affordance + per-sender opt-in)
  - cid: inline images preserved unconditionally (already in tenant
    control; no privacy concern)
  - Tracking pixel detection: 1x1 imgs flagged as ``data-tracking``
    so the iframe can render a warning

**Sanitization audit:** when bleach detects + strips dangerous content,
caller logs an ``email_audit_log`` entry per §3.26.15.8 (action=
``html_sanitized_dangerous_content``). Body content NEVER logged
(metadata only — count of stripped elements, types of elements
stripped).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import bleach
from bleach.css_sanitizer import CSSSanitizer

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Allowlist canon
# ─────────────────────────────────────────────────────────────────────


_ALLOWED_TAGS = frozenset(
    [
        # Block-level
        "p", "div", "section", "article", "header", "footer", "nav",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "blockquote", "pre", "hr",
        # Lists
        "ul", "ol", "li", "dl", "dt", "dd",
        # Tables (commonly used in marketing emails)
        "table", "thead", "tbody", "tfoot", "tr", "th", "td",
        # Inline formatting
        "span", "a", "strong", "em", "b", "i", "u", "s", "code", "small",
        "sub", "sup", "mark", "del", "ins",
        "br",
        # Media (img only — iframe blocked entirely)
        "img",
    ]
)


_ALLOWED_ATTRIBUTES = {
    "*": ["class", "id", "title", "lang", "dir", "style"],
    "a": ["href", "name", "target", "rel"],
    "img": [
        "src", "alt", "width", "height", "title",
        # Step 4c chrome — annotates inline vs external + tracking-pixel
        "data-cid", "data-external", "data-tracking",
    ],
    "td": ["colspan", "rowspan", "align", "valign"],
    "th": ["colspan", "rowspan", "align", "valign", "scope"],
    "table": ["border", "cellpadding", "cellspacing", "align", "width"],
}


_ALLOWED_PROTOCOLS = frozenset(["http", "https", "mailto", "tel", "cid"])


# Inline-style property allowlist — bleach strips style attribute
# entirely if not configured; we allow safe formatting properties only.
_ALLOWED_CSS_PROPERTIES = frozenset(
    [
        "color", "background-color",
        "font-family", "font-size", "font-style", "font-weight",
        "text-align", "text-decoration", "line-height",
        "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
        "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
        "border", "border-top", "border-right", "border-bottom", "border-left",
        "border-color", "border-style", "border-width", "border-radius",
        "width", "max-width", "height", "max-height",
        "display", "vertical-align",
    ]
)


# Tracking-pixel detector — 1x1 imgs (or width=0/height=0; common
# tracking-pixel signatures).
_TRACKING_PIXEL_SIZE = re.compile(
    r"^(0|0px|1|1px)$", re.IGNORECASE
)


# ─────────────────────────────────────────────────────────────────────
# Sanitization
# ─────────────────────────────────────────────────────────────────────


@dataclass
class SanitizationResult:
    """Returned from ``sanitize_email_html``.

    Carries the cleaned HTML + metadata about what was stripped, so
    callers can write canonical audit log entries without ever
    persisting body content.
    """

    cleaned_html: str
    original_length: int
    cleaned_length: int
    dangerous_content_detected: bool = False
    stripped_summary: dict[str, int] = field(default_factory=dict)


def _build_cleaner() -> bleach.Cleaner:
    css_sanitizer = CSSSanitizer(
        allowed_css_properties=list(_ALLOWED_CSS_PROPERTIES),
    )
    return bleach.Cleaner(
        tags=list(_ALLOWED_TAGS),
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=list(_ALLOWED_PROTOCOLS),
        strip=True,
        strip_comments=True,
        css_sanitizer=css_sanitizer,
    )


# Pre-built cleaner — bleach.Cleaner construction is non-trivial;
# reuse across calls.
_CLEANER = _build_cleaner()


# Quick danger-detection regex for audit-flagging only (NOT sanitization;
# bleach handles the actual stripping). Detection lets us flag the
# audit log when a message arrived with stripped dangerous content.
_DANGER_PATTERNS = [
    re.compile(r"<script\b", re.IGNORECASE),
    re.compile(r"<iframe\b", re.IGNORECASE),
    re.compile(r"<object\b", re.IGNORECASE),
    re.compile(r"<embed\b", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"vbscript:", re.IGNORECASE),
    re.compile(r"\bon[a-z]+\s*=", re.IGNORECASE),
]


def detect_dangerous_content(html: str) -> dict[str, int]:
    """Return a count of dangerous-pattern matches per type.

    Used for audit logging when bleach strips content. Doesn't
    sanitize — just detects.
    """
    counts: dict[str, int] = {}
    if not html:
        return counts
    for pattern in _DANGER_PATTERNS:
        matches = pattern.findall(html)
        if matches:
            label = pattern.pattern.lstrip("<\\b").rstrip(":\\b").strip("()")
            counts[label] = len(matches)
    return counts


def sanitize_email_html(html: str | None) -> SanitizationResult:
    """Clean HTML body for safe rendering in a sandboxed iframe.

    Empty/None input returns empty result. Does NOT raise on malformed
    input — bleach handles malformed HTML gracefully (one of its
    canonical strengths).
    """
    if not html:
        return SanitizationResult(
            cleaned_html="",
            original_length=0,
            cleaned_length=0,
        )

    danger_summary = detect_dangerous_content(html)
    cleaned = _CLEANER.clean(html)

    # Annotate img tags with data-external / data-tracking flags so
    # the iframe-side renderer can surface block + warning chrome.
    cleaned = _annotate_images(cleaned)

    return SanitizationResult(
        cleaned_html=cleaned,
        original_length=len(html),
        cleaned_length=len(cleaned),
        dangerous_content_detected=bool(danger_summary),
        stripped_summary=danger_summary,
    )


def _annotate_images(html: str) -> str:
    """Add data-external / data-tracking attributes to img tags so the
    sandboxed iframe can render block + warning chrome.

    Pattern: any img with src starting with cid: → data-cid="true".
    Otherwise → data-external="true". Width/height of 0 or 1 → also
    data-tracking="true".
    """
    img_re = re.compile(r"<img\b([^>]*)>", re.IGNORECASE)

    def _process(match: re.Match) -> str:
        attrs = match.group(1)
        # Detect cid: vs external
        is_cid = bool(re.search(r"src=['\"]cid:", attrs, re.IGNORECASE))
        annotation = ' data-cid="true"' if is_cid else ' data-external="true"'
        # Detect tracking pixel
        w_match = re.search(
            r'width=["\']?([^"\'\s>]+)', attrs, re.IGNORECASE
        )
        h_match = re.search(
            r'height=["\']?([^"\'\s>]+)', attrs, re.IGNORECASE
        )
        tracking = False
        if w_match and _TRACKING_PIXEL_SIZE.match(w_match.group(1)):
            if h_match and _TRACKING_PIXEL_SIZE.match(h_match.group(1)):
                tracking = True
        if tracking:
            annotation += ' data-tracking="true"'
        return f"<img{attrs}{annotation}>"

    return img_re.sub(_process, html)


# ─────────────────────────────────────────────────────────────────────
# iframe srcdoc construction
# ─────────────────────────────────────────────────────────────────────


_SRCDOC_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<style>
  body {{
    margin: 0;
    padding: 12px;
    font-family: -apple-system, BlinkMacSystemFont, 'IBM Plex Sans', sans-serif;
    font-size: 14px;
    color: #1a1a1a;
    line-height: 1.5;
  }}
  img[data-external="true"][data-blocked="true"] {{
    display: inline-block;
    width: 80px;
    height: 30px;
    background: #f5f0e8;
    border: 1px dashed #c4a880;
    color: #6b5a40;
    text-align: center;
    line-height: 30px;
    font-size: 11px;
    text-decoration: none;
  }}
  img[data-tracking="true"] {{
    display: none !important;
  }}
  blockquote {{
    border-left: 3px solid #d4c4a8;
    margin: 8px 0;
    padding: 4px 12px;
    color: #6b5a40;
  }}
  a {{
    color: #9C5640;
  }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def build_srcdoc(
    cleaned_html: str,
    *,
    block_external_images: bool = True,
) -> str:
    """Construct iframe srcdoc with CSP + image-blocking style.

    The CSP prevents script execution + restricts external resource
    loading. Image-blocking is optional — caller flips when user has
    opted in to "show images for this sender".
    """
    if block_external_images:
        # Mark all data-external images as blocked via attribute
        # toggle. The CSS selector above renders them as a placeholder
        # block.
        body = re.sub(
            r'<img([^>]*data-external="true"[^>]*)>',
            r'<img\1 data-blocked="true">',
            cleaned_html,
        )
        csp = (
            "default-src 'none'; "
            "img-src cid: data:; "
            "style-src 'unsafe-inline'; "
            "font-src 'self' data:; "
            "frame-ancestors 'self';"
        )
    else:
        body = cleaned_html
        csp = (
            "default-src 'none'; "
            "img-src cid: data: https: http:; "
            "style-src 'unsafe-inline'; "
            "font-src 'self' data:; "
            "frame-ancestors 'self';"
        )

    return _SRCDOC_TEMPLATE.format(csp=csp, body=body)
