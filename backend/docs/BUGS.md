# Pre-existing Bugs Discovered During Intelligence Migration

These bugs predate the Intelligence migration work (Phase 1 through 2c-5) and
were discovered incidentally while writing integration tests for migrated
callers. They were NOT caused by the migration.

Each bug is tracked here for a dedicated cleanup pass. Intelligence migration
tests work around them by avoiding the broken code paths — but the bugs
affect production behavior whenever users exercise the relevant feature.

Items are deleted from this doc when they are fixed AND have regression
coverage. Fixed items get moved to the **Resolved** section at the bottom.

---

## Open Bugs

### 1. `OnboardingChecklist.tenant_id` AttributeError (cluster — 7 sites, one file)

**Impact:** Any caller that filters the onboarding checklist by tenant will
raise `AttributeError: type object 'OnboardingChecklist' has no attribute
'tenant_id'`. The model's FK column is `company_id`.

**Affected files:**

| File | Line | Discovered |
|---|---|---|
| `app/services/onboarding_service.py` | 1278, 1396, 1463, 1554, 1832 | BUGS-1 sweep |
| + two more sites flagged by introspection | | |

**Cleanup approach:** Mass replace within `onboarding_service.py`:
`OnboardingChecklist.tenant_id` → `OnboardingChecklist.company_id`. The
whole file is tenant-scoped so there are no semantic ambiguities. Add a
regression test that exercises one of the previously-broken paths end-to-end.

**Status:** Open — out of scope for BUGS-1 (too large a single-class sweep
with no integration test harness in place for onboarding).

---

### 2. `VendorBill.tenant_id` AttributeError

**Impact:** Financial health scoring and the `tax_filing_prep` proactive
agent will raise AttributeError whenever the vendor-bill query branch is
reached. Column is `company_id`.

**Affected files:**

| File | Function | Line | Discovered |
|---|---|---|---|
| `app/services/financial_health_service.py` | (query) | 79 | BUGS-1 sweep |
| `app/services/proactive_agents.py` | tax_filing_prep | 201 | BUGS-1 sweep |

**Cleanup approach:** Change `VendorBill.tenant_id` → `VendorBill.company_id`
at both sites. Separately audit `proactive_agents.py:203` — `VendorBill.total_amount`
does not exist (column is `total`). Both should be fixed together with
one regression test invoking each function.

**Status:** Open — flagged for cleanup; low-risk but requires real data
to regression-test.

---

### 3. `SalesOrder.is_active` AttributeError (widget_data)

**Impact:** Widget endpoints `/widget-data/orders/today` and
`/widget-data/orders/pending-summary` raise AttributeError on first call.
SalesOrder has no `is_active` column — soft-delete on sales orders is
represented via `status` (e.g. `canceled`, `void`).

**Affected files:**

| File | Function | Line | Discovered |
|---|---|---|---|
| `app/api/routes/widget_data.py` | `orders_today` | 33 | BUGS-1 sweep |
| `app/api/routes/widget_data.py` | `orders_pending_summary` | 69 | BUGS-1 sweep |

**Cleanup approach:** Remove the `SalesOrder.is_active == True` predicate
and replace with a status exclusion like
`SalesOrder.status.notin_(["canceled", "void"])` — matches the idiom in
`operations_board.py:402`.

**Status:** Open — widget endpoints are not heavily exercised pre-launch;
fix alongside the next widget pass.

---

### 4. `SalesOrder.order_number` AttributeError (command bar)

**Impact:** Command bar entity pre-resolution for sales orders references
`order_number`, but the column is `number`. Any NLP command that resolves
a sales order will fail at query time.

**Affected files:**

| File | Function | Line | Discovered |
|---|---|---|---|
| `app/services/core_command_service.py` | (resolve entities) | 81 | BUGS-1 sweep |
| `app/services/core_command_service.py` | (resolve entities) | 231 | BUGS-1 sweep |

**Cleanup approach:** `SalesOrder.order_number` → `SalesOrder.number` at both
sites. Regression test: exercise command bar entity lookup with a SO number.

**Status:** Open — command bar ships in beta; fix before the Wilbert demo.

---

### 5. `Customer` tax / exemption / finance-charge attributes (cluster)

**Impact:** Financial reporting, tax routes, and finance-charge service
reference columns that don't exist on Customer. Dormant until the relevant
report is generated.

**Affected files / attributes:**

| Attribute | File | Line |
|---|---|---|
| `Customer.exemption_certificate` | `app/services/financial_report_service.py` | 254 |
| `Customer.exemption_expiry` | `app/services/financial_report_service.py` | 267 |
| `Customer.finance_charge_eligible` | `app/services/finance_charge_service.py` | 214 |
| `Customer.tax_status` | `app/services/financial_report_service.py` | 253, 266 |
| `Customer.tax_status` | `app/api/routes/tax.py` | 328 |

**Cleanup approach:** Audit `Customer` model — the tax fields likely moved
to a related `CustomerTaxProfile` or similar. Confirm intended columns
(`tax_exempt` is the only tax-related column visible). May require adding
new columns (feature work) rather than a rename.

**Status:** Open — needs design clarification. Do not rename blindly.

---

### 6. Other dormant `tenant_id` and attribute typos

| Class.Attr | File | Line | Note |
|---|---|---|---|
| `ActivityLog.company_id` | `app/api/routes/widget_data.py` | 339 | Needs `tenant_id`? Audit model. |
| `Company.preset` | `app/services/network_intelligence_service.py` | 48, 49 | Column is `preset_key`? |
| `Driver.is_active` | `app/api/routes/widget_data.py` | 97 | Column is `active`. |
| `EmployeeProfile.company_id` | `app/services/onboarding_summary_service.py` | 90 | Audit model for correct FK. |
| `FHCase.contacts / invoice / obituary / vault_order` | `app/services/case_service.py` | 238–241 | Relationships missing from model. |
| `HistoricalOrderImport.created_at` | `app/api/routes/unified_import.py` | 483 | Audit model. |
| `Invoice.pdf` | `app/api/routes/sales.py` | 794 | Column/relationship missing. |
| `InvoiceLine.amount / discountable` | `app/services/early_payment_discount_service.py` | 112, 117 | Audit model. |
| `LegacyProof.is_active` | `app/api/routes/widget_data.py` | 205 | Audit model. |
| `NetworkRelationship.requester_id / responder_id` | `app/services/delivery_notification_service.py` | 259, 260 | Columns are `requesting_company_id` / similar. |
| `OnboardingChecklist.check_in_call_offered_at / check_in_call_scheduled / must_complete_percent` | `app/services/onboarding_service.py` | 1939, 2049, 2056, 2057 | Columns missing — likely new feature work stubbed. |
| `OnboardingChecklistItem.company_id` | `app/services/network_intelligence_service.py` | 175 | Audit model. |
| `OrderPersonalizationPhoto.created_at` | `app/services/legacy_service.py` | 164 | Audit model. |
| `ProductionLogEntry.company_id` | `app/api/routes/widget_data.py`:130, `operations_board.py`:420 | | Audit model. |
| `ProductionLogEntry.logged_at` | `app/api/routes/operations_board.py` | 421 | Audit model. |
| `PurchaseOrderLine.purchase_order_id` | `app/services/vault_inventory_service.py` | 96 | Relationship vs FK confusion. |
| `SafetyIncident.tenant_id` | `app/services/toolbox_suggestion_service.py` | 127 | Should be `company_id`. |
| `SyncLog.tenant_id` | `app/api/routes/urn_sales.py` | 910 | Should be `company_id`. |
| `User.last_login_at` | `app/services/admin/tenant_kanban_service.py` | 54 | Column is `last_console_login_at`? |
| `User.role` | `app/services/extension_service.py` | 717 | Column is `role_id` (FK). |

**Cleanup approach:** Triage each. Most are single-site renames. A few
(`FHCase` relationships, `Customer` tax fields) may be real missing
features rather than typos. Write one regression test per fixed site
to pin the behavior.

**Status:** Open — catalogued from BUGS-1 sweep. Not fixed in BUGS-1
because each one is a one-off with distinct context.

---

## Resolved

### ✅ `audit_service.log()` does not exist — three sites in `quote_service.py`

**Fixed in:** audit_service typo fix build (2026-04-20)
**Regression test:** `backend/tests/test_vault_v1fg_vault_item_hygiene.py::TestQuoteAuditLogging` (3 tests — one per call site: create/convert/status-change; each asserts the correct action string + changes payload).

**What was wrong:** `quote_service.create_quote`,
`convert_quote_to_order`, and `update_quote_status` called
`audit_service.log(...)`, which doesn't exist — the real function is
`log_action(...)`. Every Quote write has crashed with
`AttributeError: module 'app.services.audit_service' has no attribute
'log'` at the audit-log line (post-commit, so DB state persisted but
the API response raised) since the code was added on 2026-03-19.
Surfaced during V-1f+g pre-build while adding Quote → VaultItem
dual-write tests.

**Sites fixed (1 file, 3 sites):**

| File | Function | Line (original) | Fix |
|---|---|---|---|
| `app/services/quote_service.py` | `create_quote` | 343 | `log_action(..., "created", "quote", ...)` |
| `app/services/quote_service.py` | `convert_quote_to_order` | 422 | `log_action(..., "converted", "quote", ...)` |
| `app/services/quote_service.py` | `update_quote_status` | 499 | `log_action(..., "status_changed", "quote", ...)` |

Action strings + call shape aligned with the platform-wide convention
used by `sales_service.py` (past-participle verbs + short
entity_type + positional args + `changes=` kwarg, not `details=`).
The V-1f+g test monkeypatch that stubbed `audit_service.log` to a
no-op was removed in the same build — all 16 tests in
`test_vault_v1fg_vault_item_hygiene.py` pass against the real
function.

---

### ✅ `CompanyEntity.tenant_id` AttributeError (cluster)

**Fixed in:** BUGS-1 build (2026-04-18)
**Regression test:** `backend/tests/test_bugs_regression.py::test_company_entity_has_company_id_not_tenant_id` plus behavioral tests for each affected caller.

**What was wrong:** Any caller that fuzzy-matched a funeral home or cemetery
by name raised `AttributeError: type object 'CompanyEntity' has no attribute
'tenant_id'`. The model's actual column is `company_id`.

**Sites fixed (4 files, 6 sites, + 1 extension to Contact):**

| File | Function | Line(s) |
|---|---|---|
| `app/api/routes/widget_data.py` | `at_risk_summary` | 374 |
| `app/services/call_extraction_service.py` | `_fuzzy_match_company` | 115, 128 |
| `app/services/urn_intake_agent.py` | `_match_funeral_home` | 172, 187 |
| `app/services/phone_lookup_service.py` | `find_by_phone` | 59 |
| `app/services/phone_lookup_service.py` | `find_by_phone` (Contact) | 86 — extension fix |

---

### ✅ `SalesOrder.delivery_date` / `service_date` AttributeError (cluster)

**Fixed in:** BUGS-1 build (2026-04-18)
**Regression test:** `backend/tests/test_bugs_regression.py::test_sales_order_has_scheduled_date_and_delivered_at_not_delivery_date` plus source-level guards.

**What was wrong:** The BUGS.md v1 cleanup note suggested renaming
`delivery_date` → `delivered_at`, but that was semantically wrong.
`delivered_at` is a completion timestamp (DateTime). The queries were
actually asking for the planned service date (Date), which is
`scheduled_date`. Verified by cross-checking production queries
(`briefing_service.py:1533`, `vault_inventory_service.py:78`,
`personalization.py:49`) — all use `scheduled_date` for the
"what's scheduled for today?" pattern.

**Sites fixed (3 files, 5 sites):**

| File | Function | Line(s) | Before → After |
|---|---|---|---|
| `app/api/routes/operations_board.py` | `get_daily_context` | 401 | `delivery_date` → `scheduled_date` |
| `app/api/routes/widget_data.py` | `orders_today` | 34, 36, 49 | `service_date` → `scheduled_date` (filter + order_by + `o.service_date.isoformat()`) |
| `app/api/routes/company_entities.py` | cemeteries-by-customer | 1936 | `func.max(service_date)` → `func.max(scheduled_date)` |

---

## Out-of-scope for cleanup

### AICommandBar frontend refactor

The `AICommandBar` React component (`frontend/src/components/ai-command-bar.tsx`)
accepts a `systemPrompt` prop that it sends to the deprecated `/ai/prompt`
endpoint. This defeats the Intelligence layer's prompt management: admins
can't version the prompt, A/B test it, or override per tenant.

Consumer: `pages/products.tsx` for AI product search.

**Cleanup approach:** Create a dedicated managed prompt (e.g.
`catalog.product_search`), add a backend endpoint `/products/ai-search` that
invokes `intelligence_service.execute(prompt_key="catalog.product_search")`,
and delete the `systemPrompt` prop from AICommandBar.

**Status:** Tracked via
`backend/tests/test_intelligence_phase2c0a_frontend_lint.py:FRONTEND_ALLOWLIST`.
Sunset planned 2027-04-18 alongside the `/ai/prompt` endpoint.

---

## How to add to this doc

When an incidental bug is discovered during future migration work, add a
section above following the same template:
- Clear impact statement
- Table of affected file / function / line / when-discovered
- Reproduction steps
- Cleanup approach
- Status

When you fix a bug:
1. Add a regression test that exercises the previously-broken path.
2. Move the entry from **Open Bugs** to **Resolved** with a date and a
   link to the regression test.
3. Do not delete the entry — the Resolved section is the audit trail.
