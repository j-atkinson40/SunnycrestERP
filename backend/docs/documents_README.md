# Bridgeable Documents — README

This is the entry point for the Documents system. Architecture lives
in the files this README links to; start here to understand the
surface area before diving into any single phase doc.

## What the Documents system is

One canonical model (`Document` + `DocumentVersion`) for every
template-rendered or AI-generated artifact the platform produces —
PDFs, HTML emails, signed forms, certificates. One rendering pipeline
(`document_renderer`) so every artifact gets the same treatment:
Jinja render → WeasyPrint (for PDFs) → R2 upload → DB row → audit
linkage. One audit surface (`/admin/documents/documents`) to inspect
what was produced, when, from what inputs, and for what entity.

On top of that foundation sit four feature layers:

| Layer | What it does | Arch doc |
|---|---|---|
| **Template registry** | Managed Jinja templates with versioning, tenant overrides, drafts, and activation audit | [documents_architecture.md](./documents_architecture.md) |
| **Native signing** | Anchor-based PDF field overlay + completion certificate + SignatureEnvelope state machine | [signing_architecture.md](./signing_architecture.md) |
| **Cross-tenant sharing** | `DocumentShare` fabric unifying statements, delivery confirmations, legacy vault prints, training certs, etc. with a D-6 admin inbox and per-user read tracking (D-8) | [documents_architecture.md](./documents_architecture.md) |
| **Delivery abstraction** | Channel-agnostic `DeliveryService` — every outbound message goes through one audit trail, with pluggable channels (Resend email + SMS stub today) | [delivery_architecture.md](./delivery_architecture.md) |

## Phase map — D-1 through D-8

| Phase | What shipped | Migration | Tests |
|---|---|---|---|
| **D-1 — Backbone** | Canonical `Document` + `DocumentVersion`, renderer, 4 generators migrated, workflow `generate_document` action wired | `r20_documents_backbone` | `test_documents_d1.py` (18) |
| **D-2 — Template registry** | `document_templates` + versioning, Platform/tenant scope, `DocumentLog` + `DocumentDetail` admin pages | `r21_document_template_registry` | `test_documents_d2.py` + `_lint` |
| **D-3 — Template editing** | Draft → activate → audit, test-render, fork-to-tenant, rollback, super-admin gate on platform templates | `r22_document_template_editing` | `test_documents_d3.py` |
| **D-4 — Native signing** | PyMuPDF anchor overlay, `SignatureEnvelope` state machine, signer portal, completion certificate | `r23_signing` (+ `r24` disinterment integration) | `test_documents_d4_signing.py` |
| **D-5 — Signing polish** | Envelope library + detail, webhook hooks, resend, void/decline | (schema stable) | `test_documents_d5_signing.py` |
| **D-6 — Cross-tenant sharing** | `document_shares` + events, admin inbox, `visible_to()` API, PlatformTenantRelationship enforcement, Intelligence reverse-linkage | `r25_document_sharing` | `test_documents_d6_sharing.py` (33) + `_lint` |
| **D-7 — Delivery abstraction** | `DeliveryChannel` Protocol + registry, `DeliveryService`, `document_deliveries` table, Resend email channel, SMS stub, DeliveryLog + Resend action, `send_document` workflow step | `r26_delivery_abstraction` | `test_documents_d7_delivery.py` + `_lint` |
| **D-8 — September demo polish** | 7 templates redesigned, DocumentPicker, SendDocumentConfig, per-user inbox read tracking, visual QA pass, 10 Playwright tests, this README | `r27_inbox_read_tracking` | `test_documents_d6_sharing.py` (+ 4 new) |

## The 11 admin surfaces

All live under `/admin/documents/*`:

| Path | Purpose |
|---|---|
| `/admin/documents/templates` | Managed template library — filter by type/scope/format |
| `/admin/documents/templates/:id` | Template detail + version history + draft editor |
| `/admin/documents/documents` | Document log — every rendered artifact in the last 7 days |
| `/admin/documents/documents/:id` | Document detail — linkage, versions, regenerate |
| `/admin/documents/inbox` | Admin inbox — documents shared TO this tenant (D-6), with per-user read state (D-8) |
| `/admin/documents/deliveries` | DeliveryLog — every outbound message routed through DeliveryService |
| `/admin/documents/deliveries/:id` | DeliveryDetail — provider response, linkage, resend action |
| `/admin/documents/signing/envelopes` | Signing envelope library |
| `/admin/documents/signing/envelopes/new` | Create envelope wizard (4 steps) |
| `/admin/documents/signing/envelopes/:id` | Envelope detail — parties, fields, timeline, resend/void |
| Workflow builder | `generate_document` + `send_document` step types with dedicated config UIs |

## API surface

Admin API at `/api/v1/documents-v2/*` — all tenant-scoped, admin-gated.

Key endpoints:

- `GET /documents-v2/log` — document log with filters
- `GET /documents-v2/:id` — detail + versions
- `GET /documents-v2/:id/download` — 307 → presigned R2 URL
- `POST /documents-v2/:id/regenerate` — re-render, flips `is_current`
- `GET /documents-v2/admin/templates` + CRUD per D-3 editing
- `POST /documents-v2/:id/shares` + revoke
- `GET /documents-v2/inbox` — per-user read state overlay
- `POST /documents-v2/inbox/mark-all-read`
- `POST /documents-v2/shares/:id/mark-read`
- `GET /documents-v2/deliveries` + detail + resend

Signing at `/api/v1/signing/*` (separate router, see
[signing_architecture.md](./signing_architecture.md)).

## Guardrails

- **Only `email_channel.py` may import `resend`.** Enforced by
  `test_documents_d7_lint.py`. New channels implement the
  `DeliveryChannel` Protocol and register via `register_channel`.
- **No direct `anthropic` SDK use.** All AI calls route through the
  Intelligence service; a ruff + pytest lint gate enforces this.
- **Canonical `Document` is referenced directly,** not by string
  `relationship("Document", ...)` — both legacy and canonical models
  share the class name in the registry.
- **Sharing enforces `PlatformTenantRelationship`** before grant (D-6),
  unless `ensure_share()` is called from an auto-share generator path.
- **Audit events (`document_share_events`) are append-only** by service
  contract — `test_documents_d6_sharing.py::TestAuditAppendOnly` lint.

## User guides

- [How to customize a template](./how_to_customize_a_template.md)
- [How to send a document for signing](./how_to_send_a_document_for_signing.md)

## What's not in D-8 (carried forward)

- Resend webhook handling for `delivered` status (DEBT.md)
- Persistent retry queue (DEBT.md)
- Bulk send + scheduled send (architecture exists, no UI)
- Tenant-user-facing inbox (D-6/D-8 shipped admin-only)
- Batch-aware provider APIs → `send_batch` method on `DeliveryChannel`
- Document Log pagination (hard-coded limit=200, fine for demo scale)
