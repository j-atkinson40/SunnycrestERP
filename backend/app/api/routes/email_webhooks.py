"""Email provider webhook endpoints — Phase W-4b Layer 1 Step 2.

Public endpoints (no Bearer auth — provider callbacks):

  - POST /api/v1/email/webhooks/gmail — Gmail Pub/Sub notifications
  - POST /api/v1/email/webhooks/msgraph — MS Graph subscription
    notifications (also handles validationToken handshake)

Authentication is via per-provider signature verification + per-
account routing. Each notification carries the provider account
id; we route to the matching ``EmailAccount`` by
``email_address`` (Gmail) or ``subscription_id``
mapping in ``email_account_sync_state.subscription_resource_id``
(Graph).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.email_primitive import (
    EmailAccount,
    EmailAccountSyncState,
)
from app.services.email.webhooks import (
    WebhookSignatureError,
    WebhookValidationError,
    handle_gmail_notification,
    handle_msgraph_notification,
    handle_msgraph_validation_token,
    parse_gmail_pubsub_payload,
    verify_gmail_pubsub_jwt,
)


logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# Gmail Pub/Sub
# ─────────────────────────────────────────────────────────────────────


@router.post("/gmail", status_code=204)
async def gmail_webhook(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Response:
    """Receive Gmail Pub/Sub notification.

    Pub/Sub expects a 2xx response within 10s; our handler is fast
    (audit + cursor update only — message fetch happens on the next
    sync sweep).
    """
    try:
        verify_gmail_pubsub_jwt(authorization)
    except WebhookSignatureError as exc:
        logger.warning("Gmail webhook signature failed: %s", exc)
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    try:
        envelope = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    try:
        notification = parse_gmail_pubsub_payload(envelope)
    except WebhookValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    email_address = notification.get("emailAddress", "").lower().strip()
    if not email_address:
        raise HTTPException(
            status_code=400, detail="Pub/Sub notification missing emailAddress"
        )

    # Route to account by email_address. Tenant scoping via
    # is_active=true filter; one active gmail account per email.
    account = (
        db.query(EmailAccount)
        .filter(
            EmailAccount.email_address == email_address,
            EmailAccount.provider_type == "gmail",
            EmailAccount.is_active.is_(True),
        )
        .first()
    )
    if not account:
        # Unknown account — ack so Pub/Sub doesn't retry forever.
        return Response(status_code=204)

    handle_gmail_notification(db, account=account, notification=notification)
    db.commit()
    return Response(status_code=204)


# ─────────────────────────────────────────────────────────────────────
# Microsoft Graph
# ─────────────────────────────────────────────────────────────────────


@router.post("/msgraph")
async def msgraph_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> Response:
    """Receive MS Graph subscription notification.

    Two modes:
      1. Validation handshake: ``?validationToken=<token>`` query param
         present → echo the token verbatim with text/plain.
      2. Real notification: JSON body containing ``value`` array of
         resource events.
    """
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        echo = handle_msgraph_validation_token(validation_token)
        return Response(
            content=echo or "",
            media_type="text/plain",
            status_code=200,
        )

    try:
        envelope = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    notifications = envelope.get("value") or []
    for notification in notifications:
        subscription_id = notification.get("subscriptionId")
        received_state = notification.get("clientState")

        # Route to account by subscription_id (stored on sync state).
        sync_state = (
            db.query(EmailAccountSyncState)
            .filter(
                EmailAccountSyncState.subscription_resource_id
                == subscription_id
            )
            .first()
        )
        if not sync_state:
            logger.info(
                "Graph webhook for unknown subscription_id %s — ignoring",
                subscription_id,
            )
            continue

        account = (
            db.query(EmailAccount)
            .filter(EmailAccount.id == sync_state.account_id)
            .first()
        )
        if not account:
            continue

        # Expected client_state lives in provider_config (set at
        # subscription creation time).
        expected_state = (account.provider_config or {}).get(
            "subscription_client_state"
        )

        try:
            handle_msgraph_notification(
                db,
                account=account,
                notification=notification,
                received_client_state=received_state,
                expected_client_state=expected_state,
            )
        except WebhookSignatureError as exc:
            logger.warning(
                "Graph webhook signature failed for account %s: %s",
                account.id,
                exc,
            )
            # 202 ack so Graph doesn't retry; the audit log captured
            # the failure.
            continue
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Graph webhook ingestion error for account %s: %s",
                account.id,
                exc,
            )
            continue

    db.commit()
    return Response(status_code=202)
