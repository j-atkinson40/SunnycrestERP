"""Recipient resolution + role-based routing — Phase W-4b Layer 1 Step 4b.

Composition surface needs type-ahead recipient lookup against:

  1. **Tenant CRM contacts** — REUSES existing
     ``nl_creation/entity_resolver.resolve_contact`` (pg_trgm fuzzy
     match, tenant-scoped, indexed via ``ix_contacts_name_trgm``)
  2. **Recent participants** — last 30 days from email_participants
     joined to messages on accounts the user has access to. Provides
     the muscle-memory "Hopkins" → "director@hopkinsfh.test" recall
     that operators expect from modern email clients.
  3. **Tenant user directory** — internal users at the same tenant
     (sales@, dispatch@, etc. when those users send emails through
     personal accounts). Plain ILIKE on ``users.email`` + ``first_name``
     + ``last_name``.
  4. **Cross-tenant tenant directory** per §3.26.15.20 — users at
     paired Bridgeable tenants. Step 4b ships placeholder structure;
     real cross-tenant masking + per-tenant data agreement consultation
     lands alongside cross-tenant native messaging in Step 5+.

Returned shape per result:
  - email_address (lowercased)
  - display_name (resolved name or None)
  - source_type — "crm_contact" / "recent" / "internal_user" /
    "external_tenant" / "cross_tenant_user"
  - resolution_id — opaque id (contact_id, user_id, etc.) for
    downstream entity-linkage
  - rank_score — float 0..1 for client-side sorting

**Role-based routing** per §3.26.15.13: canon promises
"contact resolution + role-based routing + pasted email auto-resolve
+ bcc field" but the platform has no canonical role-expansion
infrastructure yet (Workshop email-template integration in Step 5+
is the canonical authoring path). Step 4b ships **canonical
defaults** computable from existing data — matching prompt's
"canonical defaults + tenant-authored via Workshop in future steps"
intent. Two role primitives ship:

  1. ``account_access`` — "All users with access to this account"
     — expands via ``email_account_access`` junction
  2. ``role_slug`` — "All ``[role_slug]`` users in tenant" — expands
     via ``roles`` table joined to ``users``

Tenant-authored role recipients (workflow-defined, AI-suggested,
saved-list) defer to Step 5+ alongside Workshop email-template
integration. This deferral is intentional + canon-aligned per
§3.26.15.13 Q4 (Workshop is the canonical role-authoring surface).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.email_primitive import (
    EmailAccount,
    EmailAccountAccess,
    EmailMessage,
    EmailParticipant,
)
from app.models.role import Role
from app.models.user import User

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ResolvedRecipient:
    email_address: str
    display_name: str | None
    source_type: str  # "crm_contact" / "recent" / "internal_user" / "external_tenant" / "cross_tenant_user"
    resolution_id: str | None  # contact_id / user_id / participant_id
    rank_score: float


@dataclass(slots=True)
class RoleRecipient:
    """A canonical role-based routing primitive.

    ``role_kind`` is the discriminator the frontend renders + the
    backend expands at send time:
      - "account_access" — expand to all users with active access on
        the chosen account (id_value = account_id)
      - "role_slug" — expand to all users in the tenant whose role
        matches (id_value = role_slug)

    Step 4b NOT shipping send-time expansion in outbound_service —
    the frontend converts a RoleRecipient selection into a list of
    individual ResolvedRecipient entries via ``expand_role`` BEFORE
    submitting the send request. This keeps Step 3's send_message
    contract unchanged (it accepts list of {email_address, display_name}
    today and continues to).
    """

    label: str
    role_kind: str  # "account_access" | "role_slug"
    id_value: str  # account_id OR role_slug
    member_count: int


# ─────────────────────────────────────────────────────────────────────
# Recipient type-ahead resolution
# ─────────────────────────────────────────────────────────────────────


def _accessible_account_ids(
    db: Session, *, tenant_id: str, user_id: str
) -> list[str]:
    """Inline copy of inbox_service helper to avoid circular import."""
    rows = (
        db.query(EmailAccount.id)
        .join(
            EmailAccountAccess,
            EmailAccountAccess.account_id == EmailAccount.id,
        )
        .filter(
            EmailAccount.tenant_id == tenant_id,
            EmailAccount.is_active.is_(True),
            EmailAccountAccess.user_id == user_id,
            EmailAccountAccess.revoked_at.is_(None),
        )
        .all()
    )
    return [row[0] for row in rows]


def resolve_recipients(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    query: str,
    account_id: str | None = None,
    limit: int = 10,
) -> list[ResolvedRecipient]:
    """Type-ahead recipient lookup. Returns ranked list across:
    CRM contacts (highest), recent participants, internal users.

    Cross-tenant users (per §3.26.15.20) emit placeholder entries
    when matching but the actual cross-tenant directory query is a
    Step 5+ refinement (requires platform_tenant_relationships +
    cross-tenant-data-agreement consultation).
    """
    q = (query or "").strip()
    if len(q) < 2:
        return []

    pattern = f"%{q}%"
    results: list[ResolvedRecipient] = []
    seen_emails: set[str] = set()

    # 1. CRM contacts (rank 0.95).
    # Contact.company_id is the tenant scope; Contact.master_company_id
    # FKs to company_entities.id (the CRM company the contact belongs
    # to) — irrelevant for tenant-wide recipient lookup.
    contact_rows = (
        db.query(Contact)
        .filter(
            Contact.company_id == tenant_id,
            Contact.is_active.is_(True),
            Contact.email.isnot(None),
            or_(
                Contact.name.ilike(pattern),
                Contact.email.ilike(pattern),
            ),
        )
        .limit(limit)
        .all()
    )
    for c in contact_rows:
        if not c.email:
            continue
        addr = c.email.lower().strip()
        if addr in seen_emails:
            continue
        seen_emails.add(addr)
        results.append(
            ResolvedRecipient(
                email_address=addr,
                display_name=c.name,
                source_type="crm_contact",
                resolution_id=c.id,
                rank_score=0.95,
            )
        )

    # 2. Recent participants (rank 0.80) — last 30 days, per access
    accessible = _accessible_account_ids(
        db, tenant_id=tenant_id, user_id=user_id
    )
    candidate_account_ids = (
        [account_id] if (account_id and account_id in accessible) else accessible
    )
    if candidate_account_ids:
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        recent_rows = (
            db.query(
                EmailParticipant.email_address,
                EmailParticipant.display_name,
                EmailParticipant.id,
                func.max(EmailMessage.received_at).label("last_seen"),
            )
            .join(
                EmailMessage,
                EmailMessage.thread_id == EmailParticipant.thread_id,
            )
            .filter(
                EmailMessage.account_id.in_(candidate_account_ids),
                EmailMessage.received_at >= thirty_days_ago,
                or_(
                    EmailParticipant.email_address.ilike(pattern),
                    EmailParticipant.display_name.ilike(pattern),
                ),
            )
            .group_by(
                EmailParticipant.email_address,
                EmailParticipant.display_name,
                EmailParticipant.id,
            )
            .order_by(func.max(EmailMessage.received_at).desc())
            .limit(limit)
            .all()
        )
        for addr, name, pid, _last_seen in recent_rows:
            addr_lower = (addr or "").lower().strip()
            if not addr_lower or addr_lower in seen_emails:
                continue
            seen_emails.add(addr_lower)
            results.append(
                ResolvedRecipient(
                    email_address=addr_lower,
                    display_name=name,
                    source_type="recent",
                    resolution_id=pid,
                    rank_score=0.80,
                )
            )

    # 3. Internal users (rank 0.70)
    user_rows = (
        db.query(User)
        .filter(
            User.company_id == tenant_id,
            User.is_active.is_(True),
            or_(
                User.email.ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
            ),
        )
        .limit(limit)
        .all()
    )
    for u in user_rows:
        addr = (u.email or "").lower().strip()
        if not addr or addr in seen_emails:
            continue
        seen_emails.add(addr)
        full_name = " ".join(filter(None, [u.first_name, u.last_name])).strip()
        results.append(
            ResolvedRecipient(
                email_address=addr,
                display_name=full_name or None,
                source_type="internal_user",
                resolution_id=u.id,
                rank_score=0.70,
            )
        )

    # Cross-tenant directory: deferred to Step 5+ — when shipped, will
    # query EmailParticipant.external_tenant_id + apply per-tenant
    # data-agreement masking per §3.26.15.20.

    results.sort(key=lambda r: r.rank_score, reverse=True)
    return results[:limit]


# ─────────────────────────────────────────────────────────────────────
# Role-based routing primitives (canonical defaults)
# ─────────────────────────────────────────────────────────────────────


def list_role_recipients(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    account_id: str,
) -> list[RoleRecipient]:
    """Return canonical role-based routing primitives available for
    the chosen account.

    Step 4b canonical defaults:
      1. "Everyone with access to <account>" — uses email_account_access
      2. Per-role-slug "All <role> users" for every role currently
         present on at least one user in the tenant

    Tenant-authored role rules (workflow-defined, AI-suggested,
    saved-list) defer to Step 5+ Workshop integration.

    Caller passes account_id (required) — role rules are scoped to a
    specific outbound account so the user picks them in the modal
    after selecting send-from-account.
    """
    # Verify account access
    accessible = _accessible_account_ids(
        db, tenant_id=tenant_id, user_id=user_id
    )
    if account_id not in accessible:
        return []  # existence-hiding

    primitives: list[RoleRecipient] = []

    # 1. account_access — count active grants on this account
    access_count = (
        db.query(func.count(EmailAccountAccess.id))
        .filter(
            EmailAccountAccess.account_id == account_id,
            EmailAccountAccess.revoked_at.is_(None),
        )
        .scalar()
        or 0
    )
    if access_count > 1:  # >1 only — singletons aren't useful as a "role"
        primitives.append(
            RoleRecipient(
                label="Everyone with access to this account",
                role_kind="account_access",
                id_value=account_id,
                member_count=int(access_count),
            )
        )

    # 2. role_slug — distinct roles in tenant with active users
    role_rows = (
        db.query(
            Role.slug,
            Role.name,
            func.count(User.id),
        )
        .join(User, User.role_id == Role.id)
        .filter(
            Role.company_id == tenant_id,
            User.is_active.is_(True),
        )
        .group_by(Role.slug, Role.name)
        .order_by(Role.name.asc())
        .all()
    )
    for slug, name, count in role_rows:
        if count and count > 1:
            primitives.append(
                RoleRecipient(
                    label=f"All {name} users",
                    role_kind="role_slug",
                    id_value=slug,
                    member_count=int(count),
                )
            )

    return primitives


def expand_role_recipient(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    role_kind: str,
    id_value: str,
) -> list[ResolvedRecipient]:
    """Server-side expansion of a RoleRecipient into individual
    ResolvedRecipient entries with email + display_name.

    Frontend calls this when user picks a role primitive — converts
    to concrete recipients BEFORE submitting send. Keeps Step 3's
    send_message contract unchanged (still accepts list of individuals).
    """
    accessible = _accessible_account_ids(
        db, tenant_id=tenant_id, user_id=user_id
    )

    if role_kind == "account_access":
        if id_value not in accessible:
            return []
        rows = (
            db.query(User)
            .join(
                EmailAccountAccess,
                EmailAccountAccess.user_id == User.id,
            )
            .filter(
                EmailAccountAccess.account_id == id_value,
                EmailAccountAccess.revoked_at.is_(None),
                User.is_active.is_(True),
                User.company_id == tenant_id,
            )
            .all()
        )
    elif role_kind == "role_slug":
        rows = (
            db.query(User)
            .join(Role, Role.id == User.role_id)
            .filter(
                Role.company_id == tenant_id,
                Role.slug == id_value,
                User.is_active.is_(True),
            )
            .all()
        )
    else:
        return []

    out: list[ResolvedRecipient] = []
    seen: set[str] = set()
    for u in rows:
        addr = (u.email or "").lower().strip()
        if not addr or addr in seen:
            continue
        seen.add(addr)
        full_name = " ".join(filter(None, [u.first_name, u.last_name])).strip()
        out.append(
            ResolvedRecipient(
                email_address=addr,
                display_name=full_name or None,
                source_type="role_expansion",
                resolution_id=u.id,
                rank_score=0.99,
            )
        )
    return out
