# CLAUDE.md — Bridgeable Platform

## 1. Project Overview

**Bridgeable** (getbridgeable.com) is a multi-tenant SaaS business management platform for the death care industry, specifically Wilbert burial vault licensees and their connected funeral homes. The platform manages the full operational lifecycle: funeral order processing, delivery scheduling, inventory, AR/AP, monthly billing, cross-licensee transfers, safety compliance, and financial reporting.

**Company context:**
- **Sunnycrest Precast** — first customer and development partner (vault manufacturer in Auburn, NY); live at `sunnycrest.getbridgeable.com`
- **Able Holdings** — holding company that owns the Bridgeable platform
- **Wilbert** — national franchise network of ~200 burial vault licensees. Bridgeable targets this network as its primary market.
- **Strategic goal:** Demo at the September 2026 Wilbert licensee meeting. Multi-vertical SaaS expansion planned beyond death care.

**4 tenant presets:** `manufacturing` (primary, most features), `funeral_home`, `cemetery`, `crematory`

## 1a. Core UX Philosophy — "Monitor through hubs. Act through the command bar."

**This is the foundational design principle of Bridgeable. Every feature decision must be evaluated against it.**

### The Two Modes

**MODE 1 — MONITORING (Hub Dashboards)**

Monitoring is passive awareness. The platform surfaces what matters without being asked.

- Information comes to the user — they do not hunt for it
- Hub dashboards are role-aware: admins see team metrics, directors see their cases, drivers see their deliveries
- Morning briefing, operations board, compliance hub, case dashboard — all monitoring surfaces
- Widgets are the unit of monitoring
- A user scanning their hub should know everything they need to know for their day without clicking anything

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
- If yes → it belongs in a hub dashboard widget
- It should surface automatically based on role
- The user should see it when they open their hub
- Example: "3 compliance items due this week" → Widget on the manufacturing hub dashboard

**Question 2: Does the user DO this when they have an intent?**
- If yes → it belongs in the command bar as a workflow
- A UI page for it may exist but is not the primary path
- The command bar entry point is designed first
- The page is the fallback for complex cases
- Example: "Create a vault order for Hopkins" → Command bar workflow with natural language overlay → UI order form exists but is the backup

**If a feature is both (needs monitoring AND action):**
- Put a summary widget on the hub
- The widget has a quick-action button
- The button triggers the command bar workflow or navigates to the relevant page
- Example: "3 overdue compliance items [Review →]" → Widget surfaces the problem (monitoring) → [Review →] takes action (acting)

### What This Means in Practice

**A feature is INCOMPLETE if:**
- It can only be accessed by navigating to a page
- It has no command bar workflow or hub widget entry point
- A user needs to know WHERE to go to do it
- It requires filling out a traditional form when natural language could collect the same data

**A feature is COMPLETE if:**
- Monitoring aspects surface in the appropriate hub
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

2. **Never design a monitoring feature as page-only.** Every metric, status, or alert that users need to notice must have a hub widget representation. A page for detail is fine. A page as the only surface is not.

3. **When recommending a new feature, always specify:**
   - Which hub(s) get a widget for this feature
   - What the command bar workflow looks like
   - What natural language inputs it accepts
   - What the UI backup page looks like
   If you cannot specify all four, the feature is not fully designed.

4. **When writing a build prompt, always include:**
   - The hub widget if the feature has a monitoring aspect
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

**Migration r33_company_entity_trigram_indexes:** adds a `CREATE INDEX CONCURRENTLY ix_company_entities_name_trgm USING gin (name gin_trgm_ops)`. Required for the entity resolver's <30ms budget. Phase 1 resolver's `SEARCHABLE_ENTITIES` tuple deliberately NOT extended in Phase 4 — that's a coordinated Phase 5 nav/search unification.

**Performance targets:** p50 < 600ms, p99 < 1200ms. BLOCKING CI gate at `backend/tests/test_nl_creation_latency.py`. Actual (no-AI path on dev hardware): **p50=5.9ms, p99=7.2ms** — 100× headroom on p50 without AI. With Haiku in the loop, typical p50 drifts to ~350-450ms.

**Demo data seeding:** `backend/scripts/seed_nl_demo_data.py --tenant-slug testco` seeds Hopkins Funeral Home + other demo CompanyEntity rows + 3 prior FH cases so the resolver has real pg_trgm candidates. Idempotent; safe to re-run before demos.

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
Tenant settings are stored as a JSONB field on the `companies` table (`settings_json` column), accessed via `company.settings` property and `company.set_setting(key, value)` method. A `tenant_settings` database table also exists (migrations create it) but is orphaned — application code uses `Company.settings_json` exclusively.

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
| `resolver.py` | pg_trgm fuzzy search across 6 entity types (fh_case, sales_order, invoice, contact, product, document) via single UNION ALL per query. Recency weighting 1.0 → 0.3 over 180 days. Tenant isolation mandatory. |
| `retrieval.py` | Orchestrator. OWNS the `QueryResponse` + `ResultItem` shape contract returned by `/api/v1/command-bar/query`. Frontend callers depend on this shape. Bumping it is a coordinated schema change. |

**New endpoint:** `POST /api/v1/command-bar/query` (contract in `backend/app/api/routes/command_bar.py`). Frontend UI at `frontend/src/components/core/CommandBar.tsx` fires it as a 4th parallel fetch alongside the existing `/core/command` + `/workflows/command-bar` + `/core/command-bar/search` calls. Results merge via type-ranked sort in the existing UI pipeline.

**Migration `r31_command_bar_trigram_indexes`:** `CREATE EXTENSION IF NOT EXISTS pg_trgm` + 6 GIN trigram indexes (via `CREATE INDEX CONCURRENTLY` inside `op.get_context().autocommit_block()`) on `fh_cases.deceased_last_name`, `sales_orders.number`, `invoices.number`, `contacts.name`, `products.name`, `documents.title`. Partial clean downgrade; extension left installed.

**Performance targets (p50 < 100 ms, p99 < 300 ms) enforced as BLOCKING CI gate** via `backend/tests/test_command_bar_latency.py`. Actual on dev hardware: **p50 = 5.0 ms, p99 = 6.9 ms** (50-sample sequential mixed-shape workload; seeded tenant with ~24 entities).

**Compose-as-registry refactor:** The old `wf_compose` workflow doesn't exist in code (confirmed via audit — only `wf_create_order` exists). Missing create actions (quote, invoice, contact, product) added to both the backend registry and the frontend `actionRegistry.ts` via `crossVerticalCreateActions`. Case creation stays in `funeralHomeActions.fh_new_arrangement` (FH-preset-only). Typing `new sales order` or `create quote` directly surfaces the create action at the top.

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

## 5. Database

- **~235 tables** (ORM models for all but the orphaned `tenant_settings` table)
- **Current migration head:** `r14_urn_catalog_pdf_fetch`
- **116 migration files** in `backend/alembic/versions/`
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

## 11. Current Build Status

| Metric | Count |
|--------|-------|
| Database tables | ~258 |
| ORM model files | 165+ |
| ORM model exports (`__init__.py`) | 178+ |
| API route files | 105+ |
| API endpoints | 955+ |
| Route modules registered in v1.py | 95+ |
| Frontend routes | 150+ |
| Backend service files | 117+ |
| Migration files | 130 |
| Migration head | `r33_company_entity_trigram_indexes` |
| Documents test suite (D-1 → D-9) | 224 passing |
| Agent jobs (scheduled) | 14 |
| Accounting agents (registered) | 12/12 (complete) |
| Accounting agent tests | 105 passing |
| Urn Sales E2E tests | 39/39 passing |
| Safety Program Generation E2E tests | 12/12 passing |
| Agent jobs (not yet built) | ~30 |
| TypeScript errors | 0 |
| Backend import errors | 0 |
| Migration chain | Single head, no broken links |

## 12. Coding Conventions

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

## 13. Business Context

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

## 14. Recent Changes

- **Polish and Arc Finale — Phase 7 of UI/UX Arc (complete — ARC FINALE):** Phase 7 is the finale of the UI/UX arc. No new primitives, no new feature work — a deliberate pass over every interstitial moment (empty, loading, error, first-run, transition, mobile, accessibility) across the 6 phases shipped before it. 15 sequential polish tasks produced: 3 shared UI primitives (`EmptyState`, `Skeleton`, `InlineError`), 10 per-surface empty state replacements (7 saved view renderers + TasksList + TriagePage caught-up + TriageIndex + CommandBar no-results + SavedViewsIndex + BriefingPage + BriefingCard), 5 skeleton replacements, 1 retry-fetch hook with auto-retry-once (BriefingPage) + Triage action retry that preserves the queue item, a server-side first-run tooltip infrastructure (`User.preferences.onboarding_touches_shown`, cross-device, 5 wired tooltips at command bar / saved view / space switcher / triage / briefing), ARIA labels + aria-live on CommandBar / NLOverlay / TriagePage / BriefingPage, a `?` key context-aware `KeyboardHelpOverlay` mounted at app root, mobile 44px touch-target fixes (triage action palette, flow controls, briefing prefs), `OfflineBanner` + `useOnlineStatus` hook, a global `prefers-reduced-motion` retrofit in `index.css` neutralizing every transition + animation across the 6 prior phases without individual file edits, motion-safe micro-interactions on NL extraction entrance + triage item transitions, WCAG AA contrast verification for all 6 space accents (ALL 6 PASS — zero remediation needed) at `backend/tests/test_arc_accent_contrast.py`, and a focus-ring contrast remediation at `backend/tests/test_arc_focus_ring_contrast.py` + `--ring` darkened from `oklch(0.708 0 0)` to `oklch(0.48 0 0)` in `index.css` so focus indicators pass WCAG 3:1 against white + all 6 accent-light chips. **Telemetry** shipped as a minimal Intelligence-table + in-memory-counter surface at `/bridgeable-admin/telemetry` — platform-admin-gated; shows p50/p99/request-count/error-rate for the 5 arc endpoints (command_bar_query / saved_view_execute / nl_extract / triage_next_item / triage_apply_action) plus Intelligence aggregations over 24h/7d/30d with per-caller-module cost breakdown. Honest expectation-setting: the page explicitly states counters are per-process + clear on restart. `app/services/arc_telemetry.py` provides `record(endpoint, latency_ms, errored)` + `snapshot()`; each of the 5 endpoints wraps its handler in try/finally with the timing record. New backend route `/api/platform/admin/arc-telemetry` reads intelligence_executions aggregates. **Zero new database tables** per approved scope. **Arc documentation finale** (see next three bullets). **Tests**: 8 new contrast + focus-ring tests (all passing), total 288 backend tests across Phase 1-7 regression — no regressions. tsc 0 errors. All 5 BLOCKING latency gates from Phases 1-6 still green. Post-arc backlog documented in `UI_UX_ARC.md` (~45 items across 10 categories). Migration head unchanged at `r35_briefings_table`.

### UI/UX Arc (Phases 1-7) — Complete

Seven-phase arc that rebuilt Bridgeable's user-facing surface as a composable platform. Started April 2026, finished April 2026. Each phase shipped working + tested + documented; no phase was abandoned mid-stream. The arc establishes seven platform primitives + architectural patterns that future features compose rather than duplicate.

**The seven primitives:**
1. **Command bar** (Phase 1) — `POST /api/v1/command-bar/query` platform layer: intent classifier + pg_trgm resolver + registry + retrieval orchestrator. p50=5.0ms/p99=6.9ms. BLOCKING CI gate at 100/300ms.
2. **Saved views** (Phase 2) — storage in `vault_items.metadata_json.saved_view_config`; 7 presentation modes (list, table, kanban, calendar, cards, chart, stat); cross-tenant field masking; visibility levels; seed per role. p50=15.4ms/p99=18.5ms.
3. **Spaces** (Phase 3) — per-user workspace contexts stored in `User.preferences.spaces` (JSONB, no new table); 6 visual accents (all WCAG AA verified in Phase 7); pinned items via server-side pin resolution; `Cmd+[`/`Cmd+]`/`Cmd+Shift+1-5` shortcuts.
4. **Natural Language Creation** (Phase 4) — Fantastical-style live overlay. Pipeline: structured parsers (<5ms) → pg_trgm resolver (<30ms) → Haiku AI fallback. 5 entity types supported (case, event, contact, task, sales_order). p50=5.9ms/p99=7.2ms on no-AI path; ~350ms with Haiku.
5. **Triage Workspace** (Phase 5) — keyboard-driven decision stream. Pluggable 7-component configs (item display, action palette, context panels, embedded actions, flow controls, collaboration, intelligence). 2 shipped queues (task_triage, ss_cert_triage). SS cert parity test asserts triage path produces identical side effects as legacy UI. next_item p50=4.8ms/p99=5.8ms; apply_action p50=9.7ms/p99=13.5ms.
6. **Morning and Evening Briefings** (Phase 6) — AI narrative synthesis over the primitives. First per-user scheduled pattern on platform (every-15-min global sweep + per-user window check). Legacy `briefing_service.py` coexist-not-absorb. Space-aware prompts. p50=28.9ms/p99=32ms.
7. **Polish infrastructure** (Phase 7) — `EmptyState` / `Skeleton` / `InlineError` shared UI primitives + `useRetryableFetch` + `useOnboardingTouch` / `OnboardingTouch` (cross-device) + `KeyboardHelpOverlay` + `OfflineBanner` + `useOnlineStatus` + global `prefers-reduced-motion` retrofit + WCAG contrast verification + minimal telemetry.

**Cross-phase architectural patterns (established by the arc):**
- **In-code platform defaults + vault_item tenant overrides** — used by triage queue configs (Phase 5), saved view seeds (Phase 2), space templates (Phase 3). The pattern: platform-global configs live in Python; tenants override via vault_items that layer on top at read time.
- **Parallel resolver paths** — command bar fires 4 resolvers in parallel (Phase 1-2), NL creation fires structured + resolver + AI in sequence (Phase 4); both compose without blocking the hot path.
- **Registry singletons with side-effect imports** — action registry (Phase 5), triage platform defaults (Phase 5), saved-view entity registry (Phase 2); each imports a `*_defaults.py` at package init to populate the singleton.
- **Role-based seeding with idempotency arrays in `User.preferences`** — `saved_views_seeded_for_roles` (Phase 2), `spaces_seeded_for_roles` (Phase 3), `briefings_seeded_for_roles` (Phase 6), `onboarding_touches_shown` (Phase 7). Same pattern: track what's been seeded per role, skip on re-run.
- **Adapter pattern for registry evolution** — `commandBarQueryAdapter.ts` (Phase 1, interface-only) matured into the Phase 5 `services/actions/` full reshape without breaking backend contract.
- **Coexist-with-legacy over rewrite** — Phase 6 briefings compose the 1,869-line legacy `briefing_service.py` context builders as dependencies rather than rewriting. Phase 5 routes (`/briefings/v2/*`) coexist with legacy `/briefings/briefing`. Post-arc cleanup is deliberate, not mandatory.
- **BLOCKING CI latency gates per primitive** — every phase that shipped an endpoint-hot-path shipped a latency test that fails CI if regressed. 5 gates total across the arc.
- **Honest expectation-setting in admin UIs** — telemetry page documents "counters clear on restart"; scheduler sweep documents "first per-user scheduled pattern" in CLAUDE.md §10 for future features to inherit.

**Performance envelope (production dev-hardware, arc-complete):**

| Endpoint | p50 | p99 | Budget | Headroom p50 |
|---|---|---|---|---|
| command_bar_query | 5.0 ms | 6.9 ms | 100 / 300 ms | 20× |
| saved_view_execute | 15.4 ms | 18.5 ms | 150 / 500 ms | 10× |
| nl_extract (no AI) | 5.9 ms | 7.2 ms | 600 / 1200 ms | 100× |
| triage_next_item | 4.8 ms | 5.8 ms | 100 / 300 ms | 20× |
| triage_apply_action | 9.7 ms | 13.5 ms | 200 / 500 ms | 20× |
| briefing_generate | 28.9 ms | 32.0 ms | 2000 / 5000 ms | 69× |

**Total across the arc**: 7 migrations (r29 notification_safety_merge through r35_briefings_table); 6 new tables (triage_sessions, triage_snoozes, tasks, briefings, plus existing intelligence_executions extended, plus existing vault_items repurposed); 280+ new backend tests; 50+ Playwright specs; 13 Intelligence prompts seeded; ~25 API route modules added; ~8 shared frontend components.

**Docs**: See `UI_UX_ARC.md` at project root for full arc reference + post-arc backlog + September Wilbert demo script.

#### Vertical-Aware User-Facing Text

Any user-facing example, placeholder, or entity-specific language in the arc UI **must** adapt to the current tenant's vertical via `useVerticalExample(category)` (or `getVerticalExample(vertical, category)` for non-React callers). Hardcoded examples like `"new case"` or `"new order"` are a platform bug — they break trust for tenants in other verticals who immediately register the platform doesn't know what business they're in.

The hook (`frontend/src/hooks/useVerticalExample.ts`) is the single source of truth. 8 categories × 4 verticals:

| category | manufacturing | funeral_home | cemetery | crematory |
|---|---|---|---|---|
| `primary_entity` | order | case | burial | cremation |
| `primary_entity_plural` | orders | cases | burials | cremations |
| `primary_detail_term` | order details | case file | burial record | cremation record |
| `secondary_entity` | quote | service | plot | service |
| `new_primary` | new order | new case | new burial | new cremation |
| `new_secondary` | new quote | new service | new plot | new service |
| `workflow_verb` | process | arrange | coordinate | schedule |
| `queue_primary` | invoice | approval | approval | certificate |

Null / unknown verticals fall back to `manufacturing`. Input is case-insensitive and accepts both `funeral_home` and `funeralhome` variants.

**Who must use it:** tooltip bodies, command-bar hints, empty-state messages, keyboard help examples, briefing Intelligence prompts.

**Who doesn't need to:** per-vertical routes (e.g. `fh/pages/DirectionHub.tsx` — FH-only by route), vertical-specific action-registry files (`services/actions/funeral_home.ts` — FH-only by definition), saved view renderer empty states (entity metadata's `display_name` already provides per-entity wording like `"Cases"` / `"Sales Orders"` — no vertical substitution needed).

**Briefing prompts** (`briefing.morning` / `briefing.evening`) receive `vertical` as a Jinja variable and branch on it in a "VERTICAL-APPROPRIATE TERMINOLOGY" block that explicitly tells Claude which terms to use and which to avoid. Verified by `backend/tests/test_briefing_vertical_terminology.py` — asserts the rendered prompt contains correct terminology per vertical and excludes cross-vertical terms.

**Test coverage:** `frontend/src/hooks/useVerticalExample.test.ts` (49 tests — 32 matrix + 6 regression guards + 7 normalization + 4 cross-vertical-leak invariants) + `backend/tests/test_briefing_vertical_terminology.py` (17 tests).

**Prompt-seed behavior** (`scripts/seed_intelligence_phase6.py`): Option A idempotent seeding. Fresh install → v1 active. Exactly 1 version + matching content → no-op. 1 version + differing content → deactivate v1, create v2 active (platform update). Multiple versions exist → skip with warning log (admin customization detected; manual reconciliation via Intelligence admin UI). This preserves admin customizations without separate source-tracking infrastructure.

- **Morning and Evening Briefings — Phase 6 of UI/UX Arc (complete):** AI-generated narrative briefings as workday bookends. Morning orients forward; evening closes backward. Phase 6 is **composition over the primitives** — saved views (Phase 2) provide data, triage queues (Phase 5) provide decision counts, spaces (Phase 3) provide role context, Intelligence synthesizes prose. **Migration `r35_briefings_table`**: new `briefings` table alongside the legacy `employee_briefings` table per the approved coexist-with-legacy strategy. Shape: `id` + `company_id` + `user_id` + `briefing_type` (morning/evening) + `generated_at` + `delivered_at` + `delivery_channels` JSONB + `narrative_text` + `structured_sections` JSONB + `active_space_id/name` + `role_slug` + `generation_context` + metrics (duration_ms, cost_usd, tokens) + `read_at` + `created_at`. Indexes: `ix_briefings_user_type_generated` (user + type + DESC), `ix_briefings_company_generated`, and **partial unique `uq_briefings_user_type_date` on `(user_id, briefing_type, DATE(generated_at AT TIME ZONE 'UTC'))`** — enforces one-per-day per type while allowing morning + evening same day. **Different semantics from `employee_briefings`**: legacy uses `(company_id, user_id, briefing_date)` daily unique (one briefing per user per day total); new table allows morning + evening coexist. Zero collision. `employee_briefings` stays read-only legacy forever. **`backend/app/services/briefings/` package** — 7 modules: `types.py` (Pydantic with `extra="forbid"` — BriefingPreferences + StructuredSections + GeneratedBriefing + BriefingDataContext + MORNING/EVENING_DEFAULT_SECTIONS + DEFAULT_MORNING/EVENING_TIME + BriefingType + BriefingSectionKey + DeliveryChannel literals), `preferences.py` (User.preferences.briefing_preferences namespace + `briefings_seeded_for_roles` idempotency tracker matching Phase 2/3 pattern; `seed_preferences_for_user` translates **legacy `AssistantProfile.disabled_briefing_items` blocklist → Phase 6 `enabled_sections` allowlist** via set subtraction — no data loss, clean forward migration, idempotent per role), `data_sources.py` (**imports legacy context builders verbatim per approved coexist strategy — `_build_funeral_scheduling_context`, `_build_precast_scheduling_context`, `_build_invoicing_ar_context`, `_build_safety_compliance_context`, `_build_executive_context`, `_build_call_summary`, `_build_draft_invoice_context` reused as dependencies; months of customer tuning treated as dependencies not legacy**; also aggregates Phase 5 triage queue_count across every queue visible to the user with seeded 30 sec/item time estimate; Phase 3 active-space lookup from `user.preferences`; VaultItem event_type="event" pull for today + tomorrow; narrative_tone via existing `ai_settings_service`), `generator.py` (fires `briefing.morning` / `briefing.evening` via `intelligence_service.execute` with force_json=True; Pydantic parses response into StructuredSections; deterministic stub fallback on AI failure so user always sees content + can retry), `delivery.py` (channel dispatch — in_app stamps `delivered_at`; email routes through **existing `DeliveryService.send_email_with_template` (Phase D-7) with `template_key="email.briefing.morning"`/`email.briefing.evening"`** which seeds as managed templates in the Phase D-2 template registry — no on-disk email Jinja directory per D-2/D-3 discipline), `scheduler_integration.py` (**first per-user scheduled pattern on the platform** — `sweep_briefings_to_generate` runs every 15 min via `job_briefing_sweep`; for each active user queries prefs, resolves tenant TZ via `Company.timezone` with `America/New_York` fallback via `zoneinfo.ZoneInfo`, checks `_window_fired(local_now, target_time, 15)` + `_already_generated_today` DB check, generates + delivers; per-user failures log + continue via try/except; idempotent across re-runs because the unique index rejects duplicates even if the window check races), `__init__.py` (public exports). **`POST /api/v1/briefings/v2/*` API** — 7 new endpoints coexisting with the legacy `/briefings/briefing` + `/briefings/action-items` + `/briefings/team-config` paths (route coexistence under the same router per approved spec item #3): `GET /v2` (list most-recent-first), `GET /v2/latest?briefing_type=X` (returns latest or null), `GET /v2/preferences` (calls `seed_preferences_for_user` on first access for the legacy-blocklist → allowlist translation), `PATCH /v2/preferences` (Pydantic-validated; 400 on invalid), `POST /v2/generate` (on-demand; **deletes existing same-day-same-type row before creating fresh — explicit regenerate-today semantics, post-arc rename to `/v2/regenerate`**), `GET /v2/{id}` (tenant-scoped 404), `POST /v2/{id}/mark-read` (idempotent read stamp). **Intelligence prompts seeded** via `scripts/seed_intelligence_phase6.py` (idempotent) — `briefing.morning` + `briefing.evening` with Haiku simple route + force_json=True + 2048 max_tokens + 0.4 temperature. Both prompts have Jinja space-awareness branches (`{% if active_space_name == "Arrangement" %}` etc.) producing different section emphasis per space. Legacy `briefing.daily_summary` NOT modified or retired — coexist discipline. **Email templates seeded** via same script as managed DocumentTemplate rows (`email.briefing.morning`, `email.briefing.evening` with `output_format="html"`). **Scheduler wiring**: `app/scheduler.py` adds `job_briefing_sweep()` wrapper + `JOB_REGISTRY["briefing_sweep"]` + `CronTrigger(minute="*/15")` registration alongside existing `workflow_time_based_check` + `platform_incident_dispatcher`. **Seed hook wired** at `user_service.update_user`'s role-change site — alongside Phase 2 saved_views + Phase 3 spaces seeds, now calls `seed_preferences_for_user` (best-effort try/except, never blocks role update). **Frontend**: `types/briefing.ts` (full mirrors — BriefingType, BriefingSectionKey, DeliveryChannel + 11-key section union + MORNING/EVENING_DEFAULT_SECTIONS + QueueSummarySection/FlagSection/PendingDecisionSection typed subshapes), `services/briefing-service.ts` (7-endpoint axios client), `hooks/useBriefing.ts` (latest-briefing fetch + reload; no auto-refresh — scheduler owns backend generation), `pages/briefings/BriefingPage.tsx` (`/briefing` + `/briefing/:id` — narrative card + collapsible structured-sections cards with `QueuesCard` deep-linking to `/triage/:queueId` per Phase 5 integration; Morning/Evening toggle; Regenerate + Mark-read + Preferences buttons; detail page via `:id` param uses `getBriefing`, list page uses `useBriefing`), `components/briefings/BriefingCard.tsx` (new dashboard widget — opt-in mount; truncated narrative + "Read full briefing →" deep-link — does **NOT replace legacy `MorningBriefingCard`** per explicit scope cut), `pages/settings/BriefingPreferences.tsx` (`/settings/briefings` — optimistic-save switches + time picker + channel toggles + section-allowlist buttons for morning + evening; footer copy explaining every-15-min sweep + tenant TZ). **3 new routes** in `App.tsx` — `/briefing`, `/briefing/:id`, `/settings/briefings`. **2 new command-bar actions** in `services/actions/shared.ts` (cross-vertical, no role gate): `navigate_briefing_latest` + `navigate_briefing_preferences`. **Keyboard shortcut `G B` deliberately NOT built** per approved scope cut — users pin `/briefing` to any space via PinStar and reach via `Cmd+Shift+N`. **Legacy coexistence verified**: `MorningBriefingCard` + `morning-briefing-mobile.tsx` + `BriefingSummaryWidget.tsx` untouched, still mounted at `manufacturing-dashboard.tsx:351` + `order-station.tsx:1530`, still consume legacy `/briefings/briefing` + `/briefings/action-items` endpoints. Legacy `briefing.daily_summary` Intelligence prompt stays active + seeded. Legacy context builders imported as dependencies — if someone renames one, `test_briefings_phase6.py::TestLegacyCoexistence::test_legacy_context_builders_still_importable` fails loudly. **BLOCKING SS-cert-parity-equivalent test**: `TestLegacyCoexistence::test_legacy_briefings_endpoint_still_registered` asserts `/briefings/briefing` + `/briefings/action-items` still 200. **BLOCKING CI gate** at `backend/tests/test_briefing_generation_latency.py` — `POST /briefings/v2/generate` p50<2000ms + p99<5000ms (10-sample run after 2 warmups; Intelligence monkey-patched to canned response so we measure orchestration overhead). Actual: **p50=28.9ms / p99=32.0ms — 69× headroom on p50, 156× on p99**. **BLOCKING space-awareness test**: `TestSpaceAwareness::test_active_space_reaches_prompt_variables` parametrizes Arrangement / Administrative / Production and intercepts the Intelligence call; asserts each space's name reaches the prompt `variables["active_space_name"]` — the exact hook the prompt's Jinja branches on. **BLOCKING Call Intelligence test**: `TestDataSources::test_call_intelligence_integration` asserts `overnight_calls` is None when no RingCentralCallLog rows exist, populated with `{total, voicemails, ...}` when a seeded call exists — **preserves legacy `_build_call_summary` path as spec item #8 required**. **Tests**: 25 tests in `test_briefings_phase6.py` across 7 classes — TestPreferences × 4 (defaults, seed idempotent, legacy blocklist translation, update validation), TestDataSources × 3 (collect_morning, queue_summaries aggregated, Call Intelligence present/absent), TestGenerator × 2 (stub fallback on AI failure, valid AI response parsed), TestSpaceAwareness × 4 (parametrized × 3 + persisted context different per space), TestBriefingsV2API × 6 (preferences GET/PATCH, list empty, latest null, generate creates, mark-read, auth required, tenant isolation), TestSweep × 2 (window fire logic, already-generated skip), TestLegacyCoexistence × 4 (legacy endpoints still registered, legacy prompt still seeded, legacy context builders importable, new Phase 6 prompts seeded) + 2 BLOCKING latency gates + 7 Playwright specs in `briefings-phase-6.spec.ts` (briefing_view, briefing_card_dashboard, briefing_preferences, briefing_triage_link_structure, briefing_space_aware_api, briefing_email_delivery_api, briefing_history_list). **Total new this phase: 27 backend + 7 Playwright = 34 tests**. Full Phase 1-6 regression: **280 backend tests passing — no regressions**. Migration head advances `r34 → r35_briefings_table`. **Deferred per spec (post-arc):** voice briefings via TTS, SMS/Slack delivery, cross-tenant briefings (network rollups), briefing AI learning (auto-dropping sections user skips), shared team briefings ("Today's Services" read-mostly view), full migration of all approval-UI referenced in briefings to triage (piecemeal in future phases), briefings for non-tenant users (family portal). **Post-arc cleanup items documented in FEATURE_SESSIONS.md Phase 6 entry:** rename `/briefings/v2/` → cleaner REST; consolidate `employee_briefings` + `briefings` tables; migrate legacy `MorningBriefingCard` consumers (manufacturing-dashboard.tsx, order-station.tsx) to new `BriefingCard`; retire `briefing.daily_summary` prompt once legacy card retires; revisit `briefing_service.py` consolidation once legacy surfaces retire; rename `/v2/generate` → `/v2/regenerate` to signal delete-then-create intent.
- **Triage Workspace + actionRegistry Reshape + Task Infrastructure — Phase 5 of UI/UX Arc (complete):** Phase 5 ships the keyboard-driven triage workspace, two platform-default queues (`task_triage`, `ss_cert_triage`), the task model + API + NL creation config (deferred from Phase 4), and a full reshape of the frontend action registry from ad-hoc arrays to an `ActionRegistryEntry`-native structure split by vertical. **Migration `r34_tasks_and_triage`**: three tables + one trigram index — `tasks` (title / description / assignee / priority [low,normal,high,urgent] / status [open,in_progress,blocked,done,cancelled] / due_date / due_datetime / related_entity_type + id polymorphic link / metadata_json / is_active, indexes `ix_tasks_company_status_assignee`, `ix_tasks_company_due`, partial `ix_tasks_related WHERE related_entity_id IS NOT NULL`), `triage_sessions` (session_id / user_id / queue_id / started_at / ended_at / counters / current_item_id / cursor_meta JSONB), `triage_snoozes` (entity-type-agnostic — user_id / queue_id / entity_type / entity_id / wake_at / reason / woken_at, partial unique `uq_triage_snoozes_active WHERE woken_at IS NULL` prevents double-snooze), and a GIN trigram index on `tasks.title` via `CREATE INDEX CONCURRENTLY` for command-bar fuzzy match. **Task model + service + API**: `app/models/task.py` with TASK_PRIORITIES/TASK_STATUSES tuples; `app/services/task_service.py` with full CRUD + transition state machine in `_ALLOWED_TRANSITIONS` (open→in_progress/blocked/done/cancelled, in_progress→blocked/done/cancelled/open, blocked→in_progress/cancelled/open, done/cancelled terminal — invalid transitions raise `InvalidTransition` → 409); `list_tasks` sorts by priority rank then due_date; 7 endpoints at `/api/v1/tasks/*` (list with filters, create, get, patch, soft-delete via is_active, complete, cancel). **NL creation config extended**: `nl_creation/entity_registry.py` adds `task` with fields title/description/assignee(target="user")/due_date/priority; `nl_creation/entity_resolver.py` adds `resolve_user()` using ILIKE on first/last/email (no trigram index on users yet; noted in DEBT.md); `nl_creation/types.py` `EntityType` literal extended to `"case"|"sales_order"|"event"|"contact"|"task"`; 1 new Intelligence prompt seeded (`nl_creation.extract.task`). Phase 1 command-bar resolver `SEARCHABLE_ENTITIES` gains `task` with `url_template="/tasks/{id}"`. Phase 1 registry adds `create.task` action with aliases `["new task","add task","create task","todo","new todo"]`. **Triage platform** at `app/services/triage/` — seven modules: `types.py` (Pydantic with `extra="forbid"` + `schema_version="1.0"` — TriageQueueConfig + ItemDisplayConfig + ActionConfig [handler + optional playwright_step_id + workflow_id] + ContextPanelConfig [SAVED_VIEW/DOCUMENT_PREVIEW/COMMUNICATION_THREAD/RELATED_ENTITIES/AI_SUMMARY] + EmbeddedActionConfig + SnoozePreset + FlowControlsConfig + CollaborationConfig + IntelligenceConfig + runtime TriageItemSummary/TriageActionResult/TriageSessionSummary + typed errors with http_status), `registry.py` (in-code singleton `_PLATFORM_CONFIGS` via `register_platform_config` — pattern pivot from vault_item-backed because VaultItem.company_id is NOT NULL; per-tenant overrides STILL live as vault_items with `item_type="triage_queue_config"`; `list_all_configs` merges platform defaults with tenant overrides, overrides win; `list_queues_for_user` applies permission + vertical + extension filters), `engine.py` (start_session resumable via `current_item_id` + `cursor_meta.processed_ids`, next_item with snooze filter, apply_action handler→Playwright→workflow pipeline with auto-advance, snooze_item writes partial-unique-index-protected row, queue_count for briefings, sweep_expired_snoozes for scheduler; `_DIRECT_QUERIES` dispatch table — `_dq_task_triage` selects assignee-scoped open/in_progress/blocked tasks ordered by priority rank + due date, `_dq_ss_cert_triage` selects pending_approval certs + joins the related sales_order to derive deceased_name / funeral_home_name at query time matching the legacy route), `action_handlers.py` (module-level HANDLERS dict — `task.complete`, `task.cancel` (stamps `triage_cancellations` in metadata_json), `task.reassign`, **`ss_cert.approve` and `ss_cert.void` call `SocialServiceCertificateService.approve/void` VERBATIM — zero duplication, parity guaranteed by reuse**, generic `skip` and `escalate`), `embedded_actions.py` (`run_playwright_action` wraps existing `PlaywrightScript` registry + `credential_service`, `trigger_workflow_action` wraps `workflow_engine.start_run`), `platform_defaults.py` (two shipped queues — `task_triage` any tenant any role with actions `complete`(Enter)/`reassign`(r)/`snooze`(s)/`cancel`(shift+d), AI questions enabled; `ss_cert_triage` manufacturing vertical + `invoice.approve` permission with actions `approve`(Enter)/`void`(shift+d)/`skip`(n) + document_preview + related_entities panels; both register_platform_config'd at import time), `__init__.py` (side-effect imports platform_defaults BEFORE registry helpers so the singleton is populated by the first import). **API at `/api/v1/triage/*`** (9 endpoints, all user-scoped): GET /queues (visible to user), GET /queues/{id} (full config), GET /queues/{id}/count (for Phase 6 briefings + sidebar badges), POST /queues/{id}/sessions (start — resumable), GET /sessions/{id}, POST /sessions/{id}/next (200 with item OR 204 when exhausted — both measured in latency gate), POST /sessions/{id}/items/{item_id}/action, POST /sessions/{id}/items/{item_id}/snooze (accepts `wake_at` ISO OR `offset_hours` shorthand, 400 if neither), POST /sessions/{id}/end. **Seed script** at `backend/scripts/seed_triage_queues.py` — validator for in-code platform configs + seeds two Intelligence prompts (`triage.task_context_question`, `triage.ss_cert_context_question`) via Haiku simple route with `force_json=True`. **BLOCKING CI gates** at `backend/tests/test_triage_latency.py` — next_item p50<100ms/p99<300ms + apply_action p50<200ms/p99<500ms, 30 samples sequential per operation. Actual on dev hardware: **next_item p50=4.8ms/p99=5.8ms** (20× / 51× headroom), **apply_action p50=9.7ms/p99=13.5ms** (20× / 37× headroom). **BLOCKING SS cert parity test**: 3 tests in `test_task_and_triage.py::TestSSCertTriageParity` assert triage-path approve/void produces identical side effects (status transitions, approved_at/voided_at stamps, approved_by_id/voided_by_id, void_reason preservation) as the legacy `/social-service-certificates` route — all green. **Frontend actionRegistry reshape**: legacy `core/actionRegistry.ts` (944 lines, 61 actions in one flat file) replaced with `services/actions/` package — `types.ts` (rich `ActionRegistryEntry` with permission + required_module + required_extension + handler + playwright_step_id + workflow_id + supports_nl_creation + nl_aliases + keyboard_shortcut), `registry.ts` (singleton + toCommandAction converter + getActionsForVertical/filterActionsByRole/matchLocalActions/getActionsSupportingNLCreation helpers + legacy CommandAction/RecentAction types preserved for render-time compatibility), `shared.ts` (6 cross-vertical create actions including NEW `create_task` + `create_event` with `supports_nl_creation: true`), `manufacturing.ts` (57 mfg actions migrated verbatim), `funeral_home.ts` (9 FH actions — case creation stays FH-only with supports_nl_creation flag), `triage.ts` (3 NEW triage nav entries — index, task queue, ss cert queue), `index.ts` (side-effect registers all entries at module load). **Five call sites migrated** (CommandBar.tsx, SmartPlantCommandBar.tsx, CommandBarProvider.tsx, cmd-digit-shortcuts.ts, commandBarQueryAdapter.ts), `core/actionRegistry.ts` deleted. **detectNLIntent.ts duplication eliminated**: was a hand-maintained ENTITY_PATTERNS table; now derives patterns at call time from `getActionsSupportingNLCreation()` — the `supports_nl_creation` flag is the authoritative toggle, `nl_aliases` is the authoritative alias list, `route` is the authoritative tab-fallback URL. `NLEntityType` extended with `"task"`. **Frontend triage layer**: `types/triage.ts` (full mirrors of backend Pydantic shapes), `services/triage-service.ts` (9-endpoint axios client — `fetchNextItem` returns null on 204), `services/task-service.ts` (7-endpoint client), `contexts/triage-session-context.tsx` (TriageSessionProvider — bootstraps config + session + first item; `advance`/`act`/`snooze` functions; fire-and-forget endSession on unmount), `hooks/useTriageKeyboard.ts` (shortcut binding with shift/alt/meta/ctrl modifier support, ignores input/textarea/contenteditable targets). **UI components** under `components/triage/`: `TriageItemDisplay` (discriminates on `display_component` — task / social_service_certificate / generic), `TriageActionPalette` (renders decision buttons with kbd hints, opens reason modal when `requires_reason: true` with disabled-until-valid Confirm, Snooze handled separately in FlowControls), `TriageContextPanel` (collapsible rail — document_preview hands out the R2 URL; saved_view / communication_thread / related_entities / ai_summary are framework-ready Phase-6 stubs), `TriageFlowControls` (snooze preset buttons firing `onSnooze(offset_hours, label)`). **Pages**: `pages/triage/TriageIndex.tsx` (`/triage` — grid of queue cards with lazy-loaded counts), `pages/triage/TriagePage.tsx` (`/triage/:queueId` — composes the four surfaces inside TriageSessionProvider), `pages/tasks/TasksList.tsx` (`/tasks` — filter by status/priority, inline "Mark done", primary CTA routes to triage), `pages/tasks/TaskCreate.tsx` (`/tasks/new` — backup form; primary path is NL via command bar), `pages/tasks/TaskDetail.tsx` (`/tasks/:taskId` — shows allowed transitions mirroring backend `_ALLOWED_TRANSITIONS`). **5 new routes** in `App.tsx` — `/tasks`, `/tasks/new`, `/tasks/:taskId`, `/triage`, `/triage/:queueId` — static `/new` declared before `/:taskId` to avoid shadowing. **Tests:** 31 tests in `test_task_and_triage.py` (TaskService × 5 — CRUD + transitions + priority sort, Tasks API × 5 — create+list+complete+soft_delete+409+auth, TriageRegistry × 3 — platform defaults loaded + schema_version + permission filter, TriageEngine × 8 — resumable sessions + next_item ordering + apply_action + cancel requires reason + snooze removes from queue + double_snooze skipped + sweep_expired + queue_count, **TestSSCertTriageParity × 3 BLOCKING** — triage_approve identical to legacy + triage_void identical with reason + void without reason errors, TriageAPI × 7 — list_queues + get_queue_config + count + session_flow_end_to_end + snooze offset_hours + 400 on missing time + auth_required) + 2 BLOCKING latency gate tests + 9 Playwright specs in `triage-phase-5.spec.ts` (triage_index_lists_queues, task_triage_basic, task_triage_reject_with_reason, task_triage_snooze, task_triage_keyboard_shortcuts, ss_cert_triage_loads, triage_context_panel_structure, nl_create_task_via_command_bar, task_in_command_bar_results). **Total new this phase: 33 backend + 2 latency gates + 9 Playwright = 44**. Full Phase 1-5 regression: 253 backend tests passing — no regressions (one Phase 4 test adjusted from `{"case","event","contact"}` to `{"case","event","contact","task"}` for the added entity type). Migration head advances `r33 → r34_tasks_and_triage`. **Deferred per spec:** per-tenant triage queue customization UI (admin backup path — backend ready via `upsert_tenant_override`), AI question feature in context panels (Phase 6 alongside briefings), bulk actions + approval chains + rules engine (FlowControls scaffolded but Phase 6+), audit replay (Collaboration scaffolded but post-arc), learning + anomaly detection + prioritization (Intelligence scaffolded but post-arc), full "live preview" of triage queue configs in the admin editor (Phase 7 polish), mobile triage (Phase 7), voice triage (Phase 7). bridgeable-admin portal action registry (`admin-command-actions.ts`) UNTOUCHED per approved plan — separate scope.
- **Natural Language Creation with Live Overlay — Phase 4 of UI/UX Arc (complete):** The Fantastical-style extraction overlay that turns `new case John Smith DOD tonight daughter Mary wants Thursday service Hopkins FH` into a populated case record in 5 seconds. Four entity types supported: `case` + `event` + `contact` via the new entity-centric path + `sales_order`/`quote` via the EXISTING workflow-scoped `NaturalLanguageOverlay` + `wf_create_order` (unchanged — per approved plan, the two overlays coexist). Task deferred to Phase 5 alongside Triage Workspace. **Migration `r33_company_entity_trigram_indexes`**: `CREATE INDEX CONCURRENTLY ix_company_entities_name_trgm ON company_entities USING gin (name gin_trgm_ops)` wrapped in `op.get_context().autocommit_block()`. Required for the entity resolver's <30ms budget resolving CRM records during live extraction. Phase 1 resolver `SEARCHABLE_ENTITIES` tuple NOT extended — that's a coordinated Phase 5 cleanup. **Backend package** at `backend/app/services/nl_creation/`: `types.py` (typed dataclasses ExtractionRequest / FieldExtraction / ExtractionResult / NLEntityConfig / FieldExtractor + 4 error classes + ExtractionSource literal + SpaceDefaults dict alias), `structured_parsers.py` (pure functions <5ms each: parse_date handles ISO / US / written-month / "tonight" / weekday names / relative words; parse_time handles 12h AM/PM / 24h / noon / morning; parse_datetime composes date+time; parse_phone normalizes to E.164; parse_email lowercases; parse_currency requires $/USD/dollars flag to avoid phone-number collisions; parse_quantity with unit; parse_name with prefix/suffix stripping), `entity_resolver.py` (resolve_company_entity via pg_trgm similarity with boolean-flag filter whitelist for safety; resolve_contact + resolve_fh_case reuse pattern; one-call `resolve(target, query, user, ...)` dispatcher), `ai_extraction.py` (renders field_descriptions / structured_extractions / tenant_context / space_context blocks; calls intelligence_service.execute with prompt_key from entity config; parses `{"extractions": [...]}` OR legacy-key shape; catches all exceptions + returns empty on failure so extract endpoint never crashes), `entity_registry.py` (4 entity configs — case, event, contact + fh_case alias → case; case's date fields are DELIBERATELY AI-only since a single sentence can contain multiple dates for different fields ("DOD tonight" vs "service Thursday") and a scalar parser would mis-assign; event's datetime parser runs since single-datetime-per-event is the norm; space_defaults dict with lowercase-space-name keys for explicit per-space overrides; creator_callable per entity — `_create_case` uses `case_service.create_case` + populates CaseDeceased/CaseService/CaseInformant satellites + stamps a `note_type="nl_creation"` audit note, `_create_event` via `create_vault_item(item_type="event")`, `_create_contact` via Contact model + requires resolved master_company_id), `extractor.py` (orchestration: structured parsers first, then capitalized-token candidate scan against entity-typed fields for resolver, then AI fallback IF any required field still missing, merge with prior_extractions preserving user edits by higher confidence, apply space_defaults last, compute missing_required), `__init__.py` (public exports). **Intelligence prompts** seeded idempotently by `backend/scripts/seed_intelligence_phase4.py` — 3 new platform-global prompts (`nl_creation.extract.case`, `nl_creation.extract.event`, `nl_creation.extract.contact`), each with Haiku (`simple` route), force_json=True, response_schema enforcing `{"extractions": [{"field_key", "value", "confidence"}]}`, variable schema flat `{name: {type, required}}` shape matching `prompt_renderer.validate_variables`. Case prompt content copied from `scribe.extract_first_call` conceptually but INDEPENDENT — diverges from day one per approved plan. **Intent extension**: `intent.py` adds `detect_create_with_nl(query) → (entity_type, nl_content) | None` — additive, does NOT change the `Intent` Literal set. Two-mode matcher: exact-alias prefix (with both verb-inclusive and verb-stripped alias forms — "new case" AND "case" both match "new case John Smith") and fuzzy fallback via existing `is_create_entity_query`. 3-char minimum on nl_content prevents single-word empty-invocation false positives. New `create.event` action registered in Phase 1 registry (previously missing — audit gap). **API at `/api/v1/nl-creation/*`** (3 endpoints, all user-scoped): `POST /extract` (hot path, debounced 300ms client-side, accepts entity_type + natural_language + active_space_id + prior_extractions), `POST /create` (materializes via creator_callable, honors required_permission gate, 400 on validation errors), `GET /entity-types` (registry dump for UI — filtered by user's permissions). **BLOCKING CI gate** at `backend/tests/test_nl_creation_latency.py` — 30-sample mixed-shape across 3 entity types, p50 < 600ms + p99 < 1200ms. Actual (AI-disabled path on dev): **p50=5.9ms, p99=7.2ms** — 100× headroom. With Haiku in the loop, typical p50 drifts to ~350-450ms (well inside budget). **Frontend:** `types/nl-creation.ts` (full mirrors), `services/nl-creation-service.ts` (3 endpoints), `hooks/useNLExtraction.ts` (300ms debounce — wider than Phase 1's command-bar debounce to amortize AI calls, AbortController cancellation, manual-override state that survives re-extractions, `create()` materializes via API), `components/nl-creation/NLOverlay.tsx` (Fantastical-style panel under the command bar input — header with entity display_name + extraction_ms telemetry, captured fields with checkmark/alert icons, low-confidence amber left border, resolved-entity pills via `EntityPill`, missing-required section, Enter/Tab/Esc keyboard hints footer), `NLField.tsx` (per-row display — confidence-aware styling), `NLCreationMode.tsx` (orchestration wrapper — useNavigate + keyboard listeners on window for Enter/Tab/Esc, entity-types cache in module scope so repeated mount/unmount doesn't refetch), `detectNLIntent.ts` (client-side mirror of backend detector for instant UX response — no server round-trip to decide overlay activation). **Contact create page** at `pages/crm/new-contact.tsx` mounted at `/vault/crm/contacts/new` — fills the Phase 1 register-but-no-route gap. Form pre-fills deterministically from `?nl=<input>` query param (regex-extracts email, phone, capitalized tokens as name, `at <Company>` segment as company picker seed). **Command bar integration**: `CommandBar.tsx` adds `activeNLEntity` state, useEffect watching `query` via `detectNLIntent()`, renders `<NLCreationMode>` instead of the standard results list when matched. Suppresses AI-mode + results-list rendering during NL mode. Coexists with existing `activeNLWorkflow` state (workflow-backed entities) without interfering. Voice input reuses Phase 1's `useVoiceInput` — transcript flows into the same command-bar text field and the detector/overlay fire as if typed. **Demo seed** at `backend/scripts/seed_nl_demo_data.py --tenant-slug testco` — idempotent, seeds Hopkins Funeral Home / Riverside Funeral Home / Whitney Funeral Home / Oakwood Memorial / St. Mary's Church / Acme Manufacturing + 3 prior FH cases (Andersen / Martinez / Nakamura families) so the resolver has realistic fuzzy-match candidates for the Wilbert demo. **Tests:** 53 structured-parser unit tests in `test_nl_structured_parsers.py` (date × 12, time × 8, datetime × 3, phone × 5, email × 4, currency × 6, quantity × 4, name × 6, performance × 5), 25 integration in `test_nl_creation_backend.py` (entity registry × 5, company-entity resolver × 5 including tenant isolation + filter whitelist safety + empty query, intent detector × 6 for all 4 entity types + empty + too-short content, extractor orchestration × 3 including Hopkins-FH-resolution without AI, API × 6 for list/extract/create/auth/404/validation), 1 BLOCKING latency gate in `test_nl_creation_latency.py`, 8 Playwright specs in `nl-creation-phase-4.spec.ts` (nl_create_case demo sentence, nl_create_event, nl_create_contact, nl_extraction_live_update, nl_tab_to_form via `?nl=` param, nl_escape_cancels, nl_entity_resolution_pill conditional on seed, nl_api_extract_smoke contract). **79 new backend tests + 8 Playwright** (273 total backend across Phase 1-4 — no regressions). Migration head advances `r32 → r33`.
- **Spaces — Phase 3 of UI/UX Arc (complete):** Per-user workspace contexts layered on top of the vertical navigation. Each Space has a name, icon, six-accent visual personality, and a set of pinned items (saved views + nav routes). Phase 3 operationalizes the FH two-hub pattern (Arrangement = Funeral Direction hub; Administrative = Business Management hub) as seeded spaces rather than nav config — same architectural principle, better UX. **No new table, no migration.** Spaces live in `User.preferences.spaces` (JSONB array alongside Phase 2's `saved_views_seeded_for_roles`); r32 from Phase 2 already has the column. Migration head stays `r32_saved_view_indexes`. **Backend package** at `backend/app/services/spaces/`: `types.py` (typed dataclasses SpaceConfig / PinConfig / ResolvedSpace / ResolvedPin, MAX_SPACES_PER_USER=5, MAX_PINS_PER_SPACE=20, 6 accent literals, SpaceError subclasses), `registry.py` (role-based `SpaceTemplate` seeds keyed by `(vertical, role_slug)` — 6 pairs shipped for funeral_home director/admin/office, manufacturing production/office/admin — plus `FALLBACK_TEMPLATE` "General" for unknown roles, `NAV_LABEL_TABLE` for nav-item pin label resolution), `crud.py` (10 service functions — create/get/update/delete/reorder spaces + add/remove/reorder pins + set_active_space — each commits via `flag_modified(user, "preferences")`; first space auto-defaults; promoting a new default demotes the old; deleting the default promotes the first remaining; active_space_id cleared on delete of active space; **server-side pin resolution via `_resolve_pin` denormalizes saved_view_title / nav label** so clients render from flat data with zero N+1), `seed.py` (idempotent via `preferences.spaces_seeded_for_roles` — running twice creates zero new spaces; template additions after seed do NOT backfill; skip-if-name-exists defense-in-depth against array-drift; nav-item pins store the href as `target_id`, saved-view pins store the seed_key as `target_seed_key` + `target_id=""` placeholder — resolved at read time). **Seed hooked** at `auth_service.register_user` (new user) + `user_service.update_user` at the `role_id in changes` branch (role change) — the role-change site ALSO re-calls Phase 2's `saved_views.seed.seed_for_user` so a user promoted from office to director picks up both new spaces AND new saved views. Both calls are best-effort with try/except + logging; a seed failure never blocks user ops. Explicit two-line pattern at the hook site (not a `reseed_all` helper) so future phases attach additional seeds transparently. **API at `/api/v1/spaces/*`** (10 endpoints, all user-scoped): `GET /` (list with resolved pins + active_space_id), `POST /` (create), `GET /{id}`, `PATCH /{id}` (partial — name/icon/accent/is_default/density), `DELETE /{id}`, `POST /{id}/activate`, `POST /reorder`, `POST /{id}/pins` (idempotent — same target on existing pin returns existing pin), `DELETE /{id}/pins/{pin_id}`, `POST /{id}/pins/reorder`. Cross-user 404 isolation — a user can't read/mutate another user's spaces. 5-space cap enforced at the service layer, translates to 400 with readable detail at the API layer. **Command bar integration** (additive, no schema bump): `QueryContext` gains `active_space_id: str | None`; frontend `CommandBar.tsx` threads it from `useActiveSpaceId()`. Two behaviors added to the orchestrator at `retrieval.py` — (1) synthesized space-switch results (no registry entry; read from `user.preferences.spaces` at query time, exact name → score 1.4, 2+-char prefix → 1.1, suppresses the user's current active space), (2) pin boost (`_WEIGHT_ACTIVE_SPACE_PIN_BOOST=1.25` applied in-place to `ResultItem.score` for any result whose `url` or `id` matches a pin's `target_id` in the active space). Space-switch URLs have the shape `/?__switch_space=<space_id>`; the command-bar dispatcher intercepts the param and calls `SpaceContext.switchSpace` rather than navigating — legacy clients fall through to a harmless `/` navigation. **Frontend:** `types/spaces.ts` (full mirrors + `ACCENT_CSS_VARS` × 6 accent palette + `applyAccentVars` helper that sets `--space-accent` / `--space-accent-light` / `--space-accent-foreground` on `documentElement`; never touches `--preset-accent`). `services/spaces-service.ts` (10-endpoint axios client, no caching). `contexts/space-context.tsx` (SpaceProvider with fetch-on-mount, optimistic mutations with server reconciliation, `activeSpace` memo, `isPinned` / `togglePinInActiveSpace` convenience helpers; `useActiveSpaceId` null-safe hook for callers outside the provider scope). Mounted in `App.tsx` inside `PresetThemeProvider` on the tenant branch — `BridgeableAdminApp` / platform admin path untouched. **UI components** at `components/spaces/`: `SpaceSwitcher` (top-nav dropdown adjacent to NotificationDropdown — active space name + icon + keyboard hint; dropdown lists all spaces with `⌘⇧N` hint labels + "New space…" + "Edit current space…"; installs keyboard listeners for `Cmd+[` / `Cmd+]` / `Cmd+Shift+1..5`, skips digit shortcuts when focus is in input/textarea), `PinnedSection` (renders ABOVE `navigation.sections` in the existing sidebar — zero changes to `navigation-service.ts`; HTML5 drag-and-drop for pin reorder; hover-to-reveal X for unpin; `data-testid`/`data-pin-id`/`data-unavailable` attributes for Playwright assertions; unavailable pins render grayed-out + non-navigable with a tooltip hinting the cause), `PinStar` (one-click pin toggle — renders on SavedViewPage header; null-renders when no active space; de-duped server-side so rapid clicks don't multi-pin), `NewSpaceDialog` + `SpaceEditorDialog` (shadcn Dialog — name, accent, density, is_default toggle, delete with confirm). **Keyboard shortcut audit:** Phase 3 shortcuts (`Cmd+[`, `Cmd+]`, `Cmd+Shift+1..5`) don't collide with Phase 1's Option/Alt+1..5 or Cmd+1..5 (command-bar result shortcuts — only active when bar is open). Different modifier combos + active conditions = clean. **Tests:** 36 unit tests in `test_spaces_unit.py` (registry × 7 — templates exist, FH director has Arrangement default, unknown pair returns fallback, nav label lookup; seed × 7 — FH director seeds 3 spaces, records role, idempotent, sets active_space_id, unknown role fallback, saved-view seed-key resolution integration + unavailable when Phase 2 didn't seed; CRUD × 12 — create/update/delete/reorder/activate + 5-cap + default-reassignment + cross-user 404; pins × 8 — add/remove/reorder + idempotent + label_override + unknown href fallback + unknown type rejected; mfg admin seeds Production+Sales+Ownership × 1). 19 integration tests in `test_spaces_api.py` (13 API — list/create/get/cross-user-404/update/delete/activate/reorder/5-cap/pin-add/pin-idempotent/pin-remove/pin-reorder/auth-required; 6 command bar — space-switch on name match, current active excluded, pinned nav item boosted, active_space_id schema accepted, prefix match synthesizes, single-char suppresses). 9 Playwright specs in `spaces-phase-3.spec.ts` (keyboard shortcuts, picker, accent transition, pin saved view, pin nav item, pin reorder via API, create/edit/delete lifecycle, five-space cap, pin target deleted → unavailable). **55 new backend tests + 9 Playwright**, Phase 1+2 regression (139 tests) all green. **Deferred:** mobile space switching (Phase 7), shared team spaces (post-arc), intelligence-suggested switches (post-arc), workflow handoff between spaces (post-arc), space-scoped notifications (post-arc), space-scoped briefings (Phase 6 inherits), custom accent picker (Phase 7 polish), cross-tenant space sharing (post-arc), space export/import (post-arc). Migration head: `r32_saved_view_indexes` (unchanged).
- **Saved Views as Universal Primitive — Phase 2 of UI/UX Arc (complete):** Saved Views become the rendering engine for every list, kanban, calendar, table, card grid, chart, and dashboard surface on the platform. Storage reuses `vault_items` with `item_type='saved_view'` and `metadata_json.saved_view_config` as the ONLY canonical location — no dedicated table, no schema changes to the VaultItem shape. **Migration `r32_saved_view_indexes`**: three performance + one schema change — (1) GIN trigram `ix_vault_items_title_trgm` on `vault_items.title` for command-bar fuzzy match, (2) partial B-tree `ix_vault_items_saved_view_owner` on `(company_id, created_by) WHERE item_type='saved_view' AND is_active=true` for the hot-path list query, (3) `users.preferences JSONB DEFAULT '{}'` for seed idempotency tracking, (4) widened `vault_items.source_entity_id` from `String(36)` → `String(128)` so semantic seed keys like `saved_view_seed:director:my_active_cases` fit (backward-compatible — UUIDs still fit). CONCURRENTLY indexes wrapped in `op.get_context().autocommit_block()`. **Backend package** at `backend/app/services/saved_views/`: `types.py` (typed dataclasses with `to_dict`/`from_dict` round-trips for every class: EntityType, FilterOperator, SortDirection, PresentationMode, ChartType, Aggregation, 4-level Visibility, Filter, Sort, Grouping, AggregationSpec, Query, per-mode configs TableConfig/CardConfig/KanbanConfig/CalendarConfig/ChartConfig/StatConfig, Presentation, CrossTenantFieldVisibility, Permissions, SavedViewConfig, SavedView, SavedViewResult), `registry.py` (7 entity types seeded — fh_case, sales_order, invoice, contact, product, document, vault_item — each with `available_fields`, `default_sort`, `default_columns`, `icon`, `navigate_url_template`, per-entity `query_builder` that emits tenant-isolated SQLAlchemy queries, and `row_serializer` for result shape), `executor.py` (`execute(db, *, config, caller_company_id, owner_company_id) → SavedViewResult` with 12 filter operators dispatched in `_apply_filters`, sort, kanban grouping buckets, chart/stat aggregations, cross-tenant masking via `MASK_SENTINEL="__MASKED__"` applied per-row when `caller_company_id != owner_company_id` against a whitelist in `permissions.cross_tenant_field_visibility.per_tenant_fields`; DEFAULT_LIMIT=500, HARD_CEILING=5000, `ExecutorError` for malformed config), `crud.py` (create/get/list-for-user/update/delete-soft/duplicate with 4-level visibility enforcement — `private`, `role_shared`, `user_shared`, `tenant_public` — returns typed `SavedView` dataclasses parsed from `metadata_json`, never leaks raw VaultItem; owner_user_id forced server-side on create/duplicate; update/delete owner-only via `SavedViewPermissionDenied`), `seed.py` (`seed_for_user(db, user)` iterates user's current roles, seeds any not in `preferences.saved_views_seeded_for_roles` array; templates keyed by `(vertical, role_slug)` with factories taking role_slug; idempotency via preferences-array primary + `source_entity_id` defense-in-depth; 6 templates across manufacturing/funeral_home × admin/office/production/director roles including the FH director "My active cases" + "This week's services" calendar, office "Outstanding invoices" table, production "Active pours" kanban), `__init__.py` (public exports). Seed wired into `auth_service.register_user` post-commit, wrapped in try/except logging.exception — seed failures never block user creation. **Command bar integration:** new `saved_views_resolver.py` uses pg_trgm similarity on `vault_items.title` with post-query Python visibility filter through `crud._can_user_see`; runs PARALLEL to the entity resolver in `retrieval.py` (NOT folded into the UNION ALL — preserves Phase 1's sub-10ms latency budget). New `ResultType="saved_view"` in the backend response schema; frontend adapter maps to `CommandAction.type="VIEW"`, slot 5 in TYPE_RANK between RECORD (3) and NAV (6). Live queries, no caching — respects create/update/delete semantics across tabs. **API at `/api/v1/saved-views/*`** (8 endpoints, all tenant-scoped via `get_current_user`): `GET /` (list visible to user, optional `entity_type` filter), `POST /` (create, 201, forces owner to caller), `GET /entity-types` (registry dump for builder UI), `GET /{view_id}`, `PATCH /{view_id}` (owner-only, partial update), `DELETE /{view_id}` (soft-delete via `is_active=false`, returns 200 body rather than 204 — matches codebase pattern), `POST /{view_id}/duplicate` (always creates a PRIVATE copy owned by caller), `POST /{view_id}/execute` (hot path, 150ms-p50 / 500ms-p99 budget). **BLOCKING CI gate** at `backend/tests/test_saved_view_execute_latency.py` — 50-sample sequential across 4 view shapes (list, table, kanban, chart) over 1,000 seeded sales_orders. Actual on dev hardware: **p50=15.4ms, p99=18.5ms** — 10× headroom on p50, 27× on p99. **Frontend:** `frontend/src/types/saved-views.ts` (full mirrors of backend dataclasses + `MASK_SENTINEL` export), `frontend/src/services/saved-views-service.ts` (8-endpoint axios client, no caching), `frontend/src/components/saved-views/SavedViewRenderer.tsx` (dispatches to 7 mode renderers, displays cross-tenant masking banner listing masked fields, chart lazy-loaded via `React.lazy` + `Suspense` so recharts chunk stays out of the initial bundle). **Seven mode renderers** under `components/saved-views/renderers/`: `ListRenderer` (stacked rows with title+subtitle, auto-picked title field), `TableRenderer` (typed-format columns via shared `formatters.ts`), `KanbanRenderer` (column-per-group from `result.groups`, card-per-row with title+meta fields), `CalendarRenderer` (DIY month grid with prev/next/today navigation, 6-row by 7-col day cells, events tile with "+N more" overflow — escalation to react-big-calendar deferred), `CardsRenderer` (responsive grid with title/subtitle/body fields and optional image_field thumbnail), `ChartRenderer` (recharts 3.8.1, 5 chart types — bar/line/area/pie/donut — resolves y-axis aggregation key `{func}_{field}`, default-exports for `React.lazy`), `StatRenderer` (single scalar reading from `result.aggregations[{agg}_{field}]` with fallback to `rows[0][metric]`, record-count subtext). Shared `formatters.ts` handles currency/number/date/datetime/boolean/enum/masked value formatting — every renderer funnels cells through one place. `components/saved-views/SavedViewWidget.tsx` (hub/dashboard embed; per-session entity-registry cache so 20 widgets don't refetch; `preloadedView` prop skips the getSavedView fetch when the parent already has the view data). **Pages + routes:** `pages/saved-views/SavedViewsIndex.tsx` (grouped cards — Mine / Shared with me / Available to everyone — entity-type filter, "New view" CTA), `SavedViewPage.tsx` (detail + owner-only edit/duplicate/delete buttons with `window.confirm` for delete), `SavedViewCreatePage.tsx` (shared component used for both `/new` and `/:viewId/edit` modes; left column = basics + query builder, right column = presentation + visibility). `App.tsx` registers 4 routes — order matters (`/saved-views/new` and `/:viewId/edit` BEFORE `/:viewId` so static segments aren't shadowed by the param route). **Builder** under `components/saved-views/builder/`: `FilterEditor.tsx` (per-row field dropdown + operator dropdown across all 12 operators + value input with operator-aware parsing — single-value / multi-value comma-split / range / nullary), `SortEditor.tsx` (ordered list; first sort primary, tiebreakers after), `PresentationSelector.tsx` (mode dropdown swaps mode-specific sub-forms — table columns input, kanban group-by + card-title pair, calendar date + label pair, cards title + body-fields, chart type + x/y axes + aggregation, stat metric + aggregation). Live preview deferred as post-arc polish — users save then land on detail. **Production board rebuild:** `pages/production/ProductionBoardDashboard.tsx` composes `SavedViewWidget` instances filtered to production-role seeded views (matches against the seeded template titles + `vault_item` filter with `item_type=production_record`). `/production` now renders the dashboard; the legacy bespoke board stays available at `/production/legacy` for one release until Playwright parity verifies the replacement, after which `production-board.tsx` gets deleted and the legacy route removed. `/api/v1/work-orders/production-board` endpoint is preserved as the data source until the migration completes. **Recharts 3.8.1** added to frontend dependencies. **Tests:** 9 registry unit tests in `test_saved_views_registry.py` (default seed of 7 entities, field types, field lookup known/unknown, registration replace, reset re-seeds) + 29 integration tests in `test_saved_views.py` (CRUD, executor filters/sort/group/aggregation, tenant isolation, cross-tenant masking whitelist + defense-in-depth no-whitelist, same-tenant no masking, seed for new FH director + idempotency + records role in preferences, API entity-types, API create+get, API update, API delete+404, API execute, API auth_required, command-bar saved-view result shape + live-query semantics + deleted stops appearing) + 1 BLOCKING latency gate + 7 Playwright specs in `saved-views-phase-2.spec.ts` (create_saved_view_case_list, switch_presentation_mode list→table, kanban_view_grouping status, calendar_view_rendering month-grid, saved_view_in_command_bar VIEW-type result, production_board_saved_views /production is dashboard, cross_tenant_masking_backend_only API contract). **Total new this phase: 46 passing** (38 backend + 1 latency gate + 7 Playwright). Migration head: `r32_saved_view_indexes`. DEBT notes: live preview deferred, seed backfill on template additions requires manual script or role-version bump, `production-board.tsx` deletion gated on Playwright staging run.
- **Command Bar Platform Layer — Phase 1 of UI/UX Arc (complete):** Establishes the backend platform-layer architecture — registry, intent classifier, pg_trgm-backed entity resolver, retrieval orchestrator — and ships the new canonical endpoint `POST /api/v1/command-bar/query`. Frontend's production command bar (`core/CommandBar.tsx`, 1091 lines) continues to own UI + voice + shortcuts, now fires the new endpoint as a 4th parallel fetch alongside the legacy `/core/command`, `/workflows/command-bar`, `/core/command-bar/search` paths. Migration head advances to `r31_command_bar_trigram_indexes` (pg_trgm extension + 6 GIN trigram indexes on the search columns via CREATE INDEX CONCURRENTLY). **Audit finding:** the existing command bar is substantial — 5,900 lines across 12 files — so Phase 1 went **refactor-in-place** rather than greenfield rebuild. Two legacy files inspected: `ai/CommandBar.tsx` (250 lines, unused prototype) deleted; `ai-command-bar.tsx` (93 lines) KEPT because `products.tsx` actively imports it as a page-specific AI search bar (the audit agent incorrectly flagged it as unused; restored after discovery). `wf_compose` workflow confirmed non-existent in code — only `wf_create_order` ships, so "remove Compose menu" requirement was a no-op. Added backend registry seeds for 17 navigate actions (dashboard, ops board, financials, AR/AP aging, P&L, invoices, SOs, quoting, compliance, pricing, KB, vault + 4 vault services, accounting admin) + 6 create actions (sales_order, quote, case, invoice, contact, product). Frontend `actionRegistry.ts` extended with `crossVerticalCreateActions` for quote/invoice/contact/product (case creation stays in `funeralHomeActions.fh_new_arrangement`). Frontend `navigation-service.ts` NavItem extended with optional `aliases` field + `getAllNavItemsFlat()` helper. **Performance:** BLOCKING CI gate at `backend/tests/test_command_bar_latency.py` asserts p50 ≤ 100 ms and p99 ≤ 300 ms across 50 sequential mixed-shape queries. Actual on dev hardware: **p50 = 5.0 ms, p99 = 6.9 ms** — 14× headroom on p50, 43× on p99. **Tests:** 22 registry unit + 40 intent unit + 15 resolver integration (with real pg_trgm) + 13 retrieval integration + 9 API end-to-end = **99 new Phase-1 tests passing**; 8 regression tests for `/ai-command/*` (unambiguous routes after identifying pre-existing route-collision between `ai.py` and `ai_command.py` both at `/command`); 9 Playwright specs at `frontend/tests/e2e/command-bar-phase-1.spec.ts` covering Cmd+K open/close, page navigation, case + SO search, "new sales order" create, numbered shortcut (Alt+1) without tab-switch, typo tolerance, API response-shape contract. **Pre-existing route collision discovered:** `/api/v1/ai/command` has two handlers (ai.py and ai_command.py) — ai.py wins on resolution order, making the ai_command.py handler unreachable via that path. Documented in CLAUDE.md §4 "Command Bar Migration Tracking"; full resolution deferred to the deprecated-endpoint removal sweep. **Deferred to later phases:** natural language creation with live overlay (Phase 4), saved view results (Phase 2), space-scoped ranking (Phase 3), triage mode (Phase 5), voice-in-command-bar (Phase 7 polish — existing voice input still works), mobile command bar (Phase 7 polish), full actionRegistry.ts frontend reshape (Phase 5 alongside Triage Workspace — Phase 1 uses a thin interface-only adapter). Migration head: `r31_command_bar_trigram_indexes`.
- **Bridgeable Vault — Phase V-1h Documentation Consolidation (complete):** V-1 arc closes. Pure documentation phase — no code, no tests, no schema changes. Migration head unchanged at `r30_delivery_caller_vault_item`. **New docs:** (1) `backend/docs/vault_architecture.md` (947 lines) — internal architecture reference covering the full Vault concept, service model, widget framework, cross-cutting capabilities, integration seams for adding a new service, and the migration-head history linking every Vault-adjacent migration (r16 Intelligence → r30 delivery caller vault item). (2) `backend/docs/vault_README.md` (123 lines) — developer entry point, key files table, 5-service summary, quick links, common tasks, test inventory. (3) Five per-service user guides at `backend/docs/vault/*.md` (total 1178 lines) — one per registered service, admin-facing "how do I use this" content: documents.md (216), intelligence.md (210), crm.md (201), notifications.md (230), accounting.md (321). Each guide covers what the service does, where it lives in nav, key admin surfaces, common workflows with step-by-step instructions, permission model, related services, known limitations with DEBT.md links. **Updated docs:** CLAUDE.md §4 Architecture gains a "Bridgeable Vault" subsection with the 5-service descriptor table + V-1 timeline summary + doc pointers + V-2 candidate list. `docs/BRIDGEABLE_MASTER_REFERENCE.md` Part 3 Architecture gets a new §3.14 rolling up V-1 completion (timeline, services delivered, cumulative stats, architectural wins, deferred V-2 items). No changes to DEBT.md or BUGS.md — V-1h doesn't introduce or resolve debt/bugs, just documents what exists. **Cross-reference pass** verified every `[link](path.md)` in the new docs resolves to an existing file; every "see X" reference points at a real destination; terminology consistent (widget definition vs widget spec, service descriptor vs service entry — canonical forms chosen: "widget definition" and "service descriptor"). **V-1 arc complete.** 5 services, 10 overview widgets, 109+ Vault backend tests, 4 V-1 migrations applied (r29, r30 — V-1a/b/c/e/g/h were code-only), documentation consolidated. Next build decisions are demand-driven: September runway polish, HR/Payroll module scoping, Smart Plant @ Sunnycrest pilot, V-2 Vault work (Calendar + Reminders + CRM true absorption + Vault Sharing generalization) — all evaluated post-September against actual customer signal.
- **Bridgeable Vault — Phase V-1f+g VaultItem Dual-Write Hygiene (complete):** Three audit observations closed in one phase: (1) Quote writes VaultItem on create + updates on convert/status-change, (2) `document_deliveries` gains a `caller_vault_item_id` column for polymorphic delivery attribution, (3) Quoting Hub surfaces a deep-link to the quote template editor. JE dual-write investigation concluded **Case A** — JEs don't write VaultItem anywhere in the codebase today; a lint-style regression guard prevents silent slippage, and a future coverage decision is deferred to DEBT.md. **Migration `r30_delivery_caller_vault_item`**: adds `document_deliveries.caller_vault_item_id` (String(36) FK → `vault_items.id` ON DELETE SET NULL, nullable) with a partial unique-adjacent index `ix_document_deliveries_caller_vault_item_id WHERE caller_vault_item_id IS NOT NULL` — keeps the index small since most deliveries are document-attached via the existing `document_id` FK. Clean downgrade drops index + column. **`DocumentDelivery` model** gains the column + a lazy-select relationship. **`DeliveryService.SendParams`** gains an optional `caller_vault_item_id` kwarg (default None) that flows through to the DocumentDelivery row — additive, zero existing callers affected, new callers (Quote sends, compliance reminders) can opt in. **Quote VaultItem dual-write** via three helpers added to `quote_service.py`: `_quote_vault_metadata(quote)` builds a JSONB-safe metadata dict (Decimal→str, datetime→None safely), `_write_quote_vault_item(db, quote)` creates a VaultItem with `item_type="quote"` + `source="system_generated"` + `source_entity_id=quote.id` + `related_entity_type="quote"` + title `"Quote {number} — {customer_name}"` + metadata carrying `quote_number / customer_name / total / status / product_line / converted_to_order_id`, `_update_quote_vault_item(db, quote)` refreshes metadata on status change and flips `VaultItem.status → "completed"` + stamps `completed_at` when the Quote converts. Called at 3 sites: `create_quote` (after commit), `convert_quote_to_order` (after commit, adds `converted_to_order_id`), `update_quote_status` (after commit). All 3 call sites wrap in the defensive try/except + logger.exception pattern established in V-1d — VaultItem failures never block Quote operations. Backfill policy: **forward-only** — existing Quotes don't get retroactive VaultItems; `_update_quote_vault_item` logs + noops when the VaultItem is missing (pre-V-1f quote) so no crashes on the transitional row set. **Quoting Hub deep-link** at `frontend/src/pages/quoting/quoting-hub.tsx`: subtitle next to "New Quote" gains a subtle `<Link to="/vault/documents/templates?search=quote.standard">Customize quote template →</Link>`. The Templates library page already supports the `search` query param with ilike filtering on `template_key` + `description` — no Templates-page code change needed; `?search=quote.standard` deep-links straight to the single row. **JE investigation:** grep confirmed zero `create_vault_item` callers under `app/services/` reference JournalEntry; JEs don't participate in VaultItem today (Case A). No fix shipped. A lint-style test (`test_je_posts_do_not_write_vault_item_today`) scans the services directory and fails if any module mentions both `create_vault_item` and `journal_entry`/`JournalEntry` — forces any future JE dual-write to be intentional and to pick the right `item_type` (document vs event vs new `journal_entry` discriminator) rather than drifting into the wrong default. DEBT.md entry documents the deferred JE-coverage decision. **Pre-existing bug surfaced** (BUGS.md entry #7): `quote_service` calls `audit_service.log(...)` but the function is named `log_action(...)`. Has been broken since March 2026 — every Quote write raises AttributeError at the audit-log line (post-commit, so DB state is persisted but the response crashes). V-1f+g tests work around this with an autouse monkeypatch fixture that shims `audit_service.log` to no-op; the real fix is a separate one-line cleanup (3 call sites) tracked in BUGS.md. **Tests:** 13 backend tests in `test_vault_v1fg_vault_item_hygiene.py` across 5 test classes — migration schema (3: column exists, nullable, partial index), SendParams new field (2: accepts value, defaults None), DocumentDelivery persistence (2: round-trips via ORM with relationship, default None unchanged), Quote VaultItem dual-write (5: create writes VaultItem, metadata stringifies Decimals, convert updates metadata + flips status to completed, status change refreshes metadata, best-effort-failure doesn't block Quote creation), JE Case A lint guard (1). 4 Playwright tests in `vault-v1fg-quote-hygiene.spec.ts`: Quoting Hub link visible, link carries `?search=quote.standard`, click navigates correctly, deliveries endpoint smoke-passes post-migration. **Tests total:** 201 passing (10 V-1a + 13 V-1b + 16 V-1c + 21 V-1d + 33 V-1e + 13 V-1f+g + 95 doc regression across D-4/D-6/D-7) — no regressions. Migration head: `r30_delivery_caller_vault_item` (advanced from r29). Nav + widget surfaces unchanged; this phase is plumbing hygiene.
- **Bridgeable Vault — Phase V-1e Accounting Admin Consolidation (complete):** Accounting becomes the fifth full Vault service after Documents, Intelligence, CRM, and Notifications. Platform-admin surfaces for the accounting engine (periods + locks, agent schedules, GL classification queue, tax config, statement templates, COA templates) consolidate under `/vault/accounting/*`. Tenant-facing Financials Hub (invoices, bills, JEs, statements, reports) stays in the vertical nav and its existing routes — V-1e is admin-only. No schema changes; migration head unchanged at `r29_notification_safety_merge`. **Backend:** hub_registry adds `accounting` service (sort_order=40, icon="Calculator", route_prefix=`/vault/accounting`, `required_permission="admin"`) with 3 overview widgets. New `app/api/routes/vault_accounting.py` router mounted at `/api/v1/vault/accounting/*` — all endpoints `require_admin`. **New endpoints (10):** `GET /periods?year=N` (auto-seeds the 12 months for a queried year if absent, so the UI always renders a full year at a glance), `POST /periods/{id}/lock` (409 if already closed, writes AuditLog `period_locked` row), `POST /periods/{id}/unlock` (409 if already open, writes `period_unlocked`), `GET /period-audit?limit=N` (recent lock/unlock events), `GET /pending-close` (month-end-close agent jobs with status `awaiting_approval`/`complete` whose matching AccountingPeriod is still open — collapsed one-per-period newest-wins), `GET /coa-templates` (read-only expose of `PLATFORM_CATEGORIES` from accounting_analysis_service — 5 category types × 27 categories: revenue, AR, COGS, AP, expenses), `GET /classification/pending?limit=N&mapping_type=X` (TenantAccountingAnalysis rows with status=pending, highest-confidence first), `POST /classification/{id}/confirm` (idempotent — 409 if not pending; for `gl_account` rows also creates a `TenantGLMapping` row so downstream agents resolve the mapping), `POST /classification/{id}/reject` (marks rejected — no mapping). Audit writes use the existing `AuditLog` model with `action in ("period_locked","period_unlocked") + entity_type="accounting_period" + entity_id=period.id + changes=JSON({period_month, period_year, previous_status, new_status, display_name})`. Two supporting endpoints added to `agents.py`: `GET /schedules` (tenant-wide list — previously only POST upsert existed; now the UI can render the full 12-agent table) and `GET /jobs?limit&status&job_type` (tenant-wide job tail without the `period_start.isnot(None)` filter the existing `/accounting` endpoint carries, so cross-agent widgets see all jobs including nightly). `widget_registry.py` adds 3 new definitions at positions 8/9/10 with `required_permission="admin"` + `page_contexts=["vault_overview"]`: `vault_pending_period_close`, `vault_gl_classification_review`, `vault_agent_recent_activity`. **Frontend:** new `/vault/accounting/*` route sub-tree under `VaultHubLayout` with an admin-only `<ProtectedRoute adminOnly>` gate at the sub-tree root matching the backend filter. Index redirects to `/vault/accounting/periods`. Six sub-tabs: `AccountingPeriodsTab` (year selector + periods table + recent-activity feed; type-to-confirm modal for locks with explicit "Type *January 2026* to confirm" input that disables the destructive action until exact match; simple-confirm for unlocks since restoring writes is cheap), `AccountingAgentsTab` (schedules table + recent-jobs feed; clear copy "Configure when each accounting agent runs" distinguishes from the tenant Agents Hub), `AccountingClassificationTab` (pending AI rows with confirm/reject actions + bulk-confirm high-confidence `>0.9` button), `AccountingTaxTab` (read-only rates + jurisdictions; "Open Tax settings" deep-link to the existing CRUD page — via `buttonVariants()` styled Link, not `asChild`), `AccountingStatementsTab` (split platform-defaults/tenant-overrides view, read-only in V-1e — template editing deferred), `AccountingCoaTab` (platform standard GL categories with filter/search, read-only). `AccountingAdminLayout` renders secondary tab bar with active-state highlighting via NavLink. `VaultHubLayout.tsx` icon map gains `Bell` (V-1d drift fix) + `Calculator` (V-1e). `vault-hub-registry.ts` registers the accounting service (sort_order=40). **New widgets** at `components/widgets/vault/`: `PendingPeriodCloseWidget` (calls `/vault/accounting/pending-close`, row click → `/vault/accounting/periods`, shows anomaly count in secondary text), `GlClassificationReviewWidget` (calls `/vault/accounting/classification/pending?limit=10`, shows confidence %, click → `/vault/accounting/classification`), `AgentRecentActivityWidget` (calls `/agents/jobs?limit=10`, status-colored dot + agent label + relative time, click → `/vault/accounting/agents`). All 3 registered in the vault widget barrel under `service_key="accounting"`. **New frontend service** `accounting-admin-service.ts` wraps every admin endpoint with typed TypeScript responses that mirror backend Pydantic schemas. **Tests:** 33 backend in `test_vault_v1e_accounting.py` across 7 test classes covering hub registry (5), /vault/services visibility admin+non-admin (2), periods endpoints — auto-seed + lock + unlock + audit writes + 409 idempotency + cross-tenant 404 + non-admin 403 (8), pending-close empty + happy-path + closed-period-hidden (3), COA templates — platform categories + admin-gated (2), classification queue — pending filter + confirm creates GL mapping + reject no mapping + 409 already-confirmed + cross-tenant 404 (5), agent schedules + jobs — list + returns rows + cross-tenant (4), widget seeding + permission + admin visibility + non-admin hiding (4). 16 Playwright tests in `vault-v1e-accounting.spec.ts` covering layout render + all 6 tabs visible + tab navigation + sidebar entry + click-to-navigate, periods tab full-year render + type-to-confirm modal disabled + enabled-on-exact-match, COA platform categories render, API smoke tests on /vault/services + coa-templates + pending-close + periods auto-seed + overview/widgets V-1e inclusion, Agent Schedules + Tax Config render-without-crash. **Tests total:** 188 passing (10 V-1a + 13 V-1b + 16 V-1c + 21 V-1d + 33 V-1e + 95 doc regression suites D-4/D-6/D-7). One V-1b test fixture updated (`known_services` set extended with `"accounting"`). **Deviations from spec:** (a) spec mentions "100+ platform standard GL categories" — actual source-of-truth `PLATFORM_CATEGORIES` has 27 categories across 5 types; exposed the real set rather than invent rows. (b) Tax Config + Statement Templates tabs are read-only with deep-links to existing CRUD (tax: `/settings/tax`); full editors deferred to keep V-1e scope tight. (c) Agent Schedules tab exposes existing POST-upsert + toggle endpoints; a full cron-editor modal is deferred. (d) Widget definitions require an explicit `seed_widget_definitions(db)` run on first deploy (fired from `app/main.py` startup) — test fixtures need to match. DEBT.md adds entries for statement-template editor build, cron-editor for agent schedules, V-1e widget seed coordination. Migration head: `r29_notification_safety_merge` (unchanged). Nav: Vault hub now shows 5 services for admins (Documents, Intelligence, CRM, Notifications, Accounting).
- **Bridgeable Vault — Phase V-1d Notifications as Full Service + SafetyAlert Merge + 5 New Sources (complete):** Notifications promoted from V-1b proto-service to a full Vault service; SafetyAlert merges into Notification with a clean break (table dropped); 5 new platform-wide notification sources wire into existing services. **Migration `r29_notification_safety_merge`**: extends `notifications` with 6 alert-flavor columns (`severity` String(16), `due_date` DateTime tz, `acknowledged_by_user_id` FK → users, `acknowledged_at` DateTime tz, `source_reference_type` String(64), `source_reference_id` String(255)) that preserve every SafetyAlert semantic. Data-migrates SafetyAlert rows into Notification via admin-user fan-out — `INSERT ... SELECT ... FROM safety_alerts sa INNER JOIN users u ... INNER JOIN roles r ON r.slug='admin' AND u.is_active=TRUE` producing one Notification per admin per tenant; then `op.drop_table("safety_alerts")` guarded by `sa.inspect(conn).get_table_names()`. Type coercion: SafetyAlert.severity → Notification.type tone (critical→error, high→warning, else info) while keeping original severity; SafetyAlert.due_date (Date) → Notification.due_date (DateTime). Link auto-built as `/safety/{reference_type}/{reference_id}` when refs exist. No production data was lost — no in-app code ever created SafetyAlert rows; the data migration runs no-op on most tenants. Downgrade recreates an empty `safety_alerts` schema + drops the 6 new columns — schema-only, merged data stays in Notification. **Model changes:** `app/models/safety_alert.py` deleted, `SafetyAlert` removed from `app/models/__init__.py` (import + __all__). Notification model gains the 6 columns + an `acknowledged_by` relationship. **`notification_service.create_notification` extended** with keyword-only alert-flavor kwargs (`severity`, `due_date`, `source_reference_type`, `source_reference_id`). New `notify_tenant_admins()` fan-out helper — one row per active admin user in a tenant, joined via `Role.slug='admin'` (matches the r29 migration's SQL fan-out), logs + returns empty list for tenants without admins rather than raising. **Safety-alerts readers rewritten:** `safety_service.list_alerts` + `acknowledge_alert` now query Notification filtered by `category='safety_alert'`, return AlertResponse-compatible dicts via `_notification_to_alert_dict()` that preserves the pre-V-1d response shape (including `alert_type` extracted from title prefix, `resolved_at` mirroring `acknowledged_at`, `due_date` normalized to UTC before `.date()` call to avoid TZ drift). Severity sort uses an explicit priority map (critical/high/medium/low) instead of Postgres text ordering. Ack marks Notification `is_read=True` + sets `acknowledged_by_user_id` + `acknowledged_at`; non-safety-category rows return None so the safety endpoint can't mutate unrelated notifications. **Notifications promoted to full Vault service:** `hub_registry.py` entry now documents V-1d's promotion (sort_order=30, route_prefix=`/vault/notifications`, `overview_widget_ids=["vault_notifications"]`). Frontend `vault-hub-registry.ts` registers the notifications descriptor matching the backend. Route migration in App.tsx: `/notifications` → `<Navigate to="/vault/notifications" replace />`, `/vault/notifications` mounts `NotificationsPage` (same page component as V-1b used). 4 internal `/notifications` link refs updated: NotificationsWidget (3 — click-through + empty-state link + "View all" link), notification-dropdown "View all" footer button. FH preset `label: "Notifications"` top-level nav entry removed in `navigation-service.ts` — Notifications now reachable exclusively through the Vault hub sidebar + bell-icon dropdown + the `vault_notifications` overview widget. **5 notification sources wired:** (1) **share_granted** in `document_sharing_service.grant_share` after the DocumentShare persists — fan-out to target tenant admins, category="share_granted", link=`/vault/documents/{doc_id}`, source_reference_type="document"; wrapped in try/except so a notification failure never blocks a grant. (2) **delivery_failed** via new `_notify_delivery_failed(db, delivery)` helper called at both terminal-failure points in `delivery_service.send` (unhandled-exception path + non-retryable/retries-exhausted path). Severity="high", type="error", link=`/admin/documents/deliveries/{id}`; ONLY fires when `terminal_status == "failed"` — the `"rejected"` branch (SMS stub `NOT_IMPLEMENTED`) does NOT fire to avoid non-actionable feed noise. (3) **signature_requested** in `signature_service._advance_after_party_signed` — when a next party transitions to `sent`, if that party's `email` matches an active User in `envelope.company_id`, fire a direct (not fan-out) notification for that internal user. External signers (FH directors, cemetery reps, next-of-kin) get the email invite only and no in-app notification — they have no Vault login. Category="signature_requested", link=`/admin/documents/signing/envelopes/{id}`. (4) **compliance_expiry** in `vault_compliance_sync` — adds new `_severity_for_days()` helper (<=7 days or expired → "high", else "medium") and `_notify_admins_compliance_expiry()` with (company_id, category, source_reference_id) dedup lookup so re-runs don't spam. Fires on VaultItem CREATE path only (updates skip). Wired into all 3 sync paths (equipment inspection, training renewal, regulatory deadline). (5) **account_at_risk** in `health_score_service.calculate_health_score` — captures `prior_score = profile.health_score` BEFORE any mutation, fires notification only on transition INTO at_risk (`score == "at_risk" and prior_score != "at_risk"`). Same-score nightly recalcs do not re-fire. Category="account_at_risk", severity="high", link=`/vault/crm/companies/{master_company_id}`. **Admin fan-out pattern:** every source goes through `notify_tenant_admins()` except signature_requested (which targets a specific internal signer) — consistent fan-out semantics across the platform. **Tests:** 21 new backend tests in `test_vault_v1d_notifications.py` covering schema (2 — 6 V-1d columns present, safety_alerts table dropped), extended create_notification (1), notify_tenant_admins fan-out (2 — active admins only, empty list when no admins), hub registry (3 — notifications in services list, route_prefix, sort order after CRM/intelligence), /vault/services API (1), safety-alerts reader rewrite (4 — category filter, active_only filter, ack sets fields + is_read, returns None for non-safety category), share_granted source (1 — grant fans out to target admins with doc linkage), delivery_failed source (1 — helper fans out with high severity + delivery linkage), signature_requested source (2 — internal-email match fires, external email no-fire), compliance_expiry source (3 — severity <=7 days is high, >7 days is medium, dedupe by source_reference_id), account_at_risk source (1 — transition branch produces notification with CRM link + company entity linkage). Plus D-6 sharing test fixture extended with `notifications` table so the V-1d fan-out in `grant_share` doesn't poison SQLite sessions. 7 Playwright tests in `vault-v1d-notifications.spec.ts` covering `/vault/notifications` renders inside VaultHubLayout, `/notifications` redirect, Vault hub sidebar Notifications entry present + clickable, top-level `/notifications` anchor removed, `/api/v1/vault/services` includes notifications with correct route_prefix, `/api/v1/notifications` stays 200. **Tests total:** 60 vault tests passing (10 V-1a + 13 V-1b + 16 V-1c + 21 V-1d) — no regressions across doc test suites (D-4 signing, D-6 sharing, D-7 delivery all green). Migration head: `r29_notification_safety_merge`. DEBT.md adds entries for notification preferences (per-category opt-out), rate limiting on noisy categories, and category vocabulary central-registry — none blocking.
- **Bridgeable Vault — Phase V-1c CRM Absorption (lift-and-shift, complete):** CRM becomes the third full Vault service (after Documents + Intelligence). Per the audit's Option A, this is a lift-and-shift — URL moves from `/crm/*` to `/vault/crm/*`, all 9 CRM pages now render inside `VaultHubLayout`, top-level CRM hub entry removed from manufacturing + FH nav presets. No schema changes; migration head still `r28_d9_quote_wilbert_templates`. CRM parallel contact models (CustomerContact / VendorContact / FHCaseContact vs CRM `Contact`) stay unreconciled — that's a separate future build tracked in the audit. **Backend:** new tenant-wide activity endpoint at `GET /api/v1/vault/activity/recent?limit=N&since_days=N` backed by new `activity_log_service.get_tenant_feed(db, tenant_id, limit, since)` that aggregates across all CompanyEntity rows the tenant tracks, joins on CompanyEntity for display name, body truncated to 200 chars. Tenant isolation: every `ActivityLog` row has a `tenant_id`; the service filter is the canonical gate. CRM registered in `app.services.vault.hub_registry` with `required_permission="customers.view"` (same gate the old top-level nav entry had) and two `overview_widget_ids` — `vault_crm_recent_activity` + `at_risk_accounts`. Two widget-definition changes in `WIDGET_DEFINITIONS`: `at_risk_accounts` extends its `page_contexts` to `["home", "ops_board", "vault_overview"]` (shared component renders in Ops Board + Vault Overview contexts) and gains a `required_permission="customers.view"` gate; new `vault_crm_recent_activity` widget at position 6. **Widget seed refactor:** `seed_widget_definitions` upgraded from `ON CONFLICT DO NOTHING` to `ON CONFLICT DO UPDATE` on the system-owned columns (`page_contexts`, `default_position`, `icon`, etc.) so future extensions like "widget X also appears on page Y" just ship in code without a migration. Per-user `user_widget_layouts` rows are untouched — only definition metadata refreshes. **Frontend:** App.tsx route tree restructured — `/vault` no longer has a blanket `adminOnly` gate; instead each sub-tree gates independently — Documents + Intelligence stay `adminOnly`, new `/vault/crm/*` branch uses `<ProtectedRoute requiredPermission="customers.view" />`, Overview (index) open to any authenticated tenant user (the overview widgets themselves filter by service access server-side). Old `/crm/*` routes replaced with `<Navigate>` + `RedirectPreserveParam` redirects (9 redirect entries) — one-release grace period, then removable. `vault-hub-registry.ts` registers CRM service with `sort_order: 15` (between Documents at 10 and Intelligence at 20). `VaultHubLayout` gets `Building2` added to its icon map. CRM top-level nav entry removed from manufacturing hub items + FH hub items; both verticals' mobile tab bars repoint their CRM slot to `Vault` (icon + label). **New widget:** `CrmRecentActivityWidget` at `components/widgets/vault/CrmRecentActivityWidget.tsx` — calls the new activity endpoint, renders 10 most-recent activities with a system/manual badge, click → `/vault/crm/companies/:id`. **Reused widget:** `AtRiskAccountsWidget` (existing in `components/widgets/ops-board/`) registered with `vaultHubRegistry` under `service_key: "crm"`. Same component, two page contexts, one frontend registration. The navigate path inside the widget was rewritten from `/crm/companies/${id}` to `/vault/crm/companies/${id}` during the bulk link rewrite — valid in both Ops Board + Vault Overview contexts (legacy `/crm/` paths still redirect). **Internal link rewrite:** 55 path substitutions across 16 files (breadcrumbs, CRM pages, crm-hub, duplicates page, admin data-quality, actionRegistry, AtRiskAccountsWidget). Import paths untouched (only URL strings matched). **Tests:** 16 backend in `test_vault_v1c_crm.py` across 4 test classes — hub-registry CRM service (5 tests: seeded, permission gate, widget_ids list, sort order, route prefix), services endpoint visibility (2 tests: admin sees CRM, non-admin without permission hides it), overview-widgets endpoint (3 tests: admin sees CRM widgets, non-admin doesn't, widget service_key correctly tagged "crm"), activity endpoint (6 tests: returns 200, tenant-scoped filter, limit parameter, since_days filter, company_name join, auth required). 13 Playwright tests × 2 projects = 26 covering: 4 `/vault/crm/*` routes render, 4 old-path redirects (`/crm`, `/crm/companies`, `/crm/pipeline`, `/crm/settings`), CRM sidebar entry present + clickable, top-level CRM nav removed, `/api/v1/vault/activity/recent` returns 200, `/api/v1/vault/overview/widgets` includes CRM widgets. Full suite now: 263 passing (was 247; +16 V-1c) — no regressions. **Deviations from spec:** (a) restructured route-tree gating instead of putting adminOnly at the /vault root (required to let permission-gated CRM coexist with admin-only Documents/Intelligence under the same VaultHubLayout); (b) retained `CRMHub` as the /vault/crm index page instead of redirecting to /companies (preserves existing user-facing landing behavior, non-breaking); (c) bumped `at_risk_accounts` default_position from 3 to 7 (single default_position column shared across contexts — the home/ops_board default-layout positioning shifts, but users' saved layouts are preserved). 29 total uncommitted files (V-1a+b+c aggregate, not yet pushed).
- **Bridgeable Vault — Phase V-1b Overview Dashboard with Widgets (complete):** `/vault` landing page upgraded from V-1a placeholder to a live widget dashboard built on the existing `WidgetGrid` + `useDashboard` framework (the same one powering Operations Board / Financials Board). Five widgets ship, all service-owned and all wrapping existing tenant APIs — zero new aggregation endpoints. No schema changes; V-1b reuses the existing `user_widget_layouts` table for per-user customization persistence. **Five widgets** under `frontend/src/components/widgets/vault/`: `RecentDocumentsWidget` (DocumentLog preview, links to `/vault/documents`), `PendingSignaturesWidget` (envelopes `status=out_for_signature`, links to `/vault/documents/signing/:id`), `UnreadInboxWidget` (D-6/D-8 inbox filtered client-side to `is_read=false && revoked_at=null`, title carries unread count in header), `RecentDeliveriesWidget` (DeliveryLog + All/Failures toggle that re-fetches with `status=failed`), `NotificationsWidget` (unread notifications with fire-and-forget mark-read on click, type-colored dot). Each widget follows the existing ops-board pattern — `useState` + `useEffect` loader, `WidgetWrapper` chrome with refresh/remove/resize actions, empty-state with action link, `formatRelativeAge` for timestamps, prop pass-through of `_editMode` / `_size` / `_dragHandleProps` / `_onRemove` / `_onSizeChange` / `_supportedSizes`. **Backend:** 5 new widget definitions seeded into `WIDGET_DEFINITIONS` in `app/services/widgets/widget_registry.py` with `page_contexts=["vault_overview"]` — picked up by existing `/api/v1/widgets/available` + `/api/v1/widgets/layout` endpoints automatically (the framework already handles per-user layout CRUD, default layout generation, permission/extension/preset gating). `app/services/vault/hub_registry.py` seed updated to populate `overview_widget_ids` on the Documents descriptor (4 widgets) and on a new `notifications` proto-service (1 widget) — the proto-service gets a full `/vault/notifications` route + sidebar treatment in V-1d. **New endpoint** `GET /api/v1/vault/overview/widgets` returns a flat list of widgets the user can see plus a recommended default layout, joining the `hub_registry` (which service owns which widget) with the widget framework's availability filter. The canonical layout persistence still lives in `/widgets/layout?page_context=vault_overview`; this endpoint exists for V-1c+ consumers that need the service-key → widget-ids mapping. Default positions 1-5 are seeded; position 6 is intentionally empty so the WidgetPicker "add widget" affordance is discoverable. **Frontend registry extended:** `vaultHubRegistry` from V-1a gains a parallel widget-registration API — `registerWidget()`, `getWidget()`, `getAllWidgets()`, `getComponentMap()`. Each widget file is bundled via `components/widgets/vault/index.ts` which registers the component against its `widget_id`; `VaultOverview.tsx` imports this barrel as a side-effect + calls `getComponentMap()` to feed the `WidgetGrid` componentMap prop. **VaultOverview.tsx** replaces V-1a's static service-card placeholder with a full dashboard: header + edit-mode toggle + Add-widget + Reset buttons, `WidgetGrid` with drag-drop reordering + resize menu per widget, `WidgetPicker` slide-in for adding disabled widgets, debounced layout save via `useDashboard`. **Frontend service:** new `services/vault-service.ts` for `getServices()` + `getOverviewWidgets()`. **Tests:** 13 backend in `test_vault_v1b_widgets.py` (hub registry widget_id population × 6, overview widgets endpoint × 5, widget definitions seed × 2) + 13 Playwright in `vault-v1b-widgets.spec.ts` × 2 projects = 26 total (dashboard renders not-placeholder, widget grid renders multiple widgets, per-widget presence × 5, edit mode toggle, filter toggle switches state, `/api/v1/vault/overview/widgets` returns 5 widgets for admin, `/api/v1/widgets/available?page_context=vault_overview` returns seeds, "View all" links land on `/vault/` paths, sidebar + breadcrumbs still present). Full doc suite now: 247 passing (was 234; +13 V-1b). Migration head unchanged at `r28_d9_quote_wilbert_templates` — no schema changes this phase.
- **Bridgeable Vault — Phase V-1a Hub Frame + Nav Restructure (complete):** Establishes `/vault/*` as the cross-cutting platform-infrastructure hub across every tenant vertical. Documents + Intelligence admin surfaces move under it; future V-1 phases add CRM (V-1c), Notifications (V-1d), and Accounting admin (V-1e). Pure nav restructure — no schema changes, migration head unchanged at `r28_d9_quote_wilbert_templates`. **Backend:** new `app.services.vault` package with `hub_registry.py` — module-level singleton tracking `VaultServiceDescriptor` rows (service_key + display_name + icon + route_prefix + gating kwargs); seeds Documents + Intelligence on first `list_services()` call. New endpoint `GET /api/v1/vault/services` added to the existing `vault.py` router (sibling to the VaultItem CRUD routes); filters descriptors by permission/module/extension against the current user (super-admins bypass). **Frontend:** `/vault/*` route hierarchy wraps every child page in `VaultHubLayout` — 240px secondary sidebar (icon-only at <lg breakpoints) listing Overview + every registered service, breadcrumbs showing `Vault / {service}`, active-state resolution via `vaultHubRegistry.findServiceForPath()` longest-prefix match. `VaultHubRegistry` frontend mirror at `frontend/src/services/vault-hub-registry.ts` (source of truth for V-1a; backend becomes SOT in V-1b when widget data-aggregation needs server-side awareness). `VaultOverview.tsx` placeholder renders registered services as clickable cards — V-1b replaces with widget grid. All existing Documents/Intelligence page components unchanged — they render under new URL paths inside the Vault layout. **Route migration:** `/admin/documents/*` → `/vault/documents/*`, `/admin/intelligence/*` → `/vault/intelligence/*`. 301-style `<Navigate>` redirects preserved for one-release grace period; new `RedirectPreserveParam` helper handles paths with URL params (`:documentId`, `:promptId`, etc.). Signer-facing `/sign/:token` unchanged (public, not under Vault). **Internal link audit:** bulk-rewrote 44 internal path references across 21 frontend files using a targeted regex script (most-specific-first ordering to avoid double-replacement). One accidental import-path rewrite in `PromptDetail.tsx` caught + reverted. **Nav restructure:** new "Bridgeable Vault" top-level hub entry in all 4 verticals (Manufacturing after Compliance, FH + Cemetery + Crematory after Financials); `admin-only` gated; `Vault` lucide icon added to sidebar `ICON_MAP`. 7 entries removed from Settings → Platform subgroup (Intelligence, Experiments, Documents, Document Log, Inbox, Delivery Log, Signing) — subgroup now contains only Billing, Extensions, Onboarding. **Tests:** 10 backend tests in `test_vault_v1a_hub.py` (registry seeding, sort order, register/replace, route_prefix shape, endpoint 200 with admin, endpoint shape, auth rejection, extension-gate filtering non-admin, plus permanent-+-empty descriptor defaults). 10 Playwright tests in `vault-v1a.spec.ts` × 2 projects = 20 total (nav entry visible, landing renders, sidebar lists services, Documents/Intelligence accessible under new paths, 3 redirect tests, `/api/v1/vault/services` returns registered services, Settings → Platform subgroup cleanup). **Known deviation:** Route ordering under `/vault/documents` puts `:documentId` LAST so sibling paths (`templates`, `inbox`, `deliveries`, `signing`) don't get shadowed by the polymorphic param segment. **What's in V-1a scope but deferred to V-1b+:** Vault Overview widgets (V-1b), CRM absorption (V-1c), Notifications enrichment + SafetyAlert merge (V-1d), Accounting admin consolidation (V-1e), Quote VaultItem dual-write (V-1f), Delivery `caller_vault_item_id` column (V-1f), JE dual-write fix (V-1g), Calendar (V-2), Reminders (V-2), documentation (V-1h).
- **Bridgeable Documents — Phase D-9 Arc Debt Cleanup (complete):** Pure debt reduction — no new features. Three focused cleanups close out the Documents arc. **1. Last 3 WeasyPrint call-sites migrated through DocumentRenderer.** `pdf_generation_service.generate_template_preview_pdf` (admin invoice-preview tool) now routes through `document_renderer.render_pdf_bytes` with managed `invoice.{variant}` keys — preview reflects the same registry body the live invoice generator uses; falls back to `invoice.professional` if an unknown variant slips in. `quote_service.generate_quote_pdf` elevated quotes to first-class Documents — new `generate_quote_document()` wraps `document_renderer.render(template_key="quote.standard")` with `entity_type="quote" + entity_id=quote.id`; legacy `generate_quote_pdf` bytes API preserved via `download_bytes(doc)`. `wilbert_utils.render_form_pdf` now routes through `render_pdf_bytes(template_key="urn.wilbert_engraving_form")` with a structured `pieces` context (engraving vs non-engraving split computed in `_piece_context`); HTML-fallback contract preserved on render failure. **Migration `r28_d9_quote_wilbert_templates`** seeds two new platform templates (`quote.standard`, `urn.wilbert_engraving_form`) — idempotent skip if the template_key already exists. Both platform-global (`company_id=NULL`), both `output_format="pdf"`. **Ruff TID251 allowlist collapsed** to `document_renderer.py` + `app/main.py` (diagnostic import-only). The `TRANSITIONAL_ALLOWLIST` in `tests/test_documents_d2_lint.py` is now empty; new `test_transitional_allowlist_is_empty` invariant fails if anyone re-adds an entry. **2. EmailService `_fallback_company_id()` safety net removed.** D-7 shipped with a fallback helper that attributed missing-tenant sends to the first active Company in the DB (masking caller bugs silently). D-9 replaced it with `_require_company_id()` which raises `ValueError` if `company_id` is None. All 10 callers migrated to thread `company_id` explicitly: `sales.py` invoice email (threads `current_user.company_id`), `agents.py` collections email, `accounting_connection.py` accountant invitation, `approval_gate.py` review email (threads `tenant_id`), `statement_service.py` statement email, `draft_invoice_service.py` invoice send (threads `inv.company_id`), `social_service_certificate_service.py` SSC email (threads `order.company_id`), `urn_engraving_service.py` Wilbert + FH approval emails (×2, threads `tenant_id`), `platform_email_service.send_tenant_email` (previously a silent bug — had `tenant_id` but didn't thread it). Legacy `legacy_email_service.py` already required `company_id` — no change needed. Any caller still missing `company_id` now crashes with a clear error pointing at the call site. **3. DocumentRenderer rendering paths unified.** `document_renderer.render()` extended with optional `template_version_id` kwarg (exactly one of `template_key` / `template_version_id` must be provided). New `template_loader.load_by_version_id()` resolves a specific DocumentTemplateVersion by id — powers draft/retired rendering. The test-render endpoint (`/admin/templates/{id}/versions/{vid}/test-render`) collapsed from ~130 lines of duplicated Jinja + WeasyPrint + R2 + Document-insert logic to ~50 lines that delegate to `document_renderer.render(template_version_id=..., is_test_render=True)`. Single code path for all Document generation; test-render and production-render use identical logic. **Tests:** 22 new D-9 tests in `test_documents_d9.py` across 5 test classes: `TestWeasyPrintMigrations` (7 — no-import verification for 3 files, template registration, preview routes through renderer, fallback to professional, wilbert routes through renderer), `TestQuoteGenerationCreatesDocument` (2 — Document creation with entity linkage, legacy bytes API), `TestWeasyPrintAllowlistMinimal` (2 — transitional empty, permanent minimal), `TestEmailServiceRequiresCompanyId` (5 — fallback gone, require-helper behavior, 2 send-method crash tests), `TestRendererUnification` (5 — exactly-one kwarg required, key-mode uses active, version_id-mode uses specific version, version_id wins over mismatched key, test-render endpoint no longer imports renderer internals). D-2 lint test updated (`test_documents_d2_lint.py::test_transitional_allowlist_is_empty` new invariant; `test_weasyprint_import_forbidden_outside_documents` smoke test updated to expect empty transitional set). Total: 224 passed (baseline D-8 was 201, +1 D-2 lint invariant + +22 D-9 = 224) — no regressions. Migration head: `r28_d9_quote_wilbert_templates`. Architecture doc `documents_architecture.md` updated: roadmap row for D-9, renderer resolution-modes note for D-9, new templates added to seeded list, deprecated "3 remaining WeasyPrint sites" bullet marked resolved. Delivery architecture doc updated with "company_id required on every send" note and guidance for new callers. DEBT.md: 3 resolved entries (WeasyPrint call sites, EmailService fallback, renderer paths) moved to "Resolved debt" section with full resolution context.
- **Bridgeable Documents — Phase D-7 Delivery Abstraction (complete):** Channel-agnostic send interface — every email / SMS / future-channel send in the platform flows through one service with full audit trail. "Integrate now, make native later" made concrete: when Bridgeable's native email ships, it plugs in as a new channel implementation without any caller changes. **Migration `r26_delivery_abstraction`**: creates `document_deliveries` table (company_id + document_id + channel + recipient_type/value/name + subject + body_preview + template_key + status + provider + provider_message_id + provider_response JSONB + error_message/code + retry_count/max_retries + scheduled_for + sent_at/delivered_at/failed_at + caller_module + 4 caller_* linkage FKs + metadata_json), adds 6 targeted indexes (partial indexes on active states and non-null FKs for efficient queries), and extends `intelligence_executions.caller_delivery_id` closing the symmetric-linkage loop with D-6 (AI executions traceable to the delivery they triggered, deliveries traceable to the execution that drafted them). **`app.services.delivery` package** — protocol-based channel interface + orchestrator: `channels/base.py` defines the `DeliveryChannel` Protocol + `Recipient`, `Attachment`, `ChannelSendRequest`, `ChannelSendResult` dataclasses (duck-typed — any class with `channel_type` + `provider` class attrs + `send` method qualifies). `channels/email_channel.py` wraps Resend — the **ONLY module in the codebase allowed to import `resend`** (lint-enforced via `test_documents_d7_lint.py`), error classification maps connection/timeout errors to retryable and auth/validation to non-retryable. `channels/sms_channel.py` stubs with `success=False, error_code="NOT_IMPLEMENTED", retryable=False` so SMS callers get clean `status=rejected` rather than crashes. **`delivery_service.py` orchestrator**: resolves content (calls `document_renderer.render_html()` when `template_key` set, else uses caller-supplied body), fetches + attaches document PDF when `document_id` set and channel supports attachments (best-effort — R2 miss logs but doesn't block send), creates `DocumentDelivery` row with `status=pending` before dispatch, dispatches via `get_channel(channel).send()`, inline-retries retryable errors bounded by `max_retries` (default 3), updates row with provider response + status (`sent` on success, `failed` after exhaustion, `rejected` for non-retryable like SMS stub). Convenience builders: `send_email_with_template`, `send_email_raw`. **`send_document` workflow step type** — promoted to top-level like `ai_prompt` in Phase 3d. `_execute_send_document` reads config (`channel`, `recipient`, `template_key`/`template_context` OR `body`, `subject`, `reply_to`, optional `document_id`), auto-populates `caller_workflow_run_id` + `caller_workflow_step_id`, returns `{delivery_id, status, provider_message_id, error_message, channel, recipient}` referenceable by downstream steps. **7 email caller categories migrated** through DeliveryService while keeping public signatures intact: signing invite/completed/declined/voided (`signing/notification_service.py` — signature envelope linkage auto-populated), statement (`email_service.send_statement_email`), collections, user invitation, accountant invitation, alert digest, invoice, legacy proof (`legacy_email_service.send_email`). Test-mode behavior preserved (no API key = logs + no-op). **Admin UI** — new `/admin/documents/deliveries` DeliveryLog page (channel + status + recipient-search + template-key filters, 7 columns, status color coding with 7 states), `/admin/documents/deliveries/{id}` DeliveryDetail (metadata + template + error details + 6 linkage rows with clickable links to Document / Workflow Run / Intelligence Execution / Signature Envelope + body preview + provider response JSONB + Resend button). Nav entry "Delivery Log" under Platform admin. **4 new API endpoints** on `/documents-v2/*`: `GET /deliveries` (list with filters, defaults last 7 days), `GET /deliveries/{id}` (detail, tenant-scoped 404 otherwise), `POST /deliveries/{id}/resend` (reuses preserved inputs — templates re-render with current content so resend-after-edit uses the newer version), `POST /deliveries` (ad-hoc admin send). **Tests:** 31 new D-7 tests in `test_documents_d7_delivery.py` covering channel registry (6 — email/sms providers, unknown channel, attachment+html support flags, register_channel for provider swap), SMS stub behavior (1), DeliveryService core (8 — row creation, body/template rendering, failure handling, SMS rejection, signature envelope linkage, missing content rejection, unknown channel rejection), retry logic (3 — retryable increments then fails, non-retryable fails immediately, retry-then-success), workflow integration (4 — step creates delivery + populates linkage + rejects missing channel/recipient), migrated callers (5 — statement/collections/invitation/alert-digest/signing-invite create delivery rows with template_key + caller_module populated), empty-alert short-circuit (1), admin API (3 — list tenant-scoped, get detail, cross-tenant 404). Plus 2 lint tests enforcing `resend` imports outside EmailChannel. Test fixture updates on D-2/D-4/D-5/D-6 suites for the new `document_deliveries` table. Total: 661 passed, 2 skipped (was 628 D-6, +31 delivery + 2 lint) — no regressions. Migration head: `r26_delivery_abstraction`. New architecture doc: `backend/docs/delivery_architecture.md` (full protocol walkthrough, channel registry, content resolution, retry semantics, how to add a new channel, migrated caller table). DEBT.md: 4 new entries (inline retry vs background queue, Resend webhook callbacks not wired, bulk send not implemented, scheduled_send column exists but unused). **Deferred per spec:** native email/SMS implementations (separate workstreams), bulk send, scheduled send, Resend webhook handling for `delivered` status, SendDocumentConfig frontend designer component (D-8 polish alongside the workflow builder pass).
- **Bridgeable Documents — Phase D-6 Cross-Tenant Document Fabric (complete):** Unified cross-tenant document sharing that replaces 4 ad-hoc mechanisms (statements-as-email-attachments, VaultItem.shared_with_company_ids for delivery media, raw cross-tenant statement rows, implicit legacy-vault-print sharing) with one `document_shares` table + service + lint-enforced query abstraction. **Migration `r25_document_sharing`**: creates `document_shares` (document_id + owner/target + permission/reason + granted/revoked timestamps + source_module, partial unique index on `(document_id, target) WHERE revoked_at IS NULL`), `document_share_events` (append-only audit of granted/revoked/accessed events, sequence by created_at DESC), and adds `intelligence_executions.caller_document_share_id` FK completing the symmetric Intelligence-linkage pattern. **Owner-tenant model:** Option A chosen over copy-on-share — one source of truth owned by the creating tenant, target tenants see the same storage_key via active share rows, revocation is a timestamp flag on the share row not a data delete. **`Document.visible_to(company_id)` class method** — returns `or_(Document.company_id == X, EXISTS(active share to X))` — the single SQL expression that unifies owned + shared visibility. Every cross-tenant-relevant query in `documents_v2.py` (`_get_visible_document`, `list_documents`, `list_document_log`) rewrote to use it. Owner-only operations (grant, revoke) use separate `_get_owned_document_or_404` helper that rejects even valid shared-read visibility because *writing* requires ownership. **`document_sharing_service`** with `grant_share` (requires active `PlatformTenantRelationship` either direction — structural boundary against ad-hoc proliferation), `revoke_share` (timestamp-only, future-access cutoff, explicit UI copy about already-downloaded copies being outside platform control), `ensure_share` (idempotent variant for auto-generated shares from migrated generators — bypasses relationship check because the generator's existence evidences the business relationship), `list_outgoing_shares`, `list_incoming_shares`, `record_access`, `list_events_for_share`. Re-granting after revocation creates a new row — audit trail stays linear, revoked rows preserved forever. **5 new API endpoints** on `/documents-v2/*`: `POST /{id}/shares` (grant — owner-only, 201), `GET /{id}/shares` (list outgoing — owner-only), `POST /shares/{id}/revoke`, `GET /shares/{id}/events` (visible to owner OR target), `GET /inbox` (documents shared TO this tenant, combines share + Document metadata + owner company name). **Generator migrations (3 of 6 document types from audit):** `cross_tenant_statement_service.deliver_statement_cross_tenant` registers a share alongside the existing ReceivedStatement row; `delivery_service._sync_media_to_vault` creates a per-delivery canonical `delivery_confirmation` Document + share (VaultItem writes keep running for backward compat); `legacy_vault_print_service.generate` auto-shares with `vault_manufacturer_company_id`. The other 3 (training certs, COIs, licensee transfer notifications) were identified in audit as conceptual cross-tenant flows without backing platform generators — D-6 infrastructure is ready for them; when their generators ship they call `ensure_share()` following the same pattern. **Admin UI:** new `/admin/documents/inbox` page (tenant's incoming shares with filters for document_type + include_revoked, clickable to DocumentDetail, status badges), new `DocumentSharesPanel` component on DocumentDetail (outbox table with grant/revoke actions, owner-only — target tenants see a read-only acknowledgment), fork dialog with typed target UUID + reason, explicit revoke confirmation warning about already-downloaded copies. Nav entry "Inbox" added under Platform admin. **Lint gate** (`test_documents_d6_lint.py`) enforces `Document.visible_to()` usage — direct `Document.company_id == X` filters are forbidden outside a permanent allowlist of owner-only paths (renderer, sharing service, legacy document service, signing services, generator paths, etc). 19 files on the allowlist with per-file justification comments. **Tests:** 29 new D-6 tests in `test_documents_d6_sharing.py` covering grant (7 — with/without relationship, self-target rejection, duplicate active rejection, event write, relationship both-directions, ensure_share idempotency, ensure_share bypass), revoke + re-grant (4), `visible_to()` (5 — owner sees, non-owner without share doesn't, share target sees, revoked hides, is_visible_to instance method), listing (3 — outgoing/incoming/exclude-revoked), audit append-only (2 — service has no update/delete, record_access doesn't mutate share), generator migrations (3 — statement creates share, legacy vault print helper, same-tenant noop), API permission gates (3 — cannot grant non-owned, owner can fetch owned, visible_document resolves shared), Intelligence linkage (1 — column exists). Plus 2 lint tests. Fixtures updated on D-1 + D-3 suites for new `document_shares` / `document_share_events` tables. Total: 628 passed, 2 skipped (was 597 D-5, +29 sharing + 2 lint) — no regressions once fixtures updated. Migration head: `r25_document_sharing`. Architecture doc `documents_architecture.md` extended with "Cross-tenant document sharing (D-6)" section covering model, grant/revoke semantics, `visible_to()` contract, migrated types, and inbox design. DEBT.md: pre-D-6 data backfill script flagged as needing future work (admin inbox shows post-D-6 shares only until backfill runs); 3 deferred document types flagged as "infra-ready, awaiting generators."
- **Bridgeable Documents — Phase D-5 Disinterment Migration + Anchor-Based Signature Overlay (complete):** Disinterment release form signing fully migrated from DocuSign to native signing. Cover-page signature approach replaced with PyMuPDF-based anchor overlay — signatures now render directly on the signature lines of the source document, matching the visual quality DocuSign provides. **Migration `r24_disinterment_native_signing`**: adds `disinterment_cases.signature_envelope_id` FK (nullable, partial index `WHERE NOT NULL`), keeps `docusign_envelope_id` + `sig_*` columns for backward compat. Adds `signature_fields.anchor_x_offset`, `anchor_y_offset`, `anchor_units` for fine-tuning placement without re-rendering the source template. **Anchor overlay engine** — two new internal modules in `app/services/signing/`: `_overlay_engine.py` (PyMuPDF-based single-pass overlay — opens source PDF once, calls `page.search_for(anchor)` to resolve positions, places every signature via `page.insert_image()`, returns modified bytes; missed anchors collected for audit events), `_signature_image.py` (PIL-based signature image generation — drawn signatures decode base64 PNG and resize preserving aspect ratio; typed signatures render via Caveat-Regular.ttf if bundled, PIL default otherwise, with auto-shrink to fit target bounds; 3× PPI for print-quality crispness). `signature_renderer.py` rewritten to use the new engine with a cover-page fallback if overlay fails (missing R2, PDF corruption, all anchors unresolvable). **Disinterment flow rewiring:** `disinterment_service.send_for_signatures` replaced the DocuSign-specific implementation with a native-signing call — creates envelope with 4 parties (`funeral_home_director`, `cemetery_rep`, `next_of_kin`, `manufacturer`) in sequential routing, each with an anchor-mapped signature field (`/sig_funeral_home/`, etc). Stricter validation: missing name/email for any party raises `ValueError` (DocuSign path silently skipped missing parties). **sig_* column sync:** `signature_service.sync_disinterment_case_status` called on every state transition (view, consent, sign, decline, void, complete) to mirror envelope party state into the legacy `sig_*` columns — existing code reading those fields continues to see coherent state. Case transitions to `signatures_complete` when envelope completes. **`FieldInput` enhancement:** now accepts `party_role` (decouples field definition from party ordering) OR `signing_order`. Also accepts `anchor_x_offset`, `anchor_y_offset`, `anchor_units`. **DocuSign deprecation (soft):** `docusign_service.py` and `docusign_webhook.py` stay alive for any in-flight DocuSign envelopes created pre-cutover. `create_envelope` emits `DeprecationWarning`; module docstrings flag deprecation with SQL query for tracking remaining legacy envelopes. No new DocuSign envelopes originate from the codebase. **Template already compatible:** the disinterment release-form template has styled `.sig-anchor` as `color: white; font-size: 1px` since D-1 — anchors are already invisible in rendered PDFs while remaining extractable by text search. No template update needed. **Frontend updates:** `disinterment-detail.tsx` reads `signature_envelope_id` in addition to `docusign_envelope_id`, shows "View signature envelope" link when native envelope exists (routes to `/admin/documents/signing/envelopes/{id}`), falls back to "Legacy DocuSign envelope: {id}" readout for pre-cutover cases. "Sent for signatures via DocuSign" toast → "Sent for signatures". **Visual verification:** end-to-end test renders a 4-party disinterment form and applies typed signatures; all 4 anchors resolve (x0=200, y spaced 60pt), all 4 overlays apply cleanly (`applied=4, missed=[]`), signed PDF grows from 3KB to 1.14MB (PNG signatures embedded). **Tests:** 22 new D-5 tests in `test_documents_d5_signing.py` covering anchor overlay primitives (5 — placement, multi-signature single pass, missing-anchor fallback, skip-without-position, offset respect), signature image generation (6 — drawn PNG, data-URI strip, typed PNG, party-resolver drawn/typed/empty paths), field party-role resolution (3), disinterment case sync (5 — consent/sign/complete/decline/null-docusign_envelope_id), DocuSign deprecation (3 — importable, warning emitted, webhook module still importable). Total: 597 passed, 2 skipped (was 575 D-4, +22 D-5) — no regressions. Migration head: `r24_disinterment_native_signing`. Architecture doc `signing_architecture.md` extended with "Anchor-based overlay" and "Disinterment migration (D-5)" sections. DEBT.md: marked cover-page-vs-overlay resolved, DocuSign-active reframed as "pending deletion after legacy envelopes resolve" with SQL tracking query, added cremation-authorization deferred entry. Cremation authorization migration remains deferred to a separate focused build as spec'd.
- **Bridgeable Documents — Phase D-4 Native Signing Infrastructure (complete):** Full e-signature infrastructure replacing DocuSign — US ESIGN Act compliant, runs in parallel with existing DocuSign integration. D-4 does NOT migrate any existing flows; D-5 will swap disinterment. **Migration `r23_native_signing`**: creates 4 tables (`signature_envelopes`, `signature_parties`, `signature_fields`, `signature_events` — the last is append-only by service-layer contract) and seeds 5 new platform templates (`pdf.signature_certificate` for the ESIGN-compliant Certificate of Completion, plus `email.signing_invite` / `signing_completed` / `signing_declined` / `signing_voided`). **Envelope state machine:** `draft → sent → in_progress → completed/declined/voided/expired`. **Party state machine:** `pending → sent → viewed → consented → signed/declined/expired`. Every state transition writes a `SignatureEvent` with monotonically-increasing `sequence_number` per envelope + `meta_json` for event-specific data (previous_active_version_id, rolled_back_to_version_id, etc). **`app.services.signing` package** — 5 modules: `token_service` (256-bit cryptographic tokens via `secrets.token_urlsafe(32)`), `signature_service` (envelope CRUD + lifecycle — `create_envelope`, `send_envelope`, `record_party_view`, `record_party_consent`, `record_party_signature`, `record_party_decline`, `void_envelope`, `resend_notification`, `complete_envelope`, `check_expiration`), `signature_renderer` (applies signatures to a new DocumentVersion via a signatures cover page — anchor-based inline overlay is D-5), `certificate_service` (renders Certificate of Completion via managed template with parties, signatures, IPs, hashes, event timeline), `notification_service` (5 email types via existing EmailService + managed templates). **Document hashing:** SHA-256 of the PDF captured at envelope creation + at completion for tamper detection. **Public signer routes** `/api/v1/sign/*` (no auth — `signer_token` is sole auth mechanism, in-process token-bucket rate limit of 10 req/min per token): `GET /{token}/status` (returns envelope + party status + is_my_turn + signed-by-previous-parties for sequential routing), `GET /{token}/document` (307 redirect to presigned R2 URL, records `link_viewed` event), `POST /{token}/consent` (records ESIGN consent text), `POST /{token}/sign` (captures signature + field values, advances routing, completes envelope if last party), `POST /{token}/decline` (cancels envelope). **Admin routes** `/api/v1/admin/signing/*` (admin-gated, tenant-scoped): `POST /envelopes` (create in draft), `POST /envelopes/{id}/send` (transition draft → sent, notify), `GET /envelopes` (list with status/document filters), `GET /envelopes/{id}` (detail with parties+fields), `POST /envelopes/{id}/void` (with reason, cancels pending parties), `POST /parties/{id}/resend` (resend invite email, increments counter), `GET /envelopes/{id}/events` (paginated audit timeline). **Frontend signer experience** `/sign/{token}` — 4-step public page: Welcome → Review (embedded iframe PDF) → Consent (ESIGN checkbox) → Sign (Draw canvas with mouse/touch support OR Type in Caveat-style script font). Terminal screens for expired/voided/declined/completed/not-my-turn. Decline modal with 10-500 char reason. **Frontend admin UI** under `/admin/documents/signing/`: `SigningEnvelopeLibrary` (table with status filter, "New envelope" button), `SigningEnvelopeDetail` (parties table with resend-notification, fields table, events timeline, void/send actions, download signed PDF + certificate when completed), `CreateEnvelopeWizard` (4-step: select document → add signers → add signature fields → review & create). Nav entry "Signing" under Platform admin. **Tests:** 31 new backend tests in `test_documents_d4_signing.py` covering envelope creation (5), send lifecycle (3), signer flow (6 — view/consent/sign/decline/completion/sequential-advance), field handling (2 — persistence, required-field enforcement), void + resend + expiration (3), tamper detection hash (2), audit integrity (3), public route token validation + rate limiting (2), permission gates (2), token uniqueness (2). Public routes tested end-to-end via FastAPI TestClient. Total: 575 passed, 2 skipped (was 544 in D-3) — no regressions. **Deferred per spec:** disinterment migration (D-5), workflow engine `request_signature` step type (D-5+), SMS verification (awaits native SMS), notarization (indefinite), bulk signing (indefinite), anchor-based inline signature overlay (D-5+), DocuSign deprecation (after D-5 migrations complete). Migration head: `r23_native_signing`. New architecture doc: `backend/docs/signing_architecture.md` (full state-machine + ESIGN compliance walkthrough + developer usage).
- **Bridgeable Documents — Phase D-3 Template Editing + Versioning (complete):** D-3 adds the editing surface on top of D-2's read-only template registry. Tenant admins can create draft versions, preview them (client-side Jinja substitution), test-render them (backend-backed, flagged test documents), and activate them with diff + changelog safety gates. Platform templates can only be edited by super_admins with typed-confirmation-text; tenant admins can **fork** a platform template to their tenant (creates a tenant-scoped copy with independent v1 starting history that auto-overrides the platform via D-2's hybrid lookup). **Migration `r22_document_template_editing`**: adds `documents.is_test_render` (Boolean, default False) with partial index `WHERE is_test_render = TRUE`, creates `document_template_audit_log` table (template_id + nullable version_id + action + actor + changelog + jsonb meta + created_at). **New model:** `DocumentTemplateAuditLog` mirrors `IntelligencePromptAuditLog`. **New service:** `template_validator.py` uses `jinja2.meta.find_undeclared_variables` (real AST parsing, auto-excludes loop locals) to detect `undeclared_variable` (error — blocks activation), `unused_variable` (warning — unless marked `{"optional": true}`), and `invalid_jinja_syntax` (error). **Extended `template_service.py`** with `create_draft`, `update_draft`, `delete_draft`, `activate_version`, `rollback_to_version`, `fork_platform_to_tenant`, `write_audit`, `list_audit`. Rollback creates a monotonically-numbered new active version cloning the retired target's content (target stays retired — no row is ever reactivated, keeping the audit trail linear). **`document_renderer.render()` accepts `is_test_render`** kwarg; production code path unchanged. **Document Log endpoint** excludes test renders by default — `include_test_renders=true` opts in. **8 new API endpoints** under `/api/v1/documents-v2/admin/templates/{template_id}/`: `GET /edit-permission` (preflight for UI — returns `can_edit`, `requires_super_admin`, `requires_confirmation_text`, `can_fork`); `POST /versions/draft` (409 if draft exists); `PATCH /versions/{id}` (drafts only); `DELETE /versions/{id}` (drafts only); `POST /versions/{id}/activate` (validates variable schema — 400 with issue list on errors; 409 on non-draft; writes audit row); `POST /versions/{id}/rollback`; `POST /fork-to-tenant`; `POST /versions/{id}/test-render` (any version status — draft/active/retired; PDF path creates flagged Document, HTML/text returns string); `GET /audit` (paginated timeline). Platform-global activations + rollbacks require `confirmation_text == template_key`. **Frontend — template editor** on `DocumentTemplateDetail.tsx`: mode toggle (view / edit), body + subject (email only) + variable_schema + css_variables + changelog fields, save draft / preview / test-render / activate / discard / cancel toolbar, draft indicator banner. **Five new modal components** in `components/documents/`: `TemplatePreviewModal` (client-side substitution, iframe HTML preview, disclaimer about control-flow limitations), `TemplateTestRenderModal` (JSON context editor, cost hint, iframe/PDF result), `TemplateActivationDialog` (side-by-side field diff, changelog editor, platform-template confirmation field, inline validation issues), `TemplateRollbackDialog` (target version content + changelog + confirmation), `TemplateForkDialog` (fork explanation with bullets). `DocumentTemplateLibrary` shows "draft" badge when a template has a draft in progress (backend preloads `has_draft` in one query, no N+1). **Tests:** 36 new D-3 tests in `test_documents_d3.py` covering draft lifecycle (5), activation (4), rollback (3), fork (4), variable schema validation (6), test render flag (2), audit log (5), Document Log test-render exclusion (2), permission gates (4), plus SQLite-in-memory fixture extensions. Total: 544 passed, 2 skipped — no regressions. Migration head: `r22_document_template_editing`. Architecture doc `backend/docs/documents_architecture.md` extended with "Template editing (D-3)" section covering draft lifecycle diagram, permission model table, validation semantics, test-render isolation, audit log shape. DEBT.md adds entries for client-side preview simplification and deferred email test sending (D-7).
- **Bridgeable Documents — Phase D-2 Template Registry + Admin Read Surface (complete):** Managed template registry replaces the file-based template loader from D-1. Two new tables (`document_templates`, `document_template_versions`) with hybrid scoping — platform templates have `company_id=NULL`, tenants override per `template_key`. Lookup is tenant-first-platform-fallback. Phase D-1 backbone extended to support `output_format: "pdf" | "html" | "text"` — PDF still creates canonical `Document` + `DocumentVersion` rows via WeasyPrint + R2; HTML and text render Jinja and return a `RenderResult` (no Document row, no R2 upload). `document_renderer.render_html()`, `render_text()`, and `render_pdf_bytes()` are new convenience wrappers. **Migration `r21_document_template_registry`** seeds 18 platform templates: 8 PDF migrated from `backend/app/templates/*.html`, 3 PDF migrated from inline Python strings (`pdf.social_service_certificate`, `pdf.legacy_vault_print`, `pdf.safety_program_base`), and 7 email templates from `email_service.py` + `legacy_email_service.py` (`email.base_wrapper`, `email.statement`, `email.collections`, `email.invitation`, `email.accountant_invitation`, `email.alert_digest`, `email.legacy_proof`). Each seed creates a template row + version-1 active row; partial unique index on `(company_id, template_key) WHERE deleted_at IS NULL` enforces scope uniqueness. **3 inline generators migrated:** `social_service_certificate_pdf.py`'s legacy `generate_social_service_certificate_pdf()` signature preserved (routes through `render_pdf_bytes`), new canonical `generate_social_service_certificate_document()` available for callers wanting a Document row; `legacy_vault_print_service.py::generate()` now produces a canonical `Document` via `document_renderer.render()` + keeps the static-disk secondary write for old URL consumers; `safety_program_generation_service._wrap_program_html` routes through `document_renderer.render_html(template_key="pdf.safety_program_base", ...)` with Claude's generated HTML embedded via `{{ ai_generated_html|safe }}`, and `generate_pdf()` now routes through `document_renderer.render()` to produce canonical Documents (fixes the pre-existing bug where it was inserting legacy Document rows against a canonical FK). **Email templates migrated:** every `EmailService` content-builder now routes through `document_renderer.render_html()` with the appropriate `email.*` template_key. Subject templates render alongside bodies; tenants customize branding by inserting a tenant-scoped row with the same template_key. **Admin UI read surface (4 pages at `/admin/documents/*`):** `DocumentTemplateLibrary` (filters: document_type / output_format / scope / status / search; URL-persistent), `DocumentTemplateDetail` (active version body + subject + variable schema + CSS vars + version history with click-to-view), `DocumentLog` (last-7-day default; filters: document_type / template_key / status / entity_type / intelligence_generated with clickable AI link to the source execution), `DocumentDetail` (full linkage summary, version history with per-version downloads, regenerate dialog). Nav entries added under Platform admin: "Documents" + "Document Log". **API additions on `/api/v1/documents-v2/*`:** `GET /log` (rich Document Log schema), `GET /admin/templates` (with `DocumentTemplateFilterResponse` paginated envelope), `GET /admin/templates/{id}`, `GET /admin/templates/{id}/versions/{version_id}`. Extended existing list endpoint with `template_key` + `intelligence_generated` filters. **Ruff rule tightening (TID251):** `weasyprint` imports forbidden outside `app/services/documents/**`. Permanent allowlist: renderer + `app/main.py` diagnostic import. Transitional allowlist (3 entries queued for post-D-2 migration): `pdf_generation_service.generate_template_preview_pdf`, `quote_service.generate_quote_pdf`, `wilbert_utils` Wilbert form PDF. Enforcement via pytest `test_documents_d2_lint.py` (ruff not installed); test fails if any new weasyprint usage appears outside the allowlist, and if any transitional entry stops using weasyprint (forcing removal). **Tests:** 23 new D-2 tests in `test_documents_d2.py` (template registry scoping, renderer format dispatch, migrated generators, migrated email templates, template_service visibility rules, lint smoke) + 3 lint tests in `test_documents_d2_lint.py`. Total: 508 passed, 2 skipped — no regressions. Migration head: `r21_document_template_registry`. Architecture doc: `backend/docs/documents_architecture.md` updated with template registry + hybrid scoping + seeded-templates table + D-3 roadmap. DEBT.md marked inline-HTML generators + email templates resolved; flagged 3 remaining transitional weasyprint call sites + template-file-system cleanup.
- **Bridgeable Documents — Phase D-1 Backbone (complete):** Canonical `Document` + `DocumentVersion` model replaces ad-hoc PDF generation across the platform. Every template-rendered or AI-generated PDF now flows through `app.services.documents.document_renderer.render()` — Jinja template load → WeasyPrint HTML→PDF → R2 upload at `tenants/{company_id}/documents/{document_id}/v{n}.pdf` → inserts `documents` row + first `document_versions` row with `is_current=True`. Re-renders via `rerender()` flip the prior version's `is_current` and append a new version. The renderer computes a SHA-256 `rendering_context_hash` of the JSON-serialized context dict (stored on each version) for future dedup/change detection. **Migration `r20_documents_backbone`**: renames existing `documents` → `documents_legacy` (renaming its `ix_documents_*` indexes to `ix_documents_legacy_*` to avoid collision), creates the canonical `documents` table with polymorphic entity linkage (`entity_type`/`entity_id`) AND 7 specialty FKs (`sales_order_id`, `fh_case_id`, `disinterment_case_id`, `invoice_id`, `customer_statement_id`, `price_list_version_id`, `safety_program_generation_id`), source linkage (`caller_module`, `caller_workflow_run_id`, `caller_workflow_step_id`, `intelligence_execution_id`), and `document_versions` with a partial unique index on `(document_id) WHERE is_current=true`. Also adds `caller_document_id` FK on `intelligence_executions` for the reverse linkage (which AI call fed which document). **Coexistence with legacy model:** both `app.models.canonical_document.Document` (canonical) and `app.models.document.Document` (legacy, now backed by `documents_legacy`) live in the SQLAlchemy registry — string-based `relationship("Document", ...)` resolution hits a disambiguation error, so code uses direct class reference (`relationship(Document, ...)`) or the fully-qualified string `"app.models.canonical_document.Document"`. `SafetyProgramGeneration.pdf_document` FK rebound to canonical. **4 generators migrated:** `disinterment_pdf_service.generate_release_form_document()`, `pdf_generation_service.generate_invoice_document()`, `price_list_pdf_service.generate_price_list_document()`, and new `statement_pdf_service.generate_statement_document()` (wiring previously-orphaned statement Jinja templates). All legacy byte-returning functions (`generate_release_form_pdf`, `generate_invoice_pdf`, `generate_price_list_pdf`, `generate_release_form_base64`) preserved — they internally call the Document path then fetch bytes from R2, so existing callers in `routes/sales.py`, `routes/price_management.py`, and `docusign_service.py` keep working. **Workflow engine `generate_document` action wired:** previously a stub returning `pdf_url: None`, now `_handle_generate_document()` validates config, resolves `{input.*}`/`{output.*}` variables in context, calls `document_renderer.render()` with workflow linkage auto-populated from `run.trigger_context` (including entity_type→specialty FK routing via `_ENTITY_TYPE_TO_DOCUMENT_KWARG`), returns `{document_id, storage_key, pdf_url, version_number, document_type}` for downstream steps. **API at `/api/v1/documents-v2/*`** (admin-gated, tenant-scoped): GET list with filters (document_type, entity_type/entity_id, status, date range), GET detail with full version history, GET download (307 → presigned R2 URL, 1h TTL), GET version-specific download, POST regenerate. Legacy `/api/v1/documents/*` routes continue to serve the old Document model against `documents_legacy`. **Frontend:** `GenerateDocumentConfig.tsx` replaces the generic JSON editor in WorkflowBuilder when `action_type === "generate_document"` — dropdowns for template_key + document_type, title/description fields, context JSON editor. **Not yet migrated (Phase D-2):** Social Service Certificate inline-HTML generator, Legacy Vault Print inline-HTML, Safety Program runtime Claude-generated HTML, and email templates in `email_service.py` + `legacy_email_service.py`. **Tests:** 18 new Phase D-1 tests in `test_documents_d1.py` covering renderer (creates doc+version, storage_key convention, linkage population, SHA-256 context hash, template/WeasyPrint failure paths), rerender (new version + is_current flip, missing-document error), disinterment generator (produces Document), workflow action (creates Document, linkage from trigger_context, rejects missing template_key), and API (tenant scoping, filtering, detail+versions, soft-delete hiding, require_admin declaration lint). Total: 261 passed, 2 skipped — no regressions. Migration head: `r20_documents_backbone`. Architecture doc: `backend/docs/documents_architecture.md`. Debt tracked in `backend/docs/DEBT.md` → "Legacy document models coexist with canonical Document".
- **Bridgeable Intelligence — unified AI layer (complete):** Every AI call in the platform routes through `app.services.intelligence.intelligence_service.execute(prompt_key=..., variables=..., company_id=..., caller_module=..., caller_entity_*=...)`. The managed prompt library has 73 active platform-global prompts covering Scribe, accounting agents, briefings, command bar, NL Overlay, Ask Assistant, urn pipeline, safety, CRM, KB, onboarding, training, compose, workflows, and vision (check-image + PDF extraction). Every call produces an `intelligence_executions` audit row with prompt_id, model_used, input/output tokens, cost_usd, latency_ms, and typed caller linkage (`caller_fh_case_id`, `caller_agent_job_id`, `caller_workflow_run_id`, `caller_ringcentral_call_log_id`, `caller_kb_document_id`, `caller_price_list_import_id`, `caller_accounting_analysis_run_id`, `caller_command_bar_session_id`, `caller_conversation_id`, `caller_import_session_id`). Vision prompts use `content_blocks=[{type: "image"|"document", source: {type: "base64", media_type: ..., data: ...}}]`; raw base64 is redacted from `rendered_user_prompt` (sha256 + bytes_len only). Migration completed across 9 sub-phases (Phase 1 backbone → 2a/2b initial migrations → 2c-0a prompt batch + linkage columns → 2c-0b multimodal support → 2c-1/2/3/4 caller migrations → 2c-5 final cleanup). 14 direct-SDK callers + ~25 legacy-wrapper callers + 6 architectural-concern callers all migrated. `ai_service.py` legacy wrapper deleted. `/ai/prompt` endpoint deprecated (sunset 2027-04-18), internally routed through `legacy.arbitrary_prompt` managed prompt. TID251 ruff rule + pytest-based lint gate forbid any new `anthropic` SDK or `call_anthropic` imports outside the Intelligence package. Admin API at `/api/v1/intelligence/` exposes prompts/versions/executions/experiments/models/conversations CRUD. Migration head: `r18_intelligence_vision_support` (r16 backbone + r17 linkage columns + r18 vision columns). Audit artifact: `backend/docs/intelligence_audit_v3.md` (2,559 lines, every call site documented verbatim). Pre-existing bugs uncovered during migration tracked in `backend/docs/BUGS.md`. Intelligence tests: 154 passing. Total seed prompts: 73 platform-global (30 Phase 1 + 1 Phase 2a + 2 Phase 2b + 40 Phase 2c-0a + 3 Phase 2c-5).
- **Multi-Location Support (Model A — Single Tenant, Multiple Locations):** Location-aware architecture enabling multi-plant licensees (WMA president demo target: 11 locations). **Architectural principle:** one company = one tenant = one vault = one login domain. Locations are a filter/dimension, not separate tenants. **Single-location companies see zero UI change** — one implicit primary location created silently, no selector visible. **Database:** 2 new tables (`locations`, `user_location_access`), `location_id` FK added to 7 existing tables (`sales_orders`, `deliveries`, `vault_items`, `work_orders`, `equipment`, `employee_profiles`, `production_log_entries`). Data migration creates primary location per company and assigns all existing records. All existing users get all-location access (null location_id = admin). Migration `vault_04_multi_location`. **Backend:** `location_service.py` with 13 methods — `get_location_filter()` is the core query-filtering method used by all services. `get_locations_overview()` returns per-location stats with attention/on_track/no_activity status. 10 API endpoints under `/api/v1/locations/`. Vault service updated: `query_vault_items`, `get_vault_summary`, `get_upcoming_events`, `create_vault_item` all accept `location_id`. **Frontend:** `LocationProvider` context (fetches locations, persists selection to localStorage, exposes `isMultiLocation` flag). `LocationSelector` — compact popover in sidebar, renders null for single-location. `LocationsOverview` page (`/locations`) — grid of location cards with stats (the jaw-drop screen for the WMA demo). `LocationSettings` page (`/settings/locations`) — full CRUD + per-location user access management. `TransferRequest` component for cross-location inventory transfers via vault items. Navigation service updated with `requiresMultiLocation` filter. **Key design decisions:** location_id nullable everywhere (backward compatible), user_location_access.location_id=NULL means all-access, overview endpoint returns aggregated cross-location stats.
- **Bridgeable Core UI — Universal Command Bar, Entity Timeline, Notifications:** Three-surface interaction layer built on top of every vertical. **Universal Command Bar** (`Cmd+K`/`Ctrl+K`): Alfred-style search + action + navigation + NLP. Claude API intent classification with 800ms timeout, falls back to local fuzzy search. Numbered shortcuts `Cmd+1`–`Cmd+5` for keyboard-first execution. Voice input via Web Speech API with real audio waveform visualization (Web Audio API AnalyserNode). Action registry pattern (`actionRegistry.ts`) with 13 manufacturing actions, extensible per vertical. `CommandBarProvider` wraps the entire app. **Entity Timeline** (`EntityTimeline.tsx`): right-side slide-over panel (420px) showing vault history for any record, grouped by date. Filter tabs (All/Events/Documents/Communications). `HistoryButton` component added to CRM company detail and sales order detail pages. **Smart Plant Voice Mode** (`SmartPlantCommandBar.tsx`): touch-first variant for plant floor terminals — auto-execute on high confidence (>0.92), large touch buttons for medium confidence. **Backend:** 3 new endpoints under `/api/v1/core/` (`POST /command`, `GET /recent-actions`, `POST /log-action`). `core_command_service.py` with entity pre-resolution (companies, orders, products), Claude API classification, and local search fallback. **Database:** `user_actions` table for command bar action history. Migration `vault_03_core_ui`. **Sidebar:** old AI command bar replaced with `⌘K` trigger button that opens the universal command bar. Migration head: `vault_03_core_ui`.
- **Bridgeable Core Vault Migration (Foundation + Steps 1-4):** Unified data layer via `Vault` and `VaultItem` models. Two new tables: `vaults` (company-level containers) and `vault_items` (30+ column flexible items supporting documents, events, communications, reminders, assets, compliance items, and production records). `VaultItem` uses `item_type` discriminator with `event_type`/`event_type_sub` for domain specificity, `metadata_json` JSONB for domain-specific fields, `shared_with_company_ids` JSONB for cross-tenant visibility, and `source_entity_id` for back-reference to legacy records. **Dual-write pattern** added to 5 services: `delivery_service.py` (deliveries, routes, media → vault events/documents), `work_order_service.py` (pour events → vault), `operations_board_service.py` (production log → vault), `safety_service.py` (training events, attendee records → vault events/documents). **Vault compliance sync** (`vault_compliance_sync.py`): scans overdue inspections, expiring training certs, and regulatory deadlines (OSHA 300A), creates/updates VaultItems with deduplication via `source_entity_id` keys. **Calendar sync**: iCal feed endpoint (`GET /vault/calendar.ics`) with token-based auth, role-filtered events. `calendar_token` column added to users. **10 API endpoints** under `/api/v1/vault/`: items CRUD, summary, upcoming-events, cross-tenant, calendar.ics, compliance sync, calendar token generation. **Data migration** (`vault_02_data_migration`): idempotent SQL migration of existing deliveries, routes, pour events, production logs, training events, and training records into vault_items (source="migrated"). Migration `vault_01_core_tables` creates tables + indexes (composite on company_id/item_type/event_start, GIN on metadata_json). Migration head: `vault_02_data_migration`.
- **PDF-Native Image Extraction for Urn Catalog:** The Wilbert PDF catalog is now the sole reliable source of truth for product images. `extract_product_images()` in `wilbert_pdf_parser.py` extracts embedded JPEG images from each catalog page via PyMuPDF's `page.get_images()` and `doc.extract_image()`, filters by size (min 80x80px) and aspect ratio (max 4:1), converts to JPEG at 85% quality, and associates with SKUs via catalog page mapping. `_extract_and_upload_images()` in `wilbert_ingestion_service.py` uploads extracted images to R2 at `tenants/{company_id}/urn_catalog/images/{sku}.jpg` and sets `r2_image_key` on the product. Images are resolved to public URLs server-side in the product list/detail endpoints via `_resolve_product_image_url()`. Web enrichment (`enrich_products_from_web`) now skips image fetch for products with existing `r2_image_key` (PDF images take precedence), and wraps individual product enrichment in try/except for resilience. SECTION_MAP updated from Volume 11 (88 pages) to Volume 8 (78 pages). New `GET /urns/catalog/sync-status` endpoint returns product completeness metrics (images, descriptions, prices, dimensions). Frontend `urn-catalog.tsx` updated: data completeness bar with green/amber indicators, larger product image in expanded detail row, `r2_image_key` indicator, sync status after each operation. `CatalogIngestionResponse` and `CatalogPdfFetchResponse` schemas now include `images_uploaded` count.
- **Monthly Safety Program Generation:** AI-powered monthly safety program creation with OSHA regulatory scraping. Full pipeline: `osha_scraper_service.py` scrapes OSHA standard pages (httpx + BeautifulSoup, 14 standard URL mappings), `safety_program_generation_service.py` generates 7-section programs via Claude Sonnet (Purpose/Scope, Responsibilities, Definitions, Procedures, Training, Recordkeeping, Review), WeasyPrint renders professional PDF with cover page. Table: `safety_program_generations` with full lifecycle tracking (OSHA scrape → generation → PDF → approval). Approval workflow: draft → pending_review → approved/rejected. On approve: creates/updates `SafetyProgram` record. Scheduler job: 1st of month at 6am ET via `job_safety_program_generation`. Morning briefing integration: shows pending reviews count, missing monthly generations, failed generations. Permission: `safety.trainer` (view, generate, approve). 7 API endpoints under `/safety/programs/` (list, detail, generate, ad-hoc topic, approve, reject, regenerate-pdf). Frontend: `safety-programs.tsx` rewritten with AI Generated + Manual tabs. Migration `r15_safety_program_generation`. 12 E2E tests (all passing). Route ordering fix: generation router registered before safety router to prevent `{program_id}` catch-all conflict.
- **Urn Catalog PDF Auto-Fetch:** One-click "Fetch & Sync Catalog" replaces manual PDF upload. `UrnCatalogScraper.fetch_catalog_pdf()` downloads the Wilbert catalog PDF from a direct URL (`https://www.wilbert.com/assets/1/7/CCV8-Cremation_Choices_Catalog.pdf`), computes MD5 hash for change detection, archives to R2, and triggers `ingest_from_pdf()` if changed. Fallback URL resolver (`_resolve_pdf_url()`) scrapes the catalog landing page if the direct URL changes. Web enrichment runs automatically in background via FastAPI `BackgroundTasks` (creates its own DB session to avoid lifecycle issues). UI button always uses `force=true`; hash-based skip is for automated/scheduled runs. 3 new columns on `urn_tenant_settings` (catalog_pdf_hash, catalog_pdf_last_fetched, catalog_pdf_r2_key). Migration `r14_urn_catalog_pdf_fetch`. Frontend simplified: single "Fetch & Sync Catalog" button with collapsed manual upload fallback. 2 new E2E tests in standalone `urn-catalog-pdf-fetch.spec.ts`. PyMuPDF (`fitz`) dependency added to `requirements.txt` (was documented but missing, causing silent 0-product returns on staging).
- **Social Service Certificates:** Government benefit program delivery confirmations auto-generated when Social Service Graveliner orders are delivered. Table: `social_service_certificates` with status lifecycle (pending_approval → approved → sent, or voided). `social_service_certificate_service.py`: `generate_pending()` auto-creates on delivery completion (identifies SS products by pattern matching), `approve()` triggers PDF email to funeral home, `void()` with reason. WeasyPrint PDF generator (`pdf_generators/social_service_certificate_pdf.py`) produces professional letter-size document with company letterhead, deceased info, product details, and delivery timestamp. 6 API endpoints under `/api/v1/social-service-certificates/` (requires `invoice.approve` permission): pending list, all with status filter, detail, approve, void, PDF download (presigned R2 URL). Frontend page with status filter, approve/void/view-pdf actions, color-coded status badges. Migration `r13_social_service_certificates`.
- **Wilbert Urn Catalog Ingestion Pipeline:** Full ingestion system for Wilbert's 88-page PDF catalog. `wilbert_pdf_parser.py`: PyMuPDF-based line-by-line state machine parser extracts 259 products with SKUs (P-prefix urns, D-prefix jewelry), dimensions (height, width/diameter, depth, cubic inches), engravability flags, material categories (Metal/Wood/Stone/Glass/Ceramic/etc.), companion/memento linkage, and catalog page numbers. `wilbert_ingestion_service.py`: orchestrator with `ingest_from_pdf()` (PDF→upsert by SKU), `apply_bulk_markup()` (cost→retail with rounding), `import_prices_from_csv()`. `urn_catalog_scraper.py`: rewritten with real CSS selectors from wilbert.com research crawl (`.product-list`, `h1.item-name`, `div.item-desc p`, `#productImage img.main-image`), 9 category URLs, SKU inference from image filenames, `enrich_products_from_web()` for descriptions/images. `wilbert_scraper_config.py`: all real selectors, category URLs, site origin. Migration `r12_urn_catalog_ingestion`: 11 new columns on `urn_products` (height, width_or_diameter, depth, cubic_inches, product_type, companion_of_sku, wilbert_description, wilbert_long_description, color_name, catalog_page, r2_image_key), 3 new columns on `urn_catalog_sync_logs` (sync_type, pdf_filename, products_skipped), 2 new indexes. 6 new API endpoints: `POST /urns/catalog/ingest-pdf` (file upload), `POST /urns/catalog/enrich-from-web`, `PATCH /urns/products/{id}/pricing`, `POST /urns/pricing/bulk-markup`, `POST /urns/pricing/import-csv`, `POST /urns/pricing/import-json`. Frontend `urn-catalog.tsx` rewritten: pricing columns (Cost, Retail, Margin%) with inline click-to-edit, "Sync from Wilbert" dialog (PDF upload + optional web enrichment), Bulk Markup tool (filter by material/type, % + rounding), CSV Price Import, material/type filter dropdowns, expandable detail rows (dimensions, descriptions, companion links), unpriced product amber warnings. Design decisions: prices uploaded/entered in-platform (no WilbertDirect scraping), Wilbert marketing materials/images OK (licensee rights), font options deferred to tenant settings.
- **Urn Sales Extension (Complete):** Full urn sales lifecycle as a tenant extension (`urn_sales`). 6 tables: `urn_products` (product catalog with stocked/drop-ship source), `urn_inventory` (stocked product tracking), `urn_orders` (order management with fulfillment_type), `urn_engraving_jobs` (two-gate proof approval), `urn_tenant_settings` (configurable lead times, approval windows), `urn_catalog_sync_logs` (sync audit trail). `urn_product_service.py`: CRUD + AI-powered search (Claude extracts search terms, ILIKE query with relevance scoring). `urn_order_service.py`: create/confirm/cancel/deliver lifecycle, stocked inventory reservation on confirm, auto-release on cancel, ancillary items for scheduling board (configurable window, default 3 days), drop-ship visibility feed, search by FH/decedent. `urn_engraving_service.py`: two-gate proof approval — Gate 1: FH approval via token-based email (72hr expiry, no auth required), Gate 2: staff approve/reject. Wilbert form generation (PDF via weasyprint). Auto-send FH email when `fh_contact_email` exists on proof upload. Keepsake set support: scaffolds N engraving jobs from companion_skus, propagate specs to companions, all-jobs approval gate. Verbal approval flagging (stores transcript excerpt, does NOT auto-approve). Correction summary for resubmissions. `urn_intake_agent.py`: email intake + proof matching. 41 API endpoints under `/api/v1/urns/`. Frontend: `urn-catalog.tsx` (product management), `urn-orders.tsx` (order dashboard with status filters), `urn-order-form.tsx` (create order), `proof-approval.tsx` (public FH approval page). Migration `r11_urn_sales`. Extension gated via `require_extension("urn_sales")`. 37 E2E Playwright tests (all passing).
- **Year-End Close + Tax Package Agents (Phases 11 & 12) — ACCOUNTING AGENT SUITE COMPLETE:** YearEndCloseAgent (Phase 11): Extends MonthEndCloseAgent (not BaseAgent) — inherits all 8 month-end steps + 5 new year-end steps (13 total). execute() validates Dec 1–Dec 31 period, fails immediately if invalid. New steps: full_year_summary (full year + 4 quarters income statement, vs approved AnnualBudgetAgent with 15% variance threshold, vs prior year), depreciation_review (JournalEntryLine pattern matching for depreciation/amortization, 20% monthly variance threshold excluding December), accruals_review (December accrual keyword matching with January reversal check), inventory_valuation (InventoryItem × Product.cost_price, flags no-cost products), retained_earnings_summary (net income from step 9, distribution keyword matching, beginning RE from equity accounts). Uses FULL approval path (statement run + period lock, same as MonthEndCloseAgent). TaxPackageAgent (Phase 12): READ-ONLY capstone agent, extends BaseAgent. 5 steps: collect_agent_outputs (queries completed agent_jobs for tax year, groups by job_type, tracks month_end_closes 0-12), assess_completeness (CRITICAL gaps: missing year_end_close/1099_prep, WARNING: months not closed/missing tax estimates, INFO: optional agents; readiness_score = required_score × 0.6 + recommended_score × 0.4), compile_financial_statements (extracts from year_end_close report_payload), compile_supporting_schedules (6 schedules: A=1099 vendors, B=tax estimates, C=inventory, D=AR aging, E=budget vs actual, F=anomaly summary), generate_report (professional HTML with cover page, TOC, financial statements, supporting schedules, CPA disclaimer). Uses SIMPLE approval (no period lock). All 12 AgentJobType enum values now registered in AgentRunner. 19 tests in `test_phase_11_12_agents.py`. Total agent tests: 105 passing.
- **1099 Prep + Annual Budget Agents (Phases 10 & 13):** Prep1099Agent: 4 steps (compute vendor payment totals via VendorPaymentApplication.amount_applied, classify 1099 eligibility — INCLUDE/NEEDS_REVIEW/BELOW_THRESHOLD based on is_1099_vendor flag and $600 IRS threshold, flag data gaps — missing tax IDs CRITICAL, unreviewed vendors WARNING, w9_tracking_not_implemented INFO always, orphaned payments WARNING, generate HTML report with filing deadline banner and CPA disclaimer). `mask_tax_id()` helper — never stores or displays full tax IDs. AnnualBudgetAgent: 5 steps (pull prior year actuals via get_income_statement for full year + 4 quarters, compute quarterly seasonal shares, apply growth assumptions — defaults 5% rev / 3% COGS / 3% expense overridable via report_payload.assumptions, generate budget lines with quarterly_breakdown matching Phase 9 _extract_budget_for_period contract Q1-Q4 keys, generate HTML report with assumptions banner and scenario re-run guidance). Flags budget_projects_loss WARNING if net income < 0. Budget stored at report_payload.budget for Phase 9 consumption. Both added to SIMPLE_APPROVAL_TYPES — no financial writes, no period lock. 10 agents now registered in AgentRunner. 17 tests in `test_phase_10_13_agents.py`. Total agent tests: 86 passing.
- **Inventory Reconciliation + Budget vs. Actual Agents (Phases 8–9):** InventoryReconciliationAgent: 6 steps (snapshot current inventory with last transaction lookup, verify transaction integrity — InventoryItem.quantity_on_hand vs InventoryTransaction.quantity_after, compute reserved quantity from confirmed/processing SalesOrderLines, reconcile production vs deliveries — two-method comparison of transaction ledger vs ProductionLogEntry-minus-delivered, check physical count freshness with 90/180 day thresholds, generate HTML report). Anomaly types: `inventory_balance_mismatch` (CRITICAL), `inventory_no_transaction_history`, `inventory_oversold` (CRITICAL), `inventory_at_risk`, `inventory_reconciliation_variance` (WARNING ≤2 units, CRITICAL >2), `inventory_unplanned_production`, `inventory_count_overdue`, `inventory_large_count_adjustment`. BudgetVsActualAgent: 4 steps (get income statement for period + YTD via get_income_statement(), get comparison basis with priority: formal_budget > prior_year_same_period > prior_quarter > none, compute variances at summary + GL line level with 15% threshold, generate HTML report with comparison basis banner). Favorable direction: revenue/gross_profit/net_income ABOVE = favorable; COGS/expenses BELOW = favorable. Both added to SIMPLE_APPROVAL_TYPES — no financial writes, no period lock on approval. 8 agents now registered in AgentRunner. 16 tests in `test_phase_8_9_agents.py`. Total agent tests: 69 passing.
- **Expense Categorization + Estimated Tax Prep Agents (Phases 6–7):** ExpenseCategorizationAgent: 4 steps (find uncategorized/orphaned VendorBillLines, classify via Claude Haiku with 0.85 confidence threshold, map to GL accounts via TenantGLMapping, generate HTML report). On approval: writes high-confidence categories to VendorBillLine.expense_category; low-confidence lines require manual review (Phase 6b). EstimatedTaxPrepAgent: 5 steps (income statement via get_income_statement(), YTD annualization, quarterly tax liability with federal 20–25% range + state TaxRate lookup, prior payment detection via JournalEntry/VendorBill, HTML report with mandatory CPA disclaimer). Purely informational — no financial writes on approval. Both added to SIMPLE_APPROVAL_TYPES. Fixed naive datetime comparison bug in approval_gate.py token expiry check. 16 tests in `test_phase_6_7_agents.py`. Total agent tests: 53 passing.
- **Three Weekly Agents (Phases 3–5):** ARCollectionsAgent, UnbilledOrdersAgent, CashReceiptsAgent. All registered in `AgentRunner.AGENT_REGISTRY`. Approval gate updated with `SIMPLE_APPROVAL_TYPES` set for weekly agents — no period lock, no statement run on approval. ARCollectionsAgent: 4 steps (AR snapshot, tier classification, Claude-drafted collection emails with fallback templates, report). UnbilledOrdersAgent: 3 steps (find unbilled delivered orders, pattern analysis — repeat customers/backlog growth/high value, report). CashReceiptsAgent: 4 steps (collect unmatched payments, auto-match via 4 rules — exact+customer/exact+any/subset-sum/unresolvable, flag stale payments, report). Auto-match writes only in non-dry-run mode via `guard_write()`. 15 tests in `test_phase_3_4_5_agents.py`. Total agent tests: 49 passing.
- **MonthEndCloseAgent (Phase 2):** First real agent implementation. 8-step pre-flight verification: invoice coverage, payment reconciliation, AR aging snapshot, revenue summary with adaptive outlier detection, customer statement flag detection (reuses `statement_generation_service`), cross-step anomaly checks, prior period comparison, executive report generation. On approval: triggers `generate_statement_run()`, auto-approves unflagged statement items, locks period. Agent registered in `AgentRunner.AGENT_REGISTRY`. Anomaly types: `uninvoiced_delivery`, `invoice_amount_mismatch`, `unmatched_payment`, `duplicate_payment`, `overdue_ar_90plus`, `revenue_outlier`, `low_collection_rate`, `inactive_customer`, `low_invoice_volume`, `statement_run_conflict`, and 6 statement flags (`statement_open_dispute`, `statement_high_balance_variance`, etc.). Seed script: `scripts/seed_agent_test.py`. 11 tests.
- **Accounting Agent Infrastructure (Phase 1):** Built shared foundation for 13 accounting agents. 5 tables (`agent_run_steps`, `agent_anomalies`, `agent_schedules`, `period_locks` + extended `agent_jobs`), base agent class, approval gate with token-based email workflow, period lock service with financial write guards on invoices/payments, agent runner with validation, full API endpoints, frontend dashboard + approval review page. Migration `r10_agent_infra`. 22 tests passing.
- **Document Service R2 Migration:** `document_service.py` rewritten for Cloudflare R2 storage. Download route returns 307 redirect to signed URLs. Lazy migration for existing local files. Admin bulk migration endpoint.
- **Platform rename:** "ERP Platform" → "Bridgeable" throughout frontend. `VITE_APP_NAME=Bridgeable` in `.env`. `APP_NAME` default in `config.py` changed to `"Bridgeable"`. `SUPPORT_EMAIL` changed to `"support@getbridgeable.com"`.
- **Domain migration:** All `yourerp.com` references replaced with `VITE_APP_DOMAIN`. `platform.app` fallbacks replaced with `getbridgeable.com`. `tenant.ts` comments updated. `company-register.tsx` fallback fixed.
- **`backend/.env.example`:** Updated header, corrected `DATABASE_URL` to `bridgeable_dev`, documented all vars (Twilio, Google Places, `PLATFORM_ADMIN_*`).
- **APScheduler:** Installed (`>=3.10.0`). `start_scheduler()` / `shutdown_scheduler()` called from FastAPI lifespan. 13 jobs registered.
- **Proactive agents:** 6 new agent functions in `proactive_agents.py` — wired into scheduler nightly/weekly runs.
- **NPCA moved to extension-only:** Dashboard `isNpcaEnabled` now uses `hasModule("npca_audit_prep")`. `/npca` placeholder page created at `frontend/src/pages/compliance/npca-audit-prep.tsx`.
- **`npca_certification_status`:** Added to `CompanyResponse` Pydantic schema and frontend `Company` type so `/auth/me` returns it.
- **Migration chain fixes:** 4 duplicate revision IDs renamed. Merge migrations created. Table names corrected (`payments→customer_payments`, `orders→sales_orders`, `bills→vendor_bills`).
- **Idempotent migrations:** `alembic/env.py` monkey-patches `add_column`, `create_table`, `create_index`.
- **Environment separation:** Local `.env` → `bridgeable_dev`. Railway credentials in Railway dashboard only.
- **CORS:** `.*getbridgeable\.com` regex in production.
- **`StatementRunItem` ORM model:** Added retroactively.

## 15. Known Issues and Tech Debt

### Active Issues
- **Orphaned `tenant_settings` table** — migrations create it, but app code uses `Company.settings_json` exclusively.
- **COA extraction not implemented** — `tenant_accounting_import_staging` exists but no QBO/Sage API extraction. Only Sage CSV upload works.
- **Sage API version detection** — always returns "could not reach server"; CSV is the only real Sage path.
- **`/npca` is a placeholder** — nav item links to it; only shows "coming soon". No actual NPCA audit features built.
- **Audit package generation is a stub** — `report_intelligence_service.py:195` has a TODO for async Claude call.
- **Accountant invitation email** — `accounting_connection.py:304` has a TODO; email is not sent.
- **~30 unimplemented agent jobs** — schemas and services exist, job runners not built.

### Tech Debt
- `@app.on_event("startup/shutdown")` — deprecated FastAPI pattern; should migrate to lifespan context manager
- No query caching — all reads hit PostgreSQL directly
- AIService creates new Anthropic client per call — should use connection pooling
- `StatementRunItem` model added retroactively — verify all service code references it correctly
- `APP_NAME` used as Redis key prefix in `job_queue_service.py` — key shifts if `APP_NAME` env changes

## 16. Next Priorities

### Top Priority — Data Migration Tool
**Waiting on:** Sage CSV export files from Sunnycrest accountant (invoice history, customer list, cash receipts).

Once received:
1. Complete COA AI analysis flow end-to-end with real Sage data
2. Build customer import (Sage customer list → Bridgeable customers)
3. Build AR import (invoice history → open invoices + aging balances)
4. Build payment history import
5. Validate imported balances against Sunnycrest's current Sage totals

### Short Term (13 simpler agent jobs)
`STALE_DRAFT_MONITOR`, `REVERSAL_RUNNER`, `PO_DELIVERY_MONITOR`, `RECONCILIATION_MONITOR`, `ABANDONED_RECONCILIATION_MONITOR`, `STATEMENT_RUN_MONITOR`, `FINANCE_CHARGE_REMINDER`, `EXEMPTION_EXPIRY_MONITOR`, `1099_MONITOR`, `DELIVERY_WEEKLY_REVIEW`, `FINANCE_CHARGE_INSIGHT_JOB`, `DISCOUNT_UPTAKE_JOB`, `OUTCOME_CLOSURE_JOB`

### Medium Term
- Build actual NPCA Audit Prep feature (compliance score engine, gap analysis, audit package ZIP)
- ~~Staging environment on Railway~~ ✅ Done (April 2026)
- ~~End-to-end testing with real Sunnycrest data~~ ✅ Done (April 2026)
- Performance optimization for report generation
- Migrate FastAPI `@app.on_event` to lifespan context manager

## 17. Recent Build Sessions

### Session: April 16, 2026 — Bridgeable Core Vault Migration

Unified data layer — every feature reads from and writes to vault_items.

**New models:** `Vault` (container per company), `VaultItem` (30+ columns, JSONB metadata)

**Dual-write integration (5 services):**
- `delivery_service.py` — deliveries → delivery events, routes → route events, media → delivery_confirmation docs
- `work_order_service.py` — pour events → production_pour events
- `operations_board_service.py` — production log → production_record items
- `safety_service.py` — training events → safety_training events, attendees → training_completion docs

**Vault compliance sync:** `vault_compliance_sync.py` — periodic scan creates/updates VaultItems for overdue inspections, expiring training certs, regulatory deadlines (OSHA 300A)

**Calendar sync:** iCal feed at `GET /vault/calendar.ics` with token-based auth, role-filtered events

**10 API endpoints:** items CRUD, summary, upcoming-events, cross-tenant, calendar.ics, compliance sync, calendar token gen

**Cross-tenant foundation:** `shared_with_company_ids` JSONB enables delivery confirmations visible to funeral homes

**Migrations:** `vault_01_core_tables` (DDL), `vault_02_data_migration` (idempotent data migration of legacy records)

**Migration head:** `vault_02_data_migration`

---

### Session: April 9, 2026 — Nav Reorganization + Resale Hub Shell

- Created Resale hub (`/resale`) gated by `urn_sales` extension
- `/resale/catalog` and `/resale/orders` alias existing urn pages
- `/resale/inventory` stub page added
- Removed standalone Urn Catalog, Urn Orders, Disinterments top-level nav items
- Disinterments added as sub-item under Order Station
- SS Certificates added as sub-item under Compliance (alongside NPCA)
- Added missing icons: Agents → Bot, Compliance → ShieldCheck, Disinterments → Shovel, Resale → Store
- Compliance and Order Station use same expand/collapse sub-nav pattern as Legacy Studio
- Added Store, Shovel, FileCheck, Bot, Shield, ShoppingBag, Boxes, Skull to sidebar ICON_MAP

---

### Session: April 9, 2026 — Social Service Certificates + Urn Catalog PDF Auto-Fetch

---

#### Social Service Certificates (Complete)

Auto-generated delivery confirmations for government Social Service Graveliner benefit program.

**Table:** `social_service_certificates` — status lifecycle: `pending_approval` → `approved` → `sent` (or `voided` at any point)

**Auto-generation trigger:** When a sales order containing a Social Service Graveliner product is delivered, `generate_pending()` creates a pending certificate. SS products identified by pattern matching ("social service", "ss graveliner", etc.).

**Approval workflow:**
- Admin reviews pending certificates in `/social-service-certificates`
- Approve → generates PDF via WeasyPrint, emails to funeral home's billing email with PDF attachment
- Void → records reason, marks certificate permanently voided

**PDF Generator (`pdf_generators/social_service_certificate_pdf.py`):**
- Professional letter-size government-facing document
- Company letterhead, deceased name, funeral home, cemetery, product details, delivery date/time
- Stored in R2 with presigned download URLs

**API:** 6 endpoints under `/api/v1/social-service-certificates/` (requires `invoice.approve` permission)

**Frontend:** `/social-service-certificates` — status filter dropdown, certificate table with approve/void/view-pdf actions, color-coded status badges

**Migration:** `r13_social_service_certificates` (revises `r12_urn_catalog_ingestion`)

---

#### Urn Catalog PDF Auto-Fetch (Complete)

One-click catalog sync replaces manual PDF upload. Downloads, parses, and enriches the Wilbert catalog automatically.

**How it works:**
1. `fetch_catalog_pdf()` downloads PDF from direct URL via httpx (no Playwright needed)
2. MD5 hash compared against stored hash — skips parse if unchanged (unless `force=true`)
3. PDF archived to R2 with hash-based key for versioning
4. `ingest_from_pdf()` parses 259 products via PyMuPDF state machine (~5s)
5. Web enrichment runs in background via FastAPI `BackgroundTasks` (~3 min, 100+ pages with 1.5s polite delay)
6. Background task creates its own `SessionLocal()` to avoid DB session lifecycle issues

**Fallback URL resolver:** `_resolve_pdf_url()` tries direct URL first (`HEAD` request), falls back to scraping the catalog landing page for `.pdf` links if Wilbert moves the file.

**Config (`wilbert_scraper_config.py`):**
- `CATALOG_PDF_URL` — direct PDF URL
- `CATALOG_PDF_PAGE_URL` — landing page for fallback resolution

**New tenant settings fields:** `catalog_pdf_hash`, `catalog_pdf_last_fetched`, `catalog_pdf_r2_key`

**Frontend:** Single "Fetch & Sync Catalog" button (always `force=true`), collapsed manual upload fallback. Removed standalone enrich button — web enrichment is automatic.

**Migration:** `r14_urn_catalog_pdf_fetch` (revises `r13_social_service_certificates`)

**E2E Tests:** 2 tests in `urn-catalog-pdf-fetch.spec.ts` (both passing)

---

### Session: April 9, 2026 — Urn Sales Extension + Wilbert Catalog Ingestion Pipeline

---

#### Urn Sales Extension (Complete)

Full urn sales lifecycle as a tenant extension (`urn_sales`), gated by `require_extension("urn_sales")`.

**Tables (6):** `urn_products`, `urn_inventory`, `urn_orders`, `urn_engraving_jobs`, `urn_tenant_settings`, `urn_catalog_sync_logs`

**Two fulfillment paths:**
- **Stocked**: Inventory reserved on confirm, released on cancel, decremented on deliver
- **Drop Ship**: Ordered from Wilbert, tracked via `wilbert_order_ref` + `tracking_number`

**Engraving workflow — two-gate proof approval:**
- Gate 1: FH approval via token-based email (`secrets.token_urlsafe(48)`, 72hr expiry, no auth)
- Gate 2: Staff approve/reject with notes
- Auto-sends FH email when `fh_contact_email` exists on proof upload
- Keepsake sets: scaffold N engraving jobs from `companion_skus`, propagate specs, all-jobs approval gate
- Verbal approval: stores transcript excerpt, flags but does NOT auto-approve
- Correction summary tracks resubmission history

**Scheduling board integration:**
- Ancillary items feed: stocked orders with `need_by_date` within configurable window (default 3 days)
- Drop-ship visibility feed: all pending drop-ship orders with tracking

**Key services:**
- `urn_product_service.py` — CRUD + Claude-powered natural language search
- `urn_order_service.py` — full lifecycle + scheduling feeds
- `urn_engraving_service.py` — two-gate proofs, Wilbert form PDF, keepsake propagation
- `urn_intake_agent.py` — email intake + proof matching

**Frontend pages:** `/urns/catalog`, `/urns/orders`, `/urns/orders/new`, `/proof-approval/{token}` (public)

**API:** 41 endpoints under `/api/v1/urns/`

**Migration:** `r11_urn_sales` (revises `r10_agent_infra`)

---

#### Wilbert Catalog Ingestion Pipeline (Complete)

Ingests Wilbert's 88-page PDF catalog (Volume 11) into `urn_products`, with optional website enrichment.

**PDF Parser (`wilbert_pdf_parser.py`):**
- PyMuPDF (`fitz`) text extraction → line-by-line state machine
- Handles Wilbert's two-line dimension format (label on one line, value on next)
- Extracts 259 products: SKU (P-prefix urns, D-prefix jewelry), product type (Urn/Memento/Heart/Pendant), dimensions, cubic inches, engravability flag, material category, companion linkage, catalog page
- Section-aware: maps page ranges to material categories (Metal 4-17, Wood 18-31, Stone 32-36, etc.)
- Deduplicates by SKU (keeps latest occurrence)

**Website Scraper (`urn_catalog_scraper.py`):**
- Real CSS selectors from research crawl: `.product-list`, `h1.item-name`, `div.item-desc p`, `#productImage img.main-image`
- 9 category URLs under `/store/cremation/urns/{material}/`
- SKU inference from image filenames (e.g., `P2013-CloisonneOpal-750.jpg`)
- Enriches with short/long descriptions and hi-res product images
- Polite crawl: 1.5s delay, custom User-Agent

**Ingestion Orchestrator (`wilbert_ingestion_service.py`):**
- `ingest_from_pdf()` — full pipeline: parse PDF → upsert by SKU → optional web enrichment
- `apply_bulk_markup()` — cost → retail with configurable % and rounding ($0.01/$0.50/$1/$5)
- `import_prices_from_csv()` — match by SKU, update cost/retail

**Migration:** `r12_urn_catalog_ingestion` (revises `r11_urn_sales`) — 11 new columns on `urn_products`, 3 on `urn_catalog_sync_logs`, 2 indexes

**6 new API endpoints:**
- `POST /urns/catalog/ingest-pdf` — file upload + parse
- `POST /urns/catalog/enrich-from-web` — website enrichment pass
- `PATCH /urns/products/{id}/pricing` — inline single-product price edit
- `POST /urns/pricing/bulk-markup` — bulk markup by material/type
- `POST /urns/pricing/import-csv` — CSV price import
- `POST /urns/pricing/import-json` — JSON price import

**Frontend (`urn-catalog.tsx` rewrite):**
- Pricing columns: Cost, Retail, Margin% with inline click-to-edit
- "Sync from Wilbert" dialog: PDF upload + optional web enrichment toggle
- Bulk Markup tool: filter by material/type, set %, choose rounding, only-unpriced option
- CSV Price Import dialog
- Material and Type filter dropdowns (populated from data)
- Expandable detail rows: dimensions, descriptions, companion links, catalog page
- Unpriced product warnings (count in header, amber row highlight)

**Design decisions:**
- Prices uploaded or manually entered in-platform (no WilbertDirect scraping — avoid stepping on Wilbert's toes)
- Wilbert marketing materials/images are OK (licensee rights)
- Font options deferred to tenant settings (future)

**E2E Tests:** 37/37 passing (Playwright, staging)

---

### Session: April 7, 2026 — Call Intelligence, Knowledge Base, Price Management, Platform Email, Staging Environment

---

#### Call Intelligence (Complete)

Feature formerly called "RingCentral Integration" — rebranded to "Call Intelligence" throughout UI. RingCentral is a provider underneath, not the feature name. No user-visible text says "RingCentral" except the Connect button and provider dropdown in settings.

**Three prompts fully built and deployed:**

**PROMPT 1 — OAuth + Webhook Infrastructure**
- Tables: `ringcentral_connections`, `ringcentral_extension_mappings`, `ringcentral_call_log`
- OAuth flow: `/settings/call-intelligence`
- Webhook: `POST /api/v1/integrations/ringcentral/webhook`
- SSE endpoint for real-time call events
- Extension → Bridgeable user mapping UI
- Token refresh background task
- Webhook renewal task

**PROMPT 2 — Transcription + Extraction Pipeline**
- Tables: `ringcentral_call_extractions`
- Services:
  - `transcription_service.py` — Deepgram Nova-2, speaker diarization
  - `call_extraction_service.py` — Claude extraction, fuzzy company match, draft order creation
  - `after_call_service.py` — orchestrator: transcribe → extract → draft order, 10s delay after call ends
- Voicemail handling (RC transcription + Deepgram fallback)
- Morning briefing integration
- Reprocess endpoint for re-running extraction

**PROMPT 3 — CallOverlay UI (Complete)**
- `contexts/call-context.tsx` — SSE connection, call state, preferences
- `components/call/CallOverlay.tsx` — 3 states: ringing / active / review
  - KB panel slides in at top when knowledge query detected
  - Pushes order sections down
  - Dismisses after configurable timer or when price is detected spoken (Phase 2 — timer is Phase 1 fallback)
- `components/call/MinimizedCallPill.tsx`
- `pages/calls/call-log.tsx`
- `App.tsx`: `CallContextProvider` + `CallOverlay` mounted globally

**Key design decisions:**
- Answer via physical RC phone (not WebRTC)
- Deepgram post-call transcription (Phase 1)
- Live streaming transcription = Phase 2
- After-call fires ONLY if no order created during call (prevents duplicates)
- "Still Needed" panel is primary feature — catches what FD forgot to mention
- Missing fields are tappable → shows callback number

**ENV VARS REQUIRED:**
- `RINGCENTRAL_CLIENT_ID`, `RINGCENTRAL_CLIENT_SECRET`, `DEEPGRAM_API_KEY`
- RC App: production, private, server-side web app
- Redirect URI: `https://api.getbridgeable.com/api/v1/integrations/ringcentral/oauth/callback`
- Scopes: Call Control, Read Accounts, Read Call Recording, Read Presence, Webhook Subscriptions, Read Call Log

---

#### Call Intelligence Knowledge Base (Complete)

Platform-wide feature powering live call assistance, mid-call price lookup, and future AI answering service.

**Tables:**
- `kb_categories` — per tenant, system + custom
- `kb_documents` — uploaded or manual text
- `kb_chunks` — parsed content for retrieval
- `kb_pricing_entries` — structured price data
- `kb_extension_notifications` — briefing hooks

**Services:**
- `kb_parsing_service.py` — Claude parses uploaded documents; extracts structured pricing into `kb_pricing_entries` automatically; supports PDF, DOCX, TXT, CSV, manual
- `kb_retrieval_service.py` — `retrieve_for_call()` called mid-call; pricing tier logic: matched CRM company → contractor tier, unmatched caller → show both tiers; returns brief answer for overlay display
- `kb_setup_service.py` — `seed_categories_for_tenant()` called on tenant create + extension enable

**Pages:**
- `/knowledge-base` — main KB page
- `/knowledge-base/{slug}` — category detail with document list + upload

**KB Coaching Banner:**
- `KBCoachingBanner.tsx` — adapts copy based on vertical + enabled extensions; dismissible per user (localStorage); re-shows when new extension enabled

**System categories by vertical:**
- ALL: Company Policies
- Manufacturing: Pricing, Product Specs, Personalization Options
- Manufacturing + Cemetery ext: Cemetery Policies
- Funeral Home: GPL, Service Packages, Grief Resources
- Cemetery: Equipment Policies, Section Policies

**Extension install notifications:**
- When extension activated → inserts into `kb_extension_notifications` with `briefing_date = tomorrow`
- Admin morning briefing shows recommendation to add related KB content

---

#### Price Management + PDF Generation (Complete)

**Tables:**
- `price_list_versions` — version history
- `price_list_items` — items per version (includes previous prices for comparison)
- `price_list_templates` — PDF layout settings
- `price_update_settings` — rounding prefs per tenant

**Pages:**
- `/pricing` — 3 tabs: Current Price List, Price Increase Tool (4-step wizard), Version History
- `/pricing/templates` — template builder with live HTML preview
- `/pricing/{version_id}/send` — bulk email UI

**Price Increase Tool flow:**
1. Select scope (entire list / category / individual items)
2. Set percentage + tiers (standard / contractor / homeowner); multiple rules allowed (different % per category)
3. Rounding from settings (none / nearest $1 / nearest $5 / nearest $10 / manual)
4. Schedule with effective date

**Effective date logic:**
- Orders created ON OR AFTER effective date get new pricing
- Orders created BEFORE effective date keep original pricing regardless of status
- Draft orders keep old pricing
- Activates automatically at midnight
- Day-before reminder to admins at 8am
- Midnight notification to all office staff

**PDF Generation:**
- weasyprint (HTML → PDF)
- Layouts: grouped (by category) or flat; 1 or 2 column
- Branding: logo, primary color, header/footer text
- Layout replication: upload existing PDF → Claude analyzes structure → applies detected settings
- Sunnycrest layout reference: 2 pages, 2-column, navy category headers, medium blue sub-category headers, logo top-left in circle, serif headers, bullet point items, right-aligned prices

**Cross-tenant pricing (foundation only):**
- Architecture placeholder in `activate_price_version()`
- Full implementation deferred until funeral home vertical is built
- Will use `platform_tenant_relationships`

**Services:**
- `price_increase_service.py` — `calculate_price_increase()`, `apply_price_increase()`, `activate_price_version()`
- `price_list_pdf_service.py` — `generate_price_list_pdf()`
- `price_activation_task.py` — midnight activation scheduler, 8am day-before reminder

---

#### Platform Email Infrastructure (Complete)

**Tables:**
- `platform_email_settings` — per tenant
- `email_sends` — audit log of all emails

**Sending modes:**
- **Platform mode (default):** Resend API (`RESEND_API_KEY` in Railway); from: `noreply@mail.getbridgeable.com`; reply-to: tenant's real email
- **SMTP mode (optional):** Tenant provides own SMTP credentials; encrypted at rest; test send verification before saving

**Service:** `email_service.py`
- `send_email()` — single email
- `send_price_list_email()` — bulk to FH list; generates PDF once, sends to all; individual or all funeral home customers

**Page:** `/settings/email`
- Sending mode toggle, from name + reply-to config, SMTP credentials (optional), test send button, BCC preferences, email history table

**Used by:** invoices, statements, legacy proofs, price lists (all email goes through this service)

**ENV VARS:** `RESEND_API_KEY` (already in Railway); domain verified: `getbridgeable.com` — SPF/DKIM records in Cloudflare

---

#### Staging Environment (Complete)

**Railway staging environment** — created by duplicating production, separate PostgreSQL instance.

| Service | URL |
|---------|-----|
| Backend | `sunnycresterp-staging.up.railway.app` |
| Frontend | `determined-renewal-staging.up.railway.app` |
| Postgres | Separate staging DB |

**Migration status:** `z9g4h5i6j7k8` (head)

**Seed data** (`backend/scripts/seed_staging.py`):
- Tenant: `staging-test-001` / Test Vault Co
- Users: admin, office, driver, production (passwords: `TestAdmin123!` etc.)
- 8 company entities (5 FH + 3 cemeteries)
- 10 contacts, 25 products across 6 categories
- 10 orders in various states, 3 invoices (paid/outstanding/overdue)
- 1 active price list version, 5 KB categories + 1 manual doc

**Test Suite Results (Final):**

| Suite | File | Results |
|-------|------|---------|
| API | `backend/tests/test_comprehensive.py` | 43/44 passed, 1 skipped (contacts route path, non-blocking) |
| Business flows | `frontend/tests/e2e/business-flows.spec.ts` | 44/44 passed |
| Automated flows | `frontend/tests/e2e/automated-flows.spec.ts` | 34/34 passed |
| **Total** | | **121/122 passing** |

```bash
# Run API tests
cd backend && source .venv/bin/activate
python3 -m pytest tests/test_comprehensive.py -v --tb=short

# Run E2E tests
cd frontend && npx playwright test --project=chromium
```

**Critical fixes deployed to staging:**
- Driver permissions + console page at `/driver`
- Auto-delivery eligibility fix (`scheduled_date <= today`, `required_date` fallback)
- Statement run page at `/ar/statements`
- Internal trigger endpoints at `/api/v1/internal/` (preview + execute auto-delivery)
- Job audit logging (`job_runs` table)
- `shipped` → `delivered` status rename throughout (migration + backward compat)

**Known staging quirk:** Tenant slug not auto-detected from Railway URL — use `?slug=testco` query parameter on first visit (persists to localStorage automatically). Fixed in codebase: `frontend/src/lib/tenant.ts` bootstraps slug from `?slug=` param.

---

#### CRM Visibility Bug Fix (April 7, 2026)

**Bug:** `crm_visibility_service.py` `never_visible` filter hid records where `customer_type IS NULL` — even when `is_funeral_home=True` or `is_cemetery=True`. This caused all company entities without an explicit `customer_type` to be invisible in the CRM.

**Fix:** Added role flag guards (`is_funeral_home`, `is_cemetery`, `is_licensee`, `is_crematory`, `is_vendor`) to the unclassified exclusion in all 3 functions: `get_crm_visible_filter()`, `get_hidden_count()`, `get_hidden_companies()`. Records with role flags are no longer treated as "unclassified."

**Impact:** Affected any tenant where company_entities were created with role flags but without `customer_type` set. Staging data patched (28 FH + 255 cemetery entities).

---

#### Production Status

**Sunnycrest is live at:** `sunnycrest.getbridgeable.com`

- Go-live date: April 7, 2026
- First tenant: Sunnycrest Vault (James Atkinson)
- Migration head: `r15_safety_program_generation`

**All core features production-ready:**
- ✅ Order management
- ✅ Invoice + AR system
- ✅ CRM (`company_entities`)
- ✅ Cemetery system
- ✅ Call Intelligence (RC connected)
- ✅ Knowledge Base
- ✅ Price Management
- ✅ Platform Email (Resend)
- ✅ Morning Briefing
- ✅ Onboarding checklist
- ✅ Staging environment + test suites (121/122 passing)
- ✅ Driver console (`/driver`)
- ✅ Monthly statements (`/ar/statements`)
- ✅ Auto-delivery with eligibility preview (`/api/v1/internal/trigger-auto-delivery`)
- ✅ Job audit logging (`job_runs` table)
- ✅ Urn Sales extension (37/37 E2E passing)
- ✅ Wilbert catalog ingestion pipeline (PDF + web + pricing)
- ✅ Catalog PDF auto-fetch with hash-based change detection
- ✅ Social Service Certificates (auto-generate + approve + email)
- ✅ Monthly Safety Program Generation (OSHA scrape + Claude AI + PDF + approval workflow, 12/12 E2E passing)

**Next build focus:** Funeral Home vertical — Phase FH-1 prompts ready. Key dependency: 70-field case file data model (design with AI Arrangement Scribe in mind from day one).
