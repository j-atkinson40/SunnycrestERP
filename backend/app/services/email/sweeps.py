"""APScheduler sweep functions — Phase W-4b Layer 1 Step 2.

Three sweep functions wired into ``app/scheduler.py``:

  1. **email_imap_polling_sweep** — every 5 minutes; finds active
     IMAP accounts whose last_sync_at is > 5 min ago + runs an
     incremental UID-search sync. Polling-only per Step 2 canon
     clarification (IMAP IDLE deferred to Step 2.1).

  2. **email_token_refresh_sweep** — every hour; finds OAuth accounts
     whose token_expires_at is within the next 30 minutes + refreshes
     proactively so a sync sweep doesn't hit a 401 mid-stream.

  3. **email_subscription_renewal_sweep** — every hour; finds
     OAuth accounts with subscription_expires_at within the next 24
     hours + renews the provider-side subscription
     (Gmail watch + MS Graph subscription). Step 2 records intent;
     real renewal ships when production OAuth credentials are
     provisioned.

All sweeps are best-effort with per-account error isolation — one
account's failure never blocks the rest. Per-account audit trail
captured via ``email_audit_log``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_

from app.database import SessionLocal
from app.models.email_primitive import (
    EmailAccount,
    EmailAccountSyncState,
)
from app.services.email import oauth_service
from app.services.email.account_service import _audit
from app.services.email.crypto import decrypt_credentials
from app.services.email.sync_engine import run_initial_backfill


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# 1. IMAP polling sweep (every 5 min)
# ─────────────────────────────────────────────────────────────────────


def email_imap_polling_sweep() -> None:
    """Sweep active IMAP accounts + run incremental sync."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
        accounts = (
            db.query(EmailAccount)
            .join(EmailAccountSyncState)
            .filter(
                EmailAccount.provider_type == "imap",
                EmailAccount.is_active.is_(True),
                EmailAccount.encrypted_credentials.isnot(None),
                EmailAccountSyncState.sync_in_progress.is_(False),
                or_(
                    EmailAccountSyncState.last_sync_at.is_(None),
                    EmailAccountSyncState.last_sync_at < cutoff,
                ),
                # Circuit breaker: pause sync after 5 consecutive errors
                EmailAccountSyncState.consecutive_error_count < 5,
            )
            .all()
        )
        for account in accounts:
            try:
                # Inject IMAP password into provider_config
                creds = decrypt_credentials(account.encrypted_credentials)
                if not creds.get("imap_password"):
                    logger.warning(
                        "IMAP account %s missing password; skipping",
                        account.id,
                    )
                    continue
                cfg = dict(account.provider_config or {})
                cfg["imap_password"] = creds["imap_password"]
                account.provider_config = cfg
                run_initial_backfill(db, account=account)
                db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "IMAP polling sweep failed for account %s: %s",
                    account.id,
                    exc,
                )
                db.rollback()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# 2. Token refresh sweep (every hour)
# ─────────────────────────────────────────────────────────────────────


def email_token_refresh_sweep() -> None:
    """Refresh OAuth tokens that expire within the next 30 minutes.

    Avoids long-running syncs hitting mid-stream 401s. Per-account
    audit trail via ``credentials_refreshed`` action.
    """
    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) + timedelta(minutes=30)
        accounts = (
            db.query(EmailAccount)
            .filter(
                EmailAccount.provider_type.in_(("gmail", "msgraph")),
                EmailAccount.is_active.is_(True),
                EmailAccount.encrypted_credentials.isnot(None),
                EmailAccount.token_expires_at.isnot(None),
                EmailAccount.token_expires_at <= threshold,
            )
            .all()
        )
        for account in accounts:
            try:
                oauth_service.refresh_token(db, account=account)
                db.commit()
            except oauth_service.OAuthAuthError as exc:
                logger.warning(
                    "Token refresh failed for account %s: %s",
                    account.id,
                    exc,
                )
                # Audit row already written by oauth_service; don't
                # propagate.
                db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Token refresh sweep crashed on account %s: %s",
                    account.id,
                    exc,
                )
                db.rollback()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# 3. Subscription renewal sweep (every hour)
# ─────────────────────────────────────────────────────────────────────


def email_subscription_renewal_sweep() -> None:
    """Renew Gmail watch + MS Graph subscriptions before expiry.

    Gmail watch expires after 7 days; MS Graph subscriptions expire
    after 4230 minutes (~70.5 hours). We renew when within 24h of
    expiry to give plenty of buffer for sweep cadence.

    Step 2 records intent; real provider-side renewal calls ship
    when production OAuth credentials provisioned. Each renewal
    audit-logged.
    """
    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) + timedelta(hours=24)
        states = (
            db.query(EmailAccountSyncState)
            .join(EmailAccount)
            .filter(
                EmailAccount.provider_type.in_(("gmail", "msgraph")),
                EmailAccount.is_active.is_(True),
                EmailAccountSyncState.subscription_expires_at.isnot(None),
                EmailAccountSyncState.subscription_expires_at <= threshold,
            )
            .all()
        )
        for state in states:
            try:
                account = (
                    db.query(EmailAccount)
                    .filter(EmailAccount.id == state.account_id)
                    .first()
                )
                if not account:
                    continue
                _audit(
                    db,
                    tenant_id=account.tenant_id,
                    actor_user_id=None,
                    action="subscription_renewal_attempted",
                    entity_type="email_account",
                    entity_id=account.id,
                    changes={
                        "provider": account.provider_type,
                        "previous_expires_at": (
                            state.subscription_expires_at.isoformat()
                            if state.subscription_expires_at
                            else None
                        ),
                    },
                )
                # Step 2 stub: extend by canonical-per-provider TTL
                # without an actual provider call. Real renewal call
                # ships when production OAuth credentials registered.
                if account.provider_type == "gmail":
                    state.subscription_expires_at = (
                        datetime.now(timezone.utc) + timedelta(days=7)
                    )
                elif account.provider_type == "msgraph":
                    state.subscription_expires_at = (
                        datetime.now(timezone.utc)
                        + timedelta(minutes=4230)
                    )
                db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Subscription renewal failed for sync state %s: %s",
                    state.id,
                    exc,
                )
                db.rollback()
    finally:
        db.close()
