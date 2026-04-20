# Bridgeable Vault — README

Developer entry point for the Bridgeable Vault hub. Architecture
details live in [`vault_architecture.md`](./vault_architecture.md).

## What this is

Bridgeable Vault is the shared foundational infrastructure layer that
every tenant sees regardless of vertical. It's the platform chassis
that the verticals configure views over — not a feature, not a module
you can disable. Five services currently register with the Vault hub
(Documents, Intelligence, CRM, Notifications, Accounting); more can
plug in by calling `register_service(...)`.

V-1 (eight phases, April 2026) consolidated the hub. See
[`vault_architecture.md`](./vault_architecture.md) for the full
design reference or [`vault_audit.md`](./vault_audit.md) for the
pre-V-1 retrospective.

## Key files

**Backend:**

| File | Purpose |
|---|---|
| `backend/app/services/vault/hub_registry.py` | Service descriptors + registration |
| `backend/app/services/widgets/widget_registry.py` | Widget definitions + seed |
| `backend/app/api/routes/vault.py` | Core Vault endpoints (`/services`, `/overview/widgets`, `/activity/recent`) |
| `backend/app/api/routes/vault_accounting.py` | Accounting admin endpoints (V-1e) |
| `backend/app/models/vault_item.py` | Polymorphic `VaultItem` row |
| `backend/app/services/vault_service.py` | `create_vault_item` + queries |
| `backend/app/services/notification_service.py` | Notification fabric + `notify_tenant_admins` |

**Frontend:**

| File | Purpose |
|---|---|
| `frontend/src/pages/vault/VaultHubLayout.tsx` | Hub layout (sidebar + breadcrumbs + outlet) |
| `frontend/src/pages/vault/VaultOverview.tsx` | Overview dashboard with widget grid |
| `frontend/src/services/vault-hub-registry.ts` | Frontend service + widget registry |
| `frontend/src/components/widgets/vault/index.ts` | Widget component barrel |
| `frontend/src/pages/vault/accounting/AccountingAdminLayout.tsx` | Accounting 6-tab layout (V-1e) |

## Services currently registered

Listed in sidebar `sort_order`:

| sort_order | service_key | Display name | Route prefix | Permission |
|---|---|---|---|---|
| 10 | `documents` | Documents | `/vault/documents` | (none, admin per-route) |
| 15 | `crm` | CRM | `/vault/crm` | `customers.view` |
| 20 | `intelligence` | Intelligence | `/vault/intelligence` | (none, admin per-route) |
| 30 | `notifications` | Notifications | `/vault/notifications` | (none) |
| 40 | `accounting` | Accounting | `/vault/accounting` | `admin` |

## Quick links

- **[Full architecture](vault_architecture.md)** — the big picture:
  service model, widget framework, cross-cutting capabilities,
  integration seams, migration history
- **[Pre-V-1 audit](vault_audit.md)** — ground-truth survey of what
  existed before V-1 (useful context for understanding why V-1 is
  shaped the way it is)

**Per-service user guides** (admin-facing, "how do I use this"):

- [Documents](vault/documents.md)
- [Intelligence](vault/intelligence.md)
- [CRM](vault/crm.md)
- [Notifications](vault/notifications.md)
- [Accounting](vault/accounting.md)

**Related arcs** that Vault integrates with:

- [Documents architecture](documents_architecture.md) (D-1 → D-9)
- [Signing architecture](signing_architecture.md) (D-4/D-5)
- [Delivery architecture](delivery_architecture.md) (D-7)
- [Intelligence audit v3](intelligence_audit_v3.md) (managed prompt
  migration)

**Housekeeping:**

- [DEBT.md](DEBT.md) — deferred items including V-2 candidates
  (Calendar, Reminders, CRM true absorption, Vault Sharing
  generalization, notification preferences, etc.)
- [BUGS.md](BUGS.md) — pre-existing bugs discovered during V-1

## Common tasks

| Task | Where to look |
|---|---|
| Adding a new Vault service | [`vault_architecture.md` §6 Integration seams](vault_architecture.md#6-integration-seams--adding-a-new-service) |
| Adding a widget | [`vault_architecture.md` §4 Widget framework](vault_architecture.md#4-widget-framework) |
| Changing a service's permission requirement | `VaultServiceDescriptor.required_permission` in `hub_registry.py` + sync frontend `vault-hub-registry.ts` + update App.tsx `<ProtectedRoute>` gate |
| Migrating an old `/admin/*` path to `/vault/*` | See the V-1a redirect block in `frontend/src/App.tsx` for the `<Navigate>` + `RedirectPreserveParam` pattern |
| Writing a VaultItem from a new service | `vault_service.create_vault_item(...)` wrapped in try/except + logger.exception — see V-1f `quote_service._write_quote_vault_item` for the canonical pattern |
| Fan-out notification to tenant admins | `notification_service.notify_tenant_admins(...)` with a `category` string |
| Add a Vault-aware endpoint | `backend/app/api/routes/vault.py` if it's cross-service; under a service-specific router (`vault_accounting.py`, etc.) if it's service-scoped |
| Deep-link between services | Use `<Link to="/vault/.../...">` — see V-1f Quoting Hub's "Customize quote template" link for the pattern |

## Migration head

`r30_delivery_caller_vault_item` (April 20, 2026). Next-migration
convention: `r31_*` unless the change belongs to an existing arc
(in which case follow that arc's naming).

## Tests

V-1 test suites:

- `backend/tests/test_vault_v1a_hub.py` — hub frame (10 tests)
- `backend/tests/test_vault_v1b_widgets.py` — overview widgets (13)
- `backend/tests/test_vault_v1c_crm.py` — CRM absorption (16)
- `backend/tests/test_vault_v1d_notifications.py` — notifications +
  SafetyAlert merge + 5 sources (21)
- `backend/tests/test_vault_v1e_accounting.py` — accounting admin (33)
- `backend/tests/test_vault_v1fg_vault_item_hygiene.py` — Quote
  dual-write + polymorphic delivery + JE Case A guard (16)

Total: **109 Vault backend tests**. Plus 95+ Documents regression
tests across D-4/D-6/D-7 that the V-1 work keeps green.

Playwright specs live at `frontend/tests/e2e/vault-v1*.spec.ts`.
