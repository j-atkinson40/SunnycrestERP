# Notifications — User Guide

_Admin-facing guide for the Notifications service in the Vault hub._

## What this service does

The in-app notification inbox. Every platform event that a user
should notice without being asked — a document was shared with your
tenant, a delivery failed, a period is ready to close, an account
transitioned into at-risk — writes a row to the `notifications`
table with a category, severity, and click-through link.

The Notifications service displays the unread feed, lets users
mark-read individually or in bulk, and gates the bell-icon badge in
the top-bar dropdown.

**Phase V-1d** promoted Notifications from a proto-service (widget
only) to a full Vault service. The former top-level `/notifications`
path now redirects to `/vault/notifications`. V-1d also merged the
deprecated `SafetyAlert` table into `notifications` with
`category='safety_alert'`, dropped the `safety_alerts` table, and
wired **5 new notification sources**.

## Where it lives in the nav

**Vault hub sidebar → Notifications** (`/vault/notifications`).
Also reachable from:

- The bell-icon dropdown in the top-bar ("View all notifications" →
  `/vault/notifications`).
- The `vault_notifications` overview widget on `/vault` (shows
  unread count + top 5).

Legacy `/notifications` URL redirects to `/vault/notifications`.

Visible to any authenticated user. There's no permission gate —
users see their own notifications, but nothing else.

## Key surfaces

| Surface | Purpose |
|---|---|
| **`/vault/notifications`** | Full feed, paginated, filter by category / unread-only / severity |
| **Bell-icon dropdown** | Top 10 unread, click-through to source or to the full feed |
| **`vault_notifications` widget** | Overview page — unread-only, top 5, click-to-mark-read |

## Notification sources (post-V-1d)

Every source writes via `notification_service.create_notification()`
or `notify_tenant_admins()` with a `category` string. Categories
visible today:

| Category | Source | Severity | Fan-out pattern |
|---|---|---|---|
| `safety_alert` | `safety_service` (and pre-V-1d migrated rows from the old `safety_alerts` table) | critical / high / medium / low | Tenant admins |
| `share_granted` | `document_sharing_service.grant_share` | info | Target tenant admins |
| `delivery_failed` | `delivery_service._notify_delivery_failed` (terminal failure, NOT `rejected` status) | high | Owning tenant admins |
| `signature_requested` | `signature_service._advance_after_party_signed` | info | Internal signer only (external signers get email only) |
| `compliance_expiry` | `vault_compliance_sync` | high (≤7 days/overdue) or medium | Tenant admins |
| `account_at_risk` | `health_score_service.calculate_health_score` | high | Tenant admins (transition-only) |
| `employee`, `order`, `invoice`, etc. | Pre-V-1d platform events (profile updates, order state transitions, invoice reminders) | varies | Varies |

**Dedup semantics.** `compliance_expiry` dedupes by
(company_id, category, source_reference_id) — repeated `sync_compliance_expiries`
runs don't re-fire for the same item. `account_at_risk` dedupes by
capturing `prior_score` before mutation — only fires on transition
*into* at_risk, not on steady-state scoring.

**No rate limiting today.** A tenant with 50 compliance items
expiring in the next 7 days gets 50 notifications at once. Tracked
in DEBT.md as a future-polish item (per-category rate limits +
daily digest mode).

## Common workflows

### Read and dismiss

1. Click the bell icon → see top 10 unread.
2. Click any notification → marks read + navigates to its `link`
   (if set).
3. Click **"Mark all read"** in the dropdown footer → bulk-ack all
   unread.
4. Click **"View all notifications"** → `/vault/notifications`.

### Full feed

1. `/vault/notifications`.
2. Filter by category (multi-select), unread-only, severity, date
   range.
3. Row click = same as dropdown click (mark read + navigate to link).
4. **Bulk actions:**
   - Select rows via checkbox → **"Mark selected read"**.
   - Select all visible → **"Mark all visible read"**.

### Follow a notification to its source

Every row has a `link` pointing at the source surface. Examples:

| Category | Link pattern |
|---|---|
| `safety_alert` | `/safety/{reference_type}/{reference_id}` — e.g. `/safety/equipment_inspection/abc-123` |
| `share_granted` | `/vault/documents/{doc_id}` — inbox entry for the shared document |
| `delivery_failed` | `/admin/documents/deliveries/{id}` — delivery detail with provider response |
| `signature_requested` | `/admin/documents/signing/envelopes/{id}` — envelope you need to sign |
| `compliance_expiry` | `/safety` — compliance hub (rolls up to safety dashboard) |
| `account_at_risk` | `/vault/crm/companies/{master_company_id}` — CRM company detail with health panel |

Click the notification. You land on the source surface with full
context. If a source changes its URL scheme, update the writer —
the notification is just the pointer.

### Acknowledge a safety alert

Safety alerts merged from the old `safety_alerts` table into
`notifications` with `category='safety_alert'` in V-1d. The safety
endpoints (`GET /safety/alerts`, `POST /safety/alerts/{id}/acknowledge`)
now query Notification under the hood and return AlertResponse-shaped
dicts for backward compat.

To acknowledge from the Vault notifications feed:

1. `/vault/notifications` → filter by category=safety_alert.
2. Click the row — navigates to `/safety/...`.
3. From the safety dashboard, click **"Acknowledge"**.
4. Backend calls `safety_service.acknowledge_alert()` which marks
   the underlying Notification `is_read=True` + sets
   `acknowledged_by_user_id` + `acknowledged_at`.

The acknowledged alert drops out of the active-alerts list but
stays in the Notifications feed (read, not hidden).

## SafetyAlert merged history (for devs)

**Short version:** the `safety_alerts` table was dropped in V-1d.
Safety alerts now live in `notifications` with
`category='safety_alert'`.

**Long version:** Pre-V-1d, the platform had two parallel notify
surfaces — `notifications` (in-app inbox) and `safety_alerts` (a
specialty table with severity, due_date, acknowledged_by,
reference_type/id). The audit at V-1 found that no production code
ever actually created `SafetyAlert` rows — the writers were stubs
that never got wired. V-1d cleaned this up:

- Extended `notifications` with 6 alert-flavor columns (severity,
  due_date, acknowledged_by_user_id, acknowledged_at,
  source_reference_type, source_reference_id).
- Data-migrated any existing SafetyAlert rows to notifications via
  admin fan-out (one notification per active admin per tenant,
  joined via `Role.slug='admin'`). Type coercion: severity → type
  tone (critical→error, high→warning, else info), keeping the
  original severity in the new severity column.
- Dropped the `safety_alerts` table. Downgrade recreates an empty
  schema — data is not restorable.
- Rewrote `safety_service.list_alerts` + `acknowledge_alert` to
  query Notification under the hood, returning AlertResponse-shaped
  dicts.

Frontend code that reads safety alerts via `/api/v1/safety/alerts`
didn't notice — the contract is preserved. New code writing safety
alerts should call `notification_service.create_notification(...,
category="safety_alert", severity=..., ...)` directly.

## Permission model

- **Visible to any authenticated tenant user.** No
  `required_permission` on the Vault service descriptor.
- **Users see their own notifications.** Filtered by `user_id =
  current_user.id`. No cross-user visibility.
- **Admin fan-out** writes one row per active admin user per
  tenant (joined via `Role.slug='admin'`). An admin's own fan-out
  arrives in their own feed.
- **No super-admin "see all notifications"** surface today. If you
  need a tenant-wide view, query `notifications` directly or
  contact platform ops.

## Related services

- **Documents.** `share_granted` (target admins), `delivery_failed`
  (owning admins), `signature_requested` (internal signer). Links
  route to `/vault/documents/*` surfaces.
- **Compliance (Safety).** `compliance_expiry` fires from
  `vault_compliance_sync` when a VaultItem with
  `event_type="compliance_expiry"` is created. Covers equipment
  inspections, training renewals, OSHA 300A posting, etc.
- **CRM.** `account_at_risk` fires on health-score transition. Links
  to `/vault/crm/companies/{id}`.
- **Delivery.** Failed deliveries fan out a notification in addition
  to writing the `document_deliveries` row. `rejected` (SMS stub
  not implemented) does NOT fire — would be non-actionable noise.

## Known limitations

### No per-user notification preferences

Every eligible user receives every notification in real time.
There's no per-user per-category opt-out, no daily digest mode, no
quiet hours. A tenant with 10 active admins gets 10 copies of every
admin fan-out (one per admin).

Tracked in DEBT.md as "Notification preferences — no per-category
opt-out / digest." Likely work for this is a
`user_notification_preferences` table keyed on (user_id, category)
with enabled + delivery_mode (realtime / daily_digest / never) +
channel (in_app / email / both).

### No rate limiting on noisy categories

`compliance_expiry` dedupes by source_reference_id so the same item
doesn't re-fire. But a batch run that scans 100 expiring items
produces 100 × N-admins notifications in one transaction. Should
probably coalesce or throttle.

### Category vocabulary isn't a central registry

Each source site hardcodes its own category string. Frontend
filtering works but there's no typed enum, no per-category icon /
color mapping, no "add category X everywhere" mechanism. A future
phase adds `app/services/notifications/categories.py` with a
typed enum or frozen dict → display metadata mapping.

### Merged SafetyAlert history not cleanly delineated in UI

Pre-V-1d SafetyAlert rows that migrated to `notifications` with
`category='safety_alert'` appear alongside any post-V-1d safety
alerts. There's no visual distinction between "migrated" and
"native" rows. Doesn't matter for most users; documented for devs
who notice the gap in historical reporting.

See [`../DEBT.md`](../DEBT.md) for the full list of deferred items.
