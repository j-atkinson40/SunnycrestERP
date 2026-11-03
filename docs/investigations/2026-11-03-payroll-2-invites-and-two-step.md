# Payroll 2 — tenant invites and two-step sign-in: read-only findings

**Date:** 2026-11-03 · **Phase:** 1, read-only. No code written.
**Goal:** no tenant password passes through a request body or a session, and any user
holding a payroll permission must use two-step sign-in.

> **The STOP condition did NOT fire.** Two-step can be enforced on every token path
> inside the auth layer — but only by guarding **use** rather than **issuance**. See §2.3.

---

## 0. The headline: who gets asked to enrol

Measured read-only on **production**, using the real `get_user_permissions` rather than a
SQL reimplementation of the admin wildcard — that wildcard is the whole reason the number
is what it is, and a second implementation of it would drift.

**18 users on production, all active. 5 would be required to enrol:**

| tenant | role | perms | why | user |
|---|---|---|---|---|
| sunnycrest | admin | 207 | admin wildcard | **jim.atkinson@sunnycrest.com** |
| hopkins-fh | admin | 207 | admin wildcard | admin@hopkinsfh.example.com |
| st-marys | admin | 207 | admin wildcard | admin@stmarys.example.com |
| testco | admin | 207 | admin wildcard | admin@testco.com |
| testco | accountant | 45 | explicit `role_permissions` rows | accountant@testco.com |

**13 would be optional:** hopkins-fh director ×2, hopkins-fh office ×1, testco dispatcher
×1, testco driver ×5, testco office_staff ×2, testco production ×2.

Three observations that matter more than the count:

- **James is on the list, and that is correct.** `get_user_permissions` returns
  `set(get_all_permission_keys())` for the system admin role
  (`app/services/permission_service.py:43-46`), so every admin holds `payroll.view` the
  moment the key exists. Four of the five are admins by wildcard; only one holds payroll
  by explicit grant.
- **Of the five, only ONE is a real human on a real tenant** — James. The other three
  admins are the synthetic demo tenants (`hopkins-fh`, `st-marys`, `testco`) and the
  accountant is testco's seeded fixture. So the actual day-one enrolment burden is James,
  plus Sunnycrest's accountant once her account exists.
- **Sunnycrest has no accountant user yet.** She will be the sixth. If she is created
  before two-step ships, she is created into a state where she is *required* to enrol and
  cannot — which is why the enrolment grace path in §2.4 is not optional.

⚠️ **AND THE LIST GROWS BY ITSELF.** Any permission key beginning `payroll.` extends this
set to every admin at every tenant, automatically. That is the right behaviour and it
means the enrol population is a function of the permission catalogue, not a list anyone
maintains.

---

## 1. The portal invite flow, and what is reusable

### Model — `app/models/portal_user.py`

| field | line | note |
|---|---|---|
| `hashed_password` | :71 | **nullable** — an invited user exists before any password does. This is the field that makes invite-first possible. |
| `invite_token` | :98 | `String(128)`, nullable |
| `invite_token_expires_at` | :99 | |
| `recovery_token` | :103 | |
| `recovery_token_expires_at` | :106 | |
| partial unique on `invite_token` | :50-53 | `WHERE invite_token IS NOT NULL` |
| partial unique on `recovery_token` | :56-59 | same shape |

### Flow — `app/services/portal/auth.py`, `app/services/portal/user_service.py`

- `invite_portal_user` (`user_service.py:164`) mints `secrets.token_urlsafe(32)`, TTL via
  `invite_ttl_hours`, returns the plaintext once to the caller.
- `issue_recovery_token` (`auth.py:268`) — **1 hour**, single-use.
- `consume_recovery_token` (`auth.py:283`) — validates existence, expiry and tenant match,
  then delegates to `set_portal_password`.
- `set_portal_password` (`auth.py:253`) — hashes, and **clears both token pairs plus the
  lockout counters** (:259-263). That clearing is the single-use enforcement.
- `validate_password_strength` (`auth.py:243`).
- Email: `delivery_service.send_email_with_template` with managed D-7 templates —
  `email.portal_invite` (`portal_admin.py:163`) and `email.portal_password_recovery`
  (`portal_admin.py:201`), seeded by r43.

### Reusable as-is
The **shape** is right and should be copied wholesale: nullable password, a
`secrets.token_urlsafe(32)` token with an expiry, partial-unique index, clear-on-use, and
the managed-template email path. None of it needs inventing.

### Two things NOT to carry over

⚠️ **1. The tokens are stored in PLAINTEXT.** `issue_recovery_token` sets
`user.recovery_token = token` (`auth.py:274`) — the same value that goes in the email. So
anyone who can read the table can use any outstanding invite or reset. For portal users
that is a pre-existing weakness; for tenant users it would be a *new* one, and it
contradicts this dispatch's own ruling that recovery codes are stored hashed. **Tenant
invite tokens should be stored as a hash**, with the plaintext existing only in the email.

⚠️ **2. `portal_users.invite_token` IS NEVER WRITTEN.** Measured: the only assignments
anywhere are `invite_token = None` in `set_portal_password` (`auth.py:261`). The invite
flow puts its token in **`recovery_token`** instead (`user_service.py:182`), and the code
says so:

> *"invite and recovery still share the same token column (reuse recovery_token for the
> first-password-set flow). The email template differs … but the token plumbing is one
> field. Consolidation into a single 'pending_token' is deferred to post-arc polish."*

So the `invite_token` column and its partial unique index are machinery behind an
entrance nothing crosses. It is a **declared** deferral, not a surprise — but the tenant
version should pick one field and mean it, rather than inheriting a column that looks
load-bearing and is not.

### Password-in-body: every caller

The ruling keeps this available only where tests or seeds need it. Callers of the
password-taking paths:

Every call site, verified by line:

| file:line | function | reached by |
|---|---|---|
| `app/services/user_service.py:212` | `create_user` | `POST /api/v1/users` (`users.create`) |
| `app/services/user_service.py:493` | `reset_user_password` (def `:484`) | `POST /api/v1/users/{id}/reset-password` |
| `app/services/auth_service.py:56` | `register_company` (def `:24`) | `POST /api/v1/companies/register` — first-admin bootstrap |
| `app/services/auth_service.py:159` | `register_user` (def `:124`) | `POST /api/v1/auth/register` |
| `app/services/auth_service.py:369` | `change_password` | `POST /api/v1/auth/change-password` — her own, correct as-is |
| `app/api/routes/platform_modules.py:295` | platform tenant creation | `data.admin_password` |
| `scripts/seed_staging.py:437-439` | 7 testco users, literal passwords | canonical seed |

Plus `scripts/seed_fh_demo.py` and `scripts/seed_sunnycrest.py` (which generates and
prints once — the one that must never run in a session).

⚠️ **SIX callers, not five, and `register_user` was the one I nearly missed.** It is a
distinct path from `register_company`: the first takes a company registration, the second
adds a user to an existing company. A sweep that found only `register_company` would have
left a live password-in-body endpoint behind.

**Recommendation:** leave all of them, add the invite path alongside, and make the admin
UI use invite only. `change_password` is not in scope at all — a user setting her own
password is the thing invites exist to enable. Removing the parameter from the others
would break six callers including three seeds, and CLAUDE.md §11 is explicit that removal
is the LAST step: enforce direction, fill the callers, then remove.

---

## 2. Tenant login, token issuance, and where a second step sits

### 2.1 Credential paths — there are two, not one

`auth_service.login_user` (`auth_service.py:201`) handles both:

- **email + password** (`:205-215`) — office/management track.
- **username + PIN** (`:218-231`) — production/delivery track, `verify_pin`.

A second step that only wraps the email branch leaves the PIN branch open. Today no
PIN user holds a payroll permission (the 5 required are 4 admins + 1 accountant, all
email users), but the requirement follows the permission, so a PIN user granted
`payroll.view` tomorrow must be covered.

### 2.2 Every path that mints a tenant token — four

| # | path | file:line | credential |
|---|---|---|---|
| 1 | login, normal | `auth_service.py:312-313` | password or PIN |
| 2 | login, production/delivery (shorter TTL) | `auth_service.py:305-308` | PIN |
| 3 | **refresh** | `auth_service.py:354-355` | refresh token only — **no credential** |
| 4 | **impersonation** | `admin/impersonation_service.py:65` | platform-admin authorization |

Other realms, out of tenant scope but adjacent: `platform_auth_service.py:43,66`
(platform realm) and `portal/auth.py:203,220` (portal realm).

⚠️ **Two of the four are the dangerous ones, and neither is a login:**

- **Refresh** issues a full access token on a refresh token alone. Anyone holding a
  refresh token minted *before* two-step was required could keep minting access tokens
  indefinitely, never passing a second step.
- **Impersonation** mints a tenant-realm token with a raw `jwt.encode`
  (`impersonation_service.py:65`), **bypassing `create_access_token` entirely**. A guard
  added inside `create_access_token` would not see it.

### 2.3 Therefore: guard USE, not ISSUANCE

Enforcing at the four mint sites is four edits, and a fifth path added later escapes
silently — which is exactly how `impersonation_service` came to bypass
`create_access_token`.

**Guard verification instead.** Every tenant request passes through
`get_current_user` (`app/api/deps.py:27`). Let the token carry a claim when the second
step passed, and have `get_current_user` refuse a token that lacks it for a user who
requires it:

```
token claim        mfa: true            set only after the second step passes
check (one place)  app/api/deps.py      if requires_two_step(user) and not claim -> 401
```

This covers all four paths at once, including impersonation's raw `jwt.encode`, and
covers any future path by construction — a new mint site produces a token that simply
cannot be used by a payroll-holding user. It is the same move as the area guard: one
central check over a surface too wide to edit site-by-site.

**So the STOP condition does not fire.** The change lives in `app/core/security.py`
(the claim), `app/api/deps.py` (the check), `app/services/auth_service.py` (the step), plus
new model/migration for the secret and recovery codes. Nothing in nav, Monitor, the
routers, or the 1063 endpoints.

### 2.4 Two consequences that need rulings

⚠️ **(a) An enrolment grace path is mandatory, or the five lock themselves out.** A user
who *requires* two-step and has not yet enrolled holds a token with no `mfa` claim —
which the guard refuses. She must be able to reach the enrolment endpoints with exactly
that token. This is the area guard's common-set problem again, and the same answer: a
short explicit allowlist (`/auth/me`, the enrolment endpoints, `/auth/change-password`,
logout) reachable pre-MFA, and nothing else.

⚠️ **(b) Impersonation needs a decision.** With use-side enforcement, a platform admin
impersonating a payroll-holding user gets a token with no `mfa` claim and is refused —
which breaks support access to exactly the tenant that matters. The options:
  1. **Refuse it** (strictest): support cannot impersonate payroll users at all.
  2. **Let the platform admin's own second step stand in** — but the platform realm has
     no two-step either, so this is a promise with nothing behind it today.
  3. **Mark impersonation tokens as MFA-satisfied, audited** — honest and explicit, and
     it writes the bypass down instead of leaving it implicit.

**Recommend (3)**, with the marker recorded on the existing
`AdminImpersonationSession` row so the bypass is auditable rather than invisible.

---

## 3. Method: TOTP or emailed code

| | authenticator app (TOTP) | emailed code |
|---|---|---|
| new dependency | `pyotp` (pure Python, small). No `qrcode` needed — serve the `otpauth://` URI and let the browser render it. | none |
| delivery risk | none, works offline | a code that does not arrive is a locked-out accountant on payroll day |
| independent of email | **yes** | **no** |
| setup friction | scan or type a secret once | nothing to set up |

**Recommendation: TOTP.** The decisive argument is not convenience, it is channel
independence: **the password-reset link and an emailed code would arrive in the same
inbox.** Whoever controls her email could reset the password *and* collect the second
factor, which makes the second factor decorative. TOTP is the only option here that is
actually a second *factor* rather than a second message.

Two secondary points: there is no deliverability failure mode, and `pyotp` adds no
native build step.

⚠️ **A CANON CITATION I DROPPED BECAUSE IT DOES NOT VERIFY.** CLAUDE.md §13 lists
*"Accountant invitation email — `accounting_connection.py:304` has a TODO; email is not
sent"*, which I was about to cite as evidence that email delivery is unreliable here.
Checked: that file has **no TODO at all**, and line 304 is
`company.set_setting("accounting_accountant_email", body.email)`. Either it was fixed or
the line moved, and the entry was not updated with it. The TOTP recommendation does not
rest on it — the channel-independence argument stands on its own — but the §13 entry is
stale and is flagged for an Opus session rather than edited here (James authorised only
the CI-last-passed correction).

### Recovery — what happens when she loses her phone

Per the ruling, and in order of use:

1. **Recovery codes.** 10 single-use codes shown **once** at enrolment, stored **hashed**
   (same discipline as passwords; `hash_password` already exists). Each consumed on use.
2. **Admin reset.** An admin clears a user's two-step enrolment; she re-enrols on next
   sign-in. Audited — and this is the one that needs care, because it is a
   privilege-escalation path: an admin who can clear two-step can clear their own.
   Recommend the audit row records actor and subject separately, and that clearing
   **your own** enrolment is refused so it always takes a second person.
3. **Lockout, deliberately not solved by email.** If she has neither phone nor codes, an
   admin resets it. No emailed bypass, because that reintroduces the single-channel
   weakness TOTP was chosen to avoid.

---

## 4. Where "holds a payroll permission" is evaluated

One function, one place:

- `app/services/permission_service.py:31` `get_user_permissions(user, db) -> set[str]`
  — role rows plus per-user overrides, with the admin wildcard at `:43-46`.
- `app/services/permission_service.py:83` `user_has_permission(user, db, key)` — the same
  with a short-circuit.

So the predicate is:

```python
def requires_two_step(user, db) -> bool:
    return any(p.startswith("payroll.") for p in get_user_permissions(user, db))
```

⚠️ **PREFIX MATCH ON THE PERMISSION, NOT A ROLE LIST.** This is the point of the ruling:
`payroll.timesheets.view` added next year extends the requirement to everyone holding it
with no code change, and no `("admin", "accountant", "payroll")` tuple to drift — which
is precisely the mistake the payroll endpoints made with `ACCOUNTING_ROLES` and that
Payroll 1 had to undo.

It also means the per-user override mechanism works: granting one person `payroll.view`
makes two-step required for her alone.

---

## 5. Files I would change

| # | file | change |
|---|---|---|
| 1 | `alembic/versions/r225_*.py` | `user_two_step` table or columns on `users`: `totp_secret` (**encrypted at rest**), `totp_enrolled_at`, `two_step_required_ack_at`; `user_recovery_codes` (`user_id`, `code_hash`, `used_at`) |
| 2 | `app/models/user.py` / new `app/models/user_two_step.py` | the model |
| 3 | `app/core/two_step.py` *(new)* | TOTP verify, code generation, hashing, the `requires_two_step` predicate |
| 4 | `app/core/security.py:72` | carry the `mfa` claim in `create_access_token` |
| 5 | `app/api/deps.py:27` | **the one enforcement point** + the pre-MFA allowlist |
| 6 | `app/services/auth_service.py:201,312,354` | the second step in login; refresh must preserve/deny the claim |
| 7 | `app/api/routes/auth.py` | `POST /auth/two-step/{begin,verify,enrol}`, recovery-code consume |
| 8 | `app/services/user_service.py` | `invite_user` (no password in body) + hashed invite token |
| 9 | `app/api/routes/users.py` | `POST /users/invite`, `POST /users/{id}/two-step/reset` (audited) |
| 10 | `alembic/versions/r226_*.py` | seed `email.tenant_invite` managed template |
| 11 | `app/services/admin/impersonation_service.py:65` | per ruling (b) |
| 12 | frontend | invite-accept page, enrolment page, two-step login step, admin reset control |
| 13 | `requirements.txt` | `pyotp` |

**Not touched:** nav, Monitor, the command bar, the area guard, the 1063 endpoints, the
payroll data switch (stays admin-only and off).

---

## 6. Method notes

Token paths were enumerated by grepping for `create_access_token` / `create_refresh_token`
/ `jwt.encode` across `app/` and `scripts/` — not by looking for "login", which would have
missed both dangerous paths. The absence of SSO/SAML/passwordless was established by
enumerating the app's own route table and by a word-boundary search (`\bsso\b` matches
nothing; the five unbounded `sso` hits are substrings of other words).

The enrol list was computed with the production `get_user_permissions` in a
`SET TRANSACTION READ ONLY` session, under `railway run` in the production environment, so
no credential passed through the session.
