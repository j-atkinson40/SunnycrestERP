# Platform Action Substrate

Canonical action-token ledger powering kill-the-portal magic-link
contextual surfaces across the Email, Calendar, SMS, and Phone
primitives.

**Status**: shipped at migration `r70_platform_action_tokens` as the
substrate consolidation predecessor migration before Calendar Step 4.
Email primitive (r66) is the canonical first consumer; Calendar Step 4
+ SMS Step 4 + Phone Step 4 inherit the substrate without parallel-table
proliferation per §3.26.16.17 Phase B Q13 refinement direction note.

---

## Architecture

### Layer 1 — Database

Single table `platform_action_tokens` (renamed from `email_action_tokens`
at r70):

| Column | Type | Notes |
|---|---|---|
| `token` | `varchar(64)` PK | 256-bit URL-safe via `secrets.token_urlsafe(32)` |
| `tenant_id` | `varchar(36)` NOT NULL | FK → companies.id ON DELETE CASCADE |
| `linked_entity_type` | `varchar(32)` NOT NULL | CHECK ∈ `{email_message, calendar_event, sms_message, phone_call}` |
| `linked_entity_id` | `varchar(36)` NOT NULL | PK of the linked entity. NO FK — soft-delete via `revoked_at` per §3.26.16.18 audit canon |
| `action_idx` | `int` NOT NULL | Index into the linked entity's actions list |
| `action_type` | `varchar(64)` NOT NULL | Validated against the action_registry at issue time; NOT enforced at DB CHECK |
| `recipient_email` | `varchar(320)` NOT NULL | Lowercased + stripped at issue time |
| `expires_at` | `timestamptz` NOT NULL | Default 7-day TTL per §3.26.15.17 + §3.26.16.17 |
| `created_at` | `timestamptz` NOT NULL DEFAULT now() | |
| `consumed_at` | `timestamptz` | Stamped at single-action commit |
| `revoked_at` | `timestamptz` | Operator-side revocation (compromised-token surface) |
| `click_count` | `int` NOT NULL DEFAULT 0 | Audit visibility into multi-click patterns |
| `last_clicked_at` | `timestamptz` | |

Indexes:
- `ix_platform_action_tokens_linked_entity` btree (linked_entity_id)
- `ix_platform_action_tokens_active` btree (expires_at) WHERE consumed_at IS NULL AND revoked_at IS NULL

CHECK constraint:
- `ck_platform_action_tokens_linked_entity_type` on `linked_entity_type ∈ ('email_message', 'calendar_event', 'sms_message', 'phone_call')` — enumerated upfront so downstream Step 4 arcs (Calendar / SMS / Phone) inherit substrate without CHECK migration overhead.

**Why no FK on `linked_entity_id`** (per §3.26.16.18 audit canon):
magic-link tokens carry indefinite audit-trail value. Hard FK CASCADE
would silently destroy audit history when a linked entity is soft-
deleted. Service-layer cleanup via `revoked_at` is the canonical path;
soft-delete hooks on the linked entity revoke active tokens explicitly.

### Layer 2 — Registry

`app.services.platform.action_registry` exposes:

```python
@dataclass(frozen=True)
class ActionTypeDescriptor:
    action_type: str                    # canonical name, registry key
    primitive: PrimitiveType            # "email" | "calendar" | "sms" | "phone"
    target_entity_type: str             # action_target_type per canon
    outcomes: tuple[str, ...]
    terminal_outcomes: tuple[str, ...]
    commit_handler: Callable            # primitive-specific state propagation
    requires_completion_note: tuple[str, ...] = ()
```

Module-level singleton `_REGISTRY: dict[str, ActionTypeDescriptor]`.
Public API:
- `register_action_type(descriptor)` — idempotent re-registration
- `get_action_type(action_type) -> ActionTypeDescriptor` — raises `ActionRegistryError` on miss
- `list_action_types_for_primitive(primitive)` — per-primitive filter
- `expected_linked_entity_type(action_type) -> str` — canonical primitive-to-entity mapping

**Cross-primitive isolation**: `expected_linked_entity_type` resolves
via `PRIMITIVE_LINKED_ENTITY_TYPES` (canonical mapping). Token issuance
validates that the caller-supplied `linked_entity_type` matches the
action_type's owning primitive — `quote_approval` (Email primitive)
cannot be issued against `linked_entity_type='calendar_event'`. Cross-
primitive token issuance raises `CrossPrimitiveTokenMismatch` (HTTP 400).

### Layer 3 — Generic substrate

`app.services.platform.action_service` exposes:

| Function | Purpose |
|---|---|
| `generate_action_token() -> str` | 256-bit URL-safe token |
| `issue_action_token(db, *, tenant_id, linked_entity_type, linked_entity_id, action_idx, action_type, recipient_email, ttl_days=7) -> str` | INSERT row + return token |
| `lookup_action_token(db, *, token) -> dict` | SELECT + validate (raises on expired/consumed/invalid) + stamp click |
| `lookup_token_row_raw(db, *, token) -> dict \| None` | SELECT bypassing validation (terminal-state rendering) |
| `consume_action_token(db, *, token) -> None` | Stamp `consumed_at` |
| `commit_action(db, *, action, outcome, actor_user_id, actor_email, auth_method, completion_note=None, ip_address=None, user_agent=None, **handler_kwargs) -> dict` | Generic dispatcher → registered `commit_handler` |
| `build_magic_link_url(*, base_url, token, primitive_path='email') -> str` | Per-primitive URL composition |

### Layer 4 — Per-primitive facades

Each primitive's package init side-effect-imports a module that
registers its action_types. Pattern parallels
`app.services.triage.platform_defaults` (canonical precedent).

**Email primitive** (canonical first consumer, shipping at September scope):
- `app.services.email.email_action_service` — facade; preserves r66 / Step 4c API verbatim. Re-exports substrate symbols + retains email-specific helpers (`build_quote_approval_action`, Quote state propagation handler in `_commit_handler_quote_approval`, `ACTION_OUTCOMES_QUOTE_APPROVAL` / `TOKEN_TTL_DAYS` / `ACTION_TYPES` / `ACTION_STATUSES` constants).
- `app.services.email.__init__` imports `email_action_service` as a side effect → `quote_approval` ActionTypeDescriptor registered.

**Calendar primitive** (Calendar Step 4 inherits this substrate):
- Future `app.services.calendar.calendar_action_service` will register the 5 canonical action_types per §3.26.16.17 (`service_date_acceptance`, `delivery_date_acceptance`, `joint_event_acceptance`, `recurring_meeting_proposal`, `event_reschedule_proposal`).
- Calendar primitive's package init will side-effect-import this module.
- New routes at `/api/v1/calendar/actions/{token}` follow Email's `/api/v1/email/actions/{token}` precedent.

**SMS primitive** (SMS Step 4 inherits this substrate):
- §3.26.17.18 declares 5 canonical action_types (`customer_confirmation`, `driver_check_in_confirmation`, `delivery_arrival_acknowledgment`, `service_day_acknowledgment`, `cross_tenant_operational_acknowledgment`).
- Magic-link variant uses `linked_entity_type='sms_message'`.

**Phone primitive** (Phone Step 4 inherits this substrate):
- §3.26.18.20 declares 5 canonical action_types (`outbound_call_attempt_acknowledgment`, `inbound_call_action_item_review`, `compliance_review_required`, `voicemail_follow_up`, `cross_tenant_operational_acknowledgment`).
- All flow through `linked_entity_type='phone_call'`.

---

## Adding a new primitive's action_types

Five-step recipe for Calendar Step 4 (and SMS / Phone Step 4 by
analogy):

1. **Create primitive-specific facade module** — e.g.
   `app/services/calendar/calendar_action_service.py`. Import substrate
   symbols + retain primitive-specific shape helpers (e.g.
   `build_service_date_acceptance_action`).
2. **Define commit_handler callables** for each action_type. Handler
   signature:
   ```python
   def _commit_handler_service_date_acceptance(
       db, *, action, outcome, descriptor, actor_user_id, actor_email,
       auth_method, completion_metadata, completion_note, ip_address,
       user_agent, calendar_event, attendee, **_
   ) -> dict:
       ...
   ```
   Handler is responsible for primitive-specific state propagation
   (e.g. setting FHCase.service_date, finalizing cross-tenant pairing,
   audit log per §3.26.15.8).
3. **Register the descriptors** at module load:
   ```python
   register_action_type(ActionTypeDescriptor(
       action_type="service_date_acceptance",
       primitive="calendar",
       target_entity_type="fh_case",
       outcomes=("accept", "reject", "counter_propose"),
       terminal_outcomes=("accept", "reject", "counter_propose"),
       requires_completion_note=("counter_propose",),
       commit_handler=_commit_handler_service_date_acceptance,
   ))
   ```
4. **Side-effect import from primitive's package init**:
   ```python
   # app/services/calendar/__init__.py
   from app.services.calendar import calendar_action_service  # noqa: F401
   ```
5. **Ship primitive-specific routes** at `/api/v1/calendar/actions/{token}`
   that route through the same generic `commit_action` dispatcher.

No DB migration required. The central registry validates action_types
at issue + commit time; the CHECK constraint already enumerates all
four primitive linked_entity_type values.

---

## Audit trail discipline (§3.26.15.8)

Every action commit writes an audit log row via the primitive's
canonical audit helper (`_audit` for Email; analogous helpers for
Calendar / SMS / Phone). Audit row carries:
- action_idx + action_type + outcome
- auth_method (`bridgeable` | `magic_link` | `sms_keyword_reply` etc.)
- actor_email (lowercased)
- ip_address + user_agent (request metadata)
- target entity status post-commit

Body content NEVER logged. Tokens NEVER logged.

Magic-link click events also audit: `magic_link_viewed` rows track
click_count + consumed-vs-pending state for compliance + abuse
detection.

---

## Backwards-compat discipline (r70)

Substrate consolidation preserved:

1. **Email r66 / Step 4c imports unchanged**: `from
   app.services.email.email_action_service import (...)` continues to
   work for every public symbol. Facade re-exports substrate functions
   + retains email-specific helpers + constants.

2. **`issue_action_token(db, tenant_id=..., message_id=..., ...)`**:
   Email facade keeps the `message_id` kwarg for Step 4c callers.
   Internally maps to `linked_entity_type='email_message'` +
   `linked_entity_id=message_id` against the substrate.

3. **API routes preserved**: `/api/v1/email/actions/{token}` +
   `/api/v1/email/messages/{message_id}/actions/{action_idx}/commit`
   continue to serve the Email primitive's quote_approval flow.

4. **Frontend unchanged**: `MagicLinkActionPage` at `/email/actions/:token`
   continues to call email-scoped routes.

5. **Outbound service raw-SQL caller**: 2-line update at
   `app/services/email/outbound_service.py` — `:message_id` parameter
   key renamed to `:linked_entity_id` + new `:linked_entity_type`
   parameter added with literal `'email_message'`.

6. **Step 4c test fixture**: 1-line update at
   `tests/test_email_primitive_step4c.py` — raw SQL `UPDATE
   email_action_tokens` retargeted to `UPDATE platform_action_tokens`.

---

## Reference

- BRIDGEABLE_MASTER §3.26.15.17 — Email primitive operational-state-coupled-to-communication
- BRIDGEABLE_MASTER §3.26.16.17 — Calendar Step 4 operational-state-coupled-to-calendar
- BRIDGEABLE_MASTER §3.26.16.18 — Audit trail canonical (soft-delete via revoked_at)
- BRIDGEABLE_MASTER §3.26.16.20 — Cross-tenant joint events
- BRIDGEABLE_MASTER §3.26.17.18 — SMS Step 4 5 canonical action_types
- BRIDGEABLE_MASTER §3.26.18.20 — Phone Step 4 5 canonical action_types
- DESIGN_LANGUAGE §14.9.5 — Magic-link contextual surface canonical
- BRIDGEABLE_MASTER §3.26.7.5 — Architectural restraint discipline
- Migration `r70_platform_action_tokens.py`
- `app/services/platform/action_registry.py`
- `app/services/platform/action_service.py`
- `app/services/email/email_action_service.py` (facade)
- `tests/test_platform_action_substrate.py` (substrate-level coverage)
- `tests/test_email_primitive_step4c.py` (Email-side regression)
