# Calendar Step 4.1 — PTR consent upgrade UI write-side

Phase W-4b Layer 1 Step 4.1 ships the bilateral consent state machine +
settings page UI + audit trail + V-1d in-app notifications +
latent-privacy bug fix in Step 3 freebusy read-side. Bounded follow-on
closure of Calendar Step 4 substrate per §3.26.16.6 + §3.26.16.14 +
§3.26.11.10 cross-tenant Focus consent canonical precedent.

**Migration head**: `r71_calendar_step4_actions` → `r72_ptr_consent_metadata`.

---

## Architecture

### Storage shape (Q1 confirmed pre-build)

PTR's existing per-direction-row architecture already encodes per-side
intent. Each row's `calendar_freebusy_consent` value (shipped at Step 3)
reflects that side's stated consent. **No schema rework needed for the
state machine itself.**

| Row direction | `calendar_freebusy_consent` value semantics |
|---|---|
| forward (caller→partner, `tenant_id=caller`) | This tenant's stated consent |
| reverse (partner→caller, `tenant_id=partner`) | Partner tenant's stated consent |

Two metadata columns added in `r72_ptr_consent_metadata` for settings-
page rendering ergonomics (Q3 confirmed):

| Column | Purpose |
|---|---|
| `calendar_freebusy_consent_updated_at` (nullable timestamptz) | When consent was last flipped on this side |
| `calendar_freebusy_consent_updated_by` (nullable FK → users.id ON DELETE SET NULL) | Operator who flipped it |

NULL when consent has never been changed (default-state rows from
pre-Step-4.1 era; not backfilled).

### Three-state machine

Resolved via `resolve_consent_state(forward, reverse) -> ConsentState`:

| `(this_side, partner_side)` | State | UI label |
|---|---|---|
| `(free_busy_only, free_busy_only)` | `default` | "Privacy-preserving" |
| `(full_details, free_busy_only)` | `pending_outbound` | "Awaiting partner" |
| `(free_busy_only, full_details)` | `pending_inbound` | "Partner requested upgrade" |
| `(full_details, full_details)` | `active` | "Full details" |

Missing reverse row (partner has no PTR row) is treated as
`free_busy_only` per privacy-default discipline (§3.26.16.6).

### State transitions

| Action | Caller flips | Valid prior states | New state | Audit scope |
|---|---|---|---|---|
| `request_upgrade` | own row → `full_details` | `default` (most common) OR `pending_inbound` | `pending_outbound` (or `active` if partner already at `full_details`) | caller side only (§3.26.11.10 tenant-side-only event) |
| `accept_upgrade` | own row → `full_details` | `pending_inbound` only | `active` | both sides (joint event per §3.26.11.10) |
| `revoke_upgrade` | own row → `free_busy_only` | any non-default state | `default` (or `pending_inbound` if partner stays at full_details) | both sides (joint event) |

Either tenant can revoke unilaterally per §3.26.16.6 + §3.26.11.10.

### Latent privacy bug fix (Q2 confirmed pre-build)

Pre-Step-4.1 logic in `freebusy_service.query_cross_tenant_freebusy`:
```python
bilateral_full_details = all(level == "full_details" for level in consent_levels)
```

This had two failure modes:
1. `all([])` returns `True` — vacuously true when both PTR rows missing
2. `all([full_details])` returns `True` — when only forward exists (caller→partner) with `full_details` and reverse missing, response upgraded to `full_details` even though partner never had a chance to consent

Step 4.1 fix:
```python
bilateral_full_details = (
    forward_row is not None
    and reverse_row is not None
    and forward_row.calendar_freebusy_consent == "full_details"
    and reverse_row.calendar_freebusy_consent == "full_details"
)
```

Privacy-default discipline preserved per §3.26.16.6 — bilateral upgrade
requires BOTH directions of the PTR pair to exist AND both at
`full_details`. Test regression: `TestLatentPrivacyBugFix.test_single_row_full_details_does_not_upgrade_to_bilateral`.

---

## Service module

### `app/services/calendar/ptr_consent_service.py`

Public API:

| Function | Purpose |
|---|---|
| `request_upgrade(db, *, requesting_tenant_id, relationship_id, requested_by_user_id) -> dict` | Flip caller's PTR row to `full_details`; write audit log; notify partner admins |
| `accept_upgrade(db, *, accepting_tenant_id, relationship_id, accepted_by_user_id) -> dict` | Flip caller's PTR row to `full_details`; write per-side audit logs; notify requesting admins; bilateral consent now active |
| `revoke_upgrade(db, *, revoking_tenant_id, relationship_id, revoked_by_user_id) -> dict` | Flip caller's PTR row to `free_busy_only`; write per-side audit logs; notify partner admins |
| `list_partner_consent_states(db, *, tenant_id) -> list[dict]` | List partner tenants + per-relationship consent state for settings page |
| `resolve_consent_state(forward, reverse) -> ConsentState` | Pure state-machine resolver from PTR row pair |

Cross-tenant existence-hiding: `_resolve_pair_for_caller` returns 404
`PtrConsentNotFound` if relationship_id isn't owned by caller's tenant
(prevents cross-tenant id enumeration).

### Audit trail per §3.26.11.10

Three actions written to `calendar_audit_log`:

| Action | Tenant scope | Notes |
|---|---|---|
| `consent_upgrade_requested` | requesting tenant only | Tenant-side-only event per canon |
| `consent_upgrade_accepted` | both tenants (per-side) | Joint event per canon |
| `consent_revoked` | both tenants (per-side; same-tenant deduped) | Joint event per canon |

`changes` JSONB shape: `{relationship_id, partner_tenant_id, requesting_tenant_id|revoking_tenant_id, prior_state, new_state}`.

### Notifications per Q4 confirmed (V-1d substrate)

Three categories via `notification_service.notify_tenant_admins`:

| Category | When | Recipient |
|---|---|---|
| `calendar_consent_upgrade_request` | request_upgrade | partner tenant admins |
| `calendar_consent_upgrade_accepted` | accept_upgrade | requesting tenant admins |
| `calendar_consent_upgrade_revoked` | revoke_upgrade | partner tenant admins |

Each carries `link='/settings/calendar/freebusy-consent'` +
`source_reference_type='platform_tenant_relationship'` +
`source_reference_id=relationship_id`. Best-effort fan-out (try/except
+ logger.exception); notification failure never blocks the consent
state mutation.

---

## API routes

| Route | Auth | Purpose |
|---|---|---|
| `GET /api/v1/calendar/consent` | JWT (tenant member) | List partner tenants + per-relationship consent state |
| `POST /api/v1/calendar/consent/{relationship_id}/request` | JWT | Flip to `full_details` (request bilateral upgrade) |
| `POST /api/v1/calendar/consent/{relationship_id}/accept` | JWT | Flip to `full_details` (accept inbound request) |
| `POST /api/v1/calendar/consent/{relationship_id}/revoke` | JWT | Flip to `free_busy_only` (unilateral revoke) |

All endpoints tenant-scoped via `get_current_user`; cross-tenant ids
return 404 (existence-hiding).

---

## Frontend

### `pages/settings/CalendarConsentPage.tsx`

Settings page at `/settings/calendar/freebusy-consent` within Calendar
admin namespace (alongside `/settings/calendar`,
`/settings/calendar/oauth-callback`, `/settings/calendar/drafts`).

Surfaces:
- Page title + canonical description
- Refresh button
- Table of partner tenants: partner name + relationship_type + state
  badge + last-updated metadata + per-row action button
- Four state badges via StatusPill: Privacy-preserving / Awaiting
  partner / Partner requested upgrade / Full details
- Per-row actions per state:
  - `default` → [Request full details]
  - `pending_outbound` → [Cancel request] (revoke)
  - `pending_inbound` → [Accept]
  - `active` → [Revoke]
- Confirmation dialog before any state mutation
- Empty state for tenants without partner relationships

**Avoids `asChild` violation per CLAUDE.md §12** — uses direct Button
components without Link composition (no `Button asChild Link`
pattern). Pre-existing CalendarAccountsPage.tsx ships an `asChild`
violation that predates Step 1; Step 4.1 settings page does NOT
reintroduce the same pattern.

### `services/calendar-consent-service.ts`

4 axios methods wrapping the 4 endpoints. Type mirrors of backend
Pydantic shapes.

### `App.tsx` route registration

`/settings/calendar/freebusy-consent` mounted under Calendar admin
namespace.

---

## Cross-references

- BRIDGEABLE_MASTER §3.26.11.10 — Cross-tenant Focus consent (canonical bilateral state machine pattern)
- BRIDGEABLE_MASTER §3.26.16.6 — Multi-tenant storage + cross-tenant masking inheritance (bilateral consent canonical)
- BRIDGEABLE_MASTER §3.26.16.14 — Bilateral acceptance flow (write-side at Step 4.1)
- BRIDGEABLE_MASTER §3.26.16.17 — Phase B Q13 refinement direction (substrate consolidation; not used at Step 4.1)
- Path B substrate: `app/services/platform/action_*.py` (not used at Step 4.1 since PTR consent doesn't flow through magic-link substrate)
- V-1d notification substrate: `app/services/notification_service.py::notify_tenant_admins`
- Migration `r72_ptr_consent_metadata.py`
- `app/services/calendar/ptr_consent_service.py`
- `app/services/calendar/freebusy_service.py` (Q2 latent-bug fix)
- `app/api/routes/calendar_consent.py`
- `frontend/src/pages/settings/CalendarConsentPage.tsx`
- `frontend/src/services/calendar-consent-service.ts`
- `tests/test_calendar_step4_1_ptr_consent.py` (24 backend tests)
