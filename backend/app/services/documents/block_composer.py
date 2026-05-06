"""Block composer — Phase D-10.

Compiles a tree of `document_template_blocks` rows into a complete
Jinja string. The composed Jinja is written back to
`document_template_versions.body_template`; document_renderer then
renders the Jinja exactly as it does today (no rendering-pipeline
changes — block authoring is a new authoring path, not a new
rendering path).

The composer is the only module that knows the block model. All
render-time code reads `body_template` directly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.document_template_block import DocumentTemplateBlock
from app.services.documents.block_registry import get_block_kind

logger = logging.getLogger(__name__)


@dataclass
class ComposedTemplate:
    """Output of `compose_blocks_to_jinja`."""

    body_template: str
    """Complete Jinja string ready to write to body_template."""

    declared_variables: list[str]
    """Aggregated variable list across all blocks (deduped, sorted).

    Caller can merge into `variable_schema` so the template_validator's
    undeclared-variable check passes."""

    block_count: int


# Document boilerplate — wraps the composed body in HTML structure +
# default CSS so PDF rendering works without each tenant having to
# re-author boilerplate. css_variables on the template version are
# spliced in as a `:root` block.
_DOCUMENT_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ document_title|default('Document') }}</title>
<style>
:root {
  --doc-accent: #9C5640;
  --doc-text: #1a1a1a;
  --doc-muted: #666;
  --doc-border: #d4d4d4;
__CSS_VARS__
}
@page { size: letter; margin: 0.75in; }
* { box-sizing: border-box; }
body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 10pt; color: var(--doc-text); line-height: 1.4; }
.doc-header { display: flex; justify-content: space-between; padding: 16pt 0; margin-bottom: 18pt; }
.doc-header-titles { flex: 1; }
.doc-title { font-size: 18pt; margin: 0; }
.doc-subtitle { color: var(--doc-muted); margin-top: 2pt; }
.doc-date { color: var(--doc-muted); font-size: 9pt; }
.doc-logo { max-width: 200px; max-height: 80px; }
.doc-section { margin: 14pt 0; }
.section-heading { font-size: 12pt; margin-bottom: 6pt; color: var(--doc-accent); }
.section-body { line-height: 1.5; }
.doc-line-items { width: 100%; border-collapse: collapse; margin: 12pt 0; }
.doc-line-items th, .doc-line-items td { padding: 6pt 8pt; text-align: left; border-bottom: 1px solid var(--doc-border); }
.doc-line-items th { background: #f4f4f4; font-weight: 600; }
.doc-totals { margin-left: auto; margin-top: 12pt; min-width: 240px; }
.doc-total-row td { padding: 4pt 8pt; }
.doc-total-row .doc-total-value { text-align: right; font-variant-numeric: tabular-nums; }
.doc-total-emphasis td { font-weight: 700; border-top: 2px solid var(--doc-text); padding-top: 6pt; }
.doc-signatures { margin-top: 32pt; display: flex; gap: 32pt; flex-wrap: wrap; }
.sig-block { flex: 1; min-width: 240px; }
.sig-role { font-size: 9pt; color: var(--doc-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.sig-line { margin-top: 18pt; font-family: monospace; }
.sig-date-line { margin-top: 8pt; color: var(--doc-muted); font-size: 9pt; }
</style>
</head>
<body>
__BODY_PLACEHOLDER__
</body>
</html>"""


def _format_css_vars(css_vars: dict | None) -> str:
    if not css_vars:
        return ""
    lines = []
    for k, v in css_vars.items():
        # Light validation: alphanumeric + hyphen + underscore in keys
        # (CSS custom property names). Reject anything fancy to avoid
        # injection into the <style> block.
        safe_k = "".join(
            c for c in str(k) if c.isalnum() or c in ("-", "_")
        )
        safe_v = str(v).replace("\n", " ").replace("}", "")
        if safe_k:
            lines.append(f"  --{safe_k}: {safe_v};")
    return "\n".join(lines)


def _compose_block(db: Session, block: DocumentTemplateBlock) -> str:
    """Compose a single block (recursively for conditional_wrapper).

    Queries children explicitly rather than relying on the SA
    relationship cache — composer is called immediately after block
    inserts within the same transaction, and the cached `block.children`
    can be stale (loaded as empty before the child was added).
    """
    kind = get_block_kind(block.block_kind)
    children_jinja = ""
    config = dict(block.config or {})

    if kind.accepts_children:
        children = (
            db.query(DocumentTemplateBlock)
            .filter(DocumentTemplateBlock.parent_block_id == block.id)
            .order_by(DocumentTemplateBlock.position)
            .all()
        )
        children_jinja = "\n".join(_compose_block(db, c) for c in children)
        # Pass the condition through to the compile fn via a reserved
        # config key (registry's _compile_conditional_wrapper reads it).
        config["__condition__"] = block.condition or "False"

    return kind.compile_to_jinja(config, children_jinja)


def _gather_variables(
    db: Session, block: DocumentTemplateBlock
) -> list[str]:
    """Aggregate declared variables for a block + its descendants.

    Queries children explicitly (same rationale as _compose_block).
    """
    kind = get_block_kind(block.block_kind)
    vars_list = list(kind.declared_variables(block.config or {}))
    if kind.accepts_children:
        children = (
            db.query(DocumentTemplateBlock)
            .filter(DocumentTemplateBlock.parent_block_id == block.id)
            .order_by(DocumentTemplateBlock.position)
            .all()
        )
        for child in children:
            vars_list.extend(_gather_variables(db, child))
    return vars_list


def compose_blocks_to_jinja(
    db: Session,
    template_version_id: str,
    *,
    css_variables: dict | None = None,
) -> ComposedTemplate:
    """Compose all top-level blocks for a template version into a
    complete Jinja document body.

    Top-level blocks have parent_block_id IS NULL. Children of a
    conditional_wrapper are composed recursively when their parent is
    composed; they're NOT walked at the top level.

    Empty input (no blocks) returns a minimal Jinja document so the
    template renders without error — useful while authoring a brand-
    new template incrementally.
    """
    top_level = (
        db.query(DocumentTemplateBlock)
        .filter(
            DocumentTemplateBlock.template_version_id == template_version_id,
            DocumentTemplateBlock.parent_block_id.is_(None),
        )
        .order_by(DocumentTemplateBlock.position)
        .all()
    )

    body_parts: list[str] = []
    declared: list[str] = []
    block_count = 0

    for block in top_level:
        block_count += 1
        try:
            body_parts.append(_compose_block(db, block))
            declared.extend(_gather_variables(db, block))
        except KeyError as exc:
            # Unknown block kind — defensive (validation should reject
            # these at write time, but if a kind is removed from the
            # registry while live blocks reference it, fall through with
            # a comment so authors can see what happened.
            logger.warning(
                "Block %s references unknown kind %r — skipping in compose",
                block.id,
                block.block_kind,
            )
            body_parts.append(
                f"<!-- unknown block kind {block.block_kind!r}: {exc} -->"
            )
        # Count children of conditional_wrappers too so editor surface
        # can present an accurate count.
        try:
            kind_reg = get_block_kind(block.block_kind)
            if kind_reg.accepts_children:
                block_count += len(block.children or [])
        except KeyError:
            pass

    body_jinja = "\n\n".join(body_parts) if body_parts else (
        "<p style='color:#999;font-style:italic;'>"
        "Empty document — add blocks via the editor."
        "</p>"
    )

    css_block = _format_css_vars(css_variables)
    composed = (
        _DOCUMENT_HTML_TEMPLATE
        .replace("__CSS_VARS__", "\n" + css_block if css_block else "")
        .replace("__BODY_PLACEHOLDER__", body_jinja)
    )

    # Dedupe + sort declared variables.
    deduped = sorted(set(v for v in declared if v))

    return ComposedTemplate(
        body_template=composed,
        declared_variables=deduped,
        block_count=block_count,
    )
