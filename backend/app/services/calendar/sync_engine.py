"""Calendar sync engine — Phase W-4b Layer 1 Calendar Step 2.

Cross-provider sync orchestration. Each provider class implements
``sync_initial`` (backfill) + ``fetch_event`` (single-event fetch on
webhook notification, deferred to Step 2.1) per the ABC contract; this
module orchestrates state cursor updates + circuit-breaker + ingestion.

**Cursor management** — provider-agnostic via
``CalendarAccountSyncState.last_provider_cursor`` JSONB. Per-provider
shape:

  - Google Calendar: ``{"sync_token": "..."}``
  - MS Graph: ``{"delta_token": "https://graph.microsoft.com/...delta..."}``
  - Local: never has a cursor (no transport)

**Circuit breaker** — after 5 consecutive sync failures, sync_status
flips to "error" and ``consecutive_error_count`` keeps tracking.
Operator visibility via CalendarAccountsPage. Reset to 0 on next
successful sync.

**Sync mutex** — ``sync_in_progress=true`` prevents two sweeps from
double-syncing the same account. Cleared at the end (success or
failure).

**Backfill state machine** — ``not_started → in_progress → completed |
error``. Idempotent re-attempts: if already in_progress, raises
SyncEngineError; if completed/error, can re-trigger via /sync-now
endpoint.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAccountSyncState,
)
from app.services.calendar.account_service import _audit
from app.services.calendar.ingestion import ingest_provider_event
from app.services.calendar.providers import get_provider_class

logger = logging.getLogger(__name__)


_CIRCUIT_BREAKER_THRESHOLD = 5


class SyncEngineError(Exception):
    pass


def ensure_sync_state(
    db: Session, *, account_id: str
) -> CalendarAccountSyncState:
    """Get or create the sync_state row for an account.

    CalendarAccountSyncState is a per-account 1:1 row created lazily
    on first sync attempt (Calendar Step 1's account_service does NOT
    bootstrap the row at create_account time per Email r64 precedent
    note in the service). Step 2 creates lazily on first sync.
    """
    state = (
        db.query(CalendarAccountSyncState)
        .filter(CalendarAccountSyncState.account_id == account_id)
        .first()
    )
    if not state:
        import uuid

        state = CalendarAccountSyncState(
            id=str(uuid.uuid4()),
            account_id=account_id,
            sync_status="pending",
        )
        db.add(state)
        db.flush()
    return state


@contextmanager
def _sync_mutex(db: Session, account_id: str):
    state = ensure_sync_state(db, account_id=account_id)
    if state.sync_in_progress:
        raise SyncEngineError(
            f"Sync already in progress for account {account_id}"
        )
    state.sync_in_progress = True
    state.sync_status = "syncing"
    db.flush()
    try:
        yield state
    finally:
        state.sync_in_progress = False
        db.flush()


def _record_success(state: CalendarAccountSyncState) -> None:
    state.sync_status = "synced"
    state.sync_error_message = None
    state.consecutive_error_count = 0
    state.last_sync_at = datetime.now(timezone.utc)


def _record_failure(state: CalendarAccountSyncState, error_message: str) -> None:
    state.consecutive_error_count = (state.consecutive_error_count or 0) + 1
    state.sync_error_message = error_message[:1000]
    state.sync_status = "error"


# ─────────────────────────────────────────────────────────────────────
# Initial backfill
# ─────────────────────────────────────────────────────────────────────


def run_initial_backfill(
    db: Session,
    *,
    account: CalendarAccount,
) -> dict[str, int | str | None]:
    """Run the initial backfill for an account per canonical §3.26.16.4.

    Asymmetric backfill window: ``account.backfill_window_past_days``
    (default 90) + ``account.backfill_window_future_days`` (default 365).
    Provider-agnostic: delegates to provider.sync_initial. Updates
    ``backfill_status`` + ``backfill_progress_pct`` + cursor state.
    Idempotent via per-event dedup in ingestion.

    For local provider, this is a no-op (sync_initial returns success
    with 0 events synced — local events live directly in the canonical
    table; no provider-side inbox to backfill).
    """
    if account.backfill_status == "in_progress":
        raise SyncEngineError(
            f"Backfill already in progress for account {account.id}"
        )

    account.backfill_status = "in_progress"
    account.backfill_started_at = datetime.now(timezone.utc)
    account.backfill_progress_pct = 0
    db.flush()

    _audit(
        db,
        tenant_id=account.tenant_id,
        actor_user_id=None,
        action="backfill_started",
        entity_type="calendar_account",
        entity_id=account.id,
        changes={
            "backfill_window_past_days": account.backfill_window_past_days,
            "backfill_window_future_days": account.backfill_window_future_days,
        },
    )

    events_synced = 0
    error: str | None = None

    try:
        with _sync_mutex(db, account.id) as state:
            provider_cls = get_provider_class(account.provider_type)
            # Per Q1 Path A: pass db_session + account_id constructor
            # params so providers can reach canonical state without
            # the deliberate-hack ``__db__`` injection.
            provider = provider_cls(
                account.provider_config or {},
                db_session=db,
                account_id=account.id,
            )
            result = provider.sync_initial(
                backfill_window_days=account.backfill_window_past_days,
                lookahead_window_days=account.backfill_window_future_days,
            )
            if not result.success:
                raise SyncEngineError(
                    result.error_message or "Provider sync_initial failed"
                )
            events_synced = result.events_synced

            # Persist cursor — provider returns provider-specific shape.
            new_cursor = state.last_provider_cursor or {}
            if result.last_sync_token:
                # Google uses sync_token; MS Graph uses delta_token.
                # Per-provider cursor key chosen by provider in result.
                if account.provider_type == "google_calendar":
                    new_cursor["sync_token"] = result.last_sync_token
                elif account.provider_type == "msgraph":
                    new_cursor["delta_token"] = result.last_sync_token
                else:
                    new_cursor["cursor"] = result.last_sync_token
            state.last_provider_cursor = new_cursor

            _record_success(state)

        account.backfill_status = "completed"
        account.backfill_progress_pct = 100
        account.backfill_completed_at = datetime.now(timezone.utc)
        db.flush()

        _audit(
            db,
            tenant_id=account.tenant_id,
            actor_user_id=None,
            action="backfill_completed",
            entity_type="calendar_account",
            entity_id=account.id,
            changes={
                "events_synced": events_synced,
            },
        )
    except Exception as exc:  # noqa: BLE001 - circuit-breaker entry
        error = str(exc)
        logger.exception(
            "Backfill failed for account %s: %s", account.id, exc
        )
        state = ensure_sync_state(db, account_id=account.id)
        _record_failure(state, error)
        account.backfill_status = "error"
        db.flush()

        _audit(
            db,
            tenant_id=account.tenant_id,
            actor_user_id=None,
            action="backfill_failed",
            entity_type="calendar_account",
            entity_id=account.id,
            changes={"error": error[:500]},
        )

    return {
        "events_synced": events_synced,
        "error": error,
    }


# ─────────────────────────────────────────────────────────────────────
# Single-event ingestion (Step 2.1 webhook handlers consume; Step 2
# stub for manual fetch via /sync-now path)
# ─────────────────────────────────────────────────────────────────────


def ingest_event_by_provider_id(
    db: Session,
    *,
    account: CalendarAccount,
    provider_event_id: str,
) -> dict:
    """Fetch + ingest a single event identified by provider id.

    Used by webhook handlers (Step 2.1) + manual fetch flows. Idempotent
    via (account_id, provider_event_id) unique index in ingestion.
    """
    provider_cls = get_provider_class(account.provider_type)
    provider = provider_cls(
        account.provider_config or {},
        db_session=db,
        account_id=account.id,
    )

    try:
        provider_event = provider.fetch_event(provider_event_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "fetch_event failed for account %s event %s: %s",
            account.id,
            provider_event_id,
            exc,
        )
        state = ensure_sync_state(db, account_id=account.id)
        _record_failure(state, str(exc))
        return {"ingested": False, "error": str(exc)}

    event = ingest_provider_event(
        db, account=account, provider_event=provider_event
    )

    state = ensure_sync_state(db, account_id=account.id)
    _record_success(state)

    return {
        "ingested": True,
        "event_id": event.id,
    }
