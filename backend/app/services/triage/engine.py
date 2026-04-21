"""Triage engine — session orchestration.

Public functions:
  start_session(user, queue_id)           → TriageSession row
  get_session(session_id, user)           → TriageSession row
  next_item(session_id, user)             → TriageItemSummary | None
  apply_action(session_id, item_id,
               action_id, user, ...)      → TriageActionResult
  snooze_item(session_id, item_id, user,
              wake_at, reason)            → None
  end_session(session_id, user)           → TriageSessionSummary
  queue_count(queue_id, user)             → int (pending items)

Item stream strategy:
  The queue's `source_saved_view_id` points at a Saved View (Phase 2).
  We call `saved_views.execute(view_config, tenant, tenant)` per
  `next_item` call and skip items the current user has snoozed.
  Simple, correct, and re-fetches fresh on each navigation so items
  that turned into "ineligible" between calls (someone else approved,
  status transition, etc) self-correct.

Performance:
  - next_item p50 <100ms target. Hitting the saved view executor is
    ~15ms (Phase 2 measured); snooze filter is ~2ms; assembling the
    summary is <1ms. Plenty of headroom.
  - apply_action p50 <200ms. Most handlers are single-row UPDATE +
    commit; the SS cert approve handler also sends an email (non-
    blocking in the service — it catches on failure).

Session state is persisted to `triage_sessions` so the user can
resume after a browser reload or nav away.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.triage import TriageSession, TriageSnooze
from app.models.user import User
from app.models.vault_item import VaultItem
from app.services.saved_views import (
    SavedView,
    execute as execute_saved_view,
    get_saved_view,
)
from app.services.triage import action_handlers, embedded_actions, registry
from app.services.triage.types import (
    ActionConfig,
    ActionNotAllowed,
    HandlerError,
    NoPendingItems,
    QueueNotFound,
    SessionNotFound,
    TriageActionResult,
    TriageItemSummary,
    TriageQueueConfig,
    TriageSessionSummary,
)

logger = logging.getLogger(__name__)


# ── Session lifecycle ───────────────────────────────────────────────


def start_session(
    db: Session, *, user: User, queue_id: str
) -> TriageSession:
    """Start a new triage session. If the user has an open session
    for this queue, returns that one (resume semantics) rather than
    opening a second parallel session — prevents accidental forked
    sessions."""
    config = registry.get_config(db, company_id=user.company_id, queue_id=queue_id)
    _check_user_can_access_queue(db, user, config)

    existing = (
        db.query(TriageSession)
        .filter(
            TriageSession.user_id == user.id,
            TriageSession.queue_id == queue_id,
            TriageSession.ended_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        return existing

    session = TriageSession(
        id=str(uuid.uuid4()),
        company_id=user.company_id,
        user_id=user.id,
        queue_id=queue_id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(
    db: Session, *, session_id: str, user: User
) -> TriageSession:
    session = (
        db.query(TriageSession)
        .filter(
            TriageSession.id == session_id,
            TriageSession.user_id == user.id,
        )
        .first()
    )
    if session is None:
        raise SessionNotFound(f"Triage session {session_id!r} not found")
    return session


def end_session(
    db: Session, *, session_id: str, user: User
) -> TriageSessionSummary:
    session = get_session(db, session_id=session_id, user=user)
    if session.ended_at is None:
        session.ended_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(session)
    return _to_summary(session)


# ── Item stream ─────────────────────────────────────────────────────


def next_item(
    db: Session, *, session_id: str, user: User
) -> TriageItemSummary:
    """Return the next pending item in the queue. Skips:
      - Items currently snoozed by this user for this queue
      - Items already processed in this session (tracked in
        cursor_meta.processed_ids)
    Raises NoPendingItems when none remain.
    """
    session = get_session(db, session_id=session_id, user=user)
    if session.ended_at is not None:
        raise SessionNotFound("Session already ended")

    config = registry.get_config(
        db, company_id=user.company_id, queue_id=session.queue_id
    )

    snoozed_ids = _active_snooze_entity_ids(
        db, user_id=user.id, queue_id=session.queue_id
    )
    processed_ids = set((session.cursor_meta or {}).get("processed_ids", []))

    items = _execute_queue_saved_view(db, config=config, user=user)
    for row in items:
        eid = row.get("id")
        if not eid:
            continue
        if eid in snoozed_ids or eid in processed_ids:
            continue
        session.current_item_id = eid
        db.commit()
        return _row_to_item_summary(config, row)

    raise NoPendingItems("No pending items in queue")


def queue_count(
    db: Session, *, user: User, queue_id: str
) -> int:
    """Pending item count for a queue — used by briefings (Phase 6)
    + sidebar badges. Excludes items currently snoozed by the user."""
    config = registry.get_config(
        db, company_id=user.company_id, queue_id=queue_id
    )
    _check_user_can_access_queue(db, user, config)
    snoozed_ids = _active_snooze_entity_ids(
        db, user_id=user.id, queue_id=queue_id
    )
    items = _execute_queue_saved_view(db, config=config, user=user)
    return sum(1 for r in items if r.get("id") not in snoozed_ids)


# ── Action application ──────────────────────────────────────────────


def apply_action(
    db: Session,
    *,
    session_id: str,
    item_id: str,
    action_id: str,
    user: User,
    reason: str | None = None,
    reason_code: str | None = None,
    note: str | None = None,
    payload: dict[str, Any] | None = None,
) -> TriageActionResult:
    session = get_session(db, session_id=session_id, user=user)
    if session.ended_at is not None:
        raise SessionNotFound("Session already ended")
    config = registry.get_config(
        db, company_id=user.company_id, queue_id=session.queue_id
    )

    action = _find_action(config, action_id)
    if action is None:
        raise ActionNotAllowed(
            f"Action {action_id!r} not defined for queue {session.queue_id!r}"
        )
    if action.required_permission:
        from app.services.permission_service import user_has_permission

        if not user_has_permission(user, db, action.required_permission):
            raise ActionNotAllowed(
                f"Missing permission {action.required_permission!r}"
            )
    if action.requires_reason and not (reason or reason_code):
        return TriageActionResult(
            status="errored",
            message=f"Action {action_id!r} requires a reason.",
        )

    # Step 1 — run the handler (the state-changing core).
    handler = action_handlers.get_handler(action.handler)
    if handler is None:
        raise HandlerError(
            f"Handler {action.handler!r} not registered. "
            f"Available: {action_handlers.list_handler_keys()}"
        )
    ctx = {
        "db": db,
        "user": user,
        "entity_type": config.item_entity_type,
        "entity_id": item_id,
        "queue_id": session.queue_id,
        "action_id": action_id,
        "reason": reason,
        "reason_code": reason_code,
        "note": note,
        "payload": payload or {},
    }
    handler_result = handler(ctx)
    handler_status = handler_result.get("status", "applied")
    handler_message = handler_result.get("message", "")

    # Step 2 — Playwright (if configured + handler succeeded).
    playwright_log_id: str | None = None
    if action.playwright_step_id and handler_status == "applied":
        pw = embedded_actions.run_playwright_action(
            db,
            script_name=action.playwright_step_id,
            inputs={
                "entity_id": item_id,
                "entity_type": config.item_entity_type,
                **(payload or {}),
            },
            company_id=user.company_id,
            context_description=f"queue={session.queue_id} action={action_id}",
        )
        playwright_log_id = pw.get("log_id")
        if pw["status"] == "errored":
            # Append to message so caller sees the partial failure.
            handler_message += f" (Playwright: {pw['message']})"

    # Step 3 — Workflow trigger (if configured + handler succeeded).
    workflow_run_id: str | None = None
    if action.workflow_id and handler_status == "applied":
        wf = embedded_actions.trigger_workflow_action(
            db,
            workflow_id=action.workflow_id,
            input_data={
                "entity_id": item_id,
                "entity_type": config.item_entity_type,
                "reason": reason,
                **(payload or {}),
            },
            company_id=user.company_id,
            user_id=user.id,
        )
        workflow_run_id = wf.get("workflow_run_id")
        if wf["status"] == "errored":
            handler_message += f" (Workflow: {wf['message']})"

    # Step 4 — update session counters + mark item processed.
    _mark_processed(
        session,
        item_id=item_id,
        action_type=action.action_type.value,
        handler_status=handler_status,
    )
    db.commit()

    # Step 5 — auto-advance cursor to next item if handler succeeded.
    next_item_id: str | None = None
    if handler_status == "applied":
        try:
            nxt = next_item(db, session_id=session_id, user=user)
            next_item_id = nxt.entity_id
        except NoPendingItems:
            pass

    return TriageActionResult(
        status=handler_status,  # type: ignore[arg-type]
        message=handler_message,
        next_item_id=next_item_id,
        audit_log_id=None,
        playwright_log_id=playwright_log_id,
        workflow_run_id=workflow_run_id,
    )


# ── Snooze ──────────────────────────────────────────────────────────


def snooze_item(
    db: Session,
    *,
    session_id: str,
    item_id: str,
    user: User,
    wake_at: datetime,
    reason: str | None = None,
) -> TriageActionResult:
    """Snooze an item until `wake_at`. Removes it from the current
    user's view of the queue until then. Per the uq_triage_snoozes_
    active partial index, a second snooze on the same
    (user, queue, entity) while another is pending raises an
    integrity error — we convert that to a 409-equivalent errored
    result. Re-snooze requires un-snoozing first."""
    session = get_session(db, session_id=session_id, user=user)
    if session.ended_at is not None:
        raise SessionNotFound("Session already ended")
    config = registry.get_config(
        db, company_id=user.company_id, queue_id=session.queue_id
    )

    # The partial unique index enforces one-active-snooze-per-(user,
    # queue, entity). We check first to convert IntegrityError into a
    # clean errored result.
    existing = (
        db.query(TriageSnooze)
        .filter(
            TriageSnooze.user_id == user.id,
            TriageSnooze.queue_id == session.queue_id,
            TriageSnooze.entity_type == config.item_entity_type,
            TriageSnooze.entity_id == item_id,
            TriageSnooze.woken_at.is_(None),
        )
        .first()
    )
    if existing is not None:
        return TriageActionResult(
            status="skipped",
            message="Item already snoozed.",
        )

    snooze = TriageSnooze(
        id=str(uuid.uuid4()),
        company_id=user.company_id,
        user_id=user.id,
        queue_id=session.queue_id,
        entity_type=config.item_entity_type,
        entity_id=item_id,
        wake_at=wake_at,
        reason=reason,
    )
    db.add(snooze)

    _mark_processed(
        session, item_id=item_id, action_type="snooze", handler_status="applied"
    )
    db.commit()

    next_item_id: str | None = None
    try:
        nxt = next_item(db, session_id=session_id, user=user)
        next_item_id = nxt.entity_id
    except NoPendingItems:
        pass

    return TriageActionResult(
        status="applied",
        message=f"Snoozed until {wake_at.isoformat()}.",
        next_item_id=next_item_id,
    )


# ── Helpers ─────────────────────────────────────────────────────────


def _active_snooze_entity_ids(
    db: Session, *, user_id: str, queue_id: str
) -> set[str]:
    rows = (
        db.query(TriageSnooze.entity_id)
        .filter(
            TriageSnooze.user_id == user_id,
            TriageSnooze.queue_id == queue_id,
            TriageSnooze.woken_at.is_(None),
            TriageSnooze.wake_at > datetime.now(timezone.utc),
        )
        .all()
    )
    return {r[0] for r in rows}


def _find_action(
    config: TriageQueueConfig, action_id: str
) -> ActionConfig | None:
    for action in config.action_palette:
        if action.action_id == action_id:
            return action
    return None


def _check_user_can_access_queue(
    db: Session, user: User, config: TriageQueueConfig
) -> None:
    # Super-admins bypass.
    if getattr(user, "is_super_admin", False):
        return
    if not config.enabled:
        raise ActionNotAllowed(f"Queue {config.queue_id!r} is disabled")
    from app.services.permission_service import user_has_permission

    for perm in config.permissions:
        if not user_has_permission(user, db, perm):
            raise ActionNotAllowed(
                f"Missing permission {perm!r} for queue {config.queue_id!r}"
            )


def _execute_queue_saved_view(
    db: Session, *, config: TriageQueueConfig, user: User
) -> list[dict[str, Any]]:
    """Execute the queue's source + return rows.

    Three modes:
      - `source_direct_query_key` set → dispatch to a registered
        direct-query builder in `_DIRECT_QUERIES` (platform queues
        against entities not in Phase 2's saved-views registry).
      - `source_inline_config` set → parse the embedded
        SavedViewConfig dict and execute via Phase 2 executor.
      - `source_saved_view_id` set → resolve the saved view row
        through the Phase 2 CRUD + execute (per-tenant queues).
    """
    from app.services.saved_views.types import SavedViewConfig

    # Mode 1 — direct query (Phase 5 seed queues use this)
    if config.source_direct_query_key:
        fn = _DIRECT_QUERIES.get(config.source_direct_query_key)
        if fn is None:
            raise QueueNotFound(
                f"Queue {config.queue_id!r} references unknown direct query "
                f"{config.source_direct_query_key!r}. Available: "
                f"{list(_DIRECT_QUERIES.keys())}"
            )
        try:
            return fn(db, user)
        except Exception as exc:
            logger.exception(
                "Triage direct query %s failed for queue %s",
                config.source_direct_query_key, config.queue_id,
            )
            raise QueueNotFound(
                f"Queue {config.queue_id!r} direct query failed: {exc}"
            ) from exc

    if config.source_inline_config is not None:
        try:
            sv_config = SavedViewConfig.from_dict(config.source_inline_config)
        except Exception as exc:
            logger.exception(
                "Triage queue %s has malformed source_inline_config",
                config.queue_id,
            )
            raise QueueNotFound(
                f"Queue {config.queue_id!r} source_inline_config invalid: {exc}"
            ) from exc
        result = execute_saved_view(
            db,
            config=sv_config,
            caller_company_id=user.company_id,
            owner_company_id=user.company_id,
        )
        return result.rows

    if not config.source_saved_view_id:
        raise QueueNotFound(
            f"Queue {config.queue_id!r} has neither source_saved_view_id "
            f"nor source_inline_config."
        )

    try:
        sv: SavedView = get_saved_view(
            db, user=user, view_id=config.source_saved_view_id
        )
    except Exception as exc:
        logger.exception(
            "Triage queue %s references missing saved_view %s",
            config.queue_id, config.source_saved_view_id,
        )
        raise QueueNotFound(
            f"Queue {config.queue_id!r} source saved view unavailable: {exc}"
        ) from exc
    result = execute_saved_view(
        db,
        config=sv.config,
        caller_company_id=user.company_id,
        owner_company_id=sv.company_id,
    )
    return result.rows


def _row_to_item_summary(
    config: TriageQueueConfig, row: dict[str, Any]
) -> TriageItemSummary:
    return TriageItemSummary(
        entity_type=config.item_entity_type,
        entity_id=row["id"],
        title=str(row.get(config.item_display.title_field, "(no title)")),
        subtitle=(
            str(row.get(config.item_display.subtitle_field))
            if config.item_display.subtitle_field
            and row.get(config.item_display.subtitle_field) is not None
            else None
        ),
        extras={
            k: row.get(k)
            for k in config.item_display.body_fields
            if row.get(k) is not None
        },
    )


def _mark_processed(
    session: TriageSession,
    *,
    item_id: str,
    action_type: str,
    handler_status: str,
) -> None:
    if handler_status != "applied":
        return
    cursor = dict(session.cursor_meta or {})
    processed = list(cursor.get("processed_ids", []))
    if item_id not in processed:
        processed.append(item_id)
    cursor["processed_ids"] = processed
    session.cursor_meta = cursor
    from sqlalchemy.orm.attributes import flag_modified

    flag_modified(session, "cursor_meta")
    session.items_processed_count = (session.items_processed_count or 0) + 1
    if action_type == "approve":
        session.items_approved_count += 1
    elif action_type in ("reject", "reassign"):
        session.items_rejected_count += 1
    elif action_type == "snooze":
        session.items_snoozed_count += 1
    session.current_item_id = None


def _to_summary(session: TriageSession) -> TriageSessionSummary:
    return TriageSessionSummary(
        session_id=session.id,
        queue_id=session.queue_id,
        user_id=session.user_id,
        started_at=session.started_at,
        ended_at=session.ended_at,
        items_processed_count=session.items_processed_count,
        items_approved_count=session.items_approved_count,
        items_rejected_count=session.items_rejected_count,
        items_snoozed_count=session.items_snoozed_count,
        current_item_id=session.current_item_id,
    )


# ── Snooze sweep (called by a scheduler job in a post-arc pass) ─────


def sweep_expired_snoozes(db: Session) -> int:
    """Mark snoozes whose wake_at has passed as woken. Returns the
    count awoken. Safe to call repeatedly; idempotent.

    Phase 5 ships the function; wiring into APScheduler is a Phase 6
    add (triage briefings + scheduled resurfacing).
    """
    now = datetime.now(timezone.utc)
    rows = (
        db.query(TriageSnooze)
        .filter(
            TriageSnooze.wake_at <= now,
            TriageSnooze.woken_at.is_(None),
        )
        .all()
    )
    for row in rows:
        row.woken_at = now
    db.commit()
    return len(rows)


# ── Direct-query registry ───────────────────────────────────────────
# Platform-default queues for entities NOT in Phase 2's saved-views
# registry (task + social_service_certificate as of Phase 5) use
# these direct query builders. Each function receives (db, user) and
# returns a list of dicts shaped like saved-view rows (must include
# "id" + whatever fields the queue's item_display references).
#
# Adding a new direct query:
#   1. Write a `def _dq_<name>(db, user) -> list[dict]` function.
#   2. Register in _DIRECT_QUERIES at module bottom.
#   3. Reference from a queue config's `source_direct_query_key`.


def _dq_task_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Open/in-progress tasks assigned to the current user, sorted
    by priority then due date. Matches the spec's task_triage
    saved-view description."""
    from app.models.task import Task

    priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    rows = (
        db.query(Task)
        .filter(
            Task.company_id == user.company_id,
            Task.assignee_user_id == user.id,
            Task.is_active.is_(True),
            Task.status.in_(("open", "in_progress", "blocked")),
        )
        .all()
    )
    rows.sort(
        key=lambda t: (
            priority_order.get(t.priority, 4),
            t.due_date or datetime.max.date(),
            t.created_at or datetime.max.replace(tzinfo=timezone.utc),
        )
    )
    return [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "description": t.description,
            "related_entity_type": t.related_entity_type,
            "related_entity_id": t.related_entity_id,
            "assignee_user_id": t.assignee_user_id,
        }
        for t in rows
    ]


def _dq_ss_cert_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Pending (unapproved) social service certificates for the
    current tenant. Ordered oldest-first so the longest-waiting
    certificates are processed first. Display fields (deceased
    name, funeral home name) are derived from the related
    sales_order + customer — matching the pattern used by the
    legacy `/social-service-certificates` route."""
    from app.models.social_service_certificate import (
        SocialServiceCertificate,
    )
    from app.models.sales_order import SalesOrder

    rows = (
        db.query(SocialServiceCertificate)
        .filter(
            SocialServiceCertificate.company_id == user.company_id,
            SocialServiceCertificate.status == "pending_approval",
        )
        .order_by(SocialServiceCertificate.generated_at.asc().nulls_last())
        .all()
    )
    out: list[dict[str, Any]] = []
    for c in rows:
        order = (
            db.query(SalesOrder)
            .filter(SalesOrder.id == c.order_id)
            .first()
        )
        deceased_name = None
        funeral_home_name = None
        if order is not None:
            deceased_name = getattr(order, "deceased_name", None) or getattr(order, "ship_to_name", None)
            customer = getattr(order, "customer", None)
            if customer is not None:
                funeral_home_name = getattr(customer, "name", None)
        out.append(
            {
                "id": c.id,
                "certificate_number": c.certificate_number,
                "deceased_name": deceased_name,
                "funeral_home_name": funeral_home_name,
                "cemetery_name": None,  # not modeled on the cert today
                "generated_at": (
                    c.generated_at.isoformat() if c.generated_at else None
                ),
                "delivered_at": None,  # not modeled on the cert today
                "status": c.status,
                "order_id": c.order_id,
                "order_number": order.number if order else None,
            }
        )
    return out


def _dq_cash_receipts_matching_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8b — cash receipts matching triage items.

    Returns unresolved `AgentAnomaly` rows from the most recent
    cash_receipts_matching agent jobs for this tenant. Anomalies are
    produced by `CashReceiptsAgent._step_attempt_auto_match` (type
    `payment_possible_match`) and `_step_flag_unresolvable` (types
    `payment_unmatched_stale` + `payment_unmatched_recent`).

    Ordering: CRITICAL stale payments first (oldest + highest amount
    top), then WARNING recent unmatched, then INFO possible matches.
    Matches the operational priority — stale payments bleed the most
    AR risk so they surface first.

    Display fields denormalize the related CustomerPayment + Customer
    at query time (similar to `_dq_ss_cert_triage` denormalizing the
    sales_order + customer).
    """
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.customer import Customer
    from app.models.customer_payment import CustomerPayment

    _severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}

    rows = (
        db.query(AgentAnomaly)
        .join(AgentJob, AgentJob.id == AgentAnomaly.agent_job_id)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentJob.job_type == "cash_receipts_matching",
            AgentAnomaly.resolved.is_(False),
            AgentAnomaly.anomaly_type.in_(
                (
                    "payment_possible_match",
                    "payment_unmatched_stale",
                    "payment_unmatched_recent",
                )
            ),
        )
        .all()
    )

    out: list[dict[str, Any]] = []
    payment_cache: dict[str, CustomerPayment | None] = {}
    customer_cache: dict[str, Customer | None] = {}

    for a in rows:
        payment = None
        customer_name = None
        payment_amount = None
        payment_date = None
        payment_reference = None
        if a.entity_type == "payment" and a.entity_id:
            payment = payment_cache.get(a.entity_id)
            if a.entity_id not in payment_cache:
                payment = (
                    db.query(CustomerPayment)
                    .filter(
                        CustomerPayment.id == a.entity_id,
                        CustomerPayment.deleted_at.is_(None),
                    )
                    .first()
                )
                payment_cache[a.entity_id] = payment
            if payment is not None:
                payment_amount = float(payment.total_amount or 0)
                payment_date = (
                    payment.payment_date.isoformat()
                    if payment.payment_date
                    else None
                )
                payment_reference = payment.reference_number
                cid = payment.customer_id
                if cid not in customer_cache:
                    customer_cache[cid] = (
                        db.query(Customer)
                        .filter(Customer.id == cid)
                        .first()
                    )
                cust = customer_cache[cid]
                customer_name = cust.name if cust is not None else None

        out.append(
            {
                # The triage engine uses `id` as the item id; for
                # cash receipts, the item is the anomaly (so the
                # handler can resolve it). The underlying payment
                # is exposed via `payment_id`.
                "id": a.id,
                "anomaly_id": a.id,
                "anomaly_type": a.anomaly_type,
                "severity": a.severity,
                "description": a.description,
                "amount": float(a.amount) if a.amount is not None else None,
                "payment_id": a.entity_id,
                "payment_amount": payment_amount,
                "payment_date": payment_date,
                "payment_reference": payment_reference,
                "customer_name": customer_name,
                "created_at": (
                    a.created_at.isoformat() if a.created_at else None
                ),
                "agent_job_id": a.agent_job_id,
            }
        )

    out.sort(
        key=lambda r: (
            _severity_order.get(r.get("severity") or "", 3),
            -(r.get("amount") or 0),
            r.get("created_at") or "",
        )
    )
    return out


def _dq_month_end_close_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8c — month_end_close triage items.

    Unlike cash_receipts or ss_cert (one-per-anomaly), month-end close
    is ONE-ITEM-PER-JOB: the whole AgentJob in awaiting_approval is
    the decision. Anomalies are sub-items displayed via the context
    panel, not individually triageable.

    Ordering: oldest-awaiting-approval first — operators should close
    older periods before newer ones.
    """
    from app.models.agent import AgentJob

    rows = (
        db.query(AgentJob)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentJob.job_type == "month_end_close",
            AgentJob.status == "awaiting_approval",
        )
        .order_by(AgentJob.created_at.asc().nulls_last())
        .all()
    )

    out: list[dict[str, Any]] = []
    for j in rows:
        payload = j.report_payload or {}
        exec_summary = (
            payload.get("executive_summary", {})
            if isinstance(payload, dict)
            else {}
        )
        period_label = ""
        if j.period_start and j.period_end:
            period_label = f"{j.period_start:%B %Y}"
        out.append(
            {
                "id": j.id,
                "agent_job_id": j.id,
                "period_label": period_label,
                "period_start": (
                    j.period_start.isoformat() if j.period_start else None
                ),
                "period_end": (
                    j.period_end.isoformat() if j.period_end else None
                ),
                "dry_run": bool(j.dry_run),
                "anomaly_count": j.anomaly_count or 0,
                "critical_anomaly_count": exec_summary.get(
                    "critical_anomaly_count", 0
                ),
                "warning_anomaly_count": exec_summary.get(
                    "warning_anomaly_count", 0
                ),
                "total_revenue": exec_summary.get("total_revenue"),
                "total_ar": exec_summary.get("total_ar"),
                "created_at": (
                    j.created_at.isoformat() if j.created_at else None
                ),
            }
        )
    return out


def _dq_ar_collections_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8c — AR collections triage items.

    ONE-ITEM-PER-CUSTOMER. Each unresolved `collections_*` anomaly
    represents one customer + one drafted email ready for send
    approval. Draft subject + body are denormalized from the
    AgentJob's report_payload so the triage frontend can preview
    them without an extra round trip.

    Ordering: CRITICAL tier first (oldest-overdue bleeds the most AR
    risk), then ESCALATE, then FOLLOW_UP. Within tier, higher amount
    first.
    """
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.customer import Customer

    _severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}

    rows = (
        db.query(AgentAnomaly, AgentJob)
        .join(AgentJob, AgentJob.id == AgentAnomaly.agent_job_id)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentJob.job_type == "ar_collections",
            AgentAnomaly.resolved.is_(False),
            AgentAnomaly.anomaly_type.in_(
                (
                    "collections_follow_up",
                    "collections_escalate",
                    "collections_critical",
                )
            ),
        )
        .all()
    )

    out: list[dict[str, Any]] = []
    customer_cache: dict[str, Customer | None] = {}

    for anomaly, job in rows:
        customer_id = anomaly.entity_id
        # Pull the drafted email for this customer from the job's
        # report_payload.
        draft = None
        if isinstance(job.report_payload, dict):
            steps = job.report_payload.get("steps") or {}
            dc = steps.get("draft_communications") or {}
            for c in dc.get("communications") or []:
                if c.get("customer_id") == customer_id:
                    draft = c
                    break

        customer_name = None
        billing_email = None
        if customer_id and customer_id not in customer_cache:
            customer_cache[customer_id] = (
                db.query(Customer)
                .filter(Customer.id == customer_id)
                .first()
            )
        cust = customer_cache.get(customer_id) if customer_id else None
        if cust is not None:
            customer_name = cust.name
            billing_email = cust.billing_email or cust.email

        tier = "FOLLOW_UP"
        if anomaly.anomaly_type == "collections_critical":
            tier = "CRITICAL"
        elif anomaly.anomaly_type == "collections_escalate":
            tier = "ESCALATE"

        out.append(
            {
                "id": anomaly.id,
                "anomaly_id": anomaly.id,
                "customer_id": customer_id,
                "customer_name": customer_name or (draft or {}).get(
                    "customer_name"
                ),
                "billing_email": billing_email,
                "tier": tier,
                "severity": anomaly.severity,
                "total_outstanding": float(anomaly.amount)
                if anomaly.amount is not None
                else (draft or {}).get("total_outstanding"),
                "draft_subject": (draft or {}).get("subject"),
                "draft_body_preview": (
                    ((draft or {}).get("body") or "")[:300]
                ),
                "agent_job_id": anomaly.agent_job_id,
                "created_at": (
                    anomaly.created_at.isoformat()
                    if anomaly.created_at
                    else None
                ),
            }
        )

    out.sort(
        key=lambda r: (
            _severity_order.get(r.get("severity") or "", 3),
            -(r.get("total_outstanding") or 0),
            r.get("created_at") or "",
        )
    )
    return out


def _dq_expense_categorization_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8c — expense_categorization triage items.

    ONE-ITEM-PER-VENDOR-BILL-LINE with an unresolved anomaly of type
    `expense_low_confidence` or `expense_no_gl_mapping`. Denormalizes
    VendorBill + Vendor + the AI-suggested proposed_category from
    the job's report_payload.
    """
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.vendor import Vendor
    from app.models.vendor_bill import VendorBill
    from app.models.vendor_bill_line import VendorBillLine

    _severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}

    rows = (
        db.query(AgentAnomaly, AgentJob)
        .join(AgentJob, AgentJob.id == AgentAnomaly.agent_job_id)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentJob.job_type == "expense_categorization",
            AgentAnomaly.resolved.is_(False),
            AgentAnomaly.anomaly_type.in_(
                (
                    "expense_low_confidence",
                    "expense_no_gl_mapping",
                    "expense_classification_failed",
                )
            ),
        )
        .all()
    )

    out: list[dict[str, Any]] = []
    line_cache: dict[str, tuple[VendorBillLine, VendorBill, Vendor] | None] = {}

    def _load_line(line_id: str):
        if line_id in line_cache:
            return line_cache[line_id]
        q = (
            db.query(VendorBillLine, VendorBill, Vendor)
            .join(VendorBill, VendorBill.id == VendorBillLine.bill_id)
            .outerjoin(Vendor, Vendor.id == VendorBill.vendor_id)
            .filter(VendorBillLine.id == line_id)
            .first()
        )
        line_cache[line_id] = q
        return q

    for anomaly, job in rows:
        line_id = anomaly.entity_id
        line_info = _load_line(line_id) if line_id else None

        # Pull proposed_category from report_payload
        proposed_category = None
        if isinstance(job.report_payload, dict):
            steps = job.report_payload.get("steps") or {}
            gl_data = steps.get("map_to_gl_accounts") or {}
            for m in gl_data.get("mappings") or []:
                if m.get("line_id") == line_id:
                    proposed_category = m.get("proposed_category")
                    break
            if proposed_category is None:
                classify_data = steps.get("classify_expenses") or {}
                for c in classify_data.get("classifications") or []:
                    if c.get("line_id") == line_id:
                        proposed_category = c.get("proposed_category")
                        break

        line = line_info[0] if line_info else None
        bill = line_info[1] if line_info else None
        vendor = line_info[2] if line_info else None

        out.append(
            {
                "id": anomaly.id,
                "anomaly_id": anomaly.id,
                "line_id": line_id,
                "vendor_name": vendor.name if vendor else None,
                "vendor_bill_id": bill.id if bill else None,
                "description": (
                    line.description if line else anomaly.description
                ),
                "amount": float(line.amount)
                if line is not None and line.amount is not None
                else (
                    float(anomaly.amount)
                    if anomaly.amount is not None
                    else None
                ),
                "proposed_category": proposed_category,
                "current_category": (
                    line.expense_category if line else None
                ),
                "anomaly_type": anomaly.anomaly_type,
                "severity": anomaly.severity,
                "agent_job_id": anomaly.agent_job_id,
                "created_at": (
                    anomaly.created_at.isoformat()
                    if anomaly.created_at
                    else None
                ),
            }
        )

    out.sort(
        key=lambda r: (
            _severity_order.get(r.get("severity") or "", 3),
            -(r.get("amount") or 0),
            r.get("created_at") or "",
        )
    )
    return out


def _dq_aftercare_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8d — aftercare_7day triage items.

    Returns one row per unresolved AgentAnomaly of type
    ``fh_aftercare_pending`` that the aftercare_adapter staged. The
    anomaly carries the funeral_case id; we denormalize the deceased
    name, informant name + email, and case_number for the display.
    One-item-per-case matrix.
    """
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.models.funeral_case import (
        CaseDeceased,
        CaseInformant,
        CaseService,
        FuneralCase,
    )
    from app.services.workflows.aftercare_adapter import (
        AFTERCARE_JOB_TYPE,
        ANOMALY_TYPE,
    )

    rows = (
        db.query(AgentAnomaly, AgentJob)
        .join(AgentJob, AgentJob.id == AgentAnomaly.agent_job_id)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentJob.job_type == AFTERCARE_JOB_TYPE,
            AgentAnomaly.resolved.is_(False),
            AgentAnomaly.anomaly_type == ANOMALY_TYPE,
        )
        .order_by(AgentAnomaly.created_at.asc())
        .all()
    )

    out: list[dict[str, Any]] = []
    for anomaly, job in rows:
        case_id = anomaly.entity_id
        if not case_id:
            continue
        fc = (
            db.query(FuneralCase)
            .filter(FuneralCase.id == case_id)
            .first()
        )
        deceased = (
            db.query(CaseDeceased)
            .filter(CaseDeceased.case_id == case_id)
            .first()
        )
        informant = (
            db.query(CaseInformant)
            .filter(
                CaseInformant.case_id == case_id,
                CaseInformant.is_primary.is_(True),
            )
            .first()
        )
        if informant is None:
            informant = (
                db.query(CaseInformant)
                .filter(CaseInformant.case_id == case_id)
                .order_by(CaseInformant.created_at.asc())
                .first()
            )
        service = (
            db.query(CaseService)
            .filter(CaseService.case_id == case_id)
            .first()
        )

        deceased_name = None
        if deceased is not None:
            deceased_name = " ".join(
                p for p in [deceased.first_name, deceased.last_name] if p
            ) or None

        out.append(
            {
                "id": anomaly.id,
                "anomaly_id": anomaly.id,
                "case_id": case_id,
                "case_number": fc.case_number if fc else None,
                "family_surname": (
                    deceased.last_name
                    if deceased and deceased.last_name
                    else None
                ),
                "deceased_name": deceased_name,
                "primary_contact_name": (
                    informant.name if informant else None
                ),
                "primary_contact_email": (
                    informant.email if informant else None
                ),
                "service_date": (
                    service.service_date.isoformat()
                    if service and service.service_date
                    else None
                ),
                "missing_email": not bool(
                    informant and informant.email
                ),
                "agent_job_id": anomaly.agent_job_id,
                "created_at": (
                    anomaly.created_at.isoformat()
                    if anomaly.created_at
                    else None
                ),
            }
        )
    return out


def _dq_safety_program_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8d.1 — safety_program pending-review items.

    Returns one row per SafetyProgramGeneration with
    ``status='pending_review'``. Anomaly-less (like catalog_fetch):
    the generation row itself is the review unit, state machine
    lives on the domain entity (`draft/pending_review/approved/
    rejected`) pre-dating the arc.

    Cardinality: per-generation-run. Ordered newest-first by
    generated_at so the most-recently-generated program surfaces
    at the top (operator typically reviews immediately after the
    1st-of-month generation finishes).

    Denormalizes the related SafetyTrainingTopic so the display
    can show title + OSHA standard without a second round-trip.
    """
    from app.models.safety_program_generation import (
        SafetyProgramGeneration,
    )
    from app.models.safety_training_topic import SafetyTrainingTopic

    rows = (
        db.query(SafetyProgramGeneration, SafetyTrainingTopic)
        .outerjoin(
            SafetyTrainingTopic,
            SafetyTrainingTopic.id == SafetyProgramGeneration.topic_id,
        )
        .filter(
            SafetyProgramGeneration.tenant_id == user.company_id,
            SafetyProgramGeneration.status == "pending_review",
        )
        .order_by(SafetyProgramGeneration.generated_at.desc().nulls_last())
        .all()
    )
    out: list[dict[str, Any]] = []
    for gen, topic in rows:
        token_usage = gen.generation_token_usage or {}
        out.append(
            {
                "id": gen.id,
                "generation_id": gen.id,
                "topic_id": gen.topic_id,
                "topic_title": topic.title if topic else None,
                "osha_standard": topic.osha_standard if topic else None,
                "osha_standard_label": (
                    topic.osha_standard_label if topic else None
                ),
                "year": gen.year,
                "month_number": gen.month_number,
                "year_month_label": (
                    f"{gen.year}-{gen.month_number:02d}"
                ),
                "generated_at": (
                    gen.generated_at.isoformat() if gen.generated_at else None
                ),
                "generation_model": gen.generation_model,
                "input_tokens": token_usage.get("input_tokens"),
                "output_tokens": token_usage.get("output_tokens"),
                "pdf_document_id": gen.pdf_document_id,
                "has_pdf": bool(gen.pdf_document_id),
                "osha_scrape_status": gen.osha_scrape_status,
                "status": gen.status,
            }
        )
    return out


def _dq_catalog_fetch_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8d — catalog_fetch pending-review items.

    Returns one row per UrnCatalogSyncLog with
    ``publication_state='pending_review'``. Unlike the accounting
    queues, this one is NOT anomaly-backed — the sync_log row itself
    is the unit of review. Ordered newest-first so the most recent
    Wilbert change surfaces at the top if somehow multiple pending
    reviews exist (the adapter marks older ones superseded so this
    should normally be a single row).
    """
    from app.models.urn_catalog_sync_log import UrnCatalogSyncLog

    rows = (
        db.query(UrnCatalogSyncLog)
        .filter(
            UrnCatalogSyncLog.tenant_id == user.company_id,
            UrnCatalogSyncLog.publication_state == "pending_review",
        )
        .order_by(UrnCatalogSyncLog.started_at.desc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for log in rows:
        out.append(
            {
                "id": log.id,
                "sync_log_id": log.id,
                "r2_key": log.pdf_filename,
                "products_preview": log.products_updated or 0,
                "started_at": (
                    log.started_at.isoformat() if log.started_at else None
                ),
                "sync_type": log.sync_type,
                "publication_state": log.publication_state,
                "has_r2_pdf": bool(log.pdf_filename),
            }
        )
    return out


_DIRECT_QUERIES: dict[
    str, "Callable[[Session, User], list[dict[str, Any]]]"
] = {
    "task_triage": _dq_task_triage,
    "ss_cert_triage": _dq_ss_cert_triage,
    "cash_receipts_matching_triage": _dq_cash_receipts_matching_triage,
    # Phase 8c — core accounting migrations batch 1
    "month_end_close_triage": _dq_month_end_close_triage,
    "ar_collections_triage": _dq_ar_collections_triage,
    "expense_categorization_triage": _dq_expense_categorization_triage,
    # Phase 8d — vertical workflow migrations
    "aftercare_triage": _dq_aftercare_triage,
    "catalog_fetch_triage": _dq_catalog_fetch_triage,
    # Phase 8d.1 — AI-generation-with-approval
    "safety_program_triage": _dq_safety_program_triage,
}


# Typing forward-ref ergonomics — the dict literal above uses a
# string forward-ref so `Callable` can be late-imported at runtime.
from typing import Callable  # noqa: E402


__all__ = [
    "start_session",
    "get_session",
    "end_session",
    "next_item",
    "queue_count",
    "apply_action",
    "snooze_item",
    "sweep_expired_snoozes",
]
