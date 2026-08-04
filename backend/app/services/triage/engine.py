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
from typing import Any, NamedTuple

from sqlalchemy import and_, exists
from sqlalchemy.orm import Query, Session

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


def _count_config(db: Session, *, user: User, config: TriageQueueConfig) -> int:
    """Pending-count core for a single (already-resolved, already-access-checked)
    queue config. Shared by `queue_count` (single) and `counts_for_user`
    (batched) so the two cannot count differently.

    Fast path — direct-query queues with a membership seam count via COUNT(*)
    over the shared membership query + snooze anti-join, never materializing
    rows (no denormalization N+1). Same expression the row builder uses, so the
    count cannot disagree with the build. Fallback — inline / saved-view-backed
    queues (modes 2 + 3) materialize + count in Python.
    """
    mq_fn = (
        _MEMBERSHIP_QUERIES.get(config.source_direct_query_key)
        if config.source_direct_query_key
        else None
    )
    if mq_fn is not None:
        return _count_membership(
            db, user=user, queue_id=config.queue_id, mq=mq_fn(db, user)
        )
    snoozed_ids = _active_snooze_entity_ids(
        db, user_id=user.id, queue_id=config.queue_id
    )
    items = _execute_queue_saved_view(db, config=config, user=user)
    return sum(1 for r in items if r.get("id") not in snoozed_ids)


def queue_count(
    db: Session, *, user: User, queue_id: str
) -> int:
    """Pending item count for a queue — used by briefings (Phase 6)
    + sidebar badges. Excludes items currently snoozed by the user."""
    config = registry.get_config(
        db, company_id=user.company_id, queue_id=queue_id
    )
    _check_user_can_access_queue(db, user, config)
    return _count_config(db, user=user, config=config)


def counts_for_user(
    db: Session,
    *,
    user: User,
    configs: list[TriageQueueConfig] | None = None,
    queue_ids: list[str] | None = None,
) -> dict[str, int]:
    """Batched pending counts for every queue the user can see (or the subset
    named by `queue_ids`) — the fan-out entry point for briefings, the spaces
    sidebar, and MoC job cards.

    Hoists the per-render floor out of the per-queue path: the queue configs and
    the user's permission set are resolved ONCE via `list_queues_for_user`
    (which also applies the enabled/vertical/extension/permission gates), not
    once per queue. Each queue then costs a single COUNT (membership fast path;
    snooze folded in as a correlated anti-join). So a 12-queue fan-out is ~12
    counts + a small fixed constant, not 12 × (config + permission + count).

    Pass `configs` to reuse a `list_queues_for_user` result the caller already
    has (avoids a second gate pass). Returns {queue_id: pending_count}; queues
    the user can't access are simply absent.
    """
    if configs is None:
        configs = registry.list_queues_for_user(db, user=user)
    if queue_ids is not None:
        want = set(queue_ids)
        configs = [c for c in configs if c.queue_id in want]
    out: dict[str, int] = {}
    for cfg in configs:
        try:
            out[cfg.queue_id] = _count_config(db, user=user, config=cfg)
        except Exception:
            logger.exception(
                "counts_for_user: count failed for queue %s", cfg.queue_id
            )
            out[cfg.queue_id] = 0
    return out


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
# THE MEMBERSHIP SEAM (queue-count perf arc):
#   A queue's membership — which rows belong — is expressed ONCE as a
#   `_mq_<name>(db, user) -> MembershipQuery`. Two consumers share it:
#     - the row builder `_dq_<name>` executes `.query.all()` then
#       denormalizes each row for display (the N+1-carrying path);
#     - `queue_count` counts via `_count_membership` — a `COUNT(*)`
#       over the SAME query with the snooze anti-join folded in, so it
#       never materializes rows or pays the denormalization N+1.
#   One expression, two consumers → count and build cannot silently
#   disagree. `MembershipQuery.id_column` is the item-id column (the
#   entity whose id becomes the triage item id); it anchors the snooze
#   NOT EXISTS and must be the same id the builder emits as "id".
#
# Adding a new direct query:
#   1. Write `def _mq_<name>(db, user) -> MembershipQuery` (membership).
#   2. Write `def _dq_<name>(db, user) -> list[dict]` that denormalizes
#      `_mq_<name>(db, user).query.all()`.
#   3. Register in _MEMBERSHIP_QUERIES + _DIRECT_QUERIES at module bottom.
#   4. Reference from a queue config's `source_direct_query_key`.


class MembershipQuery(NamedTuple):
    """The membership expression for a triage queue: which rows belong.

    `query` is a SQLAlchemy Query whose result rows ARE the queue members
    (one row per member — joins must be to-one so no fan-out; every builder
    below satisfies this). `id_column` is the column carrying the triage
    item id (what the builder emits as "id"), used for the snooze anti-join.
    """

    query: Query
    id_column: Any


def _count_membership(
    db: Session, *, user: User, queue_id: str, mq: MembershipQuery
) -> int:
    """COUNT(*) over a membership query with the per-user snooze excluded
    as a NOT EXISTS anti-join (never a Python post-filter). Matches the
    legacy semantics: `len(rows) - snoozed-that-are-members`."""
    snooze_anti = ~exists().where(
        and_(
            TriageSnooze.user_id == user.id,
            TriageSnooze.queue_id == queue_id,
            TriageSnooze.woken_at.is_(None),
            TriageSnooze.wake_at > datetime.now(timezone.utc),
            TriageSnooze.entity_id == mq.id_column,
        )
    )
    return mq.query.filter(snooze_anti).count()


def _mq_task_triage(db: Session, user: User) -> MembershipQuery:
    """Membership: open/in-progress/blocked tasks assigned to this user."""
    from app.models.task import Task

    q = db.query(Task).filter(
        Task.company_id == user.company_id,
        Task.assignee_user_id == user.id,
        Task.is_active.is_(True),
        Task.status.in_(("open", "in_progress", "blocked")),
    )
    return MembershipQuery(query=q, id_column=Task.id)


def _dq_task_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Open/in-progress tasks assigned to the current user, sorted by
    priority then due date. Membership from `_mq_task_triage`; the
    priority/due sort + projection below are display-only."""
    priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
    rows = _mq_task_triage(db, user).query.all()
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


def _mq_ss_cert_triage(db: Session, user: User) -> MembershipQuery:
    """Membership: pending (unapproved) social service certificates for the
    current tenant, oldest-first (longest-waiting processed first). This is
    the single source of truth for SS-cert queue membership — both the row
    builder and `queue_count` consume it."""
    from app.models.social_service_certificate import (
        SocialServiceCertificate,
    )

    q = (
        db.query(SocialServiceCertificate)
        .filter(
            SocialServiceCertificate.company_id == user.company_id,
            SocialServiceCertificate.status == "pending_approval",
        )
        .order_by(SocialServiceCertificate.generated_at.asc().nulls_last())
    )
    return MembershipQuery(query=q, id_column=SocialServiceCertificate.id)


def _dq_ss_cert_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Rows for the SS-cert queue. Membership comes from
    `_mq_ss_cert_triage`; display fields (deceased name, funeral home name)
    are denormalized from the related sales_order + customer — matching the
    pattern used by the legacy `/social-service-certificates` route. The
    per-row SalesOrder lookup is display-only (N+1); the count path skips it
    entirely by counting the membership query."""
    from app.models.sales_order import SalesOrder

    rows = _mq_ss_cert_triage(db, user).query.all()
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


def _mq_cash_receipts_matching_triage(
    db: Session, user: User
) -> MembershipQuery:
    """Membership: unresolved cash_receipts_matching anomalies (possible-match
    + stale/recent unmatched) for this tenant. The per-row CustomerPayment +
    Customer denormalization lives in the builder, not here — the count path
    counts this query and never pays that N+1."""
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly

    q = (
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
    )
    return MembershipQuery(query=q, id_column=AgentAnomaly.id)


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
    from app.models.customer import Customer
    from app.models.customer_payment import CustomerPayment

    _severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}

    rows = _mq_cash_receipts_matching_triage(db, user).query.all()

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


def _mq_month_end_close_triage(db: Session, user: User) -> MembershipQuery:
    """Membership: month_end_close jobs awaiting approval (one-item-per-job),
    oldest-first."""
    from app.models.agent import AgentJob

    q = (
        db.query(AgentJob)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentJob.job_type == "month_end_close",
            AgentJob.status == "awaiting_approval",
        )
        .order_by(AgentJob.created_at.asc().nulls_last())
    )
    return MembershipQuery(query=q, id_column=AgentJob.id)


def _dq_month_end_close_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8c — month_end_close triage items.

    Unlike cash_receipts or ss_cert (one-per-anomaly), month-end close
    is ONE-ITEM-PER-JOB: the whole AgentJob in awaiting_approval is
    the decision. Anomalies are sub-items displayed via the context
    panel, not individually triageable. Membership from
    `_mq_month_end_close_triage`; report_payload parse below is display.
    """
    rows = _mq_month_end_close_triage(db, user).query.all()

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


def _mq_ar_collections_triage(db: Session, user: User) -> MembershipQuery:
    """Membership: unresolved ar_collections anomalies (one-per-customer) for
    this tenant. The per-row Customer denormalization + draft-email parse live
    in the builder; the count path never pays them."""
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly

    q = (
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
    )
    return MembershipQuery(query=q, id_column=AgentAnomaly.id)


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
    from app.models.customer import Customer

    _severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}

    rows = _mq_ar_collections_triage(db, user).query.all()

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


def _mq_expense_categorization_triage(db: Session, user: User) -> MembershipQuery:
    """Membership: unresolved expense_categorization anomalies (one-per-line)
    for this tenant. The per-row VendorBillLine/VendorBill/Vendor load +
    proposed-category parse live in the builder, not here."""
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly

    q = (
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
    )
    return MembershipQuery(query=q, id_column=AgentAnomaly.id)


def _dq_expense_categorization_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8c — expense_categorization triage items.

    ONE-ITEM-PER-VENDOR-BILL-LINE with an unresolved anomaly of type
    `expense_low_confidence` or `expense_no_gl_mapping`. Denormalizes
    VendorBill + Vendor + the AI-suggested proposed_category from
    the job's report_payload.
    """
    from app.models.vendor import Vendor
    from app.models.vendor_bill import VendorBill
    from app.models.vendor_bill_line import VendorBillLine

    _severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}

    rows = _mq_expense_categorization_triage(db, user).query.all()

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


def _mq_aftercare_triage(db: Session, user: User) -> MembershipQuery:
    """Membership: unresolved fh_aftercare_pending anomalies for this tenant,
    oldest-first, WITH a non-empty case id. The builder's
    `if not case_id: continue` guard is lifted into SQL here (isnot None AND
    != "") so count and build agree on membership — a null/empty entity_id is
    not a member. Per-case FuneralCase/deceased/informant/service denorm lives
    in the builder, not here."""
    from app.models.agent import AgentJob
    from app.models.agent_anomaly import AgentAnomaly
    from app.services.workflows.aftercare_adapter import (
        AFTERCARE_JOB_TYPE,
        ANOMALY_TYPE,
    )

    q = (
        db.query(AgentAnomaly, AgentJob)
        .join(AgentJob, AgentJob.id == AgentAnomaly.agent_job_id)
        .filter(
            AgentJob.tenant_id == user.company_id,
            AgentJob.job_type == AFTERCARE_JOB_TYPE,
            AgentAnomaly.resolved.is_(False),
            AgentAnomaly.anomaly_type == ANOMALY_TYPE,
            AgentAnomaly.entity_id.isnot(None),
            AgentAnomaly.entity_id != "",
        )
        .order_by(AgentAnomaly.created_at.asc())
    )
    return MembershipQuery(query=q, id_column=AgentAnomaly.id)


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
    from app.models.funeral_case import (
        CaseDeceased,
        CaseInformant,
        CaseService,
        FuneralCase,
    )

    rows = _mq_aftercare_triage(db, user).query.all()

    out: list[dict[str, Any]] = []
    for anomaly, job in rows:
        # Membership already excludes null/empty entity_id, so case_id is set.
        case_id = anomaly.entity_id
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


def _mq_safety_program_triage(db: Session, user: User) -> MembershipQuery:
    """Membership: SafetyProgramGeneration rows pending review, newest-first.
    The outerjoin to SafetyTrainingTopic is display denorm (to-one, no fan-out)
    carried on the shared query so build and count stay identical."""
    from app.models.safety_program_generation import (
        SafetyProgramGeneration,
    )
    from app.models.safety_training_topic import SafetyTrainingTopic

    q = (
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
    )
    return MembershipQuery(query=q, id_column=SafetyProgramGeneration.id)


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
    rows = _mq_safety_program_triage(db, user).query.all()
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


def _mq_catalog_fetch_triage(db: Session, user: User) -> MembershipQuery:
    """Membership: UrnCatalogSyncLog rows pending review, newest-first."""
    from app.models.urn_catalog_sync_log import UrnCatalogSyncLog

    q = (
        db.query(UrnCatalogSyncLog)
        .filter(
            UrnCatalogSyncLog.tenant_id == user.company_id,
            UrnCatalogSyncLog.publication_state == "pending_review",
        )
        .order_by(UrnCatalogSyncLog.started_at.desc())
    )
    return MembershipQuery(query=q, id_column=UrnCatalogSyncLog.id)


def _dq_catalog_fetch_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Workflow Arc Phase 8d — catalog_fetch pending-review items.

    One row per UrnCatalogSyncLog with ``publication_state='pending_review'``
    (NOT anomaly-backed — the sync_log row itself is the unit of review).
    Membership from `_mq_catalog_fetch_triage`.
    """
    rows = _mq_catalog_fetch_triage(db, user).query.all()
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


_EMAIL_UNCLASSIFIED_DISPLAY_LIMIT = 50


def _mq_email_unclassified_triage(db: Session, user: User) -> MembershipQuery:
    """Membership: inbound emails whose classification cascade exhausted without
    a dispatch — the LATEST classification per message is tier IS NULL AND NOT
    suppressed.

    This is the SQL form of the Python latest-per-message de-dup in
    ``classification.dispatch.list_unclassified`` (window over ALL
    classifications for each message, rn=1 = the latest). The window orders by
    ``created_at DESC`` — matching ``get_latest_classification_for_message`` —
    with a deterministic ``id DESC`` tiebreak (the Python has none, so on a
    created_at tie it was DB-arbitrary; this makes it stable). A WEC always has
    a real email_message_id (NOT NULL FK), so the builder's inner join to the
    message can't drop a member — membership is expressible on WEC alone.

    UNCAPPED: per the arc's EXACT-COUNTS decision, the builder's display LIMIT
    does NOT propagate here — the count answers the true 'how many waiting'.
    """
    from sqlalchemy import func

    from app.models.email_classification import WorkflowEmailClassification as WEC

    rn = func.row_number().over(
        partition_by=WEC.email_message_id,
        order_by=[WEC.created_at.desc(), WEC.id.desc()],
    ).label("rn")
    ranked = (
        db.query(WEC.id.label("cid"), rn)
        .filter(WEC.tenant_id == user.company_id)
        .subquery()
    )
    q = (
        db.query(WEC)
        .join(ranked, ranked.c.cid == WEC.id)
        .filter(
            ranked.c.rn == 1,
            WEC.tier.is_(None),
            WEC.is_suppressed.is_(False),
        )
    )
    return MembershipQuery(query=q, id_column=WEC.id)


def _dq_email_unclassified_triage(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Phase R-6.1a — inbound emails whose classification cascade exhausted
    without a dispatch (the latest classification per message is tier IS NULL
    AND NOT suppressed). Membership from `_mq_email_unclassified_triage` (shared
    with queue_count); this builder joins the EmailMessage for display (one
    batched load, no N+1), orders oldest-first, and stages at most
    `_EMAIL_UNCLASSIFIED_DISPLAY_LIMIT` rows — a DISPLAY bound for the
    workspace, NOT a bound on the count (the count is exact + uncapped).
    """
    from app.models.email_classification import WorkflowEmailClassification as WEC
    from app.models.email_primitive import EmailMessage

    mq = _mq_email_unclassified_triage(db, user)
    rows = (
        mq.query.order_by(WEC.created_at.asc())
        .limit(_EMAIL_UNCLASSIFIED_DISPLAY_LIMIT)
        .all()
    )
    msg_ids = [w.email_message_id for w in rows]
    msgs = (
        {m.id: m for m in db.query(EmailMessage).filter(EmailMessage.id.in_(msg_ids))}
        if msg_ids
        else {}
    )
    out: list[dict[str, Any]] = []
    for cls_row in rows:
        msg = msgs.get(cls_row.email_message_id)
        out.append(
            {
                "id": cls_row.id,
                "classification_id": cls_row.id,
                "email_message_id": cls_row.email_message_id,
                "subject": (msg.subject or "") if msg else "",
                "sender_email": (msg.sender_email or "") if msg else "",
                "sender_name": (msg.sender_name or "") if msg else "",
                "body_excerpt": ((msg.body_text or "")[:500]) if msg else "",
                "received_at": (
                    msg.received_at.isoformat()
                    if msg and msg.received_at
                    else None
                ),
                "created_at": (
                    cls_row.created_at.isoformat()
                    if cls_row.created_at
                    else None
                ),
                "tier_reasoning": cls_row.tier_reasoning or {},
            }
        )
    return out


def _mq_workflow_review(db: Session, user: User) -> MembershipQuery:
    """Membership: WorkflowReviewItem rows with decision IS NULL for this
    tenant, oldest-first. Per-row WorkflowRun + Workflow denorm lives in the
    builder, not here."""
    from app.models.workflow_review_item import WorkflowReviewItem

    q = (
        db.query(WorkflowReviewItem)
        .filter(
            WorkflowReviewItem.company_id == user.company_id,
            WorkflowReviewItem.decision.is_(None),
        )
        .order_by(WorkflowReviewItem.created_at.asc())
    )
    return MembershipQuery(query=q, id_column=WorkflowReviewItem.id)


def _dq_workflow_review(
    db: Session, user: User
) -> list[dict[str, Any]]:
    """Phase R-6.0a — pending WorkflowReviewItem rows for the current
    tenant. Surfaces every item with ``decision IS NULL``, oldest
    first (longest-waiting reviewed first). Membership from
    `_mq_workflow_review`; per-row run/workflow denorm below is display.

    Tenant-scoped via ``company_id == user.company_id``. The
    underlying ``workflow_runs`` table is also tenant-scoped, so the
    item-level filter is defense-in-depth.
    """
    from app.models.workflow import WorkflowRun, Workflow

    rows = _mq_workflow_review(db, user).query.all()
    out: list[dict[str, Any]] = []
    for item in rows:
        run = (
            db.query(WorkflowRun)
            .filter(WorkflowRun.id == item.run_id)
            .first()
        )
        workflow = None
        if run is not None:
            workflow = (
                db.query(Workflow)
                .filter(Workflow.id == run.workflow_id)
                .first()
            )
        out.append(
            {
                "id": item.id,
                "review_focus_id": item.review_focus_id,
                "input_data": item.input_data or {},
                "run_id": item.run_id,
                "workflow_id": run.workflow_id if run else None,
                "workflow_name": workflow.name if workflow else None,
                "trigger_source": run.trigger_source if run else None,
                "created_at": (
                    item.created_at.isoformat() if item.created_at else None
                ),
            }
        )
    return out


def _mq_reconciliation_review(db: Session, user: User) -> MembershipQuery:
    """Membership: open reconciliation exceptions — the SOURCE TRANSACTION's
    match_status is authority (JOIN to the txn, filter match_status='unmatched',
    NOT exception.resolved), excluding actively-parked exceptions (flag_id set).
    The batched candidate hydration (Option A) is display-only + lives in the
    builder; count never fetches candidates. id_column = the transaction id (the
    triage item id; the exception is one-per-txn so the join can't fan out)."""
    from app.models.financial_account import (
        ReconciliationException,
        ReconciliationTransaction,
    )

    q = (
        db.query(ReconciliationTransaction, ReconciliationException)
        .join(
            ReconciliationException,
            ReconciliationException.reconciliation_transaction_id
            == ReconciliationTransaction.id,
        )
        .filter(
            ReconciliationTransaction.tenant_id == user.company_id,
            ReconciliationTransaction.match_status == "unmatched",
            ReconciliationException.flag_id.is_(None),
        )
        .order_by(ReconciliationTransaction.sort_order)
    )
    return MembershipQuery(query=q, id_column=ReconciliationTransaction.id)


def _dq_reconciliation_review(db: Session, user: User) -> list[dict[str, Any]]:
    """Books Review — open reconciliation exceptions.

    THE EXCEPTION IS A WORKSPACE OBJECT; the source transaction's `match_status`
    is authority on whether the item is still open. So this JOINs to the
    transaction and filters on `match_status`, NOT on
    `reconciliation_exceptions.resolved`. The consequence is load-bearing: the
    Accept handler must move `match_status` OFF "unmatched" (not merely flip
    `resolved`), or the item never leaves the queue — the invariant enforces
    itself through the query, not through discipline.

    Candidates ride each row (Option A) so the card derives its form (ranked vs
    coding) from their presence WITHOUT a second fetch. Near-misses are included
    as low-ranked candidates carrying their rejection reason + measured value.
    """
    from app.models.financial_account import ReconciliationMatchCandidate

    rows = _mq_reconciliation_review(db, user).query.all()

    txn_ids = [t.id for (t, _e) in rows]
    cands_by_txn: dict[str, list[dict[str, Any]]] = {}
    if txn_ids:
        cand_rows = (
            db.query(ReconciliationMatchCandidate)
            .filter(ReconciliationMatchCandidate.reconciliation_transaction_id.in_(txn_ids))
            .order_by(ReconciliationMatchCandidate.rank)
            .all()
        )
        for c in cand_rows:
            cands_by_txn.setdefault(c.reconciliation_transaction_id, []).append(
                {
                    "id": c.id,
                    "candidate_record_type": c.candidate_record_type,
                    "candidate_record_id": c.candidate_record_id,
                    "score": str(c.score),
                    "rank": c.rank,
                    "rejection_reason": c.rejection_reason,
                    "rejection_detail": c.rejection_detail,
                }
            )

    return [
        {
            "id": t.id,  # entity_id = the transaction (candidates key to it; exception per txn)
            "description": t.description,
            "amount": str(t.amount),
            "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
            "transaction_type": t.transaction_type,
            "candidates": cands_by_txn.get(t.id, []),
        }
        for (t, _e) in rows
    ]


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
    # Phase R-6.0a — workflow review pause (invoke_review_focus)
    "workflow_review": _dq_workflow_review,
    # Phase R-6.1a — unclassified email cascade fallthrough
    "email_unclassified": _dq_email_unclassified_triage,
    # Books Review Arc B B-3 — reconciliation exceptions (candidates via Option A)
    "reconciliation_review": _dq_reconciliation_review,
}


# Membership seam (queue-count perf arc): direct-query keys that have a
# `_mq_<name>` membership function drive `queue_count` down the COUNT(*)
# fast path. Keys absent here fall back to materialize-and-count. Populated
# incrementally as builders are converted (C-1 → C-2 → C-3).
_MEMBERSHIP_QUERIES: dict[
    str, "Callable[[Session, User], MembershipQuery]"
] = {
    "task_triage": _mq_task_triage,
    "ss_cert_triage": _mq_ss_cert_triage,
    "cash_receipts_matching_triage": _mq_cash_receipts_matching_triage,
    "month_end_close_triage": _mq_month_end_close_triage,
    "ar_collections_triage": _mq_ar_collections_triage,
    "expense_categorization_triage": _mq_expense_categorization_triage,
    "aftercare_triage": _mq_aftercare_triage,
    "catalog_fetch_triage": _mq_catalog_fetch_triage,
    "safety_program_triage": _mq_safety_program_triage,
    "workflow_review": _mq_workflow_review,
    "reconciliation_review": _mq_reconciliation_review,
    # C-3: latest-classification-per-message via a window function. UNCAPPED —
    # the count is now exact (was ≤50 on the old fallback). The builder keeps a
    # display LIMIT; the cap does not propagate to the count.
    "email_unclassified": _mq_email_unclassified_triage,
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
    "counts_for_user",
    "apply_action",
    "snooze_item",
    "sweep_expired_snoozes",
]
