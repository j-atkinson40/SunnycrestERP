# Bridgeable Delivery Abstraction — Architecture

Phase D-7. Provides a channel-agnostic send interface so every message
leaving the platform (email today; SMS stubbed; future native email,
push, webhook) flows through one audit-trailed service.

Audience: developers adding a channel, integrating a native provider,
or tracing a delivery problem.

---

## The model

```
caller → DeliveryService.send(SendParams)
            │
            ├─ template_key set? → DocumentRenderer.render_html(...)
            │                      → rendered body + subject
            ├─ document_id set? → legacy_r2_client.download_bytes(...)
            │                     → primary attachment
            ├─ creates DocumentDelivery row (status=pending)
            ├─ get_channel(channel) → EmailChannel / SMSChannel
            ├─ channel.send(ChannelSendRequest) → ChannelSendResult
            ├─ retry inline on retryable errors (bounded by max_retries)
            └─ updates DocumentDelivery row with provider response + status
```

One send = one `document_deliveries` row. The row captures the full
parameter set, provider response JSONB for debugging, error details if
failed, and source-linkage back to the caller (workflow run,
intelligence execution, signature envelope, etc).

---

## The DeliveryChannel protocol

`backend/app/services/delivery/channels/base.py` defines the Protocol
that every channel implements:

```python
class DeliveryChannel(Protocol):
    channel_type: str  # "email" | "sms" | ...
    provider: str      # "resend" | "stub_sms" | "native_email" | ...

    def send(self, request: ChannelSendRequest) -> ChannelSendResult: ...
    def supports_attachments(self) -> bool: ...
    def supports_html_body(self) -> bool: ...
```

Duck-typed. Any class with these attributes and method signatures
qualifies; no inheritance required.

`ChannelSendRequest` is pre-resolved — rendered body, realized
attachments (bytes not references), recipient as a dataclass. No
per-channel-specific content negotiation at the channel layer.

`ChannelSendResult` carries:
- `success` + `provider` + `provider_message_id`
- `provider_response` (JSONB for debugging)
- `error_message` + `error_code` + `retryable` for failed sends

---

## Current implementations

### EmailChannel — Resend

`backend/app/services/delivery/channels/email_channel.py`. The ONLY
module in the codebase allowed to import `resend`. A pytest lint gate
(`tests/test_documents_d7_lint.py`) enforces this.

Test mode (`RESEND_API_KEY` unset or `"test"`) logs + returns
`success=True, provider_message_id="test-mode"`. Production mode calls
`resend.Emails.send(...)` and maps the response into
`ChannelSendResult`.

Error classification: connection / timeout / 502 / 503 errors → retryable;
everything else → non-retryable.

### SMSChannel — stub

`backend/app/services/delivery/channels/sms_channel.py`. Returns
`success=False, error_code="NOT_IMPLEMENTED", retryable=False` on every
send. Callers that invoke SMS get a clean `rejected` status in
`document_deliveries` rather than a crash.

When native SMS ships, the file is replaced with the real
implementation and `_CHANNELS["sms"]` updates — no caller changes.

---

## Adding a new channel

1. Create a class with class attrs `channel_type` + `provider` and a
   `send(ChannelSendRequest) -> ChannelSendResult` method.
2. Register it:
   ```python
   from app.services.delivery import register_channel
   register_channel("webhook", WebhookChannel())
   ```
3. Callers use `delivery_service.send(db, SendParams(channel="webhook", ...))`.

---

## Retry semantics

**D-7: inline retry, synchronous.** If a channel returns
`retryable=True`, DeliveryService re-invokes `channel.send()` in the
same request, bounded by `max_retries` (default 3). The request
blocks until either success or exhaustion.

Pros:
- Simplest possible implementation.
- Call sites don't need queue awareness.
- Good enough for transient provider flakiness.

Cons:
- A request that hits 3 timeouts blocks for tens of seconds.
- No persistent retry across restarts.
- No exponential backoff.

**Future: background retry queue.** When this matters (high-volume
deliveries, longer retry windows), introduce a Redis-backed queue.
Pending deliveries with `status=pending` and `retry_count < max_retries`
get picked up by a worker. DEBT.md tracks this; D-7 ships inline.

---

## Content resolution

Two paths into the send function:

### Template path (preferred)

```python
delivery_service.send(db, SendParams(
    ...,
    template_key="email.statement",
    template_context={"customer_name": "Joe", ...},
))
```

The service calls `document_renderer.render_html()` with the managed
template — tenant overrides, A/B versioning, and audit all come for
free via the Phase D-2 template registry.

### Direct body path

```python
delivery_service.send(db, SendParams(
    ...,
    subject="Urgent: please review",
    body="<p>Custom HTML</p>",
    body_html="<p>Custom HTML</p>",
))
```

For cases where the body content is dynamic enough that a template
doesn't make sense (e.g. invoice emails with inline line-item tables).
Still audited via `document_deliveries.body_preview`.

---

## Attachment handling

If `document_id` is set AND the channel supports attachments, the
service fetches the document bytes from R2 and attaches them as the
primary attachment (e.g. statement.pdf, invoice.pdf). Callers can
supply additional attachments via `SendParams.attachments`.

If the channel doesn't support attachments (SMS), the document is
skipped silently — the body renderer is responsible for including a
link if relevant.

Attachment fetch is best-effort: R2 miss logs a warning and the send
proceeds without that attachment.

---

## Workflow engine integration

`send_document` is a top-level workflow step type (promoted like
`ai_prompt` in Phase 3d). Config shape:

```json
{
  "step_type": "send_document",
  "step_key": "notify_customer",
  "config": {
    "channel": "email",
    "recipient": {
      "type": "email_address",
      "value": "{input.customer_email.value}"
    },
    "template_key": "email.statement",
    "template_context": {
      "customer_name": "{output.extract_customer.name}",
      "tenant_name": "{company.name}",
      "statement_month": "April 2026"
    },
    "document_id": "{output.generate_statement.document_id}"
  }
}
```

Output shape (referenceable by downstream steps):

```
{output.notify_customer.delivery_id}          — UUID of DocumentDelivery
{output.notify_customer.status}               — sent | failed | rejected
{output.notify_customer.provider_message_id}  — provider id if captured
```

Workflow linkage (`caller_workflow_run_id` + `caller_workflow_step_id`)
is auto-populated on every delivery.

---

## Observability

`/admin/documents/deliveries` (DeliveryLog) is the tenant-scoped admin
surface:

- Table view: time, channel, status, recipient, subject / template,
  provider, error.
- Filters: channel, status, recipient search, template key, date range.
- Click a row → DeliveryDetail with full provider response JSONB,
  linkage to document / workflow run / intelligence execution /
  signature envelope, body preview, error details.
- Resend action — creates a new delivery with the preserved inputs.

---

## Intelligence linkage

`intelligence_executions.caller_delivery_id` completes the
symmetric-linkage graph from D-6. An AI call that triggered a send
(e.g. "draft this collections email and send it") links both ways:
execution → delivery (via `caller_delivery_id`), delivery → execution
(via `caller_intelligence_execution_id`).

---

## Migrated callers (D-7 rollout)

All 7 categories flagged in the audit route through DeliveryService:

| Caller | Template | Module |
|---|---|---|
| Signing invite / completed / declined / voided | `email.signing_*` | `signing.notification_service` |
| Monthly statement | `email.statement` | `email_service.send_statement_email` |
| Collections | `email.collections` | `email_service.send_collections_email` |
| User invitation | `email.invitation` | `email_service.send_user_invitation` |
| Accountant invitation | `email.accountant_invitation` | `email_service.send_accountant_invitation` |
| Agent alert digest | `email.alert_digest` | `email_service.send_agent_alert_digest` |
| Invoice email | `email.base_wrapper` (inline body) | `email_service.send_invoice_email` |
| Legacy proof | `email.legacy_proof` | `legacy_email_service.send_email` |

Public surface of `EmailService` unchanged — every `send_*` method
still returns `{"success", "message_id"}`. Internally they build
`SendParams` and call `delivery_service.send(db, params)`.

---

## What's not in D-7

- **Native email / SMS implementations.** Ship as separate channel
  classes registered via `register_channel`.
- **Background retry queue.** Inline retry ships; persistent queue is
  flagged in DEBT.md.
- **Resend webhook handling.** `delivered` status requires webhooks
  from Resend; currently deliveries stop at `sent`. Flagged in DEBT.
- **Bulk send.** Single send at a time. Bulk operations can layer on
  top by calling `send()` in a loop; batch-aware provider APIs would
  go via a new channel method `send_batch` in a future phase.
- **Scheduled send.** `scheduled_for` column exists but no scheduler
  polls it yet. D-7 sends immediate only.
- ~~**SendDocumentConfig frontend** for the workflow designer~~ — ✅
  shipped in D-8. See `frontend/src/components/workflows/SendDocumentConfig.tsx`
  + `WorkflowBuilder.tsx` `step_type === "send_document"` branch.
