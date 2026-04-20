# Documents — User Guide

_Admin-facing guide for the Documents service in the Vault hub. For
internal architecture, see
[`../documents_architecture.md`](../documents_architecture.md)._

## What this service does

Documents is the canonical layer for every template-rendered and
AI-generated artifact the platform produces — PDFs (invoices,
statements, quotes, certificates, engraving forms), HTML emails,
signed contracts. Every document is a row in the `documents` table
with a versioned R2-backed storage key, linked back to the source
entity (sales order, invoice, case, etc.) and the caller that
generated it (a workflow run, an Intelligence execution, a migrated
email template).

The admin surfaces under `/vault/documents` let you inspect what the
platform produced, customize how it looks, share artifacts
cross-tenant, send them via any channel with full audit, and manage
signature envelopes end-to-end.

## Where it lives in the nav

**Vault hub sidebar → Documents** (`/vault/documents`).

Admin-only: non-admin users don't see the sidebar entry and hit 403
on direct URLs. Each sub-tab is also individually admin-gated
server-side.

## Key admin surfaces

| Surface | Path | Purpose |
|---|---|---|
| **Document Log** | `/vault/documents` | Every document rendered in the last 7 days (filterable) |
| **Document Detail** | `/vault/documents/:id` | Metadata, linkage rows, version history, regenerate action |
| **Template Library** | `/vault/documents/templates` | Managed template catalog — filter by type / scope / format / status |
| **Template Detail** | `/vault/documents/templates/:id` | Template view + draft editor + version history + activation audit |
| **Inbox** | `/vault/documents/inbox` | Documents shared TO this tenant (per-user read state) |
| **Delivery Log** | `/vault/documents/deliveries` | Every outbound message routed through DeliveryService |
| **Delivery Detail** | `/vault/documents/deliveries/:id` | Provider response, linkage, resend button |
| **Signing Library** | `/vault/documents/signing` | Signature envelope queue |
| **Create Envelope** | `/vault/documents/signing/new` | 4-step wizard to send a doc for signature |
| **Envelope Detail** | `/vault/documents/signing/:envelopeId` | Parties, fields, events, resend/void |

## Common workflows

### Inspect what the platform produced

1. Navigate to `/vault/documents`.
2. Use the filters to narrow by document type (invoice, statement,
   quote, certificate, etc.), status, template key, or date range.
3. Click a row to see the Document Detail page.
4. The detail page shows:
   - The source entity (e.g. "Invoice INV-2026-042" with a click-through)
   - The caller (e.g. "workflow run abc123" or "intelligence execution xyz")
   - The current version + full version history
   - Regenerate button if the source data has changed

### Customize a template

See the dedicated guide:
[`../how_to_customize_a_template.md`](../how_to_customize_a_template.md).

Quick summary:

1. `/vault/documents/templates` — find the template (use `search`
   filter if the library is large).
2. Open the template detail page.
3. If it's a platform template and you're a tenant admin, click
   **"Fork to tenant"** to create a tenant-scoped copy.
4. Click **"Create draft"** on the active version. This is your
   working copy.
5. Edit the body + subject (for email templates) + variable schema +
   CSS variables + changelog.
6. Use **"Preview"** for client-side Jinja substitution, or
   **"Test render"** for a backend-backed render producing a
   flagged test document.
7. When ready, click **"Activate"**. The activation dialog shows a
   side-by-side diff against the currently-active version + requires
   a changelog. For **platform-global templates**, activation
   requires typing the `template_key` as confirmation.
8. The new version becomes active; the prior version is retired (not
   deleted — visible in version history).

**Rollback.** From the version history you can roll back to any
retired version. Rollback creates a *new* active version cloning the
retired content — no row is ever reactivated (keeps the audit trail
linear).

### Send a document for signing

See the dedicated guide:
[`../how_to_send_a_document_for_signing.md`](../how_to_send_a_document_for_signing.md).

Quick summary:

1. `/vault/documents/signing/new` opens the 4-step wizard:
   - **Step 1 — Select document.** Pick the Document to send.
   - **Step 2 — Add signers.** Name + email + role for each party.
     Sequential routing orders them by `signing_order`.
   - **Step 3 — Add signature fields.** Place fields by page + x/y
     coordinates OR by anchor text (e.g. `<<fh_signature>>`) that
     PyMuPDF finds in the source PDF.
   - **Step 4 — Review & create.** Confirm and send.
2. Signers receive email invites. Signer portal is at public route
   `/sign/{token}` (no auth — the token IS the auth).
3. Monitor the envelope at `/vault/documents/signing/:id`:
   - Party status for each signer (pending / sent / viewed / signed
     / declined)
   - Full event timeline (every state transition writes a
     `SignatureEvent` with a sequence number)
   - Resend invite (individual party) / Void envelope (with reason)
4. On completion:
   - The signed PDF is added as a new `DocumentVersion`.
   - A Certificate of Completion is rendered as a platform template
     and stored as another Document.
   - Any disinterment case linked to the envelope has its status
     synced (pre-V-1d migrated from DocuSign — see
     `../signing_architecture.md`).

### Share a document cross-tenant

1. Document Detail → **"Shares"** panel.
2. Click **"Grant share"**.
3. Enter the target company UUID + optional reason.
4. Grant requires an active `PlatformTenantRelationship` between
   owner and target (either direction). If none exists, the UI shows
   "Request relationship" instead.
5. The target tenant sees the document in their Inbox
   (`/vault/documents/inbox`).
6. Revoke from the same panel. Revocation is future-access-only —
   already-downloaded copies are outside the platform's control.
   Explicit UI copy calls this out.

### Investigate a failed delivery

1. `/vault/documents/deliveries` — filter by `status=failed`.
2. Click a row.
3. The detail page shows:
   - Provider response JSONB (e.g. Resend's bounce reason)
   - Error message + error code
   - Retry count and attempts
   - Linkage rows (Document / Workflow Run / Intelligence Execution
     / Signature Envelope / VaultItem) — click any to jump back to
     the source
4. **Resend button** re-queues the delivery using the preserved
   input params. Templates re-render at resend time — edits to the
   template since the original send are picked up.
5. Correlated notification: V-1d wired `delivery_failed` to fire a
   tenant-admin fan-out notification on terminal failure (severity
   "high"). Check the admin's Notifications page for a parallel
   entry that links back to this delivery.

### Read the Inbox

1. `/vault/documents/inbox` lists documents *shared to* this tenant
   by other tenants (statements received from vault manufacturers,
   delivery confirmations from FH customers, etc.).
2. Per-user read state (D-8) — each admin sees unread-vs-read counts
   independently.
3. Filters: document_type, include_revoked.
4. Click a row to open the Document Detail (read-only for target
   tenants).

## Permission model

- **Sidebar entry visible to admins only.** Non-admin users don't
  see "Documents" in the Vault hub sidebar.
- **All sub-routes admin-gated.** Even if a non-admin user
  constructs a direct URL, the `<ProtectedRoute adminOnly>` gate in
  `App.tsx` blocks them.
- **Cross-tenant sharing requires a `PlatformTenantRelationship`.**
  No ad-hoc granting.
- **Signing public routes (`/sign/{token}`) are intentionally unauth.**
  Rate-limited to 10 req/min per token. The token IS the auth.

## Related services

- **Intelligence.** Every AI-generated artifact (Call Intelligence
  extraction, Scribe output, agent reports) produces a Document via
  `document_renderer.render(...)`. The Document Log shows these
  with `intelligence_execution_id` linkage — click through to see
  the prompt, context, and token spend.
- **Notifications.** Failed deliveries fire `delivery_failed`
  notifications. Shared documents fire `share_granted` notifications
  to the target tenant's admins. Signature-requested (internal
  signer) fires an in-app notification separately from the email.
- **CRM.** Activities (calls, emails, notes) write to the
  `activity_log` which the CRM Recent Activity widget surfaces;
  some activity types attach a Document via `source_document_id`.
- **Accounting.** Statement runs produce statement Documents via
  the Document template registry. Invoice PDFs go through the same
  pipeline. COGS + revenue reporting relies on the Document Log as
  the source-of-truth audit trail.

## Known limitations

- **Resend webhook for `delivered` status not wired.** Providers
  confirm acceptance; full delivery confirmation via webhook is
  future work. Tracked in DEBT.md.
- **Bulk send + scheduled send have no UI.** The `DocumentDelivery`
  schema supports `scheduled_for`; no admin action exposes it yet.
- **Tenant-user-facing inbox isn't built.** D-6 shipped admin-only;
  non-admin users don't have a way to see documents shared to the
  tenant.
- **Document Log pagination is hard-coded to `limit=200`.** Fine for
  current scale. Will need proper pagination when tenant document
  volumes grow.
- **Pre-D-6 cross-tenant shares not backfilled.** The admin Inbox
  only shows shares created via the D-6 flow. If a tenant has
  pre-D-6 statement emails that got attached to sales via the old
  ad-hoc mechanism, they don't appear. Tracked in DEBT.md as a
  one-off backfill script opportunity.

See [`../DEBT.md`](../DEBT.md) for the full list of deferred items.
