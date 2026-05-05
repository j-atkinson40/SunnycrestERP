# Calendar Step 5.1 — PTR Consent Extensions (Calendar arc closure)

**Phase:** W-4b Layer 1 Calendar Step 5.1 (closes Calendar primitive
arc at canon-faithful depth)
**Migration head at start:** `r72_ptr_consent_metadata`
**Migration head at finish:** `r72_ptr_consent_metadata` (no schema
change — service-layer + frontend only per Q3 confirmed pre-build)
**Test posture:** 15 backend tests + 3 Playwright smoke + frontend
tsc clean

---

## Scope

Step 5.1 ships the PTR consent extensions deferred from Step 4.1 →
Step 5 → Step 5.1 per repeated bounded-follow-on canonical scoping
discipline. Two deliverables:

1. **Email-mediated upgrade requests** via Email primitive Step 4c
   outbound substrate — managed Workshop template
   `email.calendar_consent_upgrade_request` + opt-in `send_email`
   kwarg on `ptr_consent_service.request_upgrade`.

2. **Cross-tenant Pulse widget** `calendar_consent_pending` —
   Communications Layer per §3.26.16.10 — surfacing pending consent
   upgrade requests alongside `calendar_glance` + `email_glance`.

After Step 5.1 ships, **all canonical Calendar primitive scope per
§3.26.16 is substantively complete**. Remaining Calendar work is
canonically deferred to substrate-readiness arcs (Calendar Workshop /
Intelligence / Period Pulse / Coordination Focus / briefing structured
sections / saved-view integration / §3.26.16.21 strategic vision
deferral catalog).

---

## 8 architectural decisions confirmed pre-build

| Q | Decision | Rationale |
|---|---|---|
| Q1 | Email-mediated request **opt-in** (`send_email: bool = False`) | Cross-tenant email is new surface; safe ship; in-app notify continues unconditionally per Step 4.1 contract |
| Q2 | All active admins via per-recipient `delivery_service.send_email_with_template` calls (separate `DocumentDelivery` row per admin) | Per-recipient audit + bounce attribution; mirrors `notify_tenant_admins` cohort canonical |
| Q3 | Python-script idempotent seed (`scripts/seed_calendar_step51_email_template.py`); **no migration** | Phase 6 + Phase 8b + Phase 8d.1 precedent; preserves admin customizations via Option A state machine |
| Q4 | Widget default-ships with empty state ("No pending consent requests") | Cross-vertical foundation widget per §3.26.16.10; discoverability beats stealth |
| Q5 | `request_upgrade` email path only at Step 5.1 | accept + revoke continue with in-app notify per Step 4.1 — request-of-action vs confirmation-of-receipt class distinction |
| Q6 | V-1c CRM activity feed integration **out-of-scope** | PTR consent is tenant-level admin event, not CompanyEntity-bound; V-1c canonically scoped to CompanyEntity-bound events |
| Q7 | Audit linkage via `DocumentDelivery.metadata_json` JSONB | No new FK column; future query "what emails were sent for relationship X?" via metadata search |
| Q8 | ~15 backend tests + ~3 Playwright smoke | Calibrated to ~50% Step 5 scope per bounded-follow-on framing |

---

## Architecture

### Email-mediated upgrade request (opt-in)

`ptr_consent_service.request_upgrade(... send_email: bool = False, ...)`
extends the Step 4.1 canonical signature with an opt-in kwarg. When
`send_email=True`, the helper `_email_partner_admins_for_consent_request`
fires AFTER the existing in-app notify call site (state already
flushed; best-effort discipline preserved).

**Recipient resolution** mirrors `notify_tenant_admins` cohort
canonical: query `User` join `Role` filtered to
`User.is_active=True AND Role.slug='admin'` against the partner
tenant. Per-recipient `delivery_service.send_email_with_template`
calls — one `DocumentDelivery` row per admin per Q2 (NOT BCC blast).

**Best-effort discipline preservation** (Step 4.1 contract preserved):
the email helper is wrapped in try/except. Failure NEVER blocks
consent state mutation OR in-app notify. Per-recipient failures are
also isolated via inner try/except — one admin's bounce doesn't
cascade to other admins' sends.

**`company_id=partner_tenant_id`** per Phase D-9 mandatory threading
— DocumentDelivery row attributes to the receiving tenant's audit
log scope.

**Cross-primitive audit linkage** per Q7: `DocumentDelivery.metadata_json`
JSONB carries:
- `relationship_id` — PTR row id for traceability
- `requesting_tenant_id`, `partner_tenant_id` — both endpoints
- `step_5_1_category="calendar_consent_upgrade_request"` — discriminator
- `caller_module="ptr_consent_service.request_upgrade_email"` — set on
  the dedicated column (not in metadata)

Future query: "what emails were sent for relationship X?" → SQL
search on `metadata_json->>'relationship_id'`.

### Managed email template (`email.calendar_consent_upgrade_request`)

Template seeded via `scripts/seed_calendar_step51_email_template.py`
following Phase 6 + Phase 8b + Phase 8d.1 idempotent state machine:

  - Fresh install (no row matching template_key) → **create v1 active**
  - Exactly 1 version + body+subject **matches** seed → **noop_matched**
  - Exactly 1 version + body or subject **differs** → **deactivate v1
    + create v2 active** (platform update)
  - Multiple versions exist (admin customization) → **skip with
    warning log**; manual reconciliation via document templates admin
    UI

**Template shape** parallels `email.portal_invite` (r45) +
`email.portal_password_recovery` (r43) — notification-style HTML email
to admin recipients with magic-link CTA to a settings page.

**Subject:** `"{{ requesting_tenant_name }} requests calendar consent upgrade"` (≤120 chars per email canon)

**Required Jinja vars:**
- `requesting_tenant_name`
- `partner_tenant_name`
- `recipient_first_name`
- `consent_upgrade_url` (link to `/settings/calendar/freebusy-consent`)
- `relationship_type`

**Optional Jinja vars:**
- `expires_in_copy`

### Cross-tenant Pulse widget (`calendar_consent_pending`)

Communications Layer per §3.26.16.10 hybrid contribution — placed
alongside `calendar_glance` + `email_glance`. Pattern parallels
`calendar_glance` Step 5 verbatim (3 density tiers + spaces_pin
Pattern 1 + click-through routing).

**Data source:** `ptr_consent_service.list_partner_consent_states`
(canonical at line 530-610) filtered to
`state == "pending_inbound"` (partner has consented to full_details;
this side hasn't accepted yet). Zero new DB query — pure filter +
aggregation in Python.

**Tenant isolation:** `list_partner_consent_states` already
tenant-scopes via `PlatformTenantRelationship.tenant_id ==
caller_tenant_id`; cross-tenant PTRs do NOT surface on the caller's
widget (verified by `TestConsentPendingWidget::test_tenant_isolation_cross_tenant_ptr_does_not_surface`).

**Three density tiers + spaces_pin:**
- **Default ≥121px**: UserCheck icon + "Requests" eyebrow + mono count
  + top requester body (1 line: tenant label) + "Review consent
  requests →" footer
- **Compact 101-120px**: header row + requester collapsed to single
  line; footer dropped
- **Ultra-compact 80-100px**: single-row icon + label + count
- **Spaces-pin** (sidebar): Pattern 1 — single-line icon + label +
  count badge

**Click-through routing:**
- Single-request surface (1 pending row) → `/settings/calendar/freebusy-consent?relationship_id={id}` direct deep-link
- Multi-request surface (2+ pending rows) → `/settings/calendar/freebusy-consent` (list view)
- Empty → `/settings/calendar/freebusy-consent` (page renders its own empty state)

**View-only widget per §12.6a** — no inline accept/revoke from the
widget. The settings page is the canonical action surface.

**Empty state**: "No pending consent requests" canonical copy when
`has_pending=False`. Cross-vertical default-ship per Q4 — every
tenant sees the widget; tenants with no PTR partnerships see the
empty state.

**Endpoint:** `GET /api/v1/widget-data/calendar-consent-pending`
returns the canonical shape `{has_pending, pending_consent_count,
top_requester_name, top_requester_tenant_label,
target_relationship_id}`.

---

## Files added / modified

### Backend (new)

| File | Purpose |
|---|---|
| `scripts/seed_calendar_step51_email_template.py` | Idempotent managed email template seed |
| `app/services/widgets/calendar_consent_pending_service.py` | Widget data service |
| `tests/test_calendar_step51_consent_extensions.py` | 15 backend tests |
| `docs/calendar_step51_email_consent_request.md` | This doc |

### Backend (modified)

| File | Change |
|---|---|
| `app/services/calendar/ptr_consent_service.py` | `send_email` kwarg on `request_upgrade` + `_email_partner_admins_for_consent_request` helper (~140 LOC additional) |
| `app/services/delivery/delivery_service.py` | `metadata` kwarg added to `send_email_with_template` (forward-compat extension) |
| `app/services/widgets/widget_registry.py` | `calendar_consent_pending` widget definition |
| `app/api/routes/widget_data.py` | `GET /calendar-consent-pending` endpoint |

### Frontend (new)

| File | Purpose |
|---|---|
| `components/widgets/foundation/CalendarConsentPendingWidget.tsx` | 3 density tiers + spaces_pin |
| `tests/e2e/calendar-phase-w4b-step51.spec.ts` | Playwright smoke (3 scenarios) |

### Frontend (modified)

| File | Change |
|---|---|
| `components/widgets/foundation/register.ts` | Register `calendar_consent_pending` |

---

## Test posture

**Backend tests shipped Step 5.1:** 15 in
`test_calendar_step51_consent_extensions.py` across 5 test classes —
TestEmailTemplateSeed × 3 (fresh seed creates template + v1 active,
re-run noop_matched, variable_schema declares canonical Jinja vars +
subject ≤120 chars), TestPtrConsentEmailIntegration × 5 (default off
no rows, send_email=True per-admin fan-out, email failure does NOT
block consent or notify, metadata carries relationship_id +
caller_module, no admins no rows consent still succeeds),
TestConsentPendingWidget × 4 (empty no relationships, empty no
pending_inbound, populated with pending_inbound, tenant isolation
cross-tenant does NOT surface), TestWidgetEndpointAndRegistry × 2
(widget definition seeded canonical shape, endpoint returns canonical
shape), TestEndToEndIntegration × 1 (request_upgrade send_email=True
full flow — state mutation + audit log + in-app notify + per-admin
DocumentDelivery rows).

**Playwright smoke:** 3 scenarios in
`calendar-phase-w4b-step51.spec.ts` (endpoint smoke, empty state
payload, widget definition seeded).

**No new migrations.** Migration head unchanged at
`r72_ptr_consent_metadata`. Step 5.1 ships pure service-layer +
frontend + Python-script-seed work.

**Frontend tsc clean** + vitest unaffected (no new vitest tier tests
for the widget per Step 5 vitest deferral pattern).

---

## Calendar primitive arc closure

**Step 5.1 closes the Calendar primitive arc at canon-faithful
depth.** All canonical Calendar primitive scope per §3.26.16
substantively shipped:

  - Steps 1-2: Entity foundation + provider abstraction + RRULE
    engine + free/busy substrate
  - Step 3: Outbound infrastructure + iTIP scheduling + state-changes-
    generate-events + Email primitive cross-primitive iTIP REPLY
    routing
  - Step 4: 5 action_types + cross-tenant joint events + bilateral
    acceptance flow + magic-link contextual surface
  - Step 4.1: PTR consent UI + bilateral consent state machine
  - Step 5: Cross-surface rendering + native event detail page +
    iTIP REPLY UI notifications + granularity coarsening
  - **Step 5.1: PTR-consent extensions (this work) — email-mediated
    requests + cross-tenant Pulse widget**

### Remaining Calendar work canonically deferred

Per §3.26.16.21 strategic vision deferral catalog + substrate-
readiness arc dependencies:

- **Step 5.2 candidates** (if tenant signal warrants):
  - accept_upgrade + revoke_upgrade cross-tenant email integration
  - Per-tenant opt-out flag (`Company.settings_json.email.cross_tenant_requests_disabled`)
  - Per-tenant brand customization for email template (Workshop fork
    follows existing `email.*` pattern)

- **Substrate-readiness arc dependencies:**
  - Calendar Workshop integration per §3.26.16.25
  - Calendar Intelligence integration per §3.26.16.24
  - Calendar Period Pulse via §3.26.12.4 scoped Pulse infrastructure
  - Coordination Focus participants integration via §3.26.11.13
  - Briefing structured-sections via Phase W-4b sequence steps 9-11
  - Calendar saved-view integration (after D6 hygiene + saved_views
    infrastructure)

- **§3.26.16.21 strategic vision deferral catalog:**
  CalDAV + advanced RRULE + virtual meeting links + N-way scheduling
  + cross-tenant federation + AI-drafted scheduling + multi-day
  timezone + SMS/Phone-integrated scheduling

---

## Sequencing forward

After Step 5.1 ships, sequencing options (user direction):

1. **Job Coordination Focus first concrete implementation** (Coordination Focus primitive arc)
2. **Generation Focus first concrete template** (Generation Focus primitive arc)
3. **Aesthetic Phase III closure** (Sessions 5-6 — motion + final QA)
4. **Pre-existing bug hygiene:**
   - `CalendarAccountsPage.tsx:330` `asChild` violation (predates Step 1)
   - `saved_views/registry.py:492` D6 lint failure (separate cleanup)
