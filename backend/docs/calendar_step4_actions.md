# Calendar Step 4 — operational-action affordance arc

Phase W-4b Layer 1 Step 4 ships the canonical 5 action_types per
§3.26.16.17 + cross-tenant joint events activation per §3.26.16.20 +
bilateral acceptance flow per §3.26.16.14 + magic-link contextual
surface per §3.26.11.9 + §14.10.5 against the Step 1+2+3 substrate +
Path B substrate consolidation foundation.

**Migration head**: `r70_platform_action_tokens` → `r71_calendar_step4_actions`.

---

## Architecture

### Storage shape (Q1 confirmed)

| Where | Column / Field | Notes |
|---|---|---|
| `calendar_events.action_payload` | `JSONB DEFAULT '{}' NOT NULL` | Mirrors `email_messages.message_payload` Email shape per substrate consolidation. Actions live at `action_payload['actions'][idx]` with canonical shape per §3.26.16.17. GIN index `ix_calendar_events_action_payload` for cross-primitive action queries. |
| `cross_tenant_event_pairing.paired_at` | `NULLABLE` (Q2 confirmed) | NULL = pending bilateral acceptance; timestamp = finalized post-accept. |
| `cross_tenant_event_pairing.event_b_id` | `NULLABLE` | Pending state: partner-side `CalendarEvent` row not yet created (created at accept-time). |
| `platform_action_tokens.linked_entity_type` | `'calendar_event'` | All Calendar action tokens carry this discriminator. CHECK constraint enumerates `('email_message', 'calendar_event', 'sms_message', 'phone_call')` per Path B substrate consolidation. |

### Canonical 5 action_types (per §3.26.16.17)

| action_type | action_target_type | Operational use case | State propagation on accept |
|---|---|---|---|
| `service_date_acceptance` | `fh_case` | FH director accepts service date proposed by manufacturer | event status="confirmed"; FHCase.service_date set to proposed_start_at |
| `delivery_date_acceptance` | `sales_order` | FH or cemetery accepts delivery time | event status="confirmed"; SalesOrder.scheduled_date set |
| `joint_event_acceptance` | `cross_tenant_event` | Bilateral cross-tenant event acceptance | event status="confirmed"; cross_tenant_event_pairing.paired_at set |
| `recurring_meeting_proposal` | `cross_tenant_event` | Recurring meeting proposal with bilateral acceptance (en bloc per Q4) | event status="confirmed"; pairing finalized; per-instance overrides via existing calendar_event_instance_overrides |
| `event_reschedule_proposal` | `calendar_event` | Post-confirmation event time modification + downstream cascade | event.start_at/end_at updated to proposed times; cascade impact recorded in audit completion_metadata |

### Outcomes vocabulary

`accept` / `reject` / `counter_propose`. `counter_propose` requires `completion_note` per registered descriptor + caller must supply `counter_proposed_start_at` + `counter_proposed_end_at`. Counter-propose chains a NEW action at next `action_idx` per §3.26.16.20 iterative-negotiation pattern; original action transitions to terminal `counter_proposed`.

### Status flow

`pending` → `accepted` | `rejected` | `counter_proposed` (terminal). Re-commit on terminal returns 409 `ActionAlreadyCompleted`.

---

## Service modules

### `app/services/calendar/calendar_action_service.py`

Owns the five ActionTypeDescriptor registrations + commit handlers. Registered against `app.services.platform.action_registry._REGISTRY` at module import time via Calendar package init side-effect import (parallels Email package init pattern).

Public API:
- 5 `build_*_action()` shape helpers (parallel `build_quote_approval_action`)
- `get_event_actions(event)` / `get_action_at_index(event, idx)` / `append_action_to_event(event, action)` / `replace_action_at_index(...)`
- `issue_action_token(db, *, tenant_id, event_id, action_idx, action_type, recipient_email, ttl_days=7)` — Calendar-specific facade; maps `event_id` kwarg to substrate's `linked_entity_id` with `linked_entity_type='calendar_event'`
- `commit_action(db, *, event, action_idx, outcome, ...)` → returns `CommitResult(updated_action, target_status, counter_action_idx, pairing_id)`
- `compute_reschedule_cascade(db, event)` — walks `calendar_event_linkages` + `cross_tenant_event_pairing` for §14.10.5 cascade impact disclosure
- `chain_counter_proposal(...)` — appends new chained action with counter-proposed time at next idx

Re-exported from substrate: `lookup_action_token`, `consume_action_token`, `lookup_token_row_raw`, `generate_action_token`, `build_magic_link_url`, error classes.

### `app/services/calendar/cross_tenant_pairing_service.py`

Owns the cross-tenant pairing lifecycle per §3.26.16.14 + §3.26.16.20.

Public API:
- `propose_pairing(db, *, initiating_event, partner_tenant_id, ...)` — creates pending row (paired_at=NULL, event_b_id=NULL)
- `finalize_pairing(db, *, pairing, partner_event_id=None)` — stamps paired_at; backfills event_b_id; per-side audit log
- `revoke_pairing(db, *, pairing, revoking_tenant_id, reason=None)` — either tenant can revoke; per-side audit log
- `get_pairing(db, *, pairing_id)` / `list_pairings_for_tenant(db, *, tenant_id, status=None)` / `get_pairing_status(pairing)`
- `list_participants_for_tenant_side(db, *, pairing, tenant_id)` — per-tenant participant routing per §3.26.11.7

### `app/services/calendar/outbound_service.send_event` extension (Q5)

Per Q5 confirmed pre-build: default-on with `embed_magic_links=False` opt-out. When True (default), every external (`is_internal=False`) attendee on the event gets a platform_action_token issued + magic-link URL composed against the FIRST pending action in `event.action_payload['actions']` (or caller-supplied `magic_link_action_type`). Internal attendees skipped per §3.26.11.9.

Returns dict shape extended with `magic_links: list[{recipient_email, token, url, action_idx, action_type}]`. Audit log records `magic_links_issued` count.

---

## API routes

| Route | Auth | Purpose |
|---|---|---|
| `POST /api/v1/calendar-events/{event_id}/actions/{action_idx}/commit` | JWT (tenant member) | Inline action commit from authenticated event detail surface |
| `GET /api/v1/calendar/actions/{token}` | Public (token IS auth) | Magic-link landing surface — returns canonical action context with cascade_impact for reschedule actions |
| `POST /api/v1/calendar/actions/{token}/commit` | Public (token IS auth) | Magic-link commit — atomic with token consumption |

**Cross-primitive isolation enforced at route level**: GET / POST `/calendar/actions/{token}` reject tokens with `linked_entity_type != 'calendar_event'` with HTTP 400. Email tokens (`linked_entity_type='email_message'`) cannot be consumed at calendar routes; calendar tokens cannot be consumed at email routes.

Pattern parallels Email Step 4c `email_actions.py` shape verbatim.

---

## Frontend

### `pages/calendar/MagicLinkActionPage.tsx`

Public, token-authenticated route at `/calendar/actions/:token` per §14.10.5 verbatim:

- Tenant-branded h-12 header (brand color inline-styled)
- Mobile-first max-w-md container
- Action title `text-h3 font-plex-serif text-content-strong`
- Proposed details rendered as Pattern 2 card with date/time + location + organizer attribution
- Three-button action stack: primary Accept (brass) + outline Propose alternative + ghost Decline
- Counter-proposal flow: counter-time picker (datetime-local inputs in font-plex-mono) + optional note → submits new action
- Decline flow: optional decline reason → action commit
- Reschedule flow: cascade impact disclosure ("Rescheduling this event will affect: N linked entities, M paired cross-tenant events") in status-warning-muted panel
- Footer: expiry-in-N-days indicator + privacy assurance copy
- NO Bridgeable navigation; NO sidebar; NO inbox; NO Bridgeable login flow

State machine: loading → error_invalid (401) | error_expired (410) | error_other | ready → submitting → done (terminal).

### `services/calendar-actions-service.ts`

Three exports:
- `getMagicLinkAction(token)` — bare axios (no auth header) → magic-link details
- `commitMagicLinkAction(token, body)` — bare axios → commit response
- `commitInlineCalendarAction(eventId, actionIdx, body)` — apiClient (JWT) → commit response

`CalendarMagicLinkError` carries HTTP status + detail for state-machine routing.

---

## Audit trail

Every action commit writes a `calendar_audit_log` row with:
- `action='calendar_action_committed'`
- `entity_type='calendar_event' + entity_id=event.id`
- `changes={action_idx, action_type, outcome, auth_method, target_type, target_id, target_status, actor_email, has_completion_note}`

Cross-tenant pairing lifecycle adds:
- `cross_tenant_pairing_proposed` (initiator side)
- `cross_tenant_pairing_finalized` (per-side audit logs per §3.26.11.10)
- `cross_tenant_pairing_revoked` (per-side audit logs)

Magic-link views write `calendar_magic_link_viewed` rows with click_count + consumed state (parallel to Email's `magic_link_viewed`).

Body content NEVER logged. Tokens NEVER logged.

---

## Test coverage (67 backend tests)

| Test file | Tests | Coverage |
|---|---|---|
| `test_calendar_step4_action_types.py` | 27 | 5 ActionTypeDescriptor registrations + action shape helpers + action_payload accessors + 5 commit_handlers (accept/reject/counter_propose state propagation) + counter-proposal chaining + reschedule cascade |
| `test_calendar_step4_cross_tenant_pairing.py` | 18 | propose/finalize/revoke lifecycle + bilateral state propagation + revocation discipline + per-tenant participant routing |
| `test_calendar_step4_magic_link.py` | 14 | Token issuance via substrate + 7-day TTL + single-action consumption + cross-primitive isolation + magic-link API surface + counter-proposal API |
| `test_calendar_step4_outbound_integration.py` | 8 | External attendee detection + magic-link embedding + opt-out + audit metadata |

Plus Calendar Steps 1+2+3 (138) + Email Steps 1-5 (196) + Platform action substrate (25) regression continues to pass.

---

## Cross-references

- BRIDGEABLE_MASTER §3.26.16.17 — Operational-state-coupled-to-calendar (5 action_types canonical)
- BRIDGEABLE_MASTER §3.26.16.18 — State-changes-generate-calendar-events (state propagation table)
- BRIDGEABLE_MASTER §3.26.16.20 — Cross-tenant native scheduling (iterative-negotiation pattern + per-tenant copy semantics)
- BRIDGEABLE_MASTER §3.26.16.14 — Bilateral acceptance flow
- BRIDGEABLE_MASTER §3.26.11.7 — Per-tenant participant routing
- BRIDGEABLE_MASTER §3.26.11.9 — Magic-link participant scope (default lockdown + per-template declaration)
- BRIDGEABLE_MASTER §3.26.11.10 — Cross-tenant Focus consent (bilateral acceptance precedent)
- BRIDGEABLE_MASTER §3.26.15.8 — Email primitive audit trail discipline (reused for Calendar)
- DESIGN_LANGUAGE §14.9.5 — Email magic-link visual canon (precedent)
- DESIGN_LANGUAGE §14.10.5 — Calendar magic-link visual canon (canonical)
- `backend/docs/platform_action_substrate.md` — Path B substrate consolidation foundation
- Migration `r71_calendar_step4_actions.py`
- `app/services/calendar/calendar_action_service.py`
- `app/services/calendar/cross_tenant_pairing_service.py`
- `app/api/routes/calendar_actions.py`
- `frontend/src/pages/calendar/MagicLinkActionPage.tsx`
