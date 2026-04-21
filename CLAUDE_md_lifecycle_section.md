# Vault Order Lifecycle — CLAUDE.md Reference Section

## Overview

The vault order lifecycle is the end-to-end flow of a funeral vault order through
Bridgeable, from initial order entry to closed account. Every stage is fully built
and wired as of April 2026. The only intentional gap is Stripe payment links
(planned, not yet built).

All lifecycle stages are audited and verified functional in production for the
Sunnycrest tenant. This section is the authoritative reference for how the system
works — use it when writing prompts, debugging issues, or extending any stage.

---

## Stage 1 — Sales Order Entry

### Entry paths

Three paths all produce a `SalesOrder` (via `Quote`) record:

| Path | Mechanism | Key file |
|------|-----------|----------|
| Phone / email / text | Order station UI | `order-station.tsx` |
| Cross-tenant (FH portal) | Auto-creation on FH order submit | `vault_order_service.py:154–290` |
| Voice shorthand | AI command bar → `POST /order-station/parse-order` | Claude parses vault, cemetery, date |

### Key behaviors at order entry

- **FuneralHomePicker** — debounced search with inline create via `POST /customers/quick-create`. Inline-created customers have `setup_complete = false`.
- **CemeteryPicker** — shows history shortlist (≥3 orders) or geographic shortlist (cold start). Inline create supported. Equipment prefills on selection via `GET /cemeteries/:id/equipment-prefill`.
- **Conditional pricing** — "with our product" price applies to graveside service when any burial vault or urn vault is on the order. Calculated server-side in `quote_service.py`.
- **Vault placer** — auto-added as `$0.00` line item (`is_auto_added = true`) when funeral home has `prefers_placer = true` and a lowering device is on the order. Wired in both `create_quote()` and `create_sales_order()`.
- **Deceased name** — field on order form (`order-station.tsx:547`). Stored on `SalesOrder.deceased_name`, copied to `Invoice.deceased_name` at invoice creation.
- **Credit hold check** — `check_credit_limit()` called during `create_sales_order()`. Non-blocking — creates `agent_alert` of type `order_credit_hold` if customer is on hold. Banner shown in order station UI.
- **Soft inventory check** — `create_sales_order()` checks `quantity_on_hand` vs `reorder_point`. Creates `agent_alert` and sets `order.has_inventory_warning = true` if low. Non-blocking.
- **Cemetery history** — `POST /order-station/record-cemetery-history` → `cemetery_service.record_funeral_home_cemetery_usage()` called on order save. Feeds the cemetery shortlist.

### Data model

```
Quote → QuoteLines (created first)
SalesOrder → SalesOrderLines (created from quote)
SalesOrder.cemetery_id FK → cemeteries.id
SalesOrder.deceased_name VARCHAR(200)
SalesOrder.has_inventory_warning BOOLEAN
SalesOrder.driver_confirmed BOOLEAN
SalesOrder.delivered_at TIMESTAMPTZ
SalesOrder.completed_at TIMESTAMPTZ
```

---

## Stage 2 — Inventory Check

### Current implementation

Soft check only — no hard reservation system exists. This is intentional for the
base preset.

- `create_sales_order()` checks `InventoryItem.quantity_on_hand` vs `reorder_point`
- If stock at or below reorder point after the order: `agent_alert` created, `order.has_inventory_warning = true`
- Toast shown in order station UI on save
- For **purchase mode** tenants: low stock triggers the `REORDER_SUGGESTION_JOB` context — the daily-context endpoint includes `vault_urgency` which surfaces in the Operations Board and morning briefing

### Not built (intentional)

Hard inventory reservation (blocking orders when out of stock) is not built. This
was a deliberate decision — vault operations rarely have zero stock and a blocking
check would create operational friction.

---

## Stage 3 — Scheduling

### Scheduling board

- Route: `/scheduling` → `scheduling-board.tsx`
- `GET /schedule?date=` returns unscheduled funeral vault deliveries
- `POST /assign` in `funeral_kanban.py:262–396` assigns order to driver with service time
- Uses `@hello-pangea/dnd` for drag-and-drop

### Driver portal

- Routes: `/driver` → `DriverHomePage`, `/driver/route` → `DriverRoutePage`, `/driver/stops/:id` → `StopDetailPage`
- `GET /route/today` in `driver_mobile.py:38–55` returns stops for the day
- Driver marks stop delivered: `PATCH /stops/:stopId/status` → `delivery_service.update_stop_status()`

### SalesOrder sync on delivery

When a stop is marked delivered, `delivery_service.py` now updates:
```
sales_order.status = 'delivered'
sales_order.delivered_at = now()
sales_order.driver_confirmed = true
```
This is real-time — order shows 'delivered' immediately, not waiting for 6pm batch.

---

## Stage 4 — Delivery and Exception Reporting

### Driver exception API

```
POST /api/v1/driver/stops/:stopId/exception
Auth: driver role
Body: {
  exceptions: [{
    item_description: string,
    reason: 'weather' | 'access_issue' | 'family_request' | 'equipment_failure' | 'other',
    notes: string | null
  }]
}
```

Sets on SalesOrder:
- `driver_exceptions` JSONB — array of exception objects
- `has_driver_exception = true`

Creates `agent_alert` type `driver_exception`, severity `warning`, action URL
`/ar/invoices/review`.

### Auto-confirm mode

For tenants with `require_driver_status_updates = false` (Sunnycrest default):

At 6pm, `draft_invoice_service._generate_auto_confirm_mode()` auto-sets:
```
sales_order.status = 'delivered'
sales_order.delivery_auto_confirmed = True
```

Driver exception reporting is only available when `require_driver_status_updates = true`.

---

## Stage 5 — Invoicing (Draft Creation)

### Batch job

- Job key: `DRAFT_INVOICE_GENERATOR`
- Schedule: Daily at 18:00 ET (`scheduler.py:232–239`)
- Registered in `JOB_REGISTRY`

### What it does

For each active manufacturing tenant:
1. Queries funeral orders with `scheduled_date = today`, not yet invoiced
2. Creates `Invoice` with `status = 'draft'`, `requires_review = True`, `auto_generated = True`
3. Copies `deceased_name`, `cemetery_id`, line items from the `SalesOrder`
4. If `has_driver_exception = true`: sets `invoice.has_exceptions = true`, copies exception notes to `invoice.review_notes`
5. Creates `agent_alert` type `draft_invoices_ready`

### Invoice fields set at creation

```
Invoice.deceased_name — from SalesOrder
Invoice.requires_review = True
Invoice.auto_generated = True
Invoice.has_exceptions — from order.has_driver_exception
Invoice.review_notes — from driver_exceptions
Invoice.discount_deadline — invoice_date + 15 days (if invoice_immediately customer)
Invoice.discounted_total — total * 0.95 (if invoice_immediately customer)
```

### Morning review queue

- Route: `/ar/invoices/review` → `invoice-review-queue.tsx`
- Shows draft invoices grouped by: exceptions first (amber), then auto-confirmed
- `[Approve & Post]` — posts invoice, triggers billing routing (Stage 6)
- `[Approve All]` — bulk approves invoices with `has_exceptions = false`
- Morning briefing includes draft invoice count, total, exception count via `briefing_service.py:206–247`

---

## Stage 6 — Billing Routing

### Routing logic

After `[Approve & Post]`, `draft_invoice_service.py:537–543` checks
`customer.invoice_delivery_preference`:

| Preference | Behavior |
|-----------|----------|
| `invoice_immediately` | PDF generated, emailed via Resend, `invoice.status = 'sent'` |
| `statement_only` | `invoice.status = 'open'`, no email, accumulates for month-end statement |
| `both` | PDF emailed AND stored for statement |

### PDF invoice generation

- `pdf_generation_service.py:394` `generate_invoice_pdf()`
- Template selected from `invoice_settings.template_key` (professional / clean_minimal / modern / custom)
- Template path: `backend/app/templates/invoices/{template_key}.html`
- Rendered via Jinja2, converted to PDF via WeasyPrint
- Template context includes: `deceased_name`, `cemetery_name`, `service_date`, `discount_deadline`, `discounted_total`, all line items

### Email delivery

- `email_service.py:314` `send_invoice_email()`
- Sent via Resend
- Subject includes deceased name if present: `"Invoice {number} — RE: {deceased_name} — {company_name}"`
- PDF attached as `Invoice-{number}.pdf`

### Statement generation

- `statement_generation_service.py` — `get_eligible_customers()`, `calculate_statement_data()`
- PDF via same WeasyPrint pipeline using matching statement template
- `email_service.py:252` `send_statement_email()` with PDF attachment
- Runs at month end (scheduled job)

### Early payment discount

- `Invoice.discount_deadline = invoice_date + 15 days`
- `Invoice.discounted_total = total * 0.95`
- Both set at invoice creation for `invoice_immediately` / `both` customers
- Shown on PDF template as two-payment option
- Applied at payment time by `early_payment_discount_service.py`

---

## Stage 7 — Collections

### Overdue detection

- `agent_service.py:174` `run_collections_sequence()`
- Scheduled daily at 23:05 ET
- Flags invoices and statements past `due_date`

### Collection sequence

- AI-drafts collection emails via Claude API — staff review before sending
- `email_service.py:233` `send_collections_email()`
- Escalation automatic based on days past due (tone/urgency increases)
- Credit hold applied when balance exceeds `customer.credit_limit` threshold

### Credit hold

- `customer_service.py:241–265` `check_credit_limit()`
- Called during `create_sales_order()` — non-blocking, creates `agent_alert`
- Banner shown in order station when customer is on hold
- Hold removed automatically when balance clears to zero (Stage 9)

### Collections auto-pause

When payment fully clears a customer's balance:
- Active collections sequences paused
- Credit hold removed if applied
- Logged to `agent_activity_log` as `collections_paused_on_payment`

---

## Stage 8 — Payment Application

### Payment models

```
CustomerPayment
  id, company_id, customer_id, payment_date
  total_amount, payment_method, reference_number
  payment_method: 'check' | 'ach' | 'credit_card' | 'cash' | 'wire'

CustomerPaymentApplication
  payment_id FK, invoice_id FK, amount_applied
```

### Payment endpoints

```
GET  /api/v1/sales/payments          — list payments
POST /api/v1/sales/payments          — create with applications
POST /api/v1/sales/payments/import   — batch CSV import from Sage
```

Validation: sum of applications must equal total_amount. Each invoice must
exist, belong to customer, not be void/draft, have sufficient balance.

### Check scanning

- `sales_service.py:1820` `scan_check_image()`
- Claude Vision (claude-sonnet-4-20250514) extracts: payer_name, amount, check_number, check_date, memo
- Fuzzy matches payer_name to customers table (threshold 0.75)
- Returns suggested applications (FIFO)
- Frontend: check-scanner component in payment processing queue

### Smart matching scenarios

`POST /api/v1/payments/suggest-application` detects:
- `exact_match` — amount equals total open balance
- `overpayment` — amount exceeds open balance → `customer.credit_balance` increased
- `early_pay_discount` — amount matches discounted_total of specific invoice
- `invoice_subset` — amount matches sum of specific invoice combination
- `fifo_partial` — default FIFO distribution

### Early payment discount application

`early_payment_discount_service.py:142–186` `apply_discounted_payment()`:
- If `payment_date <= invoice.discount_deadline` AND `amount == discounted_total`:
  - `invoice.discount_amount = total - discounted_total`
  - `invoice.amount_paid = invoice.total` (marked fully paid)
  - `invoice.status = 'paid'`
- If `payment_date > discount_deadline` AND `amount == discounted_total`:
  - Short pay alert created
  - `POST /invoices/:id/honor-discount` endpoint for retroactive application

### Payment processing queue

Route: `/ar/payments` → `CustomerPaymentsPage`
- [Scan Check] — check scanner flow
- [Enter Manually] — record-payment-dialog.tsx
- [Import CSV] — batch import

### Not yet built

- Stripe payment links (planned)
- Stripe webhook auto-application (planned)

---

## Stage 9 — Order Completion

### Auto-completion trigger

When `invoice.amount_paid >= invoice.total` in `sales_service.py`:
```python
invoice.status = 'paid'
invoice.paid_at = now()

if invoice.sales_order_id:
    sales_order.status = 'completed'
    sales_order.completed_at = now()
```

### Post-completion actions

1. **Collections pause** — if customer total balance = 0, collections sequences paused, credit hold removed
2. **Behavioral profile enrichment** — `behavioral_analytics_service.py` `enrich_behavioral_profile()` called with trigger `'order_completed'`
3. **Cemetery shortlist update** — already maintained in real time via `record_funeral_home_cemetery_usage()` on order save. Completion reinforces the data.

### Intelligence enrichment

`entity_behavioral_profiles` JSONB updated with:
- `most_common_vault` — from order history
- `most_common_equipment` — from order history
- `avg_days_to_pay` — from payment timing
- `early_pay_rate` — % of invoices paid with early discount
- `top_cemeteries` — from cemetery usage history

Used by: morning briefing context, order station suggestions, quick order template
recommendations, collections escalation timing.

---

## Key Agent Jobs in the Lifecycle

| Job key | Schedule | What it does |
|---------|----------|-------------|
| `DRAFT_INVOICE_GENERATOR` | 6pm daily | Creates draft invoices for all completed funeral orders |
| `AR_AGING_MONITOR` | Daily | Flags overdue invoices, updates aging buckets |
| `COLLECTIONS_SEQUENCE` | 23:05 daily | Runs collections escalation for overdue accounts |
| `FINANCIAL_HEALTH_SCORE_JOB` | Weekly | Updates customer health scores from payment history |
| `REORDER_SUGGESTION_JOB` | 7am daily | Checks vault inventory levels, creates PO suggestions |
| `AR_BALANCE_RECONCILIATION` | 2am daily | Detects and corrects drift in `customer.current_balance` |
| `DISCOUNT_EXPIRY_MONITOR` | 8am daily | Alerts when early payment discount windows expire today |

---

## Key Settings That Affect the Lifecycle

| Setting | Location | Effect |
|---------|----------|--------|
| `invoice_generation_mode` | `DeliverySettings` | `'end_of_day'` (default) / `'manual'` / `'immediate'` |
| `require_driver_status_updates` | `DeliverySettings` | Controls whether 6pm batch auto-confirms deliveries |
| `invoice_delivery_preference` | `Customer` | `'invoice_immediately'` / `'statement_only'` / `'both'` |
| `prefers_placer` | `Customer` | Auto-adds vault placer line item on lowering device orders |
| `preferred_confirmation_method` | `Customer` | Shown in order station as reminder to CSR |
| `invoice_settings` | `Company.settings_json` | Template key, content options, discount settings |
| `vault_fulfillment_mode` | `Company` | `'produce'` / `'purchase'` / `'hybrid'` |
| `credit_limit` | `Customer` | Triggers non-blocking warning at order entry |

---

## Common Debugging Reference

| Symptom | Where to look |
|---------|---------------|
| Draft invoices not created | `scheduler.py` DRAFT_INVOICE_GENERATOR registration; check 6pm cron; check `delivery_settings.invoice_generation_mode` |
| Invoice not emailed after approval | `customer.invoice_delivery_preference` — must be `invoice_immediately` or `both`; check `company.logo_url` and `invoice_settings.template_key` exist |
| Placer not auto-added | `customer.prefers_placer = true`; `product.is_placer = true` on Vault Placer product; `product.is_lowering_device = true` on equipment products |
| Cemetery equipment not prefilling | `cemetery.cemetery_provides_*` flags; `CemeteryPicker.onEquipmentPrefill` handler in order-station.tsx |
| Order not auto-completing on payment | `invoice.sales_order_id` must be set; check `sales_service.py` payment application logic |
| Customer balance drifting | `AR_BALANCE_RECONCILIATION` job runs at 2am and auto-corrects; check `agent_alerts` for correction history |
| Collections not pausing after payment | `collections_paused_on_payment` logic in payment application; check customer total balance calculation |
| Cross-tenant order not auto-creating | `vault_order_service.py:154`; check `PlatformTenantRelationship` exists between tenants |

---

## File Map — Lifecycle Critical Paths

```
Order entry
  frontend/src/pages/orders/order-station.tsx
  frontend/src/components/funeral-home-picker.tsx
  frontend/src/components/cemetery-picker.tsx
  backend/app/services/quote_service.py
  backend/app/services/sales_service.py
  backend/app/services/order_pricing_service.py

Scheduling + delivery
  frontend/src/pages/scheduling/scheduling-board.tsx
  frontend/src/pages/driver/stop-detail.tsx
  backend/app/api/routes/driver_mobile.py
  backend/app/services/delivery_service.py
  backend/app/api/routes/funeral_kanban.py

Invoicing
  backend/app/services/draft_invoice_service.py
  frontend/src/pages/ar/invoice-review-queue.tsx
  backend/app/scheduler.py (DRAFT_INVOICE_GENERATOR)

Billing + PDF
  backend/app/services/pdf_generation_service.py
  backend/app/services/email_service.py
  backend/app/templates/invoices/ (professional.html, clean_minimal.html, modern.html)
  backend/app/services/statement_generation_service.py

Collections
  backend/app/services/agent_service.py (run_collections_sequence)

Payment
  backend/app/services/sales_service.py (create_customer_payment, scan_check_image)
  backend/app/services/early_payment_discount_service.py
  frontend/src/components/record-payment-dialog.tsx
  frontend/src/components/check-scanner.tsx
  frontend/src/pages/ar/customer-payments.tsx

Order completion + intelligence
  backend/app/services/behavioral_analytics_service.py
  backend/app/services/cemetery_service.py (record_funeral_home_cemetery_usage)
  backend/app/services/proactive_agents.py (AR_BALANCE_RECONCILIATION)
```
