"""Sync engine — Phase W-4b Layer 1 Step 2.

Cross-provider sync orchestration. Each provider class implements
``sync_initial`` (backfill) + ``fetch_message`` (single-message
fetch on webhook notification or IMAP poll) per the ABC contract;
this module orchestrates state cursor updates + circuit-breaker
+ ingestion.

**Cursor management** — provider-agnostic via
``EmailAccountSyncState.last_provider_cursor`` JSONB. Per-provider
shape:

  - Gmail: ``{"history_id": "12345"}``
  - MS Graph: ``{"delta_token": "https://graph.microsoft.com/...delta..."}``
  - IMAP: ``{"uidvalidity": 123, "uidnext": 456}``

**Circuit breaker** — after 5 consecutive sync failures, sync_status
flips to "error" and ``consecutive_error_count`` keeps tracking.
Operator visibility via EmailAccountsPage. Reset to 0 on next
successful sync.

**Sync mutex** — ``sync_in_progress=true`` prevents two sweeps from
double-syncing the same account. Cleared at the end (success or
failure).
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.email_primitive import EmailAccount, EmailAccountSyncState
from app.services.email.account_service import _audit
from app.services.email.ingestion import ingest_provider_message
from app.services.email.providers import get_provider_class

logger = logging.getLogger(__name__)


_CIRCUIT_BREAKER_THRESHOLD = 5


class SyncEngineError(Exception):
    pass


def _ensure_sync_state(
    db: Session, *, account_id: str
) -> EmailAccountSyncState:
    state = (
        db.query(EmailAccountSyncState)
        .filter(EmailAccountSyncState.account_id == account_id)
        .first()
    )
    if not state:
        # Should never happen post-Step-1 (account_service.create_account
        # bootstraps the row), but defensive.
        import uuid

        state = EmailAccountSyncState(
            id=str(uuid.uuid4()),
            account_id=account_id,
            sync_status="pending",
        )
        db.add(state)
        db.flush()
    return state


@contextmanager
def _sync_mutex(db: Session, account_id: str):
    state = _ensure_sync_state(db, account_id=account_id)
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


def _record_success(state: EmailAccountSyncState) -> None:
    state.sync_status = "synced"
    state.sync_error_message = None
    state.consecutive_error_count = 0
    state.last_sync_at = datetime.now(timezone.utc)


def _record_failure(state: EmailAccountSyncState, error_message: str) -> None:
    state.consecutive_error_count = (state.consecutive_error_count or 0) + 1
    state.sync_error_message = error_message[:1000]
    state.sync_status = "error"


# ─────────────────────────────────────────────────────────────────────
# Initial backfill
# ─────────────────────────────────────────────────────────────────────


def run_initial_backfill(
    db: Session,
    *,
    account: EmailAccount,
) -> dict[str, int]:
    """Run the initial 30-day (or configured) backfill for an account.

    Provider-agnostic: delegates to provider.sync_initial. Updates
    ``backfill_status`` + ``backfill_progress_pct`` + cursor state.
    Idempotent via per-message dedup in ingestion.
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
        entity_type="email_account",
        entity_id=account.id,
        changes={"backfill_days": account.backfill_days},
    )

    messages_synced = 0
    threads_synced = 0
    error: str | None = None

    try:
        with _sync_mutex(db, account.id) as state:
            provider_cls = get_provider_class(account.provider_type)
            provider = provider_cls(account.provider_config or {})
            result = provider.sync_initial(
                max_messages=1000,  # Step 2 cap; Step 4+ surfaces config
            )
            if not result.success:
                raise SyncEngineError(
                    result.error_message or "Provider sync_initial failed"
                )
            messages_synced = result.messages_synced
            threads_synced = result.threads_synced

            # Persist cursor — provider returns provider-specific shape.
            new_cursor = state.last_provider_cursor or {}
            if result.last_history_id:
                new_cursor["history_id"] = result.last_history_id
            if result.last_delta_token:
                new_cursor["delta_token"] = result.last_delta_token
            if result.last_uid:
                new_cursor["last_uid"] = result.last_uid
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
            entity_type="email_account",
            entity_id=account.id,
            changes={
                "messages_synced": messages_synced,
                "threads_synced": threads_synced,
            },
        )
    except Exception as exc:  # noqa: BLE001 - circuit-breaker entry
        error = str(exc)
        logger.exception(
            "Backfill failed for account %s: %s", account.id, exc
        )
        state = _ensure_sync_state(db, account_id=account.id)
        _record_failure(state, error)
        account.backfill_status = "error"
        db.flush()

        _audit(
            db,
            tenant_id=account.tenant_id,
            actor_user_id=None,
            action="backfill_failed",
            entity_type="email_account",
            entity_id=account.id,
            changes={"error": error[:500]},
        )

    return {
        "messages_synced": messages_synced,
        "threads_synced": threads_synced,
        "error": error,
    }


# ─────────────────────────────────────────────────────────────────────
# Single-message ingestion (called by webhook handlers + IMAP poll)
# ─────────────────────────────────────────────────────────────────────


def ingest_message_by_provider_id(
    db: Session,
    *,
    account: EmailAccount,
    provider_message_id: str,
) -> dict:
    """Fetch + ingest a single message identified by provider id.

    Used by webhook handlers (Gmail Pub/Sub history.list yields
    message ids; MSGraph notifications carry the message id) + IMAP
    polling (UID-based fetch). Idempotent.
    """
    provider_cls = get_provider_class(account.provider_type)
    provider = provider_cls(account.provider_config or {})

    try:
        provider_message = provider.fetch_message(provider_message_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "fetch_message failed for account %s message %s: %s",
            account.id,
            provider_message_id,
            exc,
        )
        state = _ensure_sync_state(db, account_id=account.id)
        _record_failure(state, str(exc))
        return {"ingested": False, "error": str(exc)}

    msg = ingest_provider_message(
        db, account=account, provider_message=provider_message
    )

    state = _ensure_sync_state(db, account_id=account.id)
    _record_success(state)

    return {
        "ingested": True,
        "message_id": msg.id,
        "thread_id": msg.thread_id,
    }
