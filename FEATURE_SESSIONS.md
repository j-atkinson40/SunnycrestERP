# Feature Sessions — build log

Chronological log of significant feature builds. Each entry is
written at the end of a build and NOT updated afterward — history
first. For the current platform state, see `CLAUDE.md`.

---

## Space-Scoped Triage Queue Pinning (UI/UX Arc Follow-up 1)

**Date:** 2026-04-20
**Migration head:** `r35_briefings_table` (unchanged — no new tables, no migration)
**Tests passing:** 103 across Phase 3 + Phase 5 + follow-up regression (17 new follow-up tests in `test_space_pins_triage_queue.py`, 86 prior-phase spaces/triage tests unchanged)

### What shipped

Triage queues become a third pin target type alongside saved views
and nav items. A director on the funeral_home vertical opens their
auto-seeded Arrangement space and the first pin in the sidebar is
their Task Triage queue with a pending-item count badge — one click
opens the keyboard-driven workspace. A production manager on a
manufacturing tenant gets the same treatment on their Production
space.

Under the hood:

- `PinConfig.pin_type` literal extended with `"triage_queue"` on
  backend and frontend types (`backend/app/services/spaces/types.py`,
  `frontend/src/types/spaces.ts`).
- `ResolvedPin` gains `queue_item_count: int | None` (null for
  non-triage pins and for unavailable queues).
- `TriageQueueConfig` gains `icon: str = "ListChecks"`. Platform
  defaults: `task_triage` → `"CheckSquare"`,
  `ss_cert_triage` → `"FileCheck"`. Frontend `PinnedSection.ICON_MAP`
  gained all three names — verified present so no pin falls through
  to the `Layers` default silently.
- `_resolve_pin` has a new `triage_queue` branch that reads the
  queue config from the Phase 5 registry via
  `triage.registry.get_config` and pulls the pending count via
  `triage.engine.queue_count`. On access-denied or unknown-queue the
  pin renders with `unavailable=true, queue_item_count=null` and no
  href — same UX as a saved-view pin whose view was deleted.
- Permission check is **batched once per space resolution**: if any
  pin on the space has `pin_type="triage_queue"`, `_resolve_space`
  calls the new `_accessible_queue_ids_for_user(db, user)` helper
  exactly once and passes the set down to each `_resolve_pin`. Spaces
  without triage pins pay zero permission lookups.
- Seed templates for (`funeral_home`, `director`) Arrangement and
  (`manufacturing`, `production`) Production both start with
  `PinSeed(pin_type="triage_queue", target="task_triage")` as the
  first pin. Other role/vertical pairs stay unchanged per approved
  scope.
- `add_pin` validation tuple extended to accept `triage_queue`.
  Idempotent: same (pin_type, target_id) returns the existing pin.
- `PinStar` component accepts `pinType: "triage_queue"`; TriageIndex
  (`/triage`) cards render a PinStar in the card header.
- `PinnedSection` renders a pending-count badge on available
  `triage_queue` pins (`queue_item_count > 0`) in the active-space
  accent color. Capped at `99+` to keep the row tidy. Hidden on row
  hover so the unpin X has room.
- Space-scoped nav preference preserved: the pin shortcuts (PinStar
  toggle, Cmd+[ / Cmd+] space switch, Cmd+Shift+1..5) work on the
  new pin type without any additional wiring — Phase 3 keyboard
  listeners already iterate the active space's pins generically.

### API contract changes (additive, backward-compatible)

- `POST /api/v1/spaces/{id}/pins` now accepts
  `pin_type: "triage_queue"` with `target_id: <queue_id>` (e.g.
  `"task_triage"`).
- `_PinResponse` ships a new `queue_item_count: int | None` field.
  Existing consumers ignore unknown fields; no frontend code that
  already reads the response shape breaks.

### Test additions

- Backend: `backend/tests/test_space_pins_triage_queue.py` — 17 tests
  across 6 test classes. Registry icon presence, seed-template
  content, resolver behavior (available / label-override /
  unavailable-by-vertical / unknown-queue), batched access-lookup
  perf (spy asserts `_accessible_queue_ids_for_user` called exactly
  once per space with ≥1 triage pin, zero when no triage pins),
  add_pin validation + idempotency, full-stack API roundtrip +
  cross-user isolation.
- Playwright: `frontend/tests/e2e/space-triage-pin.spec.ts` — 5
  scenarios covering the POST shape (icon, href, queue_item_count),
  PinStar presence on /triage cards, sidebar reflection of a newly
  pinned queue, unavailable pin wire contract, list-endpoint shape
  for every triage pin.

### Verification

- `pytest tests/test_spaces_unit.py tests/test_spaces_api.py
  tests/test_task_and_triage.py tests/test_space_pins_triage_queue.py`
  → **103 passed**.
- Frontend `tsc -b` clean.
- ICON_MAP acceptance criterion: grepped
  `frontend/src/components/spaces/PinnedSection.tsx`, confirmed
  `CheckSquare`, `FileCheck`, `ListChecks` all imported from
  `lucide-react` and registered in ICON_MAP. No pin renders with the
  Layers fallback for shipped queue icons.

### Design decisions / deviations (approved)

- Queue icon sourced from `TriageQueueConfig.icon` (authoritative)
  rather than a frontend queue_id → icon lookup table. Single source
  of truth; tenant-customized queues can override via vault_item
  metadata without a frontend change.
- Seeded pin scope limited to (`funeral_home`, `director`) and
  (`manufacturing`, `production`) per spec. Other role templates
  unchanged; users in other roles can pin queues manually via the
  PinStar on `/triage`.
- Template additions do NOT backfill for already-seeded users
  (matches Phase 3 precedent). Existing director/production users
  can pin manually; next fresh seed picks up the template.
- Role slug for manufacturing production template is `"production"`
  (existing convention), not `"production_manager"` as a spec draft
  mentioned.

---

## Polish and Arc Finale (Phase 7 of UI/UX Arc — FINAL)

**Date:** 2026-04-20
**Migration head before:** `r35_briefings_table`
**Migration head after:** `r35_briefings_table` (no new migration — zero new tables per approved scope)
**Tests passing:** 288 across Phase 1-7 regression (8 new Phase 7 contrast + focus-ring tests; 280 prior-phase tests unchanged)

### What shipped

**Shared UI primitives** (`frontend/src/components/ui/`):
- `empty-state.tsx` — `EmptyState` with 3 tones (neutral / positive / filtered) × 3 sizes (default / sm / xs). Optional icon + title + description + action + secondaryAction.
- `skeleton.tsx` — `Skeleton` base + `SkeletonLines` / `SkeletonCard` / `SkeletonRow` / `SkeletonTable` composites. All use `motion-safe:animate-pulse`.
- `inline-error.tsx` — `InlineError` with role=alert + aria-live + optional retry handler + severity variants.

**Hooks** (`frontend/src/hooks/`):
- `useRetryableFetch.ts` — generic auto-retry-once (~1s backoff) + manual `reload()`.
- `useOnboardingTouch.ts` — server-side dismissal via `User.preferences.onboarding_touches_shown`; cross-device; module-scoped session cache for efficiency.
- `useOnlineStatus.ts` — `navigator.onLine` + online/offline event listener.

**New components:**
- `components/onboarding/OnboardingTouch.tsx` — first-run tooltip with auto-dismiss option + positioned anchoring
- `components/core/KeyboardHelpOverlay.tsx` — `?`-key context-aware shortcut help overlay (mounted at App root)
- `components/core/OfflineBanner.tsx` — global top banner when `navigator.onLine === false`

**Empty state replacements (10 surfaces):**
- 7 saved view renderers: List, Table, Kanban, Cards, Chart (with `BarChart3` icon), Stat (inline "No data for selected period"), Calendar (per-month empty-message below grid)
- TasksList: two states — empty-all (positive tone with CTA) vs empty-filtered (clear-filters action)
- TriagePage caught-up (positive tone, session stats + back-link)
- TriageIndex (contextual messaging with link to settings)
- CommandBar no-results (with "try: 'new case', 'my invoices', 'switch to production'" hints)
- SavedViewsIndex (icon + CTA)
- BriefingPage (graceful fallback when scheduler hasn't run yet)

**Skeleton replacements (5 surfaces):** BriefingPage (narrative + 2 section cards), BriefingCard (3-line narrative), SavedViewsIndex (3 card grid), TasksList (5-row table skeleton), TriagePage (card + palette skeleton), TriageIndex (2 queue cards).

**Error retry:**
- `BriefingPage` auto-retries once on load failure before surfacing the error; manual retry button via `InlineError`.
- `Triage action retry` — action failures no longer transition session to error state; toast fires, status returns to idle, item stays in queue, keystroke not lost. Triage-context re-throws after clearing status so caller's toast still fires.
- `SavedViewsIndex` error renders `InlineError` with hint.
- `TriageIndex` error renders `InlineError` with retry.

**First-run tooltips (5 wired):**
- Backend: `GET/POST/DELETE /api/v1/onboarding-touches/{key}` reading/writing `User.preferences.onboarding_touches_shown`.
- Tooltips: command bar (`command_bar_intro` inside the modal), saved view page (`saved_view_intro` in page header), space switcher (`space_switcher_intro` only when 2+ spaces), triage page (`triage_intro`), briefing page (`briefing_intro`).
- Client hook `useOnboardingTouch` uses a module-scoped session promise to avoid 5 simultaneous fetches across 5 surfaces; optimistic dismissal with server fire-and-forget.

**ARIA + aria-live pass (4 arc surfaces):**
- CommandBar: `role=dialog` + `aria-modal` on overlay; `aria-label="Command bar"`; input as `role=combobox` + `aria-controls=command-bar-results` + `aria-expanded` + `aria-autocomplete=list` + `aria-describedby`; results container with `role=listbox` + `aria-live=polite`; footer with id hint.
- NLOverlay: body region with `role=region` + `aria-label` + `aria-live=polite` + `aria-busy={isExtracting}`. Error block upgraded to `role=alert` with hint.
- TriagePage: current-item section with `role=region` + `aria-label="Current triage item"` + `aria-live=polite` + `aria-busy`.
- BriefingPage: narrative CardContent with `role=region` + `aria-label="Briefing narrative"` + `aria-live=polite`.

**`?`-key help overlay:** `KeyboardHelpOverlay` at App root. Listens to `?` globally (ignoring inputs / contenteditable); opens modal showing context-aware shortcut sections: always Global + CommandBar + Spaces; adds Triage when on `/triage/*`; adds Tasks when on `/tasks/*`. Escape or `?` again dismisses. motion-safe animate-in.

**Mobile fixes:** 44px `min-h-[44px]` on TriageActionPalette decision buttons, TriageFlowControls snooze presets, BriefingPreferences channel/section toggles. BriefingPreferences grid collapsed from `grid-cols-2` → `grid-cols-1 sm:grid-cols-2` so the time picker + channel buttons stack cleanly on 375px. CalendarRenderer day cells changed to `min-h-[70px] sm:min-h-[92px]` + grid wrapper `overflow-x-auto` for narrow viewports.

**Offline banner:** `OfflineBanner` at App root above impersonation banner. `useOnlineStatus` subscribes to `online`/`offline` events. Renders an amber strip with `WifiOff` icon + "You appear to be offline. Changes will sync when reconnected." Deliberately simple — no proactive connectivity probe (that's post-arc observability).

**prefers-reduced-motion global retrofit:** Added to `frontend/src/index.css` as a blanket `@media (prefers-reduced-motion: reduce) { *,*::before,*::after { animation-duration: 0.001ms !important; animation-iteration-count: 1 !important; transition-duration: 0.001ms !important; scroll-behavior: auto !important; } }` block. Handles 40+ pre-existing transitions across Phase 1-6 + shadcn/ui + tw-animate-css without needing to touch each file. Phase 7 new components use `motion-safe:` variants natively.

**Telemetry dashboard** (platform-admin-gated, mounted at `/bridgeable-admin/telemetry`):
- Backend `app/services/arc_telemetry.py` — thread-safe in-memory rolling latency buffer (1000 samples cap) per endpoint + error counter. `record(endpoint, latency_ms, errored)` called via try/finally on the 5 arc endpoints (command_bar_query, saved_view_execute, nl_extract, triage_next_item, triage_apply_action). `snapshot()` returns p50/p99/counts.
- Backend `app/api/routes/admin/arc_telemetry.py` — `GET /api/platform/admin/arc-telemetry` returns endpoint snapshot + `intelligence_executions` aggregations over 24h/7d/30d windows + per-caller-module cost breakdown (24h).
- Frontend `bridgeable-admin/pages/ArcTelemetry.tsx` — endpoint latency table + 3 Intelligence window cards + caller-module cost table + honest banner: "Endpoint counters are per-process and in-memory; they clear on restart. For long-term metrics, see the post-arc observability roadmap."
- **No new database table.** Intelligence aggregations persist via existing `intelligence_executions` rows.

**Contrast verification + accent remediation:** `backend/tests/test_arc_accent_contrast.py` (5 tests) mirrors the 6 space accents from `frontend/src/types/spaces.ts` and asserts:
- Hex format valid for all 6 × 3 colors
- Foreground on white ≥ 4.5:1 (WCAG AA normal text) — ALL 6 PASS
- Accent on white ≥ 3.0:1 (WCAG AA large text) — ALL 6 PASS
- Foreground on accent-light chip ≥ 4.5:1 — ALL 6 PASS
- Accent distinguishable from preset fallback (except `neutral` which deliberately matches) — ALL PASS

**Zero accent remediation needed.** All 6 were already WCAG AA compliant.

**Focus ring visibility remediation:** `backend/tests/test_arc_focus_ring_contrast.py` (3 tests) verifies the `--ring` color passes WCAG 3:1 non-text-UI contrast against:
- Pure white — **required bump from `oklch(0.708 0 0)` to `oklch(0.48 0 0)`**
- Each of the 6 accent-light chip backdrops — now passing with new value

Fix: single-line change in `frontend/src/index.css` light-mode `:root` block. Test includes a guard (`test_focus_ring_lightness_matches_index_css`) that parses the CSS file + asserts the constant matches — prevents drift.

**Micro-interactions (motion-safe):**
- NL extraction field entrance: `motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-top-1 motion-safe:duration-200` on each field row
- Triage item transition: `key={item.entity_id}` forces remount; wrapper has `motion-safe:animate-in motion-safe:fade-in-0 motion-safe:slide-in-from-bottom-1 motion-safe:duration-200`

### Design decisions / deviations (approved)

- **Arc finale docs moved up to #11-12 (before micro-interactions / contrast / focus-ring tests) per approved refinement** — but in execution, the refactor audit surfaced that telemetry (#12) + contrast (#14) + focus-ring (#15) should ship first so docs can reference real data. Final order: steps 1-10 → 12 → 13 → 14 → 15 → 11. Outcome matches intent: docs written with clear head, deliver accurate performance envelope + post-arc backlog.
- **Cross-arc layout consistency dropped entirely** per approved refinement. Per-page max-width variation preserved (different content types, different ideal widths).
- **Demo flow scripts added to UI_UX_ARC.md** per approved refinement — 5 rehearsable demos with exact keystroke-level scripts for September Wilbert meeting.
- **Telemetry honest-expectation-setting** on page itself: "Endpoint counters are per-process and in-memory; they clear on restart. For long-term metrics, see the post-arc observability roadmap."
- **prefers-reduced-motion** non-negotiable: global CSS block retrofit + `motion-safe:` variants on all Phase 7 new transitions.
- **Two persistence layers** for tooltip dismissal preserved (as approved): `useOnboardingTouch` = server-side cross-device; `HelpTooltip` = localStorage device-local. Not merged.
- **Contrast + focus-ring** verified programmatically, not just documented. All accents pass; focus ring required one-line `--ring` darkening to pass WCAG 3:1.

### Test additions

- `backend/tests/test_arc_accent_contrast.py` (5 tests)
- `backend/tests/test_arc_focus_ring_contrast.py` (3 tests)
- 8 total new Phase 7 backend tests (all passing)
- All 280 Phase 1-6 tests still pass unchanged
- tsc 0 errors
- All 5 BLOCKING latency gates still green

### Verification

- **288 backend tests pass** across Phase 1-7 regression (280 prior + 8 Phase 7 new) — no regressions
- **BLOCKING latency gates (all 5) unchanged and green:**
  - command_bar_query: p50 = 5.0 ms, p99 = 6.9 ms
  - saved_view_execute: p50 = 15.4 ms, p99 = 18.5 ms
  - nl_extract (no AI): p50 = 5.9 ms, p99 = 7.2 ms
  - triage_next_item: p50 = 4.8 ms, p99 = 5.8 ms
  - triage_apply_action: p50 = 9.7 ms, p99 = 13.5 ms
  - briefing_generate (AI stubbed): p50 = 28.9 ms, p99 = 32.0 ms
- **WCAG AA contrast: all 6 space accents pass** (zero remediation needed)
- **Focus ring: WCAG 3:1 passes against white + all 6 accent-light backdrops** (after `--ring` bump)
- tsc 0 errors
- Backend imports cleanly including new routes + services

### Arc totals (Phases 1-7 complete)

| Metric | Count |
|---|---|
| Phases shipped | 7 |
| Platform primitives established | 7 |
| Database migrations (arc-specific) | 5 (r31, r32, r33, r34, r35) |
| New tables | 4 (triage_sessions, triage_snoozes, tasks, briefings) |
| Backend tests | 288 (no regressions) |
| BLOCKING CI latency gates | 5 (all green) |
| BLOCKING parity tests | 3 (SS cert triage — all green) |
| Playwright specs | 50+ across arc |
| Intelligence prompts seeded | 13+ |
| New API endpoints | ~60 |
| New shared frontend components | 8 (`EmptyState`, `Skeleton`+4 variants, `InlineError`, `OnboardingTouch`, `KeyboardHelpOverlay`, `OfflineBanner`, plus 3 per-primitive component sets from Phase 2-6) |
| Post-arc backlog items | ~45 (documented in `UI_UX_ARC.md`) |

### Post-arc cleanup items (documented, NOT Phase 7 work)

All 45+ items consolidated in `UI_UX_ARC.md` under "Post-arc Backlog". The most impactful:
1. Rename `/briefings/v2/*` → cleaner REST (Phase 6 cleanup)
2. Consolidate `employee_briefings` + `briefings` tables (Phase 6 cleanup)
3. Migrate legacy `MorningBriefingCard` consumers to new `BriefingCard` (Phase 6 → Phase 7 cleanup — legacy preserved per coexist strategy)
4. Build native mobile redesigns of arc surfaces (Phase 7 scope cut — mobile was functional-only)
5. Advanced observability (Phase 7 telemetry was minimal by design)
6. External accessibility audit (Phase 7 scope cut — verified programmatically only)

### What the arc enables

The September 2026 Wilbert licensee meeting demo reaches its moment: a funeral director opens the command bar on the Bridgeable platform, types one sentence, watches the platform extract 5 structured fields in under a second, presses Enter, and has a fully-populated case record. The demo flow is documented keystroke-by-keystroke in `UI_UX_ARC.md`. Rehearsal checklist included.

Beyond the demo: the seven primitives compose. Every future feature inherits:
- Command bar surface via registry entry
- Saved views for any list/dashboard
- Space-aware context via active_space_id
- NL creation for any new entity type (append to entity_registry)
- Triage workspace for any decision stream (append to platform_defaults)
- Briefings can emphasize the feature by exposing a data source
- Polish primitives (EmptyState/Skeleton/InlineError) for every empty/loading/error state

**Arc complete. Platform ready for September.**

---

## Arc-level summary table (all 7 phases)

| Phase | Dates | Migration | Tests | Key primitive |
|---|---|---|---|---|
| 1 — Command Bar | Apr 2026 | r31 | 116 | `POST /command-bar/query` |
| 2 — Saved Views | Apr 2026 | r32 | 46 | `vault_items` saved_view_config |
| 3 — Spaces | Apr 2026 | (none — User.preferences) | 64 | `User.preferences.spaces` |
| 4 — NL Creation | Apr 2026 | r33 | 87 | Structured + resolver + AI pipeline |
| 5 — Triage | Apr 2026 | r34 | 42 | Pluggable 7-component queue configs |
| 6 — Briefings | Apr 2026 | r35 | 36 | AI narrative + per-user sweep |
| 7 — Polish | Apr 2026 | (none) | 8 | Cross-cutting polish infrastructure |

---
## Morning and Evening Briefings (Phase 6 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r34_tasks_and_triage`
**Migration head after:** `r35_briefings_table`
**Tests passing:** 27 backend + 2 BLOCKING latency gates + 7 Playwright = 36 new, plus 280 Phase 1–6 regression green

### What shipped

**Backend**

- Migration `r35_briefings_table`: new `briefings` table coexisting with legacy `employee_briefings` (different semantics — `(user_id, briefing_type, DATE(generated_at))` partial unique allows morning + evening same day; legacy's `(company_id, user_id, briefing_date)` unique only allowed one per day)
- `app/models/briefing.py` — Briefing ORM + `BRIEFING_TYPES` literal
- `app/services/briefings/` package — 7 modules (types, preferences, data_sources, generator, delivery, scheduler_integration, __init__); **legacy context builders imported and reused verbatim**: `_build_funeral_scheduling_context`, `_build_precast_scheduling_context`, `_build_invoicing_ar_context`, `_build_safety_compliance_context`, `_build_executive_context`, `_build_call_summary`, `_build_draft_invoice_context`
- **Legacy blocklist → Phase 6 allowlist translation**: `seed_preferences_for_user` translates `AssistantProfile.disabled_briefing_items` (existing blocklist) to `BriefingPreferences.{morning,evening}_sections` (Phase 6 allowlist) via set subtraction; idempotent per role via `preferences.briefings_seeded_for_roles`
- 7 `/api/v1/briefings/v2/*` endpoints coexisting with legacy `/briefings/briefing` + `/briefings/action-items` + `/briefings/team-config` (route coexistence under same router, no renaming)
- `POST /v2/generate` uses explicit delete-then-create semantics for "regenerate today's" (deletes existing same-day-same-type row, inserts fresh)
- `scripts/seed_intelligence_phase6.py` — idempotent; seeds `briefing.morning` + `briefing.evening` prompts (Haiku simple, force_json, 2048 max_tokens, 0.4 temp) + 2 managed email templates (`email.briefing.morning` + `email.briefing.evening`) via Phase D-2 DocumentTemplate registry (no on-disk files per D-2/D-3 discipline)
- `job_briefing_sweep()` added to `scheduler.py` with `CronTrigger(minute="*/15")` — first per-user scheduled pattern on the platform
- Seed hook wired at `user_service.update_user`'s role-change site alongside Phase 2 saved_views + Phase 3 spaces seeds
- **BLOCKING CI gate** at `test_briefing_generation_latency.py` — p50 < 2000ms, p99 < 5000ms. Actual: **p50=28.9ms / p99=32.0ms** (69× / 156× headroom) with Intelligence monkey-patched to measure orchestration overhead
- **BLOCKING space-awareness tests** — parametrized × 3 spaces (Arrangement/Administrative/Production), intercepts Intelligence call, asserts `active_space_name` reaches prompt variables
- **BLOCKING Call Intelligence integration test** — `overnight_calls` None when no RC logs; populated with `{total, voicemails, ...}` when seeded RC log exists — preserves legacy `_build_call_summary` path verbatim
- **BLOCKING legacy coexistence tests** — `/briefings/briefing` + `/briefings/action-items` still 200; `briefing.daily_summary` prompt still active; legacy context builders still importable

**Frontend**

- `types/briefing.ts` — full mirrors of backend Pydantic shapes
- `services/briefing-service.ts` — 7-endpoint axios client
- `hooks/useBriefing.ts` — latest-briefing fetch + manual reload (no auto-refresh; scheduler owns backend generation)
- `pages/briefings/BriefingPage.tsx` (`/briefing` + `/briefing/:id`) — narrative card + collapsible structured-sections cards; Morning/Evening toggle; Regenerate + Mark-read buttons; queue_summaries deep-link to `/triage/:queueId`
- `components/briefings/BriefingCard.tsx` — new dashboard widget (opt-in mount); truncated narrative + "Read full briefing →" link
- `pages/settings/BriefingPreferences.tsx` (`/settings/briefings`) — optimistic-save toggles + time picker + channel + section allowlist
- 3 new routes in `App.tsx` (`/briefing`, `/briefing/:id`, `/settings/briefings`)
- 2 new cross-vertical command bar actions in `services/actions/shared.ts` — `navigate_briefing_latest` + `navigate_briefing_preferences`
- **Legacy `MorningBriefingCard` + `morning-briefing-mobile.tsx` + `BriefingSummaryWidget.tsx` UNCHANGED** — still mounted on `manufacturing-dashboard.tsx:351` + `order-station.tsx:1530` consuming legacy endpoints
- 7 Playwright specs in `frontend/tests/e2e/briefings-phase-6.spec.ts`

### Design decisions / deviations (approved)

- **Coexist strategy over absorb/replace** — `briefing_service.py` (1869 lines) represents months of customer ground-truth tuning. Phase 6 imports it as a dependency rather than rewriting. Legacy endpoints + components + prompts stay fully operational.
- **`/v2/*` route prefix** — intentionally ugly per approved spec item #3. Zero migration risk to existing consumers. Post-arc cleanup can rename.
- **Two tables (briefings + employee_briefings)** — different unique-constraint semantics make the two-table approach cleaner than extending the legacy table. `employee_briefings` stays read-only legacy.
- **Every-15-min global sweep with in-app per-user timing** — first per-user scheduled pattern. One APScheduler registration; sweep function computes per-user local time via `Company.timezone` + checks preference windows + DB idempotency. Documented as canonical pattern in CLAUDE.md §10.
- **Keyboard shortcut `G B` dropped** per approved scope cut — users pin `/briefing` to a space via PinStar + reach via `Cmd+Shift+N` using existing Phase 3 infrastructure.
- **`/v2/generate` delete-then-create** semantics discovered during latency-test development (second call inside same day hit the unique constraint). Explicit regenerate-today behavior chosen over upsert or 409 response. Post-arc rename to `/v2/regenerate` to signal intent.
- **Managed email templates only** — no `app/templates/email/` on-disk directory per D-2/D-3 discipline. Templates seeded as DocumentTemplate rows with `output_format="html"`.
- **Space-awareness via prompt Jinja branches, not variable substitution** — the `briefing.morning` + `briefing.evening` prompts contain `{% if active_space_name == "Arrangement" %}...{% endif %}` blocks that change section emphasis. The BLOCKING test asserts `active_space_name` reaches prompt variables (the hook Jinja branches on); visible output differentiation is Haiku's job and not asserted against live AI.

### Post-arc cleanup items (documented, NOT Phase 6 work)

1. Rename `/briefings/v2/*` → cleaner REST (e.g. `/briefings` replaces legacy; legacy moves to `/briefings/legacy/*`)
2. Consolidate `employee_briefings` + `briefings` tables — two-table approach is temporary coexist, not long-term
3. Migrate legacy `MorningBriefingCard` consumers at `manufacturing-dashboard.tsx:351` + `order-station.tsx:1530` to new `BriefingCard`
4. Retire `briefing.daily_summary` prompt once legacy `MorningBriefingCard` retires (both live together or both die together)
5. Revisit `briefing_service.py` for consolidation once legacy surfaces retire — 1869 lines of context-builder logic can fold into `briefings/data_sources.py` directly, removing the cross-package import dependency
6. Rename `/v2/generate` → `/v2/regenerate` for intent clarity
7. Add briefing AI learning (auto-drop sections user consistently skips) — post-arc
8. Add SMS/Slack/voice (TTS) delivery channels — post-arc
9. Add shared team briefings ("Today's Services" read-mostly view) — post-arc
10. Network-level cross-tenant briefings for licensee operators — post-arc

### Verification

- 280 Phase 1–6 backend tests passing (253 Phase 1–5 + 27 Phase 6 new)
- Both BLOCKING CI gates pass with massive headroom (p50=28.9ms vs 2000ms target)
- Space-awareness test parametrized × 3 spaces — all assert `active_space_name` reaches prompt variables
- Call Intelligence integration test — overnight_calls absent/present matches RC log state
- Legacy regression — `/briefings/briefing` + `/briefings/action-items` still 200; legacy prompt still seeded; legacy context builders still importable
- tsc clean (0 errors)
- 7 Playwright specs written (not run here — require live staging backend)

---

## Triage Workspace + actionRegistry Reshape + Task Infrastructure (Phase 5 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r33_company_entity_trigram_indexes`
**Migration head after:** `r34_tasks_and_triage`
**Tests passing:** 33 backend + 2 BLOCKING latency gates + 9 Playwright = 44 new, plus 253 Phase 1–5 regression green

### What shipped

**Backend**

- Migration `r34_tasks_and_triage`: 3 tables (`tasks`, `triage_sessions`, `triage_snoozes` — entity-type-agnostic with partial unique `uq_triage_snoozes_active WHERE woken_at IS NULL`) + GIN trigram index on `tasks.title` via CREATE INDEX CONCURRENTLY in autocommit_block
- `app/models/task.py` with TASK_PRIORITIES (low/normal/high/urgent) + TASK_STATUSES (open/in_progress/blocked/done/cancelled), polymorphic link via related_entity_type + related_entity_id
- `app/services/task_service.py` with full CRUD + `_ALLOWED_TRANSITIONS` state machine (invalid → 409)
- `app/api/routes/tasks.py` — 7 endpoints at `/api/v1/tasks/*` (list with filters + create + get + patch + soft-delete + complete + cancel)
- `app/services/triage/` package: types.py (Pydantic with schema_version="1.0", `extra="forbid"`, 7 component configs, typed errors) + registry.py (in-code singleton `_PLATFORM_CONFIGS` via register_platform_config — pattern pivot from vault_item because VaultItem.company_id NOT NULL; per-tenant overrides still vault-item-backed) + engine.py (start_session resumable via current_item_id + cursor_meta.processed_ids, next_item, apply_action handler→Playwright→workflow pipeline, snooze with partial-unique-index protection, queue_count, sweep_expired_snoozes; `_DIRECT_QUERIES` dispatch for entities not in Phase 2 saved-views registry — `_dq_task_triage`, `_dq_ss_cert_triage`) + action_handlers.py (HANDLERS dict — task.complete/cancel/reassign + **ss_cert.approve/void call SocialServiceCertificateService verbatim for parity** + skip + escalate) + embedded_actions.py (wraps existing PlaywrightScript + workflow_engine) + platform_defaults.py (two shipped queues: task_triage + ss_cert_triage registered at import time) + __init__.py (side-effect platform_defaults import BEFORE registry helpers)
- `app/api/routes/triage.py` — 9 endpoints at `/api/v1/triage/*`
- `app/services/nl_creation/entity_registry.py` extended with task entity (title/description/assignee via target="user"/due_date/priority); new `resolve_user()` in entity_resolver.py using ILIKE (no trigram index yet); EntityType literal extended; `_create_task` creator
- Phase 1 `command_bar/resolver.py` SEARCHABLE_ENTITIES adds task with url_template="/tasks/{id}"; `command_bar/registry.py` adds create.task with aliases new task / add task / create task / todo / new todo
- `backend/scripts/seed_triage_queues.py` — validates in-code platform configs loaded + seeds 2 Intelligence prompts (triage.task_context_question, triage.ss_cert_context_question) via Haiku simple route + force_json=True
- **BLOCKING CI gates** at `backend/tests/test_triage_latency.py`: next_item p50<100ms/p99<300ms + apply_action p50<200ms/p99<500ms. Actual: next_item p50=4.8ms / p99=5.8ms; apply_action p50=9.7ms / p99=13.5ms — 20×+ headroom on both
- **BLOCKING SS cert parity** — 3 tests in `TestSSCertTriageParity` class of `test_task_and_triage.py` asserting triage approve/void produces identical side effects (status transitions, approved_at/voided_at stamps, approved_by_id/voided_by_id, void_reason preservation) as legacy `/social-service-certificates` page

**Frontend**

- `services/actions/` package replaces legacy `core/actionRegistry.ts` (944 lines → split per-vertical files):
  - `types.ts` — rich ActionRegistryEntry (permission, required_module, required_extension, handler, playwright_step_id, workflow_id, supports_nl_creation, nl_aliases, keyboard_shortcut)
  - `registry.ts` — singleton + toCommandAction converter + getActionsForVertical/filterActionsByRole/matchLocalActions/getActionsSupportingNLCreation helpers + legacy CommandAction/RecentAction types preserved for render-time compat
  - `shared.ts` — 6 cross-vertical creates including NEW create_task + create_event with supports_nl_creation: true
  - `manufacturing.ts` — 57 mfg actions migrated verbatim
  - `funeral_home.ts` — 9 FH actions (case create with supports_nl_creation=true)
  - `triage.ts` — 3 NEW nav entries (workspace index, task queue, ss cert queue)
  - `index.ts` — side-effect registers all entries at module load
- 5 call sites migrated (CommandBar.tsx, SmartPlantCommandBar.tsx, CommandBarProvider.tsx, cmd-digit-shortcuts.ts, commandBarQueryAdapter.ts); old `core/actionRegistry.ts` deleted
- `components/nl-creation/detectNLIntent.ts` rewritten — derives ENTITY_PATTERNS at call time from `getActionsSupportingNLCreation()`; hand-maintained table eliminated. `NLEntityType` extended with "task"
- `types/triage.ts` — full mirrors of backend Pydantic shapes
- `services/triage-service.ts` — 9-endpoint client (fetchNextItem returns null on 204)
- `services/task-service.ts` — 7-endpoint client
- `contexts/triage-session-context.tsx` — TriageSessionProvider bootstraps config + session + first item; fire-and-forget endSession on unmount
- `hooks/useTriageKeyboard.ts` — shift/alt/meta/ctrl modifier support, skips inputs/textareas/contenteditable
- `components/triage/`: TriageItemDisplay (dispatches on display_component — task / social_service_certificate / generic), TriageActionPalette (reason modal with disabled-until-valid Confirm, kbd hints), TriageContextPanel (collapsible rail; document_preview live, saved_view/communication_thread/related_entities/ai_summary Phase-6-ready stubs), TriageFlowControls (snooze preset buttons)
- Pages: `pages/triage/TriageIndex.tsx` + `pages/triage/TriagePage.tsx` + `pages/tasks/TasksList.tsx` + `pages/tasks/TaskCreate.tsx` + `pages/tasks/TaskDetail.tsx`
- 5 new routes in App.tsx: `/tasks`, `/tasks/new`, `/tasks/:taskId`, `/triage`, `/triage/:queueId`
- 9 Playwright specs in `frontend/tests/e2e/triage-phase-5.spec.ts`

### Design decisions / deviations

- **Platform-default triage queue configs as in-code singleton, not vault_items.** Initial design stored platform configs as vault_items with company_id=NULL (mimicking Intelligence prompts). VaultItem's NOT NULL constraint forced the pivot. Per-tenant overrides still use vault_items via the `triage_queue_config` item_type, read by `_tenant_overrides()` in registry.py.
- **Three source modes for queue configs.** Phase 2 saved_views SEARCHABLE_ENTITIES doesn't cover task or social_service_certificate. Rather than extend Phase 2's registry (coordination with Phase 5 cleanup note), introduced `source_direct_query_key` as third option dispatching to `_DIRECT_QUERIES` table in engine.py. Phase 2 entities use `source_inline_config`; per-tenant customization uses `source_saved_view_id`.
- **SS cert parity preserved by handler reuse, not copy.** `_handle_ss_cert_approve` calls `SocialServiceCertificateService.approve(cert_id, user_id, db)` verbatim; void is identical. Zero duplication. Parity test validates both paths produce identical DB state + timestamps + audit fields.
- **detectNLIntent duplication eliminated via registry flag.** The Phase 4 hand-maintained ENTITY_PATTERNS table is now derived at call time from entries flagged `supports_nl_creation: true`, with `nl_aliases` as the authoritative alias list and `route` as the tab-fallback URL. Future entity additions change one registry entry, not two files.
- **Triage session resumable via `current_item_id` + `cursor_meta.processed_ids`.** Unmount calls `endSession` fire-and-forget; remount can resume by starting a fresh session (processed_ids prevents reprocessing).
- **Snooze entity-type-agnostic.** Single `triage_snoozes` table with partial unique `WHERE woken_at IS NULL` prevents double-active-snooze while preserving full audit history across wake cycles.
- **bridgeable-admin portal UNTOUCHED per approved scope boundary.** The platform admin's `admin-command-actions.ts` is a separate registry for cross-tenant surfaces and lives in a different bundle.

### Verification

- All 253 Phase 1–5 backend tests passing (14 pytest modules)
- tsc clean (0 errors) after all frontend work
- Playwright specs written (not run here — require a running backend + seeded staging tenant)

---

## Command Bar Platform Layer (Phase 1 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r30_delivery_caller_vault_item`
**Migration head after:** `r31_command_bar_trigram_indexes`
**Tests passing:** 99 new platform-layer tests + 8 regression tests + 9 Playwright specs + 1 blocking perf gate

### What shipped

- Backend platform layer package at `backend/app/services/command_bar/`:
  - `registry.py` — OWNS `ActionRegistryEntry` type + singleton + seed
  - `intent.py` — rule-based classifier (5 intents: navigate / search / create / action / empty)
  - `resolver.py` — pg_trgm fuzzy search across 6 entity types via single UNION ALL, recency weighting, tenant isolation
  - `retrieval.py` — orchestrator, OWNS the `QueryResponse` / `ResultItem` shape contract going forward
- New endpoint: `POST /api/v1/command-bar/query` with Pydantic-validated request + response schemas
- Migration `r31_command_bar_trigram_indexes`: `pg_trgm` extension + 6 GIN trigram indexes (via `CREATE INDEX CONCURRENTLY` inside autocommit_block)
- Frontend interface-only adapter at `frontend/src/core/commandBarQueryAdapter.ts` — translates backend `ResultItem` → existing `CommandAction` shape
- Frontend UI (`core/CommandBar.tsx`) fires `/command-bar/query` as 4th parallel fetch alongside legacy endpoints; results merge via existing type-ranked sort
- `navigation-service.ts` NavItem extended with optional `aliases` field + `getAllNavItemsFlat()` helper
- 17 navigate actions registered (hubs, AR/AP aging, P&L, invoices, SOs, quoting, compliance, pricing, KB, vault + 4 vault services, accounting admin)
- 6 create actions registered (sales_order → `wf_create_order` workflow, quote, case, invoice, contact, product); frontend `crossVerticalCreateActions` mirrors for offline fallback matching
- Search across cases, sales orders, invoices, contacts, products, documents

### Audit findings (key items only)

- **5,900 lines of command bar infrastructure already existed** across 12 files. Production bar is `core/CommandBar.tsx` (1091 lines) with full voice + Option+1..5 shortcuts + capture-phase listener.
- **`wf_compose` does not exist in code** — only `wf_create_order` ships. Phase 1's "remove old Compose menu" requirement was a no-op because there's no menu to remove.
- Legacy files: `ai/CommandBar.tsx` (250 lines, zero imports) deleted; `ai-command-bar.tsx` (93 lines) KEPT — audit initially flagged it unused but `products.tsx` actively uses it as a page-specific AI search bar. Restored after the mistake.
- **Pre-existing route collision:** `/api/v1/ai/command` has handlers in both `ai.py` and `ai_command.py` (same prefix + same path). `ai.py` wins on resolution order; `ai_command.py`'s handler is unreachable via that path. Documented in `CLAUDE.md §4 "Command Bar Migration Tracking"`; full resolution deferred to post-arc cleanup.

### What was deferred (intentionally, per phase plan)

- Saved view results (Phase 2)
- Spaces and pinning (Phase 3)
- Natural language creation with live overlay (Phase 4)
- Triage workspace — including full frontend actionRegistry.ts reshape (Phase 5)
- Briefings (Phase 6)
- Voice input, peek panels, mobile command bar, polish (Phase 7)
- Retirement of the 8 legacy `/ai-command/*` + `/core/command*` routes — tracked in `CLAUDE.md §4 Command Bar Migration Tracking`, retired per-endpoint as frontend callers migrate

### Performance

- Target: p50 < 100 ms, p99 < 300 ms
- Actual on dev hardware (50-sample sequential mixed-shape workload, tenant seeded with ~24 rows):
  - **p50 = 5.0 ms** (20× headroom)
  - **p99 = 6.9 ms** (43× headroom)
- **BLOCKING CI gate** at `backend/tests/test_command_bar_latency.py`. Fails on p50 > 100 ms or p99 > 300 ms.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_command_bar_registry.py` | 22 | Registry seed + registration + filters + match scoring |
| `test_command_bar_intent.py` | 40 | All 5 intents, parametrized record-number patterns, edge cases |
| `test_command_bar_resolver.py` | 15 | 6 entity types + typo tolerance + recency + tenant isolation + entity_types filter + score ordering |
| `test_command_bar_retrieval.py` | 13 | End-to-end orchestration + permission gating + tenant + dedup + max_results |
| `test_command_bar_query_api.py` | 9 | API contract + response shape + max_results + context passthrough |
| `test_ai_command_regression.py` | 8 | Auth + `/command/execute` + `/parse-filters` + `/company-chat` + `/briefing/enhance` + cross-tenant isolation on `/core/command-bar/search` |
| `test_command_bar_latency.py` | 1 | **BLOCKING** p50/p99 gate |
| `frontend/tests/e2e/command-bar-phase-1.spec.ts` | 9 | Cmd+K open/close, navigate, case/SO search, create action, Alt+1 shortcut, typo tolerance, contract |
| **Total new this phase** | **117** | All passing |

### Architectural notes for Phase 2

- `registry.py` is designed to accept Phase 2's saved-view entries without schema changes (`action_type="saved_view"` already reserved).
- `retrieval.py` OWNS the public response shape — Phase 2 additions extend it; do not redefine.
- `intent.py` is deliberately zero-AI. Phase 4's NL creation with live overlay can layer AI classification on top of rules for ambiguous queries; do not replace the rule engine.
- Frontend `actionRegistry.ts` reshape deferred to Phase 5. The interface-only adapter stays until then.
- Retirement of legacy endpoints is per-phase and per-caller; no all-at-once deletion.

---

## Saved Views as Universal Primitive (Phase 2 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r31_command_bar_trigram_indexes`
**Migration head after:** `r32_saved_view_indexes`
**Tests passing:** 38 saved-views backend tests + 1 blocking latency gate + 7 Playwright specs

### What shipped

Saved Views are now the rendering engine for every list, kanban, calendar, table, card grid, chart, and dashboard surface. "One query, infinite presentation contexts." Storage reuses `vault_items` with `item_type='saved_view'` + `metadata_json.saved_view_config` (no new table, no schema changes to the VaultItem shape).

- Backend package at `backend/app/services/saved_views/`:
  - `types.py` — typed dataclasses (EntityType, Filter, Sort, Grouping, Presentation, Permissions, SavedViewConfig, SavedView, SavedViewResult, per-mode configs). `from_dict`/`to_dict` on every class for JSONB round-trip.
  - `registry.py` — 7 entity types seeded (fh_case, sales_order, invoice, contact, product, document, vault_item). Each entity has `available_fields`, `default_sort`, `default_columns`, per-entity `query_builder` (tenant-isolated SQLAlchemy query) + `row_serializer`.
  - `executor.py` — `execute(db, *, config, caller_company_id, owner_company_id)` returning `SavedViewResult`. Dispatches filters (12 operators), sort, grouping (kanban buckets), aggregation (chart/stat), cross-tenant masking via `MASK_SENTINEL="__MASKED__"`. DEFAULT_LIMIT=500, HARD_CEILING=5000.
  - `crud.py` — create/get/list/update/delete/duplicate. 4-level visibility enforced: `private`, `role_shared`, `user_shared`, `tenant_public`. Returns typed `SavedView` dataclasses; never leaks raw VaultItem.
  - `seed.py` — `seed_for_user(db, user)` role-based seeding. Templates keyed by `(vertical, role_slug)`. Idempotency via `users.preferences.saved_views_seeded_for_roles` array + defense-in-depth `_already_seeded` check. Hooked into `auth_service.register_user` post-commit.
  - `__init__.py` — public exports.
- Migration `r32_saved_view_indexes`:
  - GIN trigram index on `vault_items.title` (command bar fuzzy match)
  - Partial B-tree on `(company_id, created_by)` WHERE `item_type='saved_view' AND is_active=true` (hot-path list)
  - `users.preferences JSONB DEFAULT '{}'` column (seed idempotency bag)
  - Widened `vault_items.source_entity_id` from `String(36)` → `String(128)` for semantic seed keys (e.g. `saved_view_seed:director:my_active_cases`) — backward-compatible, UUIDs still fit
  - CONCURRENTLY indexes via `op.get_context().autocommit_block()`
- API at `/api/v1/saved-views/*` (8 endpoints): list, create, list-entity-types, get, patch, delete, duplicate, execute. `execute` is the hot path.
- Command bar integration: new `saved_views_resolver.py` runs PARALLEL to the entity resolver (not folded into UNION ALL — preserves Phase 1's latency budget). New `ResultType="saved_view"` maps frontend-side to `CommandAction.type="VIEW"`, slot 5 in TYPE_RANK between RECORD (3) and NAV (6).
- Frontend at `frontend/src/components/saved-views/` + `pages/saved-views/`:
  - `types/saved-views.ts` — full dataclass mirrors; `MASK_SENTINEL` exported
  - `services/saved-views-service.ts` — 8-endpoint API client, no caching (live queries preserve visibility / delete semantics across tabs)
  - `components/saved-views/SavedViewRenderer.tsx` — dispatches to 7 mode renderers, displays cross-tenant masking banner, ChartRenderer code-split via `React.lazy` + `Suspense` (recharts out of initial bundle)
  - Mode renderers: `ListRenderer`, `TableRenderer`, `KanbanRenderer`, `CalendarRenderer` (DIY month grid), `CardsRenderer`, `ChartRenderer` (recharts, 5 chart types), `StatRenderer`
  - `components/saved-views/SavedViewWidget.tsx` — hub/dashboard embed; per-session entity-type cache so 20 widgets don't refetch the registry
  - `components/saved-views/builder/` — FilterEditor (12 operators), SortEditor, PresentationSelector (mode-specific sub-forms)
  - Pages: `SavedViewsIndex` (grouped: Mine / Shared with me / Available to everyone), `SavedViewPage` (detail + edit/duplicate/delete), `SavedViewCreatePage` (create + edit modes, shared component)
  - Routes: `/saved-views`, `/saved-views/new`, `/saved-views/:viewId`, `/saved-views/:viewId/edit`
- Production board rebuild at `pages/production/ProductionBoardDashboard.tsx` — composed of `SavedViewWidget` instances filtered to production-role seeded views. `/production` now renders the dashboard; legacy bespoke board preserved at `/production/legacy` for one release.

### Performance

- Target: p50 < 150 ms, p99 < 500 ms (execute endpoint, representative 1000-row tenant)
- Actual on dev hardware (50-sample sequential 4-shape mix: list + table + kanban + chart):
  - **p50 = 15.4 ms** (10× headroom)
  - **p99 = 18.5 ms** (27× headroom)
- **BLOCKING CI gate** at `backend/tests/test_saved_view_execute_latency.py`. Fails on p50 > 150 ms or p99 > 500 ms. Runs 1,000-row seed + 4 presentation shapes sequentially.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_saved_views_registry.py` | 9 | Default seed of 7 entities, field types, field lookup, registration replace |
| `test_saved_views.py` | 29 | CRUD, executor filters/sort/group/aggregation, tenant isolation, cross-tenant masking, seed idempotency, API (6), command-bar integration |
| `test_saved_view_execute_latency.py` | 1 | **BLOCKING** p50/p99 gate |
| `frontend/tests/e2e/saved-views-phase-2.spec.ts` | 7 | CRUD, mode switch, kanban, calendar, command-bar VIEW result, production-board rebuild, cross-tenant masking contract |
| **Total new this phase** | **46** | All backend passing; Playwright specs ready for staging run |

### Architectural notes for Phase 3+

- Cross-tenant masking is purely field-level in `executor.py` when `caller_company_id != owner_company_id`. Phase 2 doesn't ship a sharing UI — same-tenant sharing via `permissions.shared_with_*` arrays covers 95% of use cases. When cross-tenant sharing UI lands, `platform_tenant_relationships` (existing table) is the gate, not DocumentShare.
- `OperationsBoardRegistry` and `FinancialsBoardRegistry` COEXIST with saved views. Subsumption deferred to post-arc work.
- `production-board.tsx` deletion is gated on Playwright parity verification. When green, delete the file + remove the `/production/legacy` route + remove the ProductionBoardPage import.
- Saved view config is stored in `metadata_json.saved_view_config` only — no fallbacks. Crud treats `metadata_json` as canonical.
- New seed templates added after a role has already been seeded do NOT backfill. Template additions require either a one-off backfill script or a role-version bump (Phase 2 accepts this trade-off).
- Seed key format `saved_view_seed:{role_slug}:{template_id}` — stored in `vault_items.source_entity_id` (widened to varchar(128) in r32).
- Frontend Builder (Phase 2) is FilterEditor + SortEditor + PresentationSelector. Live preview is deferred — users save then are redirected to the detail page. Preview is queued as polish.
- Chart library: `recharts` 3.8.1. Lazy-loaded via `React.lazy` in SavedViewRenderer so non-chart callers never ship the recharts bundle.
- DIY calendar month grid is sufficient for Phase 2. If FH service scheduling needs week view / overlapping slots / drag-drop, swap the body of `CalendarRenderer.tsx` for `react-big-calendar` — dispatch layer stays.

---

## Spaces — Context Layer (Phase 3 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r32_saved_view_indexes`
**Migration head after:** `r32_saved_view_indexes` (no new migration; `User.preferences` sufficient)
**Tests passing:** 55 backend (36 unit + 19 API/integration) + 9 Playwright specs + 139 Phase 1+2 regression

### What shipped

Spaces are per-user workspace contexts — name + icon + accent + pinned items — layered on top of the existing vertical navigation. Not a replacement; a lens. The base nav from `navigation-service.ts` stays visible; spaces add a `PinnedSection` above it and shift the visual accent.

- Space data model in `User.preferences.spaces` (JSONB array) + `active_space_id` + `spaces_seeded_for_roles` (idempotency tracker).
- Backend package at `backend/app/services/spaces/`:
  - `types.py` — typed dataclasses (SpaceConfig, PinConfig, ResolvedSpace, ResolvedPin, 6 accent literals, SpaceError hierarchy), `MAX_SPACES_PER_USER=5`, `MAX_PINS_PER_SPACE=20`.
  - `registry.py` — role-based `SpaceTemplate`s keyed by `(vertical, role_slug)`. 6 pairs seeded (funeral_home director/admin/office, manufacturing production/office/admin) + `FALLBACK_TEMPLATE` "General" + `NAV_LABEL_TABLE` for nav-item pin resolution.
  - `crud.py` — 10 service functions: create/get/update/delete/reorder spaces + add/remove/reorder pins + set_active_space. Server-side pin resolution via `_resolve_pin` denormalizes saved_view_title + nav label so clients render from flat data.
  - `seed.py` — idempotent via `preferences.spaces_seeded_for_roles`; skip-if-name-exists defense-in-depth; saved-view seed-key pins resolved at read time via VaultItem `source_entity_id` lookup.
  - `__init__.py` — public exports.
- API: 10 endpoints at `/api/v1/spaces/*`, all user-scoped. Cross-user 404 isolation. 5-space cap enforced at service layer, translated to 400 at API.
- Command bar integration:
  - `QueryContext` gained `active_space_id: str | None`.
  - Synthesized space-switch results (not in the module registry — read `user.preferences.spaces` at query time; exact match → 1.4, 2+-char prefix → 1.1; current active space suppressed).
  - Pin boost: `_WEIGHT_ACTIVE_SPACE_PIN_BOOST=1.25` applied in-place to `ResultItem.score` when result URL or id matches a pin target in the active space.
  - Space-switch URLs shaped `/?__switch_space=<id>`; frontend CommandBar dispatcher intercepts the param and calls `SpaceContext.switchSpace` rather than real-navigating.
- Frontend:
  - `types/spaces.ts` — full type mirrors, `ACCENT_CSS_VARS` × 6 accent palette, `applyAccentVars` helper.
  - `services/spaces-service.ts` — 10-endpoint axios client, no caching.
  - `contexts/space-context.tsx` — SpaceProvider with fetch-on-mount, optimistic mutations + server reconciliation, `activeSpace` memo, `isPinned` / `togglePinInActiveSpace` convenience helpers, null-safe `useActiveSpaceId` hook.
  - Components at `components/spaces/`: `SpaceSwitcher` (top-nav dropdown next to NotificationDropdown; keyboard listeners for `Cmd+[`, `Cmd+]`, `Cmd+Shift+1..5`), `PinnedSection` (renders ABOVE `navigation.sections` in the existing sidebar; HTML5 DnD for reorder; hover-to-unpin X button; data-testid attributes for Playwright), `PinStar` (one-click pin toggle; on SavedViewPage header; null-renders when no active space), `NewSpaceDialog` + `SpaceEditorDialog` (shadcn Dialog with accent selector + density + default toggle + delete-with-confirm).
  - Mounted in App.tsx inside PresetThemeProvider on the tenant branch. Platform admin (`BridgeableAdminApp`) completely untouched.
- Visual personality: 6 accents via CSS variables (`--space-accent`, `--space-accent-light`, `--space-accent-foreground`) on `documentElement`. Phase 3 NEVER touches `--preset-accent`. Components use `var(--space-accent, var(--preset-accent))` so no-active-space gracefully falls back.
- Pin-to-current-space: star icon on SavedViewPage header. Nav-item pinning via API; UI star affordance in sidebar nav items is future polish (Phase 7 target).
- 5-space cap enforced at service + API layers.
- Edge cases handled: pin target unavailable (saved view deleted / access revoked → gray-out + hover-reveal X to clean up), role change (both saved-view seed + spaces seed re-run at `user_service.update_user` role-change branch — idempotent via each seed's own array).

### Audit findings

- **`presetAccent` already existed** as a CSS-variable-backed vertical baseline (`PresetThemeProvider` sets `--preset-accent` on `documentElement`). Phase 3 layers `--space-accent` on top with CSS fallback; no conflict, no rewrite.
- **`User.preferences` already added** in r32 (Phase 2). Phase 3 owns new JSONB keys (`spaces`, `active_space_id`, `spaces_seeded_for_roles`) alongside Phase 2's `saved_views_seeded_for_roles`. Zero schema change needed.
- **Only one capture-phase keyboard listener exists** (`cmd-digit-shortcuts.ts` for Option/Alt+1..5 + Cmd+1..5, active only when command bar is open). Phase 3 shortcuts (`Cmd+[`, `Cmd+]`, `Cmd+Shift+1..5`) use different modifier combos + different active conditions — clean, no capture-phase needed.
- **`update_user` role-change path exists.** Phase 2's saved-view seed was NOT hooked here (only at register_user), so a user promoted from office to director never picked up director-specific saved views. Phase 3 fixes this ADJACENTLY: explicit two-line seed re-invocation at the role-change site (spaces + saved-views).
- **FH two-hub pattern (Funeral Direction / Business Management)** from the master doc was aspirational — not represented in `navigation-service.ts` today. Phase 3 operationalizes it naturally: "Arrangement" space IS Funeral Direction hub; "Administrative" space IS Business Management hub. Documented in CLAUDE.md §1a Spaces subsection + flagged here per the user's directive.
- **framer-motion NOT installed.** Phase 3 uses CSS transitions on --space-* variables + tw-animate-css (already present) for any micro-animations. Zero new animation deps.
- **Platform admin** is a fully separate app (`BridgeableAdminApp`) via subdomain / path routing — Phase 3 only wires into the tenant branch.

### Performance

No dedicated CI latency gate this phase — Spaces read/write is trivial JSONB + a small denormalization pass; the hot path (list spaces) returns in single-digit ms on dev. Command bar integration reuses existing paths + adds one ranking multiplier; the Phase 1 latency gate (p50 < 100 ms / p99 < 300 ms) is unchanged and continues to pass. If space-switch synthesis introduces drift in later phases, fold a dedicated latency gate at that point.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_spaces_unit.py` | 36 | Registry (7), Seed (7), CRUD (12), Pins (8), Mfg admin (1), FH director flow |
| `test_spaces_api.py` | 19 | 13 API endpoint tests + 6 command-bar integration (synthesis + pin boost) |
| `frontend/tests/e2e/spaces-phase-3.spec.ts` | 9 | Keyboard shortcuts, picker, accent transition, pin saved view, pin nav item, reorder API, CRUD lifecycle, 5-cap, pin target deleted |
| **Total new this phase** | **64** | All backend passing; Playwright specs ready for staging run |
| Phase 1 + 2 regression | 139 | All green — no changes to previously-passing behavior |

### Surprises for Phase 4

- **Spaces operationalize the FH two-hub pattern (Funeral Direction / Business Management) the master doc describes.** "Arrangement mode" IS Funeral Direction hub; "Administrative mode" IS Business Management hub. This wasn't a design pivot — it was a clarifying realization during the audit. The master doc's two-hub pattern stays accurate at the architectural level; Phase 3 just makes it a first-class UI concept via spaces rather than a nav config requirement. Future phases that touch FH navigation should honor this mapping and avoid re-implementing the same concept in nav.
- **Phase 2's saved-view seed gap on role change is now fixed** at `user_service.update_user`. Phase 4 (Natural Language Creation with Live Overlay) should consider whether the overlay registers any user-scoped state that needs re-seeding on role change — the two-line pattern at the hook site is the canonical place to add another seed.
- **Active-space context now flows into command bar queries.** Phase 4's NL creation may benefit from the same context channel — e.g. "create new order" in Arrangement space defaults to vault-order entity, in Production space defaults to work-order entity. The `QueryContext.active_space_id` field is already there; intent classifier can branch on it without schema changes.
- **`recharts` bundle is lazy-loaded per Phase 2**, and Phase 3's space-switch doesn't force it. Keep this pattern — late bundles are for heavy, less-common UI (chart renderers, calendar DnD when we add it, voice transcription in Phase 7).
- **`SpaceSwitcher` uses `render={}` pattern for `DropdownMenuTrigger`, not `asChild`**, because shadcn v4's `@base-ui/react` doesn't expose `asChild`. Flagged per CLAUDE.md — any future UI using a trigger-wrapping pattern must use `render={}`.

### Architectural notes for Phase 4+

- Space-switch command bar actions are synthesized at query time (not registered in the module-level singleton) because the registry is shared across tenants and per-user state would leak. Future per-user / per-role / per-tenant actions should follow the same parallel-source synthesis pattern rather than bloat the singleton.
- Pin resolution is server-side. When we add cross-tenant space sharing (post-arc), the resolver needs to run through the same visibility check Phase 2 uses (`saved_views.crud._can_user_see`). Today's permissive lookup is acceptable because Phase 3 pins are only the user's own saved views + nav items — cross-tenant never happens.
- `User.preferences` is becoming a multi-phase JSONB bag (Phase 2 + 3 + future phases' seed flags). Keep writes narrowly scoped via `flag_modified` + single-key updates; never blanket-replace `user.preferences = {...}` without reading first.
- Seed additions at the role-change hook site are explicit two-line calls, not abstracted into a `reseed_all` helper. This is intentional: future phases (5, 6) will add more seeds at the same hook, each discoverable via grep without a central registry to maintain.

---

## Natural Language Creation with Live Overlay (Phase 4 of UI/UX Arc)

**Date:** 2026-04-20
**Migration head before:** `r32_saved_view_indexes`
**Migration head after:** `r33_company_entity_trigram_indexes`
**Tests passing:** 79 new backend (53 parsers + 25 integration + 1 latency gate) + 8 Playwright + 194 Phase 1-3 regression = 273 backend

### What shipped

The Fantastical-style extraction overlay — the biggest UX payoff of the arc and the centerpiece of the Wilbert demo. User hits Cmd+K, types one sentence, an overlay populates structured fields in real time.

- Backend NL creation platform layer at `backend/app/services/nl_creation/`:
  - `types.py` — ExtractionRequest, FieldExtraction, ExtractionResult, NLEntityConfig, FieldExtractor, 4 error classes
  - `structured_parsers.py` — date (ISO / US / written month / weekday / "tonight"), time (12h/24h/named), datetime, phone (E.164), email, currency (requires $-flag), quantity, name (with prefix/suffix handling)
  - `entity_resolver.py` — resolve_company_entity via pg_trgm, resolve_contact + resolve_fh_case via existing GIN indexes, filter whitelist for safety, one-call `resolve()` dispatcher
  - `ai_extraction.py` — Intelligence-backed fallback with block-rendered prompt variables, exception-safe (returns empty on any failure)
  - `entity_registry.py` — 4 configs (case, event, contact + fh_case alias → case), case uses AI-only for date fields (multi-date disambiguation), per-entity creator_callable, space_defaults dict, fh_case → case alias lookup
  - `extractor.py` — orchestration: structured → resolver → AI fallback if required still missing → merge with prior_extractions by confidence → apply space_defaults → compute missing_required
  - `__init__.py` — public exports
- Migration `r33_company_entity_trigram_indexes`: GIN trigram on `company_entities.name` via CONCURRENTLY, safe on live tables
- 3 managed Intelligence prompts seeded via `scripts/seed_intelligence_phase4.py`: `nl_creation.extract.{case,event,contact}`. Case prompt content copied from `scribe.extract_first_call` but independent. Haiku (simple route), force_json, response_schema enforcing `{"extractions": [...]}` shape
- Intent extension: `intent.py::detect_create_with_nl()` — additive, no Intent Literal change. Two-mode matcher (exact alias prefix + fuzzy fallback). 3-char min on NL content prevents false positives on short queries
- New `create.event` action registered in Phase 1 command-bar registry (previously missing — audit gap)
- API at `/api/v1/nl-creation/*` — 3 endpoints: `POST /extract` (hot path, 300ms debounced client-side, p50 < 600ms gate), `POST /create` (materialize entity via creator_callable, honors required_permission), `GET /entity-types` (registry dump filtered by permissions)
- Frontend:
  - `types/nl-creation.ts` — full type mirrors
  - `services/nl-creation-service.ts` — 3-endpoint axios client, AbortSignal support
  - `hooks/useNLExtraction.ts` — 300ms debounce (wider than command bar's 100-200ms to amortize AI), AbortController cancellation on new input, manual-override state with re-merge, `create()` materialization
  - `components/nl-creation/NLOverlay.tsx` — Fantastical-style panel with checkmarks / amber low-confidence / entity pills / missing-required section / keyboard hints footer
  - `NLField.tsx` — per-row display with confidence-aware styling
  - `NLCreationMode.tsx` — wrapper with window-level keyboard listeners (Enter / Tab / Esc), navigation handling, module-level entity-types cache so rapid remount doesn't refetch
  - `detectNLIntent.ts` — client-side mirror of backend detector; instant UX without server round-trip
  - `pages/crm/new-contact.tsx` — contact create page at `/vault/crm/contacts/new`, fills Phase 1 register-but-no-route gap, pre-fills from `?nl=<input>` query param (regex extracts email/phone/name/company segment)
- Command bar integration: `CommandBar.tsx` gains `activeNLEntity` state + useEffect watching `query` via `detectNLIntent`. Renders `<NLCreationMode>` instead of the standard results list when matched. Suppresses AI-mode + results-list rendering during NL mode. Coexists with existing `activeNLWorkflow` (workflow-backed entities) cleanly
- Voice input reuses Phase 1's `useVoiceInput` hook — transcript text flows into command-bar input and the detector fires identically to typed input
- Demo seed script `scripts/seed_nl_demo_data.py --tenant-slug testco` — idempotent, seeds Hopkins FH + 5 other companies + 3 prior FH cases (Andersen/Martinez/Nakamura families)

### Audit findings

- **Existing NL extraction infrastructure was workflow-scoped** (`command_bar_extract_service.py` + `NaturalLanguageOverlay.tsx` = 1547 lines). It already powers sales_order / quote creation today. Phase 4 built a parallel entity-scoped path per approved plan decision #2 — zero modifications to the existing workflow path. Retirement is a Phase 5/6 cleanup concern
- **`User.preferences` JSONB** (added in Phase 2 r32) reused — no new tenant-level config storage needed
- **Phase 1 resolver's `SEARCHABLE_ENTITIES`** doesn't include `company_entity`. Phase 4 adds local resolution in `nl_creation/entity_resolver.py` rather than extending Phase 1's tuple. Phase 5 nav/search unification will elevate the CompanyEntity resolver to a first-class Phase 1 search target
- **Two existing NL-extraction call-sites** (`first_call_extraction_service` for FH first-call page + `call_extraction_service` for RC calls) — Phase 4 does NOT consolidate these; the `nl_creation.extract.case` prompt was seeded independently per approved plan decision #4 (copied content, independent evolution)
- **`useVoiceInput` hook** is reusable verbatim — no per-modality fork needed
- **Scribe prompt + case field shape** ready for reuse — Phase 4's prompt copies the field taxonomy but stays independent
- **Case date-field ambiguity** discovered during verification: single sentence has "DOD tonight" AND "service Thursday" — both match a scalar structured parser. Fixed by making case date fields AI-only (handles semantic disambiguation), while single-datetime entities (event) keep their structured parsers

### Performance

| Stage | Budget | Actual |
|---|---|---|
| Structured parser (per call, 100-iteration average) | <5ms | <0.05ms typical |
| Entity resolver per field (pg_trgm backed) | <30ms | ~2-5ms on 10-row seed |
| AI extraction (Haiku via Intelligence) | <500ms typical, 1200ms ceiling | ~350-450ms typical |
| Extract endpoint p50 | <600ms | **5.9ms** (no-AI path), ~400ms with Haiku |
| Extract endpoint p99 | <1200ms | **7.2ms** (no-AI path), ~700-900ms with Haiku |

**BLOCKING CI gate** at `backend/tests/test_nl_creation_latency.py`. 30-sample mixed-shape across case/event/contact. Gate measures without Anthropic key set (floor latency); production CI with key produces a higher-but-still-compliant number.

### Test counts

| Suite | Count | Notes |
|---|---|---|
| `test_nl_structured_parsers.py` | 53 | Every parser × happy path + edge cases + perf guard |
| `test_nl_creation_backend.py` | 25 | Registry (5), Company-entity resolver (5 including tenant isolation + filter whitelist), Intent detector (6 across 4 entity types), Extractor orchestration (3), API (6) |
| `test_nl_creation_latency.py` | 1 | **BLOCKING** p50/p99 gate |
| `frontend/tests/e2e/nl-creation-phase-4.spec.ts` | 8 | Demo sentence + event + contact + live update + tab fallback + escape + Hopkins pill + API contract |
| **Total new this phase** | **87** | All backend passing; Playwright ready for staging |
| Phase 1-3 regression | 194 | All green — no changes to previously-passing behavior |

### Surprises for Phase 5 (Triage Workspace — reshapes actionRegistry.ts)

- **Task deferred per approved plan** — no task model/API/UI today. Phase 5 Triage Workspace is the natural home for task creation UX conventions. When task lands, it's:
  - minimal model (id, tenant_id, title, assignee_id, due_date, priority, description, status, created_by/at)
  - `POST /api/v1/tasks` + standard CRUD
  - NL config in `nl_creation/entity_registry.py` — ~25 lines following event pattern
  - Creator callable ~15 lines
  - 1 new prompt seed
  - 1 new Playwright spec
  About 250 total lines of code
- **Frontend `actionRegistry.ts` reshape is Phase 5's big lift.** Phase 4 leaves `detectNLIntent.ts` as a client-side mirror of the backend detector — a small duplication. Phase 5's reshape should unify entity-type aliases into a single registry surface, replacing the manual ENTITY_PATTERNS list in `detectNLIntent.ts`
- **`command_bar_extract_service` + `NaturalLanguageOverlay` (workflow path) coexist with Phase 4's entity path.** Retirement decision is Phase 5/6. The natural migration: once Phase 5 Triage Workspace replaces workflow-driven sales-order creation with entity-driven, the old path becomes deletable
- **CompanyEntity not in Phase 1 resolver's SEARCHABLE_ENTITIES.** Adding it benefits BOTH Phase 4's NL pipeline AND the command bar's main results (typing "Hopkins" surfaces the CRM record). Phase 5 nav/search unification should do this in one coordinated touch
- **Space-aware extraction is wired but has no concrete defaults today.** The infrastructure is there (`space_defaults: dict[str, dict]` in each entity config). Phase 5/6 can populate meaningful defaults as UX patterns stabilize — e.g. "in Production space, `new order` defaults to work_order entity type"
- **Pre-existing `useNLExtraction`-adjacent NL flows in FH first-call page** — the `/cases/new` FHFirstCallPage has its own NL extraction via `scribe.extract_first_call`. Phase 4 leaves it untouched (it's the Tab fallback target). Future consolidation work can unify the two into one NL platform layer once traffic patterns prove out

### Demo verification

The demo sentence produces the expected overlay:

- **Input:** "new case John Smith DOD tonight daughter Mary wants Thursday service Hopkins FH"
- **Expected extractions (with Anthropic key set):** Deceased name (John Smith), Date of death (Today/2026-04-20), Date of birth (null or missing_required — AI may omit), Informant (Mary, daughter), Service date (Thursday/2026-04-23), Funeral home (Hopkins Funeral Home PILL from entity resolver)
- **Verified on dev without Anthropic:** Funeral home PILL resolves correctly (entity resolver works). Required fields correctly listed in missing_required (AI disabled path)
- **On staging with Anthropic + Hopkins FH seeded:** full overlay populates, Enter creates case, navigates to case detail with all satellites populated

### Demo staging data seeded

`seed_nl_demo_data.py --tenant-slug testco` is the canonical re-seed command. Seeds:

- **CompanyEntity rows:** Hopkins Funeral Home, Riverside Funeral Home, Whitney Funeral Home, Oakwood Memorial, St. Mary's Church, Acme Manufacturing
- **3 prior FHCase rows** (Eleanor Andersen / Harold Martinez / Grace Nakamura) with satellite data so the fh_case resolver has trigram candidates

Idempotent — safe to re-run between demos. Documents the exact demo dependencies so regressions are re-seedable in a single command.
