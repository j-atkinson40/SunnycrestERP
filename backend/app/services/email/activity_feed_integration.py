"""V-1c CRM activity feed integration for email events —
Phase W-4b Layer 1 Step 5 Surface 3.

Per §3.26.15.10 + Step 5 spec: email events surface in V-1c entity
activity feeds (V-1c CRM activity feed canon). Email is one of
multiple event source types in the existing pluralistic activity log.

**No new infrastructure** — uses the canonical
``app.services.crm.activity_log_service.log_system_event()`` write
path. Existing ``RecentActivityWidget`` already maps the ``email``
activity_type to "logged an email" verb (line 75 of the widget),
so frontend rendering ships unchanged.

**Three write sites wired**:
  1. **Inbound message ingestion** (``ingest_provider_message`` flow):
     when an inbound message resolves participants to a known
     CompanyEntity, write an activity row for that entity.
  2. **Outbound message send** (``send_message`` flow): when an
     outbound message is sent to a recipient that resolves to a
     CompanyEntity, write an activity row.
  3. **Explicit thread linkage** (``EmailThreadLinkage`` create):
     when a thread is manually linked to a customer entity, write
     an activity row for the entity.

**master_company_id resolver helper**:
  - Direct: ``EmailThreadLinkage`` with linked_entity_type="customer"
    + linked_entity_id is a CompanyEntity.id → use directly
  - Direct: ``EmailParticipant.resolved_company_entity_id`` is a
    CompanyEntity.id → use directly
  - Indirect: ``EmailThreadLinkage`` with linked_entity_type="fh_case"
    + linked_entity_id is an FHCase.id → resolve via
    FHCase.customer_id → Customer.master_company_id
  - Indirect: ``EmailThreadLinkage`` with linked_entity_type=
    "sales_order" + linked_entity_id is a SalesOrder.id → resolve via
    SalesOrder.customer_id → Customer.master_company_id

**Tenant isolation discipline**:
  - Every activity write enforces ``tenant_id`` matches the email
    message's tenant_id
  - Cross-tenant CompanyEntity references are NOT written into the
    caller's activity feed (per §3.25.x masking — partner tenant's
    CompanyEntity surfaces only in their own activity log)

**Failure-mode discipline**:
  - Activity log writes are best-effort; failures are logged but
    NEVER block email ingestion / send
  - Mirror of the canonical CRM activity log discipline
    (``log_system_event`` already wraps in try/except)

**Click-through routing**:
  - Activity row body carries ``thread_id=<uuid>`` reference; widget
    click navigates to ``/inbox?thread_id=<id>``
  - Existing ``RecentActivityWidget`` row composition supports this
    via the body field — no widget changes
"""

from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.email_primitive import (
    EmailMessage,
    EmailParticipant,
    EmailThread,
    EmailThreadLinkage,
)

logger = logging.getLogger(__name__)


def _resolve_master_company_ids_for_thread(
    db: Session, thread: EmailThread
) -> set[str]:
    """Return the set of CompanyEntity ids that should receive an
    activity log entry for events on this thread.

    Sources (deduped via set):
      1. EmailThreadLinkage with linked_entity_type="customer" →
         linked_entity_id IS a CompanyEntity.id (use directly)
      2. EmailParticipant.resolved_company_entity_id (auto-resolved
         contacts whose master_company linkage points at a
         CompanyEntity)
      3. EmailThreadLinkage with linked_entity_type="fh_case" →
         resolve FHCase → Customer.master_company_id
      4. EmailThreadLinkage with linked_entity_type="sales_order" →
         resolve SalesOrder → Customer.master_company_id

    Tenant-scoped via thread.tenant_id; we never resolve cross-tenant
    company entities. Returns empty set when thread has no resolvable
    master_company linkage (e.g., personal-account thread with no
    CRM-known participants).
    """
    master_company_ids: set[str] = set()

    # Source 1: explicit customer linkage (linked_entity_id IS
    # CompanyEntity.id directly per V-1c CRM canon)
    linkage_rows = (
        db.query(
            EmailThreadLinkage.linked_entity_type,
            EmailThreadLinkage.linked_entity_id,
        )
        .filter(
            EmailThreadLinkage.thread_id == thread.id,
            EmailThreadLinkage.tenant_id == thread.tenant_id,
            EmailThreadLinkage.dismissed_at.is_(None),
        )
        .all()
    )
    for entity_type, entity_id in linkage_rows:
        if entity_type == "customer":
            master_company_ids.add(entity_id)
        elif entity_type == "fh_case":
            mc_id = _resolve_master_company_for_case(
                db, fh_case_id=entity_id, tenant_id=thread.tenant_id
            )
            if mc_id:
                master_company_ids.add(mc_id)
        elif entity_type == "sales_order":
            mc_id = _resolve_master_company_for_order(
                db, sales_order_id=entity_id, tenant_id=thread.tenant_id
            )
            if mc_id:
                master_company_ids.add(mc_id)
        # Other entity types (vault_item, cross_tenant_thread) do not
        # surface in CRM activity feeds — they are not CompanyEntity-
        # scoped surfaces. Future entity types extend this dispatch
        # by adding a branch here.

    # Source 2: auto-resolved participant linkage
    participant_rows = (
        db.query(EmailParticipant.resolved_company_entity_id)
        .filter(
            EmailParticipant.thread_id == thread.id,
            EmailParticipant.resolved_company_entity_id.isnot(None),
        )
        .all()
    )
    for (company_entity_id,) in participant_rows:
        if company_entity_id:
            master_company_ids.add(company_entity_id)

    return master_company_ids


def _resolve_master_company_for_case(
    db: Session, *, fh_case_id: str, tenant_id: str
) -> str | None:
    """Resolve FHCase.customer_id → Customer.master_company_id.

    Returns None when the FH case doesn't exist in the tenant OR has
    no customer linkage OR the customer has no master_company_id.
    """
    try:
        from app.models.fh_case import FHCase
        from app.models.customer import Customer

        case = (
            db.query(FHCase.customer_id)
            .filter(
                FHCase.id == fh_case_id,
                FHCase.company_id == tenant_id,
            )
            .first()
        )
        if not case or not case[0]:
            return None
        cust = (
            db.query(Customer.master_company_id)
            .filter(
                Customer.id == case[0],
                Customer.company_id == tenant_id,
            )
            .first()
        )
        return cust[0] if cust and cust[0] else None
    except Exception:
        # Defensive — FHCase / Customer model issues should never block
        # email ingestion
        logger.exception(
            "Failed to resolve master_company for fh_case %s", fh_case_id
        )
        return None


def _resolve_master_company_for_order(
    db: Session, *, sales_order_id: str, tenant_id: str
) -> str | None:
    """Resolve SalesOrder.customer_id → Customer.master_company_id."""
    try:
        from app.models.customer import Customer
        from app.models.sales_order import SalesOrder

        so = (
            db.query(SalesOrder.customer_id)
            .filter(
                SalesOrder.id == sales_order_id,
                SalesOrder.company_id == tenant_id,
            )
            .first()
        )
        if not so or not so[0]:
            return None
        cust = (
            db.query(Customer.master_company_id)
            .filter(
                Customer.id == so[0],
                Customer.company_id == tenant_id,
            )
            .first()
        )
        return cust[0] if cust and cust[0] else None
    except Exception:
        logger.exception(
            "Failed to resolve master_company for sales_order %s",
            sales_order_id,
        )
        return None


def log_email_event_for_thread(
    db: Session,
    *,
    message: EmailMessage,
    thread: EmailThread,
    actor_user_id: str | None = None,
    direction_label: str | None = None,
) -> None:
    """Write activity log entries for every CompanyEntity that should
    surface this email event in their V-1c activity feed.

    Best-effort; failures are logged but never block the caller. The
    canonical ``activity_log_service.log_system_event`` already wraps
    write failures in try/except — this wrapper adds master_company
    resolution + per-entity fan-out on top.

    Args:
      message: the persisted EmailMessage
      thread: the EmailMessage's parent EmailThread (passed in to avoid
        a re-fetch since the caller usually has it in scope)
      actor_user_id: for outbound messages, the User who composed the
        send (None for inbound — inbound has no Bridgeable actor).
      direction_label: optional override; defaults to "Sent" for
        outbound, "Received" for inbound.
    """
    if not message or not thread:
        return

    try:
        master_company_ids = _resolve_master_company_ids_for_thread(db, thread)
    except Exception:
        logger.exception(
            "master_company resolution failed for thread %s", thread.id
        )
        return

    if not master_company_ids:
        # No CRM linkage — nothing to write. Activity feed surface is
        # CompanyEntity-scoped; threads without a customer linkage
        # don't surface there.
        return

    # Build display fields
    if direction_label is None:
        direction_label = (
            "Sent" if message.direction == "outbound" else "Received"
        )
    sender_display = (
        message.sender_name
        if message.sender_name
        else message.sender_email
    )
    subject = thread.subject or message.subject or "(no subject)"
    title = f"{direction_label} email — {subject}"

    # Body carries thread_id reference for click-through navigation
    # (widget renders body field; click resolves /inbox?thread_id=).
    body = (
        f"From {sender_display}. "
        f"thread_id={thread.id}"
    )

    # Defer import to avoid circular cycles between email + crm
    # service modules.
    from app.services.crm.activity_log_service import log_system_event

    for master_company_id in master_company_ids:
        try:
            log_system_event(
                db,
                tenant_id=thread.tenant_id,
                master_company_id=master_company_id,
                activity_type="email",
                title=title,
                body=body,
            )
        except Exception:
            logger.exception(
                "log_system_event failed for thread=%s master_company=%s",
                thread.id,
                master_company_id,
            )
            # Continue to other entities — one failure shouldn't
            # cascade to skip the rest


def fan_out_master_company_ids(
    master_company_ids: Iterable[str],
) -> list[str]:
    """Return a deterministic-ordered list of unique master_company ids.

    Helper for tests + callers who need a stable order over a set.
    """
    return sorted({mc_id for mc_id in master_company_ids if mc_id})
