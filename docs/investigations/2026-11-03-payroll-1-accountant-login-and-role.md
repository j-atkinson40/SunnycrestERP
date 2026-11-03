# Payroll 1 — accountant login and payroll role: read-only findings

**Date:** 2026-11-03 · **Phase:** 1, read-only. No code written.
**Dispatch:** Sunnycrest's accountant signs in as a tenant user and sees only payroll.

> ⚠️ **TWO STOP CONDITIONS FIRED.** Both are reported below with evidence and
> neither was fixed. See §0.

---

## 0. STOP conditions — both triggered

### 0.1 Endpoints that return tenant data with no permission check

**946 of 1920 tenant endpoints (49%) have no per-user authorization at all** — they
carry `get_current_user` and nothing else. A further **117 (6%)** carry only
module/extension/feature gating, which asks *"is this module on for this company"* and
never *"may this user"*. Together **1063 of 1920 (55%) are reachable by any
authenticated tenant user.**

Of the 946, **886 contain no in-handler gate signature either** (60 do — they check
inside the body, like `completeness.py`). 886 is an upper bound on exposure (a handler
may delegate to a service that checks); 60 is a lower bound on checking.

**Proven, not inferred.** A role with zero permissions was created on `testco`, a user
put on it, and 20 read-only endpoints called. **11 returned 200 with tenant data:**

```
200  /api/v1/journal-entries/entries          200  /api/v1/companies
200  /api/v1/journal-entries/gl-accounts      200  /api/v1/companies/search
200  /api/v1/price-management/current-prices   200  /api/v1/fh/cases
200  /api/v1/price-management/versions         200  /api/v1/agents/alerts
200  /api/v1/agents/activity-log               200  /api/v1/agents/periods/locked
200  /api/v1/email/threads
403  /api/v1/customers   403  /api/v1/products   403  /api/v1/vendors   <- the control
```

The three 403s are the positive control: denial **is** possible on this path and the
probe can see it, so the 11 are a finding about those endpoints, not about the probe.
Verified beforehand that `get_user_permissions` returned 0 permissions and
`user_has_permission('users.view')` was `False`.

Top modules among the 886 (file → count): `company_entities.py` 44,
`widget_data.py` 28, `tenant_onboarding.py` 27, `programs.py` 25, `tax.py` 21,
`unified_import.py` 21, `statements.py` 20, `price_management.py` 19, `fh/cases.py` 19,
`moc_tenant.py` 19, `capture.py` 19, `email_inbox.py` 18, `reconciliation.py` 17,
`agents.py` 16, `journal_entries.py` 12. Full list: `/tmp/unchecked.json` at
investigation time; regenerate with the classifier in §6.

### 0.2 One endpoint returns tenant data with NO authentication whatsoever

`GET /api/v1/settings/service-territories` — `app/api/routes/service_territory.py:27`

It depends on `get_current_company` (`app/api/company_resolver.py:30`) but **not** on
`get_current_user`. `get_current_company` resolves from `get_company_slug`
(`app/api/company_resolver.py:8`), which reads the **`X-Company-Slug` header** —
unauthenticated.

Proven with a live request, no `Authorization` header:

```
GET /api/v1/settings/service-territories   X-Company-Slug: sunnycrest  -> 200
GET  ... same, X-Company-Slug: testco                                  -> 200
     {'counties': [], 'total': 0, 'delivery_area_configured': False,
      'facility_state': 'NY'}                      <- another tenant's data
POST ... (same path, has get_current_user)                             -> 403  (control)
GET  ... no slug header                                                -> 404  (control)
```

It is the **only** such endpoint: of 4 tenant endpoints that resolve a company with no
auth dependency, the other three are `POST /auth/login`, `/auth/refresh`,
`/auth/register` (`app/api/routes/auth.py:49,82,37`), which must be unauthenticated.

**Not fixed, per the dispatch.**

### 0.3 Adjacent, outside the dispatch's STOP wording but worth one line

- `GET /api/v1/website-intelligence/debug-network` —
  `app/api/routes/website_intelligence.py:161`. Unauthenticated, takes a caller-supplied
  `url` and fetches it server-side. SSRF-shaped. Its own docstring calls it
  "Temporary endpoint". Not tenant data, so not §0.2.
- Three `GET` endpoints that sound like writes: `/companies/run-migration`
  (`company_entities.py:251`), `/companies/classify/run-bulk` (`:1416`),
  `/companies/classify/fix-role-flags` (`:1643`). Excluded from the probe for that
  reason; a mutating GET is its own finding.

### 0.4 Does this trip "needs changes to more than the permission layer"?

**No for the surfacing layers; yes for the endpoint layer.** Nav, the note/Monitor
fragments, the command bar, and the Vault hub all already consult the permission system
(§2). Nothing there needs rewriting. What needs work is 886 endpoint bodies — which is
still "the permission layer", but it is 886 sites, not a config change.

---

## 1. How tenant roles and permissions work today

### Models

| Thing | File:line | Shape |
|---|---|---|
| `Role` | `app/models/role.py:10` | per-company (`company_id` FK :20), `slug` :24, `is_system` :26, unique `(slug, company_id)` :13 |
| `RolePermission` | `app/models/role_permission.py:9` | `(role_id, permission_key)` unique :12; `permission_key` is a bare `String(100)` :24 — no FK to a catalog |
| `UserPermissionOverride` | `app/models/user_permission_override.py` | per-user grant **or** revoke |
| `PermissionCatalog` | `app/models/permission_catalog.py` | seeded display/metadata table |
| `User.role_id` | `app/models/user.py` | exactly one role per user |

### The permission vocabulary

`app/core/permissions.py:12` — `PERMISSION_CATEGORIES`, nine categories: `financials`,
`operations`, `production`, `crm`, `legacy`, `disinterment`, `knowledge_training`,
`settings`, `other`. **There is no `payroll` category or key today.**

### Where the check happens (backend)

`app/services/permission_service.py:31` `get_user_permissions`:

1. `role.is_system and role.slug == "admin"` → **wildcard**, returns
   `set(get_all_permission_keys())` (:43-46). *A new permission key is therefore granted
   to admin automatically — no migration, no backfill.*
2. else role's `RolePermission` rows (:58-64)
3. then per-user overrides: grants added, revokes discarded (:66-75)

`app/services/permission_service.py:83` `user_has_permission` is the same with an admin
short-circuit at :86-88.

Route-level enforcement, all in `app/api/deps.py`:
`require_admin` :113 · `require_permission(key)` :147 · `require_module` :200 ·
`require_extension` :223 · `require_console_access` :256 · `get_current_user` :27

### Where the check happens (frontend)

- `src/contexts/auth-context.tsx:49` `hasPermission = (key) => permissions.has(key)`;
  `isAdmin` :84
- `src/components/protected-route.tsx:29` consumes `hasPermission`/`hasModule`/`isAdmin`;
  redirects to `/unauthorized` :64,:71,:75
- `src/services/navigation-service.ts:750` `filterByPermission` — per-item
  `permission?: string` (:6), `adminOnly` (:10), **admins bypass** (:766)

### How the admin assigns a role

Already complete; no new endpoint needed.

| Action | Endpoint | Gate |
|---|---|---|
| create a role | `POST /api/v1/roles` | `require_permission("roles.create")` — `app/api/routes/roles.py:53` |
| set its permissions | `PUT /api/v1/roles/{id}/permissions` | `app/api/routes/roles.py:93` |
| put a user on it | `PATCH /api/v1/users/{user_id}` | `require_permission("users.edit")` — `app/api/routes/users.py:114` |
| per-user override | `PUT /api/v1/users/{user_id}/permissions` | `app/api/routes/users.py:167` |

`user_service._validate_role_id` (`app/services/user_service.py:94`) scopes the role to
the caller's company, so a role id from another tenant is rejected.

---

## 2. Can a role be limited to one area today?

**Partly.** The *surfacing* layers honour permissions; the *endpoint* layer mostly does
not. Taking each place the dispatch names:

| Surface | Permission-aware? | Evidence |
|---|---|---|
| **Nav** | **Yes** | `navigation-service.ts:750`; items carry `permission:`, e.g. `"ar.view"` :105, `"operations_board.view"` :112, `"safety.view"` :182 |
| **Routes (frontend)** | **Yes** | `protected-route.tsx:63-75` |
| **Monitor / note fragments** | **Yes** | `app/services/fragments/emission.py:111` gates on `user_has_permission`; `types.py:24` — *"Lacking the permission means the fragment DOES not exist"* |
| **Command bar / Opas search** | **Yes** | `app/services/command_bar/retrieval.py:169-172, 229-233` resolves permissions up front; `resolver.py:27` |
| **Vault hub** | **Partly** | `app/services/vault/hub_registry.py` — `crm` → `customers.view` (:136), `accounting` → `"admin"` (:184), but **`documents` (:116), `intelligence` (:150) and `notifications` (:167) are `required_permission=None`** → visible to every tenant user |
| **API endpoints** | **Mostly no** | §0.1 — 1063 of 1920 reachable by any authenticated tenant user |

So the answer to the dispatch's question is: permissions are **not** all-or-nothing per
tenant — the model is genuinely per-key and the UI respects it — but **hiding is all the
UI can do**, and the backend does not back it up on roughly half the surface.

---

## 3. How Opas is gated, and what a limited-reach Opas would take

**Today:** one boolean. `src/components/opas/OpasHost.tsx:226` takes
`const { isAdmin } = useAuth()`, and :2229 is the whole gate:

```tsx
// ⚠️ The sphere is admin-only for now. Not rendering is the whole gate: a hidden-but-
// mounted sphere would still answer keyboard and pointer events.
if (!isAdmin || !opas.canRender) return null
```

Mounted once at `src/App.tsx:519`. The keyboard effect is also `isAdmin`-guarded
(:575, :590), so a non-admin has no listener attached — the gate is real, not cosmetic.

**To let a non-admin open it with reach limited to one area**, three things, in order:

1. **Replace the boolean with a capability.** `isAdmin` → `hasPermission("opas.use")`
   (or `isAdmin || hasPermission(...)`). One line at :2229 plus the effect guards at
   :575/:590. Low risk; the gate shape is already "don't render".
2. **Bound what Opas can reach.** Its reach is the command bar's resolver, which is
   already permission-filtered (§2) — so an accountant with only `payroll.*` sees only
   payroll results **provided the payroll entities are registered with a
   `required_permission`**. The resolver's 8 searchable entity types
   (`command_bar/resolver.py`) are the surface to audit here; none is payroll today.
3. **Bound what Opas can *do*.** Opas writes through the capture endpoints —
   `app/api/routes/capture.py` contributes **19** of the 886 unchecked endpoints (§0.1).
   Opening Opas to a non-admin without gating those hands her order capture.

**Recommendation for this slice: leave Opas admin-only.** It is not required for "sees a
Payroll area", and item 3 is the §0.1 problem in miniature.

---

## 4. Two-step sign-in, and the audit log

**Two-step sign-in for tenant users: does not exist.** `POST /api/v1/auth/login`
(`app/api/routes/auth.py:49`) is a single call returning a token pair.

⚠️ The one grep hit for `2fa` was inside a UUID in a docstring
(`order_list/customer.py:4`, `...-32772fa49876`) — false presence from a substring match.
Searching the other forms (`multi-factor`, `second factor`, `verification code`,
`magic link`) returns only token-in-URL flows for **external** parties
(`calendar_actions.py`, `email_actions.py`, family portal) — not a tenant second factor.
Portal users have lockout and recovery (`app/services/portal/auth.py`), tenant users do
not.

**Audit log: exists, and is opt-in per call site.** `app/models/audit_log.py:10` —
`company_id`, `user_id`, `actor_type` (:33, `tenant_user` | `portal_user`), `action`,
`entity_type`, `entity_id`, `changes`, `ip_address`, `user_agent`, `created_at`.
`audit_service.log_action` (`app/services/audit_service.py:22`) uses `flush`, not
`commit`, so the row lands atomically with the business write (:34-36).

**91 call sites across 26 modules. There is no middleware** — `app/main.py` contains no
`log_action` reference, so an endpoint that does not call it is not audited. Login *is*
audited (`auth.py:63-76`, action `"login"`, entity `"session"`, with IP and user-agent).
`audit.view` exists as a permission key (`permissions.py`, `other` category).

**Consequence for this dispatch — measured, both directions:**

- ✅ **Handing her the role IS audited.** `PATCH /users/{user_id}` has no `log_action` in
  its own body, but `user_service.update_user` (`app/services/user_service.py:279`) puts
  `role_id` in its `new_data` snapshot (:325) and calls
  `audit_service.compute_changes` + `log_action(db, company_id, "updated", "user", ...)`
  at :328-333. So the grant lands as an `updated`/`user` row carrying the before and
  after `role_id` in `changes`.
- ⚠️ **CORRECTED 2026-11-03, AND THE ERROR IS MINE.** This entry read:

  > ❌ **Changing what the role may DO is NOT audited.** `app/api/routes/roles.py`
  > contains **zero** `log_action` calls (measured). So `POST /roles`,
  > `PATCH /roles/{id}` and `PUT /roles/{id}/permissions` leave no audit row.

  The measurement was right and the claim was wrong. `app/api/routes/roles.py` does
  have zero — but `app/services/role_service.py` has **four**, and
  `set_role_permissions` already recorded old and new permission sets
  (`role_service.py:389`). I measured the ROUTE file and made a claim about role
  WRITES, which is a different population: the same constructed-scope error the canon
  names, committed inside an investigation about measurement. A grep of the route
  layer cannot see auditing that lives in the service it delegates to.

  ⚠️ **It was caught by needing the data, not by review** — the first draft of
  `tests/test_role_writes_are_audited.py` added a second set of `log_action` calls at
  the route layer and found **two** `created` rows per create. Had the test only
  asserted "at least one row", the duplicate would have shipped and this entry would
  still read as true.

  **What was actually missing, and is now fixed in the service** (commit 3):
  - `delete_role` recorded only name and slug, not the permission set it held — and
    after a delete there is nothing left to read;
  - a permission change and a rename both logged action `"updated"`, so the one change
    that moves a security boundary was indistinguishable in the list; it is now
    `"permissions_changed"`;
  - `limited_to_areas` (r221) was recorded nowhere, and for an area-limited role that
    field is more decisive than the permission list.

That asymmetry matters for a payroll role specifically, because the role's permission set
is the whole security boundary being claimed. Adding one `log_action` to
`set_role_permissions` is a two-line change and is the cheapest part of this slice —
noted, not done, as this phase writes no code.

---

## 5. Proposed design — the smallest thing that works

### The shape

One new permission key, one new system role, no new endpoint, **no migration.**

```
payroll.view     she may open the Payroll area and read its reports
payroll.approve  she may approve a week   (reserved now, used in slice 2)
```

### Files to change

| # | File | Change |
|---|---|---|
| 1 | `app/core/permissions.py:12` | add a `"payroll"` category to `PERMISSION_CATEGORIES` with `"payroll": ["view", "approve"]` |
| 2 | `app/core/permissions.py:169` | two `PERMISSION_DISPLAY_NAMES` entries |
| 3 | `app/core/permissions.py:482` | `ROLE_DEFAULTS["payroll"] = ["payroll.view", "payroll.approve", "dashboard.view"]` |
| 4 | `app/services/role_service.py:51` | one `_SYSTEM_ROLES` entry: name `"Payroll"`, slug `"payroll"` |
| 5 | `app/api/routes/payroll_reports.py:44` | **replace the role-slug gate with `require_permission`** — see the conflict below |
| 6 | `frontend/src/services/navigation-service.ts` | one nav item, `permission: "payroll.view"` |
| 7 | `frontend/src/pages/payroll/payroll-home.tsx` | new — the empty shell page |
| 8 | `frontend/src/App.tsx` | register the route behind `ProtectedRoute permission="payroll.view"` |

### Migration: none

- `payroll.view` becomes real the moment it is in `PERMISSION_CATEGORIES` —
  `permission_service.user_has_permission` compares strings against
  `RolePermission.permission_key`, a bare `String(100)` with no FK
  (`role_permission.py:24`).
- Admin gets it free: the wildcard is `set(get_all_permission_keys())`
  (`permission_service.py:43`).
- `permission_catalog` rows come from `seed_permission_catalog`
  (`permission_service.py:441`), idempotent, skip-if-exists.
- The role row comes from `seed_default_roles` (`role_service.py:135`), idempotent
  per company, already invoked by `scripts/seed_sunnycrest.py:109` — which is
  ensure-only and preserve-aware.

⚠️ `seed_default_roles` **skips a role that already exists and does not update its
permissions** (`role_service.py:144-156`). Fine for a new slug; it means a later change
to the payroll role's defaults will not reach Sunnycrest without an explicit grant.

### ⚠️ A conflict I introduced last session, and it blocks this

`app/api/routes/payroll_reports.py:27` imports `ACCOUNTING_ROLES` from
`completeness.py:113`, which is `("admin", "accountant")`, and `_require_payroll_role`
(:44) rejects anything else. **A user on a new `payroll` role would be refused by the
very endpoints this dispatch is building toward** — she holds `payroll.view` but her
slug is `payroll`, not `accountant`.

Gating by role slug was the right call when the only candidates were admin and
accountant; it is the wrong primitive the moment a third role exists. Item 5 above
changes those 7 call sites to `Depends(require_permission("payroll.view"))`, which also
makes the endpoints honour per-user overrides for free.

The existing `accountant` role must keep access, so it also gets `payroll.view` in
`ACCOUNTANT_DEFAULT_PERMISSIONS` (`permissions.py:244`) — and because
`seed_default_roles` will not update an existing role, Sunnycrest's accountant row needs
the grant applied explicitly, via `PUT /roles/{id}/permissions` or a one-off.

### What this design does NOT deliver

Honesty about the gap, because the dispatch's ruling is *"a limited user must be denied
on the backend, not only hidden in the UI"*:

The design denies her **payroll** correctly and hides everything else from nav, the
note, the command bar and Vault. It does **not** deny her the 1063 endpoints in §0.1.
With no nav entry she has no way to *click* to them, but a token and a URL reach them.
**On the dispatch's own ruling, this slice cannot be called complete until that is
addressed** — which is why §0.1 is filed as a STOP rather than a footnote.

Two options for James:

- **(a) Ship the area, accept the gap, schedule it.** Fastest to a working login. The
  gap is pre-existing and equally true of every non-admin role shipping today
  (`driver`, `production`, `dispatcher`, `office`) — she is not newly exposed; she is
  exposed the same way they already are.
- **(b) Close the gap for the sensitive modules first.** Not all 886. The financially
  and PII-sensitive subset is **71 directly-callable GETs** (§6) — `journal_entries`,
  `price_management`, `statements`, `tax`, `reconciliation`, `company_entities`,
  `fh/cases`, `agents`, `email_inbox`. Default-deny on those routers is a bounded
  change with a countable denominator.

My recommendation is **(b) scoped to those routers**, then (a) for the rest, because a
payroll-only user is the first role whose whole point is that she sees *one* area — she
is the first user for whom the gap is a promise broken rather than a latent risk.

---

## 6. Reproducing the measurements

The route classifier walks FastAPI's `Dependant` tree rather than grepping for
`Depends(...)`, because a grep cannot see a dependency attached at `include_router()`
level or inherited through a nested router — which is exactly the population in
question. Positive controls used: `/api/v1/users` must resolve to
`PERMISSION:users.view`, and `/api/v1/completeness/review` must resolve to
only-`get_current_user` (it gates inside the handler).

Final reconciled counts, **1920 (path, method) tenant endpoints**:

| Bucket | Count | % |
|---|---|---|
| per-USER check (admin or permission) | 792 | 41% |
| authenticated tenant user, no per-user check | 946 | 49% |
| per-TENANT check only (module/extension/feature) | 117 | 6% |
| no auth dependency at all | 50 | 2% |
| other realm (platform/portal/console/api-key) | 15 | 0% |

⚠️ An earlier pass reported 1063 for the second row. That pass's bucketing never tested
for module gating, so module-only routes fell into it. 946 + 117 = 1063 reconciles the
two; the number to quote for "no per-user gate" is **1063**, and for "nothing but a
login" is **946**.
