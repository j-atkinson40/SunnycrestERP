"""RingCentral webhook + SSE routes for Call Intelligence.

Handles:
  - POST /webhook — RingCentral telephony event notifications
  - GET  /events  — SSE stream for frontend call overlay
  - GET  /oauth/callback — OAuth token exchange (future)
"""

import asyncio
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_db
from app.config import settings
from app.core.security import decode_token
from app.database import SessionLocal
from app.models.ringcentral_call_log import RingCentralCallLog
from app.models.user import User
from app.services.phone_lookup_service import (
    enrich_customer_context,
    lookup_customer_by_phone,
)
from app.services.sse_manager import emit_to_tenant, subscribe, unsubscribe

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Webhook validation
# ---------------------------------------------------------------------------


def _verify_webhook_signature(body: bytes, signature: str | None) -> bool:
    """Verify RingCentral webhook signature (HMAC-SHA256). FAILS CLOSED.

    ⚠️ THIS FAILED OPEN TWICE, FROM 2026-04-08 (`1e48454b`) UNTIL 2026-09-03.
    It returned True unconditionally outside production, and returned True IN
    production whenever `RINGCENTRAL_CLIENT_SECRET` was unset. The endpoint it
    guards writes to `ringcentral_call_log`, so for that window any environment
    reporting a non-production `ENVIRONMENT` — staging reports `"dev"` — exposed
    an unauthenticated public writer into the database.

    ⚠️ WHY THE PRODUCTION-SECRET CHECK WAS THE WORSE HALF. "Production's secret
    is set" was true, enforced by nothing, and checked by no one. The day it
    stopped being true the guard would have gone QUIET rather than loud — an
    expired premise living in code rather than in a shell script (CLAUDE.md §11,
    "Expired premise — and its inherited form"). A missing secret is now a
    REFUSAL, so that failure is loud in every environment.

    No unconditional pass remains. An unset secret rejects; a missing signature
    rejects; a mismatched signature rejects.
    """
    if not settings.RINGCENTRAL_CLIENT_SECRET:
        # Fail closed. An unconfigured integration must refuse traffic, not
        # accept everything — the alternative is a public write endpoint whose
        # openness is invisible because nothing reports it.
        logger.error(
            "RingCentral webhook rejected: RINGCENTRAL_CLIENT_SECRET is unset. "
            "The endpoint is refusing all traffic until it is configured."
        )
        return False
    if not signature:
        return False

    expected = hmac.new(
        settings.RINGCENTRAL_CLIENT_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ---------------------------------------------------------------------------
# POST /webhook — RingCentral telephony event handler
# ---------------------------------------------------------------------------


@router.post("/webhook")
async def ringcentral_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle RingCentral telephony webhook events.

    RC sends a validation token on subscription setup, and telephony
    notifications for call state changes.
    """
    body = await request.body()

    # RC subscription validation — echo the validation token
    validation_token = request.headers.get("Validation-Token")
    if validation_token:
        logger.info("RingCentral webhook validation received")
        return Response(
            content="",
            status_code=200,
            headers={"Validation-Token": validation_token},
        )

    # Verify signature
    signature = request.headers.get("X-RingCentral-Signature")
    if not _verify_webhook_signature(body, signature):
        logger.warning("Invalid RingCentral webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # RC wraps events in body.body for telephony notifications
    event_body = payload.get("body") or payload
    event_type = payload.get("event", "")

    logger.info("RC webhook event: %s", event_type)

    # Route based on telephony event type
    if "/telephony/sessions" in event_type or "telephonyStatus" in str(event_body):
        await _handle_telephony_event(db, event_body, payload)
    elif "/voicemail" in event_type:
        _handle_voicemail_event(db, event_body, payload)
    else:
        logger.debug("Unhandled RC event type: %s", event_type)

    return {"status": "ok"}


async def _handle_telephony_event(db: Session, event_body: dict, payload: dict):
    """Process a telephony session event (ringing, answered, ended)."""
    # RC telephony event structure varies — normalize
    parties = event_body.get("parties", [])
    if not parties:
        # Try alternate structure
        parties = [event_body]

    for party in parties:
        status = (party.get("status", {}).get("code", "") if isinstance(party.get("status"), dict) else party.get("telephonyStatus", "")).lower()
        direction = party.get("direction", "Inbound").lower()

        # Get phone numbers
        from_data = party.get("from", {})
        to_data = party.get("to", {})

        caller_number = from_data.get("phoneNumber", "") if direction == "inbound" else to_data.get("phoneNumber", "")
        caller_name = from_data.get("name", "") if direction == "inbound" else to_data.get("name", "")
        callee_number = to_data.get("phoneNumber", "") if direction == "inbound" else from_data.get("phoneNumber", "")

        session_id = party.get("sessionId") or event_body.get("sessionId") or payload.get("sessionId", "")
        rc_call_id = party.get("id") or session_id

        if not rc_call_id:
            continue

        # Tenant comes from the ENVELOPE's RC identity (subscriptionId /
        # ownerId), not from the party. `_resolve_tenant_id` logs its own
        # rejection reason; an unresolvable event is dropped, never defaulted.
        tenant_id = _resolve_tenant_id(db, payload)
        if not tenant_id:
            continue

        if status in ("ringing", "proceeding"):
            await _on_call_ringing(db, tenant_id, rc_call_id, session_id, direction, caller_number, caller_name, callee_number)
        elif status in ("answered", "callconnected"):
            await _on_call_answered(db, tenant_id, rc_call_id)
        elif status in ("disconnected", "noanswer", "busy", "voicemail"):
            await _on_call_ended(db, tenant_id, rc_call_id, status, party)


#: Per-tenant RingCentral identities, most specific first. Both are stored in
#: `companies.settings_json` by the OAuth callback / the provisioning arc's
#: subscription creation, and both are matched EXACTLY against the field of the
#: same meaning in the webhook envelope.
#:
#:   ringcentral_subscription_id ← envelope `subscriptionId` — per-subscription,
#:       so it is one-to-one with the tenant that created the subscription.
#:       NOT WRITTEN YET: no code creates RC subscriptions (S-3a). The
#:       provisioning arc must store it when it does.
#:   ringcentral_owner_id        ← envelope `ownerId` — the extension that owns
#:       the subscription. Written today by `oauth_callback` from the token
#:       response's `owner_id`.
#:
#: Envelope field names verified against RingCentral's published notification
#: structure (developers.ringcentral.com, Account Telephony Sessions Event),
#: not inferred from what this file happened to read.
_RC_IDENTITY_KEYS: tuple[tuple[str, str], ...] = (
    ("ringcentral_subscription_id", "subscriptionId"),
    ("ringcentral_owner_id", "ownerId"),
)


def _envelope_identity(envelope: dict, envelope_field: str) -> str | None:
    """Read one identity out of the webhook envelope, normalized to a string.

    RingCentral sends `ownerId` as a quoted numeric ("400144455008"); coercing
    both sides through `str().strip()` keeps a stored int and a delivered
    string from silently failing to match.
    """
    value = envelope.get(envelope_field)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_tenant_id(db: Session, envelope: dict) -> str | None:
    """Resolve which tenant this webhook belongs to, or None to REJECT it.

    ⚠️ WHAT THIS REPLACES. Until 2026-09-03 this function returned the FIRST
    company whose settings carried `ringcentral_connected`, ignoring both of
    its arguments entirely:

        for company in companies:
            if (company.settings or {}).get("ringcentral_connected"):
                return company.id
        if settings.ENVIRONMENT != "production":
            return <any active company>

    So the first tenant ever to connect RingCentral would have captured every
    inbound call for every tenant — call logs, caller identification, AR
    balances, and the after-call extraction pipeline, all written under the
    wrong `tenant_id`. Outside production it did not even require a connection:
    any active company would do, and staging reports `ENVIRONMENT="dev"`.

    ⚠️ `ringcentral_connected` IS STILL READ, AND THAT IS NOT THE OLD BUG. The
    old code used it as the ONLY predicate and took the first row satisfying
    it. Here it is a precondition ON TOP OF an exact identity match: a tenant
    must be connected AND the webhook must name that tenant's stored RC
    identity. It narrows the candidate set; it never selects from it.

    REJECTION IS THE DEFAULT, IN EVERY ENVIRONMENT. No first match, no fallback
    to any active company, no dev-mode convenience. An unresolvable webhook is
    logged and dropped, because the alternative is writing another tenant's
    call into somebody's database.

    Ambiguity also rejects: if two tenants claim the same RC identity, or if
    `subscriptionId` and `ownerId` resolve to different tenants, that is a
    misconfiguration and there is no safe way to guess through it.

    ⚠️ THIS RETURNS None FOR EVERY WEBHOOK TODAY. `ringcentral_owner_id` is
    written only by `oauth_callback`, which now rejects everything until an
    authorize endpoint exists (S-3c Part 1), and `ringcentral_subscription_id`
    is written by nothing at all. Zero tenants have RC identity stored, so
    nothing resolves. That is correct: no tenant is connected, the Connect
    button is disabled, and there is no legitimate inbound call to route.
    """
    from app.models.company import Company

    # `settings_json` is `text`, not JSONB (CLAUDE.md §4 Settings Pattern), so
    # this cannot be a SQL predicate — the decode happens in Python.
    index: dict[tuple[str, str], set[str]] = {}
    for company in db.query(Company).filter(Company.is_active == True).all():  # noqa: E712
        s = company.settings or {}
        if not s.get("ringcentral_connected"):
            continue
        for setting_key, _ in _RC_IDENTITY_KEYS:
            stored = s.get(setting_key)
            if stored is None:
                continue
            stored_text = str(stored).strip()
            if stored_text:
                index.setdefault((setting_key, stored_text), set()).add(company.id)

    resolved: str | None = None
    resolved_via: str | None = None

    for setting_key, envelope_field in _RC_IDENTITY_KEYS:
        delivered = _envelope_identity(envelope, envelope_field)
        if delivered is None:
            continue
        claimants = index.get((setting_key, delivered))
        if not claimants:
            continue
        if len(claimants) > 1:
            logger.error(
                "RingCentral webhook rejected: %s %r is claimed by %d tenants. "
                "Two tenants cannot share one RingCentral identity; refusing to "
                "guess which one this call belongs to.",
                envelope_field,
                delivered,
                len(claimants),
            )
            return None
        candidate = next(iter(claimants))
        if resolved is None:
            resolved, resolved_via = candidate, envelope_field
        elif candidate != resolved:
            logger.error(
                "RingCentral webhook rejected: %s resolves to tenant %s but %s "
                "resolves to tenant %s. Contradictory stored RC identity.",
                resolved_via,
                resolved,
                envelope_field,
                candidate,
            )
            return None

    if resolved is None:
        logger.warning(
            "RingCentral webhook rejected: no connected tenant matches the "
            "identity it names (subscriptionId=%r, ownerId=%r). Dropping — "
            "there is no default tenant, in any environment.",
            _envelope_identity(envelope, "subscriptionId"),
            _envelope_identity(envelope, "ownerId"),
        )
        return None

    return resolved


async def _on_call_ringing(
    db: Session,
    tenant_id: str,
    rc_call_id: str,
    session_id: str,
    direction: str,
    caller_number: str,
    caller_name: str,
    callee_number: str,
):
    """Handle a new incoming/outgoing call — create log, lookup caller, emit SSE."""
    # Check for existing log (RC may send duplicate events)
    existing = (
        db.query(RingCentralCallLog)
        .filter(
            RingCentralCallLog.rc_call_id == rc_call_id,
            RingCentralCallLog.tenant_id == tenant_id,
        )
        .first()
    )
    if existing:
        return

    # Phone lookup
    lookup = lookup_customer_by_phone(db, tenant_id, caller_number)
    company_entity_id = lookup["company_entity_id"] if lookup else None
    customer_id = lookup["customer_id"] if lookup else None
    resolved_name = lookup["caller_name"] if lookup else caller_name
    company_name = lookup["company_name"] if lookup else None

    # Create call log
    call_log = RingCentralCallLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        rc_call_id=rc_call_id,
        rc_session_id=session_id,
        direction=direction,
        call_status="ringing",
        caller_number=caller_number,
        caller_name=resolved_name or caller_name,
        callee_number=callee_number,
        company_entity_id=company_entity_id,
        customer_id=customer_id,
        started_at=datetime.now(timezone.utc),
    )
    db.add(call_log)
    db.commit()

    # Enrich context
    context = enrich_customer_context(db, tenant_id, customer_id, company_entity_id)

    # Emit SSE event
    emit_to_tenant(tenant_id, "call_started", {
        "call_id": call_log.id,
        "direction": direction,
        "caller_number": caller_number,
        "caller_name": resolved_name or caller_name,
        "company_name": company_name,
        "company_id": company_entity_id,
        "last_order_date": context.get("last_order_date"),
        "open_ar_balance": context.get("open_ar_balance"),
        "recent_invoices": context.get("recent_invoices", []),
    })

    logger.info("Call started: %s from %s (%s)", call_log.id, caller_number, company_name or "unknown")


async def _on_call_answered(db: Session, tenant_id: str, rc_call_id: str):
    """Update call log status and emit SSE event."""
    call_log = (
        db.query(RingCentralCallLog)
        .filter(
            RingCentralCallLog.rc_call_id == rc_call_id,
            RingCentralCallLog.tenant_id == tenant_id,
        )
        .first()
    )
    if not call_log:
        return

    call_log.call_status = "answered"
    call_log.answered_at = datetime.now(timezone.utc)
    db.commit()

    emit_to_tenant(tenant_id, "call_answered", {
        "call_id": call_log.id,
    })

    logger.info("Call answered: %s", call_log.id)


async def _on_call_ended(db: Session, tenant_id: str, rc_call_id: str, status: str, party: dict):
    """Update call log, emit SSE event, kick off after-call pipeline."""
    call_log = (
        db.query(RingCentralCallLog)
        .filter(
            RingCentralCallLog.rc_call_id == rc_call_id,
            RingCentralCallLog.tenant_id == tenant_id,
        )
        .first()
    )
    if not call_log:
        return

    call_log.call_status = status if status != "disconnected" else "completed"
    call_log.ended_at = datetime.now(timezone.utc)

    # Calculate duration
    if call_log.started_at:
        delta = call_log.ended_at - call_log.started_at
        call_log.duration_seconds = int(delta.total_seconds())

    # Check for recording ID
    recording = party.get("recording", {})
    if recording and recording.get("id"):
        call_log.rc_recording_id = str(recording["id"])

    db.commit()

    emit_to_tenant(tenant_id, "call_ended", {
        "call_id": call_log.id,
        "duration_seconds": call_log.duration_seconds,
    })

    logger.info("Call ended: %s (duration=%ss, status=%s)", call_log.id, call_log.duration_seconds, status)

    # Kick off after-call pipeline in background thread (10s delay for recording)
    if call_log.call_status == "completed" and call_log.duration_seconds and call_log.duration_seconds > 10:
        _start_after_call_pipeline(call_log.id, tenant_id)


def _start_after_call_pipeline(call_id: str, tenant_id: str):
    """Run the after-call pipeline in a background thread with its own DB session."""

    def _run():
        from app.services.after_call_service import process_call_after_end
        from app.services.sse_manager import emit_to_tenant as emit

        session = SessionLocal()
        try:
            # Get RC token from tenant settings for recording fetch
            from app.models.company import Company
            company = session.query(Company).filter(Company.id == tenant_id).first()
            rc_token = None
            if company:
                s = company.settings or {}
                rc_token = s.get("ringcentral_access_token")
                if rc_token:
                    # Decrypt at use (encrypted-from-birth; a legacy
                    # plaintext value would fail loud here — the census
                    # proved none exist anywhere).
                    from app.services.email.crypto import decrypt_secret
                    rc_token = decrypt_secret(rc_token)

            result = process_call_after_end(session, call_id, tenant_id, rc_token=rc_token)

            # Emit call_processed event with extraction results
            if result.get("extraction"):
                emit(tenant_id, "call_processed", {
                    "call_id": call_id,
                    "extraction": result.get("extraction"),
                    "kb_results": result.get("kb_results", []),
                })
        except Exception as e:
            logger.error("After-call pipeline failed for %s: %s", call_id, e)
        finally:
            session.close()

    thread = Thread(target=_run, daemon=True)
    thread.start()


def _handle_voicemail_event(db: Session, event_body: dict, payload: dict):
    """Handle a voicemail notification — create log, queue transcription."""
    logger.info("Voicemail event received: %s", payload.get("event", ""))

    from_data = event_body.get("from", {})
    caller_number = from_data.get("phoneNumber", "")

    # Same envelope, same identity fields. The old call passed ("", {}) — both
    # arguments were ignored, which is how a voicemail for any tenant landed on
    # whichever tenant happened to be first.
    tenant_id = _resolve_tenant_id(db, payload)
    if not tenant_id:
        return

    lookup = lookup_customer_by_phone(db, tenant_id, caller_number)

    call_log = RingCentralCallLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        rc_call_id=event_body.get("id", str(uuid.uuid4())),
        direction="inbound",
        call_status="voicemail",
        caller_number=caller_number,
        caller_name=lookup["caller_name"] if lookup else from_data.get("name"),
        company_entity_id=lookup["company_entity_id"] if lookup else None,
        customer_id=lookup["customer_id"] if lookup else None,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    db.add(call_log)
    db.commit()

    # Process voicemail in background
    def _run():
        from app.services.after_call_service import process_voicemail as pv

        session = SessionLocal()
        try:
            vm_text = event_body.get("attachments", [{}])[0].get("vmTranscriptionStatus") if event_body.get("attachments") else None
            pv(session, call_log.id, tenant_id, rc_voicemail_text=vm_text)
        except Exception as e:
            logger.error("Voicemail processing failed: %s", e)
        finally:
            session.close()

    thread = Thread(target=_run, daemon=True)
    thread.start()


# ---------------------------------------------------------------------------
# GET /events — SSE stream for frontend
# ---------------------------------------------------------------------------


@router.get("/events")
async def sse_events(token: str = Query(...)):
    """SSE endpoint for real-time call events.

    Authenticates via JWT token passed as query parameter (EventSource
    doesn't support Authorization headers).

    THE HANGING-JOBS FIX (2026-07-20): no Depends(get_db) — a dependency
    session lives until the RESPONSE completes, and an SSE response never
    completes, so every connected stream pinned one connection from the
    (size 5 + overflow 10) pool for its whole life. The auth lookup opens
    and CLOSES its own session before the stream starts; the stream holds
    nothing but its asyncio queue.
    """
    # Validate JWT
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Look up user to get tenant — session opened + closed HERE.
    from app.database import SessionLocal
    _db = SessionLocal()
    try:
        user = _db.query(User).filter(User.id == user_id).first()
        if not user or not user.company_id:
            raise HTTPException(status_code=401, detail="User not found")
        tenant_id = user.company_id
    finally:
        _db.close()
    queue = subscribe(tenant_id, user_id)

    async def event_generator():
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": msg["event"],
                        "data": json.dumps(msg["data"]),
                    }
                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent connection timeout
                    yield {"comment": "keepalive"}
        except asyncio.CancelledError:
            pass
        finally:
            unsubscribe(tenant_id, user_id, queue)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# GET /oauth/callback — RingCentral OAuth token exchange
# ---------------------------------------------------------------------------


@router.get("/oauth/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(""),
    db: Session = Depends(get_db),
):
    """Exchange OAuth authorization code for RC access/refresh tokens.

    Stores tokens in company.settings (same pattern as DocuSign/QBO).

    ⚠️ `state` IS A NONCE, NOT A TENANT SELECTOR. From `1e48454b` (2026-04-08)
    until 2026-09-03 this handler read `state` as a raw `company_id` on a
    public unauthenticated GET, so anyone with a RingCentral authorization
    code from their own account could write their tokens into any tenant's
    settings. The company binding now comes from server-side state created at
    initiation — see `app/services/ringcentral_oauth_state.py`, which also
    records what did and did not transfer from the two correct sibling
    implementations.

    ⚠️ THIS REJECTS EVERY REQUEST TODAY, DELIBERATELY. No authorize endpoint
    exists yet, so nothing mints nonces, so no nonce validates. A callback that
    rejects all input is strictly better than one that accepts hostile input,
    and the Connect button is already disabled (S-3b).
    """
    import httpx

    from app.services.ringcentral_oauth_state import (
        RingCentralOAuthStateInvalid,
        validate_and_consume_state_nonce,
    )

    if not settings.RINGCENTRAL_CLIENT_ID or not settings.RINGCENTRAL_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="RingCentral OAuth not configured")

    # Consume BEFORE the token exchange. A nonce burned by a failed exchange
    # costs the user a restart; a nonce still live during an exchange is a
    # retry window on a public endpoint.
    try:
        nonce_row = validate_and_consume_state_nonce(db, nonce=state)
    except RingCentralOAuthStateInvalid as exc:
        logger.warning("RingCentral OAuth callback rejected: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    # THE BINDING. Read off the consumed nonce — never off a request parameter.
    company_id = nonce_row.tenant_id

    # Commit the consumption on its own. Without this the `consumed_at` flip
    # is only flushed, so any later failure in this handler rolls it back and
    # the nonce becomes replayable — single-use that is only single-use on the
    # happy path is not single-use.
    db.commit()

    from app.models.company import Company

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        # The nonce's tenant vanished between initiation and callback. Reject;
        # there is no other company this could reasonably mean.
        raise HTTPException(status_code=404, detail="Company not found")

    # Exchange code for tokens
    redirect_uri = f"{settings.FRONTEND_URL}/settings/call-intelligence"
    if settings.ENVIRONMENT == "production":
        redirect_uri = f"https://api.{settings.PLATFORM_DOMAIN}/api/v1/integrations/ringcentral/oauth/callback"

    token_url = f"{settings.RINGCENTRAL_SERVER_URL}/restapi/oauth/token"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            auth=(settings.RINGCENTRAL_CLIENT_ID, settings.RINGCENTRAL_CLIENT_SECRET),
        )

    if resp.status_code != 200:
        logger.error("RC OAuth token exchange failed: %s %s", resp.status_code, resp.text)
        raise HTTPException(status_code=400, detail="OAuth token exchange failed")

    tokens = resp.json()

    # Store tokens in company settings — ENCRYPTED FROM BIRTH (member four
    # of the plaintext-credential class, closed 2026-07-18 with zero rows
    # ever written plaintext; the census confirmed before this landed).
    from app.services.email.crypto import encrypt_secret
    company.set_setting(
        "ringcentral_access_token",
        encrypt_secret(tokens["access_token"]) if tokens.get("access_token") else None,
    )
    company.set_setting(
        "ringcentral_refresh_token",
        encrypt_secret(tokens["refresh_token"]) if tokens.get("refresh_token") else None,
    )
    company.set_setting("ringcentral_token_expires_in", tokens.get("expires_in"))
    company.set_setting("ringcentral_owner_id", tokens.get("owner_id"))
    company.set_setting("ringcentral_connected", True)
    db.commit()

    logger.info("RingCentral OAuth connected for company %s", company_id)

    # Redirect to settings page
    frontend = settings.FRONTEND_URL
    if settings.ENVIRONMENT == "production":
        slug = company.slug or ""
        frontend = f"https://{slug}.{settings.PLATFORM_DOMAIN}"

    return Response(
        status_code=302,
        headers={"Location": f"{frontend}/settings/call-intelligence?rc_connected=1"},
    )
