# CLAUDE.md — Bridgeable Platform

## Read order for new chats

1. STATE.md — what is true right now (migration head, active arc, deferred items)
2. This file (CLAUDE.md) — conventions, patterns, schema rules
3. Canon documents as needed for the task:
   - PLATFORM_ARCHITECTURE.md — Spaces / Command Bar / Focus primitives
   - DESIGN_LANGUAGE.md — tokens, aesthetic, mood anchors
   - BRIDGEABLE_MASTER.md — mission, strategy, vertical roadmap
   - FUNERAL_HOME_VERTICAL.md — FH-specific workflows
   - VISION.md — long-horizon thesis
4. DECISIONS.md — only when you need to understand WHY something is the way it is

## Documentation write permissions (STRICT)

- **Sonnet (Code tab) may write to:** code, tests, migrations, and STATE.md. Nothing else.
- **Sonnet may NOT write to:** CLAUDE.md, PLATFORM_ARCHITECTURE.md, DESIGN_LANGUAGE.md, BRIDGEABLE_MASTER.md, FUNERAL_HOME_VERTICAL.md, VISION.md, DECISIONS.md.
- If a build prompt seems to require edits to a canon document, STOP and surface that — it means the prompt was incomplete and needs an Opus session first.
- At the end of every build session, append a STATE.md update: migration head if changed, what shipped, anything now active or newly deferred.

## 1. Project Overview

**Bridgeable** (getbridgeable.com) is a multi-tenant SaaS business management platform for the death care industry, specifically Wilbert burial vault licensees and their connected funeral homes. The platform manages the full operational lifecycle: funeral order processing, delivery scheduling, inventory, AR/AP, monthly billing, cross-licensee transfers, safety compliance, and financial reporting.

**Company context:**
- **Sunnycrest Precast** — first customer and development partner (vault manufacturer in Auburn, NY); live at `sunnycrest.getbridgeable.com`
- **Able Holdings** — holding company that owns the Bridgeable platform
- **Wilbert** — national franchise network of ~200 burial vault licensees. Bridgeable targets this network as its primary market.
- **Strategic goal:** Demo at the September 2026 Wilbert licensee meeting. Multi-vertical SaaS expansion planned beyond death care.

**4 tenant presets:** `manufacturing` (primary, most features), `funeral_home`, `cemetery`, `crematory`

## 1a-pre. Umbrella Design Principle — "Opinionated but Configurable"

**This is the overarching design principle of Bridgeable. Every design choice should be evaluable against it.**

Opinionated enough to be immediately useful. Configurable enough to respect user agency.

- **Opinionated** means the platform ships working defaults for every primitive. A new tenant gets seeded spaces, saved views, briefings, and pinned content without configuring a thing. The command bar works out of the box. Core workflows (month-end close, AR collections) are already registered. Every user has a working Monday morning.
- **Configurable** means nothing is forced. Every seeded default can be overridden. Role-based starting suggestions do not become role-based destinations. Platform workflows can be forked into independent tenant copies (Option A fork) OR soft-customized via parameter overrides (Option B enrollment). Spaces are per-user; Settings is a space itself, with the same editing affordances as any other space. Users can delete, reorder, recolor, rename — the platform stays out of the way once the defaults have done their bootstrap job.

**When the two conflict, bias toward opinionated for the first-run experience and configurable thereafter.** A new tenant seeing a fully-populated set of spaces, saved views, and a morning briefing on day one is more valuable than a pristine blank slate. But the same tenant choosing to rename the Administrative space to "Bookkeeping", remove two of the pins, and swap the accent color must succeed without friction.

Every new feature should answer two questions:

1. **What defaults ship?** If the answer is "none — user figures it out," the feature is under-opinionated.
2. **What can the user override?** If the answer is "nothing — the platform decided," the feature is over-opinionated.

Workflow Arc Phase 8a operationalizes this principle in three ways:
- Role-based seeding persists at registration (opinionated defaults) but stops force-overriding user changes on role-change (configurable: `ROLE_CHANGE_RESEED_ENABLED=False`)
- Workflow customization ships two paths: soft (parameter overrides via `WorkflowEnrollment` + `WorkflowStepParam`) for tweaks, hard (fork into independent tenant copy) for divergence
- Settings is registered as a platform space — opinionated (admin users get it seeded leftmost in the dot nav), configurable (admins rename/recolor/reorder pins, but can't delete; hide-by-moving is reserved for a later phase)

---

## 1a. Core UX Philosophy — "Monitor through the note. Act through the command bar."

**This is the foundational design principle of Bridgeable. Every feature decision must be evaluated against it.**

### The Two Modes

**MODE 1 — MONITORING (The Daily Note)**

Monitoring is passive awareness. The platform surfaces what matters without being asked.

- Information comes to the user — they do not hunt for it
- The note is per-user and per-day. Space selection filters which fragments appear; it is not a separate surface
- Monitoring is DIFFERENTIAL. The note reports change, exception, and decision-need. It does not report state. A three-line note on a quiet day is correct behaviour, not a failure, and an empty prose region is the honest output of a day where nothing needed saying
- Two registers, and only one of them is composed:
  - **Prose fragments** — composed by Intelligence, ordered by urgency, present only when there is something to say
  - **The standing set** — configured, positionally stable, always present. Capped at 7 per role. Admission test: does someone need to check this against something in their hand at an unpredictable moment? Anything looked at on a rhythm is a report, not a standing line
- Every factual claim carries its provenance. A measured span is one the system knows; whether that provenance is reachable as a link is a separate fact, and a measured span may be deliberately unlinked. Unlinked text with no provenance is connective tissue. Inference is typographically distinct from measurement
- Every standing-set label is a noun. An imperative does a badge's work through language: "Needs attention" satisfied every colour and growth prohibition and still pulled the eye
- A standing line's target is always a peek, never a Focus. The set's value is that every entry costs the same; one heavyweight click hidden among seven cheap ones destroys it
- A user reading their note should know what needs deciding today and what changed since yesterday. They should not have to read it to learn that nothing happened

**MODE 2 — ACTING (Command Bar)**

Acting is intent-driven execution. The user states what they want in natural language. The platform executes or guides — never requires navigation.

- The command bar (Cmd+K) is the PRIMARY way to do anything
- Natural language input replaces forms wherever possible
- Workflows execute inline — the user never leaves their context
- The platform detects intent, extracts structured data, and populates records automatically
- The UI (pages, forms, nav) exists as a BACKUP, not the default
- A user should be able to complete 90% of their work without navigating to any page

### The Decision Framework for Every New Feature

When designing any new feature, ask these two questions:

**Question 1: Does the user need to NOTICE this without asking?**
- If yes → it declares a FRAGMENT
- A fragment declares five things or it does not ship: who sees it (a permission predicate — lacking the permission means the fragment does not exist, not that it renders inert), what condition brings it into existence, what identity two evaluations of the same subject share, what it opens and with what scope, and what state transition ends it
- **Prompt** if it carries a bounded decision and a declared end transition. Prompts render whenever their condition holds
- **Non-prompt** otherwise. Non-prompts render only on change against the previous note's state for that identity. Truth is not sufficient for rendering
- A standing line only if it meets the admission test above, and only within the cap
- Example: "3 compliance items due this week" → a prompt fragment opening the compliance Focus scoped to those three

**Question 2: Does the user DO this when they have an intent?**
- If yes → it belongs in the command bar as a workflow
- A UI page for it may exist but is not the primary path
- The command bar entry point is designed first
- The page is the fallback for complex cases
- Example: "Create a vault order for Hopkins" → Command bar workflow with natural language overlay → UI order form exists but is the backup

**If a feature is both (needs monitoring AND action):**
- A prompt fragment IS both. It surfaces the thing and carries the entrance
- The entrance is scoped: a fragment opening a Focus opens it already scoped to what the sentence named. An unscoped landing makes the user filter for what they were just told
- Example: "4 deliveries to schedule for tomorrow" → surfaces the decision and opens the scheduling Focus scoped to tomorrow

### What This Means in Practice

**A feature is INCOMPLETE if:**
- It can only be accessed by navigating to a page
- It has no command bar workflow, and no fragment declaration if it has a monitoring aspect
- A user needs to know WHERE to go to do it
- It requires filling out a traditional form when natural language could collect the same data

**A feature is COMPLETE if:**
- Monitoring aspects declare a fragment, with all five declarations satisfied
- Action aspects are accessible from the command bar
- Natural language handles multi-field data entry
- The UI page exists for deep editing / complex cases but is not required for the primary use case

**The Scribe is the model:**
- Director has a conversation (natural input)
- Platform extracts structured data (intelligent processing)
- Director reviews and confirms (not re-enters)
- The form exists for corrections, not primary entry

**The command bar is the model:**
- User states intent in natural language
- Platform identifies workflow, extracts fields in real time
- Fields populate below as user types
- User confirms, not re-enters
- Slide-over opens for any remaining detail

### Specific Rules for Claude When Planning or Building

1. **Never design a feature as form-only.** Every feature that collects user input must have a command bar workflow with natural language extraction as the primary entry point. The form is secondary.

2. **Never design a monitoring feature as page-only.** Every metric, status or alert a user needs to notice must declare a fragment. A page for detail is fine; a page as the only surface is not. This does NOT mean everything gets a line — the composition gate decides whether a true fragment is worth saying, and a fragment that would say the same thing every day is a report, not a note fragment.

3. **When recommending a new feature, always specify:**
   - The fragment it declares, with all five declarations, if it has a monitoring aspect
   - What the command bar workflow looks like
   - What natural language inputs it accepts
   - What the UI backup page looks like
   If you cannot specify all four, the feature is not fully designed.

4. **When writing a build prompt, always include:**
   - The fragment declaration if the feature has a monitoring aspect
   - The command bar workflow registration if it has an action aspect
   - The overlay config (natural language vs. form)
   - The UI page as the backup path

5. **Result suppression in the command bar:**
   - Question queries → answers and records only, no nav
   - Action queries → workflows only, no duplicate actions
   - If a workflow covers an intent, suppress the action
   - Nav results only when no better result exists

6. **Workflow philosophy:**
   - One workflow per intent, not one per record type
   - Universal workflows that adapt via natural language are better than multiple specialized workflows
   - "Create Order" handles all order types through product type detection — not separate vault/disinterment/Redi-Rock workflows
   - When a new product line is added, it extends existing workflows, not creates new ones

### Why This Matters for September

The Wilbert demo works because of this philosophy:
- A manufacturer opens the command bar and creates a vault order by typing one sentence
- A funeral director types a sentence and a case populates
- A director types "what is our price for a monticello" and gets the answer immediately
- Nobody navigates to a form

That is the demo. That is the product. Navigation-first software cannot do this. Form-first software cannot do this. This philosophy is what makes Bridgeable different.

### Spaces — Context Switching for Power Operators

**Phase 3 of the UI/UX arc** ships Spaces as the context layer. A Space is a per-user workspace context with four attributes:

- **Name + icon + accent** (visual personality)
- **Pinned items** (saved views, nav routes, triage queues) rendered in the sidebar
- **Default home** (optional — defaults to whichever space is marked `is_default`)

Spaces are a **view overlay on the existing vertical navigation, not a replacement**. The base nav from `navigation-service.ts` stays visible; spaces add a `PinnedSection` above it and shift the visual accent. Every route remains reachable from every space via Cmd+K.

**Canonical example — funeral director's day has three spaces:**
- **Arrangement mode** (warm accent) — operationalizes the "Funeral Direction" hub from the master doc. Pins: cases, new case, my active cases, this week's services.
- **Administrative mode** (crisp accent) — operationalizes the "Business Management" hub. Pins: financials, outstanding invoices, compliance.
- **Ownership mode** (neutral accent) — strategic lens. Pins: revenue, cash position, high-level KPIs.

**Storage:** `User.preferences.spaces` (JSONB array). No dedicated table — per-user, bounded config (max 5 spaces × max ~20 pins). Follows the same rationale as saved view configs in `vault_items.metadata_json`.

**Backend:** `backend/app/services/spaces/` — `registry.py` (role templates), `crud.py` (lifecycle + pin ops + server-side pin resolution), `seed.py` (role-based seeding via `User.preferences.spaces_seeded_for_roles` array, same idempotency pattern as Phase 2).

**Frontend:** `frontend/src/contexts/space-context.tsx`, `frontend/src/components/spaces/*` (SpaceSwitcher, PinnedSection, SpaceEditorDialog, NewSpaceDialog, PinStar).

**Keyboard shortcuts:** `Cmd+[` / `Cmd+]` for prev/next space, `Cmd+Shift+1..5` for direct access. Standard useEffect listeners (not capture-phase) — different modifier combos from the command bar's Option/Alt+1..5 capture-phase listener, so no conflict.

**Role-change re-seed:** `user_service.update_user` calls BOTH `saved_views.seed.seed_for_user` AND `spaces.seed.seed_for_user` when `role_id` changes. Both are idempotent via their own `*_seeded_for_roles` arrays. A user promoted from office to director picks up both new spaces AND new saved views without re-registering.

**To add a new space template:** Append a `SpaceTemplate` to `SEED_TEMPLATES[(vertical, role_slug)]` in `backend/app/services/spaces/registry.py`. For saved-view pins use a `PinSeed(pin_type="saved_view", target=<seed_key>)` where seed_key is the Phase-2 saved-view seed key (e.g. `saved_view_seed:director:my_active_cases`). The CRUD layer's pin resolver maps seed_key → user's actual saved-view id at read time. For triage-queue pins use `PinSeed(pin_type="triage_queue", target=<queue_id>)` where queue_id is the stable identifier from a Phase 5 `TriageQueueConfig` (e.g. `"task_triage"`, `"ss_cert_triage"`) — the resolver reads the config's `icon` + `queue_name` and queries `triage.engine.queue_count` for the pending-item badge, and gracefully falls back to `unavailable` if the user lacks access or the queue no longer exists. Template additions after a role is already seeded do NOT backfill — same trade-off Phase 2 accepts.

**Triage queue pins (follow-up 1, April 2026):** Pin type `"triage_queue"` joins `"saved_view"` and `"nav_item"` as a first-class target. `ResolvedPin` carries `queue_item_count: int | None` so the sidebar can render a pending-count badge without a second round trip. Permission check is batched once per space resolution (`_accessible_queue_ids_for_user`) so a space with multiple triage pins doesn't pay N× permission lookups. `TriageQueueConfig.icon` (default `"ListChecks"`; platform defaults `"CheckSquare"` / `"FileCheck"`) is the authoritative icon source — any new icon must also land in `PinnedSection.ICON_MAP` or the pin falls back to `Layers` (silent visual bug). Seeded for (`funeral_home`, `director`) Arrangement and (`manufacturing`, `production`) Production as the first pin in each template.

**AI Questions in triage context panels (follow-up 2, April 2026):** Phase 5 shipped six context-panel types; only `document_preview` was wired. Follow-up 2 wires `ai_question` — the first interactive context panel in the platform — establishing the precedent for future interactive panels (`communication_thread`, a fully-interactive `related_entities`) when they land post-arc. Users type a question ("Why is this urgent?" / "What's the history with this funeral home?") and Claude answers grounded in item data + related entities + vertical-aware terminology. Backend: `app/services/triage/ai_question.py` — `_RELATED_ENTITY_BUILDERS` dict parallel to `_DIRECT_QUERIES` (task_triage → linked entity + last 5 tasks by assignee; ss_cert_triage → SalesOrder + Customer + past 3 certs for same FH); in-memory sliding-window rate limit (10 req/min per user) surfaces as HTTP 429 with structured body `{code: "rate_limited", retry_after_seconds, message}` so the frontend renders a friendly toast. Prompt reuse: existing `triage.task_context_question` + `triage.ss_cert_context_question` (seeded Phase 5 with Q&A-shaped `user_question` variable from the start) bumped v1→v2 via Phase 6 Option A idempotent seed (`scripts/seed_intelligence_followup2.py`) to add a VERTICAL-APPROPRIATE TERMINOLOGY Jinja block. Confidence mapping centralized in `app/services/intelligence/confidence.py::to_tier` (≥0.80 high, ≥0.50 medium, else low) for future AI-response consumers. Context panels gain two optional fields on the flat `ContextPanelConfig`: `suggested_questions: list[str]` (chips) + `max_question_length: int = 500` (UI counter + server-enforced upper bound). Input-focus discipline: Phase 5's `useTriageKeyboard` hook already suppresses triage shortcuts on INPUT/TEXTAREA/contenteditable, so typing "n" in the question textarea doesn't fire the Skip action (verified in Playwright). Session question history is frontend-local `useState` keyed on `itemId`, cleared when the user advances to the next item. Seeded on both platform queues: `task_triage` ("Ask about this task" — "Why is this task urgent?") and `ss_cert_triage` ("Ask about this certificate" — "What's the history with this funeral home?"). Latency gate: p50 < 1500 ms / p99 < 3000 ms with monkey-patched Intelligence; actual on dev **p50 = 8.2 ms / p99 = 33.3 ms** (180× p50 headroom reflects orchestration-only measurement — real Haiku call adds ~350 ms).

**Saved view live preview in builder (follow-up 3, April 2026):** `SavedViewCreatePage` gains a right-column sticky preview pane that renders results live as the user edits filters, sort, grouping, or presentation. Delivers the "live preview deferred as post-arc polish" note from the Phase 2 bullet. New endpoint `POST /api/v1/saved-views/preview` accepts `{ config: SavedViewConfig }` in the body (no saved row), reuses the shared `execute()` with owner==caller, overrides `config.query.limit = min(limit or 100, 100)` so the 300ms-debounced preview never pulls more than 100 rows. Client derives `truncated = rows.length < total_count` for the "Showing X of Y results" readout — no new backend field needed. Arc telemetry registers a sixth key `saved_view_preview` alongside the Phase 7 five; BLOCKING CI gate at `test_saved_view_preview_latency.py` targets p50 < 150 ms / p99 < 500 ms, actual on dev **p50 = 8.5 ms / p99 = 12.0 ms** (17×/41× headroom). **Mode-switch cache**: `SavedViewBuilderPreview` holds a single in-component cache slot keyed on `{query, limit, aggregation_mode ∈ {none, chart, stat}}`; swaps among list/table/kanban/calendar/cards with the same query reuse the cached result (zero network calls), swaps into chart/stat trigger a fresh fetch because the response gains `aggregations`. **Mode-hint pre-render guard** lives in the preview component (NOT `SavedViewRenderer` — the shared renderer stays lean for the detail page + widget callers): kanban without a group-by field, calendar without a date field, cards without a title field, etc. render targeted `EmptyState` copy pointing at the Presentation panel rather than the generic `ModeFallback`. **Debounce**: new `hooks/useDebouncedValue<T>(value, ms)` (~15 lines, 5 vitest tests) composes with Phase 7's `useRetryableFetch` pattern; AbortController cancels in-flight preview calls when a newer debounced config lands. Manual `Refresh` button invalidates the cache + fires immediately. **Layout refactor** on `SavedViewCreatePage`: two-column at `lg+` (LEFT = all config stacked, RIGHT = sticky preview), collapsible toggle at `<lg` with `localStorage` (key: `saved_view_preview_collapsed`). **Zero new tables, no schema change.** Post-arc: migration of the codebase's other ad-hoc debouncers (cemetery-picker, funeral-home-picker, useDashboard, useNLExtraction, cemetery-name-autocomplete) onto `useDebouncedValue` is explicitly NOT part of this follow-up — they rewrite when next touched.

**Settings as a system space + DotNav (Workflow Arc Phase 8a, April 2026):** Settings is now a first-class platform space, not a separate sub-area with different UX patterns. Backend: `SYSTEM_SPACE_TEMPLATES` list in `app/services/spaces/registry.py` — seeded conditionally based on a live `user_has_permission(user, db, "admin")` check. Initial Settings pins: Workflows (`/settings/workflows`), Saved views (`/saved-views`), Users (`/admin/users`), Roles (`/admin/roles`). More settings pages migrate in Phase 8h+. `SpaceConfig.is_system: bool = False` marks platform-owned spaces — `delete_space` rejects them with a helpful error ("System spaces can be hidden but not deleted"). Users can rename, recolor, and reorder pins on system spaces. **DotNav**: horizontal row of dots at the bottom of the left sidebar (`components/layout/DotNav.tsx`), replaces the Phase 3 top-bar `SpaceSwitcher`. System spaces sort leftmost regardless of `display_order`. Plus-button creates a new space. Per-space icons map to lucide components via a narrow `ICON_MAP` (calendar-heart, receipt, factory, kanban, store, home, settings, etc.); unknown icons fall back to a colored dot in the space accent. Keyboard shortcuts preserved from Phase 3: `Cmd+[` / `Cmd+]` prev/next, `Cmd+Shift+1..5` jump. The Phase 3 `SpaceSwitcher` component file stays in the codebase for one-release grace; `app-layout.tsx` no longer mounts it. **Idempotency**: system spaces tracked via `preferences.system_spaces_seeded: list[str]` separate from `preferences.spaces_seeded_for_roles` — admin permission grant surfaces Settings promptly on role change without forcing user-space re-seeds.

**Role decoupling (Workflow Arc Phase 8a, April 2026):** **Roles are permission grants. UX defaults are bootstrap suggestions, not forced content on role changes.** User registration still runs the Phase 2 / 3 / 6 seeds to give new users a working starting point (opinionated first-run). Role CHANGES no longer auto-re-seed saved views + briefing preferences — gated by module constant `ROLE_CHANGE_RESEED_ENABLED: bool = False` in `app/services/user_service.py`. Existing user content is preserved; promoted users keep what they had. A new public helper `reapply_role_defaults_for_user(db, user)` exposes the per-phase seeds for opt-in use (Phase 8e builds the UI surface). The spaces seed STILL runs on role change because its role-tuple seeding is itself idempotent AND the Phase-8a `_apply_system_spaces` pass checks live admin permission — a user newly granted admin sees Settings appear in the dot nav on next role update without needing a re-login.

**Peek panels (follow-up 4, April 2026 — arc finale):** Lightweight entity previews without navigation. Two interaction modes: **hover** (transient, info-only) and **click** (pinned, can include actions); hover-to-click promotion via mouse-into-panel. Six entity types: `fh_case`, `invoice`, `sales_order`, `task`, `contact`, `saved_view`. Backend: `GET /api/v1/peek/{entity_type}/{entity_id}` dispatches to `PEEK_BUILDERS` dict in `app/services/peek/builders.py` (~30 lines per builder, mirrors Phase 5 `_DIRECT_QUERIES` + follow-up 2 `_RELATED_ENTITY_BUILDERS` pattern); each builder returns a slim per-entity peek shape with `display_label`, `navigate_url`, and a typed `peek` dict. Tenant-scoped via builders' `company_id` filter. Arc-telemetry registers `peek_fetch` as the seventh tracked endpoint. **BLOCKING CI gate** at `tests/test_peek_latency.py` targets p50 < 100 ms / p99 < 300 ms, 24-sample mixed across 6 entity types; actual on dev **p50 = 3.7 ms / p99 = 7.4 ms** (27×/40× headroom). **Frontend platform layer**: `contexts/peek-context.tsx` (PeekProvider with single-active-peek state + session-scoped `Map<"{type}:{id}", {data, fetchedAt}>` cache + 5-min TTL + AbortController for superseded fetches), `hooks/usePeek` (throws when provider absent) + `usePeekOptional` (null-safe), `components/peek/PeekHost.tsx` (single floating panel rendered once at app root, mounts inside `PeekProvider` in App.tsx after `SpaceProvider`), `components/peek/PeekTrigger.tsx` (wrapper for any element + `IconOnlyPeekTrigger` variant), six per-entity renderers in `components/peek/renderers/` (CasePeek, InvoicePeek, SalesOrderPeek, TaskPeek, ContactPeek, SavedViewPeek + shared `_shared.tsx` for label/value pairs and StatusBadge). Hover debounce 200 ms. Click open immediate. Single peek at a time — opening another closes the current. **Implementation deviation from item-10 audit approval (documented):** PeekHost is a single host component with controlled state from PeekContext, NOT base-ui `Popover` (click) + `Tooltip` (hover). Equivalent ARIA semantics — `role="dialog" aria-modal="true"` for click, `role="tooltip"` for hover; Esc + focus return + click-outside backdrop manually wired (~30 lines). Trade-off: hover→click promotion is a state mutation (no re-mount flash), single render path simplifies testing. **Four trigger surfaces wired**: (1) command bar RECORD/VIEW tiles get a hover-reveal eye icon (right-aligned, opacity 0 → 60 on row hover, opacity 100 on icon hover; click `stopPropagation` so primary tile click still navigates) — adapter at `commandBarQueryAdapter.ts` propagates `result_entity_type` → `peekEntityType` for the 6 supported types; (2) briefing `pending_decisions` list items convert title to a click-peek button when `link_type` matches the `_BRIEFING_LINK_TYPE_TO_PEEK` whitelist (case/invoice/order/task/contact/saved-view route fragments), keeping the existing "Open →" link untouched — **no prompt v3 bump** (narrative-inline tokens deferred to post-arc); (3) `SavedViewRenderer` gains optional `onPeek` prop — when provided, ListRenderer + TableRenderer wrap the title cell in a click-to-peek button; detail page + widget callers don't pass the prop so click-to-navigate behavior preserved; builder preview opts in; (4) Phase 5's `related_entities` context panel **wired** (third Phase 5 stub closed after `document_preview` Phase 5 + `ai_question` follow-up 2) — new endpoint `GET /api/v1/triage/sessions/{id}/items/{item_id}/related` exposes follow-up 2's `_RELATED_ENTITY_BUILDERS` to the frontend; tiles rendered by `RelatedEntitiesPanel.tsx` are click-to-peek. **Mobile**: hover triggers detect coarse-pointer environments via `matchMedia("(pointer: coarse)")` and degrade to click — touch users get peek as click-only. **A11y**: Tab focuses peekable triggers (role=button, tabIndex=0); Enter/Space opens peek; Esc closes; focus returns to trigger on close. **Stub status after follow-up 4**: wired = document_preview (Phase 5), ai_question (follow-up 2), related_entities (follow-up 4). Remaining stubs: `saved_view` (post-arc — needs per-item scoping in Phase 2 executor), `communication_thread` (post-arc — needs platform messaging system).

**Visual accent discipline:** Six curated accents ship (`warm`, `crisp`, `industrial`, `forward`, `neutral`, `muted`). Each accent sets `--space-accent`, `--space-accent-light`, `--space-accent-foreground` CSS variables on `documentElement`. Components use `var(--space-accent, var(--preset-accent))` — if no space is active, the PresetThemeProvider's baseline accent shines through. Never touch `--preset-accent` from Phase 3 code. Spaces are SUBTLE — think lighting in different rooms of a house, not a redesign per space. Contrast ratios stay WCAG AA across all accents.

### Natural Language Creation — Platform Capability

**Phase 4 of the UI/UX arc** ships the Fantastical-style live overlay. Any entity type in the platform can support NL creation — the user types one sentence in the command bar, structured parsers + entity resolver + Intelligence (Haiku) populate fields in real time.

**The demo moment:** A funeral director hits Cmd+K and types
```
new case John Smith DOD tonight daughter Mary wants Thursday service Hopkins FH
```
An overlay appears beneath the input with checkmarks for Deceased name, Date of death (Today), Informant (Mary, daughter), Service date (Thursday), Funeral home (pilled, resolved to the Hopkins FH CRM record). Enter creates the case. 5 seconds instead of 5 minutes.

**Architectural principle:** NL creation is an additive capability on top of the Phase 1 command-bar platform layer. Empty invocation (`new case`) still navigates to the traditional form. NL invocation (`new case <content>`) routes to the overlay. One query shape, two paths; the transition is invisible to the user.

**Four entity types ship in Phase 4:** `case`, `event`, `contact` via the new entity-centric path + `sales_order`/`quote` via the EXISTING workflow-scoped `NaturalLanguageOverlay` + `wf_create_order`. The two overlays coexist intentionally — Phase 5/6 cleanup can migrate workflow-backed entities onto the entity path once patterns prove out.

**Pipeline per extraction:**
1. **Structured parsers (<5ms each)** — date, time, phone, email, currency, quantity, name. Pure functions. See `nl_creation/structured_parsers.py`.
2. **Entity resolver (<30ms per field)** — pg_trgm fuzzy match against `company_entities.name` (r33 GIN trigram index) + reuses Phase 1's resolver for contact + fh_case. Capitalized-token candidate scan against entity-typed fields. See `nl_creation/entity_resolver.py`.
3. **AI fallback via Intelligence** — Haiku (simple route) with managed prompts `nl_creation.extract.{entity_type}`. Force-JSON output; confidence-scored extractions. Only called when structured + resolver leave required fields missing. See `nl_creation/ai_extraction.py`.

**Backend package:** `backend/app/services/nl_creation/` — `types.py`, `structured_parsers.py`, `entity_resolver.py`, `ai_extraction.py`, `entity_registry.py`, `extractor.py`. Public exports via `__init__.py`.

**Entity registry** (`entity_registry.py`) declares per-entity: `field_extractors`, `ai_prompt_key`, `creator_callable`, `navigate_url_template`, `required_permission`, `space_defaults`. Adding a new entity type = append to `_ENTITY_CONFIGS` + seed a managed prompt `nl_creation.extract.{entity_type}` + wire a creator function.

**API:** `/api/v1/nl-creation/*` — `POST /extract` (hot path, p50 < 600ms blocking gate), `POST /create` (materialize), `GET /entity-types` (registry dump for UI). All user-scoped; permission gates honored per entity config.

**Command bar integration:** additive. `intent.py::detect_create_with_nl()` detects the `<create_verb> <entity> <content>` pattern. Frontend mirrors the detector in `components/nl-creation/detectNLIntent.ts` for instant UX. When matched, the command bar renders `<NLCreationMode>` INSTEAD of the standard results list (mode switch, not overlay). Enter creates + navigates; Tab opens the traditional form with `?nl=<input>` query param; Escape cancels.

**Frontend:** `types/nl-creation.ts`, `services/nl-creation-service.ts`, `hooks/useNLExtraction.ts` (300ms debounce — wider than the command bar's 100-200ms to amortize AI calls), `components/nl-creation/{NLOverlay,NLField,NLCreationMode,detectNLIntent}`. Voice input reuses Phase 1's `useVoiceInput` — transcript flows into the same text field + same pipeline.

**Migration r33_company_entity_trigram_indexes:** adds a `CREATE INDEX CONCURRENTLY ix_company_entities_name_trgm USING gin (name gin_trgm_ops)`. Required for the entity resolver's <30ms budget. Phase 1 resolver's `SEARCHABLE_ENTITIES` tuple deliberately NOT extended in Phase 4 — that's a coordinated Phase 5 nav/search unification. **SUPERSEDED (S-1, 2026-07):** the command-bar entity-portal arc IS that coordinated work; S-1 deliberately added `company_entity` as the 8th searchable type (r33 index already existed; ruled in the S-1 amendment — see DECISIONS 2026-07-23 park-ratification arc).

**Performance targets:** p50 < 600ms, p99 < 1200ms. BLOCKING CI gate at `backend/tests/test_nl_creation_latency.py`. Actual (no-AI path on dev hardware): **p50=5.9ms, p99=7.2ms** — 100× headroom on p50 without AI. With Haiku in the loop, typical p50 drifts to ~350-450ms.

**Demo data seeding:** `backend/scripts/seed_nl_demo_data.py --tenant-slug testco` seeds Hopkins Funeral Home + other demo CompanyEntity rows + 3 prior FH cases so the resolver has real pg_trgm candidates. Idempotent; safe to re-run before demos.

## 1b. Canonical Platform Specs

Ten markdown documents at repo root are the authoritative specs for Bridgeable. In-tree markdown is the source of truth. Project-knowledge PDFs uploaded to chat interfaces may lag the repo; when they disagree, the repo wins.

| File | Scope | Read when |
|---|---|---|
| [CLAUDE.md](CLAUDE.md) | Build standards, conventions, tech stack, arc logs, Recent Changes | Every session |
| [PLATFORM_DESIGN_THESIS.md](PLATFORM_DESIGN_THESIS.md) | **Top-level design synthesis** — *Bridgeable looks like a Range Rover, behaves like Tony Stark's workshop, and is built like an Apple Pro app.* Three layers, three references, three jobs, all sourced outside software. Why this synthesis works, what each layer rejects, where they conflict and how to resolve, the three tests (one per layer), strategic positioning. Established April 25, 2026 (Phase 4.4.3a-bis). | Any design decision — start here when designing a new surface or evaluating shipped work against the platform's design identity |
| [PLATFORM_PRODUCT_PRINCIPLES.md](PLATFORM_PRODUCT_PRINCIPLES.md) | Product thinking and design philosophy — one-surface-three-verbs thesis (Pulse/Command bar/Focus/Nav), opinionated-but-configurable, data density over decoration, business-function triage (universal vs vertical), onboarding as first calibration, permission requests as admin triage, user configuration templates, the learning loop, the platform is honest ("correct me" invitation), software as new-employee coaching, domain-specific operational semantics (ETA, draft/finalized, hole-dug, ancillary), Fort Miller scaling principle. Established April 23, 2026 during Phase B planning. | Any contested product decision. When the other specs disagree or don't answer, this is the tiebreaker |
| [BRIDGEABLE_MASTER.md](BRIDGEABLE_MASTER.md) | Master planning reference — vision, strategy, primitives (Spaces / Saved Views / Pins), Command Bar capabilities, Bridgeable Assist, Vision, Knowledge Ingestion, cross-tenant architecture, verticals roadmap. April 19, 2026 state. | Strategy, roadmap, or anything cross-vertical |
| [PLATFORM_ARCHITECTURE.md](PLATFORM_ARCHITECTURE.md) | Three-primitive architecture (Monitor / Act / Decide), Focus primitive, Pulse surface, entity portal, chip conversation, pause sensor, observe-and-offer, bounded-decision discipline, cross-cutting principles. April 22, 2026. | Any architectural decision touching the new primitives |
| [PLATFORM_INTERACTION_MODEL.md](PLATFORM_INTERACTION_MODEL.md) | **Layer 2 of the design thesis** — Tony Stark / Jarvis interaction model. Four primary interactions (summon · arrange · park · dismiss). Floating tablets as materialization unit. Voice/text invocation as primary verb. Chip pattern + interpretation chips + pause sensor. Persistence rules. Three modes of presence. Mobile/tablet translation. What this rejects (cinematic theater, app-switching, modal exclusivity, tab-forest navigation). Established April 25, 2026 (Phase 4.4.3a-bis). | Any interaction-model decision |
| [PLATFORM_QUALITY_BAR.md](PLATFORM_QUALITY_BAR.md) | **Layer 3 of the design thesis** — Apple Pro era execution standard for the entire platform. Reference frame: peak Jony Ive era hardware + Pro app discipline (Final Cut Pro, Logic Pro, Aperture, original iPhone, unibody MacBook). 8 quality dimensions. Surface-specific reference apps. Test method ("would this ship in an Apple Pro app at peak Apple form?"). Explicit rejection of current-decade Apple drift (Liquid Glass, soft-everything, gradient-heavy). Calibration against in-register existing surfaces. Process discipline, examples of "done right" and "almost but not quite." | **Every user-facing commit — this is the bar** |
| [FUNERAL_HOME_VERTICAL.md](FUNERAL_HOME_VERTICAL.md) | FH vertical design — AI Arrangement Scribe, Legacy Personalization Compositor, AI Compliance + Audit Intelligence, cross-tenant network, case data model (14 tables), arrangement conference intake (3 methods), casket selection, tenant website builder, onboarding migration | FH vertical build work |
| [SPACES_ARCHITECTURE.md](SPACES_ARCHITECTURE.md) | Spaces primitive — templates, system vs user spaces, access modes, portal architecture, affinity signal, purpose-limitation clause | Anything touching Spaces, portals, or space-scoped UX |
| [DESIGN_LANGUAGE.md](DESIGN_LANGUAGE.md) | Visual treatment — color tokens, typography, shadow system, spacing, motion curves, light/dark anchors, accessibility floor | Every UI-touching decision |
| [FEATURE_SESSIONS.md](FEATURE_SESSIONS.md) | Append-only session log — one entry per build session, with deliverables + tests + migration head | When context on a specific past session is needed |
| [AESTHETIC_ARC.md](AESTHETIC_ARC.md) | Aesthetic arc plan — Phase I, II, III sessions + scope + deliverables | Aesthetic / visual polish work |
| [PLUGIN_CONTRACTS.md](PLUGIN_CONTRACTS.md) | Canonical plugin category contracts — input/output, guarantees, failure modes, configuration shape, registration mechanism, current implementations + cross-references for each ✓ canonical plugin category. Established 2026-05-11 (R-8.y.a first of four R-8.y documentation sub-arcs). 10 ✓ categories at v1.0: Intake adapters, Focus composition kinds, Widget kinds, Document blocks, Theme tokens, Workshop template types, Composition action types, Accounting providers, Email providers, Playwright scripts. R-8.y.b extends to ~ partial categories; R-8.y.c to implicit; R-8.y.d ships the plugin registry browser consuming the canon. | Adding a new implementation to an existing plugin category (read that section); proposing a new plugin category (read appendix); building against an existing substrate (cite the relevant section to ground architectural choices) |

**Read PLATFORM_DESIGN_THESIS.md before designing any user-facing surface.** It articulates the three-layer synthesis (Range Rover / Tony Stark / Apple Pro) that the rest of the design canon answers to. The three sub-docs (DESIGN_LANGUAGE §0, PLATFORM_INTERACTION_MODEL, PLATFORM_QUALITY_BAR) each own a layer; the thesis doc resolves cross-layer conflicts. New surfaces must pass all three layer tests before ship.

**Read PLATFORM_QUALITY_BAR.md before building any user-facing surface.** Every commit is evaluated against this bar. "Working" is not the bar; "would this ship in an Apple Pro app at peak Apple form?" is the bar. Architectural shortcuts that compromise feel should be flagged + escalated, never silently taken. See §10 in PLATFORM_QUALITY_BAR.md for the process discipline.

**Read PLATFORM_PRODUCT_PRINCIPLES.md when a product decision is contested.** The seven-doc stack answers distinct questions: DESIGN_THESIS = *what is the design identity*; PRODUCT_PRINCIPLES = *why was it designed this way*; ARCHITECTURE = *how is it built*; INTERACTION_MODEL = *how does it behave*; QUALITY_BAR = *how good does it have to feel*; DESIGN_LANGUAGE = *what does it look like*; BRIDGEABLE_MASTER = *what's the strategic context*. When those disagree or don't settle a call, PRODUCT_PRINCIPLES is the tiebreaker for product decisions, DESIGN_THESIS is the tiebreaker for design decisions.

**Scope relationship — BRIDGEABLE_MASTER vs PLATFORM_ARCHITECTURE.** Both are authoritative for their coverage areas, but they represent two layers of architectural thinking. `BRIDGEABLE_MASTER.md` captures the April 19, 2026 consolidation — three primitives of **Spaces / Saved Views / Pins**, the Command Bar with 18 unified capabilities, Bridgeable Assist, Vision, Knowledge Ingestion, Personalization Studio, N-way cross-tenant. `PLATFORM_ARCHITECTURE.md` (April 22, 2026) introduces a later architectural layer: the three primitives reframe as **Monitor (Spaces with composed Pulse) / Act (Command Bar) / Decide (Focus)**, formalizes Focus as the bounded-decision primitive, introduces Pulse as the per-Space composed surface, entity portal as the Command Bar organizing pattern, chip conversation + pause sensor as the multi-step input pattern, and observe-and-offer as the cross-cutting configuration principle.

**Where the two docs disagree, PLATFORM_ARCHITECTURE.md wins** per its own header ("Where this doc and the existing docs disagree, this doc reflects the more recent thinking and supersedes"). Future work will merge the PLATFORM_ARCHITECTURE content back into BRIDGEABLE_MASTER to unify; deferred to post-architecture-migration.

**Per-prompt reading list:**
- **Scope/planning sessions:** CLAUDE.md + PLATFORM_PRODUCT_PRINCIPLES.md + PLATFORM_DESIGN_THESIS.md + PLATFORM_ARCHITECTURE.md + BRIDGEABLE_MASTER.md + the vertical doc if vertical-specific.
- **UI-touching prompts:** CLAUDE.md + PLATFORM_DESIGN_THESIS.md + DESIGN_LANGUAGE.md + PLATFORM_INTERACTION_MODEL.md + PLATFORM_QUALITY_BAR.md + PLATFORM_ARCHITECTURE.md (for new primitives) or UI_UX_ARC.md (for shipped primitives). Add PLATFORM_PRODUCT_PRINCIPLES.md when the prompt touches scan-and-act surfaces, Pulse composition, onboarding, or permission flows.
- **Interaction-model decisions** (drag patterns, command bar behavior, summon/arrange/park/dismiss flows, peek/Focus/spatial work): CLAUDE.md + PLATFORM_INTERACTION_MODEL.md + PLATFORM_PRODUCT_PRINCIPLES.md.
- **Backend-only prompts:** CLAUDE.md only. Loading design docs wastes context.

**Note:** `UI_UX_ARC.md` documents the seven primitives shipped during Phases 1–7 (Command Bar v1, Saved Views, Spaces, NL Creation, Triage, Briefings, Polish). It is NOT in the canonical-specs registry above because it is an arc log, not an architectural spec. `PLATFORM_ARCHITECTURE.md` supersedes its architectural framing (Command Bar v1 becomes the Act primitive; Spaces host the Pulse surface; Focus is the newly-introduced third primitive not in UI_UX_ARC).

## 2. Technical Stack

### Backend
| Component | Version |
|-----------|---------|
| Python | 3.13+ |
| FastAPI | 0.115.6 |
| SQLAlchemy | 2.0.36 (sync, not async) |
| Alembic | 1.14.1 |
| Pydantic | 2.10.4 |
| APScheduler | >=3.10.0 |
| Anthropic SDK | >=0.42.0 |
| PostgreSQL | 16 |
| PyMuPDF (fitz) | >=1.24 |
| httpx | >=0.27 |
| BeautifulSoup4 | >=4.12 |
| Uvicorn | 0.34.0 |

### Frontend
| Component | Version |
|-----------|---------|
| React | 19.2 |
| Vite | 7.3 |
| TypeScript | 5.9 |
| Tailwind CSS | 4.2 (v4 — uses `@base-ui/react`, no `asChild`) |
| shadcn/ui | 4.0 |
| React Router | 7.13 |
| Axios | 1.13 |
| Lucide React | 0.577 |

### Infrastructure
- **Hosting:** Railway (backend + frontend as separate services)
- **DNS/SSL:** Cloudflare
- **Database:** PostgreSQL on Railway (production), local PostgreSQL 16 (`bridgeable_dev`)
- **File storage:** Railway persistent volume
- **No query library** — data fetching is plain Axios via `frontend/src/lib/api-client.ts`

### Third-Party Integrations
- **Claude API** (Anthropic) — AI briefings, content generation, collections drafts, product extraction, COA analysis
- **Google Places API** — funeral home discovery, cemetery geocoding
- **QuickBooks Online** — OAuth accounting sync (`backend/app/services/accounting/`)
- **Sage 100** — CSV export accounting sync
- **Twilio** — SMS delivery confirmations
- **Stripe** — payment processing (configured, not fully wired)

## 3. Design Philosophy

All new features and flows should adhere to these guiding principles:

### Hub-Based Organization
The platform is organized around **hubs** — central data repositories (CRM, Orders, Inventory, AR/AP, Knowledge Base, etc.) that serve as the single source of truth. Every feature should read from and write to these hubs rather than maintaining isolated data stores. Cross-feature visibility comes naturally when data lives in the right hub.

### Widget-Based Dashboards
Dashboards (Operations Board, Financials Board, Morning Briefing) are composed of **widgets** that pull data from hubs. Features contribute to dashboards via the registry pattern (`BoardContributor`), not by embedding dashboard logic in feature code. This keeps dashboards composable and extensible.

### Agent Actions with Human Review
The primary workflow pattern is: **agent performs analysis/action → human reviews and approves**. This applies to:
- Accounting agents (month-end close, collections, categorization) — agent runs, human approves via token-based email
- Call Intelligence — AI extracts order data from calls, human confirms before saving
- Catalog ingestion — parser extracts products, human reviews pricing before publishing
- Certificate generation — system auto-generates on delivery, human approves before sending

Whenever possible, build the automated path first, then add the human review gate. The goal is to minimize manual data entry while maintaining human oversight for consequential actions.

### Playwright + Claude API Testing Framework
All features should be built with the existing **Playwright E2E + Claude API** testing framework in mind. Every new endpoint and UI flow should be testable against the staging environment (`sunnycresterp-staging.up.railway.app`). Tests authenticate via the staging API, exercise real backend logic, and verify end-to-end behavior.

### Visual Design Language

Two documents govern Bridgeable's visual and UX design. Read both when building any UI-touching feature.

**`DESIGN_LANGUAGE.md`** — Visual treatment. The source of truth for how Bridgeable *looks and feels*: color tokens, typography, shadow system, spacing scale, motion/animation curves, dark and light mode anchors ("Mediterranean garden morning / cocktail lounge evening"), accessibility floor (contrast ratios, focus rings). Every CSS variable, every shadow spec, every token name derives from this document. If you are making a decision about a color, a shadow, a spacing value, or a transition duration — read this doc first.

**`UI_UX_ARC.md`** — Interaction patterns and information architecture. The source of truth for how Bridgeable *works*: the seven platform primitives (Command Bar, Saved Views, Spaces, NL Creation, Triage Workspace, Briefings, Polish infrastructure), their architectural patterns, BLOCKING CI latency gates, registry/seed/executor composability contracts, and the September Wilbert demo scripts. If you are making a decision about how a surface behaves, which primitive to compose, or how a feature integrates with the platform layer — read this doc.

**Division of labor at a glance:**

| Question | Read |
|---|---|
| What color token do I use here? | `DESIGN_LANGUAGE.md` |
| What spacing value or shadow level is correct? | `DESIGN_LANGUAGE.md` |
| What easing curve should this animation use? | `DESIGN_LANGUAGE.md` |
| Does this text meet contrast requirements? | `DESIGN_LANGUAGE.md` |
| What pattern does this list / table / kanban surface use? | `UI_UX_ARC.md` |
| How does this feature integrate with the command bar or triage? | `UI_UX_ARC.md` |
| What empty-state or loading-skeleton pattern applies here? | `UI_UX_ARC.md` (Phase 7 primitives) |
| Should this be a triage queue, a saved view, or a hub widget? | `UI_UX_ARC.md` |

**For build prompts:** Any prompt that produces UI output must reference `DESIGN_LANGUAGE.md` and `UI_UX_ARC.md` alongside `CLAUDE.md`. Prompts that touch only backend logic, migrations, services, or tests should reference `CLAUDE.md` only — loading design docs into a backend-only context wastes context budget and invites misapplication.

## 4. Architecture

### Multi-Tenant SaaS
- Tenants are `companies` records. All tenant-scoped tables have a `company_id` or `tenant_id` FK.
- Subdomain routing: `{slug}.getbridgeable.com` → tenant app, `admin.getbridgeable.com` → platform admin
- `isPlatformAdmin()` in `frontend/src/lib/platform.ts` detects `admin.*` subdomain
- Tenant isolation is enforced at the service layer — all queries filter by `company_id`

### OperationsBoardRegistry Pattern
Singleton registry (`frontend/src/services/operations-board-registry.ts`) where features register as `BoardContributor` objects. Core features register as permanent contributors (`requires_extension: null`). Extensions register with their extension key and only render when active. Same pattern used for `FinancialsBoardRegistry`.

### AI Patterns
- **AIService** (`backend/app/services/ai_service.py`): Single `call_anthropic()` function, uses `claude-sonnet-4-20250514` by default. Forces JSON-only responses.
- **AICommandBar**: Frontend component for natural language input on various pages
- **ConfirmationCard**: Shows AI-extracted data for human review before saving
- **Briefing Service**: Uses `claude-haiku-4-5-20250514` for cost-effective daily briefings
- **Accounting Analysis**: Uses `claude-haiku-4-5-20250514` for COA classification (confidence threshold 0.85 for auto-approve)

### Extension System
Extensions (Wastewater, Redi-Rock, Rosetta, NPCA Audit Prep, Urn Sales) are tracked in `tenant_extensions`. When enabled, they register contributors to the Operations Board registry, add navigation items, and unlock features. Core modules are always available; extensions are per-tenant opt-in.

**Urn Sales:** `urn_sales` extension — full urn product catalog, order lifecycle (stocked + drop-ship), two-gate engraving proof approval, Wilbert catalog ingestion pipeline (PDF auto-fetch + web enrichment), pricing tools. All routes gated by `require_extension("urn_sales")`. 6 tables, 42+ API endpoints, 39 E2E tests.

**NPCA:** `npca_audit_prep` is a proper extension. All dashboard elements and nav items are gated by `hasModule("npca_audit_prep")`. Auto-enables when `npca_certification_status = "certified"` is set during platform admin tenant setup.

### Settings Pattern
Tenant settings are stored on the `companies` table in the `settings_json` column, which is **`text`, not JSONB** — a prior version of this document claimed JSONB and cost a probe. Access is via the `company.settings` property and `company.set_setting(key, value)` method; do not write JSONB operators against this column. A `tenant_settings` database table also exists (migrations create it) but is orphaned — application code uses `Company.settings_json` exclusively.

### Admin Platform Architecture

The Bridgeable codebase ships **two distinct app trees from one frontend bundle**, dispatched at runtime by `frontend/src/lib/platform.ts::isPlatformAdmin()` reading `window.location.hostname`. The two trees do NOT share auth, do NOT share layouts, and largely do NOT share routes — they share only the React render root and the visual-editor library at `frontend/src/lib/visual-editor/`.

**Tenant App tree** (`frontend/src/App.tsx`) — served at `app.getbridgeable.com` and tenant subdomains (`sunnycrest.getbridgeable.com`, etc.):
- Auth: `auth-context.tsx::useAuth()`. JWT realm = `"tenant"`. `User` model. Role.slug in {`admin`, `office`, `production`, …}.
- Backend: `/api/v1/*` mounted from `app/api/v1.py::v1_router` with `Depends(require_admin)` / `Depends(get_current_user)`.
- Layout: `AppLayout` (warm Bridgeable design tokens, sidebar nav, DotNav, command bar).

**Bridgeable Admin tree** (`frontend/src/bridgeable-admin/BridgeableAdminApp.tsx`) — served at `admin.getbridgeable.com` AND any host's `/bridgeable-admin/*` path:
- Auth: `bridgeable-admin/lib/admin-auth-context.tsx::useAdminAuth()`. JWT realm = `"platform"`. `PlatformUser` model (separate identity store; not a discriminator on `User`).
- Backend: `/api/platform/*` mounted from `app/api/platform.py::platform_router` with `Depends(get_current_platform_user)`. Cross-realm boundary enforced — `get_current_user` rejects platform tokens, `get_current_platform_user` rejects tenant tokens (both return 401 on realm mismatch).
- Two layouts coexist:
  - **`AdminLayout`** (slate chrome) wraps operational admin pages: Health Dashboard, Tenants Kanban, Audit Runner, Migrations Panel, Feature Flags, Deployments, Staging, Telemetry.
  - **`VisualEditorLayout`** (warm Bridgeable tokens) wraps the four Visual Editor pages (themes, components, workflows, registry) + the editor landing page. The editors are previewing Bridgeable's tokens, so the surrounding chrome consumes those tokens too — visual continuity between the editor's preview canvas and its frame.

**The `adminPath()` helper** (`bridgeable-admin/lib/admin-routes.ts`) is the cross-link convention. It returns `/${path}` on admin subdomain or `/bridgeable-admin/${path}` otherwise — every admin Link should route through it so paths work under both entry points.

**Where new admin pages go:**
- Operational admin (status, ops tooling, support workflows) → `bridgeable-admin/pages/<page>.tsx` + register in BridgeableAdminApp's `operationalPages` Routes block + add `<Link>` to `AdminHeader.tsx` nav. Use AdminLayout's slate chrome via `<AdminLayout>` parent.
- Visual editor pages (token authoring, component config, workflow canvas, registry inspector) → `bridgeable-admin/pages/visual-editor/<page>.tsx` + register in `visualEditorPages` Routes block. The VisualEditorLayout wraps automatically. Cross-link nav between the four editors lives in `VisualEditorLayout` itself; per-page top-bar buttons remain inside each page.

**Backend route placement:**
- Tenant-scoped functionality → `app/api/routes/<module>.py` registered in `app/api/v1.py` with `Depends(require_admin)` for tenant-admin gating, `Depends(get_current_user)` for any-tenant-user gating.
- Platform-scoped (anything that crosses tenants, edits platform/vertical defaults, or is admin-only operational tooling) → `app/api/routes/admin/<module>.py` registered in `app/api/platform.py` with `Depends(get_current_platform_user)`. URL prefix: `/api/platform/admin/<area>/<module>`.

**Visual editor library** at `frontend/src/lib/visual-editor/` is shared between trees. The tenant App tree imports it for its side-effect — `auto-register.ts` populates the in-memory component registry singleton at module load, so the registry is available regardless of which tree is rendering. The admin tree imports the same library for the editor pages. The shared library has no awareness of which tree consumes it; it has no auth dependencies, no API dependencies.

**Realm-agnostic service layer (WB-cycle-followup-2, 2026-05-27):** Service-layer modules consumed by both tenant-realm and admin-platform-realm routers ship realm-agnostic. The service layer takes operational primitives (company_id, requested operation, data) without coupling to which router invoked it; realm-specific concerns (auth context, route prefix, response envelope) live at the router layer not the service layer.

The pattern was load-bearing at WB-cycle-followup-2 (`33d5721`) where Widget Builder substrate originally shipped with tenant-router coupling at service layer; the 403 gap on Studio (admin-realm) consumption forced refactor to realm-agnostic service. Post-refactor, `visual_editor_widgets_service` consumed by both `/api/v1/widget-builder/*` (tenant router) and `/api/platform/admin/widget-builder/*` (admin platform router) with identical service-layer behavior; auth context flows through router-layer dependencies (`get_current_user` vs `get_current_platform_user`); service layer operates against company_id + operation + data without realm awareness.

Pattern application: Studio-authored substrates (substrates whose primary authoring surface lives in Studio admin shell) ship realm-agnostic at service layer from foundation, not retrofit. Service-layer modules under `backend/app/services/visual_editor/` are canonical realm-agnostic examples; new visual-editor substrates extend this convention.

Cross-reference: `Per-request API URL resolution` paragraph (this subsection) for the client-side counterpart pattern; DECISIONS.md 2026-05-27 — Discoverability canon for operator-facing substrate cycles (auth-realm reachability verification as substrate-cycle dimension).

**Audit attribution limitation (relocation phase, May 2026):** the `created_by`/`updated_by` columns on `platform_themes`, `component_configurations`, `workflow_templates`, `tenant_workflow_forks` are FK-constrained to `users.id`. PlatformUser ids cannot satisfy that FK. The route layer therefore passes `actor_user_id=None` for platform-user writes — these writes are NOT recorded at the column level. Future work: drop the FK constraint or add a parallel `platform_user_id` column. Tracked as a follow-up; no migration was shipped this phase per scope constraint.

**`last_edit_session_actor_id` without FK pattern (WB-cycle-followup-2, 2026-05-27):** The audit attribution limitation documented above (PlatformUser vs User FK constraint problem) resolves via the `last_edit_session_actor_id` without-FK pattern. Affected columns ship as `VARCHAR(36) NULL` (UUID string) rather than `UUID NULL` with FK constraint to a specific user table. The string-typed column accepts UUIDs from either user-source table (`User` for tenant-realm edits; `PlatformUser` for admin-realm edits) without schema-level enforcement of which table the UUID references.

Audit reads resolve the user-source via two-step query: (1) attempt User lookup; (2) on miss, attempt PlatformUser lookup. The pattern preserves audit attribution across realms without requiring schema-level FK resolution. Substrate trades schema-enforced referential integrity for cross-realm audit attribution; the trade is honest given the realm-distinction architectural commitment.

The pattern applies to all substrate columns capturing actor identity that may originate from either realm (audit logs, last-edit attribution, content provenance). Substrate authors documenting `actor_id`-shaped columns specify which realms can produce values + which audit-read query pattern applies.

Cross-reference: preceding `Audit attribution limitation (relocation phase, May 2026)` paragraph for problem statement; DECISIONS.md 2026-05-27 — Substrate-extending arcs with colliding field names (relevant when audit columns share field names across substrates).

**Per-request API URL resolution (R-1.6.7, 2026-05-07):** Tenant `apiClient` (`frontend/src/lib/api-client.ts`) and admin `adminApi` (`frontend/src/bridgeable-admin/lib/admin-api.ts`) both resolve their base URL **per-request** via `resolveApiBaseUrl()` / `getAdminBaseUrl()`, reading `localStorage["bridgeable-admin-env"]` to choose between staging (`https://sunnycresterp-staging.up.railway.app`) and production (`https://api.getbridgeable.com`). This pattern removes the dependency on Vite build-time env-var resolution, which was fragile because Railway's build environment did not reliably surface dashboard-set env vars at the moment `vite build` ran on the staging frontend service — the deployed bundle had `https://api.getbridgeable.com` baked into the tenant `apiClient` even though the dashboard showed the staging URL. The pattern allows the same deployed bundle to route to different backends based on operator choice (e.g., a platform admin opening the runtime editor against staging from a production frontend deploy). The localStorage key + staging URL hardcode + production URL hardcode are **load-bearing invariants**: tenant client and admin client must agree on all three values mid-impersonation; mismatch would route the two clients to different backends on the same flow. Vitest regression guard at `frontend/src/lib/api-client.test.ts` catches drift. Other tenant-tree clients (`platform-api-client`, `portal-service`, `company-service`, `calendar-actions-service`, `personalization-studio-service`, `email-inbox-service`, `AdminCommandBar`) still use build-time-baked URLs and will need the same pattern when their endpoints get exercised under impersonation. Adopt incrementally as new endpoints surface.

**Runtime editor route tree (R-1.6.9, 2026-05-07):** `<TenantRouteTree />` (`frontend/src/lib/runtime-host/TenantRouteTree.tsx`) mounts the same component tree as the production tenant operator boot path (`renderTenantSlugRoutes()` from `App.tsx`), but passes `excludeRootRedirect: true`. This swaps the role-based `<RootRedirect />` at `/` for a direct `<HomePage />` mount + replaces the catch-all `<NotFound />` at `*` with `<HomePage />`. Pre-R-1.6.9, the runtime editor mounting at `/runtime-editor/?tenant=...&user=...` would have its inner Routes match the relative empty splat path against `<Route path="/" element={<RootRedirect />} />`, and `<Navigate to="/home" replace />` would absolute-navigate the URL out of the `/runtime-editor/*` parent route — bouncing the user to `admin.<domain>/home` (empty AdminLayout chrome). The bug was structurally present since R-0/R-1 (May 2026) but invisible until R-1.6.7 + R-1.6.8 fixed the auth chain that gated `<RootRedirect />` from firing earlier. Vitest regression guard at `frontend/src/lib/runtime-host/TenantRouteTree.test.tsx` catches future "let me clean this up" patches that remove the parameterization. **Future enhancement**: the runtime editor currently renders `HomePage` regardless of impersonated role. For role-aware landing under impersonation (e.g., picking a driver user lands on driver console content), this needs expansion. Tracked but not blocking R-2.

### Component Registry (Admin Visual Editor — Phase 1, May 2026)

`frontend/src/lib/visual-editor/registry/` is the in-memory registry every visually-editable component declares metadata to. It's the foundation Phase 2+ of the Admin Visual Editor builds against — what the editor can eventually edit is bounded by what the registry's metadata schema can describe.

**Public API:** `registerComponent({...})(Component)` HOC for tagging components; introspection helpers `getAllRegistered`, `getByType`, `getByVertical`, `getByName`, `getTokensConsumedBy`, `getComponentsConsumingToken`, `getAcceptedChildrenForSlot`, `getRegistrationVersion`, plus aggregation helpers (`getTotalCount`, `getCountByType`, `getCoverageByVertical`, `getKnownTokens`). Imported via `import { ... } from "@/lib/visual-editor/registry"`.

**8 component kinds:** `widget` / `focus` / `focus-template` / `document-block` / `pulse-widget` / `workflow-node` / `layout` / `composite`. Each registration carries identity (type + name + displayName + category), scope (verticals + userParadigms + optional productLines), token consumption (`consumedTokens` array of `tokens.css` variable names without `--`), `configurableProps` (typed prop schema across 8 `ConfigPropType` values including `tokenReference` + `componentReference`), `slots` for composition, `variants` for per-variant overrides, `schemaVersion` + `componentVersion` for migration tracking, and an `extensions` JSONB-shape forward-compat field.

**Phase 1 population (17 components):** 6 widgets (cross-vertical foundation + manufacturing per-line) + 5 Focus types + 2 Focus templates + 2 document blocks + 2 workflow node types. Registrations live in shim files at `lib/visual-editor/registry/registrations/` (so existing component files stay untouched in Phase 1); `auto-register.ts` is the side-effect-on-import barrel that App.tsx imports at bootstrap. **The registry is the canonical way to make a component visually editable** — new visually-relevant components must register themselves so the editor can target them. Per-tenant theme override persistence ships in Phase 2 alongside the actual visual editor UI; debug inspector lives at `/visual-editor/registry` (admin platform).

**Canvas widget-renderer registry (R-1.6.12, 2026-05-27):** The Component Registry described above is the **visual-editor metadata registry** — admin-side metadata catalog covering component-kind enumeration, registration mechanism, public API for the visual editor's authoring surface. The visual-editor metadata registry lives at `frontend/src/lib/visual-editor/registry/` and serves authoring-time concerns: "what component kinds exist?", "what are their default property schemas?", "what UI variants are registered?"

The **canvas widget-renderer registry** is a distinct second registry serving runtime concerns. Canvas runtime (rendering authored widgets to operator-facing surfaces) consults a separate registry mapping component_kind → runtime renderer component. Canvas widget-renderer registry lives at `frontend/src/lib/canvas/widget-renderers.ts`; entries register at module import time via `registerWidgetRenderer(component_kind, renderer)` and are consumed by canvas rendering layer at runtime.

The two-layer distinction surfaced during WB-cycle work as substrate boundaries clarified: visual editor needs metadata about component kinds (for the authoring UI's component-kind palette, property schemas, etc.); canvas runtime needs renderer mappings (for actual DOM emission). Both layers consume the same component_kind enumeration but serve distinct runtime concerns. Substrate authors registering a new component_kind register against both layers — metadata in visual-editor registry + renderer in canvas widget-renderer registry.

Pattern application: when adding a new component kind, register at both layers from foundation (not retrofit). Missing canvas widget-renderer registration manifests as runtime "unknown widget kind" fallback rendering; missing visual-editor metadata registration manifests as authoring-time absence from component-kind palette. Both gaps surface reactively rather than at registration time.

Cross-reference: DECISIONS.md 2026-05-27 — Shared-dispatcher-multiple-authoring-surfaces canon (same architectural pattern at dispatcher altitude); DECISIONS.md 2026-05-27 — WYSIWYG discipline as canvas-layout-model constraint (relevant when canvas widget-renderer must match authoring-time visual representation).

### Theme Resolution (Admin Visual Editor — Phase 2, May 2026)

`platform_themes` table (migration `r79_platform_themes`) stores token overrides as one row per `(scope, vertical?, tenant_id?, mode)` tuple, with write-side versioning (every save deactivates the prior active row + inserts a new active row with `version + 1`). The full version trail accumulates as `is_active=false` rows for future history UI; partial unique index on the canonical tuple where `is_active=true` enforces "at most one active row per tuple."

**Inheritance order is computed at READ time** (`platform_themes.theme_service.resolve_theme`):

```
platform_default(mode)
    + vertical_default(vertical, mode) overrides on top
        + tenant_override(tenant_id, mode) overrides on top
```

Deeper scope wins. Empty `token_overrides: {}` is valid ("inherit fully from parent"). Read-time resolution means: changing a vertical default propagates immediately to every tenant in that vertical that hasn't overridden the affected tokens — no migration, no batch job, no cache invalidation.

**Mode is part of theme identity.** Light and dark themes are independent records — editing light mode's `--accent` does not affect dark mode's `--accent`. The editor's mode toggle switches which row is being edited; the preview's mode toggle is orthogonal (operator can edit light while viewing dark, or vice versa).

**Override semantics — only-the-deltas.** Overrides store ONLY the values that differ from the parent scope, not the full token set. A vertical-default row with `token_overrides: {"accent": "..."}` says "vertical X overrides accent + inherits everything else from platform default." Resolving for a tenant in vertical X without their own override yields platform's surface tokens + vertical's accent.

**Frontend mirrors the backend resolver.** `frontend/src/lib/visual-editor/themes/theme-resolver.ts` exports `composeEffective(mode, stack)` — same merge semantics for the editor's draft state, applied via CSS custom properties on a sandboxed preview wrapper element. Editor's own UI lives outside the wrapper so it stays unaffected by the operator's draft. The frontend resolver and backend resolver must agree on merge order; integration tests assert equivalence.

**Admin endpoints** at `/api/platform/admin/visual-editor/themes/*` (all `get_current_platform_user` — relocated May 2026):
- `GET /` (list rows with filters), `GET /{id}` (single row), `POST /` (create — versions a prior row at the same tuple if one exists), `PATCH /{id}` (replace overrides + bump version), `GET /resolve?mode&vertical&tenant_id` (full inheritance walk for the editor's live preview).

**Token catalog** at `frontend/src/lib/visual-editor/themes/token-catalog.ts` is the source of truth for "what tokens exist + what their platform defaults are" (across both light and dark mode). 80 tokens cataloged across 17 categories. Vitest catalog-completeness test parses `tokens.css` at test time and asserts every `--name` is represented in the catalog — drift is caught fast.

**OKLCH-native editing.** The color picker (`controls/OklchPicker.tsx`) edits in OKLCH coordinates directly — L (0..1), C (0..0.4), H (0..360), with optional alpha — not via hex-to-oklch conversion. Per Aesthetic Arc Session 2 the warm-family hue rules from DESIGN_LANGUAGE.md only stay interpretable when the operator works in OKLCH space. Swatch preview converts via Ottosson 2020 (`oklchToSrgb` in `theme-resolver.ts`) for display only.

**Live preview lives at `/visual-editor/themes` (admin platform).** Renders all 17 Phase 1 components inside a sandboxed CSS-variable scope; token edits propagate within one render frame (no debouncing — CSS variable writes are essentially free). Autosave debounces at 1.5s. Manual save commits immediately. Per the Phase 2 build, the preview uses structurally faithful stand-ins (cards, Focus shells, document blocks, workflow nodes) that consume the same design tokens as the real components — eliminating dependence on the live API while preserving "edit a token, see it everywhere" semantics. **Tenant-facing Workshop UI ships in a later phase** (Phase 3+); admin-side editing of tenant overrides is supported for troubleshooting / support.

### Component Configuration (Admin Visual Editor — Phase 3, May 2026)

`component_configurations` table (migration `r81_component_configurations`) stores per-component prop overrides as one row per `(scope, vertical?, tenant_id?, component_kind, component_name)` tuple. Same architectural pattern as `platform_themes` (Phase 2) — three-scope inheritance (`platform_default` → `vertical_default` → `tenant_override`), READ-time resolution, write-side versioning (every save deactivates the prior active row + inserts a new active row with `version + 1`).

**Configurations are NOT mode-specific.** Most component config (a widget's density, an action button's label, a refresh interval) doesn't differ light vs. dark. If a future prop needs mode-awareness, the schema can declare per-mode variants; Phase 3 ships configurations as mode-agnostic.

**Registry as source of truth.** The component registry stores defaults + bounds (in `frontend/src/lib/visual-editor/registry/registrations/*.ts`); `component_configurations` stores ONLY the overrides. The backend `app/services/component_config/registry_snapshot.py` mirrors the registry's prop schemas for write-time validation — out-of-bounds entries return HTTP 400 at the boundary. The snapshot is a manual mirror; the vitest backfill suite catches drift.

**Validation discipline.** Writes are validated against the snapshot:
- Unknown components → `UnknownComponent` (HTTP 400)
- Unknown prop keys → `PropValidationError` (HTTP 400)
- Out-of-bounds numeric / enum / string-length → `PropValidationError` (HTTP 400)
- Wrong-type values (string for boolean, etc.) → `PropValidationError` (HTTP 400)
- Frontend prevents most violations at the input layer (number sliders clamp; enum dropdowns show only valid options; string inputs enforce maxLength).

**Orphaned overrides** — when a registration removes a prop, pre-existing overrides for that prop become orphaned. Resolution silently drops them (logs a warning) and surfaces the keys in `ResolvedConfiguration.orphaned_keys` so the admin UI can flag for cleanup. The system-of-record stays consistent without crashing on registry refactors.

**Admin endpoints** at `/api/platform/admin/visual-editor/components/*` (all `get_current_platform_user` — relocated May 2026):
- `GET /` (list with filters), `GET /{id}` (single row), `GET /resolve?component_kind&component_name&vertical&tenant_id` (full inheritance walk for editor preview), `GET /registry` (snapshot for editor's component browser), `POST /` (create — versions a prior row at the same tuple), `PATCH /{id}` (replace overrides + bump version).

**Editor lives at `/visual-editor/components` (admin platform).** Three-pane layout: left = component browser organized by ComponentKind + scope/mode/vertical selectors; center = configurable-prop editor with auto-generated controls per `ConfigPropSchema` type (boolean → switch; number → bounds-aware slider; enum → segmented-control / dropdown; tokenReference → category-scoped picker reusing the Phase 2 catalog; componentReference → component picker filtered by `acceptedTypes`; array → list editor; object → JSON textarea, Phase 3 stub); right = single-component live preview using extended `preview-renderers.tsx` that applies override values visually (config-aware renderers for widget:today, widget:operator-profile, widget:anomalies, document-block:header-block, workflow-node:send-communication; others fall through to Phase 2 stand-ins). "Show all instances" toggle renders three preview cards with the same configuration to demonstrate consistency. Cross-links between `/admin/themes` and `/admin/components` in each editor's top bar — admins move between them frequently because component appearance is the product of both layers.

**Phase 3 also backfilled the 17 Phase 1 registrations**: `componentVersion` bumped 1 → 2; `configurableProps` expanded from minimal placeholder sets to comprehensive surfaces — **150 props total across 17 components**, 7–11 per component. Each prop carries `type`, `default`, `bounds` where applicable, `displayLabel` and/or `description`, plus per-type extras (`tokenCategory` for token references, `componentTypes` for component references, `itemSchema` for arrays). The vitest `Phase 3 backfill validation` suite asserts ≥3 props per component, all required schema fields populated, and tokenReference / componentReference props declare scope. **The component effective rendered appearance combines** (1) the active theme (tokens.css overridden by `platform_themes`) + (2) the component's effective configuration (registration defaults overridden by `component_configurations`) + (3) instance-level data passed at runtime. The two editors are intentionally separate — different concerns, different inheritance roots, different tables.

### Workflow Canvas (Admin Visual Editor — Phase 4, May 2026)

`workflow_templates` table (migration `r82_workflow_templates`) stores platform-default + vertical-default workflow definitions as canvas_state JSONB blobs (nodes + edges + trigger + version). `tenant_workflow_forks` table stores per-tenant forks with `forked_from_template_id` + `forked_from_version` provenance and a `pending_merge_available` flag set when the upstream template advances. **Locked-to-fork merge semantics**: forks REPLACE the inheritance chain rather than overlay. When a tenant forks a vertical_default template, subsequent vertical_default updates DO NOT auto-propagate to the fork; instead `mark_pending_merge` flags the fork for admin review. `accept_merge` replaces the fork's canvas_state with the new template's; `reject_merge` preserves the fork's canvas_state but updates `forked_from_version` so the pending-merge banner clears.

**Resolver inheritance order** (`workflow_templates.template_service.resolve_workflow`): tenant fork → vertical_default → platform_default. First match wins (no overlay merging at READ time per locked-to-fork semantics). Returns `{workflow_type, vertical, tenant_id, source, source_id, source_version, canvas_state, pending_merge_available}` so the caller knows which tier answered.

**Canvas state schema** lives in `app/services/workflow_templates/canvas_validator.py` with a frontend mirror at `frontend/src/lib/visual-editor/workflows/canvas-validator.ts`. Both validators MUST agree on schema rules: required keys (`version` + `nodes` + `edges`), node id uniqueness, valid node types (28 canonical types: start/end, engine action types, Phase 1 registry workflow-node names, cross-tenant primitives), edge reference integrity, cycle detection via three-color DFS (`is_iteration=true` edges excluded). Empty `{}` canvas is valid (unauthored draft). The validators are tested cross-reference: every CanvasState valid on one side must be valid on the other.

**Admin endpoints** at `/api/platform/admin/visual-editor/workflows/*` (all `get_current_platform_user` — relocated May 2026):
- `GET /` (list with filters — metadata only, no canvas_state to keep payloads small), `POST /` (create), `GET /resolve?workflow_type&vertical&tenant_id` (inheritance walk), `GET /{id}` (full canvas), `GET /{id}/dependent-forks` (list forks of a vertical_default), `PATCH /{id}` (update; `?notify_forks=true` flags every dependent fork as `pending_merge_available`), `POST /{id}/fork` (creates a tenant fork), `POST /forks/{id}/accept-merge`, `POST /forks/{id}/reject-merge`, `GET /forks/` (list).

**Editor lives at `/visual-editor/workflows` (admin platform).** Three-pane layout: left = scope selector + vertical/workflow_type/metadata + dependent forks list; center = node-list canvas with palette across the top (start/action/decision/branch/parallel_split/parallel_join/schedule/send-communication/generation-focus-invocation/cross_tenant_order/cross_tenant_request/playwright_action/log_vault_item/end), selectable nodes show outgoing edges with conditions, validation error banner above when canvas fails `validateCanvasState`; right = node configuration form with type dropdown + id/label/config-JSON inputs + outgoing edges with add/remove. Save validates client-side first; failed validation blocks save. "Save and notify forks" is an explicit alias of save with `notify_forks=true` for vertical_default updates. Cross-links to `/admin/themes`, `/admin/components`, `/admin/registry` in the top bar.

**Phase 4 backfill** seeded 2 vertical_default workflows via `scripts/seed_workflow_templates_phase4.py`: `funeral_cascade` (17 nodes — funeral_home vertical: start → trigger → generate_case_file → branch_disposition → burial/cremation paths → parallel_join → obituary/service/program/notification/death_cert/grief_check_in → end) + `quote_to_pour` (16 nodes — manufacturing vertical: start → trigger → sales_order → check_inventory → in_stock/production paths → join → qc_check → delivery_docs/log_anomaly → invoice → collections → end). Both authored as canvas_state JSONB in shape identical to what the admin canvas would produce; both validate successfully via `validate_canvas_state`. The seed is idempotent (skip-if-exists at the `(scope, vertical, workflow_type)` tuple).

### Component Class Configuration (Admin Visual Editor — May 2026)

`component_class_configurations` table (migration `r83_component_class_configurations`) introduces a **class-level configuration layer** in the inheritance chain. Many visual properties are properly scoped to a class of components rather than to individual components — "all widgets share this shadow elevation," "all entity cards have softer corners." The class layer expresses these defaults at the class level; per-component scopes layer on top.

**Inheritance chain (post-class-layer)**:

```
registration_default
    + class_default(component_class)        ← NEW (May 2026)
        + platform_default(component_kind, component_name)
            + vertical_default(vertical, component_kind, component_name)
                + tenant_override(tenant_id, component_kind, component_name)
                    + draft (operator's unsaved edits)
```

Class defaults apply to every component in the class; per-component scopes override at matching keys. Backend resolution at `app/services/component_config/config_service.py::resolve_configuration` walks the chain in this order; the response's `sources` array distinguishes class-default sources from per-component sources via a `scope` discriminator.

**Class vocabulary canonical = ComponentKind for v1.** Each component belongs to exactly one class (its ComponentKind). Storage is array-typed (`componentClasses: string[]`) so multi-class extension lands without schema migration. The 9 v1 classes:
- `widget` · `entity-card` · `focus` · `focus-template` · `document-block` · `workflow-node` · `button` · `form-input` · `surface-card`

The four new ComponentKinds (`entity-card`, `button`, `form-input`, `surface-card`) join the existing 8 (`widget`, `focus`, `focus-template`, `document-block`, `pulse-widget`, `workflow-node`, `layout`, `composite`); the migration extends both the `component_configurations.component_kind` CHECK constraint and the new `component_class_configurations.component_class` CHECK constraint to permit them.

**Class-level configurable props** are intentionally narrow — declared per-class in `frontend/src/lib/visual-editor/registry/class-registrations.ts` (canonical source of truth) with a backend mirror at `backend/app/services/component_class_config/class_registry_snapshot.py` for write-time validation. ~5–8 props per class, totaling ~50–60 across the 9 classes. Examples: widget class declares `shadowToken`, `surfaceToken`, `radiusToken`, `density`, `borderTreatment`, `hoverElevation`, `headerStyle`, `showFooter`. Validation rejects unknown prop keys, out-of-bounds enum values, wrong-type values.

**`component_class_configurations` table** stores class-scoped overrides. Single scope (`class_default`) — there's no vertical/tenant variant of a class default; class defaults apply platform-wide. Same write-side versioning pattern as `platform_themes` and `component_configurations` (each save deactivates the prior active row + inserts a new active row with `version + 1`; partial unique on `is_active=true` enforces "at most one active row per class"). Service layer at `app/services/component_class_config/class_config_service.py`.

**Admin endpoints** at `/api/platform/admin/visual-editor/classes/*` (all `get_current_platform_user`):
- GET / (list rows; filter by component_class), POST / (create / version), PATCH /{id} (update), GET /resolve?component_class= (resolved class default), GET /registry (class registry snapshot for the editor's controls), GET /{id} (single row).

**Class editor lives at `/visual-editor/classes`** (admin platform). Three-pane layout matching the Phase 3 component editor redesign: left = class browser (9 classes, search, member count); center = multi-component preview rendered in the appropriate context frame for the class (3-column dashboard for widgets, Focus shell for Focus types, document page for doc-blocks, workflow canvas for nodes); right = compact class-level prop controls. Editing the widget class's `density` updates all widgets in the preview together — that's the whole reason the layer exists.

**Component editor integration** (also `/visual-editor/components`): the resolver now applies class defaults before per-component scopes; the right rail's source-badge vocabulary gains a `class-default` source (badge letter `C`) shown for props inherited from the class layer; the right rail's component-identity card gains a class-membership pill with a "Edit class defaults →" link to the class editor.

**Frontend resolver** at `frontend/src/lib/visual-editor/components/config-resolver.ts` extended: `ConfigStack` adds `classLayer` + `classNames` slots; `mergeConfigStack` merges in canonical order `class → platform → vertical → tenant → draft`; `stackFromResolvedConfig` maps backend `class_default` sources into the `classLayer` slot; `resolvePropSource` returns `"class-default"` for class-only props.

### Documents Arc — Block-Based Authoring (Phase D-10/D-11, June 2026)

Documents arc shipped through Phase D-9 (May 2026) established the canonical Document + DocumentVersion model, two-tier (platform → tenant) template registry, native e-signature, cross-tenant DocumentShare, delivery abstraction, and 18 seeded platform templates with monolithic Jinja `body_template` strings.

**Phase D-10 + D-11 (June 2026)** add block-based authoring + a vertical tier:

- **Block model** (`document_template_blocks` table per migration `r85_document_template_blocks`). Templates that opt into block authoring have one row per block. Block records carry `block_kind` + `position` + `config` JSONB + optional `condition` (Jinja expression for `conditional_wrapper` blocks) + optional `parent_block_id` self-FK (children of conditional wrappers). The composer reads blocks ordered by position and emits Jinja per kind.
- **Block registry** at `app/services/documents/block_registry.py` — six canonical kinds: `header`, `body_section`, `line_items`, `totals`, `signature`, `conditional_wrapper`. Each kind has `kind` + `display_name` + `description` + `config_schema` + `compile_to_jinja(config, children_jinja)` + `declared_variables(config)` + `accepts_children`. New kinds register additively.
- **Composer** at `app/services/documents/block_composer.py` — `compose_blocks_to_jinja(db, template_version_id, css_variables)` walks top-level blocks, recurses into conditional_wrapper children via explicit DB query (NOT relying on SA relationship cache), wraps the composed body in HTML+CSS boilerplate. Returns `ComposedTemplate(body_template, declared_variables, block_count)`. Block service calls the composer after every mutation; the composed Jinja is written back to `document_template_versions.body_template`. **The render pipeline is unchanged** — `document_renderer.render()` reads `body_template` exactly as it does for monolithic Jinja templates.
- **Vertical tier** on `document_templates` (migration `r86_document_template_vertical_tier`). Documents now use the same three-tier scope as themes / component_configurations / focus_compositions / workflow_templates: `platform_default → vertical_default → tenant_override`. `template_loader._resolve_version(db, template_key, company_id, vertical=None)` walks tenant → vertical → platform; the `vertical` kwarg is optional for back-compat with pre-D-11 callers.
- **Document type catalog** at `app/services/documents/document_types.py` — 12 curated types across 9 categories. Types are platform-curated; new types require platform code change. Tenants author templates of existing types only. Each type's `starter_blocks` list scaffolds new templates.
- **Two authoring paths coexist**: legacy Jinja templates (the 18 seeded platform templates + any tenant template authored as raw Jinja in `/vault/documents/templates/:id`) stay where they are with their textarea editor. Block-authored templates are the new model, edited via the visual editor's Documents tab at `/visual-editor/documents`. No forced migration; both paths render through the same `document_renderer`.

**Authoring discipline**: block mutations (add / update / delete / reorder) are bounded to draft versions. Once activated, a version is immutable — mutation attempts return 409. The activate / rollback / fork / test-render flow uses the existing Phase D-3 endpoints unchanged.

**Migration head**: `r84_focus_compositions` → `r85_document_template_blocks` → `r86_document_template_vertical_tier`.

### Visual Editor Top-Level Structure (May 2026 reorganization)

The visual editor surfaces seven purpose-specific editor pages, each handling a distinct authoring concern:

| Editor | Route | Handles |
|---|---|---|
| Themes | `/visual-editor/themes` | Token-level editing — colors, surfaces, shadows, motion. Full-platform live preview. |
| Focus Editor | `/visual-editor/focuses` | Focus template authoring (per-template configuration AND accessory-layer composition in one surface, three tabs: Configuration / Composition / Preview Settings). Hierarchical browser organized by 5 Focus types. |
| Widget Editor | `/visual-editor/widgets` | Widget editing with mode toggle: Edit Individual Widgets (per-widget config) OR Edit Widgets as Class (class-level config affecting all widgets). |
| Documents | `/visual-editor/documents` | Placeholder — Phase 2 will ship full document template authoring backed by Documents arc substrate. |
| Classes | `/visual-editor/classes` | Cross-class view — every component class in one surface for cross-cutting defaults. Widget Editor + Focus Editor provide narrower scoped paths into the same data. |
| Workflows | `/visual-editor/workflows` | Canvas authoring for vertical_default workflow templates. Hierarchical browser left rail (categories = workflow types). Locked-to-fork merge semantics. |
| Registry | `/visual-editor/registry` | In-memory component registry inspector. Verify metadata coverage; reverse-lookup tokens to consumers. |

**`HierarchicalEditorBrowser` as canonical browser pattern** at `frontend/src/bridgeable-admin/components/visual-editor/HierarchicalEditorBrowser.tsx` — purely-presentational two-level browser (categories with child templates underneath). Used by Focus Editor + Workflows. New editors with categorized content reuse the same component rather than building bespoke browsers.

**Reorganization decisions (May 2026):** the previous generic Component Editor at `/visual-editor/components` was dismantled in favor of purpose-specific surfaces — operators think in domain terms ("author a Focus", "edit a widget"), not in "component-of-kind-X" terms. The standalone Compositions page at `/visual-editor/compositions` was folded into Focus Editor as a tab — composition authoring is naturally part of authoring a Focus template (the accessory layer that surrounds the bespoke core per the May 2026 accessory-layer pattern documented at §4 Focus Composition Layer below). Both routes redirect to the new structure. The underlying component files (ComponentEditorPage, CompositionEditorPage) remain in the codebase as library code; full deletion is sequenced to a follow-up cleanup arc once Widget + Focus Editor reach feature parity.

**Documents placeholder as scaffolding**: the Documents tab exists in nav so the top-level structure is established; the actual document-authoring editor ships in Phase 2 backed by the existing Documents arc substrate (Phase D-1 through D-9, migrations r20-r28).

### Studio-builder Mapping Table (WB-cycle close, 2026-05-27)

Canonical reference for Studio-builder substrates: frontend mount → backend router → realm → client. The table prevents repeat investigation of "where does Studio-builder X mount + what realm + what backend route prefix + which client?" — a question that surfaced reactively across WB cycle + studio nav arc work.

| Builder | Frontend mount | Backend router | Realm | Client |
|---|---|---|---|---|
| Theme Editor | `/admin/visual-editor/themes` (Studio) | `/api/platform/admin/visual-editor/themes/*` | platform | `adminApi` |
| Focus Editor | `/admin/visual-editor/focuses` (Studio) | `/api/platform/admin/visual-editor/focuses/*` | platform | `adminApi` |
| Widget Builder | `/admin/visual-editor/widgets` (Studio) + `/admin/widget-builder` (legacy alias) | `/api/platform/admin/visual-editor/widgets/*` (canonical) + `/api/v1/widget-builder/*` (tenant consumer path) | platform (Studio) + tenant (consumer) | `adminApi` (Studio) + `apiClient` (tenant) |
| Document Composer | `/admin/visual-editor/documents` (Studio) | `/api/platform/admin/visual-editor/documents/*` | platform | `adminApi` |
| Component Classes | `/admin/visual-editor/classes` (Studio) | `/api/platform/admin/visual-editor/classes/*` | platform | `adminApi` |
| Workflow Editor | `/admin/visual-editor/workflows` (Studio) | `/api/platform/admin/visual-editor/workflows/*` | platform | `adminApi` |
| Component Registry | `/admin/visual-editor/registry` (Studio) | `/api/platform/admin/visual-editor/registry/*` | platform | `adminApi` |

**Canonical pattern:** Studio-authored substrates default to platform realm via `/api/platform/admin/visual-editor/*` route prefix, consumed through `adminApi` client with `get_current_platform_user` auth dependency. Tenant-router consumer paths (`/api/v1/*`) exist for substrates with tenant-side consumers (e.g. Widget Builder's composed widgets registered at tenant boot); those paths route through realm-agnostic service layer (see `Realm-agnostic service layer` paragraph above) so consumption is realm-coherent at the service layer.

**Discoverability:** Each builder mounts in the Studio admin shell's left rail per Studio navigation arc (`3a019e1`). Builder rail entry registration lives in `frontend/src/admin/studio/nav-registry.ts`; entries reference the canonical frontend mount path. Future builders ship with rail entry registration as substrate deliverable (DECISIONS.md 2026-05-27 — Discoverability canon for operator-facing substrate cycles).

Cross-references:
- `Visual Editor Top-Level Structure` H3 subsection (editor-page-level enumeration; this table is broader)
- `Realm-agnostic service layer` paragraph (service-layer realm-coherence pattern)
- DECISIONS.md 2026-05-27 — Discoverability canon for operator-facing substrate cycles (auth-realm reachability verification)
- `docs/investigations/2026-05-27-widget-builder-auth-realm.md` (WB-cycle-followup-2 investigation context)

### Focus Composition Layer (Admin Visual Editor — May 2026)

**Core-plus-accessories pattern (canonical principle).** Focus types follow a core-plus-accessories pattern. The Focus's operational core is built as code — a React component with whatever structure best serves the operational job (a dispatcher kanban, a scribe panel, a decision flow, a canvas authoring surface). The Focus integrates with the composition layer to render an accessory layer around or alongside the core. The accessory layer is composition-authored: which widgets appear, where they're positioned, what's in their per-vertical arrangement. The core is not composition-authored.

Visual editor authoring controls the periphery; code authoring controls the core. Both are real authorship at different layers. New Focus types follow this pattern automatically: build the core in code, then opt into composition for the accessory layer using `ComposedFocus` (or a wrapper like `SchedulingFocusWithAccessories`) and `compositionFocusType`. There is no need to compose the core itself.

**Production Focus types using this pattern**: `funeral-scheduling` (May 2026 — `SchedulingKanbanCore` renders the dispatcher kanban core; the seeded scheduling composition renders the accessory widgets — today / recent_activity / anomalies — in a sidebar rail). Future Focus types (arrangement_scribe, triage_decision, generation Focus templates like wall designer + drawing takeoff per BRIDGEABLE_MASTER §3.26.11.12) will follow the same pattern when built — operational core as code, accessory layer authored via composition.

`focus_compositions` table (migration `r84_focus_compositions`) introduces canvas-based composition for Focus layouts. The Focus's underlying behavior (kanban drag-drop, scribe panel logic, decision flow) stays as code; what becomes data-driven is the **arrangement** of components within the Focus shell — which components appear, where they're positioned (12-column grid), what size they are, and per-placement configuration overrides.

**Inheritance chain** (parallel to themes / component_configurations / workflow_templates):

```
platform_default
    + vertical_default(vertical)
        + tenant_override(tenant_id)
```

First-match-wins at READ time — a composition is a complete layout, not a partial overlay. Absent composition means the Focus falls back to its hard-coded layout (backward compat — no need to migrate every existing Focus immediately).

**Placement record shape** (within the `placements` JSONB array): `placement_id` (unique within composition) + `component_kind` + `component_name` + `grid: { column_start: 1..12, column_span: 1..12, row_start, row_span }` (column_start + column_span ≤ 13) + `prop_overrides: Record<string, unknown>` (layered on top of normal inheritance) + `display_config: { show_header?, show_border?, z_index? }`. Canvas config: `total_columns` (default 12), `row_height` ("auto" or pixel value), `gap_size`, `responsive_breakpoints`, `background_treatment` (token reference), `padding`.

**Service layer at `app/services/focus_compositions/composition_service.py`**: validation rejects malformed placements, out-of-bounds grid coords, duplicate `placement_id`s. **Overlapping placements are PERMITTED** — `z_index` handles intentional overlap; service emits a warning but doesn't reject. References to unknown components (not in REGISTRY_SNAPSHOT) emit a warning but don't reject — the registry can evolve.

**Admin endpoints** at `/api/platform/admin/visual-editor/compositions/*` (all `get_current_platform_user`): `GET /` (list with filters), `POST /` (create / version), `PATCH /{id}` (replace placements / canvas_config), `GET /resolve?focus_type=&vertical=&tenant_id=` (full inheritance walk), `GET /{id}` (single row).

**Frontend renderer** at `frontend/src/lib/visual-editor/compositions/CompositionRenderer.tsx` consumes a `ResolvedComposition` and renders a CSS grid with each placement positioned at its declared cells. Used in two places:
1. The composition editor's canvas pane (with editor affordances — grid lines, selection borders, click handlers)
2. The Focus runtime (when a Focus has a composition; replaces the hard-coded layout) — Focus runtime integration is deferred follow-up; resolver + renderer + editor + seeded compositions all in place.

**Composition editor lives at `/visual-editor/compositions`** (admin platform). Three-pane layout: left = component palette (filtered to canvas-placeable kinds — widget / focus / focus-template by default); center = `CompositionRenderer` in editor mode; right = scope selector + canvas config + selected-placement controls (grid coords, delete button). **v1 ships form-based grid editing**: click a placement to select, edit grid coords in the right rail. Drag-drop positioning + corner-handle resize deferred to a follow-up — they require non-trivial gesture infrastructure that this phase scopes out per "ship the foundation" approach.

**Canvas placement metadata on registrations**: `RegistrationMetadata` gains optional `canvasPlaceable: boolean` and `canvasMetadata` fields. When omitted, `canvasPlaceable` defaults to true for `widget` / `focus` / `focus-template` kinds and false for the rest (primitives, document blocks, workflow nodes have their own composition surfaces). `canvasMetadata` declares `minDimensions` / `defaultDimensions` / `maxDimensions` / `aspectRatio` / `resizable`. Helper `getCanvasMetadata(entry)` returns sensible defaults (4×3 cells for widgets, 12×8 for Focus types) when no metadata is declared.

**Seed-script backfill** at `backend/scripts/seed_focus_compositions.py`: idempotent (re-runs version up via service-layer mechanics) seeds `vertical_default` compositions for `scheduling` Focus type at funeral_home + manufacturing. Following the core-plus-accessories canonical principle, the seeded compositions describe ONLY the accessory layer — 3 widgets stacked vertically in a single-column canvas: `widget:today` + `widget:recent_activity` + `widget:anomalies`. The kanban core itself (`SchedulingKanbanCore`, 1,714 LOC of dispatcher operational behavior) is rendered by code in `SchedulingFocusWithAccessories.tsx` and is **NOT** a placement in the composition. Per-vertical differentiation in the seeded baseline is intentionally identical (FH and MFG share the 3-accessory shape); future per-vertical accessory variations land via the visual editor when concrete operator signal warrants. Widget names use snake_case to match the canvas widget renderer registry (`registerWidgetRenderer("today", TodayWidget)` etc.) — runtime dispatch in `CompositionRenderer.tsx` resolves via `getWidgetRenderer(component_name)` to the production widgets with operational data.

### Bridgeable Vault (V-1 complete — April 2026)

**Bridgeable Vault is the shared foundational infrastructure layer that every tenant sees regardless of vertical.** It's the platform chassis that the verticals configure views over — not a feature, not a module you can disable. Top-level nav entry at `/vault`, `VaultHubLayout` wraps the 5 registered services.

**5 services registered** (seed in `backend/app/services/vault/hub_registry.py`):

| service_key | Display | Route prefix | Permission | Phase |
|---|---|---|---|---|
| `documents` | Documents | `/vault/documents` | admin-per-route | V-1a |
| `crm` | CRM | `/vault/crm` | `customers.view` | V-1c |
| `intelligence` | Intelligence | `/vault/intelligence` | admin-per-route | V-1a |
| `notifications` | Notifications | `/vault/notifications` | (none) | V-1d |
| `accounting` | Accounting | `/vault/accounting` | `admin` | V-1e |

**V-1 shipped in 8 phases** across 3 weeks (April 2026): V-1a (hub frame + nav restructure), V-1b (overview dashboard + 5 widgets), V-1c (CRM absorption lift-and-shift), V-1d (notifications promoted + SafetyAlert merge + 5 new notification sources), V-1e (accounting admin consolidation — 6 sub-tabs), V-1f+g (Quote VaultItem dual-write + polymorphic delivery + JE Case A guard), bug fix (audit_service typo), V-1h (documentation). 10 overview widgets on the Vault landing page. 109+ Vault backend tests. Migration head: `r30_delivery_caller_vault_item`.

**Docs:**
- [`backend/docs/vault_architecture.md`](backend/docs/vault_architecture.md) — full internal architecture reference (service model, widget framework, cross-cutting capabilities, integration seams, migration history)
- [`backend/docs/vault_README.md`](backend/docs/vault_README.md) — developer entry point with key files + quick links
- [`backend/docs/vault_audit.md`](backend/docs/vault_audit.md) — pre-V-1 retrospective (ground-truth survey)
- Per-service guides under [`backend/docs/vault/`](backend/docs/vault/): [documents.md](backend/docs/vault/documents.md), [intelligence.md](backend/docs/vault/intelligence.md), [crm.md](backend/docs/vault/crm.md), [notifications.md](backend/docs/vault/notifications.md), [accounting.md](backend/docs/vault/accounting.md)

**V-2 candidates (not yet scoped):** Calendar (unified view over VaultItems with `event_type`), Reminders (proactive surface for upcoming events), CRM true absorption (Option B from the V-1 audit — make `CompanyEntity` a first-class VaultItem + unify the 4 parallel contact models), Vault Sharing generalization (D-6 `DocumentShare` abstraction extended to any VaultItem), notification preferences (per-user per-category opt-out + daily digest). All tracked in `backend/docs/DEBT.md`.

### Task Substrate (v1 complete — May 2026)

Bridgeable runs on tasks. The platform's operational model is task-centric: tasks are the canonical representation of work that needs attention. All operational events that require human awareness, decision, or action manifest as tasks. The platform's various capabilities relate to each other through task lifecycle — workflows create and complete tasks; Focuses enable task work; documents are often task outputs; communications are often task triggers and task outputs; Intelligence creates tasks from observations.

The task substrate is foundational, not feature. It exists at the level of Vault-as-foundation and workflow-as-orchestration — substrate that capabilities consume rather than capability among many.

User experience of the platform is fundamentally about task awareness and task completion. The platform's value proposition is helping users know what needs doing and helping them complete it efficiently, with reduced cognitive burden of tracking work mentally.

**Substrate shape.** Tasks are VaultItems with `item_type='task'` (12th value added to existing 11-value enum at v1 task substrate B1) + `task_details` join table for task-specific fields. The hybrid pattern preserves Vault-as-canonical-row-type while normalizing task-specific schema (assignee, lifecycle_shape, provenance, visibility, etc.) into a dedicated join table. Task service layer + Task façade preserves backward-compat for the 8 existing Task consumers; consumers query through service-layer abstraction rather than direct table access.

Task lifecycle is dual-shape: action shape (`created → assigned → in_progress ↔ blocked → done | cancelled`) for tasks requiring completion action; reminder shape (`informational → acknowledged | dismissed`) for time-based informational tasks that don't require completion. Lifecycle state machine implementation lives at `backend/app/services/tasks/lifecycle.py`; backward-compat mapping from existing 5-state machine ships in backfill.

Task provenance is polymorphic across 12 `provenance_kind` values (workflow_step, intelligence_observation, manual_creation, communication_inbound, integration_event, shelf_parking, coaching_observation, scheduled_recurring, triage_event, focus_completion, anomaly_detection, system_internal). Composite idempotency key `(provenance_kind + provenance_ref + event_kind)` is partial-unique at schema layer; this is load-bearing for the operationally-idempotent claim that task-creation-event-driven dispatch depends on.

**Plugin substrate.** Three plugin categories register against the task substrate (see PLUGIN_CONTRACTS.md):
- **Task creators** (workflow steps, Intelligence observations, communications, shelf parking, manual creation, future triage adapters)
- **Task surfaces** (list views, detail views, creation forms, Pulse Personal layer wire, briefings consumption, future authoring surfaces)
- **Task type behaviors** (lifecycle behaviors, surface defaults, routing defaults per task type)

v1 ships 5 task type behavior plugins: `generic_task`, `review_approval_task`, `scheduled_recurring_task`, `customer_communication_task`, `anomaly_resolution_task`. Future task types register additively against the substrate.

**Subscriber registry.** Task lifecycle events fire to a subscriber registry (7 event types × 6 v1 subscribers; sync dispatch with isolated try/except per subscriber at `backend/app/services/tasks/subscribers/`). v1 subscribers: `audit_writer` (active at substrate-foundation), `notification_dispatcher` (active post-B2 (c) refactor), `briefings_invalidator`, `pulse_invalidator`, `workflow_resumer`, `focus_closer` (all active post-B3 consumer integration).

**Producer integration.** (c)'s 8 producer sites flow through task substrate post-v1.5 B2 refactor: producer call-sites create tasks via `task_service.create_task_with_provenance`; notification dispatch fires from task-creation events via subscriber registry rather than producer-direct dispatch. Parity preserved bit-for-bit at recipient side. Site mapping documented at task substrate v1 completion artifact §2 producer refactor section (`docs/investigations/task_substrate_v1_completion.md`).

**Reference instances.** v1 task substrate shipped across 3 commits: `2fba161` (B1 substrate foundation + r108 Focus extension), `a400d1b` (B2 (c) producer refactor), `1c8dbbd` (B3 consumer integration + r109 routing rules + v1 arc close). v1 build prompt at `docs/investigations/task_substrate_v2_v1_build_prompt.md`; v1 completion artifact at `docs/investigations/task_substrate_v1_completion.md`. v2 sub-arcs (10-triage-queue adapters, family portal, substrate refinements) await operator-observable signals per task substrate v2 phasing doc §5.

### Command Bar Platform Layer (Phase 1 complete — April 2026)

The command bar is a **platform layer, not a UI component**, accessed via Cmd+K globally. Six logical layers:

```
CAPTURE LAYER     — keyboard input now; voice/ambient/camera in later phases
INTENT ENGINE     — classifies navigate / search / create / action / empty
RESOLUTION ENGINE — entity resolution (fuzzy via pg_trgm), recency weighting, tenant + permission filtering
ACTION REGISTRY   — navigate actions, create actions (Compose-as-registry), workflow + saved-view entries in later phases
RETRIEVAL ENGINE  — orchestrator + public response shape
SURFACE RENDERER  — overlay + result list + shortcut handling
```

**Backend platform layer** (`backend/app/services/command_bar/`):

| Module | Role |
|---|---|
| `registry.py` | OWNS `ActionRegistryEntry` type + singleton registry + seed. Pattern mirrors `OperationsBoardRegistry` / `vault.hub_registry`. Phase 2+ adds saved views; Phase 5 adds workflows; Phase 6 adds briefings. |
| `intent.py` | Rule-based classifier (no AI in Phase 1 — preserves p50 < 100 ms budget). 5 outcomes: navigate / search / create / action / empty. Record-number regex + exact-alias + create-verb + navigate-verb detectors. |
| `resolver.py` | pg_trgm fuzzy search across 8 entity types (fh_case, sales_order, invoice, contact, company_entity, product, document, task) via single UNION ALL per query. Recency weighting 1.0 → 0.3 over 180 days. Tenant isolation mandatory. `task` added Phase 5 (Triage Workspace migration r34) — twelfth audit-count recalibration fixed at Arc 4b.2a. `company_entity` added S-1 (entity-portal arc, 2026-07) riding the r33 trigram index — thirteenth recalibration. |
| `retrieval.py` | Orchestrator. OWNS the `QueryResponse` + `ResultItem` shape contract returned by `/api/v1/command-bar/query`. Frontend callers depend on this shape. Bumping it is a coordinated schema change. |

**New endpoint:** `POST /api/v1/command-bar/query` (contract in `backend/app/api/routes/command_bar.py`). Frontend UI at `frontend/src/components/core/CommandBar.tsx` fires it as a 4th parallel fetch alongside the existing `/core/command` + `/workflows/command-bar` + `/core/command-bar/search` calls. Results merge via type-ranked sort in the existing UI pipeline.

**Migration `r31_command_bar_trigram_indexes`:** `CREATE EXTENSION IF NOT EXISTS pg_trgm` + 6 GIN trigram indexes (via `CREATE INDEX CONCURRENTLY` inside `op.get_context().autocommit_block()`) on `fh_cases.deceased_last_name`, `sales_orders.number`, `invoices.number`, `contacts.name`, `products.name`, `documents.title`. Partial clean downgrade; extension left installed.

**Performance targets (p50 < 100 ms, p99 < 300 ms) enforced as BLOCKING CI gate** via `backend/tests/test_command_bar_latency.py`. Actual on dev hardware: **p50 = 5.0 ms, p99 = 6.9 ms** (50-sample sequential mixed-shape workload; seeded tenant with ~24 entities).

**Compose-as-registry refactor:** The old `wf_compose` workflow doesn't exist in code (confirmed via audit — only `wf_create_order` exists). Missing create actions (quote, invoice, contact, product) added to both the backend registry and the frontend action registry (`frontend/src/services/actions/registry.ts`) via `crossVerticalCreateActions`. Case creation stays in `funeralHomeActions.fh_new_arrangement` (FH-preset-only). Typing `new sales order` or `create quote` directly surfaces the create action at the top.

**Frontend:** `frontend/src/core/commandBarQueryAdapter.ts` is the interface-only adapter translating backend `ResultItem` → frontend `CommandAction`. No added logic. Full frontend registry reshape deferred to **Phase 5 (Triage Workspace)**.

**How to register a new action:**

1. Define an `ActionRegistryEntry` in `backend/app/services/command_bar/registry.py`'s seed path (or call `register_action()` from an extension's startup hook).
2. Permission / module / extension gates mirror `VaultServiceDescriptor` semantics — same filter pipeline.
3. The action is now queryable via `/api/v1/command-bar/query` immediately — no migration, no frontend change.

**Docs:** full architecture + Phase 2-7 plans live in `docs/BRIDGEABLE_MASTER_REFERENCE.md` §3.15 (forthcoming in the UI/UX arc planning pass). Build session log in `FEATURE_SESSIONS.md`.

### Command Bar Migration Tracking

Legacy endpoints kept alongside `/api/v1/command-bar/query` during the Phase 2+ frontend migration window. Deprecation classifications:

| Endpoint | Status | Plan |
|---|---|---|
| `POST /api/v1/command-bar/query` | **Active — canonical** | The platform layer contract. All new callers. |
| `POST /api/v1/ai/command` | **Deprecated** (marked in code) | Kept for the one remaining frontend caller (`core/CommandBar.tsx`'s intent-classifier fetch). Migrates off in Phase 4 when natural-language creation lands. Route collision note: `ai.py` registers the same path and wins on resolution order; `ai_command.py`'s handler is unreachable via `/ai/command` today. Pre-existing, not a Phase 1 regression. Fixed during the deprecated-endpoint removal sweep. |
| `POST /api/v1/ai/command/execute` | **Kept separate** | Action execution. Will migrate into the platform layer's workflow/action invoker in Phase 5 when the workflow registry lands. |
| `POST /api/v1/ai/parse-filters` | **Kept separate** | Orthogonal feature — parses natural-language filter queries for table/list views. Not command-bar work. No migration planned in this arc. |
| `POST /api/v1/ai/company-chat` | **Kept separate** | Per-company Q&A. Moves to Intelligence layer, not the command bar. |
| `POST /api/v1/ai/briefing/enhance` | **Kept separate** | Briefing enhancement. Phase 6 briefings will own their own path; this stays until then. |
| `POST /api/v1/core/command` | **Legacy** (active) | The existing intent-classification endpoint. Called in parallel with `/command-bar/query` today. Retirement target: Phase 4 once `/command-bar/query` absorbs its remaining behaviors. |
| `GET /api/v1/core/command-bar/search` | **Legacy** (active) | Unified record + document search. Absorbs into `/command-bar/query`'s resolver in Phase 4 when saved views + document search expand. Regression-covered in `backend/tests/test_ai_command_regression.py`. |
| `GET /api/v1/workflows/command-bar` | **Kept separate** | Workflow detection endpoint. Phase 5 moves workflows into the platform registry. |

**Do NOT add new callers to `/ai-command/command` or `/core/command`.** New work targets `/command-bar/query`.

**Retirement:** each legacy endpoint is deleted once every frontend caller has migrated. Tracked per-phase. No all-at-once deletion.

### Workflows — Scope + Dual Customization Paths (Workflow Arc Phase 8a)

Workflows live in the `workflows` table (existing from Workflow Engine Phase W-1). Workflow Arc Phase 8a added the `scope` field to classify every row into one of three values used by the three-tab builder UI:

- **`scope="core"`** — platform-wide workflows shipped with the platform. Visible to every tenant regardless of vertical. Today these are the 16 `wf_sys_*` workflows (month_end_close, ar_collections, statement_run, etc.). Tier 1 in the existing tier vocabulary. Three of these delegate to the accounting agent system (see "Agent-backed stubs" below).
- **`scope="vertical"`** — default workflows tied to a tenant's vertical. Only visible to tenants whose `company.vertical` matches. 21 workflows today (manufacturing: wf_compose, wf_mfg_*; funeral_home: wf_fh_*). Tiers 2 (default-on) + 3 (default-off).
- **`scope="tenant"`** — workflows owned by a specific tenant. `company_id` set. Created via the fork mechanism (below) or the built-in "New workflow" action. Tier 4.

Backfilled via migration `r36_workflow_scope`. CHECK constraint enforces the three-value set. Partial index on `forked_from_workflow_id` supports the "find all forks of this workflow" query.

**Dual customization paths — both supported, intentionally:**

1. **Soft customization (Option B — existing):** tenant enrolls in a platform workflow via `WorkflowEnrollment`, overrides specific step parameters via `WorkflowStepParam` rows with `company_id` set. Platform updates to the base workflow DO propagate (new steps appear; base parameter defaults update). Cheap, reversible. **Use when: "I want to tweak a parameter but stay on the base."**
2. **Hard customization (Option A — new in Phase 8a):** tenant clicks "Fork" on a core/vertical workflow; server creates an independent copy in tenant scope. `forked_from_workflow_id` + `forked_at` stamped on the fork. Platform updates do NOT propagate — the fork is the tenant's outright. **Use when: "I want to own this workflow and diverge."**

The two paths coexist. `app/services/workflow_fork.py::fork_workflow_to_tenant` is the fork service function; `POST /api/v1/workflows/{id}/fork` is the endpoint. Fork copies steps + DAG edges + platform-default step params (company_id IS NULL). One active fork per source per tenant (409 AlreadyForked prevents silent duplication). Tenant-scoped and non-forkable-scoped sources (e.g., a tenant's own workflow) reject fork with 403. The fork's `agent_registry_key` is cleared — a fork runs through `workflow_engine`, not `AgentRunner`.

**Agent-backed stubs (transitional):** Three `wf_sys_*` workflow rows (`wf_sys_month_end_close`, `wf_sys_ar_collections`, `wf_sys_expense_categorization`) have `agent_registry_key` pointing at entries in `app.services.agents.agent_runner.AgentRunner.AGENT_REGISTRY`. Execution delegates to the agent runner, NOT `workflow_engine`. The UI renders a "Built-in implementation" badge (indigo) on these cards; click-through goes to a read-only view instead of the builder editor (which would mislead users into thinking they can edit Python-class-backed steps). Phase 8b-8f migrates the agents into real workflow definitions; per migrated agent, the `agent_registry_key` clears on the workflow row and the badge disappears. The broader accounting agent system (13 agents, `AgentRunner` + `BaseAgent` + approval-gate + period-lock) stays separate from workflows until those migrations complete.

**Fork UX (deferred to Phase 8c):** The specific UX for when to fork vs. when to use soft customization deserves a design conversation that hasn't happened yet. Phase 8a ships both paths functionally + minimal affordances (Fork button on Core/Vertical rows); decision-support UI, explanatory copy, and "you have both options" messaging land in Phase 8c or whenever workflow customization UX is designed.

### Cash Receipts Matching — first agent-to-workflow migration (Workflow Arc Phase 8b)

Phase 8b is the reconnaissance migration — one accounting agent migrated end-to-end into a real workflow to discover the migration template that Phases 8c–8f apply systematically. Cash receipts was chosen for reconnaissance because it has the right characteristics: cross-vertical, SIMPLE approval (no period lock), no existing scheduler entry (net-new insertion), mid-complexity anomaly taxonomy.

**Primary deliverable:** [`WORKFLOW_MIGRATION_TEMPLATE.md`](WORKFLOW_MIGRATION_TEMPLATE.md) at project root — the checklist 8c–8f compare their audits against. Written as a deliverable alongside the migration itself (not retroactively).

**Pattern: parity adapter via service reuse.** `backend/app/services/workflows/cash_receipts_adapter.py` is a thin module that bridges triage actions + workflow steps to existing agent logic. `run_match_pipeline()` delegates end-to-end execution to `AgentRunner.run_job()` (zero logic duplication). Per-item triage actions (`approve_match`, `reject_match`, `override_match`, `request_review`) replicate the agent's CONFIDENT_MATCH branch write pattern (CustomerPaymentApplication + Invoice.amount_paid + Invoice.status). **Parity discipline:** a dedicated BLOCKING parity test (`test_cash_receipts_migration_parity.py`) asserts triage-path and legacy agent-path produce identical side effects — 9 tests across 5 categories: (a) PaymentApplication identity, (b) reject no-write, (c) anomaly resolution shape, (d) negative PeriodLock assertion, (e) pipeline-scale equivalence + cross-tenant isolation + triage engine integration.

**Pattern: `call_service_method` action subtype.** New in `workflow_engine.py` — a whitelisted dispatch table (`_SERVICE_METHOD_REGISTRY`) mapping `"{agent}.{method}"` keys to importable callables with allowed-kwargs safelists. Workflow definitions reference it via `{"action_type": "call_service_method", "method_name": "cash_receipts.run_match_pipeline", "kwargs": {...}}`. Auto-injected kwargs: `db`, `company_id`, `triggered_by_user_id`. Phase 8b adds one entry; 8c–8f add one per migrated agent — zero further engine changes needed.

**Pattern: triage queue as user-facing approval surface.** New `cash_receipts_matching_triage` queue (`backend/app/services/triage/platform_defaults.py`) with 5 actions (approve/reject/override/request_review/skip), 2 context panels (related_entities + ai_question), invoice.approve permission gate, cross-vertical. Direct query builder (`_dq_cash_receipts_matching_triage`) returns unresolved `AgentAnomaly` rows ordered CRITICAL→WARNING→INFO with amount tiebreak. Related entity builder (`_build_cash_receipts_matching_related`) returns payment + customer + top-5 candidate invoices (ranked by |balance − payment| proximity) + past 3 applied payment/invoice pairs.

**Pattern: AI question prompt seeded via Option A idempotent.** `triage.cash_receipts_context_question` seeded by `backend/scripts/seed_triage_phase8b.py`. Same seed discipline as Phase 6 briefings: fresh install → v1 active; matching content → no-op; differing content → deactivate v1, create v2; multiple versions (admin customization) → skip with warning log.

**Pattern: `wf_sys_cash_receipts` workflow seed.** Added to `TIER_1_WORKFLOWS` with `trigger_type="time_of_day"` + `trigger_config.time="23:30"` (daily slot between ar_aging_monitor@11:00pm and ap_upcoming_payments@11:10pm). `agent_registry_key` is **NULL** on the seed entry (the "8b-beta" state per the migration template's badge choreography). Single step invokes the adapter via `call_service_method`. Existing workflow_scheduler 15-min sweep fires it — no changes to `backend/app/scheduler.py`.

**Operational coexistence contract (applies to 8c–8f too):**
- Triage queue (`/triage/cash_receipts_matching_triage`) = canonical path for routine daily processing.
- Legacy `POST /api/v1/agents/accounting` + `/agents/:id/review` = ad-hoc forensic re-runs only.
- Do not run both paths on the same unresolved-items set simultaneously.
- Legacy retirement deferred to Phase 8h+.

**Latency gates (BLOCKING):** `cash_receipts_triage_next_item` p50<100/p99<300 and `cash_receipts_triage_apply_action` p50<200/p99<500. Actual on dev: **p50=18.7ms/p99=20.1ms** (next_item, 5×/15× headroom) and **p50=15.7ms/p99=22.5ms** (apply_action, 13×/22× headroom).

**Tests shipped Phase 8b:** 9 parity + 2 latency + 18 unit + 5 Playwright = **34 new tests**. All green. Phase 1–8a regression unaffected.

**Latent bugs surfaced during 8b audit (flagged for separate sessions, NOT fixed in 8b):**
- `wf_sys_ar_collections` declares `trigger_type="scheduled"` but `workflow_scheduler.check_time_based_workflows()` dispatches only `time_of_day` and `time_after_event`. The workflow isn't actually firing on schedule today.
- Approval-gate email body is hardcoded HTML in `ApprovalGateService._build_review_email_html()` — predates D-7's delivery abstraction. Parity for cash receipts requires preserving verbatim.

### Pre-8c Cleanup (Workflow Arc Phase 8b.5)

Both Phase 8b audit-surfaced latent bugs fixed in a narrow cleanup session between 8b and 8c:

**Scheduler `scheduled` trigger dispatch.** `workflow_scheduler.check_time_based_workflows()` now dispatches `trigger_type="scheduled"` workflows alongside the existing `time_of_day` + `time_after_event`. Cron parsed via APScheduler's `CronTrigger.from_crontab(cron, timezone=tenant_tz)` — no new dep. Tenant TZ resolved via `Company.timezone` with `America/New_York` fallback (mirrors briefings precedent). Idempotency via new `_already_fired_scheduled` helper that queries `WorkflowRun.trigger_context.intended_fire` JSONB — audit-trail-based, self-healing across system restarts. Invalid cron logs + skips that workflow + continues. Eight Tier-1 `wf_sys_*` workflows now fire correctly per tenant-local cron: `ar_collections`, `statement_run`, `compliance_sync`, `training_expiry`, `safety_program_gen`, `document_review_reminder`, `auto_delivery`, `catalog_fetch`.

**Approval gate email migrated to D-7 managed template.** Migration `r37_approval_gate_email_template` seeds `email.approval_gate_review` into `document_templates`. Single template serves all 12 agent job types via `job_type_label` context variable. `ApprovalGateService.send_review_email()` now dispatches through `delivery_service.send_email_with_template` with `caller_module="approval_gate.send_review_email"` — audit-queryable via `document_deliveries.template_key='email.approval_gate_review'`. `_build_review_email_html()` deleted — no fallback to hardcoded HTML. Phase 8b cash receipts parity test unchanged (audit confirmed it asserts no email properties — pure refactor).

**Still-latent: `time_of_day` TZ bug.** Existing `time_of_day` dispatch fires at UTC wall-clock, not tenant-local. `wf_sys_cash_receipts` (23:30) and `wf_mfg_eod_delivery_reminder` are affected. Flagged in `WORKFLOW_MIGRATION_TEMPLATE.md` §7.5 for a follow-on session. 8c migrations needing tenant-local sub-daily timing should use `trigger_type="scheduled"` (correct) instead of `time_of_day` (UTC-only).

**Migration head:** `r37_approval_gate_email_template`. **Tests shipped:** 10 scheduler + 8 email migration = 18 new. Phase 8b cash receipts parity remains 9/9 green.

### Core Accounting Migrations Batch 1 (Workflow Arc Phase 8c)

Three agents migrated into real workflows using the Phase 8b reconnaissance template. Each exercises a meaningfully different shape — proving the template generalizes across Tier-1 accounting agents. **Primary deliverable: `WORKFLOW_MIGRATION_TEMPLATE.md` v2** with four new parity patterns + a queue-cardinality matrix + rollback-gap convention. 8c establishes all remaining patterns Phase 8f needs for the final batch.

**Migration 1: `month_end_close` — FULL approval with period lock + per-job cardinality.**
Adapter: `backend/app/services/workflows/month_end_close_adapter.py`. Three public functions (`run_close_pipeline`, `approve_close`, `reject_close`) delegate 100% to existing `MonthEndCloseAgent` + `ApprovalGateService._process_approve`/`_process_reject`. Triage cardinality: **per-job** (the whole AgentJob in awaiting_approval is the decision; anomalies are sub-context in the panel). Parity test positively asserts `PeriodLock` row creation + matches legacy `_process_approve` side effects. Pre-existing statement-run-failure rollback gap preserved verbatim for parity — flagged in template §11 for dedicated cleanup. Trigger: `manual`. Permission: `invoice.approve`.

**Migration 2: `ar_collections` — SIMPLE approval with per-customer fan-out + new email-dispatch capability.**
Adapter: `backend/app/services/workflows/ar_collections_adapter.py`. Four functions (`run_collections_pipeline`, `send_customer_email`, `skip_customer`, `request_review_customer`). **Closes pre-existing Phase 3b TODO** — legacy approval was a no-op; triage `send` action dispatches the email via the managed `email.collections` template. Triage cardinality: **per-customer** (one item per anomaly, which represents one customer with a drafted email). Fan-out fidelity parity test covers 3 customers × 3 different actions. Trigger: `scheduled` cron `0 23 * * *` (preserved from 8b.5 fix). Permission: `invoice.approve`. **Deploy-day note:** tenants whose ops workflow relied on the legacy no-op will see real email dispatches for the first time — discontinue manual compensation runs.

**Migration 3: `expense_categorization` — SIMPLE approval with per-line review + AI-suggestion-with-override.**
Adapter: `backend/app/services/workflows/expense_categorization_adapter.py`. Four functions (`run_categorization_pipeline`, `approve_line`, `reject_line`, `request_review_line`). `approve_line` accepts optional `category_override` kwarg — backend ships the capability; frontend UI deferred to Phase 8e triage design. **Trigger-type change (not a bug fix — explicit workaround):** seed changed from `trigger_type="event"` + `trigger_config.event="expense.created"` to `trigger_type="scheduled"` + `cron="*/15 * * * *"`. The event dispatch system doesn't exist today (no event subscription registry, no publish-event hooks). Latency is ~15 min vs. real-time. Flagged in latent-bug tracking for future event-infrastructure arc. Template §7.6 documents this convention for 8d+ migrations declaring event triggers. Permission: `invoice.approve`.

**New queue cardinality matrix** (template §10): **per-anomaly** (cash_receipts, expense_categorization) · **per-entity** (ar_collections: per-customer) · **per-job** (month_end_close) · **per-record** (future 8f: likely unbilled_orders). Chooses `id` in the direct-query shape + adapter's action signature + whether fan-out fidelity tests apply.

**New rollback-gap convention** (template §11): when a migration's approval path has partial-failure modes that don't cleanly roll back, document in (a) the parity test's module docstring, (b) template §15 latent-bug catalog, (c) CLAUDE.md latent-bug tracking. Preserve verbatim for parity; fix in dedicated cleanup session. Month-end close's statement-run-failure gap is the working example.

**Agent registry keys cleared** for all three migrated workflows in `default_workflows.py` (8b-beta state — the "Built-in implementation" badge disappears on the Platform workflows tab for these rows).

**Operational coexistence contract unchanged** — legacy `/agents` dashboard + `/agents/:id/review` approval page + `POST /agents/accounting` endpoint all still work for ad-hoc forensic re-runs. Triage is the canonical path for routine daily processing.

**Migration head:** `r37_approval_gate_email_template` (no new migrations in 8c — no schema changes). **Tests shipped Phase 8c:** 25 parity (8+8+9) + 6 BLOCKING latency gates + 20 unit + 9 Playwright scenarios = **60 new tests**. Phase 1–8b.5 regression: unchanged. Migration template v2 at project root.

**Remaining migrations (Phase 8f):** unbilled_orders, estimated_tax_prep, inventory_reconciliation, budget_vs_actual, 1099_prep, year_end_close, tax_package, annual_budget. Each follows the 9-question audit from template §1 + applies patterns from §5.5 / §10 / §11 as applicable.

### Vertical Workflow Migrations (Workflow Arc Phase 8d)

Two migrations (`wf_fh_aftercare_7day` + `wf_sys_catalog_fetch`) + a corrective r36 scope-backfill fix (r38) + a staging-state schema extension for urn_catalog_sync_logs (r39) + a seeded email template for the previously-phantom aftercare template (r40). Phase 8d also formally documents `wf_sys_safety_program_gen` as deferred to Phase 8d.1 and the engraved urn two-gate as intentionally service-only.

**r38 fix — r36 scope-backfill bug.** r36's CASE expression `WHEN tier = 1 THEN 'core'` ignored the `vertical` column, misclassifying 10 vertical-specific tier-1 workflows under `scope='core'` in the three-tab workflow builder. `r38_fix_vertical_scope_backfill` corrects them (all 10 listed verbatim in the migration file) via idempotent UPDATE. Regression gate `test_r38_scope_backfill_fix.py` enforces `tier=1 AND vertical IS NOT NULL IMPLIES scope='vertical'`. Phase 8a's `test_tier_1_workflows_are_core` was tightened to `test_tier_1_cross_vertical_workflows_are_core`.

**Aftercare migration (`wf_fh_aftercare_7day`) — triage-only.**
Pre-8d: 2-step workflow (send_email referencing phantom template + log_vault_item) → silent no-op because `template="aftercare_7day"` never existed in the D-2 registry. Post-8d: 1-step `call_service_method` → `aftercare.run_pipeline`. `backend/app/services/workflows/aftercare_adapter.py` stages one AgentAnomaly per eligible case (service_date + 7 days == today) via the same AgentJob + AgentAnomaly container pattern as Phase 8b/8c. Triage actions `send`/`skip`/`request_review`; approve renders managed `email.fh_aftercare_7day` template (r40) via `delivery_service.send_email_with_template` + logs a VaultItem. Per-case cardinality. Tier 3, vertical=funeral_home, trigger `time_after_event` 7 days at 10:00 local (unchanged).

**Catalog fetch migration (`wf_sys_catalog_fetch`) — triage-gated publish.**
Pre-8d: weekly cron auto-upserted every MD5-diffed Wilbert catalog to urn_products — no admin gate. Post-8d: cron fires `catalog_fetch.run_staged_fetch` which downloads + hashes + archives to R2 + creates a pending-review `UrnCatalogSyncLog`. Triage approve fetches R2 bytes, runs the **unchanged** legacy `WilbertIngestionService.ingest_from_pdf` (zero duplication), flips `publication_state='published'`. Reject flips to `rejected` with reason; no product writes. **Supersede semantics**: a newer fetch marks older pending-review rows as `superseded` so the queue never holds two competing catalogs. `r39_catalog_publication_state` adds the column + partial index on pending-review. Per-sync-log cardinality. Tier 1, vertical=manufacturing (corrected by r38), required_extension=urn_sales, trigger `scheduled` cron `0 3 * * 1` (weekly).

**NO AI question panels on 8d queues** — approved scope decision. Aftercare + catalog_fetch are audit/retry workspaces, not decision workspaces. The invariant is test-enforced; any future phase that wants to add an AI panel must explicitly lift it.

**Engraved urn two-gate — intentionally service-only.** The urn engraving workflow ([urn_engraving_service.py](backend/app/services/urn_engraving_service.py)) ships a token-based public FH approval URL (`/proof-approval/{token}`, 72-hour expiry, no auth) plus internal staff approval. Migrating to workflow_engine + triage would invert the customer-facing URL contract for no platform benefit. Phase 8d explicitly documents this as service-owned so future migration passes don't re-audit it.

**wf_sys_safety_program_gen deferred to Phase 8d.1.** First workflow-arc migration exercising AI-generation-with-approval-gating (Claude Sonnet → 7-section HTML → WeasyPrint PDF → admin approval → SafetyProgramGeneration row writes + month-ahead lookahead). The current adapter pattern hasn't been exercised against AI-generation flows yet. Earns its own reconnaissance session rather than batching into 8d.

**Migration head:** `r37_approval_gate_email_template` → `r38_fix_vertical_scope_backfill` → `r39_catalog_publication_state` → `r40_aftercare_email_template`. **Tests shipped Phase 8d:** 20 unit + 10 aftercare parity + 10 catalog_fetch parity + 4 BLOCKING latency + 3 r38 regression = **39 new**. Phase 8a/8b/8c regression: 140 passing, no regressions. **Latency on dev:** aftercare next_item p50=30.3ms + apply_action p50=22.1ms; catalog_fetch next_item p50=2.9ms + apply_action p50=5.5ms (all comfortably under the 100/200ms p50 targets).

### Safety Program Migration — AI-generation-with-approval reconnaissance (Workflow Arc Phase 8d.1)

Phase 8d.1 is the dedicated reconnaissance session for **AI-generation-with-approval shape**, deferred from Phase 8d because it has meaningfully different shape than any prior migration. Primary deliverable alongside the migration itself: `WORKFLOW_MIGRATION_TEMPLATE.md` v2.2 with three additions covering the new patterns.

**Per-run cardinality** (Template v2.2 §10, sixth variant). Distinct from per-job (AgentJob-backed) and per-staging-row (schema column ADDED by the migration) by the "pre-existing state machine" criterion: `SafetyProgramGeneration.status` was a 4-state enum (`draft / pending_review / approved / rejected`) added at feature-build time in `r15_safety_program_generation`. Phase 8d.1 is purely an alternate UX surface over the existing state — triage queue reads the domain table directly via `_dq_safety_program_triage`. No AgentJob wrapper, no AgentAnomaly, no new schema column. Adapter action functions take `generation_id` as their identifier. When to use: migration target's domain entity already has a review-status machine + bespoke review UI; migration adds an alternate canonical path rather than introducing a new review gate.

**AI-generation-content-invariant parity** (Template v2.2 §5.5.5). Non-deterministic AI generation forces the parity claim to shift. Instead of "legacy + triage paths produce identical PDF bytes" (unprovable), the claim is "given the same frozen pre-approval staging state, both paths produce byte-identical field writes on the domain entities." Test pattern: seed `SafetyProgramGeneration` directly with pre-populated `generated_content` + `generated_html` + `pdf_document_id=NULL` (the pre-existing FK-mismatch latent bug precludes Document seeding without tripping the constraint — see §15 entry #7). Run approval through both paths. Assert SafetyProgramGeneration + SafetyProgram writes match field-by-field. Never invoke Claude. Never assert on generated content bytes.

**Legacy APScheduler cron removal** (Template v2.2 §7.7). Pre-8d.1, the monthly safety-program generation fired via `job_safety_program_generation` APScheduler cron (`CronTrigger(day=1, hour=6, minute=0)`) — container-UTC, not tenant-local. Post-migration, the `wf_sys_safety_program_gen` workflow row (cron `0 6 1 * *`, `timezone="America/New_York"`) is the single-owner firing path via `workflow_scheduler`'s `scheduled` dispatch. APScheduler entry retired in 3 places: function definition, `JOB_REGISTRY` entry, `add_job` block — all replaced with explanatory comments. Unit test asserts `JOB_REGISTRY` no longer carries the retired key (catches future re-adds). Tenant-local 6am is an improvement: pre-8d.1, all tenants fired at the same UTC clock-tick regardless of their timezone setting.

**AI panel on AI-generated artifacts.** First migration-arc queue with AI-assisted review of AI-generated content. Prompt `triage.safety_program_context_question` (seeded via `scripts/seed_triage_phase8d1.py`, Option A idempotent) includes a **VERTICAL-APPROPRIATE TERMINOLOGY** block (precast concrete / burial vault hazards — silica dust from cutting cured concrete, rebar handling, vault pour demolding, chemical admixtures, forklift + vault maneuvering) and a **COMPLIANCE DISCIPLINE** block instructing Claude to cite the scrape snippet or say "would need to check the full standard at <scrape_url>" rather than invent OSHA citations. Related entities builder returns a 5-entity payload: generation metadata, target training topic (title + OSHA code + key_points), OSHA scrape preview (text_snippet + scrape_url), **prior SafetyProgram version** (for year-over-year diff — "what's changing from last year?"), and the generated PDF Document with a D-1 presigned URL for inline preview.

**Zero duplication.** `safety_program_adapter.approve_generation` / `reject_generation` delegate to `safety_program_generation_service.approve_generation` / `reject_generation` verbatim. The legacy service is unchanged. The adapter's only additions are: tenant-scope check (defense-in-depth) + dict-shaped return for workflow variable resolution.

**Legacy coexistence.** The bespoke `/safety/programs` UI remains fully operational. Triage covers the primary decision flow (approve/reject pending_review generations); bespoke covers everything else — AI Generated history view, Manual tab (non-AI programs), PDF regeneration for failed renders, ad-hoc topic generation via `/generate-for-topic/{topic_id}`. Legacy retirement deferred to Phase 8h or later.

**Migration head unchanged** (no new DB migration — per-run reuses the existing r15-created status column). **Tests shipped Phase 8d.1:** 13 BLOCKING parity (9 categories) + 2 BLOCKING latency + 16 unit + 6 Playwright = **37 new tests**. Full Phase 8a–8d regression: 171 passing, no regressions. **Latency on dev hardware:** next_item p50=5.7ms/p99=7.6ms; apply_action p50=10.0ms/p99=13.3ms.

### Spaces + Default Views (Workflow Arc Phase 8e)

Phase 8e expands the Phase 3 Spaces primitive with template coverage for previously-unmapped office roles, a deliberate-activation landing-route concept, onboarding touches, and the reapply-defaults escape hatch. **Drivers and other operational roles are explicitly excluded** — those roles get portal UX in Phase 8e.2, not platform Space templates. See `SPACES_ARCHITECTURE.md` for the full office-vs-operational distinction and Phase 8e.2 scope.

**6 new (vertical, role_slug) template combinations** in `backend/app/services/spaces/registry.py::SEED_TEMPLATES`:

| (vertical, role_slug) | Spaces (default first) | Default landing |
|---|---|---|
| cemetery / admin | Operations · Administrative · Ownership | /interments |
| cemetery / office | Administrative · Operational | /financials |
| crematory / admin | Operations · Administrative | /crematory/schedule |
| crematory / office | Operations · Administrative | /crematory/schedule |
| funeral_home / accountant | Books · Reports | /financials |
| manufacturing / accountant | Books · Reports · Compliance | /financials |

**2 enrichments to existing templates:** (a) `manufacturing / safety_trainer` promoted from FALLBACK to dedicated Compliance + Training spaces (`safety_program_triage` queue pinned in Compliance, safety training nav + OSHA 300 + toolbox talks in Training); (b) `manufacturing / production` Production space gained `safety_program_triage` pin alongside the existing `task_triage` — production managers see both pending safety program reviews (Phase 8d.1 output) and task-triage items at the top of their primary workspace.

**Deliberate-activation landing route.** New `SpaceConfig.default_home_route: str | None` field. When a user activates a space via a **deliberate** action (DotNav click, Switch-to-X command-bar result), the frontend navigates to the space's `default_home_route` via `useNavigate`. When activation is via **keyboard** (`⌘[`, `⌘]`, `⌘⇧1..7`), navigation is skipped — rapid Space cycling shouldn't fling the user between routes. `SpaceContext.switchSpace(spaceId, { source: "deliberate" | "keyboard" })` is the contract; default when omitted is `"keyboard"` (safer). All 14 shipped templates (including FALLBACK + Settings system space) now carry a `default_home_route`.

**Landing-route authoring UI.** `SpaceEditorDialog` gains a "Landing route" dropdown populated from: (1) `"Don't navigate"` (null), (2) every pin in the space with a resolvable `href` de-duped, (3) `/dashboard` as universal fallback, (4) existing custom value if not in the above three. Unavailable pins are excluded — you can't land somewhere you can't reach. The picker is deliberately narrow to nudge users toward coherent Space-to-route mappings.

**Saved-view seed dependency verification.** Every `saved_view` pin in a Space template must have a matching `SeedTemplate` in `saved_views/seed.py` for the **same vertical** (seed key format: `saved_view_seed:{role_slug}:{template_id}`). `test_spaces_phase8e.py::TestSavedViewSeedDependencies` cross-references at load time and fails loudly if a pin points at a seed key that doesn't resolve. 6 new saved-view seed combinations added alongside the new space templates: `(cemetery, "admin")` outstanding_invoices + recent_cases, `(cemetery, "office")` outstanding_invoices, `(crematory, "admin")` outstanding_invoices + recent_cases, `(crematory, "office")` outstanding_invoices, `(funeral_home, "accountant")` outstanding_invoices, `(manufacturing, "accountant")` outstanding_invoices.

**MAX_SPACES_PER_USER bumped 5 → 7** in `backend/app/services/spaces/types.py` and `frontend/src/types/spaces.ts`. Accommodates users who pick up the Settings system space (Phase 8a) plus multiple role-seeded spaces plus custom user-created spaces. DotNav horizontal layout tightened (`gap-1.5` → `gap-1`, added `overflow-x-auto`) so the 240px sidebar still fits 7 dots + plus gracefully. `Cmd+⇧1..5` bumped to `Cmd+⇧1..7` on the DotNav keyboard handler.

**Reapply-defaults endpoint** at `POST /api/v1/spaces/reapply-defaults`. Wraps existing `user_service.reapply_role_defaults_for_user()`. Returns `{saved_views, spaces, briefings}` counts. Idempotent via the underlying seed functions' per-role preferences arrays (briefings returns 1-on-success by contract, not a row count). Exposed because `ROLE_CHANGE_RESEED_ENABLED=False` (Phase 8a) — role changes no longer auto-reseed saved views; users who want fresh role defaults call this endpoint. Future Phase 8e.1 UI surface wires it into `/settings/spaces`.

**Two new onboarding touches** via the Phase 7 `useOnboardingTouch` infrastructure (no new table, server-persisted via `User.preferences.onboarding_touches_shown`): (1) `welcome_to_spaces` on DotNav when the user has ≥2 spaces — explains the spaces concept + keyboard shortcuts; (2) `pin_this_view` on any PinStar the user hasn't-yet-pinned — explains pinning into the active space. Both dismissed server-side cross-device.

**Phase 3 SpaceSwitcher component retired.** The top-nav `SpaceSwitcher.tsx` (Phase 3) was replaced by DotNav in Phase 8a with a one-release grace period; Phase 8e deletes the file. No remaining callers — Phase 8a already removed the mount from `app-layout.tsx`. The Phase 8a regression test `test_old_top_space_switcher_gone` stays valid (header should not contain `data-testid="space-switcher-trigger"`) since nothing mounts the component anywhere.

**DotNav ICON_MAP extended** with `bar-chart-3` (Reports), `shield-check` (Compliance), `graduation-cap` (Training) to render the icons referenced by new 8e templates. Unknown icons fall back to a colored accent dot.

**NAV_LABEL_TABLE additions** for every new nav_item pin target: `/interments`, `/plots`, `/deeds`, `/crematory/cases`, `/crematory/schedule`, `/crematory/custody`, `/reports`, `/financials/board`, `/compliance`, `/safety`, `/safety/training`, `/safety/osha-300`, `/safety/incidents`, `/safety/training/calendar`, `/safety/toolbox-talks`.

**Portal deferral documented.** `SPACES_ARCHITECTURE.md` at project root carves out the architectural distinction between **office roles** (platform UX with DotNav + command bar + customization) and **operational roles** (portal UX with single-purpose login + mobile-first chrome + tenant branding + no navigation away). Drivers (FH + MFG) are operational; Phase 8e.2 ships portal foundation with MFG driver as reconnaissance. `test_spaces_phase8e.py::TestNoDriverTemplates` enforces the invariant: `(funeral_home, "driver")` and `(manufacturing, "driver")` must NOT appear in SEED_TEMPLATES until Phase 8e.2 deliberately adds them as portal-shaped spaces. The "portal-as-space-with-modifiers" architectural insight — external portals (family/supplier/customer/partner) and internal operational-role portals (driver/yard operator) share the same primitive — a SpaceConfig with `access_mode: "portal_restricted"` + `tenant_branding` + `write_mode` modifiers — is the Phase 8e.2 thesis.

**Template coverage today after Phase 8e ships:** 13 (vertical, role_slug) combinations + 1 system space (Settings, admin-only) + 1 fallback (General). Up from 6 pre-Phase-8e.

**Tests shipped Phase 8e:** 31 new tests in `test_spaces_phase8e.py` across 7 test classes — TestPhase8eTemplates × 6 (parametrized coverage), TestPhase8eEnrichments × 2 (safety_program_triage pin on production, safety_trainer promotion), TestNoDriverTemplates × 3 (portal-deferral invariant: FH driver falls to fallback, MFG driver falls to fallback, no driver keys in SEED_TEMPLATES), TestSavedViewSeedDependencies × 3 (every saved_view pin resolves, cemetery/admin explicit seed, fh/accountant explicit seed), TestDefaultHomeRoute × 8 (create with/without route, update set/clear/preserve-on-unset, seeded template carries route, round-trip through JSON, legacy JSON without field round-trips as null), TestMaxSpacesBump × 2, TestReapplyDefaultsEndpoint × 3 (shape, idempotency, auth-required), TestNavLabelCoverage × 1, TestDefaultHomeRouteViaAPI × 3 (create, patch clears on null, patch omit preserves via model_fields_set). 2 pre-existing tests updated for Phase 8e contract: `test_spaces_api.py::test_space_cap_enforced_at_api` (bumped from 5 to MAX_SPACES_PER_USER=7), `test_space_pins_triage_queue.py` × 2 (Production space now has task_triage + safety_program_triage instead of just task_triage). **Full Phase 1–8e regression: 117 spaces tests passing**, no regressions across saved_views + briefings + command_bar neighbors.

**Migration head unchanged** at `r40_aftercare_email_template`. Phase 8e is pure JSONB + service-layer work; no schema change.

### Smart Spaces — topical affinity + customization UI (Workflow Arc Phase 8e.1)

Phase 8e.1 layers a behavior-inferred ranking signal on top of the Phase 8e spaces fabric. **Users don't configure "what this space is about" — the command bar learns from what they actually do.** Signal is implicit, computation is automatic, result is a command bar that responds to the user's workflow. See `SPACES_ARCHITECTURE.md` §9 for the full affinity model + purpose-limitation clause.

**Migration `r41_user_space_affinity`**: new table with composite PK on `(user_id, space_id, target_type, target_id)` — upsert semantics via `INSERT ... ON CONFLICT DO UPDATE`. CHECK constraint enumerates the four `target_type` values (`nav_item`, `saved_view`, `entity_record`, `triage_queue`). Two partial indexes: `ix_user_space_affinity_user_space_active (user_id, space_id) WHERE visit_count > 0` powers the read-path prefetch; `ix_user_space_affinity_user_recent_active (user_id, last_visited_at DESC) WHERE visit_count > 0` future-proofs for post-arc "top N by recency" consumers. Composite PK means no surrogate UUID; bounded storage ≤ `pins × spaces ≤ 7 × 20 = 140 rows` per user steady-state.

**`app/services/spaces/affinity.py`**: write + read + throttle + clear + count service. Key functions: `record_visit()` (PostgreSQL `ON CONFLICT DO UPDATE`, returns `recorded: bool`), `prefetch_for_user_space()` (one indexed query per `command_bar/query` call → dict keyed on `(target_type, target_id)`), `boost_factor()` (pure function: `1.0 + 0.4 * log10(visit+1)/log10(11) * max(0, 1 - age_days/30)` — saturates at visit_count=10, fully decays at age=30 days), `delete_affinity_for_space()` (cascade helper called by `crud.delete_space`), `clear_affinity_for_user()` (GDPR "clear my history"), `count_for_user()` (powers the "N tracked signals" counter). In-memory 60-second throttle bucket keyed on `(user_id, target_type, target_id)` — process-local, defense-in-depth over the client throttle.

**`POST /api/v1/spaces/affinity/visit`** — fire-and-forget write. Returns 200 with `{recorded: bool}` either way; 400 on invalid target_type (Pydantic catches); 404 on space_id that doesn't belong to caller (defense-in-depth — Space IDs are opaque UUIDs). **`GET /api/v1/spaces/affinity/count?space_id=...`** — `{count: int}` for the privacy counter. **`DELETE /api/v1/spaces/affinity?space_id=...`** — `{cleared: int}`. Privacy action, idempotent. **Route ordering is load-bearing**: all three `/affinity/*` routes declared BEFORE `/{space_id}` routes in `spaces.py` — otherwise FastAPI would match `DELETE /affinity` against `DELETE /{space_id}` with `space_id="affinity"` → 404. The `/{space_id}` routes are in a distinct later block with a comment marking the required order.

**Command bar retrieval integration** (`app/services/command_bar/retrieval.py`): three boost sources applied multiplicatively after the existing Phase 1 + Phase 3 scoring:

| Boost | Weight | Condition |
|---|---|---|
| Phase 3 active-space pin boost (existing) | 1.25× | Result matches a currently-pinned target |
| Phase 8e.1 starter-template boost (new) | 1.10× | Result matches a target in the role template that seeded the active space, EVEN IF unpinned. Skipped when pin boost already applied — pin wins. |
| Phase 8e.1 topical affinity boost (new) | 1.0×–1.40× | Per the boost_factor formula over `user_space_affinity` |

Max compound stack (pinned + affinity'd + today) = 1.25 × 1.40 = **1.75×**. Above the single-boost ceiling (1.5 create-intent) but bounded; acceptable because a heavily-used pinned target should outrank generic create actions. New retrieval helpers: `_active_space_starter_template_targets(user, active_space_id)` walks `SEED_TEMPLATES` keys matching the user's seeded role and returns target_ids from the template whose name matches the active space; `_affinity_factor_for_result(item, affinity, boost_for_target)` inspects `item.type` + `item.id` + `item.url` to resolve the (target_type, target_id) key and returns the boost factor.

**Affinity write wiring (4 surfaces)**: `PinnedSection` pin click fires `recordVisit({pinType, targetId})`; `PinStar` toggle ONLY on the pin-TO-pinned transition (unpinning is not intent); `CommandBar` activation branch fires on navigate when `active_space_id` is set — target_type inferred from action.type (VIEW → saved_view, RECORD → entity_record) + action.route (starts-with `/triage/` → triage_queue, else nav_item) with prefix-stripping on backend-shaped ids (`entity:<type>:<uuid>` → `<uuid>`, `saved_view:<uuid>` → `<uuid>`); new `AffinityVisitWatcher` component mounted at app root under `SpaceProvider` watches `useLocation().pathname` and fires on match against active-space pins (starts-with for nav_item; exact for saved_view + triage_queue).

**`useAffinityVisit` hook** (`frontend/src/hooks/useAffinityVisit.ts`): module-scoped `Map` for throttle buckets keyed on `{target_type}:{target_id}` with 60-second window (matches server). Fire-and-forget contract — `apiClient.post(...).catch(()=>{})`. Null-safe via `useActiveSpaceId` — no active space = no-op.

**`/settings/spaces` customization page** (`frontend/src/pages/settings/SpacesSettings.tsx`, ~900 LOC): full editor built strictly on Aesthetic Arc Session 3 primitives. Features: 2-column layout (sidebar + main editor), drag-reorder user spaces, full space identity + appearance + behavior editing, pin list with drag-reorder + per-pin "Move to…" popover for transferring between spaces, 16-icon narrow picker (Popover), 6-accent chip picker with hover-live-preview (temporarily sets `--space-accent` CSS var on mouseEnter), landing-route dropdown sourced from pins + /dashboard + preserved custom, reapply-defaults action (confirmation-before-commit modal with explicit "this won't change customizations" copy per user spec), type-to-confirm `Reset spaces` destructive modal, template picker dialog, affinity counter card ("N tracked signals") with "Clear learning history" action, `welcome_to_settings_spaces` onboarding touch. Registered at `/settings/spaces`.

**Dialog deep-links**: `NewSpaceDialog` gains "More options…" footer link to `/settings/spaces?new=1`; `SpaceEditorDialog` gains "Manage all pins, move items between spaces, import templates…" link to `/settings/spaces#pins-<space_id>`. Both dialogs remain the DotNav quick-path; `/settings/spaces` is the power surface.

**Purpose-limitation clause (Architecture)**: affinity data is used ONLY for command bar ranking. Any future use (briefings recommendations, dashboard personalization, saved-view recommendations) requires a separate scope-expansion audit. Documented in `SPACES_ARCHITECTURE.md` §9.4. Load-bearing for user trust — do not extend silently.

**Performance**: command bar baseline pre-8e.1 p50 = 7.9 ms / p99 = 10.3 ms; **post-8e.1 p50 = 8.2 ms / p99 = 77.3 ms** (dev hardware). Against the 100 / 300 ms BLOCKING budget: 12× / 3.9× headroom. **`test_command_bar_latency.py` extended** to seed 10 affinity rows + an active space for the test tenant so every sampled query exercises the prefetch + boost pipeline. BLOCKING gate preserved.

**Tests shipped Phase 8e.1**: 33 new in `test_spaces_phase8e1_affinity.py` across 10 test classes (schema × 3 — composite PK, CHECK, partial indexes exist; formula × 6 — zero/one/ten/saturation/decay-half/decay-full; record_visit × 3; prefetch × 3; cross-user + cross-tenant isolation × 2; cascade × 2; clear × 2; API × 7 — visit/throttle/bad-target/unknown-space/auth/count/clear; pin-boost regression × 1; starter-template × 3; composition × 1). Plus 1 extended latency gate = **34 new tests**. Full Phase 1–8e.1 spaces regression: **151 tests passing**, no regressions.

**Arc sequencing after 8e.1**: 8e.2 (portal foundation, MFG driver reconnaissance) → Aesthetic Sessions 4-5 → 8f (remaining accounting migrations) → 8g (dashboard) → Aesthetic 6 QA → latent bug cleanup → 8h arc finale.

**Migration head advances**: `r40_aftercare_email_template` → **`r41_user_space_affinity`**.

### Portal Foundation — MFG driver reconnaissance (Workflow Arc Phase 8e.2)

Phase 8e.2 ships the portal-as-space-with-modifiers infrastructure with **MFG driver as the first concrete portal application**. Validates the architecture the Phase 8e spaces fabric left room for: operational-role users get portal UX (identity-separated, tenant-branded, single-purpose) while office users stay on platform UX. Future portals (family/supplier/customer/partner, other operational roles) inherit the validated infrastructure. See `SPACES_ARCHITECTURE.md` §10 for the full architecture reference.

**Migration `r42_portal_users` + `r43_portal_password_email_template`**: new `portal_users` table with separate identity store (NOT a discriminator on users — identity-level separation prevents cross-realm privilege bleed), partial unique indexes on invite/recovery tokens; `drivers.portal_user_id` optional parallel FK (non-destructive — existing `employee_id` tenant-user drivers unchanged); `audit_logs.actor_type` discriminator with `'tenant_user'` default (backward-compatible); r43 seeds `email.portal_password_recovery` managed template via D-7. Migration head: `r41_user_space_affinity` → `r42_portal_users` → `r43_portal_password_email_template`.

**`PortalUser` model** at `app/models/portal_user.py`: `hashed_password` nullable (invite-only users), `assigned_space_id` matches SpaceConfig.space_id (no FK — spaces live in JSONB), `failed_login_count` + `locked_until` for lockout, distinct `invite_token` + `recovery_token` fields. Driver business-logic invariant (NOT DB CHECK): exactly one of `drivers.employee_id` OR `drivers.portal_user_id` populated per row. CHECK omitted deliberately to permit migration windows.

**SpaceConfig modifier fields** in `app/services/spaces/types.py`: `access_mode: "platform" | "portal_partner" | "portal_external"`, `tenant_branding: bool`, `write_mode: "full" | "limited" | "read_only"`, `session_timeout_minutes: int | None`. JSONB-only — no schema migration. Legacy spaces default to `platform / false / full / null` via `from_dict` (non-destructive). MFG driver template added at `("manufacturing", "driver")` in `SEED_TEMPLATES` with `access_mode="portal_partner"`, `tenant_branding=True`, `write_mode="limited"`, `session_timeout_minutes=720` (12h driver shift).

**JWT realm extension**: third realm `"portal"` alongside existing `"tenant"` + `"platform"`. Portal access token carries scope claims (`sub`, `realm="portal"`, `company_id`, `space_id`). Load-bearing security boundary enforced by **4 cross-realm-isolation tests**: portal→tenant reject, tenant→portal reject, cross-tenant portal reject, deactivated portal user reject. `get_current_portal_user` dependency validates realm + loads PortalUser; `get_portal_company_from_slug` resolves tenant from URL path (not header); tenant's `get_current_user` tightened to also reject portal realm.

**Portal services** at `app/services/portal/`: `auth.py` (login + lockout + rate limit + password recovery), `branding.py` (read + set branding via `Company.settings_json.portal.*`), `user_service.py` (invite portal user + resolve driver for portal user). `authenticate_portal_user` generic error messages don't leak email existence. In-memory IP+email rate bucket 10 attempts/30min per worker. Account lockout 10 fails → 30min `locked_until`. 1-hour single-use recovery tokens.

**Portal API routes** at `app/api/routes/portal.py` mounted at `/api/v1/portal/*`:
- Public: `GET /{slug}/branding`, `POST /{slug}/login`, `POST /{slug}/refresh`, `POST /{slug}/password/recover/{request,confirm}`
- Portal-authed: `GET /me`, `GET /drivers/me/summary` (thin router over existing delivery services)

**Path-scoped routing**: portal URLs are `/portal/<tenant-slug>/...` (not subdomain). Path-scoped works in dev + prod with zero infra changes. Subdomain routing deferred to post-September.

**Thin-router-over-service canonical pattern**: portal endpoint → `get_current_portal_user` → `resolve_driver_for_portal_user(portal_user)` → existing service layer with Driver as actor. Zero business logic duplication. Future portals (family/supplier/customer) inherit this shape. Documented in `SPACES_ARCHITECTURE.md` §10.7.

**Tenant branding "wash, not reskin"** discipline (§10.6): brand color applies ONLY to portal header bg + primary CTA + focus ring. Does NOT apply to status colors, typography, surface tokens, border radius, motion, shadow system — those stay DESIGN_LANGUAGE tokens. `PortalBrandProvider` sets `--portal-brand` + `--portal-brand-fg` CSS vars + `data-portal-brand` root attribute; luminance-based foreground picker keeps text contrast WCAG AA.

**Frontend portal layer** (entirely separate from tenant AppLayout):
- `types/portal.ts` (PortalBranding, PortalMe, PortalTokenPair, PortalDriverSummary)
- `services/portal-service.ts` (own axios instance — NOT shared apiClient; separate LocalStorage keys `portal_access_token`/`portal_refresh_token`/`portal_space_id`)
- `contexts/portal-auth-context.tsx` (PortalAuthProvider + usePortalAuth hook; isReady gating to prevent flash-of-unauthenticated)
- `contexts/portal-brand-context.tsx` (PortalBrandProvider; fetches + applies brand CSS vars; luminance-computed foreground)
- `components/portal/PortalLayout.tsx` (h-12 branded header + main + optional footer; logout action)
- `components/portal/PortalRouteGuard.tsx` (redirect to `/portal/<slug>/login` on missing auth)
- `pages/portal/PortalLogin.tsx` (branded login form, generic error message)
- `pages/portal/PortalDriverHome.tsx` (driver summary card with today's stop count + unlinked-account graceful path)
- `PortalApp.tsx` (top-level route tree mounted when `location.pathname.startsWith("/portal/")`)

**Phase 8e invariant test renamed + evolved**: `TestNoDriverTemplates` → `TestDriverTemplatesUsePortalAccessMode`. New symmetric invariant: operational-role slugs (driver, yard_operator, removal_staff) MUST use `access_mode` starting with `portal_` if a template exists; office-role slugs MUST use `platform`. No accidental drift in either direction. `test_spaces_phase8e.py` enforces.

**Non-destructive driver migration**: Sunnycrest's existing tenant-user drivers (employee_id → users.id, portal_user_id null) continue working unchanged. Tenants opt in per-driver when ready. Validated by `test_portal_phase8e2.py::TestNonDestructiveDriverMigration`.

**Phase 8e.2 explicitly defers to 8e.2.1**: tenant admin UI for portal user management (`/settings/portal-users`), branding editor UI, remaining 4 driver pages mounted under portal routes (route, stop detail, mileage, vehicle inspection), offline-tolerance touches, full mobile polish pass, reset-password page.

**Tests shipped Phase 8e.2**: 25 new in `test_portal_phase8e2.py` across 9 test classes (schema × 4, auth service × 4, password recovery × 2, cross-realm isolation × 4 LOAD-BEARING, branding × 2, login endpoint × 3, SpaceConfig modifiers × 2, MFG driver template × 1, driver data mirror × 2, non-destructive migration × 1) + 3 Playwright smoke tests (branded login, driver home post-login, no DotNav/cmdbar/settings). Full Phase 1–8e.2 regression: **379 backend tests passing, no regressions**. Frontend vitest 165/165, tsc 0 errors, build clean 6.36s.

**Arc sequencing after 8e.2**: 8e.2.1 (portal admin UI + branding editor + driver pages polish) → Aesthetic Sessions 4-5 (dark mode + motion) → 8f (remaining accounting migrations) → 8g (dashboard) → Aesthetic 6 QA → latent bug cleanup → 8h arc finale. **8e.2 ships before September Wilbert demo** — demo includes the portal-side delivery driver narrative alongside the platform-side office work.

### Portal substrate access modes (R-6.2b)

Portal substrate has **two canonical access modes**. Each has its own layout primitive.

**Mode 1 — Magic-link-authenticated portal users.** Identity = `PortalUser` (Phase 8e.2 `r42_portal_users` separate identity store). Surface = `PortalLayout` (h-12 branded header + Sign Out + body + footer). Requires `PortalAuthProvider` mounted above. Used by: driver portal (Phase 8e.2.1 driver console at `/portal/:slug/driver/*`), future family/supplier/customer portal instances. JWT realm = `"portal"`.

**Mode 2 — Fully anonymous public surfaces.** No identity. No JWT. Surface = `PublicPortalLayout` (h-12 branded header, NO Sign Out, body, footer, "Powered by Bridgeable" attribution). Does NOT require `PortalAuthProvider`; requires only `PortalBrandProvider` for tenant chrome. Used by: R-6.2b intake forms at `/portal/:tenantSlug/intake/:slug`, R-6.2b file uploads at `/portal/:tenantSlug/upload/:slug`, R-6.2b confirmation pages, Phase 1E family-approval at `/portal/:tenantSlug/personalization-studio/family-approval/:token` (token-as-auth; precedent). CAPTCHA gates write endpoints to prevent spam.

**Mount discipline at `PortalApp.tsx`**: Mode 1 routes mount inside `PortalShell` which wraps in `PortalBrandProvider` + `PortalAuthProvider`. Mode 2 routes mount at PortalApp top level OUTSIDE `PortalShell` — each page wraps itself in `PortalBrandProvider` only. This avoids the parent shell's auth provider entirely. FamilyPortalApprovalView is the precedent (Phase 1E); R-6.2b intake pages follow the same pattern.

**Wash-not-reskin discipline preserved across both modes** per `SPACES_ARCHITECTURE.md §10.6`: brand color affects portal header background + foreground only. Status colors, typography, surface tokens, border radius, motion, shadows all stay DESIGN_LANGUAGE regardless of mode.

**Adding a new anonymous public portal surface** (future FH website embed widgets, vendor registration forms, public inquiry forms): wrap in `<PortalBrandProvider slug={tenantSlug}><PublicPortalLayout>...</PublicPortalLayout></PortalBrandProvider>`, register the route at PortalApp top level (parallel to existing `/intake/:slug` + `/upload/:slug` routes), gate write endpoints with CAPTCHA via `verify_turnstile_token` per R-6.2b backend pattern.

### Design System (Aesthetic Arc Phase I complete, Phase II in progress)

`DESIGN_LANGUAGE.md` at project root is the canonical source of truth for Bridgeable's visual and sensory design language — Mediterranean garden morning (light mode), cocktail lounge evening (dark mode), deepened terracotta `#9C5640` as cross-mode architectural-color thread (single value across both modes per the architectural-color rule; Aesthetic Arc Session 2 retired the prior aged-brass thread). Every token value in the platform derives from DESIGN_LANGUAGE.md Section 3 (color), Section 4 (typography), Section 5 (spacing), Section 6 (surface + behavior). See `AESTHETIC_ARC.md` for the arc plan (Phase I 4 sessions complete, Phase II in progress with Batch 0 shipped, Phase III = Motion + QA pending).

**Tokens.css is a mirror.** `DESIGN_LANGUAGE.md §3` (+ §9 CSS block) and `frontend/src/styles/tokens.css` must stay synchronized. A change to either requires a same-commit update to the other. Documentation drift between the canonical reference and the implementation is a defect. When adjusting a token value, update both files and note the change in the CLAUDE.md Recent Changes entry + the session log.

**Reference images win over prose — for diagnosis, not just authority.** When canonical reference images exist in `docs/design-references/`, sample them directly via PIL (`from PIL import Image; Image.open(path).convert('RGB')`) before inferring tuning values from prose anchors. This discipline is canonicalized after Tier 4 (April 2026) — three consecutive sessions of inferring-from-anchors produced three misses ("strengthen highlight" / "add perimeter border" / "bump lightness"), while one session of direct pixel sampling produced an immediate correct calibration. The measurement workflow: `from PIL import Image`, scan with `getpixel()` at strategic coordinates (page, card body, edge transitions, top-edge band, bottom shadow halo), convert sRGB → OKLCH using the Ottosson 2020 formulas, compare to current tokens. If values disagree, update both the tokens and the prose they derived from — `DESIGN_LANGUAGE.md §1 canonical-mood-references` explicitly says images win when prose is ambiguous, and this applies to diagnosis (what does the reference actually demonstrate) as well as authority (what should the spec say). `docs/design-references/README.md` enumerates current canonical references and their purpose.

**Shadcn default tokens are aliased to DESIGN_LANGUAGE tokens** (Phase II Batch 0, April 2026; updated Aesthetic Arc Session 2). The `:root` and `.dark` blocks in `frontend/src/index.css` alias every shadcn semantic token (`--background`, `--foreground`, `--card`, `--card-foreground`, `--popover`, `--popover-foreground`, `--primary`, `--primary-foreground`, `--secondary`, `--secondary-foreground`, `--muted`, `--muted-foreground`, `--accent-foreground`, `--destructive`, `--border`, `--input`, `--sidebar*`) to DL equivalents via `var(...)` references. **`--accent` itself is the DL strong terracotta token (no shadcn alias)** — Aesthetic Arc Session 2 dropped the shadcn-style `--accent: var(--accent-subtle)` alias because the variable name collides with DL's primary accent token; shadcn primitive consumers using `bg-accent` for menu hover backgrounds were migrated to `bg-accent-subtle` in the same session. Pages using shadcn defaults (`bg-muted`, `bg-card`, `text-muted-foreground`, `text-primary`, etc.) render in the DESIGN_LANGUAGE warm palette automatically in both modes — no component code changes required. **New work should prefer DESIGN_LANGUAGE tokens directly** (`bg-surface-sunken` over `bg-muted`, `text-content-muted` over `text-muted-foreground`, `bg-accent` over `bg-primary`) for clarity. Shadcn defaults remain safe to use in legacy/third-party components during the coexistence window. Preserved as-is (not aliased): `--radius` (underpins shadcn radius scale), `--chart-*` (no DL chart palette yet), `--brand-*` (legacy custom teal tokens), `--status-*-{light,dark}` (coexistence window), `--ring` (WCAG 2.4.7 concern — kept as neutral dark gray since accent at 40% alpha doesn't reliably clear 3:1 on every surface; `.focus-ring-accent` utility remains the opt-in accent focus ring).

**Comment-code discipline for conditional renders.** Tests that seed state should also test unseeded state. Components with conditional rendering based on data presence need coverage for each branch. DotNav's `spaces.length === 0 → return null` early-return survived 14 months (Phase 8a → Nav Bar Completion) because the populated-spaces path was the only one tested, and the inline comment "render just the plus button so new tenants can still create one" described intent that the code never implemented. When adding a branching render, add a test for each branch — especially the empty / loading / error path that your happy-path fixture skips over.

**Severity attribution methodology for aesthetic audits.** Grep-only audits under-estimate user-visible impact. Pattern counts don't weight by UI prominence or compositional failure mode — a page with 12 Tailwind hits concentrated in the title and widget-wrapper fails harder user-visibly than a page with 50 hits distributed through deep nested states. Infrastructure components (WidgetWrapper, PortalLayout, AppLayout, shared banner components, etc.) have disproportionate severity because a single file's bypass pattern replicates across every consumer. Future audits should (a) attempt dev-environment visual verification in parallel with grep counts, OR (b) defer severity assessment to user post-batch visual verification. Phase II Audit v1 under-scoped Batch 1 by 7 blocking files because visual verification was deferred until Batch 0 ship — the v2 re-audit corrected scope after user visual verification surfaced Operations Board + Agents + order-station + financials-board + team-dashboard as blocking rather than P1/P2. The corrective loop (audit → Batch 0 ship → user visual check → re-audit) worked; the lesson is to run the visual check EARLIER if possible.

**Token surface (`frontend/src/styles/`):**
- `tokens.css` — all DESIGN_LANGUAGE Section 9 tokens as CSS custom properties at `:root` (light mode defaults) + `[data-mode="dark"]` (dark overrides). Token families: `--surface-{base,elevated,raised,sunken}`, `--content-{strong,base,muted,subtle,on-accent}`, `--border-{subtle,base,strong,accent}`, `--shadow-color-*` + `--shadow-level-{1,2,3}`, `--accent{,-hover,-muted,-subtle}` (single value across modes per Aesthetic Arc Session 2 — no `--accent-active`; selected-item state uses `--accent-subtle` + `--accent` border), `--status-{error,warning,success,info}{,-muted}`, `--font-plex-{sans,serif,mono}`, `--text-{display-lg,display,h1..h4,body,body-sm,caption,micro}`, `--radius-{base,full}` (supplements legacy shadcn `--radius-*`), `--duration-{instant,quick,settle,arrive,considered}`, `--ease-{settle,gentle}`, `--max-w-{reading,form,content,wide,dashboard}`.
- `fonts.css` — self-hosted via `@fontsource-variable/ibm-plex-sans` (variable 100-700) + `@fontsource/ibm-plex-serif/500.css` + `@fontsource/ibm-plex-mono/400.css`. No Google Fonts CDN.
- `base.css` — reduced-motion collapse (`prefers-reduced-motion: reduce`), dark-mode font smoothing, accent focus-visible utility class `.focus-ring-accent` (renamed from `.focus-ring-brass` in Aesthetic Arc Session 2), explicit `@utility duration-{instant,quick,settle,arrive,considered}` declarations (Tailwind v4 doesn't auto-generate `duration-*` utilities from `--duration-*` namespace).
- `globals.css` — entry point imported by `frontend/src/index.css`.

**Tailwind v4 via `@theme inline`:** DESIGN_LANGUAGE Section 9 shows tokens as a Tailwind v3-style `tailwind.config.js`; the actual implementation uses Tailwind v4's `@theme inline { ... }` block inside `frontend/src/index.css`. Each Section 9 config entry translates to an `@theme` line (`--color-surface-base: var(--surface-base)`, `--font-plex-sans: var(...)`, etc.). DESIGN_LANGUAGE.md Section 9 carries a v4-clarification note pointing at `frontend/src/index.css` as the live mapping.

**Mode switching:** initial mode set by a synchronous inline script in `frontend/index.html` head (reads `localStorage['bridgeable-mode']` + `prefers-color-scheme` fallback; sets `data-mode="dark"` on `<html>` before any CSS loads — prevents flash-of-wrong-mode). Runtime API at `frontend/src/lib/theme-mode.ts`: `getMode()`, `setMode(mode)`, `toggleMode()`, `clearMode()` (revert to system preference), and `useThemeMode()` React hook that subscribes to custom-event dispatches and system `prefers-color-scheme` changes. **No mode toggle UI yet** — that's Session 2's settings-refresh concern. Setting `document.documentElement.setAttribute("data-mode", "dark")` in devtools console toggles mode for manual verification.

**Session 1 shipped:** 4 new CSS files (`tokens.css`, `fonts.css`, `base.css`, `globals.css`), 1 new TS module (`theme-mode.ts`), `index.css` + `index.html` modifications. Status color values migrated from hex to oklch (accepted one-time drift). Infrastructure only; no visual change.

**Session 2 shipped:** 14 files refactored onto DESIGN_LANGUAGE tokens (~480 LOC touched). UI primitives — Button (6 variants, `bg-brass` primary, brass focus ring, `radius-base` 6px), Label (`text-body-sm font-medium text-content-base`), Input/Textarea (`bg-surface-raised` + `border-base` + `focus-visible:border-brass` + `ring-brass/30` per canonical §9 form), Select (10 sub-components with overlay-family popup composition), Card (`bg-surface-elevated` + `shadow-level-1` + footer sinks to `bg-surface-base`), Dialog (`bg-surface-raised` + `rounded-lg` + `shadow-level-2` + `duration-arrive ease-settle`), DropdownMenu (matches Select popup; destructive items `bg-status-error-muted`; shortcuts in `font-plex-mono`), SlideOver (`shadow-level-3` floating). Navigation — Sidebar (`bg-surface-sunken` shell; items `text-content-muted` → `bg-brass-subtle` hover → brass focus ring; Phase 3 Spaces per-space accent chrome preserved with alpha bumped 10→18 hex for legibility against quieter sunken background), DotNav, Breadcrumbs, Mobile tab bar (`min-h-11` WCAG 2.2 Target Size), app-layout top header, notification-dropdown Popover (unread indicator flips blue→brass for primary-accent continuity). **Single-line `--font-sans` flip** in `index.css` from `'Geist Variable'` → `var(--font-plex-sans)` cascades to every rendered text node platform-wide. Geist package removed from dependencies. Overlay family unified (Dialog/DropdownMenu/Select popup/SlideOver/notification Popover all share level-2/3 composition + `duration-settle/arrive` + `ease-settle/gentle`).

**Session 3 shipped:** 23 files touched (~1,200 LOC). **6 net-new primitives** (`ui/alert.tsx` / `ui/status-pill.tsx` / `ui/tooltip.tsx` / `ui/popover.tsx` / `ui/form-section.tsx` / `ui/form-steps.tsx`) + **11 primitive refreshes** (Badge with 4 new status variants + destructive-alias; Table / Tabs / Separator / Avatar / Switch / Radio / Skeleton / EmptyState / InlineError / Sonner) + **6 ad-hoc surface refreshes** (3 platform banners + peek StatusBadge + 2 ErrorBoundaries + agent-alerts-card). `next-themes` package REMOVED — confirmed single-consumer; `theme="system"` hardcoded; Sonner `richColors` enabled for auto-tinted status toasts. **0 UI primitives remain in shadcn aesthetic** (target achieved). ~213 pages still carry shadcn page-chrome (accepted; migration recipe documented below). 5 settings pages deferred to Phase 8e. 1,305 ad-hoc status-color usages + 266 native `title=` tooltips deferred to natural-refactor. Tests: tsc clean, 165/165 vitest, 171/171 backend regression, build clean.

**Session 4 shipped:** Dark mode verification pass. No new components; no net-new aesthetic work. Surgical token adjustments + 3 targeted component fixes for Session 1-3 misses + 1 tenant-facing branding-preview feature. **Token adjustments (2 families):** (1) M1 — dark-mode `status-*-muted` backgrounds tightened from L 0.28/0.30 → 0.22/0.24 (chroma eased proportionally 0.08→0.07/0.07→0.06/0.06→0.05/0.05→0.04). Clears WCAG AA 4.5:1 for status-text-on-muted-bg (was 3.83–4.32:1, now 5.0–5.4:1). Affects Alert, StatusPill, InlineError, Badge status variants, agent-alerts-card — every status-rendering surface inherits the fix via semantic token cascade with zero component code changes. (2) m2 — new `--focus-ring-alpha` composable token (light 0.40 default, dark 0.48 override) lifts brass focus ring contrast on `--surface-raised` from ~3.00:1 (WCAG 2.4.7 edge) to ~3.5:1. `.focus-ring-brass` utility in `base.css` now composes via `color-mix(in oklch, var(--accent-brass) calc(var(--focus-ring-alpha) * 100%), transparent)` with a 0.40 fallback. **Component fixes:** M2 — portal fg fallback (`PortalLayout`, `PortalLogin`, `PortalResetPassword`): 6 substitutions of `var(--portal-brand-fg, white)` → `var(--portal-brand-fg, var(--content-on-brass))`. Fallback is now mode-aware; in dark mode + no tenant brand, brass-backed text renders as dark charcoal per DL §3 "brass button reads as 'glowing pill with dark text.'" M5 — `NotificationDropdown` status icons migrated from 4 hardcoded Tailwind colors (`text-green-500`/`text-yellow-500`/`text-red-500`/`text-blue-500`) to the DESIGN_LANGUAGE warm status palette (`text-status-{success,warning,error,info}`). Session 3 miss — now consistent with Alert, StatusPill, InlineError, Sonner. m3 — `PortalLayout` logout button focus ring migrated from `focus:ring-white/50` to `focus-visible:ring-[color:var(--portal-brand-fg,var(--content-on-brass))]/50` — mode-aware + scoped to the brand-colored header. **New feature — M3 branding-editor preview:** `/settings/portal-branding` gains a Light/Dark toggle above the preview panel (scoped `data-mode="dark"` on the preview subtree only — doesn't affect the rest of the admin page) + a WCAG contrast readout showing (a) brand → header-text contrast with pass/fail against 4.5:1 AA body-text, (b) brand-against-page-surface contrast with visible/low-contrast advisory. Proper WCAG sRGB gamma luminance computed in-component (`_wcagContrast` + `_wcagLuminance`). **Deferred:** m1 — `focus-ring-brass` utility gap-ring color uses `--surface-base` per DL §6 spec; on elevated surfaces in dark mode this reads as a subtle darker-than-parent cut. Spec-vs-pragmatism call, deferred to Session 6. m4 — `OfflineBanner` hardcoded `bg-amber-500 text-amber-950`; low priority (transient, amber is close to warning hue in both modes), deferred to natural refactor. The ~20 pre-Session-3 pages (vault-mold-settings, tax-settings, etc.) remain on the long-tail natural-refactor list. **Tenant brand color approach confirmed Option A** (identical hex in both modes, tenant responsibility) + M3 preview helper as the verification tool. **Mirror discipline canonicalized:** tokens.css + DESIGN_LANGUAGE.md §3 must stay synchronized in the same commit (see "Tokens.css is a mirror" above). **Luminance formula discrepancy noted as known minor item:** `PortalBrandProvider.applyBrandColor` uses BT.601 luminance (`0.299R + 0.587G + 0.114B`); the branding-editor preview uses proper WCAG sRGB-gamma luminance; the two diverge <5% for most colors. Aligning PortalBrandProvider is deferred — see `SPACES_ARCHITECTURE.md §10.6`. **LOC:** ~90 changed (~30 tokens/base.css + ~15 portal fg fallback substitutions + ~4 notification-dropdown + ~10 PortalLayout logout + ~130 branding-editor preview). **No new tests.** tsc clean, vitest 165/165 unchanged (no component behavior changes), build clean. **Ready for Session 5 (motion pass).**

**Status-color vocabulary (Session 3):**
- **Status families**: `success` / `warning` / `error` / `info` (+ `neutral` for unmapped). Each family has full-saturation `--status-{X}` and muted-background `--status-{X}-muted` tokens.
- **Status-family recipe**: `bg-status-{X}-muted` background + `text-status-{X}` text + optional `border-status-{X}` border. Used consistently across Badge status variants, Alert, StatusPill, Sonner richColors, InlineError, peek StatusBadge, agent-alerts, ErrorBoundary.
- **StatusPill vs. Badge distinction**: **StatusPill** (`ui/status-pill.tsx`) = `rounded-full` pill for inline status markers in lists/tables/detail panels. Takes a `status` string (auto-maps via `STATUS_MAP` — 33 keys covering the platform's status vocabulary: approved/pending/rejected/completed/failed/voided/active/inactive/paid/overdue/etc). **Badge status variants** (`ui/badge.tsx`) = `rounded-sm` pill for general-purpose emphasis with flexible semantics (counts, labels, arbitrary tags, explicit-variant use cases). Different shape, different use case. Documented in each file's header comment.
- **Alert vs. InlineError distinction**: **Alert** (`ui/alert.tsx`) = page/section-level banner with 5 variants (info/success/warning/error/neutral) + optional title/description/action/dismiss. **InlineError** (`ui/inline-error.tsx`) = panel-scoped recoverable-error UX with narrow shape + `onRetry` callback contract. Different use cases; kept coexisting. Documented in each file's header.

**Status-key-keyed dict pattern (Session 3 convention):** when a component renders per-state chrome via a config object (agent-alerts-card's severity mapping, peek status renderers, future status-rendering pages), declare a `StatusFamily` key per state + share a `FAMILY_STYLES` lookup mapping family → token triple. **Don't embed raw color strings in component code.** Adding a new severity/state = one row in the config; zero raw colors.

Reference implementation: `components/agent-alerts-card.tsx`. Pre-Session-3 the file had:
```ts
const SEVERITY_CONFIG = {
  action_required: { icon: AlertTriangle, color: "text-red-600", bg: "bg-red-50", border: "border-red-200" },
  warning:         { icon: Bell, color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-200" },
}
```
Post-Session-3:
```ts
const SEVERITY_CONFIG: Record<string, { icon: LucideIcon; status: StatusFamily }> = {
  action_required: { icon: AlertTriangle, status: "error" },
  warning:         { icon: Bell,          status: "warning" },
}
const FAMILY_STYLES: Record<StatusFamily, { bg: string; fg: string; border: string }> = {
  error:   { bg: "bg-status-error-muted",   fg: "text-status-error",   border: "border-status-error/30" },
  warning: { bg: "bg-status-warning-muted", fg: "text-status-warning", border: "border-status-warning/30" },
  // ...
}
```

**Status-color migration recipe (for long-tail adoption as pages are next touched):**

| Legacy pattern | DESIGN_LANGUAGE replacement |
|---|---|
| `bg-green-50 text-green-800` | `bg-status-success-muted text-status-success` |
| `bg-red-50 text-red-800` | `bg-status-error-muted text-status-error` |
| `bg-amber-50 text-amber-800` or `bg-yellow-*` | `bg-status-warning-muted text-status-warning` |
| `bg-blue-50 text-blue-800` or `bg-sky-*` | `bg-status-info-muted text-status-info` |
| `bg-{green,red,amber,blue}-100` | respective `bg-status-*-muted` |
| `border-{green,red,amber,blue}-200` | `border-status-*` (optional `/30` opacity) |
| `text-emerald-*` / `text-rose-*` / `text-sky-*` | `text-status-success / -error / -info` |

The recipe applies to pages (not component library code). Don't proactively refactor untouched pages — pages migrate as they're next touched for unrelated reasons. Session 6 QA verifies no net-new legacy patterns introduced.

**Coexistence with existing shadcn tokens:** shadcn CSS variables remain untouched (`--background`, `--foreground`, `--card`, `--popover`, etc.). All UI primitives migrated to DESIGN_LANGUAGE tokens in Sessions 2–3; final cleanup session retires the shadcn layer when no references remain. **Platform font = IBM Plex Sans post-Session 2**: `--font-sans` points at `var(--font-plex-sans)`. `@custom-variant dark` matches both legacy `.dark` class (noop) and `[data-mode="dark"]` attribute.

### Intake Adapter Contract (R-6.2a)

Canonical adapter contract — every inbound intake source (email, form, file, and future channels) implements the same shape:

```
adapter.ingest(db, *, tenant_config, source_payload) → canonical_record
```

- **Input**: raw source-specific payload as a typed dataclass (`ProviderFetchedMessage` for email, `FormSubmissionPayload` for form, `FileUploadPayload` for file).
- **Output**: canonical row persisted in the adapter's record table (`email_messages`, `intake_form_submissions`, `intake_file_uploads`).
- **Guarantees**: idempotency via natural key; tenant isolation enforced from `tenant_config`; best-effort downstream classification cascade hook that never blocks ingest; failure surfaces in a replayable audit row.

**Adapter-specific configuration tables** (R-6.2a architectural call): per-adapter configuration tables rather than a unified god-table. Email uses `email_accounts` (provider OAuth + sync state); form uses `intake_form_configurations` (form_schema JSONB); file uses `intake_file_configurations` (allowed_content_types + size caps + r2_key_prefix_template). All three follow **three-scope inheritance at READ time** — `platform_default → vertical_default(vertical) → tenant_override` — with first match wins. Resolver at `app/services/intake/resolver.py` mirrors R-6.1's three-tier classification cascade + the visual editor's platform_themes resolver verbatim.

**Cascade is source-agnostic** (R-6.1 principle preserved). Form submissions + file uploads enter the same three-tier classification pipeline via parallel entry points `classify_and_fire_form` + `classify_and_fire_file` at `app/services/classification/dispatch.py`. Tier 1 rules gain an `adapter_type` discriminator on `tenant_workflow_email_rules` (CHECK enumerates `'email' | 'form' | 'file'`; defaults `'email'` for R-6.1 backward compat). Tier 2 + Tier 3 LLM prompts renamed from `email.classify_into_*` to `intake.classify_into_*` with an `adapter_type` template variable — same prompt handles all three sources. Behavioral equivalence verified via test gates; R-6.2a `seed_intake_intelligence_prompts.py` handles the rename via Option A idempotent state machine (matches Phase 6 / 8b / 8d.1 / R-6.1a canon).

**Per-row denormalized classification outcome.** Form + file adapter rows carry their own `classification_tier` + `classification_workflow_id` + `classification_workflow_run_id` + `classification_is_suppressed` + `classification_payload` columns. R-6.1's email-bound `workflow_email_classifications` table is deliberately NOT extended cross-source — cross-source audit unification deferred to R-6.x hygiene when concrete signal warrants. Each adapter's record table owns its own audit chain.

**Parameter binding extension.** `workflow_engine.resolve_variables` gains two new prefixes: `incoming_form_submission.<path>` resolves against `trigger_context.incoming_form_submission`; `incoming_file.<path>` resolves against `trigger_context.incoming_file`. Workflow steps reference form fields via `{incoming_form_submission.submitted_data.field_id}` and file metadata via `{incoming_file.presigned_url}`. Trigger context shapes are built by `_build_form_trigger_context` + `_build_file_trigger_context` in dispatch.py. Generation Focus templates already consuming `incoming_email.body_text` inherit the new sources without template changes.

**Public surfaces use path-based portal routing.** Form + file intake pages mount under the canonical Phase 8e.2 portal substrate at `/portal/:tenantSlug/intake/:formSlug` and `/portal/:tenantSlug/upload/:fileSlug`. No subdomain DNS per tenant; existing `PortalBrandProvider` + `PortalLayout` substrate consumed verbatim; CAPTCHA gates public POST endpoints (Cloudflare Turnstile stubbed in R-6.2a + wired in R-6.2b).

**API mount point.** Routes mounted at `/api/v1/intake-adapters/*` (NOT `/api/v1/intake/*` — that prefix is already owned by the existing `intake.py` router serving the disinterment intake form with a catch-all `/{token}` route that would shadow new adapter paths). Per CLAUDE.md §12 Spec-Override Discipline: investigation report canonical-named the surface as `/api/v1/intake/*`, but the actual codebase had a name collision that forced override. R-6.x can consolidate when the disinterment intake is migrated onto the adapter substrate.

**R2 storage substrate** for file uploads. `legacy_r2_client.generate_presigned_upload_url(r2_key, *, content_type, expires_in, max_size_bytes)` returns a presigned PUT URL with 15-minute TTL. Browser uploads bytes directly to R2 without proxying through Bridgeable. Completion endpoint optionally verifies the object exists via `legacy_r2_client.head_object(r2_key)` + re-validates size against the config's cap before persisting the IntakeFileUpload row. R2 dependency is operational — staging + production deployments require R2 ENV vars configured.

## 5. Database

- **~235 tables** (ORM models for all but the orphaned `tenant_settings` table)
- **118 migration files** in `backend/alembic/versions/`
- **Single root:** `e1e2120b6b65` (create_users_table)

### Running Migrations Locally
```bash
cd backend && source .venv/bin/activate
DATABASE_URL=postgresql://localhost:5432/bridgeable_dev alembic upgrade head
```

### Idempotent Migrations
`backend/alembic/env.py` monkey-patches `op.add_column`, `op.create_table`, and `op.create_index` to be idempotent. This allows the same migration chain to run on both fresh databases and databases where tables were created outside migrations.

### Table Name Conventions
These are the **correct** table names (corrected from old incorrect names):
- Customer payments: `customer_payments` (not `payments`)
- Sales orders: `sales_orders` (not `orders`)
- Vendor bills: `vendor_bills` (not `bills`)
- Customer payment applications: `customer_payment_applications`

### Key Schema Patterns
- All IDs are `String(36)` UUIDs generated with `uuid.uuid4()`
- Timestamps use `DateTime(timezone=True)` with `default=lambda: datetime.now(timezone.utc)`
- Soft deletes via `is_active` boolean (not physical deletion)
- JSONB used extensively for flexible fields (settings, config, metadata)
- `company_id` or `tenant_id` FK on all tenant-scoped tables
- **Vertical column convention (post-r95):** Going forward, any migration introducing a column referring to a vertical must reference `verticals.slug` as a foreign key. The existing pattern of String(32) nullable `vertical` columns on `platform_themes`, `focus_compositions`, `workflow_templates`, `document_templates`, `component_configurations`, `dashboard_layouts`, `companies`, and others is preserved for backward compatibility. A future cleanup arc may migrate these to FKs; new tables should not perpetuate the String-not-FK pattern.

### ⚠️ A constraint defines behaviour on DELETE too, and can REVOKE

The intuition that a constraint only refuses things is wrong, and the wrong half
is silent.

**A foreign key specifies what happens on DELETE as well as what is accepted on
INSERT, and its `ON DELETE` default is `NO ACTION`.** So adding a SECOND foreign
key over a parent that an existing key already cascades from does not layer a
check on top of the cascade — **it revokes it.** The delete that used to remove
children starts raising, and nothing in the migration mentions deletes.

When adding a constraint, state both halves:

    "What does this refuse on INSERT, and what does it now do on DELETE?"

If another constraint already covers the same parent, match its `ON DELETE`
explicitly rather than taking the default.

Discovered September 2026 in `r177`. `agent_anomalies.agent_job_id` carried an FK
with `ON DELETE CASCADE`; a composite `(agent_job_id, tenant_id)` FK was added
for cross-tenant integrity and omitted `ondelete`. Deleting a job with anomalies
began to raise, surfacing as **64 teardown errors across unrelated suites** — the
first time that day a gate caught something rather than confirming something. The
INSERT side had been reasoned about carefully; the DELETE side had not been
reasoned about at all.

### Timestamp column convention — two conventions in active use

The codebase has two conventions for "last modified" timestamps. **Verify the actual column name on the target table before writing raw SQL UPDATE statements.** Don't assume `updated_at` exists everywhere.

- **`updated_at`** — newer tables (post-FH-1 ish; most tables added 2025-2026): companies, users, roles, customers, company_entities, contacts, cemeteries, products, product_categories, kb_documents, kb_categories, price_list_items, company_modules. SQLAlchemy `mapped_column(... onupdate=lambda: datetime.now(timezone.utc))` auto-bumps on ORM update. Raw SQL has to set it explicitly.
- **`modified_at`** — older tables that follow the original four-field audit convention (`created_at` / `modified_at` / `created_by` / `modified_by`) from CLAUDE.md §16: sales_orders, invoices, customer_payments, and other pre-FH-1 financial tables. The corresponding `created_at` column is also present.
- **Neither** — a few tables expose only `created_at` (e.g., `price_list_versions` has `created_at` + `activated_at` but no rolling-update timestamp). Don't try to set an update timestamp that doesn't exist.

**R-1.6.4 → R-1.6.5 historical context**: R-1.6.4 added existing-row + UPDATE patterns to seed_staging.py assuming `updated_at` was universal. Three crashes surfaced on first staging deploy (sales_orders, invoices, customer_payments). R-1.6.5 fixed each + added the seed-idempotency CI gate. Future migration to unify the convention is plausible but out of scope; for now, verify per-table.

**Class-of-bug prevention**: `.github/workflows/seed-idempotency.yml` runs `alembic upgrade head + test_seed_idempotency.sh` against a fresh Postgres on every PR or push touching `backend/scripts/seed_*.py` or `backend/alembic/versions/**`. Catches raw-SQL column drift, idempotency regressions, and migration-vs-seed drift in one ~60-90s gate.

## 6. Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app, middleware, startup/shutdown
│   ├── config.py            # pydantic-settings, reads .env
│   ├── database.py          # SQLAlchemy engine + SessionLocal
│   ├── scheduler.py         # APScheduler — 13 registered jobs + JOB_REGISTRY
│   ├── worker.py            # Background job queue worker (polls DB/Redis)
│   ├── models/              # 157 model files, 170 exports in __init__.py
│   ├── services/            # 109 service files (business logic)
│   │   ├── ai_service.py            # Claude API wrapper
│   │   ├── agent_service.py         # AR/AP/Collections agents
│   │   ├── proactive_agents.py      # 6 proactive agent functions
│   │   ├── briefing_service.py
│   │   ├── onboarding_service.py    # MANUFACTURING_CHECKLIST_ITEMS
│   │   ├── accounting_analysis_service.py  # COA AI analysis (Haiku)
│   │   ├── accounting/              # QBO + Sage providers
│   │   ├── urn_product_service.py   # Urn CRUD + AI search
│   │   ├── urn_order_service.py     # Urn order lifecycle + scheduling feeds
│   │   ├── urn_engraving_service.py # Two-gate proof approval, Wilbert form PDF
│   │   ├── wilbert_pdf_parser.py    # PyMuPDF catalog parser (259 SKUs)
│   │   ├── wilbert_ingestion_service.py  # PDF→upsert→web enrich orchestrator
│   │   ├── urn_catalog_scraper.py   # Wilbert.com web scraper
│   │   ├── wilbert_scraper_config.py # CSS selectors + category URLs
│   │   └── ...
│   ├── api/
│   │   ├── v1.py            # Route aggregator (94+ modules registered)
│   │   ├── deps.py          # Auth dependencies (get_current_user, require_admin)
│   │   ├── routes/          # 104 route files, 945+ total endpoints
│   │   └── platform.py      # Platform admin routes
│   ├── core/
│   │   └── security.py      # JWT + bcrypt utilities
│   └── jobs/
│       └── __init__.py      # Job handler registry
├── alembic/
│   ├── env.py               # Idempotent op wrappers
│   └── versions/            # 114 migration files
├── data/
│   ├── us-county-tax-rates.json
│   └── us-zip-county-mapping.json
├── static/safety-templates/ # Generated safety training PDFs
├── .env                     # LOCAL only — points to bridgeable_dev
└── .env.example             # All env vars documented

frontend/
├── src/
│   ├── App.tsx              # 150+ route definitions, platform admin detection
│   ├── contexts/
│   │   └── auth-context.tsx # JWT auth state, token refresh
│   ├── lib/
│   │   ├── api-client.ts    # Axios with token refresh interceptor
│   │   ├── platform.ts      # isPlatformAdmin(), platform mode
│   │   ├── tenant.ts        # getCompanySlug(), subdomain routing
│   │   └── utils.ts         # cn() for tailwind class merging
│   ├── components/
│   │   ├── ui/              # shadcn/ui v4 components
│   │   ├── dashboard/       # ManufacturingDashboard, SpringBurialWidget, etc.
│   │   ├── morning-briefing-card.tsx
│   │   ├── contextual-explanation.tsx
│   │   ├── confirmation-card.tsx
│   │   └── protected-route.tsx
│   ├── pages/               # Page components organized by feature
│   │   ├── urns/
│   │   │   ├── urn-catalog.tsx      # Product catalog + pricing + sync
│   │   │   ├── urn-orders.tsx       # Order dashboard + status filters
│   │   │   ├── urn-order-form.tsx   # Create/edit order
│   │   │   └── proof-approval.tsx   # Public FH proof approval (token)
│   │   └── compliance/
│   │       └── npca-audit-prep.tsx  # Placeholder — feature not yet built
│   ├── services/
│   │   ├── navigation-service.ts        # Preset-driven nav
│   │   ├── operations-board-registry.ts # Board contributor registry
│   │   └── board-contributors/index.ts  # Core contributor registrations
│   └── types/
│       └── operations-board.ts
├── Dockerfile               # Node build → nginx, port 8080
│                            # Accepts VITE_APP_DOMAIN build arg (default: getbridgeable.com)
├── nginx.conf
└── package.json
```

## 7. Environment Setup

### Local Development
```bash
# Prerequisites: PostgreSQL 16, Python 3.13+, Node 22+
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

# Database
createdb bridgeable_dev

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATABASE_URL=postgresql://localhost:5432/bridgeable_dev alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Local dev seeding

The local `bridgeable_dev` database ships empty after `alembic upgrade head`. Two seed scripts populate usable tenants:

- **Default test tenant (most sessions):** `DATABASE_URL=postgresql://localhost:5432/bridgeable_dev python backend/scripts/seed_staging.py` → creates the `testco` manufacturing tenant ("Test Vault Co", id `staging-test-001`) with 7 users, 8 company entities, 25 products, 10 orders, 3 invoices, 1 price list, 5 KB categories. Idempotent via slug-adoption (re-running cleans + re-seeds).
- **Default admin credentials:** `admin@testco.com` / `TestAdmin123!` (admin role, all permissions). Full roster in `backend/scripts/seed_staging.py:350-356` (accountant, office, driver, production roles seeded alongside).
- **FH demo tenant (Phase B onward + September demo):** `python -m scripts.seed_fh_demo --apply` (from `backend/`) → creates `hopkins-fh` funeral-home tenant + `st-marys` cemetery + pre-seeded Hopkins↔Sunnycrest cross-tenant connection + demo case FC-2026-0001 (John Michael Smith, veteran). Admin: `admin@hopkinsfh.example.com` / `DemoAdmin123!`. Director: `director1@hopkinsfh.example.com` / `DemoDirector123!`. Demo seed emails use `.example.com` (RFC 2606 reserved-for-documentation) rather than `.test` (RFC 6761 reserved-for-testing). The latter is rejected by `email-validator`, the lib Pydantic's `EmailStr` uses, breaking direct login flows. Confirmed in R-1.6.10; migration `r48_fh_demo_email_tld_fix` updates any pre-existing rows.
- **Browser tenant bootstrap:** on `localhost`, `getCompanySlug()` reads from `localStorage.company_slug`. Visit `http://localhost:5173/?slug=testco` on first load — the module at `lib/tenant.ts` persists the slug and strips the query param. Subsequent visits resolve the tenant from localStorage.

### Canonical development tenants

Bridgeable maintains separate canonical dev tenants per vertical so that all R-N work has stable, synthetic test fixtures without entangling production operations. The pattern: synthetic tenant per vertical, seeded by a per-vertical seed script, isolated from real customer operations.

- **Hopkins Funeral Home** (slug `hopkins-fh`): canonical funeral-home dev tenant. Synthetic. All FH-vertical work — arrangement scribe, family portal, scheduling, document signing, cross-tenant connections — goes through Hopkins. Seeded by `seed_fh_demo.py`. Pairs with `st-marys` cemetery for cross-tenant scenarios.
- **Test Vault Co** (slug `testco`, id `staging-test-001`): canonical manufacturing-vertical dev tenant. Synthetic. All manufacturing work — production scheduling, kanban dispatch, compliance hub, resale hub, entity card customization, runtime editor R-2 work — goes through testco. Seeded by `seed_staging.py` for the company + users + orders + products substrate, then `seed_dispatch_demo.py` for the dispatch + delivery + driver kanban substrate (R-1.6.16 wiring).
- **Sunnycrest Precast**: NOT a dev tenant. Sunnycrest is the real company that owns Bridgeable — a Wilbert burial vault licensee in Auburn, NY. Eventually Sunnycrest becomes a tenant on production. Until then, all manufacturing dev work goes through testco specifically to avoid entanglement between platform development and Sunnycrest's real operations. The Hopkins↔Sunnycrest cross-tenant relationship in `seed_fh_demo.py` queries for `sunnycrest` and gracefully skips if absent (production-only).
- **Future verticals** (vet, paving, wastewater, etc.): each gets its own canonical synthetic dev tenant when that vertical's work begins. Same pattern — synthetic, seeded, isolated.

This separation matters for: seed scripts (each script targets one vertical's tenant), migrations (no migration depends on production data), integration tests (synthetic state always available), and demos (testco demos show "what your data will look like" rather than Sunnycrest's data). Cross-tenant tests have stable receivers. Production never accidentally gets dev seed data — every staging seed script carries an `ENVIRONMENT=production` refusal guard.

### Staging deploy + auto-seed (Phase R-1.6)

Staging auto-deploys from `main` via `.github/workflows/deploy.yml` → `railway up`. The Railway start script `backend/railway-start.sh` runs after every deploy:

1. `alembic upgrade head` — apply pending migrations.
2. `python -m scripts.seed_staging --idempotent` — ensure testco tenant + demo data.
3. `python -m scripts.seed_fh_demo --apply --idempotent` — ensure Hopkins FH + St. Mary's + cross-tenant connection + FC-2026-0001.
4. `uvicorn` — start server.

Both seed scripts are idempotent (the `--idempotent` flag is the explicit-intent alias for the default ensure-or-skip behavior). Re-running on existing data is a no-op for `seed_fh_demo`; `seed_staging` cleans + re-seeds for end-state consistency. Both refuse to run if `ENVIRONMENT=production` — production has no test seed.

**R-1.6.3: seed failures FAIL the deploy.** Pre-R-1.6.3 the start script logged a warning and continued on seed errors. That swallowed a TypeError in `seed_fh_demo._ensure_user` (passing `role` string into a `User` model that has only `role_id` FK) for six R-* phases — Hopkins FH was half-seeded (company row exists, no users) and the deploy went green anyway. The CI bot investigation in R-1.6.3 surfaced the cascade. New contract: any seed failure exits the start script non-zero, Railway dashboard goes red, ops sees the failure immediately. Half-seeded tenants are not acceptable. Production still skips all staging seeds via the `ENVIRONMENT` guard.

**R-1.6.4: seed_staging idempotency across all 7 substantive seed steps.** R-1.6.3's fail-loud surfaced that `seed_staging.py` was non-idempotent at steps 4-10 + the `kb_documents` block of step 11. R-1.6.4 fixes all 7 in one patch using the existing-row + UPDATE pattern matching step 3's "password updated" canon — for each table, look up by natural key (e.g., `(company_id, name)` for company_entities, `(company_id, account_number)` for customers, `(tenant_id, version_number)` for price_list_versions), UPDATE mutable fields if found, INSERT only on miss. Identifier generation tightened to be deterministic across runs (account_number derived from loop index, NOT from a per-run counter that resets each run). Cleanup-then-insert applied to bounded child rows (sales_order_lines, invoice_lines, customer_payment_applications, price_list_items) where natural-key lookup per row would be more code than a delete + small re-insert. **Known residual debt:** `seed_staging._run_cleanup_deletes` has an FK ordering bug — dynamic FK discovery returns tables alphabetically, so `DELETE FROM customers` runs before `DELETE FROM sales_orders` and fails (silently, via savepoint swallow) when sales_orders FK references customers. R-1.6.4 makes this harmless for re-seeds via the UPDATE-on-conflict pattern in all step functions: residual rows that survived cleanup get UPDATEd in place. **Do NOT remove the existing-row checks in step functions** — they are load-bearing for cleanup-bug tolerance. A future patch may topologically-sort the cleanup deletes (or replace cleanup with a pure UPDATE-everywhere pattern), but it's not blocking.

`/api/health` includes a `commit` field sourced from Railway's `RAILWAY_GIT_COMMIT_SHA` env var. CI workflows poll the health endpoint to verify staging deployed the just-pushed SHA before running Playwright specs (closes the deploy-timing race).

### CI bot platform admin (Phase R-1.6)

Staging has a dedicated `ci-bot-runtime-editor@bridgeable.internal` PlatformUser with `support` role (the minimum role that can call `/api/platform/impersonation/impersonate`). The Playwright workflow at `.github/workflows/playwright-staging.yml` authenticates as this user — never as a human admin — so audit-log rows from CI activity are distinguishable by email pattern.

**The credential lives in GitHub Secrets, NOT in the repo, NOT in `.env.example`:**

- `STAGING_CI_BOT_EMAIL` = `ci-bot-runtime-editor@bridgeable.internal`
- `STAGING_CI_BOT_PASSWORD` = (32-char random; printed once by `provision_ci_bot.py` at provision time)

To rotate the password (e.g. quarterly hygiene): re-run `python -m scripts.provision_ci_bot --rotate` on staging, capture the new password, update `STAGING_CI_BOT_PASSWORD` in GitHub Secrets in lockstep. Failing to update the secret invalidates the Playwright CI run on next push.

### Backend Environment Variables
All defined in `backend/app/config.py` via pydantic-settings. Copy `backend/.env.example` to `backend/.env`.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `SECRET_KEY` | ✅ | — | JWT signing key |
| `ALGORITHM` | — | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | — | `30` | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | — | `7` | Refresh token TTL |
| `CONSOLE_TOKEN_EXPIRE_MINUTES` | — | `480` | Production/delivery terminal TTL |
| `CORS_ORIGINS` | — | `["http://localhost:5173"]` | Allowed CORS origins (JSON array) |
| `CORS_ORIGIN_REGEX` | — | `""` | Regex for wildcard CORS (`.*getbridgeable\\.com` in prod) |
| `ENVIRONMENT` | — | `dev` | `dev`, `staging`, or `production` |
| `FRONTEND_URL` | — | `http://localhost:5173` | Used in email links |
| `PLATFORM_DOMAIN` | — | `getbridgeable.com` | Domain for tenant URLs |
| `APP_NAME` | — | `Bridgeable` | OpenAPI title, notification sender name |
| `SUPPORT_EMAIL` | — | `support@getbridgeable.com` | Support email in notifications |
| `ANTHROPIC_API_KEY` | — | `""` | Claude API (AI features degrade gracefully without it) |
| `GOOGLE_PLACES_API_KEY` | — | `""` | Funeral home directory discovery |
| `REDIS_URL` | — | `""` | Job queue (falls back to DB polling without it) |
| `STRIPE_SECRET_KEY` | — | `""` | Payment processing |
| `STRIPE_WEBHOOK_SECRET` | — | `""` | Stripe webhook validation |
| `QBO_CLIENT_ID` | — | `""` | QuickBooks Online OAuth |
| `QBO_CLIENT_SECRET` | — | `""` | QuickBooks Online OAuth |
| `QBO_REDIRECT_URI` | — | `""` | QuickBooks Online OAuth callback |
| `TWILIO_ACCOUNT_SID` | — | `""` | SMS delivery confirmations |
| `TWILIO_AUTH_TOKEN` | — | `""` | SMS delivery confirmations |
| `TWILIO_FROM_NUMBER` | — | `""` | SMS sender number |
| `PLATFORM_ADMIN_EMAIL` | — | `""` | Seeds platform super admin on first startup |
| `PLATFORM_ADMIN_PASSWORD` | — | `""` | Seeds platform super admin on first startup |

### Frontend Environment Variables
Copy `frontend/.env.example` to `frontend/.env`.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `VITE_API_URL` | ✅ | `http://localhost:8000` | Backend API base URL |
| `VITE_APP_NAME` | — | `Bridgeable` | Brand name used in UI |
| `VITE_APP_DOMAIN` | — | `getbridgeable.com` | Base domain for subdomain routing; injected at Docker build time |
| `VITE_ENVIRONMENT` | — | `dev` | Environment identifier |

### CRITICAL RULE
**Never point local `DATABASE_URL` at Railway production.** Production credentials live exclusively in the Railway dashboard.

### CREDENTIALS DO NOT TRANSIT A SESSION

**No credential value passes through a session, in either direction. Any
procedure that requires one is restructured or handed to James.**

A secret that transits a transcript has a copy in a log, permanently, regardless
of intent. That is a property of the medium, not of the care taken, so it is a
standing constraint rather than a judgment made fresh each time.

This binds both directions and both mechanisms:

- **Out:** do not run a procedure that PRINTS a secret. `provision_ci_bot`
  without `--ensure` generates a password and writes it to stdout; that is
  disqualifying on its own, independent of what happens next.
- **In:** do not write a secret into a field — `gh secret set`, a Railway
  variable, a `.env`, a config form. Having the access does not change this.
  This holds when the value is supplied, when the action is explicitly
  authorized, and when it would be faster.

**RESTRUCTURE FIRST, ESCALATE SECOND.** A procedure that requires a secret to
pass through a session is usually a procedure that can be inverted so it does
not. `provision_ci_bot --ensure` is the worked example: instead of the database
minting a secret a human carries to a settings page, the stored secret becomes
the source of truth and the environment-recreating path makes the database match
it. Same outcome, nothing printed, nothing typed, and the failure mode becomes
self-repairing. Look for that inversion before handing the task over.

Reading whether a credential is PRESENT is not handling it. `gh secret list`
returns names and timestamps, not values, and the last-updated timestamp is
often the diagnostic — a secret unchanged for twelve weeks before a channel died
says the credential was fine and the environment was reset out from under it.

## 8. URLs and Domains

| Environment | Frontend | Backend | Platform Admin |
|-------------|----------|---------|----------------|
| **Production** | `app.getbridgeable.com` | `api.getbridgeable.com` | `admin.getbridgeable.com` |
| **Local** | `localhost:5173` | `localhost:8000` | `admin.localhost:5173` |

Tenant pattern: `{slug}.getbridgeable.com`
First live tenant: `sunnycrest.getbridgeable.com`

## 9. Key Features and Modules

### Accounting & Finance
| Feature | Status | Key Files |
|---------|--------|-----------|
| AR (invoices, payments, aging) | Built | `invoice.py`, `customer_payment.py`, `sales_service.py` |
| AP (vendor bills, payments) | Built | `vendor_bill.py`, `vendor_bill_service.py` |
| Purchase Orders (3-way match) | Built | `purchase_order.py`, `purchase_order_service.py` |
| Journal Entries (recurring, reversals) | Built | `journal_entry.py`, `journal_entry_service.py` |
| Bank Reconciliation | Built | `reconciliation.py`, `reconciliation_service.py` |
| Monthly Statements | Built | `statement.py`, `statement_generation_service.py` |
| Finance Charges | Built | `finance_charge.py`, `finance_charge_service.py` |
| Early Payment Discounts | Built | `early_payment_discount_service.py` |
| Tax System (jurisdictions, exemptions) | Built | `tax.py`, `county_geographic_service.py` |
| Cross-Tenant Billing | Built | `cross_tenant_statement_service.py` |
| Financial Reports (13 types) | Built | `financial_report_service.py` |
| Audit Packages | Built (stub) | `report_intelligence_service.py` |
| COA Analysis (AI) | Built | `accounting_analysis_service.py`, `accounting_connection.py` |

### Operations
| Feature | Status | Key Files |
|---------|--------|-----------|
| Operations Board (registry-driven) | Built | `operations-board.tsx`, `operations-board-registry.ts` |
| Financials Board (5 zones) | Built | `financials-board.tsx` |
| Order Management | Built | `sales_order.py`, `sales_service.py` |
| Delivery Scheduling | Built | `delivery.py`, `delivery_service.py` |
| Cross-Licensee Transfers | Built | `licensee_transfer.py`, `licensee_transfer_service.py` |
| Inter-Licensee Pricing | Built | `inter_licensee_pricing.py` |
| Social Service Certificates | Built | `social_service_certificate.py`, `social_service_certificate_service.py` |

### Urn Sales Extension
| Feature | Status | Key Files |
|---------|--------|-----------|
| Urn Product Catalog | Built | `urn_product.py`, `urn_product_service.py`, `urn-catalog.tsx` |
| Wilbert PDF Ingestion + Image Extraction | Built | `wilbert_pdf_parser.py`, `wilbert_ingestion_service.py` |
| Website Enrichment | Built | `urn_catalog_scraper.py`, `wilbert_scraper_config.py` |
| Catalog PDF Auto-Fetch | Built | `urn_catalog_scraper.py`, `wilbert_scraper_config.py` |
| Pricing Tools (inline, bulk, CSV) | Built | `wilbert_ingestion_service.py`, `urn-catalog.tsx` |
| Stocked + Drop Ship Orders | Built | `urn_order.py`, `urn_order_service.py` |
| Engraving Workflow (two-gate) | Built | `urn_engraving_job.py`, `urn_engraving_service.py` |
| FH Proof Approval (token-based) | Built | `urn_engraving_service.py`, `proof-approval.tsx` |
| Scheduling Board Integration | Built | `urn_order_service.py` (ancillary + drop-ship feeds) |
| Urn Inventory Tracking | Built | `urn_inventory.py` |
| Tenant Settings | Built | `urn_tenant_settings.py` |

### Safety & Compliance
| Feature | Status | Key Files |
|---------|--------|-----------|
| Safety Training (12 OSHA topics) | Built | `safety_training_system_service.py` |
| Equipment Inspections | Built | `safety_service.py` |
| Toolbox Talks + Suggestions | Built | `toolbox_suggestion_service.py` |
| OSHA 300 Log | Built | `osha_300_entry.py` |
| Monthly Safety Program Generation | Built | `safety_program_generation_service.py`, `osha_scraper_service.py` |
| NPCA Audit Prep | Extension — placeholder UI | `pages/compliance/npca-audit-prep.tsx` |

### Intelligence Layer
| Feature | Status | Key Files |
|---------|--------|-----------|
| Financial Health Scores | Built | `financial_health_service.py` |
| Cross-System Insights | Built | `cross_system_insight_service.py` |
| Behavioral Analytics | Built | `behavioral_analytics_service.py` |
| Network Intelligence | Built | `network_intelligence_service.py` |
| Report Commentary (AI) | Stub | `report_intelligence_service.py` |

### Onboarding — Manufacturing Preset (25 items)

| Sort | Key | Tier |
|------|-----|------|
| 2 | `connect_accounting` | must_complete |
| 3 | `accounting_import_review` | must_complete |
| 4 | `setup_tax_rates` | must_complete |
| 5 | `setup_tax_jurisdictions` | must_complete |
| 6 | `add_products` | must_complete |
| 7 | `setup_price_list` | should_complete |
| 8 | `setup_financial_accounts` | should_complete |
| 9 | `add_employees` | must_complete |
| 10 | `setup_safety_training` | must_complete |
| 11 | `setup_scheduling_board` | must_complete |
| 12 | `setup_purchasing_settings` | optional |
| 13 | `configure_cross_tenant` | must_complete |
| 75 | `setup_inter_licensee_pricing` | optional |
| 99 | `setup_team_intelligence` | must_complete |

## 10. Agent Jobs

### Scheduled (13 total) — `backend/app/scheduler.py`

| Job | Schedule | Source File |
|-----|----------|-------------|
| `ar_aging_monitor` | Daily 11:00pm ET | `agent_service.py` |
| `collections_sequence` | Daily 11:05pm ET | `agent_service.py` |
| `ap_upcoming_payments` | Daily 11:10pm ET | `agent_service.py` |
| `receiving_discrepancy_monitor` | Daily 11:15pm ET | `proactive_agents.py` |
| `balance_reduction_advisor` | Daily 11:20pm ET | `proactive_agents.py` |
| `missing_entry_detector` | Daily 11:25pm ET | `proactive_agents.py` |
| `tax_filing_prep` | Daily 11:30pm ET | `proactive_agents.py` |
| `uncleared_check_monitor` | Daily 11:35pm ET | `proactive_agents.py` |
| `financial_health_score` | Daily 5:03am ET | `financial_health_service.py` |
| `cross_system_synthesis` | Daily 6:07am ET | `cross_system_insight_service.py` |
| `reorder_suggestion` | Monday 6:12am ET | `proactive_agents.py` |
| `network_snapshot` | 1st of month 2:17am ET | `network_intelligence_service.py` |
| `onboarding_pattern` | 1st of month 4:13am ET | `network_intelligence_service.py` |
| `safety_program_generation` | 1st of month 6:00am ET | `safety_program_generation_service.py` |

All jobs use `_run_per_tenant()` or `_run_global()` wrappers with per-session DB isolation and error logging. All are manually triggerable via `JOB_REGISTRY` dict and the agent trigger API endpoint.

### Per-user Scheduled Jobs (new pattern — Phase 6)

Phase 6 (Briefings) introduced the first per-user scheduled pattern. APScheduler doesn't register one trigger per user (that would scale poorly with 100+ users per tenant); instead:

- **Single global sweep trigger**: `CronTrigger(minute="*/15")` — one APScheduler job registration.
- **Sweep function queries users whose per-user time preference fell in the trailing window**: e.g. `briefing_preferences.morning_delivery_time ∈ [local_now - 15min, local_now]`. Per-user timing runs in application code, not in the scheduler.
- **Idempotent via DB unique constraint**: the briefings table has a partial unique on `(user_id, briefing_type, DATE(generated_at AT TIME ZONE 'UTC'))`. Even if a sweep ran twice inside the same 15-min window, the second insert raises; the sweep pre-checks with `func.date(...) == today` for a cheap short-circuit.
- **Tenant timezone aware**: the sweep resolves `Company.timezone` (fallback `America/New_York`) + computes `local_now` per tenant before the window check. One tenant's 7am is a different wall-clock than another's.
- **Best-effort per user**: failures log and continue; one user's error never blocks the rest of the sweep.

Future per-user scheduled features (e.g. individual reminder digests, per-user inbox notifications, personal KPI pulls) reuse this same pattern: write a sweep function that queries users by a per-user preference, register a global cron trigger in `scheduler.py`. Reference implementation: `app/services/briefings/scheduler_integration.py`.

### Not Yet Implemented (~30 jobs)
`CREDIT_MONITOR`, `PAYMENT_MATCHER`, `1099_MONITOR`, `VENDOR_STATEMENT_RECONCILIATION`, `STATEMENT_RUN_MONITOR`, `RECONCILIATION_MONITOR`, `ABANDONED_RECONCILIATION_MONITOR`, `PO_DELIVERY_MONITOR`, `THREE_WAY_MATCH_MONITOR`, `RECURRING_ENTRY_RUNNER`, `REVERSAL_RUNNER`, `STALE_DRAFT_MONITOR`, `FINANCE_CHARGE_CALCULATOR`, `FINANCE_CHARGE_REMINDER`, `EXEMPTION_EXPIRY_MONITOR`, `DELIVERY_INTELLIGENCE_JOB`, `DELIVERY_WEEKLY_REVIEW`, `SEASONAL_PREP_JOB`, `NETWORK_ANALYSIS_JOB`, `NETWORK_READINESS_JOB`, `EMPLOYEE_COACHING_MONITOR`, `COLLECTIONS_INSIGHT_JOB`, `PAYMENT_PREDICTION_JOB`, `VENDOR_RELIABILITY_JOB`, `VENDOR_PRICING_DRIFT_JOB`, `FINANCE_CHARGE_INSIGHT_JOB`, `DISCOUNT_UPTAKE_JOB`, `RELATIONSHIP_HEALTH_JOB`, `PROFILE_UPDATE_JOB`, `OUTCOME_CLOSURE_JOB`

## 11. Coding Conventions

### API Routes
```python
# backend/app/api/routes/{module}.py
router = APIRouter()

@router.get("/endpoint")
def get_something(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Docstring."""
    return db.query(Model).filter(Model.company_id == current_user.company_id).all()
```
Register in `backend/app/api/v1.py`:
```python
v1_router.include_router(module.router, prefix="/module", tags=["Module"])
```

### SQLAlchemy Models
```python
class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```
Import in `backend/app/models/__init__.py` and add to `__all__`.

### Frontend Pages
```tsx
export default function FeaturePage() {
  const [data, setData] = useState(null)
  useEffect(() => { apiClient.get("/endpoint").then(r => setData(r.data)) }, [])
  return <div className="space-y-6 p-6">...</div>
}
```
Register route in `frontend/src/App.tsx`. Add nav item in `frontend/src/services/navigation-service.ts`.

### Nightly Agent Jobs
Add function in the appropriate service file. Add wrapper in `backend/app/scheduler.py`. Add to `JOB_REGISTRY`. Per-tenant jobs use `_run_per_tenant()`.

### Accounting Agents (Phase 1 Infrastructure)

**Architecture:** Shared infrastructure for 13 accounting agents (month-end close, AR collections, unbilled orders, etc.). Agents run as background jobs with a human-in-the-loop approval gate before committing changes.

**Key files:**
- `backend/app/services/agents/base_agent.py` — Abstract base class all agents extend
- `backend/app/services/agents/agent_runner.py` — Job creation, validation, execution orchestrator
- `backend/app/services/agents/approval_gate.py` — Token-based email approval workflow (simple path for weekly agents, full path with period lock for month-end)
- `backend/app/services/agents/period_lock.py` — Financial period locking service
- `backend/app/services/agents/ar_collections_agent.py` — AR Collections Agent (Phase 3)
- `backend/app/services/agents/unbilled_orders_agent.py` — Unbilled Orders Agent (Phase 4)
- `backend/app/services/agents/cash_receipts_agent.py` — Cash Receipts Matching Agent (Phase 5)
- `backend/app/services/agents/expense_categorization_agent.py` — Expense Categorization Agent (Phase 6)
- `backend/app/services/agents/estimated_tax_prep_agent.py` — Estimated Tax Prep Agent (Phase 7)
- `backend/app/services/agents/inventory_reconciliation_agent.py` — Inventory Reconciliation Agent (Phase 8)
- `backend/app/services/agents/budget_vs_actual_agent.py` — Budget vs. Actual Agent (Phase 9)
- `backend/app/services/agents/prep_1099_agent.py` — 1099 Prep Agent (Phase 10)
- `backend/app/services/agents/year_end_close_agent.py` — Year-End Close Agent (Phase 11)
- `backend/app/services/agents/tax_package_agent.py` — Tax Package Compilation Agent (Phase 12)
- `backend/app/services/agents/annual_budget_agent.py` — Annual Budget Agent (Phase 13)
- `backend/app/schemas/agent.py` — All Pydantic schemas (enums, request/response models)
- `backend/app/api/routes/agents.py` — API endpoints (under `/api/v1/agents/accounting`)
- `frontend/src/pages/agents/AgentDashboard.tsx` — Run agents, view history, manage period locks
- `frontend/src/pages/agents/ApprovalReview.tsx` — Review anomalies, approve/reject with period lock

**Database tables:** `agent_jobs` (extended), `agent_run_steps`, `agent_anomalies`, `agent_schedules`, `period_locks`

**Job lifecycle:** `pending` → `running` → `awaiting_approval` → `approved` → `complete` (or `rejected`/`failed`)

**Creating a new agent (Phase 2+):**
```python
from app.services.agents.base_agent import BaseAgent
from app.schemas.agent import StepResult, AnomalySeverity

class MonthEndCloseAgent(BaseAgent):
    STEPS = ["validate_balances", "post_accruals", "reconcile"]

    def run_step(self, step_name: str) -> StepResult:
        if step_name == "validate_balances":
            # Read-only analysis — always safe
            issues = self._check_balances()
            for issue in issues:
                self.add_anomaly(
                    severity=AnomalySeverity.WARNING,
                    anomaly_type="balance_mismatch",
                    description=issue["desc"],
                    amount=issue["amount"],
                )
            return StepResult(message=f"Found {len(issues)} issues", data={"issues": issues})
        elif step_name == "post_accruals":
            self.guard_write()  # Raises DryRunGuardError if dry_run=True
            # ... commit financial writes ...
            return StepResult(message="Posted accruals", data={})
```
Register in `AgentRunner.AGENT_REGISTRY`:
```python
from app.schemas.agent import AgentJobType
AgentRunner.AGENT_REGISTRY[AgentJobType.MONTH_END_CLOSE] = MonthEndCloseAgent
```

**Period lock integration:** `PeriodLockService.check_date_in_locked_period()` is called in `sales_service.py` before creating invoices or recording payments. Returns `PeriodLockedError` (HTTP 409) if the date falls in a locked period.

**Dry-run mode:** Default for all agent runs. `guard_write()` prevents any database mutations. Produces the same report/anomalies as a live run without committing changes.

**Approval gate:** After agent completes, generates a `secrets.token_urlsafe(48)` token, sends HTML email with approve/reject buttons. Token expires after 72 hours. No auth required — the token IS the auth. Approval locks the period; rejection does not.

### shadcn/ui v4
Uses `@base-ui/react` — **no `asChild` prop**. Use `render={<Component />}` instead. Use `buttonVariants()` for styling Links as buttons.

### Focus Canvas tier-renderer pointer-events contract

All three Focus Canvas tier renderers (`canvas`, `stack`, `icon`) are uniformly `pointer-events: none`. Interactive descendants self-assert `pointer-events: auto` on their own outer containers — `WidgetChrome` for canvas-tier widgets, `StackRail` for the right-rail Smart Stack, `IconButton` + `BottomSheet` (4 elements) for icon tier. CSS pointer-events is not inherited; descendants with explicit `pointer-events: auto` receive events normally even when the parent renderer is `pointer-events: none`.

This contract enables full-viewport renderer placement (`absolute inset-0`) without intercepting events meant for surfaces beneath. Canvas is a sibling of the focus-core-positioner inside `Dialog.Portal` but renders AFTER (Phase 4.2.3 DOM-order swap so accessories paint on top of core); at equal z-index this would otherwise mean every viewport coordinate gets captured by the topmost tier renderer, breaking kanban interactions in the popup beneath.

Established in **Phase 4.2.1** for canvas tier; extended to stack + icon tiers in **Phase 4.3b.3.1** after the `AncillaryPoolPin` widget triggered the latent bug — pre-pin the stack tier was rarely active in production (no widgets → canvas tier always passed), so the pin's 260px width forcing fall-through to stack tier exposed the asymmetric pointer-events contract for the first time.

**Future tier renderers + interactive children must follow this pattern.** Tier renderer = pointer-events: none. Each interactive surface inside self-asserts pointer-events: auto on its OWN container. New widgets that wrap their interactive content in another auto layer don't break anything; widgets that rely on the renderer's pointer-events would (silently — the bug surfaces only when widgets actually need to be active in production tier).

### Spec-Override Discipline

When user specification appears to conflict with design system canons, implementation conventions, or Sonnet's preferred interpretation:

1. **Flag the conflict** during pre-build investigation phase.
2. **Articulate both interpretations** clearly.
3. **Wait for user decision.**
4. **Execute per confirmed direction.**

Do not execute opposite of stated spec and justify after the fact. User spec is the primary source of direction. Canonical docs inform the approach but do not override explicit user direction. When tension exists between the two, resolution happens through conversation, not unilateral interpretation.

This rule caught an instance in Phase 3.3 where three explicit spec items were not executed due to Sonnet's preference for canonical doc interpretation (Dispatch Monitor rename skipped; empty driver columns shipped as "always render" when spec said "hide by default reveal on drag"; rotation physics left untouched when user specified "needs polish"). Rework was required in Phase 3.3.1. The discipline prevents this pattern from recurring.

Scope: applies to build prompts where the user has stated explicit direction. Exploratory/design conversations where the user is asking Sonnet to think alongside them are different — those invite interpretation. Build prompts with spec lists do not.

### Build discipline — session lessons

Process conventions discovered during the Workflow Builder rebuild + inline-params thread (2026-05/06). These govern how build sessions are gated, verified, and reported — orthogonal to the code conventions above.

**Scope is the STOP gate, not a line count.** Bound a phase by *what it touches*, not by LOC. Numeric ceilings false-trip on test-thoroughness and JSX/gesture verbosity, which inflate line count over logic without indicating scope creep — observed repeatedly (P1 landed ~582 vs a ~580 estimate; P3a ~452 vs ~370; P3b-1a ~338 vs a 250 "ceiling"), every one on-spec. The live STOP signal is "is this still just the bounded thing (the gesture / the helper / the rail-flip)?" — if a keyboard listener, an inspector change, a new infra dependency, or an out-of-scope file appears, STOP and surface. A high line count with on-spec scope is not a STOP; verbose JSX is expected. Dispatches should phrase STOP triggers as scope predicates, not numbers (a numeric ceiling, if given, is a soft flag to re-confirm scope, not a hard halt).

**The `EnvironmentTeardownError` flake (r21/DocumentsTab class) is environmental — 0 test failures.** vitest intermittently emits `EnvironmentTeardownError: [vitest-worker]: Closing rpc while "onUserConsoleLog" was pending` under parallel full-suite load (often surfacing via `DocumentsTab.test.tsx`). It is a worker-teardown rpc artifact, **not a test failure** — the suite reports 0 failures, and the implicated file passes in isolation (DocumentsTab: 21/21 ×2). Do not treat it as a build failure, do not re-derive its cause each time, and do not let it block a commit. Confirm 0 *test* failures, re-run once (it usually doesn't recur, or recurs harmlessly), note "the known r21/DocumentsTab environmental class," and proceed. The capture-or-clean-streak discipline is satisfied by one clean run + the characterization.

**Read build reports against the acknowledgement, not just for green gates.** A green build (tsc + vitest + build all passing) can still have drifted from the agreed design — green proves "it works," not "it's what we agreed." The semanticParams legibility drift (a prior cleanup repointing the sentence-engine exclusion at the wrong set) shipped green and was caught only by cross-checking the build-complete report's *wording* against the acknowledged intent, not by any failing test. When reporting a build, state what was built in terms the operator can check against the acknowledgement; when reviewing one, verify intent, not just the gate.

**Repo-on-Drive-mount fragility — migrate to `~/Projects/`.** The project root currently lives under a Google Drive CloudStorage path (`~/Library/CloudStorage/GoogleDrive-…/My Drive/…`). Mid-session this caused an **actual filesystem outage** — `git` and file reads returned `Operation not permitted` / `EPERM` for several minutes while the Drive file-provider was in a denied/reconnecting state, blocking all work until it resynced. This is now justified-by-incident: migrating the repo to a local path (`~/Projects/`) is recommended to remove the dependency on the Drive mount's availability. Until then: a transient `Operation not permitted` on git/reads is the mount, not the repo — surface it, hold, and resume when access returns (nothing is lost; the working tree is intact).

**Stale-view-after-deploy — hard-refresh an open staging tab.** Railway's native GitHub-integration deploy does NOT auto-reload an already-open staging tab. After a push, **hard-refresh** the tab before judging behavior — a tab opened against the pre-deploy bundle can show a degraded/"unsaved" or "Network Error" state mid-deploy that looks like a regression but is just the old bundle against the new (or restarting) backend. This is expected deploy choreography, not a bug; confirm against a freshly-loaded tab.

### Characterization before extraction

Any extraction of logic out of a route handler or into a new service follows this order,
without exception:

1. **Characterization tests first**, pinning current behavior — *including behavior that
   is wrong*. Tag wrongness explicitly (`# WRONGNESS`) with what is wrong about it.
   These must pass against the current code before anything moves.
2. **Extract.** The characterization suite must still pass **unmodified**.
3. **Fixes get their own visible commits**, after the move, never inside it.

Behavior-preserving includes **test-observable** behavior — import location, flush
timing, exception type — not only outputs. If a test breaks on a refactor, the default
is that the refactor changed something, not that the test needs updating.

A refactor commit that also changes behavior is unreviewable, and correctness fixes
deserve to be visible rather than riding along inside a move.

**Exception — security-adjacent fixes do not queue behind refactors.** A cross-tenant
read or an unenforced permission ships first, as its own commit, before the extraction
it was found during.

### Money math is hand-proven — including aggregates

Financial calculations are cross-checked against hand-computed expected values stated
as literals in the test, with the arithmetic shown. Never compute the expected value
using the code under test.

This extends to **any aggregate in a write path**. SQLAlchemy autoflush inserts pending
rows before a `sum()` or `count()` in the same session, so an aggregate that appears to
exclude the row being created silently includes it. Every such site is a potential wrong
number with no error signal.

### Test hygiene is a ratchet

New test files clean up their own tenants via `tests/_cleanup.py::purge_companies_by_slug`,
which encodes the FK-safe deletion order in one place. The company-litter count can only
shrink. Cascade behavior in this schema is uneven — extend the helper rather than writing
a local delete list.

### Removal before recognition — how the rest of this section is meant to be used

Read this before the taxonomies that follow, because it decides whether they
apply.

**When a failure shape is identified, ask whether the available method that
produced it can be REMOVED, and prefer that to a rule asking people not to use
it. Taxonomy is the fallback for when removal is not possible.**

The distinction is not stylistic. A named shape has to be recognised in the
moment by someone who is looking; a removed method does not, because there is
nothing left to recognise. Recognition requires attention at exactly the point
where attention is scarce — mid-task, on the thing that is not the topic.

**A validated field is a hole with a guard on it. An absent field is not a
hole.** That is the test for whether a removal is real.

Worked examples, all September 2026, in both directions:

- **Removed at the type level.** The fragment contract had a supplied
  `instance_key`, which a condition could set from its own run. Validating it
  would have meant checking every producer forever. The field was deleted and
  the key derived from a declared subject, so a run-scoped key is now
  unexpressible rather than merely forbidden.
- **Removed at the procedure level.** `provision_ci_bot --ensure` reads the
  stored secret instead of minting one, so nothing is printed and nothing must
  be typed. The rule "do not let credentials transit a session" still exists,
  but the procedure no longer asks anyone to obey it.
- **Removed at the document level.** Dating discipline, the filing test, and
  supersession marking each delete an inference that a reader would otherwise
  make correctly and be wrong: date-from-position, rule-from-the-unread-document,
  liveness-from-adjacency.

**And the counter-example that proves the criterion.** The persistent-storage
rule — deliverables to `docs/investigations/`, never `/tmp/` — was correct,
well-argued, and written in response to a real loss. It failed for four months
and a second loss happened underneath it. It asked for care, and it asked in a
document the read order says to open only for *why*. Nothing about the rule was
wrong except that obeying it required someone to be looking.

So: when adding to the taxonomies below, first try to make the entry
unnecessary. If the shape can only be named, name it — recognition is worth
having, and most of these could not be removed. But an entry that could have
been a deletion is a rule that will be followed until the day it matters.

#### Removal is the LAST step, not the first

The criterion above says prefer removal. It says nothing about ordering, and the
ordering is where it goes wrong.

**You cannot remove a method while its callers still use it.** In a language that
fails at call time rather than at import — Python, and most of what runs here —
removing the method first does not surface the defect, it converts a latent
defect into a LIVE OUTAGE. A required parameter added to a function with
non-compliant callers raises nothing at import, nothing in a parse, and
`TypeError` at whatever hour the scheduler next fires it.

The sequence is:

    1. ENFORCE DIRECTION   — a ratchet: the non-compliant count may only shrink
    2. FILL THE CALLERS    — per-site, which is where the real judgement lives
    3. THEN REMOVE         — once nobody calls it the old way, the removal
                             breaks nothing and the method becomes unexpressible

⚠️ **The ratchet is what makes the interim honest rather than a permanent
almost.** Without it, step 2 is a plan, and plans decay into "we should tighten
that someday." A ratchet is mechanically enforced and its direction is one-way,
so an interim that lasts longer than intended is still an interim rather than
the new normal.

⚠️ **A ratchet needs two positive controls, not one.** It asserts an absence —
"no new violations" — and absences look identical whether the instrument works or
not. Prove the scanner can SEE (a scanner matching nothing satisfies `0 <= N`
trivially) and prove the ceiling is TIGHT (a ceiling above the real count has
stopped ratcheting and rejects nothing). See §11 *Absent signal*.

Discovered September 2026: a ruling to make a parameter required was correct as a
destination and unshippable as a first step — 34 of 64 call sites passed it, and
requiring it would have raised `TypeError` in twelve scheduled production agents
against a live tenant's books.

#### A guard reasoned from one caller is a guard reasoned from a sample

The sequencing rule above says fill the callers before removing. This says how
to know which callers there are, and it is not by reading the one in front of
you.

**Enumerate the callers. Never reason from the caller you happen to be looking
at, however authoritative that caller looks.**

⚠️ **The failure is not that the reasoning is wrong. It is that the reasoning is
RIGHT ABOUT A SAMPLE and is then applied to the population.** A guard whose
justification names one construction path is making a claim about every
construction path, silently, and the claim reads exactly like the true statement
it was derived from.

This is the instrumented-path defect arriving at a smaller scale: a reachable,
correct, verified path that is not where the traffic goes. Sample and population
diverge, and nothing in the sample announces that it is one.

THE TEST, before any guard that raises, refuses, or requires:

    "How many paths construct this, and did I count them or read one?"

Discovered September 2026, and the provenance is the point. A helper raised when
its input was absent, justified in its own docstring: *"`AgentRunner.create_job`
requires both dates, so this can only fire on a job created some other way."*
Every word true. Measured against production, the other way is the common way —
the only `month_end_close` job that has ever run there was built by a seed
script and carries no period, as does one in every other job type the script
seeds, while four whole job types are 100% null. The raise would have aborted
the step at its next run.

⚠️ **It was written by the author who had landed the sequencing rule that morning,
inside the commit fixing that exact class.** Knowing the rule did not help,
because the rule was about callers and the defect was about which callers you
know of. That is the argument for a fixed test rather than a remembered
principle.

Same move as per-row over per-type, and the same family as the constructed
count: a bound taken from the view rather than from the data.

### Figures in dispatches are never inherited

Every dispatch that states a figure — a count, a file list, a set of sites, a row total —
carries an instruction not to inherit it. The instruction is unconditional. It is not
applied where uncertainty is felt, because the figures it catches are the ones nobody
thought to check.

Measured 2026-09-04: the line caught two figures in a single dispatch cycle. A universal
claim about entity-id coverage, produced by a query ending `LIMIT 6` and reported without
its bound. And a phase count of 41, produced by subtracting 4 from 45 where the 4 counted
agents and the 45 counted sites. Both authors were confident. Neither figure survived
re-derivation.

This is the removal criterion applied to dispatch authorship: a figure that cannot be
inherited cannot be inherited wrongly. The alternative — asking the reader to notice when
a number looks uncertain — fails at exactly the cases that matter, because confidence is
not correlated with correctness.

Corollary: a dispatch's own scope figures are subject to its own method constraints. A
brief that imposes enumeration discipline and then populates its question list from an
inherited file list has violated itself. This has happened; see the services/pulse
sixfold undercount, 2026-09-04.

### A gate reports its denominator

**Every gate result is reported as a fraction of the surface it selects from.**
"2,281 passing across 164 of 426 test files," never "2,281 passing." The scope
is stated at the point of reading, not left for someone to go and ask.

A curated manifest is a legitimate instrument. Reporting it in unscoped language
is not, because **"gate green" reads identically whether the gate covers
everything or a third of it.** That is the same sentence doing two different
jobs, and the reader cannot tell which from the words.

⚠️ **THE SECOND-ORDER PROPERTY IS THE REASON THIS IS A RULE AND NOT A
PREFERENCE.** A gate that SELECTS rather than COVERS can be satisfied by adding
files to the manifest, and it can be silently narrowed by files never being
added. **Neither movement appears in the number.** A denominator that is never
printed is a denominator nobody notices shrinking, and what accumulates outside
it is not a backlog — it is an unclassified population, growing while every
session reports green.

This is the removal criterion, not a request for care. A reported denominator
makes the scope unmissable; a remembered one asks every reader to reconstruct it
at exactly the moment they are reading past it.

Measured 2026-09-04: the backend gate covers **164 of 426** test files. The
other 262 hold **182 red results** — 45 failed, 137 errors, across 28 files.
Five gate numbers had been reported and accepted that day (2243, 2251, 2269,
2274, 2281), each as "gate green, no pre-existing red," each true and each about
38% of the files.

⚠️ **A red result outside the gate is not yet a defect.** The one manifest file
among the 28 passes 20/20 alone and 20/20 inside the gate, and errors 20/20
under a whole-tree run — order coupling, not breakage. So some fraction of the
182 is contamination rather than defect, **and that fraction cannot be guessed.**
Classifying the 262 is real work; asserting their status without doing it would
be the constructed count again.

⚠️ Kin to the absent signal, one layer in. There the instrument was dead. Here
it is alive, correct, and pointed at part of the surface — and the phrase
reporting it is the same either way.

**The same discipline applies to any count whose POPULATION is ambiguous, not
only to gates.** A count that silently mixes two kinds of row reads identically
to one whose population is known, which is the denominator problem wearing
different clothes.

Standing instance: `agent_anomalies` in production contains **five seeded demo
rows across four types**, written by `backend/scripts/seed_accounting_demo.py`,
which creates `AgentJob`/`AgentAnomaly` directly because both are unguarded.
**Every count over that table states whether it includes them.** Two of the
three anomaly types an investigation once reported as having no locatable writer
are among those five — the "unlocated" types were seeded, and a count that had
declared its population would have said so.

### A CAUSE is inherited more easily than a count

*Figures in dispatches are never inherited* covers counts. This covers the
sentence that gets built on top of one, and it is harder to catch for a reason
worth stating: **a count looks like a measurement, so someone eventually
re-derives it. A cause does not look like a measurement, so nobody does.**

**A causal claim repeated across two or three messages stops reading as an
inference at all.** It acquires the texture of background fact — not because
anyone decided it was established, but because it was never phrased as a
question after the first time.

THE TEST, applied to any because-clause a decision rests on:

    "Was this MEASURED, or was it inferred from two things that were?"

⚠️ **The specific trap is a shared symptom.** Two different causes producing
identical evidence is the case where inference feels safest and is worthless.
An agent that stopped RUNNING and a condition that stopped HOLDING produce the
same silence. A check comparing the two by that silence returns equality under
both, so it looks like a discriminator and is one only when they differ —
exactly when you did not need it.

Discovered September 2026, twice in one arc and once inside the guard against
it. "The condition resolved on 2026-08-31" was inferred from an agent going
quiet, carried through three messages, and used to authorise marking 1,825 rows
stale. The condition had not resolved: the category those rows named still had
no GL mapping, and the agent was quiet because a step upstream stopped finding
input. The first attempt to verify staleness compared each key's last write to
its type's last write — which is the shared-symptom shape again, and it returned
equality for every key.

**Break the tie on the CONDITION, never on the reporter.** Ask what the finding
claims and go look at that, rather than asking whether the thing that reported it
is still talking.

### Checks that are green without being evidence

Extracted 2026-09-01 from the accounting arc's working record, which carries shapes
1–5 from before that arc. Nine recorded shapes, each with the defect it caught.
⚠️ None was found by a failing check — by construction, every one was green at the
moment it was caught.

**These are three mechanisms, not nine of a kind.** Shapes 1–5 share a mechanism: the
check's passing state can be produced by the very defect it should catch. Shapes 6–8 are
green-without-evidence by a different mechanism entirely — nothing about the defect
produces the green; the check simply never had contact with what it names. One remedy
catches all eight.

⚠️ **Shape 9 is the one that remedy does not catch**, which is why it is filed
separately and last.

#### Mechanism A — the defect produces the green (1–5)

**1. Conditional teardown.** A test that cleans up conditionally can be made to stop
cleaning up by the thing it failed to clean. Caught in `tests/_tenant.py`: the fixture
skipped cleanup when the row already existed, so run 1 leaked and every run after took
the skip branch. *"Clean when run alone" was true and meant nothing.*

**2. A ratchet too weak to catch its own bug.** Asserted a job name appeared anywhere in
`scheduler.py`; the unregistered wrapper function satisfied it. Deleting the registration
left it green. ⚠️ No rule was recorded for this shape — the record is the incident only.
Do not supply one retroactively.

**3. Void reversal unwired.** Every test called the helper directly, so deleting the
production call site broke nothing. ⚠️ No rule was recorded. Incident only.

> Shapes 2 and 3 are adjacent — both checks exercised an artifact rather than the wiring
> that reaches it. That is an observation, not a rule. If a third instance appears, the
> generalization will have been earned; until then it has not been.

**4. A ratchet matching the receiver's NAME.** Match the attribute, not the receiver — a
check that requires the caller to have named their variable conventionally passes on
unconventional code, which is where defects live. Caught: the ratchet asserted `Customer.x`
and `customer.x`; the real code called the local `cust`.

**5. A failed flag that proved nothing.** A page set the flag in `.catch` and the test
asserted the error state; removing the `.catch` entirely still rendered the error, because
a rejected promise left the data null either way. *The flag was bookkeeping; `!data` was
the real guard.*

#### Mechanism B — green without contact (6–8)

**6. A check that passes for a reason unrelated to what it claims.** Ask what would have
to be true for this to fail. If the answer involves a condition the test does not control,
it is not covering what it names. Caught: the GL decoy resolver test, still green after a
CHECK constraint narrowed the vocabulary out from under it. *The behaviour was correct and
the coverage was imaginary.*

**7. A check whose success condition is invariant under the failure it catches.** When a
check tests an invariant — balances, totals, round-trips — ask which WRONG answers also
satisfy it. Symmetric corruption usually does. Caught: the trial balance filtering
`status == "posted"`, reporting the negation of figures that should have been zero, and
reporting `balanced: True` while doing it.

**8. A monitor whose failure mode is silence.** Anything that reports by EMITTING — a
monitor, a tail, a grep pipeline, a poll loop — needs a positive control. Confirm it can
speak before trusting that it is quiet. Caught: two CI watchers on
`gh run list --commit <SHORT-sha>`. Shapes 6 and 7 return a wrong answer; ⚠️ this one
returns NO answer and lets you supply the wrong one yourself. It was written four minutes
after shape 6 was described, into the instrumentation of the session that described it.

#### Mechanism C — green, with contact, against the wrong specification (9)

**9. A check that asserts the value the implementation produces, because it was written
from the implementation.** The check sees perfectly. It has full contact with the thing it
names. It is simply asserting the wrong answer, because the answer was copied from the code
rather than derived from the world the code is supposed to describe.

Caught 2026-09-09: **55 literals** across eight frontend and two backend test files pinned
`"/dispatch"` as the expected navigation target of four shipped widgets. `/dispatch` had
never been a route in any revision of the app. Every one of those assertions was green, and
the widgets' primary call-to-action had been landing on a 404 for four and a half months.

⚠️ **A break test on shape 9 passes its own criterion and still defends the defect.**
Break the wiring and those 55 assertions go red — correctly, specifically, exactly as the
remedy below demands. They would also have gone red the moment someone *fixed* the dead
route. **The check is not broken; it has been taught the defect as the specification.**

This is *fixtures modelled on the implementation* reaching literals rather than fixtures,
and the literal is the harder case: **a fixture looks like data you might have derived, and
a literal looks like a fact.** `"/dispatch"` reads as knowledge about the app. It was a
transcription of a mistake.

**The remedy for shape 9 is different in kind from the remedy for 1–8.** No amount of
coverage, and no positive control, reaches it — both operate inside the code's own account
of itself. The only thing that catches it is **checking the value against the world rather
than against the code**: click the link, resolve the id, enumerate the routes and confirm
the target is among them. When an expected value names something outside the system — a
route, a URL, a file path, an external id — the check is only worth what its correspondence
to that thing is worth, and that correspondence cannot be established from inside the repo.

#### The remedy — one test for shapes 1–8

**Break the thing it guards and confirm it goes red — and check the break turns THAT check
red, not merely something.**

The final clause is the load-bearing half. A break that turns the suite red while leaving
the specific check green is the failure this whole list describes.

**If a check cannot be made to fail, it is documentation.** File it as such or delete it;
do not count it as coverage.

⚠️ **Passing this remedy is necessary and not sufficient** — see shape 9, which passes it.

**The deletion corollary: the fix is often deletion, not another test.** Both times this
list caught asserted-but-absent coverage in a single session, the repair simplified the
code rather than adding to it.

#### The counterweight

This list is not an argument that guards are untrustworthy. The session-scoped COMPANY
LITTER row-counting tripwire earns its keep **precisely because it does not trust the
per-fixture cleanup it watches.** A check that assumes its neighbours are honest inherits
their failures; a check that re-derives independently is the thing this list is asking for,
not the thing it is warning about.

The distinction is what a green result is evidence OF. A check that would still pass under
the defect proves nothing. A check that re-derives from a different direction proves
something, and is worth its cost.

### Failures in the other direction — negatives, derivations, and dead signals

The preceding section covers checks that are green without being evidence, and
one remedy catches all eight of them. This section covers a different mechanism,
and the break test does not detect any of it. These entries are named rather
than numbered: they are not more shapes of the same kind, and reading them as a
continuation of the list is itself the error.

Three concern claims that are wrong while looking right. The fourth concerns
inference rather than checking at all.

#### False absence from a constructed name

The preceding shapes describe checks that pass when they should not. This is the
mirror: a NEGATIVE result that is not a finding.

A query built around a name you constructed can return nothing while the thing
exists under a different name. A route path, a pluralized table, a filename
keyword, a directory prefix glob — all the same object. A miss on any of them is
a FAILED LOOKUP, not an absence.

THE TEST, applied to every negative result before it is reported:

    "Could this query have returned nothing while the thing exists?"

If yes, the null is uninformative. Re-derive by enumeration: enumerate the app's
route table rather than grepping path strings; query information_schema rather
than guessing pluralization; read __tablename__ off the model; walk the
directory tree rather than matching a naming convention.

Note that a filesystem walk can still fail this test. `app/services/focus*/`
walks the filesystem and never enters a directory that does not start with
"focus". The question tests the QUERY, not the querier — which is why it works
where care does not. No amount of attention distinguishes a constructed name
from a real enumeration at the moment of writing it.

Discovered September 2026, Sales & Orders census: five distinct false absences
across four namespaces, none caught by review, each caught only by re-deriving
with a different method.

#### The constructed count — magnitude is a claim too

Sibling of the entry above, at the same mechanism and a different target. That
one concerns whether a thing EXISTS; this one concerns HOW MUCH, and the same
constructed-scope failure produces both.

**A correct finding recorded at the wrong magnitude is functionally a missed
one.** Not a lesser version of the finding — a different one, because magnitude
selects the response class. Six consecutive failures reads as a flaky week and
prompts a note; ninety-five reads as a dead channel and prompts a repair. Same
diagnosis, same evidence, same honesty, opposite outcome.

So magnitude claims need the enumeration discipline that existence claims get. A
count taken from what happened to be in view is a constructed count, and it
carries the same warning as a constructed name: it will be plausible, it will be
well-formed, and nothing about it announces its scope.

THE TEST, applied to any count that will drive a decision:

    "What bounded this count — the thing, or my view of it?"

If the answer is the view — the page of results returned, the runs the tool
listed by default, the window the query happened to cover — the number is a
lower bound wearing an exact figure's clothes. Enumerate to the actual boundary,
or report it as a bound.

⚠️ Note that "when did this last pass?" is a MAGNITUDE question wearing an
existence question's clothes, which is why it works and why it gets skipped.
Asked of a red channel it looks like a yes/no about the current state; what it
actually returns is the size of the dark window.

Discovered September 2026: a session correctly identified a dead CI channel,
correctly attributed it to the CI credential, and honestly recorded it — as "six
consecutive runs" against an actual ninety-five, because six was what the
default listing showed. The finding was right and produced no action for six
more days. See "Absent signal" below.

#### Conclusion survives, derivation falsified

The worst case is not a wrong conclusion. It is a RIGHT conclusion reached
through evidence that does not support it.

A wrong conclusion eventually contacts reality and gets corrected. A correct
conclusion resting on a falsified derivation never does — nothing downstream
contradicts it, so it is never re-examined, and it is cited later by people with
no way to know what it rests on.

Consequence: verify derivations on claims you AGREE with. Agreement is not
confirmation. When an investigation records how a claim was reached, the
derivation is auditable; when it records only the claim, it is not.

#### A confession is a claim, and it is the one nobody audits

Self-criticism carries the same burden of evidence as any other assertion. An
overstated fault is a false claim, and aiming it at yourself does not make it
true.

⚠️ **This is the only entry here whose failure mode is that the claim SURVIVES
BECAUSE IT WAS SELF-DIRECTED.** Every other false claim in this file was caught
because somebody checked. Candour reads as reliability, so a confession is
received as evidence of care rather than as an assertion about the world — and
nothing in the reviewer's habits points at it. The reader's attention moves to
whether you were honest, which you were, and away from whether you were right.

THE TEST, applied to your own fault-finding exactly as to a finding about the
code:

    "Did I measure this fault, or does admitting it just read well?"

An invented fault is not a harmless excess of rigour. It misdirects the next
session, it can mark correct work as suspect, and it inflates the record of
what went wrong — which is the same bias as *Reconstruction recovers errors
first*, produced deliberately rather than by memory.

Discovered September 2026. A commit recorded that a job the author had written
during that same arc "was written that way" among a list of defective ones. It
was measured afterwards at 0.63 try-coverage with its handler inside a loop —
per-item tolerance, which is the CORRECT design. The job belonged on a
different list. The self-criticism was specific, plausible, volunteered, and
wrong, and it had already been committed.

#### Saturated signal

An already-red check cannot report a new failure.

A failing test does not merely stop protecting its territory — it CONCEALS
subsequent regressions in that territory, because the red it would emit is
already being emitted for an unrelated reason, and nobody re-reads a test they
know is broken. Where the check is also ungated, nothing is listening either;
the two conditions compose, and the composed form is worse than either. The
detector is correct, its output is correct, its output is being emitted, and its
information content is zero.

This subsumes the weaker "unwired detector" framing. Unwired describes who is
listening. Saturated describes whether there is anything new to hear.

OPERATIONAL CONSEQUENCE — quarantine is deliberate saturation:

Every QUARANTINE verdict MUST record the file's exact failure signature at
quarantine time: error type, message, and count. Not "fails." A quarantined file
is a saturated signal by policy, which is acceptable only if a later, different
failure remains distinguishable from the known one. The owning arc re-runs the
file at its open and diffs against the recorded signature. A changed signature
is a finding, not a continuation.

The same applies at pipeline altitude. A CI channel red for N consecutive runs
on a known cause is dark for those N runs, and the window's length is not
knowable from inside it. When such a channel is repaired, the first green run is
a BASELINE, not a confirmation — everything that landed during the dark window
remains unverified by that channel regardless of what the first run says.

Discovered September 2026: test_phase_8_9_agents.py was red on a missing SQLite
fixture table since before the arc began; a commit added two further missing-table
dependencies inside that red and was completely invisible.

#### Absent signal — the instrument that never worked

A gate at 99-red-out-of-99 is not a saturated signal, it is an absent one.
Saturated means real failures hide inside existing red. This never produced a
signal at all, which is a different and worse condition, and it is detectable by
a question nobody asked — WHEN DID THIS LAST PASS?

The distinction matters because the two have different remedies and different
blast radii. A saturated channel has a working instrument and a known red; its
history is readable and its repair restores a signal that existed. An absent
channel has never measured anything, so there is no baseline to return to, and
"repaired" means "measuring for the first time."

**A reason not to read an instrument is not a reason to assume it works.** This
is the specific trap, because the reason is usually correct. Declining to run a
check because its result would not be evidence — wrong branch, stale deploy,
unrelated red — is right, and it stops one step short. The instrument's own
health is a separate question from whether this run would be informative, and
only the second one gets asked.

So: before reporting that a check was skipped, and before treating any gate as
covering anything, ask when it last passed. Not whether it is passing now.

Discovered September 2026: the Playwright staging channel had produced zero
green results in 99 consecutive runs across five and a half weeks, every spec
dying at a 401 before exercising anything. It was noticed once, six days in,
counted as "six consecutive runs" and correctly attributed to the CI credential
— and the last-pass question was still not asked, so the six-week figure and the
never-passed condition both went unseen.

WHY THIS NEEDS TO BE STRUCTURAL RATHER THAN REMEMBERED. The two questions look
alike and differ in what it costs to answer them. *Would this run be evidence?*
is answerable from what you already know — the branch, the deploy, the pending
red. *Does this instrument work?* requires going and looking, and it has **no
natural trigger**, because a broken instrument produces the same silence as a
healthy one nobody consulted.

That asymmetry is the whole problem. The cheap question gets asked because
something prompts it; the expensive one is prompted by nothing, and skipping it
produces no symptom. Hence a fixed check rather than an intention: **when did
this last pass** is answerable without trusting the current run, without running
anything, and against any channel with a history.

#### Causation — proximity is not necessity

Sibling to false absence above. That entry tests a query; this tests an
inference.

    "Could this failure have this cause and also several others?"

A change close in time to a failure, with a readable mechanism connecting them,
is SUFFICIENT-LOOKING. It says nothing about necessity. The test is running the
parent commit. If the failure predates the accused change, the mechanism was
real and irrelevant.

Bisect before naming a cause in writing. A ledger entry naming a specific commit
will be quoted later without its evidence, so the derivation belongs in the
entry: which SHAs were run, in what state each was, and whether the conclusion
came from measurement or inference.

Discovered September 2026: c2d82fe9 was named as the cause of a test failure from
timing plus code-reading. The test was red at the accused commit's parent. Four
worktree runs cost less than the entry would have cost being wrong in canon.

#### Expired premise — and its inherited form

A stated premise is not a check. It does not go green or red; it is simply true
when written and, sometimes, false later. Nothing signals the transition. The
sentence reads exactly the same on the day it stops being true as on the day it
was written.

This is why standing instructions, dispatch boilerplate, and carried-forward
context require re-derivation rather than review. Reading a stale line does not
reveal that it is stale.

**Inherited form.** The mechanism is much harder to see when the expired thing
is inherited rather than copied. A dispatch is READ each time it is used; an
environment variable, config default, seed flag, or CI setting is INHERITED — it
rides into successive contexts without ever being the subject of any of them. It
was a decision once, under conditions that have since expired, and then it
stopped being a decision while continuing to have effects. What makes it
invisible is precisely that it was never anyone's topic.

The exposure test is not "is this still true" — nobody asks that of a line they
are not reading. It is:

    "What is in force here that nothing in this session decided?"

Enumerate the inherited state at the start of any run whose result will be
trusted, and re-derive anything that suppresses a guard.

**Design criterion for guards.** A guard you can silence from the same place you
write the code protects you from mistakes and not from yourself. Grade every
guard on whether it runs somewhere the person who could disable it does not
reach. This is a stronger property than the guard's design quality and should be
stated separately when a guard is added.

Discovered September 2026: a test-data guard was disabled by a flag set once for
a real reason, which then rode into four successive scripts as boilerplate. It
was never re-examined because it was never any script's topic. It was caught by
an independent tripwire in CI — the first place it ran where the suppression did
not travel with it. The tripwire did not catch it by being well designed; it
caught it by running somewhere the export could not reach.

#### Answering a question does not retract it — sweep where it was ASKED

An open question gets written down in several places: the findings doc that
raises it, the docstring of the thing it blocks, a STATE entry, a commit body.
**Answering it updates the place the answer lands. Every other copy keeps
asking, and keeps instructing.**

⚠️ **The copies are not equally harmless, and the ranking is inverted from where
attention goes.** A stale line in a findings document is noise — someone reading
an investigation is reading history. A stale line in the DOCSTRING OF THE SCRIPT
saying *this must not run until X is resolved* is read by someone standing at a
terminal about to run it, after X was resolved. That is the one location where
being wrong has an effect rather than a cost, and it is the one least likely to
be revisited, because the answer was written somewhere more interesting.

So closing a question includes a SWEEP OF WHERE IT WAS ASKED, not only an
update of where it was answered:

    "Where else does this question appear, and does that copy still instruct?"

Discovered September 2026. A STOP was raised in a preconditions doc and in the
blocking script's own module docstring. The ruling arrived, the doc was updated,
and the docstring still read `UNRESOLVED — THIS SHOULD NOT RUN`. It was found by
re-reading the file, not by any check — which is the argument for making the
sweep part of the closure rather than hoping someone re-reads.

⚠️ Kin to expired premise above, with the difference that matters: there, nothing
signalled the transition. Here **something did** — a ruling was made, on a known
date, by someone who knew it closed the question. The information to update every
copy existed and was not spent.

#### Complete machinery behind an unprovisioned entrance

A subsystem can be fully built, correct, and tested downstream of a boundary
that nothing ever crosses. Every read site works. Every transformation is right.
No path produces the input.

This is invisible to code review, which reads the machinery and finds it sound,
and invisible to tests, which supply the input the entrance would have supplied.
It surfaces only when someone asks what WRITES the thing, or what CALLS the
entry point, or how a tenant would ever reach this — and that question is almost
never asked, because the machinery's correctness is not in doubt.

THE TEST, for any subsystem believed to work:

    "What produces this system's input in production, and has it ever run?"

Three instances, September 2026, two areas, found by three unrelated methods:
`post_invoice` — complete, never called, eight permanently unreachable invoices.
`legacy_photo_pending` — six read sites including a board filter and a
user-visible badge, one write, which sets it False; nothing can raise it.
The RingCentral chain — webhook through draft-order creation built and correct,
with no OAuth initiation anywhere, so no tenant can attach a phone system.

CLASS KILLER, owed: a platform-wide read-site/write-site census over boolean
columns and over service entry points, asking of each whether any code path in
production produces it. Three instances found by luck is an argument for running
the census rather than waiting for the fourth.

THE PROVISIONING COROLLARY. **If a credential, token, or account is required for
something to work, its creation belongs in the path that recreates the
environment, or it will be missing after the next reset and the absence will
surface incidentally.**

The common mechanism across instances is that provisioning is a one-time act
performed by a human at a terminal, and one-time human acts leave no artifact
that any later process depends on — so nothing ever fails loudly enough to
reveal them. The entrance is not merely unbuilt; it is unbuildable by anything
that runs on its own.

The inversion that fixes it: make the stored secret the source of truth and have
the environment-recreating path make the world match it, rather than having a
human carry a value from a generator to a settings page. Ensure, do not
provision. Never rotate on a schedule something whose counterpart is updated by
hand.

Fourth instance, September 2026: the CI Playwright bot was created by a one-time
manual script that no deploy step and no seed re-ran, so the gate it
authenticated had no provisioning path at all.

#### Enumeration defeated by presentation

A correct query can be made uninformative by what happens to its output. A pipe,
a truncation, or a viewport destroys the property being read while leaving a
plausible-looking result.

`head -10` cut an enumeration before the writer that falsified the conclusion.
`tail -30` cut earlier output the same way. `$?` read through a pipe returned
`tail`'s exit status while `tsc` had exited 2 — the same error at both ends of
the same pipe.

Never read a status, a count, or a completeness claim through a transform you
have not accounted for. If the result will be trusted, read it whole, or read
the status of the process that produced it rather than the last one in the
chain.

This is the sibling of false absence at a different layer: there, the query was
wrong; here, the query was right and its output was cut.

⚠️ **A TRUNCATION FLAG IS A `WHERE` CLAUSE ON THE OUTPUT STREAM.** That is the
whole entry in one sentence, and the reason it keeps being violated by people who
know it: `LIMIT 6` looks like part of the question, so it gets declared. `tail
-30`, `--tb=no`, `--tb=line`, `head`, a viewport — these look like part of the
PLUMBING, so they do not. They bound the answer exactly as hard.

So the declaration rule covers output flags, not only query clauses: **state the
bound wherever it was applied, including the ones that felt like formatting.**

⚠️ And the sharpest form is a NEGATIVE result read through a suppressed channel.
A grep returning zero against output whose tracebacks were switched off is not
evidence of no errors; it is evidence of no tracebacks. Measured 2026-09-04 to
09-08: three such reductions inside a single diagnosis turn — a backgrounded gate
piped through `tail -8`, leaving a ten-line log; `--tb=no` on the re-run, so a
grep for the error text returned zero and was nearly read as the errors being
absent; and `--tb=line` before that, which had already suppressed the first
diagnosis. Each was a reasonable reduction. Each destroyed the evidence the
command was run to gather.

**Remedy: capture full output to a file and read the file.** Reduce when
displaying, never when collecting.

⚠️ **THE ACTION, because the principle above has now been violated four times by
people who were holding it: ANY COMMAND WHOSE OUTPUT FEEDS AN ABSENCE CLAIM GETS
ITS FULL LENGTH CHECKED BEFORE THE CLAIM IS WRITTEN.** `wc -l` the file, compare
it to what you read, and only then write the sentence. Not a reminder to be
careful — a step with an output, performed before the claim exists, because
every violation so far was committed by someone who knew the principle and did
not have a moment at which checking was the next thing to do.

Instance, 2026-09-10: a full backend suite wrote 1,921 lines to one file while a
background task file captured only the four-line `tail` of it. A grep over the
four-line file returned nothing and was one sentence away from being reported as
"no failures in note territory."

⚠️ **A BOUND IS A DEFECT IN THE METHOD WHETHER OR NOT IT CHANGED THE ANSWER.**

This is the entry's hardest case, and the only one that cannot be caught by
noticing a wrong result. Every other instance recorded here was found because
the conclusion was false. A bound that did not happen to bite produces a TRUE
answer by luck, agrees with everything downstream, and is never revisited.

Measured 2026-09-10: a production probe asked "which audit actions carry an
actor" with `LIMIT 8` and reported the answer as complete. Re-run unbounded,
production had exactly two — so the bound never bit and the conclusion was
right. **The same query against the local database would have been truncated at
8 of 11.** The method was wrong in both places; only the environment decided
whether it mattered.

So the test is not "did this look wrong". It is:

    "Was a bound applied, and did I remove it before believing the result?"

**The only way to know whether a bound bit is to remove it and look**, which
costs one re-run. Correctness of the conclusion is not evidence about the
method, and a right answer reached through a bounded read is the version nobody
catches.

⚠️ **THE BOUND CAME FROM THE TOOL, NOT FROM THE DATA — in both instances, and
that is the shape.** Not "I looked at too little," which sounds like a lapse of
diligence and would be answered by looking harder. The transform imposed a
bound, and **the result carried no trace of having been bounded.** A truncated
listing and a complete one are the same shape on the screen.

So the operative question is about the pipeline, not the effort:

    "What in this command could have bounded the output, and would I see it if it had?"

Same mechanism as the constructed count one section up — `LIMIT 6` and `tail -30`
are the same defect at different layers, one bounding the query and one bounding
its rendering. Both produce a well-formed number that announces nothing.
Measured 2026-09-04: both occurred within one session, by the same author,
while that author was actively holding this entry.

#### A guard whose protection is supplied by a layer beneath it

The break test's usual job is to confirm a check can go red. Occasionally it
does something better: it FALSIFIES the claim the check was documented with.

**A guard can be correct, tested, and green while the thing actually producing
the behaviour is something underneath it that nobody wrote down.** Remove the
guard and nothing fails, because the lower layer still supplies the protection.
Remove the LOWER LAYER — a refactor, a library swap, a rewrite into raw SQL —
and the guard is still there, still documented as load-bearing, still green, and
no longer doing anything.

THE TEST, when documenting a guard as the reason something is safe:

    "If I replaced this with the obvious naive version, what would go red?"

If the answer is nothing, the guard is DEFENSIVE, not load-bearing. Keep it —
independence from a coercion you did not choose is worth having — but say so,
because the next reader will otherwise trust a test that is not watching it.

Discovered September 2026: an anomaly supersede key used
`col.is_not_distinct_from(value)` on nullable subject columns, documented as
load-bearing on the grounds that `= NULL` never matches. Rewritten to `==`,
every test stayed green — SQLAlchemy compiles `col == None` to `col IS NULL`, so
the ORM was supplying the null-matching, not the operator. The operator's real
value is surviving a rewrite that removes the ORM from the path, at which point
`= NULL` matches nothing and the rows it protects duplicate forever with the
whole suite still passing.

⚠️ Kin to the green-without-evidence list above and distinct from all eight: the
check is not passing for a wrong reason, it is passing for a reason that is
CORRECT AND NOT THE ONE CLAIMED. Nothing in the result distinguishes them.

#### A container test that cannot succeed looks exactly like one that ran

`x in container` is valid Python whatever the container holds. Against a list of
DICTS it compares a string to each dict, matches nothing, and returns False —
**a plausible negative from a test that could never have returned True.**

That is worse than a crash and worse than a wrong answer. A crash gets
investigated; a wrong positive gets contradicted by something downstream. **A
negative that can only ever be negative agrees with whatever you already
suspected**, and it is most convincing when it confirms that some work does not
exist yet — which is the direction that quietly inflates an estimate.

THE TEST, before a negative from any membership or containment check:

    "What is IN this container, and could a match ever have occurred?"

Assert the element type first, or the negative means nothing. `assert
isinstance(next(iter(c)), str)` is one line and converts an unfalsifiable check
into a falsifiable one.

Discovered September 2026: `k in WIDGET_DEFINITIONS` where `WIDGET_DEFINITIONS`
is a **list of dicts**. It printed "no widget of that id" for all five standing
targets. **All five were widget ids.** The report built on it would have said the
peek payloads did not exist and sized a session several times too large. It was
caught by a TypeError on an unrelated line of the same script — luck, not method.

⚠️ Kin to false absence from a constructed name, one layer down: there the QUERY
named the wrong thing, here the query is right and the CONTAINER cannot answer
it. Both return a confident nothing.

#### False presence from a substring match

The mirror of false absence. A filter that matches inside longer names produces
findings for things that were never there — a search for "ring" matched
`spring_burial*`.

Both directions fail for the same reason: the query's shape was never checked
against what it could match. Bound the match, or enumerate and read.

#### Fixtures modeled on the implementation

A test double built from the code under test inherits that code's mistakes and
then certifies them. A mock declaring `{ apiClient }` against a module that
default-exports made five tests pass against a member that does not exist.

The check has contact with something — just not with reality. Build fixtures
from the contract, not from the caller, and where a double stands in for a real
module, assert the real module's shape somewhere.

⚠️ **THE GENERAL FORM: A FIXTURE DERIVED FROM THE SAME READING AS THE
IMPLEMENTATION IS NOT INDEPENDENT EVIDENCE.** Both halves inherit one
misunderstanding and then confirm each other, which is indistinguishable from
agreement between two independent things.

**THE TELL IS THAT THE TEST PASSES ON INPUTS THE SYSTEM CANNOT ACTUALLY
PRODUCE.** That question is answerable without knowing what the defect is, which
is what makes it usable: ask of any fixture whether the shipped code path could
have produced this row, and go and look.

Instance, 2026-09-10: a settling fixture built tasks with NO ASSIGNEE, while the
fragment that emits the prompt filters `assignee_user_id == user.id` — so the
tests settled a prompt over tasks that could never have produced it. The
implementation had the matching gap (it filtered on the actor and never on the
assignee), so fixture and code agreed, and the defect they jointly hid wrote
settled records onto the wrong person's note.

Corollary for test SELECTION, not assertion: when replacing a check that
conflated two things, the tests that matter are the ones where the two DISAGREE.
Aligned-only cases pass against the defect being fixed. An indicator reading
SSE-connected as phone-connected is certified green by every test where both are
true.

#### Reconstruction recovers errors first

Memory of an investigation is not merely lossy; it is biased toward what was
DISCUSSED. In an investigation, the discussed is disproportionately the errors —
they get argued about and become canon, while correct findings are recorded once
and never revisited.

So a document reconstructed from memory will look like a document about what went
wrong, and will be trusted as a document about what is true. The bias has a
direction, which makes it predictable and therefore avoidable.

When an investigation's artifact is lost: write a STUB naming what it covered
and instructing a re-run. Do not produce a best-effort reconstruction. A
reconstruction that reads as cleanly as the original is the more dangerous
artifact.

Where reconstruction is unavoidable, mark provenance per claim — unmarked,
UNCERTAIN, RE-DERIVED, NEW SINCE THE ORIGINAL, LOST — and re-source rather than
restate. Re-sourcing recovers more than it costs: RingCentral's refresh-token
rotation, re-read rather than recalled, returned a mechanism the original did
not have.

## 12. Business Context

### Tenant Types
- **Manufacturer** (Wilbert licensee) — produces burial vaults, manages deliveries, bills funeral homes monthly
- **Funeral Home** — orders vaults, pays on charge account, receives monthly statements
- **Cemetery** — orders cemetery products, interacts with manufacturers
- **Crematory** — specialized funeral service operations

### Product Lines
- **Funeral Service** (core) — burial vaults, urn vaults, cemetery equipment
- **Urn Sales** (extension) — cremation urns (stocked + Wilbert drop-ship), engraving workflow, Wilbert catalog ingestion
- **Wastewater** (extension) — septic tanks, precast wastewater products
- **Redi-Rock** (extension) — retaining wall blocks for contractors
- **Rosetta Hardscapes** (extension) — hardscape products
- **NPCA Audit Prep** (extension) — compliance and audit readiness; auto-enabled when `npca_certification_status = "certified"`

### Key Business Workflows
1. **Monthly Statement Billing** — funeral homes get consolidated statements, not individual invoices
2. **Finance Charges** — calculated on overdue balances, reviewed before posting
3. **Early Payment Discounts** — 2% if paid by 15th of month
4. **Cross-Licensee Transfers** — NY licensee transfers burial to NJ licensee; billing chains automatically
5. **Spring Burial Season** — March–May peak, requires delivery capacity management

### Chart of Accounts Classification

The chart of accounts is a grouping query, not a maintained artifact. Classification is one
fact; presentation is a query over it. A statutory presentation variant is a second grouping,
never a reclassification.

**Classification authority is platform-owned.** An importer reading a legacy chart (Sage,
QuickBooks) PROPOSES a classification. Bridgeable's vertical default DECIDES. A tenant may
override with a recorded reason. Importer output is never the record.

**The non-operating test.** An account is non-operating if its activity would continue
unchanged were the business to stop selling its product. Interest income, gain or loss on
asset disposal, and insurance settlements are non-operating. Anything that moves with
production or sales volume is operating, whatever its number.

⚠️ Account number ranges are convention, not evidence. Sage's 9000 range does not make an
account non-operating. Classifying by range is the same defect shape as inferring a name
from a shape rather than a config — see §11 "Checks that are green without being evidence."

**Delivery cost is presented below gross profit** (2026-09-01). Per-unit costing views that
need fully-loaded delivery pull it back in as their own grouping.

## 13. Known Issues and Tech Debt

### Active Issues
- **Orphaned `tenant_settings` table** — migrations create it, but app code uses `Company.settings_json` exclusively.
- **COA extraction not implemented** — `tenant_accounting_import_staging` exists but no QBO/Sage API extraction. Only Sage CSV upload works.
- **Sage API version detection** — always returns "could not reach server"; CSV is the only real Sage path.
- **`/npca` is a placeholder** — nav item links to it; only shows "coming soon". No actual NPCA audit features built.
- **Audit package generation is a stub** — `report_intelligence_service.py:195` has a TODO for async Claude call.
- **Accountant invitation email** — `accounting_connection.py:304` has a TODO; email is not sent.
- **~30 unimplemented agent jobs** — schemas and services exist, job runners not built.
- **`seed_fh_demo` R2 dependency** — **RESOLVED by R-6.2a.1** (commit pending). `_seed_personalization_studio_phase1g` + Step 2 wrapped via `_commit_canvas_state_r2_optional` helper that catches `RuntimeError("R2 not configured")` + logs degradation + continues; seed completes regardless of R2 config; CI `test_seed_idempotency.sh` passes. Runtime callers of `commit_canvas_state` retain the hard-error contract — only seed callers handle gracefully. Original entry preserved for cross-arc lineage: surfaced post-R-6.1a (verified `git log ea8d88d..1a945d2 -- seed_fh_demo.py personalization_studio/ legacy_r2_client.py` is empty — R-6.1a touched zero files in the failure path); root cause predated R-6.2.
- **`seed_idempotency` CI script python invocation** — **DISMISSED by R-7-η** (2026-05-11). CI environments standardize on `setup-python@v5` aliasing `python` to the configured version; the script is correct under CI convention. Local-dev callers without an alias should use `python3` via shell alias or virtualenv activation. Not platform work. Original entry preserved for cross-arc lineage.
- **Inbound-cascade hand-validation requires real provider** — staging has no synthetic-email-injection endpoint by design; production code paths only. R-6.1a hand-validation against staging requires either (a) configured inbound email providers (Gmail Pub/Sub / MS Graph / IMAP) reaching testco's account, OR (b) replay against existing `email_messages` rows via `POST /messages/{id}/replay-classification`. Unit tests cover the same cascade paths via mocked LLM + real DB writes (72/72 passing R-6.1a). Runtime production validation defers to the Sunnycrest pilot launch when real inbound traffic flows.
- **`/openapi.json` disabled on staging** — **RESOLVED by R-7-β** (this commit). Staging now serves `/openapi.json`, `/docs`, `/redoc` gated by `Depends(get_current_platform_user)` (platform-admin JWT required). Production stays disabled (404 at all auth levels). Dev keeps open access for local developer ergonomics. Cross-arc-lineage discipline per R-6.2a.1 + R-7-α precedent: original framing preserved with closure note; operational verification deferred to next staging deploy + curl with platform admin token. Implementation in `backend/app/main.py` via `_should_mount_openapi` + `_should_gate_openapi` env-conditional helpers + three custom routes at canonical paths; old `/api/docs / /api/redoc / /api/openapi.json` paths retired in favor of OpenAPI conventional canon.
- **`CalendarAccountsPage.tsx` asChild violation** — **RESOLVED by Path E** (commit `73427db`, 2026-05-23); **VERIFIED CLOSED by R-7-ζ** (2026-05-11). Path E genuinely fixed the violation by routing `<DropdownMenuTrigger asChild><Button>...</Button></DropdownMenuTrigger>` → `<DropdownMenuTrigger render={<Button>...</Button>} />` at line 330 per `EmailAccountsPage.tsx` + `PortalUsersSettings.tsx` precedent. R-6.1 + R-6.2 verification reports across ~14 entries inherited stale framing flagging the violation as "pre-existing untouched" without re-verifying the source file. R-7-ζ pre-flight (per R-7-δ canonical lesson "investigate when surfaced") confirmed: (a) line 330 carries canonical `render={...}` pattern intact; (b) zero `asChild=` JSX usage anywhere in `frontend/src/`; (c) tsc clean; (d) full-codebase grep returns only the `asChild?: boolean` prop declaration in `PeekTrigger.tsx` (component's own API surface, not a violation) + a different identifier `hasChildren` in `sidebar.tsx`. R-7-ζ shipped comment-hygiene updates to `CalendarConsentPage.tsx` + `EventDetailPage.tsx` (which carried stale "pre-existing CalendarAccountsPage violation" comments perpetuating the label across grep audits) — comments rewritten to positive canonical guidance referencing Path E commit hash + R-7-ζ verification. Architectural pattern locked: cross-arc "pre-existing" labels should be re-verified at investigation time, not perpetuated; closure-stale labels carried across N verification reports produce phantom backlog items. Future arcs should NOT re-flag this as pre-existing.
- **`test_themes_tenant_phase_r25::test_resolve_cannot_request_other_tenant` failure** — **RESOLVED by R-7-δ** (this commit). Pre-existing across 7+ arcs since `3ba9f7d` (R-2.5); inline-flagged in R-5.0.1 / R-5.0.2 / R-5.0.3 / R-5.0.4 / R-6.2a verification reports as "pre-existing" without investigation triggering. R-7-δ investigation classified as class (a) stale test fixture — NOT a security regression; cross-tenant boundary at `themes_tenant.py` verified intact (route signature only declares `mode`; FastAPI discards query-param tenant_id hints; server reads tenant_id from JWT). Root cause: test order coupling — earlier tests seed `manufacturing` vertical_default rows without cleanup; later tests creating fresh manufacturing tenants legitimately inherit leftovers per canonical inheritance order. Fix: autouse PlatformTheme-DELETE fixture in `test_themes_tenant_phase_r25.py` matching canonical pattern at `test_platform_themes_phase2.py:182-186`. Pre-fix: 2 failed / 6 passed; post-fix: 8 passed. Adjacent admin theme tests (21) unchanged. Original entry preserved for cross-arc lineage; future arcs should NOT re-flag this as pre-existing. Architectural pattern locked: pre-existing test failures investigated when first surfaced, not rolled forward; tests sharing DB without per-test cleanup are intrinsically order-coupled; canonical fix is fixture-level, not test-specific workarounds.

### Tech Debt
- `@app.on_event("startup/shutdown")` — deprecated FastAPI pattern; **DEFERRED by R-7-η** (2026-05-11) to a focused FastAPI-version-bump arc where lifespan migration + version bump ship together. 6 sites in `app/main.py` (startup x2, shutdown x4); mechanical migration coupled to FastAPI lifespan API + sync-vs-async scheduler startup ordering + cross-test fixture lifecycle. Current deprecation warnings harmless (FastAPI 0.115.6 still honors `on_event`).
- No query caching — all reads hit PostgreSQL directly
- AIService creates new Anthropic client per call — should use connection pooling
- `StatementRunItem` model added retroactively — verify all service code references it correctly
- `APP_NAME` used as Redis key prefix in `job_queue_service.py` — key shifts if `APP_NAME` env changes


## Design-system conventions (chrome/steel pivot, 2026-07)

- TOKENS ARE THE SINGLE SOURCE. A design change is a token revalue, not a
  component edit. The pivot re-skinned the whole platform by flipping the token
  layer; the only sanctioned component touches were the card primitive, the dead
  brass fallback, and the info badge. If a visual change needs a fourth component
  edited, the token layer is wrong — stop and fix tokens.
- MACHINED DEPTH LIVES IN ONE PRIMITIVE. specular-edge + gradient + shadow is baked
  into ui/card.tsx keyed by an `elevation` prop (recessed/panel/raised) so all
  importers flip together. Never a per-component `.panel-machined` utility.
- DERIVED TOKENS EXPRESS RELATIONSHIPS, NOT LITERALS. gradients = color-mix ratios;
  washes = accent RGB at fixed alphas; rings = steel/0.5 — so they track their
  anchor when it moves. Never freeze a computed pair as a hardcoded value.
- SEMANTIC SWEEPS: CLASSIFY, DON'T PURGE. A severity ramp (red>orange>amber) is ONE
  semantic unit — migrate all tiers together or the most-severe tier keeps the
  banned style. Buckets: decorative→neutral/chrome token; bad-state→fn-negative
  (border/text/pill, never a wash); caution→fn-caution (sparingly). Route through
  tokens, never new literals.
- "REVALUE-ONLY" DISPATCHES FREEZE STRUCTURE. No new tokens, renames, or slots;
  STOP if a value change requires a structural one.

## Ground-truth-first (stale-premise discipline)

Before acting on a remembered problem, verify it's still true. The "r125 staging
heal" was chased for an outage resolved 6 days earlier; staging was serving fine and
r125 already existed — blind-authoring the migration would have forked the alembic
head and caused a real outage. A remembered "X is broken/down/blocked" is a
hypothesis to confirm against live ground truth, not a fact to act on.
Investigation-first is the cheap path, not the ceremonial one.

### Investigation framing — existence-first

Investigation questions ask **what exists, by any mechanism, exhaustively**. They never
ask to confirm an absence or to verify that two named things compose.

- Wrong: "Expect no Plaid integration — confirm." / "Can a schedule-triggered workflow
  invoke `plaid_sync`?"
- Right: "What Plaid integration exists, if any?" / "How is `plaid_sync` scheduled
  today, by any mechanism?"

A dispatch that states its expected answer has primed the investigator toward it, and
the investigator will verify the named mechanism while missing the one actually in use.
Absence is a finding to be established, never a premise to be confirmed.

This applies to remembered state as much as to expectations. A prior session's account
of the repo is a hypothesis. Ground against HEAD.

**Deliverables live in the repository.** Investigation output written to /tmp is
destroyed at the next boot. Findings files, census documents, audits, predictions,
and scope documents go to `docs/investigations/` and are committed —
including read-only investigations that produce no code. A conclusion whose
derivation was deleted becomes a claim with no auditable basis, which is the
condition canon exists to prevent.

### Filing test: where a finding goes

DECISIONS records why a decision was made. It binds nothing, and CLAUDE.md's read order
says it is opened only when a session needs to understand why something is the way it
is. CLAUDE.md binds behavior and is read every session.

Therefore: if a finding changes what a session should DO, it lands in CLAUDE.md.
DECISIONS may reference it. A rule filed where it will not be read is not in force,
however well written.

This is not hypothetical. The persistent-storage rule (investigation deliverables to
docs/investigations/, never /tmp/) was landed in DECISIONS on 2026-05-27 in response to
a /tmp rotation that destroyed ~35,500 words. Four months later a second loss occurred
the same way, under that rule. The rule was sound; its filing location was not.

Corollary: when a rule is violated by someone who would have followed it, check where it
was filed before concluding anything about discipline.

Two method shapes belong here for the same reason — both are things a session must do,
not things it must know:

**The count that measured the wrong unit.** `grep -c` counts matching lines, not
occurrences. The failure is invisible because the result is well-formed and plausible.
Always report the unit measured. Distinct from enumeration-defeated-by-presentation,
where members are hidden rather than the unit being wrong.

**Fixtures modeled on the implementation.** A test that passes because it shares the
code's wrong assumption. Fixtures must be derived from the specification or from real
data, never from reading the implementation being tested.

### Dating discipline in STATE.md

**Every STATE.md line carries its own date. No line inherits a date from a
heading or from a neighbour.**

This binds what a session writes, and it exists to remove a method rather than
to discourage one. A reader who needs a line's date and finds none will infer it
from position, because position is the only signal available; that inference is
reasonable, unavoidable, and wrong whenever the nearest dated line belongs to a
different entry. Asking readers not to infer does not work. Making every line
self-dating removes the inference as an available move.

⚠️ A date inferred from document position is a CONSTRUCTED NAME, and produces
the same class of confident error — see §11.

Discovered September 2026, and the near-miss is the argument: an investigation
into whether the record contained false claims nearly filed one. `STATE.md`
carried "53 of 56 Playwright gates pass" under `## Active deferred items`, a
heading with no date, 634 lines below the nearest dated bullet. Read by
position it appeared to be a September claim made while the channel was dead —
a fabricated integrity finding, inside an integrity investigation. `git log -S`
on the literal string put it ten weeks earlier. The line was STALE, not false.

Measured at the time of writing: 410 top-level bullets, 310 carrying their own
date, 100 without. Most of the hundred sit under headings that at least carry a
date; fifteen sit under `## Active deferred items`, which carries none. That
section is where the false inference happened, and it is the shape to fix first.

`git log -S "<literal string>"` is the enumeration that answers "when was this
written." Use it before attributing any undated line to a period.

### Supersession marking in STATE.md

When an entry supersedes an earlier one, mark the earlier entry at the moment of
supersession. The superseding author is the only person who knows the supersession
occurred; a later reader sees two adjacent entries with no way to tell which is live,
and will read the one nearest to hand.

Mark in place, do not delete: quote or leave the original wording and append
`[SUPERSEDED <date> by <entry or commit>]`. An entry that is corrected rather than
replaced takes `[CORRECTED <date>]` with the original wording preserved. The record of
what was believed is part of the record.

Marking is currently ad hoc — measured 2026-09-04 at roughly 14 markings across 400+
top-level entries, and the 2026-05-26 entry that produced a false claim in a 2026-09-04
investigation was not among them. As with dating discipline, existing unmarked entries
are owed work, enumerable, and are not to be marked retroactively by inference. A
supersession relationship derived from reading rather than from knowing is a constructed
claim.

Corollary: an entry inherited from STATE without checking whether it was superseded is
an inherited claim, not a measured one, and carries the same status as anything else
reported rather than verified.

### Three filing defects, one mechanism

Recorded as an observation, not yet a rule. Within a single day: a binding
constraint filed in the document the read order says to open only for *why*; a
canon addition dispatched to a section number that turned out to be Business
Context; and a document whose structure made a false date inference the natural
reading.

None was a discipline failure. Each was a correct instinct applied to a document
that could not support it — the rule was sound and unread, the reason was right
and the address wrong, the inference was reasonable and the structure silent.

If a fourth appears, the generalisation will have been earned: that document
STRUCTURE is a control surface, and that "people should be more careful" is the
response available when the structure cannot be changed, not the first one to
reach for. Until then this is three instances and a hypothesis.

## Act-side spatial discipline (park, 2026-07)

- SUMMON IS INTENT-SHAPED. Never app-launcher grammar. If a command reads "Open X,"
  it's wrong — surfaces materialize from what the user is doing, not from a menu.
- THE ~3-OBJECT RULE IS THE ACT/DECIDE BOUNDARY. Past ~3 parked tablets, offer a
  Focus. Do not use drag-affordance presence as the boundary test.
- PARK IS SESSION-SCOPED. Anything wanting durable placement gets promoted to a Space
  pin or Focus layout via observe-and-offer — never silently persisted.
- ONE DRAG SYSTEM. Park builds on WidgetChrome's shipped @dnd-kit drag/resize/8px-grid
  machinery and the three-tier mobile cascade. Do not introduce a second window manager.
