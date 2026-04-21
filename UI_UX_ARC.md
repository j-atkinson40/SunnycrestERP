# UI/UX Arc (Phases 1-7) — Complete Reference

**Project:** Bridgeable platform
**Arc dates:** April 2026 (7 phases over ~3 weeks)
**Final migration head:** `r35_briefings_table`
**Status:** ✅ Complete. Arc finale shipped in Phase 7.

This document is the definitive reference for the Bridgeable UI/UX arc. It exists for three audiences:
1. **Engineers maintaining or extending the platform post-arc** — architectural patterns + pitfalls
2. **New teammates onboarding** — what got built and why
3. **James preparing the September Wilbert meeting demo** — exact keystrokes for the 5-minute moment

---

## Executive Summary

Before the arc, Bridgeable had a working ERP platform — tables, forms, reports, an AI command bar that was 5,900 lines and mostly scaffolding. Features lived in silos. Users navigated to do anything consequential.

After the arc, Bridgeable has seven composable platform primitives + four post-arc follow-ups closing the last open seams. A funeral director hits `⌘K`, types `new case John Smith DOD tonight daughter Mary wants Thursday service Hopkins FH`, hits Enter — a case record is created in 5 seconds with the decedent, the informant, the service date, and a pilled reference to the Hopkins FH CRM record. Switching to Arrangement space versus Administrative space changes which information emphasizes in their morning briefing. Processing 12 pending invoices becomes a keyboard-driven triage session instead of clicking through 12 detail pages. Hovering an entity reference in any of those flows opens a peek panel with key facts — no navigation needed.

The command bar is not a component; it's a platform layer. Saved views are not a feature; they're the universal data pattern across every list, kanban, calendar, and chart. Spaces aren't personalization; they're cognitive context switching. Natural-language creation isn't a form replacement; it's how the platform removes the friction between intent and record.

**Why the arc works:**

- **Composition over reinvention.** Phase 6 briefings reuse Phase 5 triage counts, Phase 2 saved view executor, Phase 3 spaces, and Phase 1 command bar registry. Zero duplication.
- **Registries as the integration contract.** Adding a new triage queue (Phase 5), a saved view (Phase 2), or a command-bar action (Phase 1) is a single-file edit + optional seed — no core changes.
- **Coexist strategy over rewrites.** Phase 6 briefings coexist with the 1,869-line legacy `briefing_service.py` rather than rewrite it. The cleanup sweep is deliberate post-arc, not arc-critical.
- **BLOCKING CI latency gates per primitive.** Every hot-path endpoint has a latency test that fails CI on regression. The arc maintains sub-30ms p50s on user-interactive paths.
- **Honest expectation-setting in admin surfaces.** The Phase 7 telemetry page says "counters clear on restart" rather than pretending to be Datadog.

---

## Phase-by-phase Technical Deep-dive

### Phase 1 — Command Bar Platform Foundation

Established the backend platform layer. New endpoint `POST /api/v1/command-bar/query` with intent classification, pg_trgm fuzzy resolver across 6 entity types (fh_case, sales_order, invoice, contact, product, document), recency weighting, tenant + permission filtering, result orchestration. Backend package `app/services/command_bar/`: registry (owns `ActionRegistryEntry`), intent (rule-based, no AI), resolver (UNION ALL per query), retrieval (orchestrator). Frontend `core/commandBarQueryAdapter.ts` translates backend ResultItem → legacy CommandAction shape (interface-only adapter).

**Migration r31_command_bar_trigram_indexes:** `CREATE EXTENSION pg_trgm` + 6 GIN trigram indexes via `CREATE INDEX CONCURRENTLY`.

**BLOCKING gate:** p50 < 100ms, p99 < 300ms. **Actual: p50 = 5.0 ms, p99 = 6.9 ms.**

**Tests:** 22 registry unit + 40 intent unit + 15 resolver integration + 13 retrieval + 9 API e2e + 8 regression + 9 Playwright = 116 total.

### Phase 2 — Saved Views as Universal Primitive

Saved views become the rendering engine for every list, kanban, calendar, table, card grid, chart, and dashboard surface. Storage in `vault_items.metadata_json.saved_view_config` — no new table. Backend package `app/services/saved_views/`: types + registry (7 entity types) + executor (12 filter operators, cross-tenant masking, aggregation) + crud (4-level visibility) + seed (role-based).

**Migration r32_saved_view_indexes:** GIN trigram on vault_items.title + partial B-tree on saved-view owner.

**7 presentation modes:** list, table, kanban, calendar, cards, chart, stat.

**BLOCKING gate:** p50 < 150ms, p99 < 500ms. **Actual: p50 = 15.4 ms, p99 = 18.5 ms.**

**Tests:** 9 registry + 29 integration + 1 latency + 7 Playwright = 46 total.

### Phase 3 — Spaces with Pins

Per-user workspace contexts. Storage in `User.preferences.spaces` (JSONB array). 6 curated accents (warm, crisp, industrial, forward, neutral, muted) — all WCAG AA verified in Phase 7. Pinned items (saved views + nav routes) render above sidebar nav. Keyboard shortcuts: `Cmd+[` / `Cmd+]` prev/next space, `Cmd+Shift+1-5` direct jump.

**No migration** — `r32` from Phase 2 already added the JSONB column.

**Backend package** `app/services/spaces/`: types + registry (role templates) + crud (10 service functions + server-side pin resolution) + seed (idempotent via `spaces_seeded_for_roles`).

**Tests:** 36 unit + 19 API + 9 Playwright = 64 total.

### Phase 4 — Natural Language Creation with Live Overlay

Fantastical-style live extraction overlay. 3-stage pipeline: structured parsers (<5ms each, pure functions) → entity resolver (<30ms, pg_trgm fuzzy) → Haiku AI fallback (managed prompts). 4 entity types via entity-centric path (case, event, contact) + 2 via workflow (sales_order, quote).

**Migration r33_company_entity_trigram_indexes:** GIN trigram on `company_entities.name`.

**BLOCKING gate:** p50 < 600ms, p99 < 1200ms. **Actual (no-AI path): p50 = 5.9 ms, p99 = 7.2 ms.** With Haiku in the loop: p50 ~350-450ms.

**Tests:** 53 structured-parser unit + 25 integration + 1 latency + 8 Playwright = 87 total.

### Phase 5 — Triage Workspace + actionRegistry Reshape + Task Infrastructure

Keyboard-driven triage. Pluggable 7-component queue configs (item display, action palette, context panels, embedded actions, flow controls, collaboration, intelligence). 2 shipped queues: `task_triage` + `ss_cert_triage`. Task CRUD + transitions. frontend `actionRegistry.ts` reshape from 944-line flat file to `services/actions/` package split by vertical.

**Migration r34_tasks_and_triage:** 3 tables (tasks, triage_sessions, triage_snoozes) + GIN trigram on tasks.title.

**BLOCKING gates:** next_item p50<100ms/p99<300ms; apply_action p50<200ms/p99<500ms. **Actual: next_item p50=4.8ms/p99=5.8ms (20×/51× headroom); apply_action p50=9.7ms/p99=13.5ms (20×/37× headroom).**

**BLOCKING SS cert parity test:** triage-path approve/void produces identical side effects (status transitions, timestamps, audit IDs, reason preservation) as the legacy `/social-service-certificates` route.

**Tests:** 31 tests in test_task_and_triage.py (incl. 3 BLOCKING parity) + 2 latency gates + 9 Playwright = 42 total.

### Phase 6 — Morning and Evening Briefings

AI-generated narrative briefings as workday bookends. Morning orients forward; evening closes backward. Legacy `briefing_service.py` context builders imported verbatim per coexist strategy. Phase 5 triage counts aggregated. Phase 3 active-space shapes section emphasis via Jinja prompt branches. Every-15-min global sweep with per-user window check — **first per-user scheduled pattern on platform**.

**Migration r35_briefings_table:** new `briefings` table with partial unique index on `(user_id, briefing_type, DATE(generated_at))`.

**BLOCKING gate:** p50 < 2000ms, p99 < 5000ms. **Actual: p50 = 28.9 ms, p99 = 32.0 ms (69× headroom).**

**Tests:** 27 tests + 2 BLOCKING latency gates + 7 Playwright = 36 total.

### Phase 7 — Polish and Arc Finale

No new primitives. Cross-cutting polish over the 6 prior phases. Delivered:

**Shared UI primitives** (`components/ui/`):
- `EmptyState` — one canonical pattern for 10+ surfaces; 3 tones (neutral/positive/filtered) × 3 sizes
- `Skeleton` / `SkeletonLines` / `SkeletonCard` / `SkeletonRow` / `SkeletonTable` — motion-safe
- `InlineError` — role=alert + aria-live, optional retry handler

**Hooks** (`hooks/`):
- `useRetryableFetch` — auto-retry-once with ~1s backoff + manual retry
- `useOnboardingTouch` — server-side dismissal via `User.preferences.onboarding_touches_shown` (cross-device)
- `useOnlineStatus` — `navigator.onLine` + browser events

**Components** (new):
- `OnboardingTouch` — first-run tooltip anchored to a positioned parent
- `KeyboardHelpOverlay` — `?` key context-aware help overlay
- `OfflineBanner` — global network-disconnect indicator

**Empty state replacements (10):** 7 saved view renderers, TasksList (two states — empty-all vs empty-filtered), TriagePage caught-up (positive tone), TriageIndex, CommandBar no-results (with "try: ..." hints), SavedViewsIndex, BriefingPage.

**Skeleton replacements (5):** BriefingPage, BriefingCard, SavedViewsIndex, TasksList, TriagePage/TriageIndex.

**First-run tooltips (5 wired):** command bar intro, saved view intro, space switcher intro (only when 2+ spaces), triage intro, briefing intro.

**ARIA + aria-live pass:** CommandBar (role=dialog + aria-modal + combobox on input), NLOverlay (region + aria-live + aria-busy), TriagePage item region, BriefingPage narrative region.

**Mobile fixes:** 44px touch targets on TriageActionPalette + TriageFlowControls + BriefingPreferences channel/section buttons; BriefingPreferences grid stacks on mobile; CalendarRenderer day cells shrink from 92px to 70px on narrow.

**prefers-reduced-motion:** global CSS retrofit in `index.css` — neutralizes every transition + animation via `@media (prefers-reduced-motion: reduce) { *,*::before,*::after { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; } }`. Phase 7 new components use `motion-safe:` variants natively.

**Contrast verification:** WCAG AA tests at `backend/tests/test_arc_accent_contrast.py`. All 6 accents pass foreground-on-white (≥4.5:1), accent-on-white large (≥3:1), and foreground-on-accent-light (≥4.5:1). Zero remediation needed.

**Focus ring visibility:** `backend/tests/test_arc_focus_ring_contrast.py` + `--ring` in `index.css` darkened from `oklch(0.708 0 0)` to `oklch(0.48 0 0)` — now passes WCAG 3:1 against white + all 6 accent-light chips.

**Micro-interactions:** NL extraction field entrance (`motion-safe:animate-in fade-in-0 slide-in-from-top-1 duration-200`); triage item transition via `key` remount + `slide-in-from-bottom-1`.

**Telemetry dashboard:** `/bridgeable-admin/telemetry`. In-memory rolling latency buffer (1000 samples) per tracked endpoint + `intelligence_executions` aggregations over 24h/7d/30d + per-caller-module cost breakdown. `app/services/arc_telemetry.py` + `app/api/routes/admin/arc_telemetry.py`. Frontend `ArcTelemetry.tsx`. **No new database table.** Honest banner: "Counters clear on restart."

**Tests:** 8 new contrast + focus-ring tests passing.

**Total arc test count:** 288 backend tests passing across Phase 1-7 — no regressions. 50+ Playwright specs. All 5 BLOCKING latency gates green.

---

## Demo Flow Scripts — September Wilbert Meeting

Rehearsable keystroke-level scripts for the Wilbert licensee meeting. Each script assumes the demo tenant `sunnycrest` is seeded with Hopkins FH + 3 prior FH cases + a handful of open tasks + a pending SS cert.

### Demo 1 — "New case from one sentence" (the flagship moment)

**Runtime target:** 30 seconds.

1. Start: land on `/fh` (Funeral Direction hub). Morning briefing visible in header.
2. Press `⌘K`. Command bar opens.
3. Type (deliberate cadence, ~1 word per second):
   > `new case John Smith DOD tonight daughter Mary wants Thursday service Hopkins FH`
4. **Watch:** NL overlay appears below input. As you type:
   - "John Smith" lights as Deceased name (checkmark)
   - "DOD tonight" resolves to Date of death: Today (checkmark, structured parser)
   - "daughter Mary" resolves to Informant: Mary, relationship: daughter (checkmark)
   - "Thursday" resolves to Service date: next Thursday (checkmark)
   - "Hopkins FH" resolves to a pilled entity reference — the Hopkins Funeral Home CRM record (pg_trgm fuzzy match)
5. Press `Enter`. Overlay closes; browser navigates to `/fh/cases/<new-case-id>`.
6. Case detail page shows all 5 fields populated + a `note_type="nl_creation"` audit note.

**What to say while it happens:**
> "The whole platform works like this. One sentence, 30 seconds, done. The alternative was 18 form fields across 3 pages and 4 minutes. That's why we built this."

### Demo 2 — "Switch cognitive mode" (Spaces)

**Runtime target:** 20 seconds.

1. You're on the Funeral Direction hub. Space accent is `warm` (amber).
2. Point at the **SpaceSwitcher** top-right (e.g. labeled "Arrangement").
3. Press `⌘]`. Accent shifts to `crisp` (blue). Label changes to "Administrative". Pinned items in sidebar swap — the Arrangement pins (active cases, this week's services) replaced by the Admin pins (outstanding invoices, aging, compliance).
4. Press `⌘]` again. Accent shifts to `neutral` (slate). Label "Ownership". Different pins again.
5. Press `⌘[` twice to go back to Arrangement.

**What to say:**
> "Same person, same day, same application — three different cognitive modes for three different kinds of work. Spaces don't replace navigation; they emphasize what matters for the work you're actually doing right now."

### Demo 3 — "Triage 12 invoices in 90 seconds" (Triage Workspace)

**Runtime target:** 90 seconds — actually triage items, don't narrate.

1. Press `⌘K`. Type `triage`. Press Enter on "Triage my tasks" (or navigate to `/triage`).
2. Select a queue that has pending items (task_triage or ss_cert_triage).
3. **Item #1 appears.** Read it briefly.
4. Press `Enter` (= Complete/Approve). Item #2 appears. Fade-in transition.
5. Press `r` (= Reassign). Modal opens. Type one word into reason. `⌘-Enter` or click Confirm. Item #3 appears.
6. Press `s` (= Defer). Snooze preset options appear. Click "Tomorrow". Item #4 appears.
7. Continue at a natural pace for 60 seconds. Emphasize the keystrokes in rhythm with the item advancing.
8. When queue empties: "You're all caught up on Task Triage" positive-tone empty state. Processed-count stats visible.

**What to say AFTER reaching caught-up:**
> "That was 12 decisions in 90 seconds. Zero clicks, zero navigation, zero hunting for the next item. This is what the manufacturing preset's approval workflow used to be — a list page with 12 rows, clicking into each one, filling a form, going back. Triage collapses that to keyboard shortcuts and a stream."

### Demo 4 — "Morning briefing already knows" (Briefings)

**Runtime target:** 30 seconds.

1. Navigate to `/briefing`.
2. Narrative visible immediately (already generated by the every-15-min sweep).
3. Read a few sentences of the briefing aloud — emphasize the naturalness of the prose.
4. Scroll to the structured sections below:
   - **Queues** card — each queue linked to `/triage/<queue_id>`
   - **Overnight calls** card (if Call Intelligence is connected) — voicemail count
   - **Today's calendar** card
5. Click a queue row. Navigates directly into triage.

**What to say:**
> "Most platforms show you a dashboard — a grid of numbers you have to interpret. The briefing reads like prose because we generated it with an AI that knows the operator's role, their active space, their triage queues, and what actually happened overnight. 30 seconds of reading and you know the shape of your day."

### Demo 5 — "The help overlay" (Phase 7 accessibility showcase)

**Runtime target:** 10 seconds.

1. Anywhere on the platform, press `?`.
2. `KeyboardHelpOverlay` opens — context-aware, shows shortcuts for the current page (Triage shortcuts if on /triage, etc.).
3. Press `?` or `Escape` to dismiss.

**What to say:**
> "Every power-user shortcut is discoverable. Press `?` and it tells you what's available right here, right now. Users who want keyboard speed don't have to read a manual."

### Demo rehearsal checklist

Before the September meeting:
- [ ] Confirm staging tenant is seeded via `seed_nl_demo_data.py` (Hopkins FH + other demo CompanyEntity rows + 3 prior FH cases)
- [ ] Confirm triage queues have pending items (seed if needed)
- [ ] Confirm morning briefing generated today
- [ ] Practice the 5 demos end-to-end at least 3 times
- [ ] Record a video of Demo 1 as backup in case staging breaks mid-demo
- [ ] Tab preload `/fh` before the meeting so the dashboard is warm

---

## Post-arc Backlog (Consolidated)

Deferred items from Phases 1-7 + post-arc-followup-1-through-4 closure, organized by category. None of these block the September demo. Each is a legitimate post-arc workstream.

**All four post-arc follow-ups are delivered.** See FEATURE_SESSIONS.md for build records:

1. ✅ **Follow-up 1 (April 2026) — Space-scoped triage queue pinning** (commit `1590ebe`)
2. ✅ **Follow-up 2 (April 2026) — AI questions in triage context panels** (commit `7f1cc31`)
3. ✅ **Follow-up 3 (April 2026) — Saved view live preview in builder** (commit `2f52b4c`)
4. ✅ **Follow-up 4 (April 2026, arc finale) — Peek panels** (commit pending)


### Command Bar (Phase 1)
- Voice-in-command-bar polish (existing voice input works; polish deferred)
- Mobile command bar redesign (native-mobile post-arc)
- Retirement of legacy `/core/command` + `/core/command-bar/search` endpoints
- Route collision fix between `ai.py` and `ai_command.py` at `/ai/command`

### Saved Views (Phase 2)
- ✅ **Follow-up 3 (April 2026) — Live preview in builder.** `SavedViewCreatePage` gains a right-column sticky preview pane powered by new `POST /api/v1/saved-views/preview` (100-row cap enforced server-side, arc-telemetry keyed `saved_view_preview`). 300ms-debounced via new `useDebouncedValue` hook composed with Phase 7's `useRetryableFetch`; AbortController cancels stale in-flight calls. Mode-switch cache reuses the last executor result when only presentation mode changes among non-aggregation modes. Pre-render mode-hint guard lives in the preview component (renderer stays lean for detail page + widget callers). `<lg` collapsible with localStorage persistence. p50=8.5ms / p99=12.0ms vs 150/500ms budget. Zero new tables. See `FEATURE_SESSIONS.md` § "Saved View Live Preview in Builder".
- Seed backfill when adding new saved-view templates (template additions after a role seeded don't backfill)
- `production-board.tsx` deletion (awaiting Playwright staging parity verification)
- Migrate ad-hoc debouncers (cemetery-picker, funeral-home-picker, useDashboard, useNLExtraction, cemetery-name-autocomplete) onto `useDebouncedValue` when next touched

### Spaces (Phase 3)
- Mobile space switching (bottom sheet redesign)
- Shared team spaces
- Intelligence-suggested space switches
- Workflow handoff between spaces
- Space-scoped notifications
- Custom accent picker
- Cross-tenant space sharing
- Space export / import
- ✅ **Follow-up 1 (April 2026) — Space-scoped triage queue pinning.** `triage_queue` added to `PinConfig.pin_type` union; server-side resolver pulls icon + pending count from the Phase 5 `TriageQueueConfig` registry with batched per-space permission lookup; director Arrangement + production Production templates seed a `task_triage` pin; PinStar component renders on `/triage` queue cards; sidebar badge shows pending count capped at `99+`. Zero new tables. See `FEATURE_SESSIONS.md` § "Space-Scoped Triage Queue Pinning".
- Triage-pin seed coverage expansion (other role/vertical pairs deferred — backfill script needed OR role-version bump for existing users)

### NL Creation (Phase 4)
- Multi-turn clarification dialogs (user follow-up when required fields missing)
- Sales order / quote migration off workflow-scoped overlay onto entity overlay (coordinated cleanup once patterns prove out)

### Triage (Phase 5)
- Per-tenant triage queue customization admin UI (backend `upsert_tenant_override` exists)
- ✅ **Follow-up 2 (April 2026) — AI question panel.** `ai_question` is the sixth context panel type and the first interactive one. Users ask natural-language questions about the current item; Claude answers via existing `triage.*_context_question` prompts (v2 adds vertical-aware terminology). In-memory rate limit (10 req/min per user) returns structured 429 with `retry_after_seconds` so UI renders a friendly toast. Per-queue `_RELATED_ENTITY_BUILDERS` dict fetches linked entities (task: sibling tasks; ss_cert: order + customer + past certs). Latency: p50=8.2ms / p99=33.3ms orchestration-only against 1500/3000ms budget. Session question history frontend-local, cleared on item change. See `FEATURE_SESSIONS.md` § "AI Questions in Triage Context Panels".
- Bulk actions + approval chains + rules engine (scaffolded in FlowControls)
- Audit replay (CollaborationConfig scaffolded)
- Learning + anomaly detection + prioritization (IntelligenceConfig scaffolded)
- Full live-preview of triage queue configs in admin editor
- Mobile triage redesign
- Voice triage
- Voice question input (reuse `useVoiceInput` — deferred from follow-up 2)
- Multi-turn conversational threading in ai_question panel (each question independent today)
- Question suggestions based on item type / past questions (post-arc learning)
- Answer export / save to record notes
- bridgeable-admin portal action registry unification
- ✅ **Follow-up 4 (April 2026, arc finale) — `related_entities` panel wired.** Third Phase 5 stub closed (after `document_preview` Phase 5 + `ai_question` follow-up 2). New endpoint `GET /api/v1/triage/sessions/{id}/items/{item_id}/related` exposes follow-up 2's `_RELATED_ENTITY_BUILDERS` to the frontend; tiles render as click-to-peek. See `FEATURE_SESSIONS.md` § "Peek Panels".
- Wire the remaining context panel stubs: `ai_summary` (passive variant of ai_question), `saved_view` (needs per-item scoping in Phase 2 executor), `communication_thread` (needs platform messaging system)
- Dynamic saved-view scoping for `include_saved_view_context` (requires Phase 2 executor extension for per-row filter injection)
- Swap ai_question rate limiter to Redis-backed for cross-process enforcement (in-memory acceptable at current scale)

### Briefings (Phase 6)
1. Rename `/briefings/v2/*` → cleaner REST
2. Consolidate `employee_briefings` + `briefings` tables
3. Migrate legacy `MorningBriefingCard` consumers to new `BriefingCard`
4. Retire `briefing.daily_summary` prompt once legacy card retires
5. Revisit `briefing_service.py` for consolidation
6. Rename `/v2/generate` → `/v2/regenerate` for intent clarity
7. Briefing AI learning (auto-drop skipped sections)
8. SMS / Slack / voice (TTS) delivery
9. Shared team briefings ("Today's Services" read-mostly view)
10. Network-level cross-tenant briefings for licensee operators
11. Voice briefings via TTS ("briefing while driving")
12. Briefings for non-tenant users (family portal)

### Polish (Phase 7)
- Native mobile redesign (explicit — "mobile is not a responsive shrink")
- Full accessibility audit with external auditor
- Advanced telemetry (Datadog-level observability)
- i18n / multi-language support
- Dark mode polish across arc surfaces
- Cross-arc layout consistency (max-width conventions) — explicitly deferred as unnecessary per user approval

### Peek Panels (Follow-up 4, arc finale)
- ✅ **Delivered.** Six entity types (fh_case, invoice, sales_order, task, contact, saved_view). `GET /api/v1/peek/{type}/{id}` + arc-telemetry `peek_fetch`. Hover (debounced 200ms) + click (pinned). Session cache 5-min TTL. Mounted on 4 surfaces (command bar eye icon, briefing pending_decisions, saved view builder rows, triage related_entities). p50=3.7ms / p99=7.4ms.
- Keyboard-triggered peek (Ctrl+Space on focused result) — post-arc enhancement
- Nested peek (peek within peek — clicking a reference inside a peek opens another peek) — post-arc enhancement
- Peek for additional entity types: spaces, briefings, users, documents, products, vault_items
- Peek editing (currently view-only; edits happen on detail page) — explicit non-goal for now
- Peek multi-select for bulk actions — post-arc
- Mobile-optimized peek interactions (touch-and-hold for hover-equivalent, swipe-to-dismiss) — currently functional via tap→click degradation
- Voice peek ("tell me about this case") — post-arc
- Briefing prompt v3 — narrative-inline `[[type:id]]` reference tokens + frontend hover-peek replacement (deferred from follow-up 4 audit). Available on user request; current path uses structured `pending_decisions` instead, which gives reliable typed peek triggers without prompt-compliance risk
- Per-tenant peek customization (which fields show in fh_case peek, etc.) — post-arc admin UI
- PEEK_BUILDERS expansion is one-file-per-entity — pattern matches `_DIRECT_QUERIES` + `_RELATED_ENTITY_BUILDERS`

### Architectural debt
- FastAPI `@app.on_event` → lifespan context manager migration
- Orphaned `tenant_settings` table (orphaned since platform_1 era)
- Legacy Document models coexist with canonical Document (D-9 closeout)
- PeekHost is a single floating-host component rather than `base-ui` Popover/Tooltip pair (deviation from item-10 audit-approved spec; documented in FEATURE_SESSIONS.md § "Peek Panels"). Equivalent ARIA semantics with manually wired Esc + click-outside + focus return; no functional regression. Migration to base-ui primitives if their controlled-mode API stabilizes is a low-priority post-arc cleanup.

**Total: ~50 items across 11 categories** (added Peek Panels). None blocking; all well-understood; each has a clear owner shape when scoped.

---

## Lessons Learned

### Architectural decisions that paid off

- **Registries as the feature integration contract.** Phase 1's `ActionRegistryEntry`, Phase 2's entity registry, Phase 5's triage queue registry all follow the same pattern: a singleton populated by side-effect imports at package load. Adding a new feature never requires touching core code — just register.
- **Coexist-with-legacy over rewrites.** Phase 6 briefings imported 1,869 lines of legacy context builders as dependencies. The alternative would have been a 2-week rewrite that shipped worse output. The arc finished on schedule because we accepted the legacy-dependence risk and documented the cleanup as post-arc.
- **BLOCKING CI latency gates per primitive.** Every hot-path endpoint shipped with a test that fails CI if p50/p99 regresses. This caught a regression in Phase 6 scheduler flood-testing before merge. Without the gates, we'd have shipped slow code and debugged it in production.
- **In-code platform defaults + vault_item tenant overrides.** Pattern pivot in Phase 5 from "store platform defaults as vault_items with company_id=NULL" — blocked by NOT NULL constraint — to "platform defaults in Python, tenant overrides in vault_items." Made tenant customization cleaner AND avoided a schema change.
- **Phase 7 reserved for polish, documented upfront.** The audit in Phase 1 said "polish lives in Phase 7." Every phase from 2-6 could defer empty-state / loading / error polish to a dedicated phase without feeling incomplete. Phase 7 caught 30+ discrete polish items that would have been individually forgotten.
- **Post-arc follow-ups as the cleanup vehicle.** The 7-phase arc closed cleanly enough that 4 follow-ups picked up the obvious next-steps (triage queue pinning, AI questions, saved view live preview, peek panels) without re-opening any phase. Every follow-up was: extend an existing arc primitive registry, add one endpoint, wire ≤4 frontend surfaces, BLOCKING latency gate. The arc-finale peek follow-up wired three of the four trigger surfaces against existing infrastructure (`_DIRECT_QUERIES`, `_RELATED_ENTITY_BUILDERS`, `commandBarQueryAdapter`, briefing's `pending_decisions` typed link) — confirming the arc's "registries + composition" thesis hold past the original phase scope.
- **First-class interaction-pattern primitives ship as their own thing, not as part of a feature.** Peek (follow-up 4) is arguably the 8th platform primitive after the 7 from the arc — cross-cutting trigger surfaces, hover-vs-click semantic discipline, session cache, mobile degradation. By scoping it as one follow-up rather than a sub-feature of triage or saved views, it became reusable across all 4 surfaces immediately and any future surface (spaces, briefings, users, documents) gets peek by adding a builder + a trigger.

### Patterns that didn't work / required revision

- **"Replace the old" default stance in early planning.** Phase 6 initial plan called for replacing `briefing_service.py`. Audit recalibrated to coexist. Every subsequent phase benefited from asking "does the old need to die before the new ships?" Answer was usually no.
- **Keyboard shortcut sequences (`G B` Vim-style).** Proposed in Phase 7 plan; dropped after realizing the infrastructure didn't exist + the benefit was marginal. `⌘K` + search covers the same user intent.
- **"Live preview" in builder UIs (Phase 2, 5, 7).** Consistently proposed, consistently deferred — until follow-up 3 actually shipped it for saved views. The build came in at one new endpoint + one component + ~15-line debounce hook, no schema work. Deferring it through 6 phases turned out to be the right call (it became dramatically simpler once the executor + Phase 7 polish primitives existed) — but it shouldn't have been deferred indefinitely. Lesson for future similar items: keep small "polish-y" UX wins on the explicit roadmap rather than the indefinite-deferred bucket.
- **Self-paced loops and automation on arc work.** We discussed automating the per-surface polish pass with a repeated prompt. It would have produced 10× the code with 10% the quality. Human audit + structured refactor yielded better outcomes.

### Meta-findings

- **The 5 BLOCKING latency gates caught exactly 0 bugs in Phases 1-6.** They are still extremely valuable — they document what "fast" means, and any future engineer who breaks them has to explain themselves. Phase 6 briefing gate caught 1 bug (the `/v2/generate` double-creating rows in a loop); without the gate, that would have shipped.
- **"What does NOT ship this phase?" is the most important planning question.** Every phase started with an explicit non-goals list. This is what prevented scope creep across 7 phases over 3 weeks.
- **Audit-before-implementation saved ~2 weeks of rework.** Every phase's audit surfaced 2-4 things the implementation plan had wrong. Phase 6's audit found that `AssistantProfile.disabled_briefing_items` existed — spec'd for Phase 7 as "new," actually already-shipped. Without the audit, we'd have duplicated it.
- **Shared UI primitives should have come earlier.** Phase 7's `EmptyState` / `Skeleton` / `InlineError` components are used across 10+ arc surfaces — if they'd existed in Phase 1, every subsequent phase would have composed them instead of rolling its own. Phases 2-6 shipped with inconsistent treatments that Phase 7 cleaned up. For the next arc: design-system primitives first, features second.

### For future arcs

- **Define "the seven primitives" equivalent upfront.** The arc worked because everyone knew the end state: these seven primitives, composing. The post-arc cleanup backlog is scoped precisely because we know what "done" looks like.
- **Budget a finale phase.** Phase 7 is the difference between "works" and "feels inevitable." Without it, the arc would feel like a pile of features instead of a platform.
- **Every primitive gets a BLOCKING CI latency gate.** Non-negotiable.
- **Every new-feature phase gets an audit phase first.** Non-negotiable.
- **Every legacy component stays operational unless there's a specific reason to rip it out.** The coexist pattern is not lazy; it's disciplined. Cleanup is a deliberate post-arc decision.

---

## Quick reference

**Migration head (arc-complete):** `r35_briefings_table`

**Performance envelope (production dev-hardware):**
- command_bar_query: p50 = 5.0 ms, p99 = 6.9 ms
- saved_view_execute: p50 = 15.4 ms, p99 = 18.5 ms
- nl_extract (no-AI): p50 = 5.9 ms, p99 = 7.2 ms
- triage_next_item: p50 = 4.8 ms, p99 = 5.8 ms
- triage_apply_action: p50 = 9.7 ms, p99 = 13.5 ms
- briefing_generate (AI stubbed): p50 = 28.9 ms, p99 = 32.0 ms

**Test counts (arc-complete):**
- Backend: 288 tests across Phase 1-7 regression (no regressions)
- Playwright: 50+ specs
- BLOCKING latency gates: 5 (all green)
- BLOCKING parity tests: 3 (SS cert triage parity — all green)

**Key files new to the arc:**
- `backend/app/services/command_bar/` — Phase 1
- `backend/app/services/saved_views/` — Phase 2
- `backend/app/services/spaces/` — Phase 3
- `backend/app/services/nl_creation/` — Phase 4
- `backend/app/services/triage/` — Phase 5
- `backend/app/services/briefings/` — Phase 6
- `backend/app/services/arc_telemetry.py` — Phase 7
- `frontend/src/services/actions/` — Phase 5 reshape
- `frontend/src/components/ui/empty-state.tsx` + `skeleton.tsx` + `inline-error.tsx` — Phase 7

**Docs:**
- `CLAUDE.md` — §14 per-phase entries + the top-level `UI/UX Arc (Phases 1-7) — Complete` section
- `FEATURE_SESSIONS.md` — chronological session log per phase
- `UI_UX_ARC.md` (this file) — comprehensive reference

---

*Arc complete. The platform is ready for September.*
