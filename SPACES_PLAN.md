# SPACES_PLAN.md

Canonical Space taxonomy for Bridgeable's three-primitive architecture. Produced by Phase 0 of the [Architecture Migration](ARCHITECTURE_MIGRATION.md). Defines what Spaces exist, what seeds them, how they compose their Pulse surfaces, and how the existing seed-template system migrates onto the new shape.

Companion docs: [PLATFORM_ARCHITECTURE.md](PLATFORM_ARCHITECTURE.md) (especially §3 Spaces and §3.3 Pulse Surface), [SPACES_ARCHITECTURE.md](SPACES_ARCHITECTURE.md), [ARCHITECTURE_MIGRATION.md](ARCHITECTURE_MIGRATION.md), [FUNERAL_HOME_VERTICAL.md](FUNERAL_HOME_VERTICAL.md), [CLAUDE.md](CLAUDE.md).

**Status:** Approved. Phase 0 complete.

**Core thesis:** Spaces distinguish fundamentally different *contexts* — not different views of the same work. A funeral director does their job in one context (work); they check their paycheck in another (personal); they configure the platform in a third (admin). That's three Spaces. "Arrangement vs Administrative" is not a context distinction — both are the director's work context. That differentiation lives inside the work-context Space's Pulse composition, not as separate Spaces. **Role-based differentiation is Pulse work; context differentiation is Space work.**

---

## Part 1 — Space Taxonomy

Four system-seeded Space types + one user-created type. All share the `SpaceConfig` primitive (JSONB on `User.preferences.spaces`) with `is_system` and `access_mode` modifiers distinguishing the types.

### 1.1 Home Space

The user's work context. Every user lands here on first login; most of the user's day happens here.

| Attribute | Value |
|---|---|
| `is_system` | `true` (non-deletable) |
| `is_default` | `true` for fresh users (until user changes) |
| Seed logic | Every active user on signup (all 4 creation paths per Phase 8e.2.2). Never role-gated. |
| Access scope | Owner user only (1:1 per user) |
| `access_mode` | `platform` |
| Icon | `home` (Lucide) |
| Accent | `brass` default; user may change via `/settings/spaces` |
| `default_home_route` | `/` (renders the composed Pulse directly) |
| Pulse | Role-driven composition with four layers (Personal / Operational / Anomaly / Activity) per PA §3.3. Defaults seeded per (vertical, role); user refines via drag/hide/add and via observe-and-offer. |
| Pins | Role-seeded nav + saved views. Today's Phase 8e seed templates become the *Pulse default layouts* for this Space rather than separate Spaces. See Part 2. |

**Naming.** "Home" is the canonical Space name. Internally the Space's primary surface is the "Pulse" — the two names together are unambiguous ("go to your Home Space's Pulse" = "go to the Pulse of your Home"). Consistent with ARCHITECTURE_MIGRATION.md §6.1 decision.

### 1.2 My Stuff Space

The user's personal context. Payroll, time-off, benefits, personal schedule, training records, expense reports, profile, **and ongoing platform learning** (see §1.2.1). Role-invariant — everyone's My Stuff has the same shape.

| Attribute | Value |
|---|---|
| `is_system` | `true` (non-deletable) |
| `is_default` | `false` |
| Seed logic | Every active user on signup. Role-invariant. |
| Access scope | Owner user only (1:1) |
| `access_mode` | `platform` |
| Icon | `user-circle` (Lucide) |
| Accent | `brass` default; user may change |
| `default_home_route` | `/my-stuff` (new route; renders the Pulse) |
| Pulse | Universal composition (identical for all users). See Part 3 §3.14. |

**Canonical name confirmed: "My Stuff".** Friendly, conversational tone matches Bridgeable's coach-shaped philosophy.

#### 1.2.1 The Platform Learning layer — My Stuff as ongoing coaching surface

My Stuff hosts more than personal HR data. It's also where **ongoing platform learning lives** once onboarding (which is a one-time linear flow at `/onboarding/*`) completes. The director who's been using Bridgeable for six months doesn't need the onboarding wizard, but they do benefit from short tutorials about primitives they haven't tried yet, digests of recent platform features, and Intelligence-surfaced tips when behavior suggests they're doing something the hard way.

This reframes the relationship between onboarding and My Stuff: **onboarding is a hand-off point**. Users graduate from the linear wizard into a Pulse surface that keeps teaching them as the platform evolves and as their own usage matures.

**Strategic value (September Wilbert demo):** "The platform teaches itself to your team" is a differentiator — reduces ongoing training cost for licensees onboarding new staff, and powers self-serve onboarding for Wilbert licensees joining the network. Platform Learning is a September demo talking point even though video content is post-September.

Learning layer composition detailed in Part 3 §3.14.

### 1.3 Settings Space

System configuration. Shipped Phase 8a as the first system Space. Admin-only.

| Attribute | Value |
|---|---|
| `is_system` | `true` (non-deletable, admin-restricted) |
| `is_default` | `false` |
| Seed logic | Seeded via `_apply_system_spaces` when user has `admin` permission. Phase 8a invariant preserved. |
| Access scope | Admin users only |
| `access_mode` | `platform` |
| Icon | `settings` |
| Accent | `brass` |
| `default_home_route` | `/settings` |
| Pulse | Minimal; pins are configuration pages (users, roles, workflows, saved views, cemeteries, tax, etc.) organized into groups. Gains **Spaces Overview** section per Part 5. |

Phase 8a already ships this Space. This plan adds the Spaces Overview surface (Part 5) and moves a subset of current settings into richer Pulse composition (e.g., "configuration alerts" widget).

### 1.4 Network Space (cross-tenant)

Single Space per user. Hidden by default. Auto-surfaces when the tenant establishes its first cross-tenant relationship via `platform_tenant_relationships`. Contains one section per active relationship.

| Attribute | Value |
|---|---|
| `is_system` | `true` (non-deletable when present; relationship-gated visibility) |
| `is_default` | `false` |
| Seed logic | **Visibility-gated**: the SpaceConfig seeds into user's preferences only when (a) user's tenant has ≥1 active cross-tenant relationship AND (b) the user has permission to see cross-tenant data (admin OR explicit `cross_tenant.view` permission). Auto-removes when last relationship closes. |
| Access scope | Tenant-admin users + users with explicit `cross_tenant.view` permission (new permission, gates access for staff engaged in cross-tenant workflows) |
| `access_mode` | `platform` |
| Icon | `network` (Lucide) |
| Accent | `brass` |
| `default_home_route` | `/network` (new route; renders Space-level Pulse) |
| Pulse | **Space-level**: aggregate across all relationships (recent cross-tenant activity, pending shared Focuses the user is invited to, cross-relationship anomalies). **Section-level sub-pulses** per relationship: relationship-specific activity, pending decisions in that relationship, shared dashboards. |
| Sections | One per active relationship. Section-naming convention: `"{Own Tenant Name} ↔ {Partner Tenant Name}"` (e.g., `"Sunnycrest ↔ Hopkins"`). Section stores its own pin set for the specific relationship. |

**User-facing name confirmed: "Network".** Matches PA §7 "cross-tenant network" framing and BRIDGEABLE_MASTER's network narrative; fits the Wilbert licensee-network pitch. Internal canonical name remains "Cross-Tenant Space" in code where disambiguation from generic networking concepts matters; user-facing text reads "Network" everywhere.

**Relationship types** (per `fh_02_cross_tenant` migration):
- FH ↔ Manufacturer (vault orders)
- FH ↔ Cemetery (plot reservations)
- FH ↔ Crematory (cremation jobs)
- Manufacturer ↔ Manufacturer (network inventory sharing — future)
- FH ↔ FH (referral, mutual-aid — future)

Each section inherits its relationship's data scope from `platform_tenant_relationships` + the per-relationship shared Vault views.

### 1.5 Portal Spaces (permissioned external-user surfaces)

External non-employee users (family members, drivers hired by FHs but on external accounts, cemetery sextons, document signers) land directly in their Portal Space on login. Never see Home / My Stuff / Settings. Portal Spaces are the *unified primitive* for what the existing codebase treats as separate portal architectures (driver portal is live; MFG driver reconnaissance in Phase 8e.2; family + sexton portals are future).

| Portal type | access_mode | Seeded when | Pulse composition |
|---|---|---|---|
| Family Portal | `portal_external` | FH creates family portal invite for a case's informant | Case-specific info: funeral details, proof approvals pending, tribute wall, vault item gallery, family memorial posts |
| Driver Portal (FH + MFG) | `portal_partner` | Admin invites driver (existing Phase 8e.2 MFG; FH version follows) | Today's route, delivery status, mileage entry, route history |
| Sexton Portal | `portal_partner` | Cemetery admin invites sexton | Plot reservations for today, burial coordination tasks, plot map, interment schedule |
| Signer Portal | `portal_external` | Signature envelope sent to external signer (Phase D-4/D-5 native signing) | Single active envelope + history of completed signings |

Portal Spaces inherit:
- `tenant_branding: true` (see PA §10.5 + SPACES_ARCHITECTURE.md §10.6 "wash not reskin")
- `write_mode: "limited"` or `"read_only"` per portal type
- Path-scoped routing `/portal/<slug>/<portal-type>/*`
- JWT realm `portal`
- Separate identity store (`portal_users` table, Phase 8e.2)

Each portal user has exactly one Portal Space. Their SpaceConfig points at the portal-type-specific Pulse composition. Portal users never see a DotNav (they have only one Space) — Pulse is their landing page.

**No Home / My Stuff for portal users.** Explicit per user scope decision. A driver is a driver; a signer signs; a family member attends. Portal context IS the user's complete relationship with the platform.

### 1.6 User-Created Custom Spaces

Users can create their own work-context Spaces. The accountant who wants a dedicated "Accounting" Space — that's this path, not system-seeded. The safety trainer who wants to separate "Training Programs" from "OSHA Monitoring" — same path.

| Attribute | Value |
|---|---|
| `is_system` | `false` (user owns it, can delete) |
| `is_default` | `false` (unless user promotes it) |
| Creation | Via DotNav "+" button → `NewSpaceDialog` (existing Phase 8e.1) → inline settings (name, icon, accent from curated palette, default landing route, initial pins) |
| Access scope | Owner user only |
| `access_mode` | `platform` |
| Icon | User-chosen from Lucide picker (16-entry narrow set existing in Phase 8e.1) |
| Accent | User-chosen from 6-color palette (existing); will expand to full curated palette when Part 4 session happens |
| `default_home_route` | User-chosen from pin list + `/dashboard` fallback |
| Pulse | **Blank slate**. User pins saved views, nav items, triage queues over time. Observe-and-offer may propose helpful additions ("I notice you mostly use this for AR work — want the AR aging widget?") but never adds proactively. |

Existing infrastructure (Phase 8e.1 `/settings/spaces` + `NewSpaceDialog` + `SpaceEditorDialog`) already supports this. Phase 0 verifies the popover-is-inline-settings discipline (no nav to separate settings page for creation).

**`MAX_SPACES_PER_USER` raised from 7 to 12.** The Phase 8e.2.3 cap of 7 accommodated a minimum viable workflow; 12 gives power users room for the curated-workflow pattern (system seeds use 1–4 slots; user has 8–11 slots for custom Spaces). Backend + frontend bumped in lockstep (`backend/app/services/spaces/types.py` + `frontend/src/types/spaces.ts`). DotNav layout reconsidered in Part 6.2 — at 12 dots the existing `gap-1 + overflow-x-auto` may need a compact-mode variant.

**Summary inventory for a typical user (with new cap):**

| User type | Seeded Spaces | Room for user-created |
|---|---|---|
| FH director | Home, My Stuff | 10 custom |
| FH admin | Home, My Stuff, Settings | 9 custom |
| MFG accountant | Home, My Stuff | 10 custom ("Books" if desired) |
| MFG admin with active cross-tenant | Home, My Stuff, Settings, Network | 8 custom |
| MFG admin + safety_trainer doing separate workstreams | Home, My Stuff, Settings + user-created Compliance + Training | 7 custom remaining |
| Family portal user | Family Portal (only) | 0 |
| MFG driver (portal) | MFG Driver Portal (only) | 0 |

---

## Part 2 — Current Seed Template Migration

Current state: [`backend/app/services/spaces/registry.py`](backend/app/services/spaces/registry.py) has 13 `(vertical, role_slug)` keys each seeding 1–3 Spaces. Examples: `(funeral_home, director)` seeds `Arrangement · Administrative · Ownership`; `(manufacturing, production)` seeds `Production · Operations`.

### 2.1 What changes

All 13 work-context templates stop seeding *separate Spaces*. The per-role content they encode becomes *Pulse composition defaults* for Home Space. The role distinction preserved; the vehicle changes.

### 2.2 Template value → Pulse composition default mapping

| Current template output | New location |
|---|---|
| `SpaceTemplate(name="Arrangement", pins=[cases, tasks, ...])` | Home Space Pulse default composition for `(funeral_home, director)`: cases widget + tasks widget + scheduling widget |
| `SpaceTemplate(name="Administrative", pins=[financials, compliance])` | Same Home Pulse composition — financials widget + compliance widget appear as additional layers on the same Pulse |
| `SpaceTemplate(name="Ownership", pins=[dashboard, financials])` | Pulse's Anomaly + Activity layers get ownership-oriented widgets (revenue trends, KPIs) |
| `SpaceTemplate(name="Production", pins=[production-hub, ...])` | Home Pulse default for `(manufacturing, production)` |
| `SpaceTemplate(name="Books", pins=[outstanding_invoices])` | Home Pulse default for `(*, accountant)` |
| etc. | |

**The content work already done in Phase 8e isn't lost.** It's reshaped from "which Space to seed" to "how to compose this user's Pulse." Same pins, same saved views, same triage queues — different container.

### 2.3 Seed code changes

Backend `app/services/spaces/registry.py`:
- Existing `SEED_TEMPLATES` dict emptied of work-context entries
- New `HOME_PULSE_COMPOSITIONS: dict[(vertical, role), PulseComposition]` keyed identically, values become Pulse layer compositions
- New `seed_home_space(user)` function (always creates a Home SpaceConfig with the role-appropriate Pulse composition baked in)
- New `seed_my_stuff_space(user)` function (universal composition)
- Existing `_apply_system_spaces(user)` unchanged (Settings seeding preserved)
- New `seed_network_space_if_applicable(user)` hook fires from (a) user creation + (b) tenant relationship creation
- `seed_for_user(db, user)` orchestrates: always seeds Home + My Stuff, calls `_apply_system_spaces` if admin, calls network-if-applicable, stamps `spaces_seeded_for_roles` with user's role slug

### 2.4 Migration for existing seeded users

No production users per user confirmation. Development + test tenants need clearing + re-seeding.

**Migration `r48_spaces_taxonomy_reshape`** (revision number actual when built):
1. For every active user with existing seeded Spaces: clear `preferences.spaces` array + `preferences.spaces_seeded_for_roles`
2. Call `seed_for_user(db, user)` using new taxonomy
3. Preserve any user-created custom Space (`is_system=false`) — those survive untouched
4. Log per-user + per-vertical summary (same shape as r46, r47)

**Retrofit logic** (adapted from r47):
- Widened invariant stays: post-migration every active user has `spaces_seeded_for_roles` populated
- Home + My Stuff always present post-migration
- Settings present if admin
- Network present if tenant has active relationship AND user has cross_tenant.view
- Custom user-created Spaces preserved

### 2.5 Network Space seeding hooks

Two event sources trigger visibility:

1. **On tenant relationship creation** (`platform_tenant_relationships` INSERT): iterate all tenant users with `cross_tenant.view` permission; if no Network Space in their preferences, seed one.
2. **On user creation/role-change for users who gain `cross_tenant.view`**: check if their tenant has any active relationships; if yes, seed Network Space.

Both call `seed_network_space_if_applicable(user)` which is idempotent (checks for existing Network Space first, adds only relationship sections the user doesn't yet have).

**When last relationship closes**: Network Space is preserved but empty-state-rendered ("No active network relationships"). User not forcibly removed — reads as degraded rather than erased. Hide-on-empty deferred to design conversation post-Phase-D.

### 2.6 Portal Space seeding hooks

On portal user creation (existing Phase 8e.2 `/api/v1/portal/admin/users` invite flow), create the Portal Space matching the portal type. Portal user has exactly this one Space; `default_home_route` matches the portal type's entry route.

---

## Part 3 — Pulse Composition Per Role

Default Home Space Pulse compositions per `(vertical, role_slug)`. All follow PA §3.3 four-layer structure (Personal, Operational, Anomaly, Activity). Pulse components compose from the existing board-contributor registry pattern + saved views + Phase 5 triage queues + Phase 6 briefing card + Phase 7 anomaly infrastructure.

### 3.1 Funeral Home × Director (demo hero role)

**Personal layer:**
- Morning briefing card (today's focus — from Phase 6 briefings)
- My active cases needing action (saved view, cases assigned to me, ordered by staircase urgency)
- Pending family approvals (proofs awaiting director review, from urn engraving + legacy personalization)
- Today's services I'm leading
- Triage queue pending items (`task_triage`)
- @mentions + unread notifications

**Operational layer:**
- Today's schedule component (cross-FH work: arrangement conferences, services, deliveries)
- Active cases by staircase step (grouped kanban-style summary, click to drill in)
- This week's upcoming services
- Active Scribe sessions (live or recent transcripts)

**Anomaly layer:**
- Families with overdue follow-ups (aftercare + first-call pending)
- Cases approaching staircase deadlines
- Missing documents before service date (FTC compliance, authorization)
- Delivery coordination anomalies with manufacturers
- Unusual case patterns (Intelligence-detected)

**Activity layer:**
- Recent case updates
- Family portal activity
- Manufacturer proof submissions
- Delivery status changes
- Legacy proof approvals

Primary default landing: composed Pulse view. Click any widget to drill. No separate "Arrangement" or "Administrative" Space — the layers cover both.

### 3.2 Funeral Home × Admin

Same shape as Director plus broader access to admin functions:

- **Personal layer** — as Director + pending admin items (user approvals, tenant config notifications)
- **Operational layer** — as Director + staff-wide case distribution + office task queue
- **Anomaly layer** — as Director + billing/financial anomalies visible to admin role
- **Activity layer** — as Director + audit log tail

### 3.3 Funeral Home × Office

Office manager / bookkeeper working inside an FH tenant.

**Personal layer:**
- Morning briefing card (admin-flavor)
- My admin tasks (approvals pending, reports to send)
- Outstanding invoices needing follow-up

**Operational layer:**
- Today's case admin tasks (documents to file, forms pending)
- AR aging summary (widget version, drill to page)
- Statement run status
- Financial scoreboard

**Anomaly layer:**
- Unreconciled payments
- Overdue statements
- Pending compliance items
- Unusual financial patterns

**Activity layer:**
- Recent payments received
- Recent statement sends
- Financial agent job results

### 3.4 Funeral Home × Accountant

External or internal accountant focused on books.

**Personal layer:**
- Morning briefing (accountant-flavor, books-oriented)
- Pending approvals (month-end close items, reconciliation items)
- Review queues (invoice review, collections review)

**Operational layer:**
- AR aging snapshot
- AP aging snapshot
- Financial reports status
- Recent journal entries
- Unreconciled transactions

**Anomaly layer:**
- Reconciliation discrepancies
- Period-close blockers
- Expense categorization confidence-low flags
- Budget variance alerts

**Activity layer:**
- Recent agent job activity (cash receipts, expense categorization, etc.)
- Recent approvals processed

### 3.5 Manufacturing × Production

Plant manager / production supervisor.

**Personal layer:**
- Morning briefing (production-flavor)
- Today's pour schedule
- My assigned tasks (production, QC, training)
- Triage queue pending items (`task_triage`, `safety_program_triage`)
- Pending production decisions

**Operational layer:**
- Current production queue (active pours, molds in use)
- Inventory levels (saved view, critical products)
- Today's delivery schedule (outbound from plant)
- Active work orders
- Operations Board contributors (incident, safety-obs, QC, product-entry, delivery, team-presence — existing registry)

**Anomaly layer:**
- Low-inventory alerts
- QC failures
- Safety observations needing follow-up
- Production delays / overdue orders
- Equipment inspection overdue

**Activity layer:**
- Recent production log entries
- Recent QC inspections
- Recent safety events
- Shift handoff log

### 3.6 Manufacturing × Admin

Plant owner / manufacturing admin.

**Personal layer:**
- Morning briefing (owner-flavor, cross-cutting)
- Pending admin decisions (approvals, escalations)
- Network Space notifications (if tenant has relationships)
- Strategic anomalies surfaced by Intelligence

**Operational layer:**
- Cross-location overview (if multi-location — widget from Model A multi-location)
- Financial scoreboard (revenue, AR, AP)
- Production summary (queue depth, output today, week-over-week)
- Sales pipeline snapshot (quotes, orders, recent activity)
- Compliance status dashboard

**Anomaly layer:**
- Cross-system insights (from `cross_system_insight_service`)
- Financial health score alerts
- Network anomalies (cross-tenant relationship health)
- Major production anomalies
- Safety program status

**Activity layer:**
- Recent high-value orders
- Recent customer communications
- Recent strategic decisions logged
- Audit trail of admin actions

### 3.7 Manufacturing × Office

Office admin / bookkeeper in manufacturing tenant.

- **Personal layer:** as Office in FH vertical but manufacturing-flavored
- **Operational layer:** AR/AP widgets + order-station summary + invoice review queue + delivery coordination
- **Anomaly layer:** billing anomalies + shipment anomalies
- **Activity layer:** recent payments + recent invoicing + recent delivery confirmations

### 3.8 Manufacturing × Accountant

Same shape as FH accountant (§3.4) but manufacturing data.

### 3.9 Manufacturing × Safety Trainer

**Pulse composition on Home, not a dedicated Compliance Space.** Consistent with the minimal-Spaces principle: even a safety trainer lives in one work context — their work happens to *be* safety/compliance, so their Pulse composes from safety/compliance widgets. Creating a dedicated "Compliance" Space for them would be a role-specific exception that breaks the clean "Spaces = contexts, not information views" rule. If a trainer wants additional context separation (e.g., "Training Programs" as their own workspace alongside "OSHA Monitoring"), the user-created custom Space path (§1.6) is always available.

**Personal layer:**
- Pending safety program approvals (from Phase 8d.1 safety program triage)
- Upcoming training deadlines
- My assigned toolbox talks
- Safety triage queue pending items (`safety_program_triage`)

**Operational layer:**
- Training completion scoreboard (across plant)
- OSHA 300 log status
- Equipment inspection status
- Safety program generation status
- Upcoming training calendar

**Anomaly layer:**
- Overdue equipment inspections
- Overdue training assignments
- Recent incidents
- Compliance gaps by topic

**Activity layer:**
- Recent training events
- Recent safety observations
- Recent safety program generations
- Recent toolbox talks posted

### 3.10 Cemetery × Admin

Cemetery operator / owner. Cross-vertical pattern (cemetery is a supported vertical per CLAUDE.md).

**Personal layer:**
- Morning briefing (cemetery-flavor)
- Pending admin decisions
- Today's interment schedule

**Operational layer:**
- Plot availability snapshot
- Active interments / today's schedule
- Cross-tenant FH partnership activity (if Network Space active)
- Financial scoreboard

**Anomaly layer:**
- Plot reservation conflicts
- Overdue interment documentation
- Cross-tenant coordination issues

**Activity layer:**
- Recent interments
- Recent plot reservations
- Recent FH partner activity

### 3.11 Cemetery × Office

Cemetery office admin / bookkeeper. Analogous to FH office + cemetery-flavored (plot reservations, interment documentation, cross-tenant FH coordination rather than funeral-direction work).

### 3.12 Crematory × Admin

Crematory operator. Analogous to Manufacturing admin + cremation-specific operational widgets (cremation job queue, identification disc tracking, permit status).

### 3.13 Crematory × Office

Crematory office admin. Analogous to FH office + cremation-specific.

### 3.14 My Stuff Pulse (universal, role-invariant)

Same composition for every user regardless of (vertical, role). Five layers (adds a **Learning layer** between Personal and Operational).

**Personal layer:**
- My profile card (name, role, contact, photo)
- My schedule this week (my assignments only — services I'm leading, pours I'm running, routes I'm driving, training I'm taking)
- My tasks (personal items only — role tasks live in Home Pulse)
- My training status (certifications, upcoming renewals, completion rate)
- My unread direct notifications

**Learning layer (Platform Learning):**
- **Recommended tutorials** — short-form (60–90 sec) video tutorials for platform primitives (Focus, Pulse, Command Bar, NL Creation, Spaces, Scribe, Triage, etc.). Intelligence-driven ranking: tutorials the user hasn't yet watched, prioritized by primitives they haven't yet used in their real work
- **"What's new this month"** — feature digest card showing recently-shipped platform capabilities relevant to the user's role + vertical
- **Completion progress** — per-tutorial completion tracking, visible to the user only; no admin surveillance
- **Personalized tips** — observe-and-offer driven: when Intelligence detects manual workflow (e.g., "user typed a multi-field sentence but didn't use NL Creation overlay") or underutilization ("haven't opened a Focus this week"), surfaces a concise actionable tip card
- **Onboarding hand-off** — when the linear onboarding flow at `/onboarding/*` completes, the Learning layer is where ongoing learning lives. First-week content: "Now that you're set up, here are the most useful platform primitives to learn next"

**Operational layer (post-HR-module expansion):**
- My timesheet this period
- My pending time-off requests
- My recent paychecks (link only, never full content in Pulse)
- My benefits summary (link)
- My expense reports status

**Pre-HR (ships for September):**
- Personal + Learning layers render fully
- Operational layer ships as a single "Payroll, benefits, and expenses connect when your HR module is configured — [Learn more →]" placeholder card
- No skeleton cards for each HR section — one unified stub avoids clutter

**Anomaly layer:**
- My overdue training
- My upcoming certification expiry
- My timesheet approval pending (post-HR)

**Activity layer:**
- Recent changes to my profile
- Recent training completions
- Recent tutorials watched (from Learning layer)
- Recent timesheet submissions (post-HR)

#### 3.14.1 Platform Learning — September demo scope

- Layer ships with composition wiring + placeholder tutorial cards
- Intelligence prompt `pulse.suggest_tutorial` seeded (analyzes user behavior + tenure + role, returns ranked tutorial recommendations)
- Recommended-tutorials card renders with 3–5 placeholder tutorial entries (real video content post-September)
- "What's new this month" card wired to a new `platform_feature_digest` service that reads from a simple admin-editable content table (content initially hand-seeded)
- Completion tracking schema in place (`user_tutorial_completions` table) but content is placeholder until real videos ship
- Personalized-tip observe-and-offer path fires using existing Phase 8e.1 behavioral analytics infrastructure — "I notice you've been creating cases via forms. The Command Bar can do this in one sentence — [Try it →]" style prompts work from day one, before video content lands

#### 3.14.2 Platform Learning — post-September expansion

- Real video content (60–90 sec per primitive)
- Video hosting infrastructure (likely Cloudflare Stream or similar)
- Knowledge Base integration deepened — `training-hub`, `procedure-library`, and `vault-order-lifecycle` pages survive as detail destinations for deep-dive learning; Learning layer tutorials cross-link to KB pages for extended reading
- Per-tenant-admin ability to add tenant-specific tutorials (onboarding-for-new-staff content)
- Learning digest email option (weekly summary of new tutorials + tips user hasn't acted on)

---

## Part 4 — Color Palette

**Deferred to dedicated session.** Rationale: the aesthetic arc canonicalized "reference images win over prose for diagnosis" (CLAUDE.md §3). Picking 8–12 swatches for the per-Space accent system deserves the same measurement discipline — sample design-reference images, compute OKLCH values, validate contrast against surface tokens in both modes, iterate. Not something to decide from prose.

**Requirements captured for the future session:**
- 8–12 curated swatches, all warm-family hues (cocktail-lounge mood per DESIGN_LANGUAGE.md §2)
- All contrast-validated against `--surface-base`, `--surface-elevated`, `--surface-raised`, `--surface-sunken` in both light + dark modes (WCAG 3:1 for focus ring use, 4.5:1 for text-on-accent use)
- Implementation via `--space-accent` CSS variable — replaces brass ONLY in:
  - Active DotNav dot
  - Selected nav-item edge indicator
  - Focus ring on inputs within the Space
  - Optional 2px page chrome border
- Preferred subtler execution (PA §3.8): shift `--surface-base` by 2–3% chroma toward the Space color rather than tinting UI elements. Peripheral "light changed" signal, not "UI is colored."
- Scheduled as dedicated session post-Phase-D with reference images available.

Until that session: all system-seeded Spaces use `brass` default. User-created Spaces pick from the existing 6-color palette (Phase 8e.1's `warm / crisp / industrial / forward / neutral / muted`) as working set. Network Space may warrant a distinct accent — deferred.

---

## Part 5 — Spaces Overview Design

PA §3.7 describes an "Arc-inspired peek page" for cross-Space management. Proposal for the Spaces Overview surface:

### 5.1 Core content

Layout: side-by-side column per Space the user can see (their own + system + any cross-tenant shared).

Per Space:
- Column header: Space name + icon + accent swatch + `is_system` indicator if applicable
- Nav pin list (current pins in display order)
- Optional Pulse composition preview (a compact layer-diagram showing what's in Personal / Learning / Operational / Anomaly / Activity at a glance — see §5.3)
- Column footer: "Add pin" button (inline configurator, same shared edit surface as in-Space edit — Vault-as-foundation principle)

Interactions:
- **Drag-and-drop** elements between Spaces (pin moves from Column A to Column B)
- **Multi-select** for bulk operations (select 3 pins, "move to Home" or "delete")
- **Templates rail** (left or right side): saved Space configurations the user can stamp — "New Space from template: 'Accounting Space' / 'Marketing Space' / …". Initially empty; user adds via "Save this Space as template" from any Space they've customized
- **Cross-space search**: top-of-page search box; results highlight pins across columns

### 5.2 Access

- Every user reaches Spaces Overview from **Settings Space** ("Manage my Spaces" section; visible to admin + non-admin since it's per-user management of own Spaces, not platform-wide config).
- Leadership users (admin with cross-tenant permissions) additionally see the Network Space in a separate panel (see §5.4).

### 5.3 Pulse visualization in the Overview — lightweight

Each Space's column renders a compact "Pulse composition blocks" diagram below its nav pin list — horizontal bars representing Personal / Learning / Operational / Anomaly / Activity layers (My Stuff has 5 layers; all other Spaces have 4), each showing the count of composed widgets in that layer. Hovering a bar shows a tooltip listing the widgets. Clicking a widget name drills into Space Edit mode for that widget.

Keeps the Overview useful beyond nav management (which is the Phase 8e.1 `/settings/spaces` page). Stops short of rendering the full Pulse (that's heavy and duplicates the in-Space view).

### 5.4 Network Space in the Overview

Network Space renders in a bordered "Network" panel with a "Shared" badge:
- Pin list is editable (user can pin/unpin within their Network Space)
- Pulse composition is partly shared (shared dashboards can't be removed, only reordered) and partly per-user (user-added pins or personal overrides)
- Visual treatment emphasizes "this is cooperative, not yours alone"

### 5.5 Mobile / iPad adaptation

Desktop / iPad-landscape: full side-by-side columns as described.
iPad-portrait / mobile: single column, each Space rendered as an expandable accordion with nav list + Pulse blocks visible on expand. Drag-drop replaced by tap-and-menu ("Move this pin to…").

### 5.6 Implementation surface

Lives at `/settings/spaces/overview` (or replaces the current `/settings/spaces` landing — Phase 0 defers that routing decision to implementation). Uses `SpaceEditorDialog` + `NewSpaceDialog` for inline operations. Reuses Phase 8e.1 pin-manager primitives.

### 5.7 Out of scope for Phase 0

Detailed UX design (exact drag behavior, hover effects, empty-state copy, mobile gesture spec) — deferred to Phase D or a dedicated Overview design session once the Pulse composition engine is built. Phase 0 establishes the shape + access rules; implementation detail follows.

---

## Part 6 — Implementation Recipe

### 6.1 Backend changes

**New migration `r48_spaces_taxonomy_reshape`** (revision number actual when built):
- Operates on dev/test tenants (Sunnycrest, Hopkins) and any seeded test fixtures
- For each active user: clear `preferences.spaces` + `preferences.spaces_seeded_for_roles`
- Preserve custom user-created Spaces (`is_system=false`) if any exist
- Call new `seed_for_user(db, user)` with new taxonomy
- Per-user try/except + batch commit every 100 users + structured WARNING on failure + end-of-migration INFO summary with per-vertical breakdown (pattern from r46 + r47)
- Idempotent via `spaces_seeded_for_roles` check

**Constant bump `MAX_SPACES_PER_USER`** from 7 to 12:
- `backend/app/services/spaces/types.py` — source of truth
- `frontend/src/types/spaces.ts` — in-lockstep mirror
- Phase 8e.2.3 cap-breach guard logic unchanged; threshold tweaked
- No migration needed (cap is runtime; existing user data compatible)

**Refactor `app/services/spaces/`:**
- `registry.py`: strip `SEED_TEMPLATES` of work-context entries; introduce `HOME_PULSE_COMPOSITIONS` dict keyed on `(vertical, role_slug)` returning `PulseComposition` dataclass
- `seed.py`:
  - New `seed_home_space(db, user)` — creates the Home SpaceConfig with role-appropriate Pulse composition as default
  - New `seed_my_stuff_space(db, user)` — creates My Stuff SpaceConfig (includes Learning layer composition)
  - New `seed_network_space_if_applicable(db, user)` — visibility-gated Network seeding
  - Existing `_apply_system_spaces(db, user)` — unchanged (Settings)
  - `seed_for_user(db, user)` orchestrates: Home → My Stuff → system spaces → Network-if-applicable → stamp marker
  - `seed_spaces_best_effort` wrapper unchanged (Phase 8e.2.2 pattern preserved)
- `crud.py`: unchanged for space CRUD; add Network Space section CRUD (add/remove relationship sections) as new methods
- `types.py`: add `PulseComposition` dataclass (Personal / Learning / Operational / Anomaly / Activity layer lists; Learning optional — only My Stuff uses it today), add section-config to `SpaceConfig` for Network Space only, bump `MAX_SPACES_PER_USER = 12`

**Cross-Tenant relationship hook:**
- `platform_tenant_relationships` INSERT trigger (or ORM post-commit hook in the service that creates relationships) calls `seed_network_space_for_tenant_users(db, tenant_id)` — iterates eligible users, seeds Network Space if absent
- Equivalent hook for DELETE to preserve-but-empty-state the Network Space

**Portal Space seeding:**
- Existing `/api/v1/portal/admin/users` invite endpoint (Phase 8e.2.1) creates a PortalUser; extend to also create the portal-type-specific Portal SpaceConfig in that PortalUser's preferences

**Permission additions:**
- New `cross_tenant.view` permission — gates Network Space visibility for non-admin users engaged in cross-tenant workflows
- Seeded automatically for admin role; admins can grant to specific non-admin users via `/admin/roles` or role-user assignments

**Platform Learning tables (new):**
- `user_tutorial_completions` (user_id, tutorial_key, completed_at, progress_pct, is_active) — tracks per-user tutorial progress; composite PK on `(user_id, tutorial_key)`
- `platform_feature_digests` (id, vertical, role_slug_or_null, published_at, title, body_md, active) — admin-editable monthly digest content
- New Intelligence prompt `pulse.suggest_tutorial` seeded — analyzes user behavior + tenure + role, returns ranked tutorial recommendations
- Observe-and-offer consumer hook (see 6.3)

### 6.2 Frontend changes

**DotNav updates (`components/layout/DotNav.tsx`):**
- No shape change — still renders dots per SpaceConfig in `preferences.spaces`
- System Spaces (Home, My Stuff, Settings, Network) render leftmost in a stable order (Home → My Stuff → Network if present → Settings if admin → user-created)
- User-created Spaces render right of system Spaces; DotNav drag-reorder applies within user-created only (system Spaces have fixed ordering)
- **At 12-dot capacity**, existing `gap-1 + overflow-x-auto` may need a compact-mode variant (tighter gap, smaller dots) to fit gracefully in the 240px sidebar. Compact mode engages automatically when `spaces.length >= 8`. Implementation detail deferred to Phase D; UX OK via scroll in the meantime.

**New page: Home Space Pulse (`pages/home/HomePage.tsx`):**
- Route: `/` (replaces current landing)
- Renders composed Pulse from role-defaulted composition + user overrides
- Pulse composition engine is Phase D deliverable — HomePage is the consumer surface
- **Transition strategy**: until Phase D Pulse engine lands, HomePage renders a baseline layout using existing `WidgetGrid` (Phase 8e.1 pattern) as a transitional implementation. Phase D swaps the WidgetGrid call site for the composition engine without changing the route. Zero user-visible regression during transition.

**New page: My Stuff Space (`pages/my-stuff/MyStuffPage.tsx`):**
- Route: `/my-stuff`
- Renders universal composition (Personal + Learning + Operational + Anomaly + Activity)
- Components mostly exist (profile, training); new components for Learning layer tiles + HR placeholder card
- Learning layer card components new: `RecommendedTutorialsCard`, `WhatsNewCard`, `CompletionProgressCard`, `PersonalizedTipCard`

**New page: Network Space (`pages/network/NetworkPage.tsx`):**
- Route: `/network`
- Renders Space-level Pulse (aggregate) + section navigation (one tab/link per relationship)
- Section sub-pages at `/network/<relationship-id>` render relationship-specific sub-pulse

**Portal redirect logic:**
- Existing Phase 8e.2 PortalApp routing handles "portal users land in portal" — no change needed if the Portal Space config correctly points `default_home_route` at the portal's root route
- Verify on first login the user's single SpaceConfig is the Portal Space and `default_home_route` matches the portal's entry route

**New-space popover verification:**
- Existing `NewSpaceDialog` (Phase 8e.1) already handles inline settings: name, icon (16-Lucide picker), accent (6-color picker), density toggle, is_default flag
- Phase 0 verifies: no link-out to separate settings page during creation; popover dismisses on completion; Space immediately visible in DotNav
- Minor additions: "initial pins" multi-select picker in the dialog (currently added post-creation via SpaceEditorDialog) — improves first-creation UX

**New page: Spaces Overview (`pages/settings/SpacesOverviewPage.tsx`):**
- Route: `/settings/spaces/overview`
- Implements Part 5 design
- Reuses existing pin-manager primitives from `/settings/spaces`
- Large deliverable — may span its own 2-3 sessions post-Phase-D

### 6.3 Intelligence backbone integration

**New service: `app.services.pulse.composition_service`:**
- `get_composition_for_user(db, user) -> PulseComposition` — computes role-default + user-override + observe-and-offer-suggested composition
- Reads `HOME_PULSE_COMPOSITIONS[(vertical, role)]` defaults, overlays per-user customizations from `User.preferences.home_pulse_config`, applies adaptive composition (time of day, behavior, etc.)
- **Intelligence prompt `pulse.suggest_composition`** — periodically analyzes user behavior and proposes composition adjustments ("You check the cemetery contacts list every Monday — want it as a Pulse component?"). Runs via existing Phase 8e.1 affinity signal + behavioral analytics infrastructure.

**New service: `app.services.pulse.network_composition_service`:**
- Aggregates across active cross-tenant relationships for the Network Space Pulse
- Computes per-relationship sub-pulse compositions

**New service: `app.services.pulse.learning_service`:**
- `get_recommended_tutorials(db, user) -> list[TutorialCard]` — uses `pulse.suggest_tutorial` Intelligence prompt
- `get_whats_new_digest(db, user) -> FeatureDigest` — reads `platform_feature_digests` filtered by user's vertical + role
- `record_tutorial_completion(db, user, tutorial_key, progress_pct)` — writes to `user_tutorial_completions`
- `get_personalized_tip(db, user) -> Tip | None` — consumes observe-and-offer patterns detected by the behavioral-analytics infrastructure

**Observe-and-offer consumer:**
- New generic service `app.services.observe_and_offer.suggestion_service`
- Detects patterns (behavioral + explicit-affinity signals) and fires suggestions via existing notification infrastructure or via My Stuff Learning layer
- Respects "quiet, not nagging" (PA §6.1) — minimum 3-5 instances over reasonable window before suggesting; long cool-down on decline
- Primary consumers: Home Pulse composition suggestions, My Stuff personalized tips, Focus pin suggestions (Phase A session 6)

### 6.4 Testing strategy

- Port Phase 8e.2.2 invariant test (`test_platform_space_invariant`) to new taxonomy: every active user has Home + My Stuff (+ Settings if admin) (+ Network if applicable) post-migration
- New test: `test_network_space_visibility_gated` — user without cross-tenant permission doesn't see Network; with permission + active relationship sees it
- New test: `test_network_space_relationship_sections` — seeds a 3-relationship tenant, verifies 3 sections appear for admin, appropriate subset for non-admin per-relationship permissions
- New test: `test_my_stuff_role_invariant` — 5 different (vertical, role) users all get identical My Stuff composition (Learning layer included)
- New test: `test_home_pulse_composition_role_defaults` — each `(vertical, role_slug)` key produces expected layer composition
- New test: `test_max_spaces_per_user_is_12` — cap is 12 (not 7); attempting 13th creation returns 400
- New test: `test_learning_layer_ships_before_hr_module` — My Stuff composition returns Personal + Learning + Anomaly + Activity layers with HR placeholder when no HR module configured
- Preserve all Phase 8e.2.2 / 8e.2.3 defensive-reseed-on-login tests; adapt them to new taxonomy

---

## Part 7 — Dependencies + Blocking Relationships

```
Phase 0 (this plan: SPACES_PLAN.md) ← APPROVED
  ↓
Phase D (Space + Pulse Foundation) — requires SPACES_PLAN.md approved
  ↓
Phase E (Cross-tenant Personalization) — depends on Network Space architecture from this plan

Phase B (Funeral Scheduling Focus) — needs to know launch Space
  ├─ ANSWER from this plan: launches from Home Space (Arrangement-shaped Pulse composition for FH director)
  └─ Does not block on Phase 0 approval — can ship independently

Phase A (Focus primitive) — does not depend on Phase 0
Phase C (Command Bar v2) — does not depend on Phase 0
```

**Phase 0 unblocks Phase D.** Phase D's Pulse composition engine consumes the taxonomy + composition defaults from this plan.

**Phase B proceeds in parallel** — Phase B session 1 doesn't need this plan; the answer "Funeral Scheduling Focus launches from the user's Home Space" is in this plan but was inferable from the minimal-Spaces thesis regardless.

---

## Part 8 — Open Questions for Future Sessions

Explicitly deferred:

1. **Color palette selection (Part 4)** — dedicated design session with reference images post-Phase-D
2. **Per-role Pulse composition refinement** — detailed widget-level composition choices made during Phase D as the composition engine is built. Part 3 establishes the shape and default layer contents; Phase D fills in widget specifics
3. **Portal Space detailed UI design** — per-portal-type Pulse compositions (family portal, sexton portal, signer portal) are portal-workstream deliverables, not Phase 0
4. **Network Space sub-pulse detailed structure** — per-relationship section Pulse composition is designed during Phase E (cross-tenant personalization implementation). Part 1.4 establishes the shape; Phase E details it
5. **User-created Space template library** — "save this Space as template" feature (Part 5.1) is post-September polish
6. **Spaces Overview implementation details** — exact drag behavior, animations, empty states, mobile gestures — deferred to post-Phase-D dedicated session
7. **My Stuff HR module expansion** — Check integration (payroll, benefits) is post-September; Operational layer of My Stuff Pulse expands when that work lands
8. **Platform Learning video content** — real 60–90 sec video content per primitive, video hosting infrastructure (likely Cloudflare Stream), per-tenant-admin tutorial authoring — post-September. September ships composition wiring + Intelligence-driven ranking + placeholder cards + `pulse.suggest_tutorial` prompt + completion tracking schema
9. **DotNav compact mode at 12-dot capacity** — automatic compact-variant when `spaces.length >= 8`; implementation detail deferred to Phase D
10. **Network Space hide-on-empty behavior** — when tenant's last relationship closes, Space auto-removes vs preserves-as-empty-state. Currently proposed: preserve-as-empty-state. Revisit post-Phase-E if UX signal says otherwise.

---

_End of SPACES_PLAN.md_
