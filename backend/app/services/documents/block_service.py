"""Block CRUD service for block-based document templates (Phase D-10).

Each mutating operation:
  1. Validates the block kind + config against the registry
  2. Persists the block row(s)
  3. Recomposes the template version's body_template via block_composer
  4. Writes back the composed Jinja + aggregated variable_schema

The composed Jinja is derived from the blocks; blocks are the source
of truth. Render-time code reads body_template directly without
knowing about blocks.

Authoring is bounded to draft versions — once a version is activated,
it's immutable. Callers should create_draft → edit blocks → activate.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.document_template import DocumentTemplateVersion
from app.models.document_template_block import DocumentTemplateBlock
from app.services.documents.block_composer import compose_blocks_to_jinja
from app.services.documents.block_registry import get_block_kind


class BlockServiceError(Exception):
    """Raised on validation / state-machine failures."""

    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.http_status = http_status


# ─── Validation ─────────────────────────────────────────────────────


def _validate_block_kind(kind: str) -> None:
    try:
        get_block_kind(kind)
    except KeyError as exc:
        raise BlockServiceError(
            f"Unknown block kind: {kind!r}. {exc}",
            http_status=400,
        ) from exc


def _validate_version_is_draft(
    db: Session, version_id: str
) -> DocumentTemplateVersion:
    version = (
        db.query(DocumentTemplateVersion)
        .filter(DocumentTemplateVersion.id == version_id)
        .first()
    )
    if version is None:
        raise BlockServiceError(
            f"Template version {version_id} not found", http_status=404
        )
    if version.status != "draft":
        raise BlockServiceError(
            f"Cannot mutate blocks on a {version.status!r} version. "
            f"Only drafts are editable. Create a new draft via "
            f"create_draft + edit + activate.",
            http_status=409,
        )
    return version


def _validate_parent(
    db: Session,
    version_id: str,
    parent_block_id: str | None,
) -> DocumentTemplateBlock | None:
    if parent_block_id is None:
        return None
    parent = (
        db.query(DocumentTemplateBlock)
        .filter(DocumentTemplateBlock.id == parent_block_id)
        .first()
    )
    if parent is None:
        raise BlockServiceError(
            f"Parent block {parent_block_id} not found", http_status=404
        )
    if parent.template_version_id != version_id:
        raise BlockServiceError(
            "Parent block belongs to a different template version",
            http_status=400,
        )
    if not get_block_kind(parent.block_kind).accepts_children:
        raise BlockServiceError(
            f"Parent block kind {parent.block_kind!r} doesn't accept "
            f"children. Only conditional_wrapper accepts children.",
            http_status=400,
        )
    return parent


# ─── Recompose hook ─────────────────────────────────────────────────


def _recompose_and_persist(
    db: Session, version: DocumentTemplateVersion
) -> None:
    """Recompose body_template + variable_schema from current blocks.

    Called after every block mutation so the template stays renderable
    against the latest block state. variable_schema is merged with
    existing entries — block-declared variables get added; manually
    declared variables (set via the template editor's variable schema
    tab) are preserved.
    """
    composed = compose_blocks_to_jinja(
        db,
        version.id,
        css_variables=version.css_variables,
    )
    version.body_template = composed.body_template

    # Merge declared variables into variable_schema. Existing entries
    # win (admin may have annotated optional/required); auto-discovered
    # variables get added with a stub schema entry so the
    # template_validator's undeclared-variable check passes.
    schema = dict(version.variable_schema or {})
    for v in composed.declared_variables:
        if v not in schema:
            schema[v] = {"type": "string", "auto_declared": True}
    version.variable_schema = schema
    # Flush so the UPDATE lands in the same transaction as the block
    # mutation. Without this, a subsequent `db.refresh()` on the
    # version instance discards the pending changes.
    db.flush()


# ─── Public API ─────────────────────────────────────────────────────


def list_blocks(
    db: Session, version_id: str
) -> list[DocumentTemplateBlock]:
    """Return all blocks (top-level + nested) for a version, ordered
    by position. Caller filters by parent_block_id to pick the level."""
    return (
        db.query(DocumentTemplateBlock)
        .filter(DocumentTemplateBlock.template_version_id == version_id)
        .order_by(
            DocumentTemplateBlock.parent_block_id.nullsfirst(),
            DocumentTemplateBlock.position,
        )
        .all()
    )


def add_block(
    db: Session,
    *,
    version_id: str,
    block_kind: str,
    position: int | None = None,
    config: dict[str, Any] | None = None,
    condition: str | None = None,
    parent_block_id: str | None = None,
) -> DocumentTemplateBlock:
    """Add a new block to a draft version.

    If `position` is omitted, the new block is appended to the end of
    its parent context (top-level OR within the conditional_wrapper).
    Positions are normalized so consumers can pass any monotonic
    integer; the service enforces ordering.

    Returns the created block (with its DB-assigned id + timestamps).
    """
    _validate_block_kind(block_kind)
    version = _validate_version_is_draft(db, version_id)
    parent = _validate_parent(db, version_id, parent_block_id)

    # condition is only meaningful on conditional_wrapper
    kind_reg = get_block_kind(block_kind)
    if condition is not None and not kind_reg.accepts_children:
        raise BlockServiceError(
            f"`condition` only applies to conditional_wrapper blocks; "
            f"{block_kind!r} doesn't accept conditions.",
            http_status=400,
        )

    if position is None:
        # Append: position = max(existing) + 1 within the parent context.
        scope_filter = (
            DocumentTemplateBlock.parent_block_id == parent_block_id
            if parent_block_id
            else DocumentTemplateBlock.parent_block_id.is_(None)
        )
        max_pos = (
            db.query(DocumentTemplateBlock)
            .filter(
                DocumentTemplateBlock.template_version_id == version_id,
                scope_filter,
            )
            .count()
        )
        position = max_pos

    block = DocumentTemplateBlock(
        id=str(uuid.uuid4()),
        template_version_id=version_id,
        block_kind=block_kind,
        position=position,
        config=config or {},
        condition=condition,
        parent_block_id=parent_block_id,
    )
    db.add(block)
    db.flush()  # assign id + timestamps so recompose sees the row

    _recompose_and_persist(db, version)
    return block


def update_block(
    db: Session,
    *,
    block_id: str,
    config: dict[str, Any] | None = None,
    condition: str | None = None,
) -> DocumentTemplateBlock:
    """Update a block's config and/or condition. Position changes go
    through `reorder_blocks` so multi-block reorders are atomic."""
    block = (
        db.query(DocumentTemplateBlock)
        .filter(DocumentTemplateBlock.id == block_id)
        .first()
    )
    if block is None:
        raise BlockServiceError(
            f"Block {block_id} not found", http_status=404
        )
    version = _validate_version_is_draft(db, block.template_version_id)

    if config is not None:
        block.config = config
    if condition is not None:
        kind_reg = get_block_kind(block.block_kind)
        if not kind_reg.accepts_children:
            raise BlockServiceError(
                f"`condition` only applies to conditional_wrapper blocks",
                http_status=400,
            )
        block.condition = condition

    db.flush()
    _recompose_and_persist(db, version)
    return block


def delete_block(db: Session, *, block_id: str) -> str:
    """Delete a block. Children of a conditional_wrapper are deleted
    explicitly (DB-level CASCADE works on Postgres but isn't
    reliable on SQLite test fixtures unless `PRAGMA foreign_keys=ON`
    is enabled — explicit deletion is portable across both).

    Returns the version_id that was affected (so the caller can refresh
    its view of the version)."""
    block = (
        db.query(DocumentTemplateBlock)
        .filter(DocumentTemplateBlock.id == block_id)
        .first()
    )
    if block is None:
        raise BlockServiceError(
            f"Block {block_id} not found", http_status=404
        )
    version = _validate_version_is_draft(db, block.template_version_id)
    version_id = block.template_version_id

    # Explicit children cleanup. Query rather than rely on the
    # `block.children` relationship cache (same rationale as the
    # composer's explicit query).
    children = (
        db.query(DocumentTemplateBlock)
        .filter(DocumentTemplateBlock.parent_block_id == block_id)
        .all()
    )
    for child in children:
        db.delete(child)
    db.delete(block)
    db.flush()
    _recompose_and_persist(db, version)
    return version_id


def reorder_blocks(
    db: Session,
    *,
    version_id: str,
    block_id_order: list[str],
    parent_block_id: str | None = None,
) -> list[DocumentTemplateBlock]:
    """Set new positions for blocks in a single parent context (top-level
    OR within a single conditional_wrapper).

    The caller passes block ids in the desired order; positions are
    assigned 0..N-1. Atomic — either all blocks reorder or none do.
    """
    version = _validate_version_is_draft(db, version_id)

    # Validate every id belongs to this version + parent context.
    blocks = (
        db.query(DocumentTemplateBlock)
        .filter(
            DocumentTemplateBlock.template_version_id == version_id,
            DocumentTemplateBlock.id.in_(block_id_order),
        )
        .all()
    )
    if len(blocks) != len(block_id_order):
        raise BlockServiceError(
            "Some block ids in reorder list don't belong to this version",
            http_status=400,
        )
    by_id = {b.id: b for b in blocks}

    # Validate parent context consistency.
    expected_parent = parent_block_id
    for b in blocks:
        if b.parent_block_id != expected_parent:
            raise BlockServiceError(
                f"Block {b.id} has parent {b.parent_block_id!r}; "
                f"reorder targets parent {expected_parent!r}.",
                http_status=400,
            )

    for i, block_id in enumerate(block_id_order):
        by_id[block_id].position = i

    db.flush()
    _recompose_and_persist(db, version)
    return [by_id[bid] for bid in block_id_order]
