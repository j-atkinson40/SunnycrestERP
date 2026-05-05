# Calendar Step 5 — Cross-Surface Rendering

**Phase:** W-4b Layer 1 Calendar Step 5 (closes substantive Calendar
primitive arc)
**Migration head at start:** `r72_ptr_consent_metadata`
**Migration head at finish:** `r72_ptr_consent_metadata` (no schema
change — service-layer + frontend only per Q1 confirmed pre-build)
**Test posture:** 28 backend tests + 6 Playwright smoke + frontend
tsc clean

---

## Scope (TIGHT — Q3 confirmed pre-build)

Step 5 ships **4 of 7 canonical cross-surface rendering surfaces** per
[BRIDGEABLE_MASTER §3.26.16.10](../../BRIDGEABLE_MASTER.md). The
remaining three rendering surfaces (saved-view integration, full
workspace right-pane integration, briefing integration) are deferred
to follow-on substrate-readiness arcs per the canonical scoping
decisions documented below.

**Step 5.1** ships PTR-consent extensions in a dedicated ~3-day
follow-on arc. **Email-mediated upgrade requests** route through the
Email primitive substrate (Step 5.1+).

### Cross-surface deliverables (4)

| Surface | Endpoint / Component | §3.26.16.10 row |
|---|---|---|
| Pulse Communications Layer Glance | `calendar_glance` widget @ `GET /widget-data/calendar-glance` | Row 1 |
| Pulse Operational Layer extension | `calendar_summary` widget + today_widget extension @ `GET /widget-data/{calendar-summary,today-calendar}` | Rows 2-3 |
| Customer Pulse composition source | `GET /pulse/calendar-events-for-customer/{customer_entity_id}` | Row 4 |
| V-1c CRM activity feed integration | Auto-write per lifecycle (scheduled / modified / cancelled / attendee_responded) | Row 5 |
| Native event detail page | `EventDetailPage.tsx` @ `/calendar/events/:eventId` | Row 6 |
| iTIP REPLY V-1d notify hook | Per-organizer notification on response transition | (extension) |
| Granularity coarsening | `_coarsen_windows` hour/day bucket aggregation | §3.26.16.6 |

### Explicit deferrals (Q3 / Q5 pre-build)

| Deferral | Concrete signal triggering future scope | Phase |
|---|---|---|
| Saved-view integration | D6 lint failure resolved + saved view registry adoption pattern locked | post-Step-5 |
| Workspace right-pane event detail integration | Workspace surface architecture decisions (right-pane vs split-pane vs modal) | post-Step-5 |
| Briefing integration | Briefing primitive Step 5+ (per arc sequencing) | post-Briefing-arc |
| Email-mediated upgrade requests | Email Step 5.1+ substrate ready | Step 5.1 |
| Cross-tenant Pulse widget surfacing pending requests | Cross-tenant calendar widget infrastructure | Step 5.1+ |
| Calendar Workshop integration (§3.26.16.25) | Workshop primitive scope-expansion decisions | Workshop arc |
| Calendar Intelligence integration (§3.26.16.24) | Intelligence prompt scope-expansion decisions | Intelligence arc |
| Front-style shared calendar UX (§3.26.16.19) | Shared calendar architecture decisions | Future |

---

## Architecture

### Pulse Communications Layer (Glance)

Per §3.26.16.10 **hybrid contribution canonical**, calendar primitive
contributes to MULTIPLE Pulse layers based on signal type:

  - **Communications Layer** (`calendar_glance` widget) surfaces
    interpersonal-scheduling signals — responses awaiting the caller's
    reply OR new cross-tenant invitations. "Who needs me?" cognitive
    question.
  - **Operational Layer** (`today_widget` extension +
    `calendar_summary` widget) surfaces operational-team-facing
    schedule signals — today's confirmed events + week schedule.
    "What's my work right now?" cognitive question.

Pattern parallels Email Step 5 verbatim (canonical Step 5 cross-
surface rendering precedent).

### Customer Pulse composition source

`GET /pulse/calendar-events-for-customer/{customer_entity_id}`
establishes the canonical query pattern that the Customer Pulse
template's `calendar_events` slot will consume when scoped Pulse
summoning + per-template slot mapping infrastructure ships per
§3.26.12.4. **Step 5 ships data-layer-only** — Customer Pulse template
extension (slot mapping declaration) deferred until the scoped Pulse
infrastructure lands.

**Multi-source resolution** (4 sources unioned):
  1. Explicit `CalendarEventLinkage(linked_entity_type='customer')`
  2. Indirect via `fh_case` linkage → `Customer.master_company_id`
  3. Indirect via `sales_order` linkage → `Customer.master_company_id`
  4. Attendee `resolved_company_entity_id`

**Tenant isolation:** customer_entity_id must belong to caller's
tenant; cross-tenant probes return existence-hiding empty payload
(`customer_name: null, total_count: 0, recent_events: [],
upcoming_events: []`). Pattern matches Email Step 5 verbatim.

### V-1c CRM activity feed integration

`activity_feed_integration.log_calendar_event_activity(db, *, event,
kind, actor_user_id, detail)` writes activity log rows for every
CompanyEntity that should surface the calendar event lifecycle event.
**4 lifecycle kinds:**

  - `scheduled` — `event_service.create_event` (Step 9 wiring)
  - `modified` — `event_service.update_event` (substantive fields
    only: start_at, end_at, status, location)
  - `cancelled` — `event_service.delete_event`
  - `attendee_responded` — `itip_inbound.process_inbound_reply` (Step 8)

**`activity_type="calendar"`** is the new canonical mapping (added
alongside existing `email`); `RecentActivityWidget`'s `activityVerb`
map gains the `"calendar"` entry + click-through routing extracts
`event_id={uuid}` from the body and routes to `/calendar/events/{id}`.

**`master_company_id` resolver** handles 4 entity-shape sources
identical to the customer Pulse composition source above. Cross-tenant
CompanyEntity references NEVER write into the caller's activity feed
per §3.25.x masking discipline.

### Native event detail page (§14.10.3)

`/calendar/events/:eventId` renders Pattern 2 card with internal
sections per [DESIGN_LANGUAGE.md §14.10.3](../../DESIGN_LANGUAGE.md):

  1. **Subject + time strip** — `font-plex-serif text-h2` + relative-
     time mono
  2. **Metadata strip** — status pill + location + transparency +
     cross-tenant indicator + attendee count
  3. **Recurrence section** (conditional)
  4. **Description section** (conditional; HTML rendered in sandboxed
     iframe per §3.26.15.5 outbound sanitization discipline)
  5. **Attendees section** — response-state status dots + "You" row
     inline Accept / Decline / Tentative
  6. **Linked entities section** — polymorphic linkage chips
  7. **Action footer** — `[Edit event]` / `[Reschedule]` /
     `[Cancel event]` (confirmed only) / `[Send invites]` (tentative)

**Spec discipline:** the new page deliberately uses direct
`<Button onClick={...}>` shape — does NOT introduce the pre-existing
`asChild` violation that lives on `CalendarAccountsPage.tsx`. See
CLAUDE.md §12 shadcn v4 invariant.

### iTIP REPLY V-1d notify hook (Step 8)

`itip_inbound.process_inbound_reply` fires
`_notify_event_organizer(db, *, event, responder_attendee,
new_response_status, tenant_id)` when an attendee transitions OUT of
`needs_action`. Notification category `calendar_attendee_responded`,
linked to `/calendar/events/{event_id}`. Internal-organizer routes via
`CalendarEventAttendee.role='organizer' + resolved_user_id`; external
organizers (no `resolved_user_id`) skip in-app notify since iTIP REPLY
transport via Email primitive already delivered the canonical signal.

Best-effort + tenant-scoped — notification failure NEVER blocks reply
processing per V-1d discipline.

### Granularity coarsening (privacy-preserving)

`freebusy_service._coarsen_windows(windows, *, granularity, consent_level)`
implements **window-bucket-aggregation** per Q6 confirmed pre-build:

  - **Hour granularity:** windows bucketed by floor-to-hour; collapse
    overlapping windows in the same hour into a single output window
    spanning the full hour.
  - **Day granularity:** windows bucketed by floor-to-day; collapse
    all events in the same day into a single full-day window.
  - **Status precedence:** `_aggregate_status` returns
    highest-precedence status (`busy=3 > tentative=2 >
    out_of_office=1`) across all member windows in the bucket.

**Privacy discipline:** coarsened windows DROP `subject`, `location`,
`attendee_count_bucket` regardless of consent_level. Coarsening only
LOSES detail; never exposes more than original. Per §3.26.16.6
anonymization canonical: when operator chooses coarsened view,
detail is LOST not preserved.

---

## Files added / modified

### Backend (new)

| File | Purpose |
|---|---|
| `app/services/widgets/calendar_glance_service.py` | Pulse Communications Layer Glance data |
| `app/services/widgets/calendar_summary_service.py` | Operational Layer week schedule + today_widget extension |
| `app/services/calendar/customer_calendar_events_service.py` | Customer Pulse composition source |
| `app/services/calendar/activity_feed_integration.py` | V-1c CRM activity feed integration |
| `tests/_calendar_step5_fixtures.py` | Shared test fixtures |
| `tests/test_calendar_step5_cross_surface.py` | 28 backend tests |
| `docs/calendar_step5_cross_surface.md` | This doc |

### Backend (modified)

| File | Change |
|---|---|
| `app/services/calendar/freebusy_service.py` | `_aggregate_status` + `_coarsen_windows` granularity coarsening |
| `app/services/calendar/itip_inbound.py` | `_notify_event_organizer` V-1d hook + activity feed integration |
| `app/services/calendar/event_service.py` | Activity feed hooks in create/update/delete + `list_linkages_for_event` |
| `app/api/routes/widget_data.py` | `GET /calendar-glance`, `/calendar-summary`, `/today-calendar` endpoints |
| `app/api/routes/pulse.py` | `GET /calendar-events-for-customer/{id}` endpoint |
| `app/api/routes/calendar_events.py` | `GET /{id}/linkages` endpoint |
| `app/services/widgets/widget_registry.py` | `calendar_glance` + `calendar_summary` widget definitions |

### Frontend (new)

| File | Purpose |
|---|---|
| `components/widgets/foundation/CalendarGlanceWidget.tsx` | Pulse Communications Layer Glance |
| `components/widgets/foundation/CalendarSummaryWidget.tsx` | Operational Layer week schedule |
| `pages/calendar/EventDetailPage.tsx` | Native event detail page (§14.10.3) |
| `tests/e2e/calendar-phase-w4b-step5.spec.ts` | Playwright smoke (6 scenarios) |

### Frontend (modified)

| File | Change |
|---|---|
| `components/widgets/foundation/register.ts` | Register calendar_glance + calendar_summary |
| `components/widgets/foundation/RecentActivityWidget.tsx` | "calendar" activityVerb + click-through routing to /calendar/events/{id} |
| `services/calendar-account-service.ts` | `listEventLinkages` method |
| `App.tsx` | Mount `/calendar/events/:eventId` route |

---

## Test posture

- **Backend tests shipped Phase W-4b Step 5:** 28 in
  `test_calendar_step5_cross_surface.py` across 7 test classes
  (TestCalendarGlanceWidget × 5, TestTodayWidgetCalendarExtension × 3,
  TestCustomerPulseEvents × 4, TestCalendarActivityFeed × 4,
  TestEventDetailEndpoints × 5, TestItipReplyNotifications × 2,
  TestGranularityCoarsening × 5).
- **Playwright smoke:** 6 scenarios in
  `calendar-phase-w4b-step5.spec.ts`.
- **No new migrations.** Migration head unchanged at
  `r72_ptr_consent_metadata`.
- **Frontend tsc clean** + vitest unaffected (no new vitest tier
  tests; backend coverage + Playwright smoke is canonical at this
  scope).

---

## Forward sequencing

After Step 5 closes:

  1. **Step 5.1** — PTR consent upgrade UI write-side extensions
     (~3 days bounded follow-on per Calendar Step 4 → Step 4.1
     canonical scoping precedent).
  2. **Workshop arc** — Calendar Workshop integration per §3.26.16.25.
  3. **Intelligence arc** — Calendar Intelligence integration per
     §3.26.16.24.
  4. **Future:** Front-style shared calendar UX (§3.26.16.19),
     drafted-event review queue, full saved-view + briefing
     integrations (against substrate-ready dependencies).

Calendar primitive arc closes at canon-faithful depth with Step 5;
remaining substantive work is per-substrate-readiness extensions
rather than core primitive scope.
