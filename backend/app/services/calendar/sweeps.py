"""APScheduler sweep functions — Phase W-4b Layer 1 Calendar Step 2.

Two sweep functions wired into ``app/scheduler.py``:

  1. **calendar_token_refresh_sweep** — every hour; finds OAuth
     accounts whose token_expires_at is within the next 30 minutes +
     refreshes proactively so a sync sweep doesn't hit a 401 mid-stream.
     Mirrors Email's ``email_token_refresh_sweep``.

  2. **calendar_subscription_renewal_sweep** — every hour; finds
     OAuth accounts with subscription_expires_at within the next 24
     hours + renews the provider-side subscription (Google Calendar
     watch + MS Graph subscription). Step 2 records intent; real
     renewal ships at Step 2.1 alongside webhook receivers + production
     OAuth credential provisioning.

All sweeps are best-effort with per-account error isolation — one
account's failure never blocks the rest. Per-account audit trail
captured via ``calendar_audit_log``.

Note: there is NO calendar_imap_polling_sweep parallel to Email's. The
Calendar primitive's polling fallback is the IMAP-equivalent CalDAV
provider strategy per §3.26.16.4 sync table — and CalDAV is omitted
entirely from Step 1 + Step 2 per Q3 architectural decision.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.database import SessionLocal
from app.models.calendar_primitive import (
    CalendarAccount,
    CalendarAccountSyncState,
)
from app.services.calendar import oauth_service
from app.services.calendar.account_service import _audit


logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# 1. Token refresh sweep (every hour)
# ─────────────────────────────────────────────────────────────────────


def calendar_token_refresh_sweep() -> None:
    """Refresh OAuth tokens that expire within the next 30 minutes.

    Avoids long-running syncs hitting mid-stream 401s. Per-account
    audit trail via ``credentials_refreshed`` action.
    """
    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) + timedelta(minutes=30)
        accounts = (
            db.query(CalendarAccount)
            .filter(
                CalendarAccount.provider_type.in_(("google_calendar", "msgraph")),
                CalendarAccount.is_active.is_(True),
                CalendarAccount.encrypted_credentials.isnot(None),
                CalendarAccount.token_expires_at.isnot(None),
                CalendarAccount.token_expires_at <= threshold,
            )
            .all()
        )
        for account in accounts:
            try:
                oauth_service.refresh_token(db, account=account)
                db.commit()
            except oauth_service.OAuthAuthError as exc:
                logger.warning(
                    "Calendar token refresh failed for account %s: %s",
                    account.id,
                    exc,
                )
                # Audit row already written by oauth_service; don't
                # propagate.
                db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Calendar token refresh sweep crashed on account %s: %s",
                    account.id,
                    exc,
                )
                db.rollback()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────
# 2. Subscription renewal sweep (every hour)
# ─────────────────────────────────────────────────────────────────────


def calendar_subscription_renewal_sweep() -> None:
    """Renew Google Calendar watch + MS Graph subscriptions before expiry.

    Google Calendar watch expires after 7 days; MS Graph subscriptions
    expire after 4230 minutes (~70.5 hours). We renew when within 24h
    of expiry to give plenty of buffer for sweep cadence.

    Step 2 records intent; real provider-side renewal calls ship at
    Step 2.1 alongside webhook receivers + production OAuth credential
    provisioning. Each renewal audit-logged.
    """
    db = SessionLocal()
    try:
        threshold = datetime.now(timezone.utc) + timedelta(hours=24)
        states = (
            db.query(CalendarAccountSyncState)
            .join(CalendarAccount)
            .filter(
                CalendarAccount.provider_type.in_(
                    ("google_calendar", "msgraph")
                ),
                CalendarAccount.is_active.is_(True),
                CalendarAccountSyncState.subscription_expires_at.isnot(None),
                CalendarAccountSyncState.subscription_expires_at <= threshold,
            )
            .all()
        )
        for state in states:
            try:
                account = (
                    db.query(CalendarAccount)
                    .filter(CalendarAccount.id == state.account_id)
                    .first()
                )
                if not account:
                    continue
                _audit(
                    db,
                    tenant_id=account.tenant_id,
                    actor_user_id=None,
                    action="subscription_renewal_attempted",
                    entity_type="calendar_account",
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
                # ships at Step 2.1 when production OAuth credentials
                # registered + webhook receivers wired.
                if account.provider_type == "google_calendar":
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
                    "Calendar subscription renewal failed for sync state %s: %s",
                    state.id,
                    exc,
                )
                db.rollback()
    finally:
        db.close()
