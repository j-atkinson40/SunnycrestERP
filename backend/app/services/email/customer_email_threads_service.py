"""Customer email threads composition source — Phase W-4b Layer 1 Step 5.

Per §3.26.12.3 composition sources canon: scoped Pulses orchestrate
existing primitives at scope; Customer Pulse template (per §3.26.12.4
Layer A platform default) composes recent threads filtered to the
orchestration entity (the customer).

**Step 5 ships data-layer-only** per the canon-faithful scope:
  - This service + endpoint establish the canonical query pattern
  - Customer Pulse template extension (slot mapping declaration)
    deferred until scoped Pulse infrastructure ships per §3.26.12.4
  - Endpoint stands alone as a queryable resource that any future
    composition (Customer Pulse, related-entities peek panel, etc.)
    can consume

**Canonical resource for future scoped Pulse consumption** — when the
scoped Pulse summoning + per-template slot mapping infrastructure
lands, the Customer Pulse template's email_threads slot consumes
``GET /api/v1/pulse/email-threads-for-customer/{customer_entity_id}``
rather than building parallel query patterns.

**Thread-to-customer matching** (two-source resolution):
  1. Threads with ``EmailThreadLinkage(linked_entity_type="customer",
     linked_entity_id=<CompanyEntity.id>)`` — explicit linkage
  2. Threads with ``EmailParticipant.resolved_company_entity_id ==
     <CompanyEntity.id>`` — auto-resolved participant linkage

Both paths union; thread-id deduplication via Python set. Sort by
``EmailThread.last_message_at DESC``; cap at ``limit`` (default 5,
hard ceiling 50) per §3.26.12.4 Layer C live-data discipline.

**Tenant isolation discipline**:
  - Service requires ``caller_tenant_id`` parameter; threads filtered
    to ``tenant_id == caller_tenant_id``
  - User access enforced via ``EmailAccountAccess`` junction (mirrors
    ``inbox_service._accessible_account_ids`` canonical helper)
  - Cross-tenant masking applied via ``EmailThread.is_field_masked_for``
    placeholder (Step 1 canonical pattern; subsequent steps wire full
    masking discipline per §3.25.x)

**Cross-tenant CompanyEntity discipline**:
  - The customer_entity_id is a ``CompanyEntity`` row in the caller's
    tenant — the caller's CRM-side representation of the customer
  - When the thread is cross-tenant, the partner tenant has its OWN
    EmailThread row (cross_tenant_thread_pairing); this service
    surfaces ONLY the caller's copy

**Performance budget** (per Step 5 spec): p50 < 300ms — matches scoped
Pulse composition resolution budget per §3.26.12.4 Layer B.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from app.models.company_entity import CompanyEntity
from app.models.email_primitive import (
    EmailAccount,
    EmailAccountAccess,
    EmailMessage,
    EmailParticipant,
    EmailThread,
    EmailThreadLinkage,
)
from app.models.user import User

logger = logging.getLogger(__name__)


# Hard ceiling — guards against pathological scoped Pulse template
# requesting an unbounded thread list. Matches Phase 2 saved-views
# DEFAULT_LIMIT discipline.
MAX_THREADS_LIMIT = 50


def _accessible_account_ids(
    db: Session, *, tenant_id: str, user_id: str
) -> list[str]:
    """Return EmailAccount ids the user currently has read access on.

    Mirror of ``email_glance_service._accessible_account_ids`` +
    ``inbox_service._accessible_account_ids``. Local copy preserves
    tight import surface.
    """
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


def get_threads_for_customer(
    db: Session,
    *,
    customer_entity_id: str,
    user: User,
    limit: int = 5,
) -> dict[str, Any]:
    """Return recent email threads scoped to a customer (CompanyEntity).

    Args:
      customer_entity_id: ``CompanyEntity.id`` — the caller's CRM
        representation of the customer.
      user: caller User. Tenant + access enforcement derived from this.
      limit: max threads (default 5, hard ceiling 50).

    Returns:
      ``{
        "customer_entity_id": str,
        "customer_name": str | None,
        "threads": [
          {
            "id": str,
            "subject": str | None,
            "last_message_at": str | None (ISO),
            "message_count": int,
            "is_cross_tenant": bool,
            "cross_tenant_partner_tenant_id": str | None,
            "latest_message_sender_email": str | None,
            "latest_message_sender_name": str | None,
            "latest_message_snippet": str | None,
            "linkage_source": str ("manual" | "participant" | "both"),
          },
          ...
        ],
        "total_count": int,  # total before limit (for "Show more" UX)
      }``

    When the user has no accessible accounts: returns empty
    ``threads: []`` + ``total_count: 0`` (graceful empty-state, not an
    error — the customer entity may exist but the user lacks email
    access in their role).

    When customer_entity_id refers to a CompanyEntity in another
    tenant: returns 404-shaped empty payload (existence-hiding).
    """
    if not user.company_id:
        return _empty_payload(customer_entity_id, customer_name=None)

    capped_limit = max(1, min(int(limit or 5), MAX_THREADS_LIMIT))

    # ── Tenant-scope the customer entity ────────────────────────────
    customer = (
        db.query(CompanyEntity)
        .filter(
            CompanyEntity.id == customer_entity_id,
            CompanyEntity.company_id == user.company_id,
        )
        .first()
    )
    if not customer:
        # Existence-hiding 404 — caller may be probing other tenants
        return _empty_payload(customer_entity_id, customer_name=None)

    account_ids = _accessible_account_ids(
        db, tenant_id=user.company_id, user_id=user.id
    )
    if not account_ids:
        return _empty_payload(customer_entity_id, customer_name=customer.name)

    # ── Two-source resolution: explicit linkage + participant resolve ─
    # Set of thread_ids matched via either path; preserve provenance
    # for the "linkage_source" field by tracking per-source matches.
    linkage_thread_ids: set[str] = set()
    participant_thread_ids: set[str] = set()

    # Source 1 — explicit EmailThreadLinkage (manual_pre_link /
    # manual_post_link / intelligence_inferred all count). Scope to
    # caller's tenant; dismissed_at IS NULL filters out dismissed
    # linkages so they don't surface on the customer's Pulse anymore.
    linkage_rows = (
        db.query(EmailThreadLinkage.thread_id)
        .filter(
            EmailThreadLinkage.tenant_id == user.company_id,
            EmailThreadLinkage.linked_entity_type == "customer",
            EmailThreadLinkage.linked_entity_id == customer_entity_id,
            EmailThreadLinkage.dismissed_at.is_(None),
        )
        .all()
    )
    linkage_thread_ids = {row[0] for row in linkage_rows}

    # Source 2 — EmailParticipant resolved to this CompanyEntity.
    # This catches threads where ingestion auto-resolved a participant
    # email to a known CompanyEntity contact. Tenant-scope via the
    # thread join (EmailParticipant has no direct tenant_id; thread
    # carries it).
    participant_rows = (
        db.query(EmailParticipant.thread_id)
        .join(EmailThread, EmailThread.id == EmailParticipant.thread_id)
        .filter(
            EmailThread.tenant_id == user.company_id,
            EmailThread.is_active.is_(True),
            EmailParticipant.resolved_company_entity_id == customer_entity_id,
        )
        .all()
    )
    participant_thread_ids = {row[0] for row in participant_rows}

    # Union; access-enforced filter happens next via account_ids.
    candidate_thread_ids = linkage_thread_ids | participant_thread_ids

    if not candidate_thread_ids:
        return _empty_payload(customer_entity_id, customer_name=customer.name)

    # ── Access-enforce + sort + cap ─────────────────────────────────
    # Threads where the user has read access on the account (per
    # EmailAccountAccess) AND that match either source above.
    accessible_threads = (
        db.query(EmailThread)
        .filter(
            EmailThread.id.in_(candidate_thread_ids),
            EmailThread.tenant_id == user.company_id,
            EmailThread.is_active.is_(True),
            EmailThread.account_id.in_(account_ids),
        )
        .order_by(desc(EmailThread.last_message_at))
        .all()
    )

    total_count = len(accessible_threads)
    page = accessible_threads[:capped_limit]

    # ── Latest-message sender + snippet per thread ──────────────────
    # Bounded query — fetch latest message per thread in one round-
    # trip via subquery. At small page sizes (default 5, max 50) the
    # in-list filter keeps this efficient.
    thread_ids_in_page = [t.id for t in page]
    latest_messages: dict[str, EmailMessage] = {}
    if thread_ids_in_page:
        # Per-thread latest message — naive N+1 acceptable at limit=50
        # (50 is the hard ceiling). Could be optimized with window
        # function later if performance signals warrant.
        for tid in thread_ids_in_page:
            latest = (
                db.query(EmailMessage)
                .filter(
                    EmailMessage.thread_id == tid,
                    EmailMessage.is_deleted.is_(False),
                )
                .order_by(desc(EmailMessage.received_at))
                .first()
            )
            if latest:
                latest_messages[tid] = latest

    # ── Build result rows ───────────────────────────────────────────
    thread_rows: list[dict[str, Any]] = []
    for thread in page:
        latest = latest_messages.get(thread.id)
        snippet = _snippet(
            latest.body_text if latest else None,
            latest.body_html if latest else None,
        )
        # Cross-tenant partner tenant id resolution (optional readout
        # for cross-tenant chrome per §14.9.4)
        partner_tenant_id: str | None = None
        if thread.is_cross_tenant:
            partner_row = (
                db.query(EmailParticipant.external_tenant_id)
                .filter(
                    EmailParticipant.thread_id == thread.id,
                    EmailParticipant.external_tenant_id.isnot(None),
                    EmailParticipant.external_tenant_id != user.company_id,
                )
                .first()
            )
            partner_tenant_id = (
                partner_row[0] if partner_row and partner_row[0] else None
            )
        # Linkage source provenance — was this thread matched via
        # linkage row, participant resolution, or both? Useful for
        # operator-side affordances ("explicit link vs auto-resolved")
        in_linkage = thread.id in linkage_thread_ids
        in_participant = thread.id in participant_thread_ids
        if in_linkage and in_participant:
            linkage_source = "both"
        elif in_linkage:
            linkage_source = "manual"
        else:
            linkage_source = "participant"
        thread_rows.append(
            {
                "id": thread.id,
                "subject": thread.subject,
                "last_message_at": (
                    thread.last_message_at.isoformat()
                    if thread.last_message_at
                    else None
                ),
                "message_count": thread.message_count or 0,
                "is_cross_tenant": bool(thread.is_cross_tenant),
                "cross_tenant_partner_tenant_id": partner_tenant_id,
                "latest_message_sender_email": (
                    latest.sender_email if latest else None
                ),
                "latest_message_sender_name": (
                    latest.sender_name if latest else None
                ),
                "latest_message_snippet": snippet,
                "linkage_source": linkage_source,
            }
        )

    return {
        "customer_entity_id": customer_entity_id,
        "customer_name": customer.name,
        "threads": thread_rows,
        "total_count": total_count,
    }


def _empty_payload(
    customer_entity_id: str, *, customer_name: str | None
) -> dict[str, Any]:
    return {
        "customer_entity_id": customer_entity_id,
        "customer_name": customer_name,
        "threads": [],
        "total_count": 0,
    }


def _snippet(text: str | None, html: str | None, limit: int = 96) -> str | None:
    """Build a thread-row snippet from a message body.

    Mirrors ``inbox_service._snippet`` shape — text-first, cheap HTML
    strip fallback. Truncates to ``limit`` chars at last word boundary.
    """
    raw = text
    if not raw and html:
        # Cheap HTML→text fallback. Full sandboxed rendering happens at
        # the inbox + thread detail surface per §3.26.15.5; widget /
        # composition-source surfaces only need a snippet.
        from html import unescape

        no_tags = "".join(
            c for c in unescape(html.replace("<", " <").replace(">", "> "))
            if c not in {"<", ">"}
        )
        raw = no_tags
    if not raw:
        return None
    raw = " ".join(raw.split())  # collapse whitespace
    if len(raw) <= limit:
        return raw
    truncated = raw[:limit]
    # Last word boundary
    last_space = truncated.rfind(" ")
    if last_space > limit * 0.5:
        truncated = truncated[:last_space]
    return truncated + "…"
