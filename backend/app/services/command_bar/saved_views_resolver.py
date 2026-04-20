"""Saved Views resolver for the command bar — Phase 2.

Parallel to `command_bar.resolver` (the entity resolver). Given a
user query string, fuzzy-matches against saved-view titles that
the caller can see, returns hits in the command-bar ResultItem
shape at VIEW rank.

Architectural rule (per Phase 2 approved audit): DO NOT fold saved
views into the entity resolver's UNION ALL. Saved views are stored
in `vault_items` with fuzzy match on `title`; folding them into the
entity UNION would inflate the query plan + pollute the p99 budget.

The retrieval orchestrator calls entity resolver + this resolver
separately and merges results at the Python layer. VIEW-rank sort
happens in the existing TYPE_RANK ordering.

Live queries — no caching. Newly-created views show up on the very
next query; edits flow through immediately; deletes stop appearing.
This is the user-approved behavior (item #6 of the Phase 2 refinements).

Tenant isolation: EVERY query filters by `current_user.company_id`.
Permission filtering on the config.permissions.visibility rules is
applied AFTER the SQL fetches by calling crud._can_user_see — this
is the same logic crud.list_saved_views_for_user uses, so there's
one source of truth for visibility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User


logger = logging.getLogger(__name__)

# Trigram similarity threshold — matches Phase 1 entity resolver.
_SIMILARITY_THRESHOLD: float = 0.2


@dataclass
class SavedViewHit:
    """One saved view resolver result, pre-normalization."""

    view_id: str
    title: str
    description: str | None
    entity_type: str           # for the result tile's subtitle
    score: float                # trigram similarity × recency_weight


def resolve(
    db: Session,
    *,
    query_text: str,
    user: User,
    limit: int = 10,
) -> list[SavedViewHit]:
    """Fuzzy-match saved views by title.

    Tenant isolation: WHERE company_id = :company_id.
    Visibility filtering: applied AFTER the SQL — per-row via
    crud._can_user_see. SQL can't easily express the 4-level
    visibility rules that live in JSONB.

    Returns a list of SavedViewHit sorted by score desc, truncated
    to `limit`. Failures log + return empty rather than crash the
    command-bar query.
    """
    if not user.company_id:
        # Defense in depth — command-bar auth wouldn't let this
        # through, but crash-safe.
        return []

    q = (query_text or "").strip()
    if not q:
        return []

    # Fetch candidates via the trigram GIN index on vault_items.title
    # (r32). The query is broad — matches on title only — so
    # post-filtering in Python via _can_user_see is the final gate.
    sql = text(
        """
        SELECT
            id,
            title,
            description,
            metadata_json,
            company_id,
            created_by,
            similarity(title, :q) AS sim,
            GREATEST(0.3,
                     1.0 - 0.7 * (EXTRACT(EPOCH FROM NOW() - updated_at)
                                  / (86400.0 * 180))) AS recency_weight
        FROM vault_items
        WHERE company_id = :company_id
          AND item_type = 'saved_view'
          AND is_active = true
          AND title IS NOT NULL
          AND title % :q
          AND similarity(title, :q) >= :threshold
        ORDER BY (similarity(title, :q) *
                  GREATEST(0.3,
                           1.0 - 0.7 * (EXTRACT(EPOCH FROM NOW() - updated_at)
                                        / (86400.0 * 180)))) DESC
        LIMIT :limit
        """
    )
    try:
        rows = db.execute(
            sql,
            {
                "q": q,
                "company_id": user.company_id,
                "threshold": _SIMILARITY_THRESHOLD,
                "limit": max(1, min(limit * 3, 60)),  # over-fetch for post-filter
            },
        ).fetchall()
    except Exception:
        logger.exception(
            "saved_views_resolver SQL failed (q=%r company_id=%s)",
            q[:80],
            user.company_id,
        )
        return []

    # Apply post-filtering through crud._can_user_see — the canonical
    # 4-level visibility gate. Import locally to avoid a circular
    # dependency at module load (crud imports models heavily).
    from app.services.saved_views import crud as sv_crud
    from app.services.saved_views.types import SavedViewConfig
    from app.models.vault_item import VaultItem

    out: list[SavedViewHit] = []
    for row in rows:
        meta = row.metadata_json or {}
        config_dict = meta.get("saved_view_config")
        if not config_dict:
            # Malformed row — skip silently (logged elsewhere).
            continue
        try:
            cfg = SavedViewConfig.from_dict(config_dict)
        except Exception:  # noqa: BLE001
            continue

        # Build a minimal VaultItem facade for the permission check.
        # Using the real ORM row here would require a second DB
        # round-trip per hit; instead we hand _can_user_see a
        # lightweight object with the fields it inspects.
        facade = VaultItem()
        facade.id = row.id
        facade.company_id = row.company_id
        facade.created_by = row.created_by
        if not sv_crud._can_user_see(db, user, facade, cfg):
            continue

        out.append(
            SavedViewHit(
                view_id=row.id,
                title=row.title,
                description=row.description,
                entity_type=cfg.query.entity_type,
                score=float(row.sim) * float(row.recency_weight),
            )
        )
        if len(out) >= limit:
            break

    return out
