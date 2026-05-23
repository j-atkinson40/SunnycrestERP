# Widget Builder — Auth Realm Mismatch

**Date:** 2026-05-26
**Type:** Read-only investigation
**Scope:** Operator-validation finding from staging after `WB-cycle-followup-1` (commit `537ebff`) shipped the Widget Builder rail entry. Clicking the rail entry routes to `/studio/widgets` (`WidgetListPage`) and to `/studio/widget-builder/:slug` (Widget Builder shell). Both surfaces fail to load data; Chrome devtools shows `GET /api/v1/widgets/composed-definitions` and `GET /api/v1/widget-definitions` returning **403** (operator-reported; see §3 for an honest treatment of whether 403 vs 401 vs 404 is the true status — the diagnosis converges on the same root cause across all three failure modes). Console log surfaces the catch-block string from `registerComposedWidgets.ts:181` — `"composed widgets unavailable in palette this session"`.
**Working HEAD:** `537ebff` (`WB-cycle-followup-1` rail entry activation).
**Constraint:** Zero production code changes. Zero test changes. Zero canon-doc changes beyond STATE.md. Investigation + STATE.md update only.

---

## 1. Context

The Widget Builder substrate (WB-1 through WB-8, May 21–24, 2026) shipped as a fully-end-to-end authoring stack — schema (`widget_definitions` table at migration `r105`/`r106`), runtime (composed-widget registration bridge), canvas authoring, per-atom inspectors, composition validation, list view, canvas preview, saved-view binding picker, button action dispatch, and variant authoring. Per the WB-8 build report (commit `5df25a1`), the cycle was "structurally complete — end-to-end operator-ready stack."

`WB-cycle-followup-1` (commit `537ebff`, 2026-05-25) added the Studio rail entry consuming F-1.1's `overrideHref` + `newAffordanceId` primitives verbatim. Per the build report: "operator-observable verification (post-deploy): sidebar at admin.getbridgeable.com shows Widget Builder entry at index 5 with Wand2 icon + dismissible 'New' badge; click routes to `/studio/widgets` list-view; WB cycle substrate becomes operator-discoverable end-to-end."

That post-deploy verification step is where the failure surfaced. The rail entry renders correctly. The route resolves. `WidgetListPage` mounts. But the data fetches issued by the page (and by the `registerComposedWidgetsFromApi()` boot adapter at app startup) fail in the network tab, and the operator sees an empty list view + a console warning.

**The hypothesis from the dispatch text** is that the Widget Builder substrate was authored under the tenant API tree (`get_current_user`-gated, `/api/v1/*` prefix) while the rail entry surfaces it inside Bridgeable Studio (admin tree, `admin.getbridgeable.com` host, `PlatformUser` JWT realm). The cross-realm boundary at `backend/app/api/deps.py:40-52` then rejects.

This investigation audits the substrate end-to-end to determine the precise root cause, scope the fix, and surface the canon class lesson without making any production change at this depth.

The investigation is bounded to ~3,000 words / ~30 minutes per the dispatch — narrower than WB sub-arc investigations because the audit converges quickly on a small set of fix options once the endpoint registration + frontend client mapping are in hand.

---

## 2. Area 1 — Endpoint Registration Audit (Backend)

**The Widget Builder substrate registers all of its endpoints exclusively under the tenant API tree at `/api/v1/*`.** Zero endpoints exist on the platform admin router (`/api/platform/*`).

### `/api/v1/widget-definitions/*` (router: `widget_definitions.router`)

Registered at `backend/app/api/v1.py:872-876` with prefix `/widget-definitions`. Source: `backend/app/api/routes/widget_definitions.py`. Five endpoints, all gated by `Depends(get_current_user)`:

| Endpoint | Method | Auth dependency | File:line |
|---|---|---|---|
| `POST ""` (create) | POST | `get_current_user` | `widget_definitions.py:80-83` |
| `GET ""` (list) | GET | `get_current_user` | `widget_definitions.py:110-114` |
| `GET "/{slug}"` (fetch) | GET | `get_current_user` | `widget_definitions.py:142-146` |
| `PUT "/{slug}/draft"` (save draft) | PUT | `get_current_user` | `widget_definitions.py:156-161` |
| `POST "/{slug}/publish"` (publish) | POST | `get_current_user` | `widget_definitions.py:184-187` |

`get_current_user` itself depends transitively on `get_current_company` (deps.py:29), which resolves a `Company` row from the `X-Company-Slug` header OR the host's first subdomain segment (`company_resolver.py:30-57`).

### `/api/v1/widgets/composed-definitions` (router: `widgets.router`)

Registered at `backend/app/api/v1.py:878-880` with prefix `/widgets`. Source: `backend/app/api/routes/widgets.py:14-55`.

| Endpoint | Method | Auth dependency | File:line |
|---|---|---|---|
| `GET "/composed-definitions"` | GET | `get_current_user` | `widgets.py:14-17` |

The endpoint's docstring (widgets.py:30-33) is candid about the auth gate's purpose: *"The bridge runs in tenant context (auth required); cross-tenant isolation isn't a concern here because widget definitions are platform-wide (no `company_id` column), but the auth gate keeps the endpoint behind login so unauthenticated probes can't inventory the platform."*

### Tenant scoping on the underlying data model

`backend/app/models/widget_definition.py:165-167` declares `tier_scope: Mapped[str]` (values: `"platform"` or `"vertical"`) but **no `company_id` or `tenant_id` column**. Tier-3 (per-tenant override) lives at the *placement* level via `focus_compositions.deltas`, not in the widget definition itself. The widget definition table is **platform-wide data** — every tenant sees the same composed widgets. The `tier_scope` field is purely a classification for which authoring surface owns the row, not a tenant isolation key.

### Implication

The data is platform-wide. The auth gate exists only as a "behind login" check. Both `get_current_user` (tenant realm) and `get_current_platform_user` (platform realm) would satisfy the underlying intent. The endpoint signature historically required `get_current_user` because the substrate was authored before the rail entry surface decision was locked. WB cycle assumed Widget Builder would be reached from a tenant Studio surface (e.g. `/visual-editor/widgets` under the v1 admin tree mounted off tenant hosts). WB-cycle-followup-1 surfaced it from `admin.getbridgeable.com` Studio — a host where no tenant company resolves and no tenant token is in scope.

### Platform admin router check

`grep -n "widget" backend/app/api/platform.py` returns zero matches. **Zero widget endpoints exist on the platform router.** This is the structural gap.

---

## 3. Area 2 — Frontend Fetch Path Audit

Three frontend call sites consume the Widget Builder backend, all routed through the **tenant `apiClient`** instance even though two of the three files live under `frontend/src/bridgeable-admin/`.

### Call sites

| File | Endpoint | Client instance | Token source |
|---|---|---|---|
| `frontend/src/lib/widget-builder/runtime/registerComposedWidgets.ts:35` | `GET /widgets/composed-definitions` (lines 163, 206) | tenant `apiClient` (`@/lib/api-client`) | `localStorage["access_token"]` |
| `frontend/src/bridgeable-admin/hooks/useWidgetList.ts:15` | `GET /widget-definitions` (line 45) | tenant `apiClient` | `localStorage["access_token"]` |
| `frontend/src/bridgeable-admin/services/widget-builder-service.ts:9` | `POST /widget-definitions`, `GET /widget-definitions/{slug}`, `PUT /widget-definitions/{slug}/draft`, `POST /widget-definitions/{slug}/publish` | tenant `apiClient` | `localStorage["access_token"]` |

`useWidgetAutoSave.ts:27` consumes `widgetBuilderService` (same path). `useCanvasPreviewData.ts:35` consumes `executeSavedView` from `frontend/src/services/saved-views-service.ts:13`, which is also tenant `apiClient` — meaning canvas preview's saved-view binding picker is on the same failure path.

### Tenant `apiClient` base-URL + token logic

`frontend/src/lib/api-client.ts:29-51` resolves the base URL per-request from `localStorage["bridgeable-admin-env"]` (the R-1.6.7 fix pattern). On `admin.getbridgeable.com` staging, the admin tree sets that key to `"staging"`, so the tenant `apiClient` correctly targets `https://sunnycresterp-staging.up.railway.app/api/v1`. **URL resolution is not the problem.**

The interceptor at `api-client.ts:62-76` reads `localStorage["access_token"]` and attaches it as `Authorization: Bearer ...`. Critically, it does **not** read the admin token at `localStorage["bridgeable-admin-token-staging"]` — those are separate storage keys with separate values written by separate code paths.

### Admin tree token storage

`frontend/src/bridgeable-admin/lib/admin-api.ts:13-46` declares `TOKEN_STORAGE_KEY = "bridgeable-admin-token"`, scoped per-environment as `"bridgeable-admin-token-staging"` or `"bridgeable-admin-token-production"`. Platform admin login (`adminLogin` at admin-api.ts:69-86) writes the platform JWT to that environment-scoped key, never to `access_token`. The two clients (`apiClient` tenant, `adminApi` platform) are deliberately disjoint per the structural separation documented in CLAUDE.md §4 ("Admin Platform Architecture") — `adminApi` targets `/api/platform/*`, `apiClient` targets `/api/v1/*`.

### What's actually in `localStorage["access_token"]` on `admin.getbridgeable.com`?

Three possibilities:

1. **Empty.** The operator visited only `admin.getbridgeable.com` in the current browser session, never a tenant subdomain, never the runtime-editor impersonation flow. The tenant `apiClient` sends the request without an `Authorization` header.
2. **Stale tenant token.** The operator previously logged into a tenant subdomain (`sunnycrest.getbridgeable.com` testing, or local dev with the `?slug=testco` query-param adoption). That token carries `realm="tenant"` and is structurally valid for the endpoint — but the tenant company resolver still needs a matching `X-Company-Slug` or subdomain, which on `admin.*` it would not find correctly (see §3 below).
3. **Impersonation token.** The operator used the runtime-editor flow (`TenantUserPicker.tsx:102`) or the legacy admin tenant-impersonation flows (`pages/platform/tenants.tsx:53`, `pages/admin/admin-tenant-list.tsx:247`, etc.). Those write a `realm="tenant"` impersonation token (per `app/services/admin/impersonation_service.py:52-59` and `app/core/security.py:104-120`) to `localStorage["access_token"]`.

Only case 3 yields a usable token. Cases 1 and 2 cascade to failure.

### Per-request `X-Company-Slug` header

`api-client.ts:70-73` attaches `X-Company-Slug` from `getCompanySlug()` (`@/lib/tenant`). On `admin.getbridgeable.com`, no slug has been stored via `?slug=...` query-param adoption, and the host-name-derived path returns nothing because `"admin"` isn't a tenant subdomain. So the header is absent. The backend `company_resolver.py:24` then falls back to `parts[0]` of the hostname — `"admin"` — and queries `Company.slug == "admin"`. No such company exists → `get_current_company` raises **404** at `company_resolver.py:51-55`.

---

## 4. Area 3 — 403 Root Cause Trace

The dispatch text reports the operator-observed status as **403**. Both candidate failure paths I can trace from the substrate yield **401** (cross-realm rejection on platform-token-presented-to-tenant-endpoint, deps.py:40-44) or **404** (company resolver fails to find a `"admin"` slug company, company_resolver.py:51-55). I do not find a 403-yielding path in `widget_definitions.py`, `widgets.py`, or `deps.py:get_current_user` for the described scenario.

Three honest interpretations:

1. **Operator misread the status.** The console log catch block fires on any axios rejection. 401 + redirect-to-login would not actually redirect on `admin.getbridgeable.com` because the redirect target `/login` resolves to the *tenant* login (per the tenant App tree route table at `frontend/src/App.tsx`), and the admin tree (`BridgeableAdminApp.tsx`) likely intercepts and renders its own catch-all instead — leaving the operator looking at the admin tree with a console error and a failed network request that they then read in devtools and reported as "403." Could be 401 in actuality. The investigation's root cause analysis does not depend on the precise status code.

2. **Operator's localStorage carries a stale tenant token that fails the `token_company_id != company.id` check.** Deps.py:61-65 raises 401 (not 403) when `token.company_id != resolved_company.id`, which would happen if the operator's stale token was issued for tenant X but the host-derived slug resolves to a different tenant (or to nothing). Still 401, not 403.

3. **Genuine 403 from elsewhere in the call stack.** Some middleware (CORS, rate-limit, request-size) might emit 403. I do not have direct evidence in the read-only audit.

**Resolution:** the root cause is the same regardless of exact status — **the Widget Builder backend endpoints are tenant-scoped (`/api/v1/*`, `get_current_user`, `get_current_company`); the rail entry surfaces them on a platform host (`admin.getbridgeable.com`) where neither realm nor company context resolves correctly.** The operator's "403" should be treated as "non-2xx from the backend, blocking the Widget Builder UI from operating." Whether it is 401 / 403 / 404 does not change the fix scope.

A useful clarifying step before fix dispatch would be a one-line operator request: "open Chrome devtools → Network → click the failing request → screenshot the Headers tab (request URL + response status + response body `detail` field if present) → paste." That would pin the exact status. Not blocking; the fix options cover all three failure modes uniformly.

---

## 5. Area 4 — WB-cycle-followup-1 Retrospective

The studio-nav investigation at `docs/investigations/2026-05-25-studio-nav-widget-builder.md` audited the rail substrate (Area 1), Focus Builder precedent (Area 2), Widget Builder route registration (Area 3), `WidgetListPage` substrate (Area 4), sidebar completeness (Area 5), and fix-scope options. It did **not** audit the end-to-end auth realm path from the admin Studio host to the backend endpoints.

The investigation's Area 3 verified: "routes registered today per WB-4a + WB-4b at `StudioShell.tsx:259-281` — `/studio/widget-builder/:slug` (editor), `/studio/widget-builder` (slug-optional create landing), `/studio/widgets` (list view via WB-4b rewire)." That confirms the **frontend routing** works. It did not check whether the backend endpoints those routes' page components fetch from are reachable from the host.

The build prompt for WB-cycle-followup-1 inherited the investigation's framing — substrate end-to-end operator-ready, discoverability is the only gap, fix is a rail entry consuming F-1.1 primitives verbatim. The build executed exactly that. The post-deploy verification claim "WB cycle substrate becomes operator-discoverable end-to-end" was correct for **discoverability**. It was not correct for **functionality** — the rail entry lights up, the click navigates, and the destination surface fails to load data.

### Honest gap finding

The investigation's Area 3 substrate-route audit verified frontend route registration without verifying backend endpoint reachability from the host. The Focus Builder precedent (F-1.1) wasn't an analogous test of the auth realm hypothesis because the Focus Builder shell at `/studio/builder/focuses` consumes the `focus-compositions` substrate, which **is** registered on `/api/platform/admin/visual-editor/compositions/*` with `get_current_platform_user` per the Phase 4.x focus-compositions arc (CLAUDE.md §4 "Focus Composition Layer (Admin Visual Editor — May 2026)"). Focus Builder works from `admin.*` because its backend is on the platform router. Widget Builder's backend is on the tenant router. The two builders are asymmetric in their backend-realm placement, and the rail-entry precedent did not surface this asymmetry because no one tested.

Class of bug: **investigation Areas verifying frontend mounting and route registration do not substitute for verifying that the page's data-fetching paths reach a backend the host's auth realm can satisfy.** Future builder-entry investigations should include an "auth-realm reachability" check — list the page's network calls, list their backend dependencies, confirm those dependencies are mounted on the router the host's realm consumes.

The class of bug is closely related to the WB-4b silent-rail-label-inheritance noted in the studio-nav investigation Area 10 — "route-target changes without companion navigation-entry updates produce silent operator-perception drift." This case is the dual: navigation-entry adds without companion backend-router check produce silent functional drift.

---

## 6. Area 5 — Fix Scope (Options A through D) + Lock

Four fix options. I lay them out, estimate LOC, lay out trade-offs, and lock.

### Option A — Add platform-realm mounts for existing endpoints

Mount the same `widget_definitions.router` + `widgets.router` (or new platform-realm wrapper routers) on the platform admin tree at `/api/platform/admin/visual-editor/widgets/*` with `get_current_platform_user` gating. Frontend switches the three call sites (`registerComposedWidgets.ts`, `useWidgetList.ts`, `widget-builder-service.ts`) to consume `adminApi` (`@/bridgeable-admin/lib/admin-api`) instead of tenant `apiClient`. Same SQL queries, same response shapes.

- **Backend LOC:** ~80-120. New route file at `backend/app/api/routes/admin/visual_editor_widgets.py` mirroring `widget_definitions.py` with `get_current_platform_user` swapped in; register on platform.py; thin or zero changes to underlying service layer at `backend/app/services/widget_definitions/`.
- **Frontend LOC:** ~30-60. Three import swaps (`@/lib/api-client` → `@/bridgeable-admin/lib/admin-api`); three URL prefix updates (`/widget-definitions` → `/api/platform/admin/visual-editor/widgets`, `/widgets/composed-definitions` → `/api/platform/admin/visual-editor/widgets/composed-definitions`). `registerComposedWidgets.ts` is the awkward case because it lives in the *shared* runtime library imported by both tenant and admin trees; needs a host-aware client picker or a separate boot path for admin contexts.
- **Tests:** ~60-100 LOC. Parametrize existing widget_definitions endpoint tests across both realms; new auth gate tests at the platform router.
- **Trade-off:** **Two router mounts for one set of business logic.** Risk of drift over time. Matches the precedent for focus-compositions / platform-themes / component-configurations — all of which exist exclusively on the platform router today and reach tenant render contexts via separate, lower-level resolution paths (read-only resolvers consumed by the tenant render layer). The Widget Builder substrate could follow that pattern.
- **Total:** ~170-280 LOC.

### Option B — Move endpoints to platform-realm only (breaking change for tenant render path)

Move `widget_definitions` + `widgets/composed-definitions` exclusively to `/api/platform/admin/visual-editor/widgets/*`. The tenant render path (Focus Builder palette, dashboard composed-widget rendering) currently calls `/api/v1/widgets/composed-definitions` from `registerComposedWidgets.ts` at app boot **inside the tenant App tree too** (`frontend/src/App.tsx` imports + invokes the boot adapter — verify before locking). If the boot adapter fires from both trees and now needs to call the platform endpoint from the tenant tree, the tenant tree needs a platform JWT, which it doesn't have. Cross-tree coupling explodes.

- **LOC:** smaller in isolation but cross-tree coupling makes it impractical without a full architectural pivot.
- **Trade-off:** **breaks tenant render of composed widgets**. Not viable without companion read-only tenant endpoint.
- **Rejected.**

### Option C — Dual-realm endpoint (accept both tenant + platform tokens via custom dependency)

A new dependency `get_current_actor_any_realm` that accepts either `get_current_user` or `get_current_platform_user`. Swap `widget_definitions.router` + the composed-definitions endpoint to use it. Single mount, dual realm.

- **Backend LOC:** ~40-60. New dependency function in `deps.py`; three router gate swaps.
- **Frontend LOC:** ~20-40. The admin tree's three call sites swap to a custom axios instance that sends whichever token is present (platform if on admin host, tenant otherwise) — or simpler, the admin tree keeps consuming `apiClient` BUT the tenant `apiClient` is extended to attach the platform token on admin hosts. The latter inverts the deliberate two-client separation from CLAUDE.md §4.
- **Trade-off:** **explicitly weakens the cross-realm boundary**. CLAUDE.md §4 calls cross-realm enforcement "Load-bearing security boundary"; opening a "dual-realm" backdoor on a subset of endpoints invites drift and confusion. The pattern would need a strong justification doc and a precedent — neither exists today.
- **Rejected.**

### Option D — Move Widget Builder's authoring surfaces fully into the tenant tree

Retire the `bridgeable-admin/components/widget-builder/*` + admin Studio rail entry; move the WidgetListPage + Widget Builder shell into the tenant App tree at `/visual-editor/widgets` (parallel to the existing v1 admin pages at `frontend/src/pages/visual-editor/*` that live in the tenant tree). The rail entry retires; tenant operators reach Widget Builder via their per-tenant Studio.

- **LOC:** ~200-400 across file moves + import updates + ProtectedRoute mounting + nav.
- **Trade-off:** **conflicts with the deliberate split that put Studio under `admin.*` for platform-tier authoring**. The whole Bridgeable Studio surface at `admin.getbridgeable.com/studio/*` was designed to be platform-team-authored content (per the Studio shell substrate at `docs/investigations/2026-05-13-studio-shell.md` + DECISIONS.md entries). Moving Widget Builder out of Studio contradicts that. Possibly correct long-term, but a large architectural pivot, not a fix.
- **Rejected for this fix scope.**

### LOCKED: Option A

Option A is the lock. Reasoning:

1. It matches the established precedent for every other Studio-authored substrate (themes, component configurations, focus compositions, workflow templates, document templates) — all on the platform admin router with `get_current_platform_user`.
2. It preserves the tenant render path. The existing `/api/v1/widgets/composed-definitions` stays so that the tenant App tree's boot-time `registerComposedWidgetsFromApi()` continues to register composed widgets for tenant Focus Builder palettes + dashboard rendering. Tenant authoring (via tenant render path) is read-only — no tenant operator authors composed widgets, only platform admins do, matching the `tier_scope="platform"` semantics. The tenant path stays read-only-shaped; the platform path adds full CRUD.
3. The backend service layer at `backend/app/services/widget_definitions/` is realm-agnostic — `create_widget_definition`, `save_draft`, `publish_draft`, `serialize_widget` all take `db` + payload, no `current_user`-derived scoping. Splitting the route layer is mechanical.
4. The frontend "shared runtime library" concern is real but bounded: `registerComposedWidgets.ts` is invoked from both trees but only **reads** the composed-definitions endpoint; the tenant tree keeps calling `/api/v1/widgets/composed-definitions` (no change), the admin tree's Widget Builder shell calls the new platform-realm endpoint for authoring. Two separate purposes; clean split.

**LOC estimate (locked):** ~170-280 production + ~60-100 test = ~230-380 total.

**Dispatch dependencies before locking the build:**

- Q-B1: confirm `registerComposedWidgets.ts` is imported from the tenant App tree boot path (`frontend/src/App.tsx`) AND not imported from the admin tree, OR vice versa. If imported from both, decide whether the admin tree should be calling its own new platform-realm endpoint for the registry-refresh-after-publish path. Likely yes — the admin Widget Builder shell's "Publish" should refresh composed widgets via the platform path it has auth for.
- Q-B2: confirm `useCanvasPreviewData`'s `executeSavedView` dependency — is the WB-5 canvas preview supposed to execute saved views against the platform admin's currently-selected tenant scope (impersonation context), or platform-default scope (no tenant)? This influences whether the WB-5 saved-view dependency also moves to platform realm or stays on the tenant realm with an impersonation token. Out of arc scope; flag for a follow-up.
- Q-B3: confirm the platform router prefix. Existing precedent is `/api/platform/admin/visual-editor/{themes,components,workflows,compositions,classes}/*`. Widget Builder fits as `/api/platform/admin/visual-editor/widgets/*`.

---

## 7. Area 6 — Studio Shell + Live Mode Interaction + Widget Tier Model

### Live mode interaction

Studio supports a "Live mode" pattern (per the Studio shell substrate investigation at `docs/investigations/2026-05-13-studio-shell.md`) where platform admins preview their authoring against a live tenant via the runtime-editor impersonation flow. The runtime editor at `TenantUserPicker.tsx:102` writes a tenant-realm impersonation token to `localStorage["access_token"]`. **When Live mode is engaged, the tenant `apiClient` works** — the operator has a tenant token, the X-Company-Slug header is set (via runtime editor's tenant selection), and `/api/v1/widget-definitions/*` resolves correctly.

The current failure mode is **Studio in its default (non-impersonating) state**. With Option A locked, the admin Studio authoring path consumes the new platform-realm endpoints regardless of impersonation state. Live mode preview (rendering inside an impersonated tenant) continues to consume the tenant render path (`/api/v1/widgets/composed-definitions`) via the impersonation token. The two paths coexist cleanly.

### Widget tier model

`widget_definitions.tier_scope` takes values `"platform"` or `"vertical"` (model: `widget_definition.py:165-167`, backfill: r105). Tier-3 (per-tenant override) lives at placement level via `focus_compositions.deltas`, not in the widget definition row.

**Implication for Option A:** widget definitions are platform-authored regardless of `tier_scope` value. Both `"platform"` and `"vertical"` rows are authored from the admin Studio surface. The tier_scope field classifies whose authoring surface "owns" the row (platform team vs. vertical-specific platform authoring), not who is allowed to author. The endpoint's authorization gate enforces "any platform admin" for authoring. Tier-3 placement-level overrides remain a tenant-render concern outside the WB substrate.

This matches the focus_compositions / platform_themes precedent — every layer of the three-tier inheritance chain (`platform_default → vertical_default → tenant_override`) is **authored** from the platform tree; only `tenant_override` is *visible* to tenant operators, and even then via specific tenant-authoring surfaces (Workshop / per-tenant theme override UI, not generic admin Studio).

### Coexistence

The tenant render-path endpoint at `/api/v1/widgets/composed-definitions` stays. It is the read-only consumer for Focus Builder palette + dashboard rendering — every tenant tree boot needs it. Option A does not break that. It adds an authoring-side platform-realm sibling.

---

## 8. Area 7 — Canon Candidates (NOT Filed)

Five candidates surface during this investigation. Per dispatch, do **not** file them in canon docs — accumulate and surface to the next canon-update arc.

1. **Auth-realm reachability checklist.** A class of bug: investigation Areas verifying frontend routing + frontend mounting do not substitute for verifying that the page's network calls reach a backend the host's auth realm satisfies. New investigation discipline: before locking "substrate end-to-end operator-ready" claims, list page's network calls + each call's backend router + each router's realm, confirm match. Closely related to the WB-4b silent-rail-label-inheritance class.

2. **Studio-authored substrates default to platform-realm endpoints.** Convention candidate: any new authoring substrate surfaced from Bridgeable Studio (`admin.getbridgeable.com/studio/*`) registers its CRUD endpoints under `/api/platform/admin/visual-editor/*` with `get_current_platform_user`. Tenant render paths get a separate read-only mount under `/api/v1/*` when needed (matching the WB-1..WB-3 read-only tenant path). The Widget Builder substrate violated this convention silently because it predated the rail entry decision. Future substrates avoid the misstep by default-placing endpoints on the platform router.

3. **Shared runtime-library boot adapters.** `registerComposedWidgets.ts` is a shared library imported by both tenant + admin trees. Its tenant `apiClient` import is correct for the tenant boot path and wrong for the admin Widget Builder shell's publish-refresh call. Candidate: shared runtime-library files that fetch must take their client instance as a parameter (or via a context registered at tree boot), not import it directly. Defers the realm choice to the consumer.

4. **F-1.1 + WB-cycle-followup-1 represent a pattern: substrate cycles consistently under-scope entry-point wiring + post-entry-functional verification.** F-1 didn't ship its rail entry; F-1.1 did. WB cycle didn't ship its rail entry; WB-cycle-followup-1 did. WB-cycle-followup-1's "post-deploy verification" claim was discoverability-only; functional verification surfaced this auth-realm gap. The pattern: substrate work → entry-point follow-up → post-entry functional verification. Three discrete steps, all required. Naming the pattern + including all three in build-cycle scope envelopes is the candidate.

5. **The Studio shell's authoring-realm asymmetry across builders.** Focus Builder reaches platform-realm endpoints. Widget Builder reaches tenant-realm endpoints (until Option A lands). This asymmetry is silent; no canon doc enumerates which builder targets which router. Candidate: a canonical Studio-builders table mapping (Builder name) → (frontend mount) → (backend router + realm) → (per-tier read-only tenant mount, if any). One row per builder; clarifies the convention and surfaces drift.

---

## 9. Proposed Fix Execution Plan

Build dispatch should follow this order. ZERO production changes in this investigation. Plan only.

### Backend (estimated ~80-120 production LOC + ~60-80 test LOC)

1. **New router file:** `backend/app/api/routes/admin/visual_editor_widgets.py`. Mirror `widget_definitions.py` endpoints with `get_current_platform_user` swapped in. Delegate to existing `app/services/widget_definitions/` service functions verbatim — no business-logic duplication. Add `actor_user_id` derivation handling for PlatformUser (matches the audit-attribution-limitation pattern from CLAUDE.md §4 "Admin Platform Architecture" — pass `None` for platform-user writes).
2. **Platform router registration:** `backend/app/api/platform.py` — register the new router at prefix `/admin/visual-editor/widgets`. Final path: `/api/platform/admin/visual-editor/widgets/*`. Composed-definitions endpoint surfaces as `/api/platform/admin/visual-editor/widgets/composed-definitions`.
3. **Tests:** `backend/tests/test_widget_definitions_platform_realm.py`. Mirror existing widget_definitions tests; cross-realm rejection tests (tenant token rejected, platform token accepted, missing token → 401). Confirm tier_scope CRUD across both `"platform"` + `"vertical"` values from platform realm.
4. **Tenant endpoint stays unchanged.** `/api/v1/widget-definitions/*` + `/api/v1/widgets/composed-definitions` remain on the tenant router. The tenant render path (`registerComposedWidgetsFromApi()` boot adapter at app startup in the tenant tree) continues to consume the tenant endpoint unchanged.

### Frontend (estimated ~30-60 production LOC + ~20-40 test LOC)

5. **New admin client wrapper:** `frontend/src/bridgeable-admin/services/visual-editor-widgets-service.ts`. Wraps `adminApi` calls to `/api/platform/admin/visual-editor/widgets/*`. Mirrors the existing `widget-builder-service.ts` shape so the swap-out is mechanical.
6. **Hook swap:** `useWidgetList.ts` → consume `adminApi` via the new service. Same response shape; same loading/error states.
7. **Service swap:** `widgetBuilderService` callers in `useWidgetAutoSave.ts` + WidgetListPage's "+ New Widget" handler + Widget Builder shell's load + publish paths → consume new admin service.
8. **`registerComposedWidgets.ts` careful handling:** keep the tenant `apiClient` boot path as-is (tenant tree consumers unchanged). Add a separate `refreshComposedWidgetsFromAdmin(adminApi)` helper consumed by the admin tree's publish-success path. Decision per Q-B1: if `registerComposedWidgets` is only imported from the tenant tree, no admin-side refresh needed; if imported from both, ship the separate helper.
9. **Vitest updates:** existing `useWidgetList.test.tsx`, `widget-builder-service.test.ts` mock targets update. New tests for the admin-service wrapper.
10. **Build + tsc check.** No new types beyond the service wrapper.

### Verification

11. **Post-deploy:** operator validates from `admin.getbridgeable.com` Studio. WidgetListPage loads the row list. Widget Builder shell loads + saves + publishes a draft. Composed widgets re-register in the admin Studio palette after publish. Tenant render path unaffected — sunnycrest.getbridgeable.com Focus Builder palette + dashboard rendering continues to surface composed widgets as it did pre-fix.

### Out of scope for this fix

- `useCanvasPreviewData`'s `executeSavedView` saved-view binding picker — Q-B2 pending. Likely needs a separate platform-realm saved-view-preview endpoint OR explicit impersonation-context requirement.
- Documents Builder + future builders' analogous gaps (Documents builder is currently a placeholder per CLAUDE.md §4 "Visual Editor Top-Level Structure"); flag for the Documents arc.
- The runtime-editor impersonation flow's interaction with admin Studio surfaces — a separate concern about which surfaces should be impersonation-aware.

---

## 10. Architectural Surprises

1. **Two of three frontend call sites live under `frontend/src/bridgeable-admin/` but import the tenant `apiClient`.** `useWidgetList.ts:15` and `widget-builder-service.ts:9` both `import apiClient from "@/lib/api-client"`. The file location convention (admin tree) and the API client convention (tenant client) disagreed silently. Lint-rule candidate: files under `bridgeable-admin/` may not import `@/lib/api-client` except via an explicit, audited adapter (the runtime-editor's impersonation path being the audited exception). Would have caught this at authoring time.

2. **The cross-realm boundary at deps.py:40-44 returns 401, not 403.** The dispatch text reported "403" — possibly operator misread, possibly some other middleware path. Either way, no `widget_definitions.py` / `widgets.py` / `deps.py` path returns 403 for the described scenario. The investigation's working answer is "status code observation is operator-side noise; the root cause is realm + company-context mismatch regardless of which non-2xx surfaces." A clarifying screenshot from the operator would pin the precise status but does not change the locked fix.

3. **The Focus Builder substrate's backend lives on the platform router; the Widget Builder substrate's backend lives on the tenant router. The asymmetry is invisible without reading both substrate cycles' build reports.** This wasn't a deliberate architectural decision — Focus compositions were authored as part of the focus-compositions arc which had the Visual Editor pattern locked at the platform router. Widget Builder was authored as a follow-on substrate consuming the existing pre-Studio tenant-side `/api/v1/widgets/` routes which predated the Studio shell entirely. The asymmetry is historical, not intentional. Canon candidate #5 surfaces the fix.

4. **`widget_definitions` has no `company_id` column** — it is platform-wide data. The endpoint's `get_current_user` gate exists purely as a "behind login" check (widgets.py:30-33), not as tenant isolation. Moving the gate from `get_current_user` to `get_current_platform_user` doesn't weaken any tenant isolation — there is none to weaken. This is the lowest-risk security-wise of any cross-realm migration the platform has done.

5. **The `WB-cycle-followup-1` build report's post-deploy verification claim — "WB cycle substrate becomes operator-discoverable end-to-end" — was technically accurate (discoverability) but the build report carried it forward as if it implied functional end-to-end correctness.** It did not. The discoverability + functional verification are two discrete claims; future build reports should separate them. Candidate canon refinement.

---

**End of investigation.**

**Cross-references:**

- Prior investigation: `docs/investigations/2026-05-25-studio-nav-widget-builder.md` (the rail-entry substrate audit that this investigation extends).
- WB substrate cycle build reports: `docs/investigations/2026-05-21-widget-builder.md`, `2026-05-21-widget-builder-canvas.md`, `2026-05-22-widget-builder-bindings.md`, `2026-05-23-widget-builder-canvas-preview.md`, `2026-05-24-widget-builder-button-actions.md`, `2026-05-24-widget-builder-variants.md`.
- WB-cycle-followup-1 commit: `537ebff` (rail entry activation).
- F-1.1 precedent commit: `7456b57` (Focus Builder rail entry).
- Backend endpoint files: `backend/app/api/routes/widget_definitions.py`, `backend/app/api/routes/widgets.py:14-55`.
- Backend router registration: `backend/app/api/v1.py:872-880`, `backend/app/api/platform.py` (zero widget mounts today).
- Backend auth dependencies: `backend/app/api/deps.py:27-110` (`get_current_user`), `backend/app/api/deps.py:287-330` (`get_current_platform_user`), `backend/app/api/company_resolver.py` (`get_current_company`).
- Backend service layer: `backend/app/services/widget_definitions/publish.py` (realm-agnostic; reused unchanged by Option A).
- Backend impersonation flows: `backend/app/services/impersonation_service.py`, `backend/app/services/admin/impersonation_service.py:52-59`, `backend/app/core/security.py:104-120` (impersonation tokens carry `realm="tenant"`).
- Frontend tenant client: `frontend/src/lib/api-client.ts` (reads `localStorage["access_token"]`).
- Frontend admin client: `frontend/src/bridgeable-admin/lib/admin-api.ts` (reads `localStorage["bridgeable-admin-token-{env}"]`).
- Frontend call sites: `frontend/src/lib/widget-builder/runtime/registerComposedWidgets.ts`, `frontend/src/bridgeable-admin/hooks/useWidgetList.ts`, `frontend/src/bridgeable-admin/services/widget-builder-service.ts`, `frontend/src/bridgeable-admin/hooks/useWidgetAutoSave.ts`, `frontend/src/bridgeable-admin/hooks/useCanvasPreviewData.ts`.
- Widget tier model: `backend/app/models/widget_definition.py:165-167` (tier_scope; no company_id).
- Canon reference: CLAUDE.md §4 "Admin Platform Architecture" (cross-realm boundary, two-tree structure), §4 "Component Configuration / Theme Resolution / Focus Composition Layer / Workflow Canvas" (platform-realm authoring precedent).
