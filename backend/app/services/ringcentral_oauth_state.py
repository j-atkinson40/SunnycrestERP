"""RingCentral OAuth state — an opaque, single-use, TTL-bounded nonce.

⚠️ WHAT THIS REPLACES. From `1e48454b` (2026-04-08) until 2026-09-03,
`GET /api/v1/integrations/ringcentral/oauth/callback` read its `state` query
parameter as a RAW `company_id`:

    company_id = state
    company = db.query(Company).filter(Company.id == company_id).first()
    ...
    company.set_setting("ringcentral_access_token", encrypt_secret(...))

That endpoint is a public, unauthenticated GET. `state` is a CSRF parameter —
attacker-supplied by construction — and it was being used as a tenant SELECTOR.
Anyone holding a valid RingCentral authorization code, trivially obtained from
their own free RingCentral account, could name any tenant's `company_id` and
write their own tokens into that tenant's settings. That is a cross-tenant
write on an unauthenticated public endpoint.

THE INVARIANT THIS MODULE ESTABLISHES: the company binding comes from
server-side state created at INITIATION, never from the callback's parameters.
The callback learns which tenant it is acting for by reading the nonce row it
just consumed. Nothing the caller sends can change that answer.

──────────────────────────────────────────────────────────────────────────
WHAT TRANSFERRED FROM THE SIBLINGS, AND WHAT DID NOT

Two correct implementations already existed in this repo:
`app/services/calendar/oauth_service.py` and
`app/services/email/oauth_service.py`. Both are the same shape.

TRANSFERRED verbatim:
  - the `oauth_state_nonces` table (Email r64, platform-shared; the
    `provider_type` column takes arbitrary strings, so RingCentral joins with
    a disjoint value rather than needing a migration)
  - `secrets.token_urlsafe(32)` as the nonce
  - the ten-minute TTL
  - single-use semantics via the `consumed_at` flip
  - the rejection ladder: not-found → replay → expired → provider mismatch

DID NOT TRANSFER — and this is the one real design difference:

  The siblings' `validate_and_consume_state_nonce` takes `tenant_id` and
  `user_id` as INPUTS TO BE MATCHED. It can, because their callbacks are
  authenticated: the browser arrives with a session, the route already knows
  who the caller is, and the nonce is a cross-CHECK against that.

  RingCentral's callback has no session. RC redirects the browser to it
  directly and there is no authenticated identity to check against. So here
  the nonce row is the SOURCE of the binding, not a check on one. There is no
  `tenant_id` parameter to `validate_and_consume_state_nonce` in this module —
  deliberately, because accepting one would reintroduce the exact defect: a
  caller-supplied tenant identifier reaching a write path.

  The consequence is that this module's validate is STRICTLY less permissive
  than the siblings', not more: it has fewer inputs to be lied to with.

──────────────────────────────────────────────────────────────────────────
ORDERING — THE CALLBACK REJECTS EVERYTHING TODAY, ON PURPOSE

No authorize endpoint exists yet (S-3a established the entrance is half-built:
no authorize route, no frontend authorize URL, and the "Connect RingCentral"
button has no `onClick` and no `href` — S-3b disabled it outright). So nothing
calls `issue_state_nonce` today, so no nonce exists, so every callback request
is rejected.

That is the intended state and not a gap. A callback that rejects all input is
strictly better than one that accepts hostile input. `issue_state_nonce` is
built now so the provisioning arc's authorize endpoint has the correct minting
already sitting here, rather than inventing its own under schedule pressure.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.email_primitive import OAuthStateNonce

logger = logging.getLogger(__name__)


#: Disjoint from Calendar's (``google_calendar`` / ``msgraph``) and Email's
#: (``gmail`` / ``msgraph``). A nonce minted for a calendar or mail flow must
#: not redeem at RingCentral's callback, and vice versa — enforced below.
PROVIDER_TYPE = "ringcentral"

#: Matches the siblings. Ten minutes is an OAuth round trip with room for a
#: consent screen, not a session.
_NONCE_TTL_MINUTES = 10


class RingCentralOAuthStateInvalid(Exception):
    """The state nonce is unknown, expired, already consumed, or not ours.

    Every one of those is a REJECTION. There is no degraded path, no
    best-effort resolution, and no environment in which this is tolerated.
    """


def issue_state_nonce(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    redirect_uri: str,
) -> str:
    """Mint a state nonce binding this OAuth flow to `tenant_id`.

    Called from an AUTHENTICATED initiation endpoint — the provisioning arc's
    authorize route — where `tenant_id` comes from the caller's session and
    never from a request parameter. The returned string is what goes into the
    RingCentral authorize URL's ``state=``.

    The nonce is opaque: it carries no information, so it discloses nothing if
    logged or leaked into a Referer header, and it cannot be forged into a
    different tenant's identifier because it is not an identifier.

    Does not commit — the caller owns the transaction, as in both siblings.
    """
    nonce = secrets.token_urlsafe(32)
    row = OAuthStateNonce(
        nonce=nonce,
        tenant_id=tenant_id,
        user_id=user_id,
        provider_type=PROVIDER_TYPE,
        redirect_uri=redirect_uri,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=_NONCE_TTL_MINUTES),
    )
    db.add(row)
    db.flush()
    return nonce


def validate_and_consume_state_nonce(db: Session, *, nonce: str) -> OAuthStateNonce:
    """Validate + atomically consume the nonce. Returns the row it validated.

    ⚠️ THE RETURN VALUE IS THE POINT. The caller reads `row.tenant_id` to learn
    which company this callback is acting for. It must not read a company from
    any request parameter — that is the defect this module exists to remove.

    Raises `RingCentralOAuthStateInvalid` on every failure mode, with no
    fallback in any environment:

      - unknown nonce (including the empty string, and including a raw
        `company_id` supplied by an attacker who read the old code)
      - already consumed — replay
      - expired
      - minted for a different provider's flow

    Single-use is enforced by flipping `consumed_at` in the same transaction,
    so the second redemption of a nonce takes the replay branch.
    """
    if not nonce:
        raise RingCentralOAuthStateInvalid("OAuth state nonce missing.")

    row = db.query(OAuthStateNonce).filter(OAuthStateNonce.nonce == nonce).first()
    if row is None:
        # This is also the branch a raw company_id lands in. The old callback
        # would have looked that up and written to it.
        raise RingCentralOAuthStateInvalid("OAuth state nonce not found.")
    if row.consumed_at is not None:
        raise RingCentralOAuthStateInvalid("OAuth state nonce already consumed (replay).")
    if row.expires_at < datetime.now(timezone.utc):
        raise RingCentralOAuthStateInvalid("OAuth state nonce expired.")
    if row.provider_type != PROVIDER_TYPE:
        raise RingCentralOAuthStateInvalid("OAuth state nonce provider mismatch.")

    row.consumed_at = datetime.now(timezone.utc)
    db.flush()
    return row
