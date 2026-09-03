# S-3a — does a RingCentral entrance exist?

> ## ⚠️ RECONSTRUCTED FROM CONTEXT AFTER /tmp LOSS — 2026-09-03
>
> The original lived at `/tmp/s3a_entrance_findings.md` (219 lines, written
> 2026-09-03). `/tmp` was wiped at that day's 11:47 boot.
>
> This is the best-preserved of the four lost deliverables, because the STATE.md
> S-3a entry had captured most of its conclusions **with their derivations** —
> which is the half that usually goes missing. §7 lists what did not survive.
>
> Claims below are restated at the confidence held when written unless marked
> **UNCERTAIN** or **LOST**.

---

## 1. The question

Existence-first, per CLAUDE.md §12: *what RingCentral entrance exists, if any,
by any mechanism?* Not "confirm there is no authorize endpoint" — absence is a
finding to be established, never a premise to be confirmed.

---

## 2. The token WRITER exists

`GET /api/v1/integrations/ringcentral/oauth/callback` (`ringcentral.py`,
`oauth_callback`) exchanges an authorization code and writes:

- `ringcentral_access_token` — `encrypt_secret` at the write site
- `ringcentral_refresh_token` — `encrypt_secret` at the write site
- `ringcentral_token_expires_in`
- `ringcentral_owner_id`
- `ringcentral_connected`

**Derivation:** found by enumerating **all 80 `set_setting(` call sites**,
including the five that write a constructed key — *not* by grepping for the key
string. A key-string grep would have missed any constructed-key writer, and the
question was "what writes RC settings by any mechanism."

**This settled Sales & Orders census open question #8 by direct observation at
the writer:** RC tokens are encrypted from birth. `decrypt_secret` at use in the
after-call pipeline. Zero rows ever written plaintext. Observed at the write
site, not inferred from a neighbouring module that happened to encrypt.

---

## 3. ⚠️ The initiating end does not exist

Three independent derivations, each by a different method:

1. **No `oauth/authorize` route** — established by enumerating the app's route
   table, not by grepping path strings. (A path-string grep is a constructed
   name and its null would have been uninformative — see the absence audit.)
2. **No RC authorize URL anywhere in `frontend/src`.**
3. **The "Connect RingCentral" button has no `onClick` and no `href`** —
   `call-intelligence-settings.tsx:92-95`. It renders and does nothing.

**A tenant cannot be connected to RingCentral by any means present in the
product.**

---

## 4. ⚠️ The connection indicator names the wrong thing

The same settings page's "Phone system connected" was driven by `connected`
from `useCall()`, which is `call-context.tsx:140` — **the SSE stream's state**,
not RingCentral's. A tenant with no RC connection read as connected whenever the
browser's event stream was open.

This mattered more than the gap it concealed: a missing OAuth flow is
discoverable the moment someone clicks the button, but an indicator reporting
green for a different proposition guarantees nobody clicks.

Fixed in S-3b (`f2b59df7`).

---

## 5. ⚠️ `ringcentral_refresh_token` is written and never read

Exactly two occurrences in `app/`, both the write. No `grant_type=refresh_token`
for RC anywhere. Both siblings have one — `calendar/oauth_service.py:343,362`
and `email/oauth_service.py:313`.

`ringcentral_token_expires_in` is stored and never consulted.

---

## 6. Subscription state: NOT determinable from here, and why

RC was queried **read-only** with production credentials.

| Grant attempted | RC response |
|---|---|
| `client_credentials` | `OAU-270` (partner-level grant) |
| `password` | `OAU-251` "Unauthorized for this grant type" |

These are **structured RC errors, not transport failures** — which is what makes
them informative. The credentials are real and the app is known to RC, and the
app is authorized only for `authorization_code`. Listing subscriptions requires
an access token; that token requires a flow with no initiator.

**MEASURED:** 0 rows in `ringcentral_call_log`, ever, across four tenants. No
tenant holds the token key.

**INFERRED, not proven:** this system has never created a subscription. A
subscription hand-created in RC's own console remains possible and is not
knowable from inside. The distinction is preserved deliberately.

`RINGCENTRAL_SERVER_URL` is unset → the default is **production** RingCentral,
not sandbox.

---

## 7. What is LOST

Claims or material known to have been in the original that cannot be honestly
restated:

- **The full route-table enumeration output.** The conclusion ("no authorize
  route") survives; the dump that established it does not. Re-derivable cheaply.
- **The per-tenant breakdown of the zero-row measurement.** "0 rows across four
  tenants" survives; which four tenants, and the query used, do not.
- **The 80 `set_setting(` call-site enumeration.** The count and the conclusion
  survive; the list — including *which* five write a constructed key — does not.
  This is the most costly loss in this file: that list is reusable evidence for
  any future settings-surface question, and re-deriving it is a full pass.
- **Timestamps and exact request/response bodies of the two RC probes.** The
  error codes survive; the raw exchanges do not.
- **UNCERTAIN:** the original may have enumerated additional RC-adjacent
  surfaces (the call-log page, the briefing integration, the workflow block).
  I recall the file being broader than its conclusions; I cannot restate what
  else it covered.

---

## 8. The pattern this was the fourth instance of

**Complete machinery behind an unprovisioned entrance.** Four instances, three
areas, four discovery methods, **none found by a check**:

1. `post_invoice` — complete, never called.
2. `legacy_photo_pending` — readers, no writer that can set it True.
3. The RC chain — complete downstream of an unbuilt entrance.
4. `ringcentral_refresh_token` — written, never read.

This is queued for arc-close canon.
