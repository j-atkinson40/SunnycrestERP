"""Block kind registry for block-based document authoring (Phase D-10).

Each block kind has:
  - kind: stable string identifier matching `document_template_blocks.block_kind`
  - display_name + description: operator-facing
  - config_schema: JSON schema-shape dict for validation + editor controls
  - compile_to_jinja(config, children_jinja): emits a Jinja fragment
  - declared_variables(config): variables this block declares it uses

The composer at `block_composer.py` reads blocks ordered by position
and calls each kind's compile_to_jinja, concatenating the fragments
into a complete Jinja template body. The variable_schema for the
template version is aggregated from each block's declared_variables.

Block kinds canonical at v1: header, body_section, line_items,
totals, signature, conditional_wrapper. New kinds register via
`register_block_kind()` (additive — no schema migration needed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# Compile signature: (config: dict, children_jinja: str) -> str
# children_jinja is the already-composed Jinja for nested blocks
# (used by conditional_wrapper); empty string for leaf blocks.
CompileFn = Callable[[dict[str, Any], str], str]
DeclareVarsFn = Callable[[dict[str, Any]], list[str]]


@dataclass(frozen=True)
class BlockKindRegistration:
    kind: str
    display_name: str
    description: str
    config_schema: dict[str, Any]
    compile_to_jinja: CompileFn
    declared_variables: DeclareVarsFn
    accepts_children: bool = False
    """Whether this kind wraps child blocks (conditional_wrapper does)."""


# ─── In-memory registry ────────────────────────────────────────────


_REGISTRY: dict[str, BlockKindRegistration] = {}


def register_block_kind(reg: BlockKindRegistration) -> None:
    """Register a block kind. Idempotent — re-registration replaces
    the existing entry (useful for hot-reload + tests)."""
    _REGISTRY[reg.kind] = reg


def get_block_kind(kind: str) -> BlockKindRegistration:
    """Resolve a kind. Raises KeyError if unknown — callers handle as
    a 400 at the API boundary."""
    if kind not in _REGISTRY:
        raise KeyError(
            f"Unknown block kind {kind!r}. Registered kinds: "
            f"{sorted(_REGISTRY.keys())}"
        )
    return _REGISTRY[kind]


def list_block_kinds() -> list[BlockKindRegistration]:
    """Return all registered kinds. Order is registration order."""
    return list(_REGISTRY.values())


# ─── Compile helpers ────────────────────────────────────────────────


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


# ─── header ────────────────────────────────────────────────────────


def _compile_header(config: dict[str, Any], _children: str) -> str:
    show_logo = bool(config.get("show_logo", True))
    title = _safe_str(config.get("title", "{{ document_title }}"))
    subtitle = _safe_str(config.get("subtitle", ""))
    accent_color = _safe_str(config.get("accent_color", "#9C5640"))
    logo_position = _safe_str(config.get("logo_position", "top-left"))
    show_date = bool(config.get("show_date", True))

    logo_html = (
        '{% if company_logo_url %}'
        '<img src="{{ company_logo_url }}" alt="{{ company_name }}" '
        'class="doc-logo" />'
        '{% endif %}'
        if show_logo
        else ""
    )
    date_html = (
        '<div class="doc-date">{{ document_date }}</div>' if show_date else ""
    )
    subtitle_html = (
        f'<p class="doc-subtitle">{subtitle}</p>' if subtitle else ""
    )

    return f"""
<header class="doc-header doc-header-{logo_position}" style="border-top:4px solid {accent_color};">
  {logo_html}
  <div class="doc-header-titles">
    <h1 class="doc-title">{title}</h1>
    {subtitle_html}
  </div>
  {date_html}
</header>
""".strip()


def _vars_header(config: dict[str, Any]) -> list[str]:
    out = ["company_name", "document_title"]
    if config.get("show_logo", True):
        out.append("company_logo_url")
    if config.get("show_date", True):
        out.append("document_date")
    return out


# ─── body_section ───────────────────────────────────────────────────


def _compile_body_section(config: dict[str, Any], _children: str) -> str:
    heading = _safe_str(config.get("heading", ""))
    body = _safe_str(config.get("body", ""))
    accent_color = _safe_str(config.get("accent_color", ""))

    heading_html = (
        f'<h2 class="section-heading"'
        f'{f" style=\"color:{accent_color};\"" if accent_color else ""}>'
        f'{heading}</h2>'
        if heading
        else ""
    )
    return f"""
<section class="doc-section">
  {heading_html}
  <div class="section-body">{body}</div>
</section>
""".strip()


def _vars_body_section(config: dict[str, Any]) -> list[str]:
    # Body content may contain {{ var }} references; we don't parse
    # them here (the composer-level template_validator handles full
    # AST analysis on the composed Jinja). Caller declares relevant
    # vars via the variable_schema editor.
    return []


# ─── line_items ─────────────────────────────────────────────────────


def _compile_line_items(config: dict[str, Any], _children: str) -> str:
    items_var = _safe_str(config.get("items_variable", "items"))
    columns = config.get("columns") or [
        {"header": "Description", "field": "description"},
        {"header": "Qty", "field": "quantity"},
        {"header": "Unit Price", "field": "unit_price"},
        {"header": "Total", "field": "line_total"},
    ]

    th_cells = "".join(
        f'<th>{_safe_str(c.get("header", ""))}</th>' for c in columns
    )
    # Build cell expressions. Each column's `field` is a path within
    # the loop variable `item`. Format hint applied if present.
    td_cells = "".join(
        '<td>{{ '
        + f'item.{_safe_str(c.get("field", ""))}'
        + (
            f' | {_safe_str(c["format"])}'
            if c.get("format")
            else ""
        )
        + ' }}</td>'
        for c in columns
    )

    return f"""
<table class="doc-line-items">
  <thead><tr>{th_cells}</tr></thead>
  <tbody>
  {{% for item in {items_var} %}}
  <tr>{td_cells}</tr>
  {{% endfor %}}
  </tbody>
</table>
""".strip()


def _vars_line_items(config: dict[str, Any]) -> list[str]:
    return [_safe_str(config.get("items_variable", "items"))]


# ─── totals ─────────────────────────────────────────────────────────


def _compile_totals(config: dict[str, Any], _children: str) -> str:
    rows = config.get("rows") or [
        {"label": "Subtotal", "variable": "subtotal"},
        {"label": "Tax", "variable": "tax"},
        {"label": "Total", "variable": "total", "emphasis": True},
    ]
    parts = []
    for r in rows:
        label = _safe_str(r.get("label", ""))
        var = _safe_str(r.get("variable", ""))
        is_emphasis = bool(r.get("emphasis"))
        cls = "doc-total-row doc-total-emphasis" if is_emphasis else "doc-total-row"
        parts.append(
            f'<tr class="{cls}">'
            f'<td class="doc-total-label">{label}</td>'
            f'<td class="doc-total-value">{{{{ {var} }}}}</td>'
            f'</tr>'
        )
    rows_html = "\n  ".join(parts)
    return f"""
<table class="doc-totals">
  {rows_html}
</table>
""".strip()


def _vars_totals(config: dict[str, Any]) -> list[str]:
    rows = config.get("rows") or []
    return [_safe_str(r.get("variable", "")) for r in rows if r.get("variable")]


# ─── signature ──────────────────────────────────────────────────────


def _compile_signature(config: dict[str, Any], _children: str) -> str:
    parties = config.get("parties") or [{"role": "Customer"}]
    show_dates = bool(config.get("show_dates", True))

    blocks = []
    for i, party in enumerate(parties):
        role = _safe_str(party.get("role", f"Signer {i + 1}"))
        # `.sig-anchor` markers are extractable by PyMuPDF anchor
        # overlay (Phase D-5 disinterment migration). White color
        # makes them invisible in the rendered PDF while remaining
        # text-search-able.
        anchor_token = f"/sig_party_{i + 1}/"
        date_html = (
            '<div class="sig-date-line">Date: ____________</div>'
            if show_dates
            else ""
        )
        blocks.append(
            f"""
<div class="sig-block sig-block-{role.lower().replace(" ", "-")}">
  <div class="sig-role">{role}</div>
  <div class="sig-line">
    <span class="sig-anchor" style="color:white;font-size:1px;">{anchor_token}</span>
    ____________________________________
  </div>
  {date_html}
</div>
""".strip()
        )

    return (
        '<section class="doc-signatures">\n  '
        + "\n  ".join(blocks)
        + "\n</section>"
    )


def _vars_signature(_config: dict[str, Any]) -> list[str]:
    return []


# ─── conditional_wrapper ────────────────────────────────────────────


def _compile_conditional_wrapper(
    _config: dict[str, Any], children_jinja: str
) -> str:
    # The `condition` is stored on the block row, NOT in config — the
    # composer reads it from the block record and passes it via a
    # special config key when calling compile.
    condition = _safe_str(_config.get("__condition__", "False"))
    if not children_jinja:
        return ""
    return f"{{% if {condition} %}}\n{children_jinja}\n{{% endif %}}"


def _vars_conditional_wrapper(_config: dict[str, Any]) -> list[str]:
    return []


# ─── Seed registrations ─────────────────────────────────────────────


def _seed_registry() -> None:
    register_block_kind(
        BlockKindRegistration(
            kind="header",
            display_name="Header",
            description=(
                "Document header with logo, title, subtitle, accent color, "
                "and optional date. Usually the first block in a template."
            ),
            config_schema={
                "show_logo": {"type": "boolean", "default": True},
                "logo_position": {
                    "type": "enum",
                    "enum": ["top-left", "top-right", "centered"],
                    "default": "top-left",
                },
                "title": {"type": "string", "default": "{{ document_title }}"},
                "subtitle": {"type": "string", "default": ""},
                "accent_color": {"type": "string", "default": "#9C5640"},
                "show_date": {"type": "boolean", "default": True},
            },
            compile_to_jinja=_compile_header,
            declared_variables=_vars_header,
        )
    )
    register_block_kind(
        BlockKindRegistration(
            kind="body_section",
            display_name="Body Section",
            description=(
                "A section with optional heading and rich body content. "
                "Body content can include Jinja variables."
            ),
            config_schema={
                "heading": {"type": "string", "default": ""},
                "body": {"type": "text", "default": ""},
                "accent_color": {"type": "string", "default": ""},
            },
            compile_to_jinja=_compile_body_section,
            declared_variables=_vars_body_section,
        )
    )
    register_block_kind(
        BlockKindRegistration(
            kind="line_items",
            display_name="Line Items",
            description=(
                "Table iterating over a variable list. Configure columns, "
                "field paths, and optional format filters."
            ),
            config_schema={
                "items_variable": {"type": "string", "default": "items"},
                "columns": {
                    "type": "array",
                    "default": [
                        {"header": "Description", "field": "description"},
                        {"header": "Qty", "field": "quantity"},
                        {"header": "Unit Price", "field": "unit_price"},
                        {"header": "Total", "field": "line_total"},
                    ],
                },
            },
            compile_to_jinja=_compile_line_items,
            declared_variables=_vars_line_items,
        )
    )
    register_block_kind(
        BlockKindRegistration(
            kind="totals",
            display_name="Totals",
            description=(
                "Subtotal/tax/total presentation. Configure rows with "
                "labels and variable references; mark a row as emphasis "
                "for the final total."
            ),
            config_schema={
                "rows": {
                    "type": "array",
                    "default": [
                        {"label": "Subtotal", "variable": "subtotal"},
                        {"label": "Tax", "variable": "tax"},
                        {"label": "Total", "variable": "total", "emphasis": True},
                    ],
                },
            },
            compile_to_jinja=_compile_totals,
            declared_variables=_vars_totals,
        )
    )
    register_block_kind(
        BlockKindRegistration(
            kind="signature",
            display_name="Signature",
            description=(
                "Signature collection area with one block per party. "
                "Generates `.sig-anchor` markers compatible with the "
                "Phase D-5 PyMuPDF anchor overlay used by native signing."
            ),
            config_schema={
                "parties": {
                    "type": "array",
                    "default": [{"role": "Customer"}],
                },
                "show_dates": {"type": "boolean", "default": True},
            },
            compile_to_jinja=_compile_signature,
            declared_variables=_vars_signature,
        )
    )
    register_block_kind(
        BlockKindRegistration(
            kind="conditional_wrapper",
            display_name="Conditional Wrapper",
            description=(
                "Wraps child blocks in a Jinja `{% if %}` block. The "
                "condition is stored on the block row (not in config); "
                "child blocks live in the database with their parent_block_id "
                "pointing at this wrapper."
            ),
            config_schema={
                # Display label for the editor; the actual condition lives on
                # `document_template_blocks.condition`.
                "label": {"type": "string", "default": ""},
            },
            compile_to_jinja=_compile_conditional_wrapper,
            declared_variables=_vars_conditional_wrapper,
            accepts_children=True,
        )
    )


# Side-effect at import time: populate the registry. Tests that need
# isolation can clear via `_REGISTRY.clear()` + `_seed_registry()`.
_seed_registry()
