# Spaces Architecture

Authoritative reference for how Spaces work in Bridgeable, the distinction between **office roles** and **operational roles**, and the architectural decisions that carve out when a role gets a platform Space vs. a portal-shaped surface.

Companion doc to `CLAUDE.md` and `UI_UX_ARC.md`. Referenced by Phase 8e and inherited by Phases 8e.1 and 8e.2.

---

## 1. Spaces at a glance

A **Space** is a per-user workspace context layered over the vertical navigation. Each Space carries:

| Field | Purpose |
|---|---|
| `name` | Short label (e.g. "Arrangement", "Books", "Production") |
| `icon` | Lucide icon name |
| `accent` | One of six curated accent palettes (`warm`, `crisp`, `industrial`, `forward`, `neutral`, `muted`) |
| `density` | `comfortable` or `compact` |
| `is_default` | Exactly one Space per user carries this flag — the Space the user lands in on first login |
| `is_system` | Platform-owned spaces (Settings — Phase 8a); non-deletable |
| `default_home_route` | **Phase 8e** — deliberate-activation landing route (see §3) |
| `pins` | Ordered list of `PinConfig` (saved views, nav items, triage queues) |

Spaces live on `User.preferences.spaces` (JSONB array). No dedicated table. Per-user and bounded (`MAX_SPACES_PER_USER = 7`, `MAX_PINS_PER_SPACE = 20`).

Backend: `backend/app/services/spaces/` (registry, crud, seed, types). API: `/api/v1/spaces/*` (11 endpoints as of Phase 8e). Frontend: `frontend/src/contexts/space-context.tsx` + `frontend/src/components/spaces/*` + `frontend/src/components/layout/DotNav.tsx`.

---

## 2. Office roles vs. operational roles — the umbrella distinction

**This distinction is the reason Phase 8e ships template coverage for accountants + safety trainers but deliberately excludes drivers.**

### Office roles → platform UX

Office roles operate across many kinds of work in a day. Their workflow benefits from:

- **DotNav** — multiple Spaces for different contexts (Arrangement / Administrative / Ownership for a funeral director; Books / Reports / Compliance for an accountant).
- **Command bar** — cross-feature search + action + navigation for intent-driven execution. Cmd+K is the primary path for 90% of actions.
- **Customization** — user can create Spaces, pin items, rename, recolor, set landing routes.
- **Briefings + dashboards + hubs** — cross-cutting monitoring surfaces.
- **Cross-cutting navigation** — vertical nav + Space pins both reachable; user moves freely across the full platform.

Office roles shipping platform Space templates today:

| Vertical | Role | Spaces (default first) |
|---|---|---|
| funeral_home | director | Arrangement · Administrative · Ownership |
| funeral_home | admin | Arrangement · Administrative |
| funeral_home | office | Administrative |
| funeral_home | accountant | Books · Reports *(Phase 8e)* |
| manufacturing | admin | Production · Sales · Ownership |
| manufacturing | office | Administrative · Operational |
| manufacturing | production | Production · Operations |
| manufacturing | accountant | Books · Reports · Compliance *(Phase 8e)* |
| manufacturing | safety_trainer | Compliance · Training *(Phase 8e promotion from fallback)* |
| cemetery | admin | Operations · Administrative · Ownership *(Phase 8e)* |
| cemetery | office | Administrative · Operational *(Phase 8e)* |
| crematory | admin | Operations · Administrative *(Phase 8e)* |
| crematory | office | Operations · Administrative *(Phase 8e)* |

Plus the `settings` system space (Phase 8a, admin-only) and the `General` fallback for unmapped roles.

### Operational roles → portal UX

Operational roles are **single-purpose**. A driver does delivery routes. A yard operator moves vault stock. A removal staff member collects remains. These roles:

- **Log in to one thing.** They do not "switch contexts" — their day is the scope.
- **Work on mobile or tablet**, often standing or in motion, often outside.
- **Benefit from reduced chrome**, not customization. The fewer decisions the surface forces, the faster the work.
- **Should be tenant-branded**, not platform-branded — the funeral home driver thinks of themselves as working for the funeral home, not for "Bridgeable."

Shipping a DotNav + command bar + briefing stack for a driver inverts the shape of their work. It's the wrong surface for them even though they're internal employees of a tenant.

**Therefore: operational roles do NOT get platform Space templates.** Phase 8e explicitly excludes:

- `(funeral_home, "driver")` — FH removal staff work is dispatched through case workflows; no driver-specific Space.
- `(manufacturing, "driver")` — reserved for Phase 8e.2 as the reconnaissance portal use case.

Both fall to the `General` fallback template today (one space, `/dashboard` as landing). That's fine as a temporary state — drivers reaching the platform see a working Home screen. Phase 8e.2 replaces that with a proper portal surface.

---

## 3. Deliberate vs. keyboard activation (Phase 8e)

When a user "switches into" a Space, the platform either navigates the user to the Space's `default_home_route` or stays on the current page. The distinction turns on **how** the user switched.

### Deliberate activation → navigate

- Click a dot in **DotNav**.
- Click a row in the SpaceSwitcher dropdown *(retired Phase 8e; kept here for history — the callout below covers replacement surfaces)*.
- Activate a **Switch-to-X** result from the command bar (`/?__switch_space=<id>`).

In every case, the target Space's `default_home_route` fires (via `useNavigate`). If `default_home_route` is null, no navigation — Space switches still apply the accent, refresh pins, and update `active_space_id`, but the URL stays.

### Keyboard activation → no navigate

- `⌘[` / `⌘]` (previous/next).
- `⌘⇧1..7` (jump to Space N).

Rapid switching across Spaces shouldn't fling the user between routes. Keyboard users cycling Spaces to skim accents + pins expect to stay where they are.

### Why this distinction matters

The alternative — "always navigate on Space activation" — breaks the fluid "look at my other Spaces without leaving this page" interaction. The alternative — "never navigate" — wastes the signal that clicking a Space IS a deliberate commitment to a different kind of work.

The implementation: `SpaceContext.switchSpace(spaceId, { source: "deliberate" | "keyboard" })`. Default when omitted is `"keyboard"` (safer). DotNav click passes `"deliberate"`; DotNav keyboard handlers pass `"keyboard"`. Command bar Switch-to-X passes `"deliberate"`.

---

## 4. Landing-route authoring

Every shipped Space template carries a `default_home_route`. Users can edit via `SpaceEditorDialog`'s "Landing route" dropdown which populates from:

1. `"Don't navigate"` (explicit null).
2. Every pin in the Space with a resolvable `href` (de-duped).
3. `/dashboard` as a universal fallback (if not already in the pin list).
4. The Space's current `default_home_route` if it's not in any of the above (preserves custom settings).

Unavailable pins (deleted saved view, revoked triage queue) are excluded — you can't land somewhere you can't reach.

The dropdown is deliberately narrow to prevent users from pointing a Space at an unrelated route. A Space named "Production" with landing route `/financials` creates cognitive friction; keeping the picker scoped to the Space's own pins nudges users toward coherent choices.

---

## 5. Reapply-defaults

`POST /api/v1/spaces/reapply-defaults` re-runs Phase 2 (saved views), Phase 3 (spaces), and Phase 6 (briefings) role-based seeding for the caller. Idempotent via the underlying seed functions' per-role preferences arrays. Returns counts per subsystem.

**Exposed because** `ROLE_CHANGE_RESEED_ENABLED = False` (Phase 8a opinionated-but-configurable discipline). Role changes no longer auto-reseed saved views; users who want their fresh role defaults call this endpoint.

**Future UI surface** (post-Phase-8e): a "Reapply role defaults" action in `/settings/spaces` or in the space editor dialog. Phase 8e ships the endpoint but not the dedicated UI page.

---

## 6. Phase 8e.2 (coming) — portal foundation

Phase 8e.2 is the **reconnaissance phase for portals**. Manufacturing driver becomes the first concrete portal user. Scope:

- `SpaceConfig` modifier fields:
  - `access_mode: "full" | "portal_restricted"` — controls whether the user sees DotNav, command bar, and customization. `portal_restricted` collapses to a single-space lock + mobile-first chrome.
  - `tenant_branding: bool` — swap platform header/footer for tenant logo + colors.
  - `write_mode: "full" | "restricted"` — narrow the set of actions the portal user can perform (e.g., driver can update delivery status but not edit the underlying order).
- **Portal user authentication** — separate identity store from tenant users; portal users may be internal (driver) or external (funeral home director pinging a supplier portal).
- **Portal session management** — session scope bound to the portal's Space + that Space's pins only.
- **Portal-restricted UI shell** — no DotNav, no command bar, no settings. Single-Space view; mobile-first.
- **Per-tenant portal branding override** — logo, primary color, tenant URL slug at `<tenant>.portal.getbridgeable.com`.
- **MFG driver template** — the first concrete portal, shipping as reconnaissance for future portals (family, supplier, customer).
- **Portal user management UI** for tenant admins — invite + provision portal users.

The Phase 8e.2 architecture reuses the `SpaceConfig` primitive with modifiers instead of introducing a separate portal data model. This is the "portal-as-space-with-modifiers" architectural insight: external portals (family, supplier, customer, partner) AND internal operational role portals (driver, yard operator) are the same primitive — a Space with restricted access mode — differing only by who authenticates.

**Phase 8e.2 ships before September Wilbert demo** so the demo story can include the portal-side delivery driver narrative alongside the platform-side office work narrative.

---

## 7. Arc sequencing (as of Phase 8e)

1. ✅ Phase 8c
2. ✅ Aesthetic Arc Session 1
3. ✅ Phase 8d
4. ✅ Phase 8d.1
5. ✅ Aesthetic Arc Session 2
6. ✅ Aesthetic Arc Session 3
7. **▶ Phase 8e — Spaces and default views** *(current)*
8. Phase 8e.1 — Smart spaces (topical affinity, customization UI, advanced default-view configuration)
9. Phase 8e.2 — Portal foundation (driver as reconnaissance)
10. Aesthetic Arc Sessions 4–5
11. Phase 8f — remaining accounting migrations
12. Phase 8g — dashboard rework
13. Aesthetic Arc Session 6 — final QA
14. Latent bug cleanup session
15. Phase 8h — arc finale

---

## 8. Invariants (test-enforced)

- **No driver templates in `SEED_TEMPLATES`** until Phase 8e.2. `tests/test_spaces_phase8e.py::TestNoDriverTemplates::test_no_driver_key_in_seed_templates` fails if anyone adds one without the portal infra.
- **Every `saved_view` pin in a space template has a matching `SeedTemplate` in `saved_views/seed.py`** (for the same vertical). `tests/test_spaces_phase8e.py::TestSavedViewSeedDependencies` cross-references at module load; fails loudly if a pin points at a seed key that doesn't resolve.
- **Every `nav_item` pin target has a `NAV_LABEL_TABLE` entry.** `tests/test_spaces_phase8e.py::TestNavLabelCoverage` — catches template-additions that forget to add the label lookup.
- **`MAX_SPACES_PER_USER == 7`** (backend + frontend in lockstep). Bump in lockstep — type `backend/app/services/spaces/types.py` + `frontend/src/types/spaces.ts`.
- **`tier=1 AND vertical IS NOT NULL IMPLIES scope='vertical'`** — Phase 8a invariant preserved. Not directly related to Spaces, but Phase 8e touches the same namespace during workflow arc work.
- **Command bar `p50 ≤ 100 ms, p99 ≤ 300 ms` with affinity enabled.** `tests/test_command_bar_latency.py` is a BLOCKING CI gate. The seeded tenant carries 10 affinity rows + an active space so the prefetch + boost passes are exercised.

---

## 9. Smart Spaces — topical affinity (Phase 8e.1)

Phase 8e.1 adds a ranking-signal layer on top of the Phase 8e spaces fabric. **Users don't configure "what this space is about" — the system infers it from what users actually do in the space.** Signal is implicit, computation is automatic, result is a command bar that responds to behavior.

### 9.1 Data model

Per-user, per-space, per-tenant affinity row. One row per unique `(user, space, target_type, target_id)` — upsert semantics via `INSERT ... ON CONFLICT DO UPDATE`.

```
user_space_affinity
  user_id        FK users(id)       NOT NULL  ← tenant-scoped via user.company_id
  company_id     FK companies(id)   NOT NULL
  space_id       String(36)         NOT NULL  ← matches SpaceConfig.space_id (no FK — spaces live in JSONB)
  target_type    String(32)         NOT NULL  CHECK IN (nav_item, saved_view, entity_record, triage_queue)
  target_id      String(255)        NOT NULL
  visit_count    Integer            NOT NULL  default 0
  last_visited_at Timestamptz       NOT NULL
  created_at     Timestamptz        NOT NULL

  PRIMARY KEY (user_id, space_id, target_type, target_id)
  INDEX ix_user_space_affinity_user_space_active (user_id, space_id) WHERE visit_count > 0
  INDEX ix_user_space_affinity_user_recent_active (user_id, last_visited_at DESC) WHERE visit_count > 0
```

Composite PK: no surrogate UUID — the tuple IS the row identity. Partial indexes shrink to active rows. Storage bound: `pins × spaces ≤ 7 × 20 = 140 rows` per user steady-state (in practice well under).

Tenant isolation is **by construction** — `user_id` resolves to a specific tenant via `user.company_id`. Cross-tenant affinity leakage is impossible.

### 9.2 Write path — 4 deliberate-intent triggers

Affinity writes ONLY on deliberate user intent. Five anti-triggers explicitly don't count (DotNav space-switch clicks, keyboard space cycling, unpin, hover peek, rendered-but-not-activated results).

| Trigger | Target type | Target id | Wired in |
|---|---|---|---|
| Pin click in PinnedSection | Whatever pin.pin_type is | pin.target_id (or resolved saved_view_id) | `components/spaces/PinnedSection.tsx` |
| PinStar toggle → pinned | pinType prop | targetId prop | `components/spaces/PinStar.tsx` |
| Command-bar navigate (active space set) | Inferred from action.type + route | Stripped prefix for saved_view/entity_record | `components/core/CommandBar.tsx` |
| Pinned-nav direct page visit | Matches active-space pin | pin.target_id | `components/spaces/AffinityVisitWatcher.tsx` (mounted at app root under SpaceProvider) |

Matching rules: `nav_item` is **starts-with** (pin to `/cases` catches `/cases/X/edit`); `saved_view` and `triage_queue` are **exact** (pin to `/triage/task_triage` doesn't match `/triage/other`).

### 9.3 Write path — fire-and-forget contract

- Client hook `useAffinityVisit()` exposes `recordVisit({targetType, targetId, spaceId?})`. **No await.** UI never blocks.
- Client throttle: 60 seconds per `(target_type, target_id)` per session (tab). Module-scoped `Map` in `hooks/useAffinityVisit.ts`.
- Server throttle: 60 seconds per `(user_id, target_type, target_id)` per process. Defense-in-depth. `app/services/spaces/affinity.py::_should_throttle`.
- Both return `{recorded: boolean}` from the endpoint — `false` indicates throttled; clients ignore.
- Brief server downtime: signal loss is acceptable (affinity is signal, not transactional state).

**Endpoint:** `POST /api/v1/spaces/affinity/visit`. See `app/api/routes/spaces.py`. Status 200 either way; 400 on bad target_type; 404 on unknown space_id.

### 9.4 Read path — boost formula

One prefetch query per `command_bar/query` call → in-memory dict → O(1) lookup during ranking.

```
affinity_weight = 1.0 + 0.4 * log_visits * recency_decay
  log_visits     = min(1.0, log10(visit_count + 1) / log10(11))       [0..1]
  recency_decay  = max(0.0, 1.0 - (age_days / 30.0))                  [0..1]
```

Examples (visit_count → weight, fresh row):

| visits | weight | notes |
|---:|---:|---|
| 0 | 1.000 | No boost (row doesn't exist) |
| 1 | 1.116 | Small nudge |
| 5 | 1.299 | Medium |
| 10 | 1.400 | Max |
| 20 | 1.400 | Saturated — same as 10 |

Decay (at visit_count=10):

| age_days | weight |
|---:|---:|
| 0 | 1.400 |
| 15 | 1.200 |
| 30 | 1.000 |
| 45 | 1.000 |

**Purpose-limitation clause**: affinity data is used ONLY for command bar ranking. Any future use (briefings recommendations, dashboard personalization, saved-view recommendations, learning-based suggestions, anything else) requires a **separate scope-expansion audit** and explicit user consent flow. This clause is load-bearing for privacy + trust — do not extend silently.

### 9.5 Read path — boost composition

Three multiplicative boosts in `command_bar/retrieval.py` (applied in this order):

1. **Phase 3 active-space pin boost** — `1.25×` for any result matching a currently-pinned target.
2. **Phase 8e.1 starter-template boost** — `1.10×` for any result matching a target in the role-template that seeded the active space, EVEN IF the user has since unpinned it. Skipped when pin boost already applied (not additive with pin boost; pin boost wins).
3. **Phase 8e.1 topical affinity boost** — `1.0×` to `1.40×` per the formula above. Composes multiplicatively with the other two.

**Max stack:** pinned + in-template-too + 10+ visits today → `1.25 × 1.00 × 1.40 = 1.75×` (template skipped because pin is a stronger same-shape signal).
**Max stack without pin:** template + affinity → `1.10 × 1.40 = 1.54×`.
**Max single boost ceiling in the system** (pre-8e.1): `_WEIGHT_CREATE_ON_CREATE_INTENT = 1.5`. The 1.75× max compound is slightly above this — accepted because a heavily-used + pinned target deserves to outrank a generic "new X" create action.

### 9.6 Privacy and data hygiene

- **`DELETE /api/v1/spaces/affinity`** — clears all affinity rows for the caller. Optional `?space_id=X` narrows to one space.
- **UI action** — "Clear command bar learning history" button in `/settings/spaces` with a confirmation modal.
- **Cascade on space delete** — `delete_space()` removes the space's affinity rows in the same transaction.
- **Cross-user / cross-tenant** — impossible by PK construction.
- **Retention** — indefinite storage; 30-day read-side decay makes old rows contribute 0 to ranking. No hard-delete job in 8e.1; revisit post-September if storage becomes a concern.
- **Affinity viewer** — `/settings/spaces` shows an aggregate "N tracked signals" counter via `GET /api/v1/spaces/affinity/count`. Detailed per-target breakdown is deferred (post-arc); the single counter satisfies GDPR right-to-access without leaking implementation detail.

### 9.7 Performance

- **Baseline** `command_bar_query` p50 = 7.9 ms / p99 = 10.3 ms (Phase 8e, pre-8e.1 measurement).
- **With affinity enabled** p50 = 8.2 ms / p99 = 77.3 ms on dev. Headroom: 12× on p50, 3.9× on p99. Well under the 100 / 300 ms BLOCKING budget.
- **BLOCKING CI gate** at `tests/test_command_bar_latency.py` — the seeded tenant now carries 10 affinity rows + an active space; every sampled query passes `context.active_space_id` so the prefetch + boost passes are exercised in the measurement.

### 9.8 Customization UI — `/settings/spaces`

Phase 8e.1 ships the full customization surface. Features:

- **Sidebar** — user's spaces, system first (sticky leftmost), drag-reorder for user spaces.
- **Main editor** — name, icon (16-entry narrow picker), accent (6-option + hover live preview), density, is_default, landing route (pin-derived dropdown).
- **Pin manager** — drag-reorder, remove, "Move to…" popover for transferring pins between spaces.
- **Header actions** — "New space", "Add starter template", "Reapply role defaults" (with confirmation modal — non-destructive), "Reset all spaces" (destructive, type-to-confirm `Reset spaces`).
- **Privacy card** — affinity counter + "Clear learning history" button.
- **Onboarding touch** — `welcome_to_settings_spaces` at top of page on first visit.

Built strictly on Aesthetic Arc Session 3 primitives (Alert, StatusPill, Tooltip, Popover, FormSection, FormStack, Card, Dialog, brass focus rings). Page is a showcase for the design language.

The existing `NewSpaceDialog` and `SpaceEditorDialog` (DotNav quick-paths) **coexist** with `/settings/spaces`. They gain "More options…" / "Manage all pins…" deep-link footers that navigate to the power surface.

### 9.9 Test coverage

**33 new tests** in `tests/test_spaces_phase8e1_affinity.py` — schema, boost formula (incl. decay), record_visit service, prefetch service, cross-user/cross-tenant isolation, cascade-on-delete, clear_affinity_for_user, API endpoints (visit, count, clear), starter-template boost, pin boost regression, boost composition. **Plus the BLOCKING latency gate** in `test_command_bar_latency.py` extended to seed affinity rows.

Full Phase 1–8e.1 regression: **151 spaces tests passing**, no regressions.

---

## 10. Portal Foundation (Phase 8e.2) — portals as spaces with modifiers

Phase 8e.2 validates the portal-as-space-with-modifiers architecture introduced in §6 with **MFG driver** as the first concrete portal application. Office users continue on platform UX; operational-role users (drivers today, yard operators + removal staff when added) get portal UX — identity-separated, tenant-branded, single-purpose. Phase 8e.2 ships **infrastructure + end-to-end minimal driver portal**; Phase 8e.2.1 ships admin UI + branding editor + the remaining 4 driver pages mounted.

### 10.1 SpaceConfig modifier fields

Four new fields on `SpaceConfig` (JSONB on `User.preferences.spaces[*]`, no schema migration for the modifiers themselves):

| Field | Values | Purpose |
|---|---|---|
| `access_mode` | `platform` (default) \| `portal_partner` \| `portal_external` | Platform = full office UX. `portal_partner` = internal-but-restricted operational role (driver). `portal_external` = external user (family/supplier/customer — future). |
| `tenant_branding` | `bool`, default `false` | When `true`, portal UI applies tenant branding (logo, brand color) on the highest-attention surfaces. |
| `write_mode` | `full` \| `limited` \| `read_only` | Narrows the set of actions available. Driver = `limited` (updates status + proof; doesn't edit orders). |
| `session_timeout_minutes` | `int \| null` | Optional per-space JWT TTL override. Null → realm default (12h for portals). Future family portal sets `60` (1h); supplier `240` (4h). |

Legacy spaces (pre-8e.2) default to `platform / false / full / null` via `SpaceConfig.from_dict` — non-destructive to every existing user row.

### 10.2 Portal user identity store

**Separate `portal_users` table** (migration `r42_portal_users`). NOT a discriminator column on `users` — identity-level separation per the audit's approved principle. Prevents cross-realm privilege bleed at the query layer.

```
portal_users
  id, company_id FK (cascade), email, hashed_password (nullable — invite-only),
  first_name, last_name, assigned_space_id (matches SpaceConfig.space_id),
  is_active, last_login_at, failed_login_count, locked_until,
  invited_by_user_id FK users, invite_token, invite_token_expires_at,
  recovery_token, recovery_token_expires_at,
  created_at, updated_at
  UNIQUE (email, company_id)
  partial unique indexes on invite_token + recovery_token (WHERE NOT NULL)
```

**Driver link**: `drivers.portal_user_id` added as an optional parallel column to the existing `drivers.employee_id → users.id`. Non-destructive: Sunnycrest's existing tenant-user drivers keep working on `employee_id`; new portal drivers use `portal_user_id`. Business-logic invariant (NOT a DB CHECK): exactly one populated per Driver row. Tests enforce. CHECK constraint omitted deliberately to permit migration windows where a driver transitions between identities.

**Audit log discriminator**: `audit_logs.actor_type` column with default `'tenant_user'`. Portal-user-authored actions stamp `'portal_user'`. Existing audit queries continue working unchanged; future queries that need to join the correct identity table filter by `actor_type` first.

### 10.3 JWT realm extension — `realm="portal"`

Third realm alongside existing `tenant` + `platform`. Portal access token payload:

```
{
  "sub": portal_user_id,
  "realm": "portal",
  "company_id": tenant_id,
  "space_id": assigned_space_id,   // scope claim
  "type": "access",
  "exp": now + 12h (or per-space override)
}
```

Load-bearing security boundary — four cross-realm-isolation tests enforce:
1. Portal token → tenant endpoint = 401
2. Tenant token → portal endpoint = 401
3. Portal token for tenant A → tenant B's portal URL = 401
4. Deactivated portal user → 401 on next request

**Dependencies** in `backend/app/api/deps.py`:
- `get_current_user` (tenant) — now rejects `realm=portal` in addition to `realm=platform`.
- `get_current_portal_user` (new) — validates `realm=portal`, loads `PortalUser`, stashes the token's `space_id` on the user for downstream scope-check.
- `get_portal_company_from_slug` (new) — resolves the tenant from the URL path segment (not header), since portal URL = tenant identity.
- `get_current_portal_user_for_tenant` (new) — composite that validates both.

### 10.4 Path-scoped routing

**Portal URLs are `/portal/<tenant-slug>/...`** (not `<tenant>.portal.getbridgeable.com` subdomains). Path-scoped lands in dev + prod with zero infra changes. Subdomain routing is a post-September infrastructure phase; path-scoped routes keep working as a fallback.

```
/portal/<slug>/login                   — public
/portal/<slug>/driver                  — authed driver home (Phase 8e.2)
/portal/<slug>/driver/route            — future (Phase 8e.2.1)
/portal/<slug>/driver/stops/:stopId    — future (Phase 8e.2.1)
/portal/<slug>/driver/mileage          — future (Phase 8e.2.1)
/portal/<slug>/reset-password?token=…  — future (Phase 8e.2.1)
```

Frontend: App.tsx detects `location.pathname.startsWith("/portal/")` and routes the render to a separate `PortalApp` component (new `frontend/src/PortalApp.tsx`) that mounts its own provider tree. **Zero overlap with the tenant `AppLayout` provider stack** — never share auth context across realms.

### 10.5 Tenant branding configuration

Per-tenant branding fields stored in `Company.settings_json.portal.*`:

| Field | Source | Type |
|---|---|---|
| `display_name` | `Company.name` (reused) | existing column |
| `logo_url` | `Company.logo_url` (reused) | existing column |
| `brand_color` | `Company.settings_json.portal.brand_color` | NEW, hex string |
| `footer_text` | `Company.settings_json.portal.footer_text` | NEW, optional string |

Public endpoint `GET /api/v1/portal/<slug>/branding` returns this shape to pre-auth portal frontend so the login page loads branded. No data leak — these fields already surface in emails and are public-adjacent.

**Phase 8e.2 ships the backend setter** (`portal.branding.set_portal_branding`) but NOT the admin UI. Branding editor UI lands in Phase 8e.2.1 alongside the portal user admin page.

### 10.6 Portal UI shell — "wash, not reskin"

Brand color applies ONLY to:
- Portal header background
- Primary CTA background (login submit, future bottom-nav active indicator)
- Focus-ring color for interactive portal elements

Brand color does **NOT** apply to:
- Status colors (`--status-success` / `-warning` / `-error` / `-info`) — stay DESIGN_LANGUAGE tokens
- Typography (stays IBM Plex Sans)
- Surface tokens (stay brass-themed; wash sits on top)
- Border radius / motion curves / shadow system — DESIGN_LANGUAGE

Discipline rationale: portal feels tenant-branded without sacrificing Aesthetic Arc consistency. Tenant sees their color on the highest-attention surfaces; the underlying experience stays Bridgeable-coherent.

Shell scope:
- **NO** DotNav (portal users have one space)
- **NO** command bar (out of portal scope)
- **NO** settings (portal users don't customize)
- **NO** saved views, peek, briefings
- Tenant-branded header (logo + display name + user name + Sign Out)
- Mobile-first single-column content area
- Optional footer (tenant `footer_text` if set)

Frontend components:
- `PortalBrandProvider` (`frontend/src/contexts/portal-brand-context.tsx`) — fetches branding + applies `--portal-brand` + `--portal-brand-fg` CSS vars + sets `data-portal-brand` root attribute.
- `PortalAuthProvider` (`frontend/src/contexts/portal-auth-context.tsx`) — parallel to `AuthContext`, separate LocalStorage keys (`portal_access_token` etc.), separate login/refresh/logout.
- `PortalLayout` (`frontend/src/components/portal/PortalLayout.tsx`) — header + `<Outlet>` + optional footer.
- `PortalRouteGuard` (`frontend/src/components/portal/PortalRouteGuard.tsx`) — `ProtectedRoute` equivalent for portal realm. Redirects to `/portal/<slug>/login`.
- `PortalLogin` page, `PortalDriverHome` page.

**Tenant brand color in dark mode (Aesthetic Arc Session 4 decision — Option A).** Tenant configures a single hex color applied in both modes. Provider computes a contrast-safe `--portal-brand-fg` (white or dark charcoal) based on the brand color's luminance. Admins verify dark-mode rendering via the Light/Dark toggle in the `/settings/portal-branding` preview panel — both a brand→fg WCAG contrast readout (pass/fail against 4.5:1 AA) and a brand→page-surface visibility readout (1.5:1 advisory threshold) surface in the editor. Options B (auto-adjust luminance per mode) and C (separate light/dark brand schema) were explicitly considered and rejected. If post-arc production signal shows tenants regularly pick poor-contrast dark brands, revisit.

**Known minor discrepancy (deferred):** `PortalBrandProvider.applyBrandColor` computes the brand-color luminance via BT.601 (`0.299R + 0.587G + 0.114B`) to pick between `#1a1a1a` and `#ffffff` for `--portal-brand-fg`. The branding-editor preview panel uses proper WCAG relative luminance (sRGB gamma-corrected, `0.2126·R + 0.7152·G + 0.0722·B` with linearization). The two formulas diverge <5% for most colors; no shipping issue. Aligning `PortalBrandProvider` with WCAG is deferred because it's tangential to current portal UX concerns. Revisit if/when portal branding becomes a larger focus area.

**Fallback discipline (Session 4, M2):** the 3 portal pages that set header/CTA colors via inline styles use `var(--portal-brand-fg, var(--content-on-brass))` for the text fallback — NOT a literal `white`. This matters during PortalBrandProvider's first load (before branding has been fetched) and when a tenant has no custom brand (the underlying brass color shows through). Per DESIGN_LANGUAGE §3, dark-mode `content-on-brass` is deep warm charcoal, which correctly reads as "glowing pill with dark text" on brass. Hardcoding `white` inverted that in dark mode.

### 10.7 Thin-router-over-service pattern (canonical)

When a portal endpoint needs data the tenant side already has, the pattern is **thin router over existing service**:

1. Portal endpoint consumes `portal_user` via `get_current_portal_user`.
2. Resolves `portal_user.id → drivers.portal_user_id → Driver row` via `portal.user_service.resolve_driver_for_portal_user`.
3. Calls the existing service layer using `Driver` as the actor.
4. Returns a response shaped for the portal UI.

Example: `GET /api/v1/portal/drivers/me/summary` (Phase 8e.2) resolves the Driver row then queries `DeliveryStop` + `DeliveryRoute` filtered by driver_id. No business logic duplication; same underlying query path as the tenant-user driver flow.

**Why this is the canonical pattern**: future portals (family looking up case status, supplier checking inventory allocation, customer viewing order status) all follow the same shape. Resolve portal_user → domain actor → existing service. Zero business logic duplication, clean audit trails (the Driver row is the actor of record in both paths).

### 10.8 Portal authentication security

| Concern | Phase 8e.2 |
|---|---|
| Password min length | 8 chars, no complexity rules |
| Account lockout | 10 failed attempts → 30-min `locked_until` stamp |
| Rate limit | In-memory IP+email bucket, 10 attempts / 30 min per worker |
| Password recovery | Single-use 1-hour token via D-7 email template `email.portal_password_recovery` (migration `r43_portal_password_email_template`) |
| Access token TTL | 12 hours (driver default); per-space `session_timeout_minutes` override |
| Refresh TTL | 7 days |
| Session revocation on deactivate | Future requests fail at `get_current_portal_user` (DB check confirms `is_active=True`); existing tokens die at TTL. Acceptable for 8e.2. |

### 10.9 Office vs. operational distinction — driver validates

Phase 8e.2 closes the gap opened in §2: operational roles now have a shape. The MFG driver template lives at `("manufacturing", "driver")` in `SEED_TEMPLATES` with `access_mode="portal_partner"`, `tenant_branding=True`, `write_mode="limited"`, `session_timeout_minutes=720`.

The Phase 8e invariant test renamed from `TestNoDriverTemplates` → `TestDriverTemplatesUsePortalAccessMode`. The invariant evolves:

**Before 8e.2**: "Drivers have NO templates (operational roles deferred)."
**After 8e.2**: "Drivers + yard_operator + removal_staff (operational role slugs) MUST have `access_mode` starting with `portal_` if a template exists. Office role slugs (admin/director/accountant/etc.) MUST have `access_mode='platform'`. Symmetric invariant — no accidental drift in either direction."

FH driver remains excluded — FH removal staff work dispatches through case workflows today; their portal template lands when that workflow matures.

### 10.10 Invariants (Phase 8e.2 additions)

Added to §8:

- **MFG driver template is portal-shaped.** `test_portal_phase8e2.py::TestMfgDriverTemplate::test_mfg_driver_template_is_portal` asserts `access_mode="portal_partner"` + `tenant_branding=True` + `write_mode="limited"` + `session_timeout_minutes=720`.
- **Driver template invariant symmetric.** Operational-role templates use `portal_*` access_mode; office-role templates use `platform`. `test_spaces_phase8e.py::TestDriverTemplatesUsePortalAccessMode` enforces.
- **Cross-realm token isolation is 401, not quietly tolerated.** Four explicit tests.
- **Sunnycrest's existing tenant-user drivers continue working.** `test_portal_phase8e2.py::TestNonDestructiveDriverMigration` — a Driver with `employee_id` set + `portal_user_id=None` round-trips cleanly.

### 10.11 What Phase 8e.2 explicitly defers to 8e.2.1

- Tenant admin UI for portal user management (`/settings/portal-users` page)
- Branding editor UI
- Remaining 4 driver pages mounted under `/portal/<slug>/driver/*` (route, stop detail, mileage, vehicle inspection)
- Offline-tolerance touches (OfflineBanner + retry toasts in portal)
- Full mobile polish pass (touch target audit beyond the login page)
- Reset-password / first-time-password pages at `/portal/<slug>/reset-password`

Phase 8e.2.1 completes the driver portal surface; Phase 8e.2's job is validating the portal-as-space-with-modifiers architecture end-to-end through one concrete working flow.

### 10.12 Test coverage

**25 new tests** in `tests/test_portal_phase8e2.py` across 9 test classes:

- `TestPortalUsersSchema` × 4 (table + unique email/tenant + drivers.portal_user_id + audit_logs.actor_type default)
- `TestPortalAuthService` × 4 (login success, invalid password, inactive, lockout after 10 fails)
- `TestPasswordRecovery` × 2 (issue + consume, expired rejected)
- `TestCrossRealmIsolation` × 4 (load-bearing — tenant→portal reject, portal→tenant reject, tenant-A token→tenant-B portal reject, deactivated user reject)
- `TestBrandingEndpoint` × 2 (returns default color, 404 for invalid slug)
- `TestLoginEndpoint` × 3 (success token pair, invalid 401, /me after login)
- `TestSpaceConfigModifiers` × 2 (round-trip + legacy defaults)
- `TestMfgDriverTemplate` × 1
- `TestDriverDataMirror` × 2 (unlinked graceful zero, linked returns driver_id)
- `TestNonDestructiveDriverMigration` × 1 (Sunnycrest tenant-user driver continues working)

Plus **3 Playwright smoke tests** at `frontend/tests/e2e/portal-phase-8e2.spec.ts`:
1. Branded login renders with tenant display name + brand color CSS var applied
2. Driver home renders after login with portal driver summary data
3. No DotNav, no command bar, no settings in portal shell (architectural boundary)

Full Phase 1–8e.2 backend regression: **379 tests passing, no regressions.** Migration head advances `r41_user_space_affinity` → `r42_portal_users` → `r43_portal_password_email_template`.

### 10.13 Phase 8e.2.1 — portal completion (the driver portal, end to end)

Phase 8e.2.1 closes the items deferred in §10.11. The architecture doesn't change; it gets filled in. Three things ship:

**1. Tenant-admin surfaces for managing portals.** Two new settings pages — `/settings/portal-users` and `/settings/portal-branding` — backed by a new `/api/v1/portal/admin/*` router. These are **tenant-realm** (JWT `realm="tenant"` + `require_admin`), distinct from `/api/v1/portal/*` (which is portal-realm and portal-user-facing). The realm separation is the same boundary Phase 8e.2 established: only tenant admins provision portal users; portal users themselves never reach the admin endpoints. The routing split is explicit — `portal_admin.router` is mounted BEFORE `portal.router` in `api/v1.py` so the parameterized `/{tenant_slug}/…` routes in the public portal don't swallow `/admin/*` by matching `tenant_slug="admin"`.

Admin user CRUD: list (with status + space filters), invite (POST, 201), edit (PATCH), deactivate, reactivate, unlock, reset-password, resend-invite. Email dispatch rides D-7's `send_email_with_template` with two separate managed templates — `email.portal_invite` (r45) is onboarding-flavored, distinct from the existing `email.portal_password_recovery`. Admin branding: GET + PATCH (brand_color + footer_text) + POST /branding/logo (PNG or JPG only, ≤2 MB, 50–1024 px dimensions, Pillow-verified). SVG logos are explicitly rejected for safety (future polish can add sanitization).

**2. Driver page completion.** The 4 remaining driver pages mount at `/portal/<slug>/driver/{route,stops/:stopId,mileage}` + the auth-flow reset page at `/portal/<slug>/reset-password`. The backend ships thin-router mirrors at `/portal/drivers/me/{route,stops/{id},stops/{id}/status,stops/{id}/exception,mileage}` — each one follows the canonical thin-router-over-service pattern (§10.7): resolve `portal_user → Driver via portal_user_id` then delegate to the existing `driver_mobile_service`. **Zero duplication** of route-loading or stop-status logic. The portal routes enforce driver-scoped isolation: cross-driver stop access 404s, cross-tenant access 404s (tenant context comes from the portal JWT — there's no X-Company-Slug sidechannel on portal-authed endpoints). `OfflineBanner` from Phase 7 is mounted inside `PortalLayout` (not the top-level PortalApp) so it only renders in the authed shell.

**3. Dual-identity migration for `Driver`.** Pre-8e.2.1 drivers linked to a tenant `User` via `drivers.employee_id` (NOT NULL). Post-8e.2.1, `employee_id` is nullable (migration **r44**) and `portal_user_id` is the canonical path forward. Both paths coexist during the migration window — legacy `employee_id`-only drivers continue to read cleanly; new drivers auto-create via the portal invite flow. **Actual column drop is deferred** to a latent-bug cleanup session; a test guarantees `is_nullable='YES'` is the post-r44 schema invariant. `widget_data.team_driver_performance` was rewritten from an INNER JOIN on `employee_id` to a two-lookup pattern that resolves display name from either `employees` OR `portal_users` — the widget now shows every active driver regardless of identity path.

**Auto-create Driver on invite (narrow scope).** `user_service._is_driver_space_template` checks the admin's assigned-space JSONB for a space named literally `"Driver"` (case-insensitive). Only that exact match triggers `_maybe_auto_create_driver_row`, which inserts a `Driver` row with `employee_id=NULL + portal_user_id=<new portal user>`. Future operational portals (yard_operator, removal_staff, family, supplier) will not accidentally become drivers — the predicate is deliberately narrow.

**Legacy `POST /api/v1/delivery/drivers` retired.** The tenant-admin create-driver endpoint was deleted. The portal invite flow is the only path for creating a new Driver row going forward. Manual `Driver` table inserts are still permitted for data migrations and tests; the HTTP-addressable surface is gone.

**Test coverage:** 31 new tests in `tests/test_portal_phase8e21.py` across 8 test classes:

- `TestAdminListAndInvite` × 5 (empty list, invite creates pending, duplicate email 409, status-filter correctness, non-admin 403)
- `TestAutoCreateDriverOnInvite` × 2 (driver-space triggers auto-create, non-driver-space does not)
- `TestAdminLifecycleActions` × 5 (edit, deactivate+reactivate cycle, unlock clears lockout, reset-password stamps token, resend-invite pending-only)
- `TestBrandingAdmin` × 3 (read, patch, invalid-hex 422)
- `TestLogoUpload` × 6 (SVG reject, empty reject, too-small reject, too-large reject, corrupt bytes reject, JPG happy path)
- `TestLegacyCreateDriverRetired` × 1 (POST /delivery/drivers returns 404 or 405)
- `TestPortalDriverDataMirror` × 8 (route shell when none, route with rows, 404 for unlinked, cross-driver stop 404, patch status, exception, mileage happy path, mileage end<start 400)
- `TestAdminRoutesCrossRealm` × 1 (portal token rejected on `/portal/admin/users`)

Plus **7 Playwright mobile scenarios** at `frontend/tests/e2e/portal-phase-8e21.spec.ts` (run under the Pixel 5 project in `playwright.config.ts`):
1. Driver route page renders mobile stop list
2. Stop detail allows marking delivered
3. Mileage page validates end≥start + navigates on success
4. Reset-password page renders branded with token param
5. Reset-password without token renders a helpful error
6. Mobile touch targets on stop detail meet 44px WCAG 2.2 minimum
7. OfflineBanner appears on offline event in portal shell

**Migration head advances** `r43_portal_password_email_template` → `r44_drivers_employee_id_nullable` → `r45_portal_invite_email_template`.

### 10.14 Deferred to post-8e.2.1

- Actual drop of `drivers.employee_id` column (latent-bug cleanup session after full production drift settles)
- Invite vs. recovery token column consolidation (`recovery_token` reused for both today — clean split is post-arc polish)
- Mobile touch-target audit beyond stop detail (lint-style coverage on every interactive element in the portal shell)
- Vehicle inspection page (mentioned in §10.11 but not shipped this phase — not blocking James dogfood, surfaces when the pre-trip-inspection workflow lands)
- Tenant-logo SVG support with server-side sanitization

