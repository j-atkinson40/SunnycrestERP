# RingCentral provisioning — arc scope

> ## ⚠️ RECONSTRUCTED FROM CONTEXT AFTER /tmp LOSS — 2026-09-03
>
> The original lived at `/tmp/rc_provisioning_scope.md` (199 lines, written
> 2026-09-03 during S-3b). `/tmp` was wiped at that day's 11:47 boot. This file
> was rebuilt the same day from conversational context plus the STATE.md S-3a
> and S-3b entries, which had preserved a compressed form of it.
>
> **This is not the original document.** It is shorter in the per-piece detail
> and longer in two places, because S-3c landed after the original was written
> and one claim was re-derived from source rather than recalled.
>
> Provenance is marked inline on every claim:
>
> | Marking | Meaning |
> |---|---|
> | (unmarked) | Restated with the confidence held when originally written; traceable to STATE.md, to code read in-session, or to a cited primary source. |
> | **UNCERTAIN** | Remembered as a conclusion; the derivation is gone. Re-derive before relying on it. |
> | **RE-DERIVED 2026-09-03** | Not reconstruction — established freshly from a cited source during the rescue. |
> | **NEW SINCE THE ORIGINAL** | Was not in the original; comes from S-3c. |
> | **LOST** | Known to have been in the original; cannot be honestly restated. |
>
> A reconstruction that reads as cleanly as the original is the more dangerous
> artifact. Where this file is thinner than the original, it is thinner on
> purpose.

---

## 1. The finding this scope rests on

The RingCentral call pipeline is **built and correct from webhook receipt
through draft-order creation, and cannot be connected to a phone system by any
means present in the product.**

Provisioning is an arc, not a config step. Of eight required pieces, two exist.

---

## 2. The eight pieces

| # | Piece | State |
|---|---|---|
| 1 | OAuth token exchange | **EXISTS** — `ringcentral.py::oauth_callback` |
| 2 | Encrypted token storage | **EXISTS** — `encrypt_secret` at the write site |
| 3 | Authorize / redirect initiation | ABSENT |
| 4 | Token refresh | ABSENT |
| 5 | Expiry awareness | ABSENT |
| 6 | Subscription creation | ABSENT |
| 7 | Subscription renewal | ABSENT |
| 8 | Failure visibility | ABSENT |

### What exists

**1. Token exchange.** `GET /api/v1/integrations/ringcentral/oauth/callback`
exchanges an authorization code and writes `ringcentral_access_token`,
`ringcentral_refresh_token`, `ringcentral_token_expires_in`,
`ringcentral_owner_id`, `ringcentral_connected`. Found by enumerating all 80
`set_setting(` call sites including the five that write a constructed key —
not by filtering for the key string.

**2. Encrypted storage.** Both tokens pass through `encrypt_secret` at the
write site; `decrypt_secret` at use in the after-call pipeline. This settled
the Sales & Orders census's open question #8 by direct observation at the
writer, not by inference from a neighbouring module: **RC tokens are encrypted
from birth**, with zero rows ever written plaintext.

### What is absent

**3. Authorize / redirect initiation.** No `oauth/authorize` route (established
by enumerating the app's route table, not by grepping path strings). No RC
authorize URL anywhere in `frontend/src`. The "Connect RingCentral" button had
no `onClick` and no `href`; S-3b disabled it and labelled it.

**4. Token refresh.** No `grant_type=refresh_token` for RC anywhere.
`ringcentral_refresh_token` has exactly two occurrences in `app/`, both the
write. Both siblings have a refresh path — `calendar/oauth_service.py:343,362`
and `email/oauth_service.py:313`.

**5. Expiry awareness.** `ringcentral_token_expires_in` is stored and never
consulted. See §5 for why storing it at all is insufficient.

**6. Subscription creation.** No code creates an RC subscription. See §4 for
what is and is not knowable about whether one exists.

**7. Subscription renewal.** Nothing renews a subscription. No other
integration in this repo maintains a provider-side subscription, so there is
no in-repo pattern to transfer.

**8. Failure visibility.** Nothing surfaces a broken connection. A tenant whose
token expired or whose subscription lapsed has no signal — this is the
condition under which the integration "demos beautifully and dies quietly."

---

## 3. Session estimate — 5 to 6 sessions

| Portion | Sessions | Why |
|---|---|---|
| Transcription from the siblings (pieces 3, 4, 5) | ~2 | The pattern is fully worked out twice in-repo. |
| Genuinely new (pieces 6, 7) | ~2 | Provider-side subscription lifecycle; no in-repo precedent. |
| Failure visibility (piece 8) | ~1.5 | |

**LOST:** the original contained a finer per-session sequencing plan — which
piece lands in which session and in what order. That breakdown cannot be
honestly restated and should be re-derived at dispatch time.

### ⚠️ Refresh and renewal are INSIDE the minimum set, not adjacent to it

Stated verbatim because it is the exact place a schedule squeeze would cut, and
cutting it produces a connection that demos beautifully and dies quietly.
Without refresh, the connection works for about an hour. Without renewal, it
works until the subscription expires. Both failures arrive *after* the demo, in
silence, in front of a customer rather than in front of a developer.

---

## 4. What transfers from the siblings, and what does not

`app/services/calendar/oauth_service.py` and
`app/services/email/oauth_service.py` are the same shape and both correct.

### Transfers

- The platform-shared `oauth_state_nonces` table (Email r64). **No migration
  needed** — `provider_type` takes arbitrary strings.
- `secrets.token_urlsafe(32)` as the nonce; a ten-minute TTL; single-use via a
  `consumed_at` flip; the rejection ladder (not-found → replay → expired →
  provider mismatch).
- The refresh-on-use discipline: `ensure_fresh_token(account)` as the single
  entry point every provider call goes through, rather than refresh scattered
  at call sites.
- Fernet credential encryption via the shared `CREDENTIAL_ENCRYPTION_KEY`.

### Does NOT transfer

**The authenticated-callback assumption.** Both siblings'
`validate_and_consume_state_nonce` takes `tenant_id` and `user_id` as inputs to
be MATCHED, because their callbacks arrive with a session and the nonce is a
cross-check against it. **RingCentral's callback has no session** — RC redirects
the browser to it directly. The nonce row must therefore be the *source* of the
company binding, not a check on one. Landed in S-3c Part 1 as
`app/services/ringcentral_oauth_state.py`, which has deliberately no
`tenant_id` parameter.

**Subscription lifecycle.** Neither sibling maintains a provider-side
subscription; Google and Microsoft are polled or webhook-registered by a
different mechanism. Pieces 6 and 7 have no in-repo template. **UNCERTAIN:** the
original may have said more about *why* the sibling mechanism does not
generalize; that reasoning is not recoverable.

---

## 5. Transfer caveats and decay traps

### RC rotates refresh tokens — **RE-DERIVED 2026-09-03**

The original recorded this as a caveat. Its derivation did not survive, so
rather than restate it from memory it was re-read from RingCentral's
documentation during this rescue.

Per RingCentral's refresh-token documentation: a new refresh token is usually
generated when the access token is refreshed. Once the app uses the newly
issued access token, the previous refresh token becomes invalid in
approximately ten seconds; if the new access token is not used, the old refresh
token remains valid for up to sixty minutes.

**Consequence for the arc:** the stored refresh token must be replaced on every
refresh, in the same transaction as the access token. The sixty-minute grace
window is a trap, not a feature — it makes a broken implementation work in
testing and fail in production.

> The ten-second / sixty-minute figures are **NEW SINCE THE ORIGINAL**. The
> original asserted rotation without them.

### `ringcentral_token_expires_in` cannot answer whether the token expired

It is stored as a **duration with no issue time**. `expires_in: 3600` says the
token was good for an hour starting at a moment nobody wrote down. The arc must
store an absolute `ringcentral_token_expires_at`, computed at write time, and
consult that.

### ⚠️ RC's subscription TTL was NOT read from RC, and is not stated here

Listing subscriptions requires an access token this system cannot obtain (§6).
**No TTL figure is asserted in this document.** A plausible number is available
from general knowledge and supplying it would look like diligence; it would be
an unsourced claim in a document the arc plans against.

**The arc must read the TTL from RC's response at subscription creation and
store it, not hardcode it.** This non-answer survives the reconstruction
deliberately.

### Store `ringcentral_subscription_id` at subscription creation — **NEW SINCE THE ORIGINAL**

From S-3c Part 2. Tenant resolution on the inbound webhook matches the
envelope's `subscriptionId` and `ownerId` against stored per-tenant RC
identity. `ownerId` identifies the **extension that owns the subscription**, not
the subscription — a tenant with multiple extensions, or one that re-authorizes,
can drift off it. `ringcentral_subscription_id` is written by nothing today.

Envelope field names verified against RingCentral's published notification
structure (Account Telephony Sessions Event), not inferred from what the
handler happened to parse.

### One `redirect_uri`, derived in one place — **NEW SINCE THE ORIGINAL**

The callback's non-production `redirect_uri` is
`{FRONTEND_URL}/settings/call-intelligence` — a frontend page, not the callback
endpoint. Only the production branch points at the API. The token exchange's
`redirect_uri` must equal the one used in the authorize request, so the arc must
derive both from a single helper. S-3c deliberately did **not** bind
`redirect_uri` in nonce validation for exactly this reason: binding to a
presently-wrong value would have coupled that fix to a defect it does not own.

---

## 6. Subscription state: not determinable from here, and why

RC was queried read-only with production credentials.

- `client_credentials` → **`OAU-270`** (partner-level grant)
- `password` → **`OAU-251` "Unauthorized for this grant type"**

These are structured RC errors rather than transport failures, so the
credentials are real and the app is known to RC — and the app is authorized only
for `authorization_code`. Listing subscriptions needs an access token; that
token needs a flow with no initiator.

**MEASURED:** 0 rows in `ringcentral_call_log`, ever, across four tenants. No
tenant holds the token key.

**INFERRED, not proven:** this system has never created a subscription. A
subscription hand-created in RC's own console remains possible and is not
knowable from inside.

`RINGCENTRAL_SERVER_URL` is unset, so the default is **production**
RingCentral, not sandbox.

---

## 7. Framing the arc should carry

Three defects have now been found on this one integration:

1. A signature check that passed when unconfigured (S-3a).
2. A CSRF parameter repurposed as a tenant selector (S-3c Part 1) — a
   cross-tenant write on an unauthenticated public GET.
3. A resolver that returned the first match, with a non-production fallback to
   any active company (S-3c Part 2).

Plus a refresh token stored and never read, and an expiry stored in a form that
cannot answer whether it expired.

Each is individually explicable. Together they say **RingCentral was built as a
happy path, with every adversarial and decay case unwritten.** It was written to
work once, by someone who knew the intended sequence, and never against the case
where something arrives wrong or time passes.

**The arc should treat "what does this do when it fails" as a first-class
deliverable rather than a polish pass.**

### The September bar assumed a proven chain

The chain is proven downstream of a boundary nothing crosses. The honest
statement for planning: the call features are demo-able but **not sellable as
connected**.

---

## 8. Current state after S-3c

Both remaining entrance defects are fixed, and both fixes are *closed* rather
than open:

- The OAuth callback **rejects every request** — nothing mints nonces yet.
- `_resolve_tenant_id` **returns None for every webhook** — no tenant has RC
  identity stored.

Both are correct states, not gaps. They mean the arc starts from a refusing
entrance rather than a permissive one, and every piece it adds moves the system
from "rejects everything" toward "accepts exactly what it should" — which is the
direction that fails safe if the arc is interrupted.
