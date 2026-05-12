"""Mention substrate — Arc 4b.2a.

Jinja `ref` filter + per-render cache for entity mentions inside
block-authored document templates.

Token shape (canonical, Q-ARC4B2-1):
    {{ ref("case", "<uuid>") }}
    {{ ref("order", "<uuid>") }}
    {{ ref("contact", "<uuid>") }}
    {{ ref("product", "<uuid>") }}

Rendering shape (Q-ARC4B2-2, v1):
    Reference-only — emits `@DisplayName` as an inline anchor. The
    Phase 1 resolver returns the same `primary_label` used by the
    command bar; this surface re-uses it as the display_name. The
    resolver's `secondary_context` is exposed to the picker endpoint
    (Arc 4b.2b consumer) as preview_snippet but NOT rendered at v1.

    Hover-tooltip preview deferred to
    Arc-4b.x-mention-hover-preview bounded sub-arc when concrete
    operator signal warrants.

Cache scope (Q-ARC4B2-3):
    Per-render request-scoped. `MentionResolutionCache` lives at the
    render-pipeline layer; one cache instance per render-pass. Same
    `(entity_type, entity_id)` requested multiple times in one
    template resolves once. Cache discarded at render-pass completion.

    Cross-render cache (Option c) deferred — trigger criteria locked
    at investigation.

UI vocabulary translation (per-consumer endpoint shaping canon):
    Picker uses UI vocabulary `case` / `order` / `contact` / `product`.
    Substrate uses canonical entity_type vocabulary `fh_case` /
    `sales_order` / `contact` / `product`. Translation happens at the
    Jinja filter boundary AND at the dedicated mention endpoint
    boundary — single canonical translation table at
    `MENTION_PICKER_VOCAB`.

Cross-primitive scope: Phase 1 entity resolver substrate is shared
(Phase 1 command bar + this mention layer). Per-consumer endpoint
shaping canon (Arc 3b) — each consumer gets its own endpoint shape;
shared underlying substrate. The vocabulary translation is a
consumer-boundary concern, not a substrate concern.

Entity-not-found canonical placeholder copy:
    `@[deleted {ui_label}]` — e.g. `@[deleted case]`. Filter never
    breaks template rendering; missing entities surface visibly so
    operators notice + can clean up references.

Picker subset (Q-COUPLING-1):
    4 entity types — case, order, contact, product. Substrate
    supports 7 entity types but the picker UI surface ships with the
    4 most-mentioned. Expansion trigger criteria locked at
    investigation.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from markupsafe import Markup, escape
from sqlalchemy.orm import Session

from app.services.command_bar.resolver import (
    SEARCHABLE_ENTITIES,
    ResolverHit,
)

logger = logging.getLogger(__name__)


# ── Vocabulary translation (Q-COUPLING-1 + UI vocabulary boundary) ────


# UI picker vocabulary → substrate entity_type vocabulary.
# This is the canonical translation table; the dedicated mention
# endpoint applies the same mapping at request layer.
MENTION_PICKER_VOCAB: dict[str, str] = {
    "case": "fh_case",
    "order": "sales_order",
    "contact": "contact",
    "product": "product",
}

# Reverse mapping: substrate → UI label. Used when rendering entity-
# not-found placeholders so the operator sees the UI vocabulary they
# authored against (e.g. `@[deleted case]` not `@[deleted fh_case]`).
MENTION_PICKER_UI_LABEL: dict[str, str] = {
    v: k for k, v in MENTION_PICKER_VOCAB.items()
}


def picker_vocab_to_substrate(ui_vocab: str) -> str | None:
    """Translate UI picker vocabulary to substrate entity_type.

    Returns None for unknown UI vocabulary (caller decides how to
    surface — typically 422 at request layer or placeholder at render
    layer)."""
    return MENTION_PICKER_VOCAB.get(ui_vocab)


def substrate_to_picker_ui_label(entity_type: str) -> str:
    """Translate substrate entity_type to UI label.

    Returns the substrate string verbatim if not in the picker subset
    (defensive — entities outside the picker can still be referenced
    by tokens authored manually)."""
    return MENTION_PICKER_UI_LABEL.get(entity_type, entity_type)


# ── Per-render cache (Q-ARC4B2-3) ─────────────────────────────────────


@dataclass
class _ResolvedMention:
    """Cached resolution of a single entity mention."""

    entity_type: str
    entity_id: str
    display_name: str
    url: str | None
    found: bool


@dataclass
class MentionResolutionCache:
    """Per-render-pass cache for mention resolutions.

    Lifecycle: instantiated at render-pipeline entry; passed to the
    Jinja environment as a filter-bound context; discarded at render-
    pass completion. Does NOT persist across requests; does NOT share
    across documents in a single request.

    Single render-pass dedup: same `(entity_type, entity_id)` requested
    multiple times in one template (e.g. a case mentioned in heading +
    body) resolves once.

    Boundary discipline per Q-ARC4B2-3:
        - Scope: per-render-request, request-scoped
        - Lifecycle: created at render start; discarded at render end
        - Cross-render cache deferred (Option c); trigger criteria
          locked at investigation
    """

    db: Session
    company_id: str
    _store: dict[tuple[str, str], _ResolvedMention] = field(default_factory=dict)
    _resolution_count: int = 0
    """Total resolutions attempted (cache hits + misses). For
    diagnostics — confirms dedup behaviour in tests."""

    def resolve(self, entity_type: str, entity_id: str) -> _ResolvedMention:
        """Resolve a single mention, hitting the cache on repeat lookups.

        `entity_type` here is the SUBSTRATE vocabulary (e.g.
        `fh_case`), not the UI vocabulary. The caller (filter or
        endpoint) translates before calling resolve().
        """
        self._resolution_count += 1
        key = (entity_type, entity_id)
        cached = self._store.get(key)
        if cached is not None:
            return cached

        resolved = _resolve_single_entity(
            self.db, entity_type=entity_type, entity_id=entity_id,
            company_id=self.company_id,
        )
        self._store[key] = resolved
        return resolved

    @property
    def resolution_count(self) -> int:
        """Total invocations of resolve() — diagnostic only."""
        return self._resolution_count

    @property
    def unique_resolutions(self) -> int:
        """Count of unique (entity_type, entity_id) tuples that hit DB.
        Equals len(_store)."""
        return len(self._store)


def _resolve_single_entity(
    db: Session, *, entity_type: str, entity_id: str, company_id: str,
) -> _ResolvedMention:
    """Single-entity lookup against the Phase 1 SEARCHABLE_ENTITIES
    catalog. Tenant-scoped via `company_id`.

    Returns _ResolvedMention with `found=True` on hit; `found=False`
    with placeholder display_name on miss. Never raises — entity-
    not-found is a render-time placeholder, not an error.
    """
    ent_cfg = next(
        (e for e in SEARCHABLE_ENTITIES if e.entity_type == entity_type),
        None,
    )
    if ent_cfg is None:
        # Unknown entity_type — author may have typed a bad token.
        # Surface as deleted-placeholder; never crash.
        logger.warning(
            "mention_filter: unknown entity_type %r — rendering placeholder",
            entity_type,
        )
        return _ResolvedMention(
            entity_type=entity_type, entity_id=entity_id,
            display_name=f"[unknown {entity_type}]",
            url=None, found=False,
        )

    # Direct primary-key lookup; bypass pg_trgm scoring (resolver is
    # query-text based; mention rendering is id-based).
    #
    # Implementation note: Postgres-specific `::varchar` casts are
    # avoided here so the same SQL works in test fixtures (SQLite).
    # Phase 1 resolver.py uses casts for UNION ALL type-coercion;
    # this id-lookup query doesn't UNION across entity types so the
    # casts aren't needed.
    from sqlalchemy import text

    is_active_filter = ""
    if ent_cfg.entity_type in ("contact", "product"):
        is_active_filter = "AND is_active = TRUE"

    extra_id_col = (
        "master_company_id"
        if ent_cfg.entity_type == "contact"
        else "NULL AS master_company_id"
    )

    sql = f"""
        SELECT
            {ent_cfg.id_col} AS entity_id,
            ({ent_cfg.primary_label_expr}) AS primary_label,
            {extra_id_col}
        FROM {ent_cfg.table}
        WHERE {ent_cfg.id_col} = :entity_id
          AND company_id = :company_id
          {is_active_filter}
        LIMIT 1
    """

    try:
        row = db.execute(
            text(sql),
            {"entity_id": entity_id, "company_id": company_id},
        ).fetchone()
    except Exception:
        logger.exception(
            "mention_filter._resolve_single_entity SQL failed "
            "(entity_type=%s entity_id=%s)",
            entity_type, entity_id,
        )
        return _ResolvedMention(
            entity_type=entity_type, entity_id=entity_id,
            display_name=_placeholder_for(entity_type),
            url=None, found=False,
        )

    if row is None:
        # Entity not found / deleted / cross-tenant — render placeholder.
        return _ResolvedMention(
            entity_type=entity_type, entity_id=entity_id,
            display_name=_placeholder_for(entity_type),
            url=None, found=False,
        )

    # URL substitution mirrors resolver.py's substitution logic.
    if ent_cfg.entity_type == "contact":
        url = ent_cfg.url_template.format(
            master_company_id=row.master_company_id or row.entity_id
        )
    else:
        url = ent_cfg.url_template.format(id=row.entity_id)

    display = (row.primary_label or "").strip() or _placeholder_for(entity_type)
    return _ResolvedMention(
        entity_type=entity_type, entity_id=entity_id,
        display_name=display, url=url, found=True,
    )


def _placeholder_for(entity_type: str) -> str:
    """Canonical entity-not-found placeholder copy.

    Form: `[deleted <ui_label>]` — surfaces in the rendered document
    so operators notice broken references. UI label uses picker
    vocabulary (e.g. `case`) when the substrate type maps; falls
    back to the substrate string for unmapped types.
    """
    ui_label = substrate_to_picker_ui_label(entity_type)
    return f"[deleted {ui_label}]"


# ── Jinja filter (Q-ARC4B2-1) ─────────────────────────────────────────


def make_ref_filter(cache: MentionResolutionCache):
    """Build a Jinja-compatible `ref` filter bound to a render-pass
    cache.

    Used as a Jinja **global** (function-call form: `ref("case", "id")`)
    rather than a filter so the canonical token shape stays a clean
    function call. Jinja Environment.globals['ref'] = make_ref_filter(...).

    Filter accepts:
        entity_type: UI vocabulary picker string (`case`/`order`/`contact`/`product`)
                     OR substrate vocabulary (`fh_case`/`sales_order`/...).
                     Translation applied transparently; both forms work.
        entity_id:   String UUID.

    Returns Markup (autoescape-safe inline HTML anchor when entity
    resolves; plain placeholder text when not found).

    Entity-not-found never raises — returns escaped placeholder.
    """

    def _ref(entity_type: Any, entity_id: Any) -> Markup:
        # Defensive coercion: Jinja may pass non-strings if author wrote
        # `{{ ref(1, 2) }}` by accident.
        et = str(entity_type) if entity_type is not None else ""
        eid = str(entity_id) if entity_id is not None else ""

        if not et or not eid:
            # Token shape failure (author typed `{{ ref("", "") }}` or
            # similar) — surface as visible placeholder rather than
            # silent empty.
            return Markup("@[invalid mention]")

        # Translate UI vocabulary → substrate if applicable; otherwise
        # pass through. Both `{{ ref("case", ...) }}` and
        # `{{ ref("fh_case", ...) }}` resolve identically.
        substrate_type = MENTION_PICKER_VOCAB.get(et, et)

        resolved = cache.resolve(substrate_type, eid)

        # Build the rendered anchor.
        display_escaped = escape(resolved.display_name)
        if resolved.found and resolved.url:
            url_escaped = escape(resolved.url)
            return Markup(
                f'<a href="{url_escaped}" class="doc-mention" '
                f'data-entity-type="{escape(substrate_type)}" '
                f'data-entity-id="{escape(eid)}">'
                f'@{display_escaped}'
                f'</a>'
            )
        # Not found / unknown type — placeholder with explicit class
        # so consumers can style.
        return Markup(
            f'<span class="doc-mention doc-mention-deleted" '
            f'data-entity-type="{escape(substrate_type)}" '
            f'data-entity-id="{escape(eid)}">'
            f'@{display_escaped}'
            f'</span>'
        )

    return _ref


# ── Token shape utilities ─────────────────────────────────────────────


_REF_TOKEN_RE = re.compile(
    r"""\{\{\s*ref\(\s*  # opening {{ ref(
        ['"](?P<entity_type>[a-z_]+)['"]   # 'case' or "fh_case"
        \s*,\s*
        ['"](?P<entity_id>[A-Za-z0-9_-]+)['"]   # uuid
        \s*\)\s*\}\}      # closing )}}
    """,
    re.VERBOSE,
)


def parse_ref_tokens(body: str) -> list[tuple[str, str]]:
    """Extract all `{{ ref("...", "...") }}` references from a body string.

    Returns list of `(entity_type, entity_id)` tuples in document order
    (duplicates preserved — caller can dedup if desired). Used by:
      - test fixtures that need to verify token parsing
      - future analytics surfaces (e.g. "which documents reference
        case X?") if/when needed

    Pure function — no DB, no cache.
    """
    return [
        (m.group("entity_type"), m.group("entity_id"))
        for m in _REF_TOKEN_RE.finditer(body or "")
    ]


def build_ref_token(entity_type: str, entity_id: str) -> str:
    """Build a canonical `{{ ref(...) }}` token string.

    Used by frontend serializers + tests. Both UI vocabulary
    (`case`/`order`/...) and substrate vocabulary (`fh_case`/...)
    are valid inputs; the filter normalizes at render time.
    """
    # Defensive: strip quote characters that would break the token shape.
    safe_type = str(entity_type).replace('"', '').replace("'", '')
    safe_id = str(entity_id).replace('"', '').replace("'", '')
    return f'{{{{ ref("{safe_type}", "{safe_id}") }}}}'
