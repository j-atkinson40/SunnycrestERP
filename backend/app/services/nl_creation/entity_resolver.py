"""Real-time vault entity resolver for NL extraction.

Phase 4 resolves candidate names (e.g. "Hopkins FH", "John Smith",
"Mary") against the vault's entity tables during overlay extraction.
The resolver uses pg_trgm similarity matching backed by GIN trigram
indexes — same mechanism Phase 1's command-bar resolver uses.

Why this module exists alongside Phase 1's resolver:
  - Phase 1's `SEARCHABLE_ENTITIES` doesn't include `company_entity`
    (the CRM's company table). Phase 4 needs it for `case.funeral_home`,
    `sales_order.customer`, `contact.company` fields.
  - Phase 1 returns a list of hits for the command bar; Phase 4 wants
    TOP-1 resolution (there's one funeral_home pill per case, not a
    list). Narrower API.
  - Keeping Phase 4 resolution local avoids touching Phase 1's
    response shape until the Phase 5 nav/search unification.

Latency budget: <30ms per resolution. Empirically well under that on
the r33-indexed table; the budget covers network + parse overhead.

Tenant isolation: every query filters by `company_id`. The caller
(extractor) passes the user's tenant id into every resolve call.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)


# ── Result shape ─────────────────────────────────────────────────────


@dataclass
class ResolvedEntity:
    """A single top-1 resolution hit."""

    entity_id: str
    entity_type: str
    display_name: str
    similarity: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "display_name": self.display_name,
            "similarity": self.similarity,
        }


# Default minimum similarity to treat as a confident match. Per the
# spec, a below-threshold hit falls back to storing the raw string
# (user can manually link later).
DEFAULT_SIMILARITY_THRESHOLD: float = 0.35


# ── company_entity resolver ──────────────────────────────────────────


def resolve_company_entity(
    db: Session,
    *,
    query: str,
    tenant_id: str,
    filters: dict[str, Any] | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> ResolvedEntity | None:
    """Top-1 fuzzy match against `company_entities.name` for the tenant.

    `filters` is a dict of boolean role flags to AND into the query.
    Common choices:
      - {"is_funeral_home": True} for case.funeral_home
      - {"is_customer": True} for sales_order.customer (any customer)
      - {"is_vendor": True} for a sales-order supplier context
      - {} (or None) for any company_entity

    Returns the top hit above `similarity_threshold`, or None. Uses
    pg_trgm `similarity(name, :query)` backed by the r33 GIN index.
    """
    q = (query or "").strip()
    if not q or not tenant_id:
        return None

    where_clauses = ["company_id = :tenant_id", "similarity(name, :q) >= :thresh"]
    params: dict[str, Any] = {
        "tenant_id": tenant_id,
        "q": q,
        "thresh": similarity_threshold,
    }
    for flag, val in (filters or {}).items():
        # Only allow whitelisted boolean flags for safety (prevents
        # any SQL-injection-via-filter-key scenario).
        if flag not in _ALLOWED_COMPANY_ENTITY_FLAGS:
            logger.warning("resolve_company_entity: ignoring disallowed filter %s", flag)
            continue
        where_clauses.append(f"{flag} = :{flag}")
        params[flag] = bool(val)

    where = " AND ".join(where_clauses)
    sql = text(
        f"""
        SELECT id, name, similarity(name, :q) AS sim
          FROM company_entities
         WHERE {where}
         ORDER BY sim DESC, updated_at DESC NULLS LAST
         LIMIT 1
        """
    )
    try:
        row = db.execute(sql, params).first()
    except Exception:
        logger.exception("resolve_company_entity failed (query=%r)", q[:80])
        return None
    if row is None:
        return None
    return ResolvedEntity(
        entity_id=row[0],
        entity_type="company_entity",
        display_name=row[1],
        similarity=float(row[2]),
    )


# Whitelist of company_entity boolean flags we allow in `filters`.
# Keep in sync with `app.models.company_entity.CompanyEntity`.
_ALLOWED_COMPANY_ENTITY_FLAGS: set[str] = {
    "is_customer",
    "is_vendor",
    "is_funeral_home",
    "is_cemetery",
    "is_crematory",
    "is_licensee",
    "is_active",
    "is_billing_group",
}


# ── contact resolver ─────────────────────────────────────────────────


def resolve_contact(
    db: Session,
    *,
    query: str,
    tenant_id: str,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> ResolvedEntity | None:
    """Top-1 fuzzy match against `contacts.name`. Tenant-scoped."""
    q = (query or "").strip()
    if not q or not tenant_id:
        return None
    sql = text(
        """
        SELECT id, name, similarity(name, :q) AS sim
          FROM contacts
         WHERE company_id = :tenant_id
           AND similarity(name, :q) >= :thresh
         ORDER BY sim DESC, updated_at DESC NULLS LAST
         LIMIT 1
        """
    )
    try:
        row = db.execute(
            sql,
            {"tenant_id": tenant_id, "q": q, "thresh": similarity_threshold},
        ).first()
    except Exception:
        logger.exception("resolve_contact failed (query=%r)", q[:80])
        return None
    if row is None:
        return None
    return ResolvedEntity(
        entity_id=row[0],
        entity_type="contact",
        display_name=row[1],
        similarity=float(row[2]),
    )


# ── fh_case resolver ─────────────────────────────────────────────────


def resolve_fh_case(
    db: Session,
    *,
    query: str,
    tenant_id: str,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> ResolvedEntity | None:
    """Top-1 fuzzy match against `fh_cases.deceased_last_name`.

    Used when the user references an existing case by the decedent's
    surname (e.g. "add service for Hopkins"). Tenant-scoped.
    """
    q = (query or "").strip()
    if not q or not tenant_id:
        return None
    sql = text(
        """
        SELECT
            id,
            COALESCE(deceased_last_name, '') || ', ' ||
                COALESCE(deceased_first_name, '') AS display_name,
            similarity(deceased_last_name, :q) AS sim
          FROM fh_cases
         WHERE company_id = :tenant_id
           AND deceased_last_name IS NOT NULL
           AND similarity(deceased_last_name, :q) >= :thresh
         ORDER BY sim DESC, updated_at DESC NULLS LAST
         LIMIT 1
        """
    )
    try:
        row = db.execute(
            sql,
            {"tenant_id": tenant_id, "q": q, "thresh": similarity_threshold},
        ).first()
    except Exception:
        logger.exception("resolve_fh_case failed (query=%r)", q[:80])
        return None
    if row is None:
        return None
    return ResolvedEntity(
        entity_id=row[0],
        entity_type="fh_case",
        display_name=row[1],
        similarity=float(row[2]),
    )


# ── Dispatch ─────────────────────────────────────────────────────────


def resolve(
    db: Session,
    *,
    target: str,
    query: str,
    user: User,
    filters: dict[str, Any] | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> ResolvedEntity | None:
    """One-call dispatch used by the extractor.

    `target` is the entity type string from a field's
    `entity_resolver_config["target"]`. Unknown targets log + return
    None (field falls back to literal string).
    """
    tenant_id = user.company_id
    if not tenant_id:
        return None

    if target == "company_entity":
        return resolve_company_entity(
            db,
            query=query,
            tenant_id=tenant_id,
            filters=filters,
            similarity_threshold=similarity_threshold,
        )
    if target == "contact":
        return resolve_contact(
            db,
            query=query,
            tenant_id=tenant_id,
            similarity_threshold=similarity_threshold,
        )
    if target == "fh_case":
        return resolve_fh_case(
            db,
            query=query,
            tenant_id=tenant_id,
            similarity_threshold=similarity_threshold,
        )
    if target == "user":
        return resolve_user(
            db,
            query=query,
            tenant_id=tenant_id,
        )

    logger.warning("resolve: unknown target %r", target)
    return None


# ── user resolver (no trigram index yet; ILIKE on first+last) ────────


def resolve_user(
    db: Session,
    *,
    query: str,
    tenant_id: str,
) -> ResolvedEntity | None:
    """Match a user by first+last name within the tenant. No pg_trgm
    index on user names today — ILIKE is acceptable at typical
    tenant sizes (<1000 users). If user-name fuzzy match becomes a
    hot path, add a r35 migration with a trigram index."""
    q = (query or "").strip()
    if not q or not tenant_id:
        return None
    # First try "First Last" compound match via concatenation.
    like = f"%{q}%"
    sql = text(
        """
        SELECT
            id,
            (COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) AS full_name
          FROM users
         WHERE company_id = :tenant_id
           AND is_active = TRUE
           AND (
             (first_name || ' ' || last_name) ILIKE :like_q
              OR first_name ILIKE :like_q
              OR last_name ILIKE :like_q
              OR email ILIKE :like_q
           )
         ORDER BY updated_at DESC NULLS LAST
         LIMIT 1
        """
    )
    try:
        row = db.execute(
            sql, {"tenant_id": tenant_id, "like_q": like}
        ).first()
    except Exception:
        logger.exception("resolve_user failed (query=%r)", q[:80])
        return None
    if row is None:
        return None
    return ResolvedEntity(
        entity_id=row[0],
        entity_type="user",
        display_name=(row[1] or "").strip() or "(no name)",
        similarity=0.85,  # synthetic — no similarity score from ILIKE
    )


__all__ = [
    "ResolvedEntity",
    "resolve",
    "resolve_company_entity",
    "resolve_contact",
    "resolve_fh_case",
    "DEFAULT_SIMILARITY_THRESHOLD",
]
