# What does "confirmed" set in motion?

Read-only investigation. James's dispatch, 2026-10-16. No writes, no migration.

**Environment naming.** Every number carries its environment. Code citations are
`file:line` against the working tree at the time of writing (HEAD = `fc9e4334`).
Production figures came from four read-only probes run through `railway run`, each query
on `create_engine(url, connect_args={"options": "-c default_transaction_read_only=on"})`;
the target was `shuttle.proxy.rlwy.net:57253/railway`. No query carried a `LIMIT` except
one explicitly marked.

---

## The short answer

Confirming a Sunnycrest order today sets in motion **exactly one thing**: it moves the
order inside the end-of-day batch's net, and the batch then marks it **delivered** and
drafts an invoice.

It does not put the order on a delivery schedule — the hook that would is disabled for
Sunnycrest. It does not start personalization — that already happened at Approve. And it
does not wait for the service to happen; it fires on the first batch run where
`scheduled_date <= today`.

⚠️ **And the batch does not run at 6 PM Eastern.** It runs at **18:00 UTC = 2:00 PM EDT
/ 1:00 PM EST**. Measured on production: see §2a. Every docstring, comment and dispatch
in play says "6 PM"; none of them is right. For a 2 PM service this means the order is
marked delivered and invoiced *during the service*.

---

## 1. Every path that turns a sales order from draft to confirmed

There is **no `confirm_sales_order` function.** Confirming is a field assignment through
the generic update path. That is the first finding, and it shapes the rest.

### 1a. The only path a human uses: `PATCH /api/v1/sales/orders/{id}`

| Layer | Site |
|---|---|
| Button | `frontend/src/pages/sales-order-detail.tsx:193-200` — rendered only when `order.status === "draft"`, calls `handleStatusUpdate("confirmed")` |
| Route | `backend/app/api/routes/sales.py:451` — `require_permission("ar.update_order")` |
| Schema | `backend/app/schemas/sales.py:146-147` — `status: str \| None = None` |
| Service | `backend/app/services/sales_service.py:621` — `update_sales_order` |

**What it writes** (`sales_service.py:637-657`):

- `sales_orders.status = 'confirmed'`
- `sales_orders.modified_by`, `sales_orders.modified_at`
- one `audit_logs` row, action `"updated"`, entity `"sales_order"` (`:649-656`)
- then `db.commit()`

Nothing else. No delivery row, no invoice, no task, no notification, no journal entry.

**What it triggers** (`sales_service.py:660-667`):

```python
if new_status == "confirmed":
    try:
        order_integration_service.on_order_confirmed(db, order)
    except Exception as exc:
        logger.error("Order integration hook failed for %s: %s", order.id, exc)
```

One hook, and every exception inside it is swallowed into a log line. See §1e.

**Three gaps, none of them the dispatch's question but all of them live:**

1. **There is no state machine.** `status` is an unconstrained `str` on the update schema
   and the service assigns whatever arrives (`sales_service.py:640-642`). The only
   refusal is on the *starting* state — `completed` or cancelled orders cannot be
   modified (`:626-630`). A `PATCH {"status": "delivered"}` on a draft is accepted. The
   UI's button sequence (draft → confirmed → processing → delivered → completed,
   `sales-order-detail.tsx:193-236`) is a convention rendered in the frontend, not a rule
   the server enforces.
2. **`status` is free text.** The codebase writes at least eleven values into it across
   services (`draft`, `confirmed`, `processing`, `shipped`, `delivered`, `completed`,
   `pending`, `scheduled`, `in_production`, `spring_burial`, plus two cancel spellings).
   Consumers each carry their own allow-list and the lists disagree — see §1f.
3. **The hook's failure is invisible to the caller.** The PATCH returns 200 with
   `status: confirmed` whether the hook ran, no-opped, or raised.

### 1b. Capture / Opas Approve — does NOT confirm

`backend/app/services/capture/session_service.py:874` `approve()` creates the order with
`status="draft"` at `:941`, and its docstring says why in terms:

> ⚠️ STATUS `draft`, BY JAMES'S DECISION D1 (2026-10-13), AND IT IS A SAFETY MECHANISM
> RATHER THAN A DEFAULT.

**This contradicts item 1 of James's proposed shape** ("Approve on the Review confirms
the order directly"). It deliberately does the opposite. See §6.

What Approve *does* write, in one transaction (`session_service.py:936-1010`):

- the `sales_orders` row — `status='draft'`, `order_type='funeral'`,
  `scheduled_date` = the service date, `burial_date` = the service date, `deceased_name`,
  `cemetery_id`, `service_location`, `service_time`, `eta`, `notes` = the director's own
  typed sentence, `subtotal`/`total`
- one `sales_order_lines` row per priced line
- **one `order_personalization_tasks` row per personalization substrate chosen**
  (`_write_personalization_tasks`, called at `:997`)
- `capture_sessions.status = 'approved'` and `capture_sessions.sales_order_id`
- one `audit_logs` row, action `"created"`

**So personalization work starts at Approve, not at confirm.** That is item 2 of James's
shape — also wrong, but wrong in the direction of already-done rather than missing.

### 1c. Spring burial — two more doors, with different side effects

| Site | Transition |
|---|---|
| `backend/app/services/spring_burial_service.py:173` | `schedule_spring_burial` — `spring_burial` → `confirmed`, also sets `required_date` |
| `backend/app/services/spring_burial_service.py:224` | un-flagging a spring burial — → `confirmed` |

Neither calls `update_sales_order`, so **neither fires the delivery hook** and neither
writes an audit row. Both are direct ORM assignments followed by `db.commit()`.
Sunnycrest has no spring-burial orders on production (§5), so this is latent rather than
active — but it is a second and a third door into `confirmed` whose consequences differ
from the first.

### 1d. Paths reaching `confirmed` on *other* entities (not sales orders)

For completeness, since a grep for `"confirmed"` returns them and they are noise:
`urn_order_service.py:193` (`UrnOrder.status`), `accounting_analysis_service.py:295-371`
(COA mapping rows), `price_list_import.py:500`, `reconciliation.py:992`,
`vault_accounting.py:577`. None touches `sales_orders`.

*Method note: I enumerated the real paths by grepping `(order|so)\.status\s*=` assignments
across `app/`, not by searching the string `"confirmed"` — the latter is dominated by
these.*

### 1e. The confirm hook: `on_order_confirmed`

`backend/app/services/order_integration_service.py:23-82`.

Gated on `delivery_settings.auto_create_delivery_from_order` (`:32-34`). If enabled it
creates one `deliveries` row — `status='pending'`, `priority='normal'`,
`delivery_type='standard'`, `requested_date = order.required_date.date()`, address built
from the order's ship-to fields — and de-duplicates on `deliveries.order_id` (`:38-50`).

**On production, `auto_create_delivery_from_order = False` for Sunnycrest** (probe 1). So
confirming a Sunnycrest order creates no delivery. Sunnycrest's `deliveries` table is
empty (probe 1).

⚠️ Note what the delivery would be dated from if the flag were on: `order.required_date`,
**not** `scheduled_date`. Capture's Approve leaves `required_date` NULL and puts the
service date in `scheduled_date` (`session_service.py:948`), so a captured order
confirmed with the flag on would produce a delivery with `requested_date = NULL`.
Enabling the flag alone would not make §6's "it goes on the schedule" true.

### 1f. Who else reads `status == 'confirmed'`

| Consumer | Allow-list | Effect of confirming |
|---|---|---|
| `draft_invoice_service.py:226-228` (the batch) | `confirmed, processing, shipped, delivered, completed` | **the order enters the batch** — §2 |
| `api/routes/internal.py:138` (`GET /trigger-auto-delivery` preview) | `confirmed, processing, shipped, delivered` | appears in the auto-delivery preview |
| `api/routes/widget_data.py:456,465` | `pending, scheduled, in_production, confirmed, draft` | moves from the dashboard's `unscheduled` count to `scheduled` |
| `data/default_workflows.py:283` | `confirmed, pending` | a workflow filter |
| `operations_board.py:321,402` | *excludes* cancelled/void only | no change — drafts already appear |

**The dashboard counter is the whole of "it goes on the schedule" today.**
`widget_data.py:465` adds `confirmed` into a bucket labelled `scheduled`. There is no
scheduling-board row, no dispatch entry, no driver assignment. The delivery kanban reads
`deliveries`, and nothing created one.

---

## 2. The end-of-day batch, exactly

### 2a. ⚠️ When it actually fires — 18:00 UTC, not 18:00 ET

`backend/app/scheduler.py:709-715`:

```python
scheduler.add_job(
    job_draft_invoice_generator,
    CronTrigger(hour=18, minute=0),
    id="draft_invoice_generator",
    name="draft_invoice_generator",
    replace_existing=True,
    misfire_grace_time=3600,
)
```

`scheduler = BackgroundScheduler(timezone="America/New_York")` (`scheduler.py:19`), and
the comment above the registration reads `# DAILY at 6pm ET`. The service module's own
docstring says `Runs at 6 PM daily` (`draft_invoice_service.py:3`).

**All three are wrong, and the scheduler's timezone argument is dead.** Two independent
instruments agree:

**The mechanism** — APScheduler 3.x, read from the installed library:

- `schedulers/base.py::_create_trigger` opens with
  `if isinstance(trigger, BaseTrigger): return trigger` — a pre-constructed trigger object
  is **returned unchanged**. The line that would apply the scheduler's timezone,
  `trigger_args.setdefault("timezone", self.timezone)` (`base.py:1131`), is only reached
  for *string* triggers (`add_job(func, "cron", hour=18)`).
- `triggers/cron/__init__.py:86-92` — with no `timezone`, no `start_date` and no
  `end_date`, `CronTrigger.__init__` falls through to `self.timezone = get_localzone()`.
  On the Railway container that is UTC.

**The measurement** — production `job_runs`, last 7 days, every scheduled job, no bound:

| job_type | declared in `scheduler.py` | actual UTC firing |
|---|---|---|
| `DRAFT_INVOICE_GENERATOR` | `:710` `hour=18, minute=0` — comment "6pm ET" | **18:00 UTC** |
| `PRICE_VERSION_ACTIVATION` | `:889` `hour=0, minute=1` | 00:01 UTC |
| `AR_BALANCE_RECONCILIATION` | `:743` `hour=2, minute=0` — "2am ET" | 02:00 UTC |
| `PLATFORM_HEALTH_RECALCULATE` | `:863` `hour=2, minute=15` | 02:15 UTC |
| `TAX_ACCUMULATION` | `:753` `hour=2, minute=30` | 02:30 UTC |
| `PROFILE_UPDATE` | `:843` `day_of_week="sun", hour=3, minute=17` | 03:17 UTC (1 run in 7 days ✓) |
| `NETWORK_READINESS` | `:853` `day_of_week="sun", hour=3, minute=30` | 03:30 UTC (1 run ✓) |
| `AUDIT_HEALTH_TASKS` | `:783` `hour=4, minute=40` | 04:40 UTC |
| `FINANCIAL_HEALTH_SCORE` | `:793` `hour=5, minute=3` — "5:03am ET" | 05:03 UTC |
| `CROSS_SYSTEM_SYNTHESIS` | `:803` `hour=6, minute=7` — "6:07am ET" | 06:07 UTC |
| `REORDER_SUGGESTION` | `:813` `hour=7, minute=0` | 07:00 UTC |
| `DISCOUNT_EXPIRY_MONITOR` | `:763` `hour=8, minute=0` | 08:00 UTC |
| `AR_AGING_MONITOR` … `INCOMPLETE_CUSTOMER_PROFILE` | `:733` `hour=23, minute=0/5/…/45` — "11pm ET" | 23:00 / 23:05 / … / 23:45 UTC (all 10) |
| `PAYMENT_PATTERN_ENRICHMENT` | `:773` `day_of_week="sat", hour=2, minute=0` | 02:00 UTC (1 run ✓) |

**23 fixed-hour job types, and every one fires at its declared hour read as UTC.** Not one
is offset by 4 or 5 hours. The run counts corroborate the `day_of_week` declarations too —
the three weekly jobs show exactly 1 run in the 7-day window.

(The remaining 5 job types in the probe — `BRIEFING_SWEEP`, `NOTE_SETTLING_SWEEP`,
`DISPATCH_AUTO_FINALIZE`, `PLATFORM_INCIDENT_DISPATCHER`, `WORKFLOW_TIME_BASED_CHECK` — are
`minute="*/15"` interval sweeps with no declared hour, so they are not evidence either way
and are excluded from the count. One of them is worth a separate look:
`WORKFLOW_TIME_BASED_CHECK` is `CronTrigger(hour="13-23", minute="*/15")` at `:1034`, which
under the same defect means tenant workflows are only checked between 9 AM and 7 PM
Eastern, not 1 PM and 11 PM. Out of scope here.)

**Scope: all of them.** `app/scheduler.py` contains **25** `CronTrigger(...)`
constructions, **0** of which pass `timezone=`, and **0** string-trigger `add_job` calls.
So `BackgroundScheduler(timezone="America/New_York")` has no effect on any cron job in the
file.

**What this means for the batch:** it fires at **2:00 PM Eastern** during EDT and
**1:00 PM Eastern** during EST. On a service day it runs in the early afternoon — before
an afternoon service, not after it. In winter the gap widens by another hour.

*Harmless side-effect, stated so it isn't later mistaken for a bug:* the job computes
`today = date.today()` (`draft_invoice_service.py:199`), container-local, i.e. the UTC
date. At 18:00 UTC the UTC date and the Eastern date are the same, so the date arithmetic
is correct either way. It is only the clock that is wrong.

The job runs per-tenant through `_run_per_tenant` (`scheduler.py:356-358`), which records
a `job_runs` row.

⚠️ **The tenant's own timezone is never consulted.** All four production tenants have
`companies.timezone = 'UTC'` anyway (probe 2), and the batch would ignore it — it is one
global tick for every tenant.

### 2b. Has it actually been running?

Yes. Production `job_runs`, whole history, no bound (probe 3):

| status | runs | first | last | tenant-runs | succeeded | errored |
|---|---|---|---|---|---|---|
| `completed` | 148 | 2026-04-07 21:01 UTC | **2026-10-15 18:00 UTC** | 582 | 582 | 0 |
| `failed` | 173 | 2026-04-07 21:20 UTC | 2026-06-25 18:00 UTC | 540 | 367 | 173 |

The last five runs (2026-10-11 through 10-15) all read
`completed / scheduled / tenant_count 4 / success 4 / error 0`. It fires nightly, covers
all four tenants, and has not errored since 2026-06-25.

### 2c. The tenant gate

`draft_invoice_service.py:181-198`. Two settings decide everything:

| Setting | Model default | Sunnycrest on production |
|---|---|---|
| `invoice_generation_mode` | `"end_of_day"` (`delivery_settings.py:48-50`) | `end_of_day` |
| `require_driver_status_updates` | `False` (`delivery_settings.py:54`) | `False` |

A tenant not in `end_of_day` mode returns `nothing_to_do(skipped="mode_not_end_of_day")`.
Sunnycrest is in it. `require_driver_status_updates=False` selects **auto-confirm mode**.

⚠️ `delivery_settings_service.get_settings` **creates the row if absent**, with the model
defaults — so a tenant that has never configured anything is still in
end_of_day/auto-confirm. All four production tenants are (probe 1). Sunnycrest's row was
created `2026-08-03 18:00:01 UTC` with `modified_at = NULL`: **it has never been edited.**
These are defaults, not choices.

### 2d. The selection query, quoted

`draft_invoice_service.py:217-242`:

```python
base_q = (
    db.query(SalesOrder)
    .filter(
        SalesOrder.company_id == tenant_id,
        SalesOrder.status.in_(
            ["confirmed", "processing", "shipped", "delivered", "completed"]
        ),
        ~SalesOrder.status.in_(SKIP_STATUSES),
    )
    .filter(
        (SalesOrder.scheduled_date <= today)
        | (
            SalesOrder.scheduled_date.is_(None)
            & (func.date(SalesOrder.required_date) <= today)
            & SalesOrder.required_date.isnot(None)
        )
    )
    .filter(
        (SalesOrder.order_type == "funeral") | (SalesOrder.order_type.is_(None))
    )
)
```

with `SKIP_STATUSES = {*CANCEL_SPELLINGS, "postponed"}` (`:157`) and
`today = date.today()` (`:199`).

Then the uninvoiced filter (`:203-212, 245`): any order whose id appears in
`invoices.sales_order_id` for this tenant — **at any invoice status, including void** — is
excluded.

**Four things that selection means:**

1. **`draft` is the only protection.** The `order_type` filter admits `'funeral'` **OR
   NULL** (`:240`), so both are inside the net; setting `order_type='funeral'` protects
   nothing. `session_service.approve`'s docstring says this explicitly, noting that a
   break test caught the author's first, wrong claim that it was a second guard.
2. **The date test is `<= today`, not `== today`.** An order confirmed with a service date
   in the past is picked up on the **next** run, not skipped.
3. **A confirmed order with no date at all is never selected.** Both branches require a
   date; `scheduled_date IS NULL AND required_date IS NULL` matches neither.
4. **Nothing in the query asks whether the service happened.** There is no such column and
   no such check anywhere in the path.

### 2e. What it writes — auto-confirm mode (Sunnycrest's mode)

`draft_invoice_service.py:291-340`. Per selected order:

**On the order** (`:307-311`), when its status is not already in
`DRIVER_CONFIRMED_STATUSES = {"completed","shipped","delivered"}` (`:152`):

- `sales_orders.status = 'delivered'`
- `sales_orders.delivered_at = now()`
- `sales_orders.delivery_auto_confirmed = True`

A `confirmed` order is not in that set, so **a confirmed order is rewritten to
`delivered` by the batch.** That is the mechanism behind "counts as delivered on the
service date" — it is real and automatic. `delivery_auto_confirmed = True` is the system
recording that it assumed.

**Then the invoice** (`:320-330`) via
`sales_service.create_invoice_from_order(db, tenant_id, None, order.id)` — system actor,
nullable attribution — and immediately:

- `invoices.status = 'draft'`
- `invoices.requires_review = True`
- `invoices.review_due_date = tomorrow`
- `invoices.auto_generated = True`
- `invoices.generation_reason = 'end_of_day_batch'`
- a billing-policy note stamped onto `invoices.notes` (`_stamp_billing_policy`)

Plus an `agent_alerts` row and an activity-log entry via `create_alert` / `log_activity`.

### 2f. The guards inside `create_invoice_from_order`

`sales_service.py:724-770`:

- cancelled order → 400
- **`status == 'draft'` → 400**, "confirm it before invoicing" (`:736-740`)
- an existing non-void invoice for the order → 409, naming it (`:744-762`)
- a closed accounting period → `PeriodLockedError`

So the draft refusal is belt-and-braces with the batch's own allow-list.

### 2g. require_driver mode (not Sunnycrest's)

`draft_invoice_service.py:~400-460`. Only orders already in
`{completed, shipped, delivered}` get invoices; everything else is gathered into an
unconfirmed-services alert for dispatch. In this mode a **`confirmed` order drafts
nothing** and raises a warning instead. This is the switch that would make "invoiced only
after a human says it happened" true.

### 2h. What happens to the draft invoice afterwards

| Step | Site |
|---|---|
| Review queue | `GET /api/v1/sales/invoices/review` → `get_review_queue` (`sales.py:869`) |
| Approve one | `POST /api/v1/sales/invoices/{id}/approve` → `draft_invoice_service.py:653` |
| Approve all clean | `approve_all_no_exceptions` (`sales.py:903`) |
| Also surfaced | morning briefing (`briefing_service.py:335` filters `requires_review`) |

`approve_invoice` (`:653-700`) is **the one posting moment**: it clears `requires_review`,
stamps `reviewed_by`/`approved_by`, calls `sales_service.post_invoice_to_ar` (which moves
`customers.current_balance` and writes the AR journal entry), then sets the invoice to
`sent` if the customer's `invoice_delivery_preference` is `invoice_immediately`/`both`,
else to `open`.

**Hopkins Funeral Home is `statement_only`** (probe 1) — so an approved Sunnycrest invoice
goes to `open` and **no email is sent**. It waits for the statement.

### 2i. Statements

`statement_generation_service.py:24`:
`EXCLUDED_INVOICE_STATUSES = ("draft", "void", "write_off")`, applied at `:76, :91, :155`.

**A batch-drafted invoice does not appear on a statement until someone approves it.**
Sunnycrest has three statement runs on production, created 2026-08-31, 2026-09-30 and
2026-10-01 at ~06:07–06:13 UTC (probe 1), with statuses `in_review`, `draft`, `draft`.

---

## 3. The hypothetical, walked

**Order for Hopkins, service next Tuesday, confirmed today at 11:00.** Sunnycrest's
production settings as measured. Assume the order came from Opas, so
`scheduled_date = 2026-10-20` and `required_date = NULL`.

### Today, 11:00 — the confirm

- `sales_orders.status` → `'confirmed'`; `modified_by`/`modified_at` set
  (`sales_service.py:640-645`)
- one audit row (`:649-656`)
- `on_order_confirmed` runs and returns `None` at `order_integration_service.py:32-34` —
  `auto_create_delivery_from_order` is False. **No delivery row.**
- the dashboard's `scheduled` count goes up by one (`widget_data.py:465`)
- nothing is scheduled, nobody is notified, no driver sees anything

### Tonight — Friday 2026-10-16, 18:00 UTC (2:00 PM ET)

`generate_draft_invoices` runs for Sunnycrest. The order is in the status allow-list, but
the date test is `scheduled_date <= today` and `2026-10-20 > 2026-10-16`.
**Not selected.** *Deciding lines: `draft_invoice_service.py:233-239`.*

### Monday — 2026-10-19, 18:00 UTC

Same test: `2026-10-20 > 2026-10-19`. **Not selected.** Nothing happens.

### Tuesday — 2026-10-20, 18:00 UTC = **2:00 PM Eastern**, the service date

1. Selected: status `confirmed` ∈ allow-list (`:226-228`); `scheduled_date` 2026-10-20
   `<= today` (`:234`); `order_type='funeral'` (`:240`); no invoice exists (`:245`).
2. Status is not in `DRIVER_CONFIRMED_STATUSES`, so the batch rewrites the order
   (`:307-311`): **status → `delivered`**, `delivered_at = 2026-10-20 18:00 UTC`,
   `delivery_auto_confirmed = True`.
3. `create_invoice_from_order` runs with a `None` actor (`:320-324`). An `invoices` row is
   created from the order's lines.
4. The invoice is stamped draft/review (`:326-330`): `status='draft'`,
   `requires_review=True`, `review_due_date=2026-10-21`, `auto_generated=True`,
   `generation_reason='end_of_day_batch'`, billing-policy note appended.
5. An `agent_alerts` row and an activity-log entry are written.

⚠️ **2:00 PM Eastern is the finding here.** A 2 PM service is being marked delivered and
invoiced while it is happening; a 3 PM service, before it starts. The dispatch's phrase
"the night of the service date" describes behaviour the system does not have.

### Wednesday morning

The draft appears in the review queue and in the morning briefing. Until someone approves
it:

- `customers.current_balance` unchanged — no AR movement
- no journal entry
- it will not appear on October's statement

On approval, AR moves, the invoice goes to **`open`** (Hopkins is `statement_only`, so no
email), and it becomes eligible for the month's statement.

**One thing in this walk is luck, not design.** The three-day gap comes from the dates, not
from any rule. Had the service date been *today*, the 11:00 confirm would have produced a
delivered order and a drafted invoice **three hours later**, at 2 PM — see §5, where that
is not hypothetical.

---

## 4. Sunnycrest's real practice vs. the current model

### What the repo records

Searched `STATE.md`, `DECISIONS.md`, `CLAUDE.md` and the memory directory.

| Claim from the dispatch | What the repo records |
|---|---|
| Monthly statement billing is the model | **Yes, repeatedly.** `CLAUDE.md §12`: "Monthly Statement Billing — funeral homes get consolidated statements, not individual invoices." `STATE.md:2523` treats it as a vertical-level mechanism, not a tenant quirk. |
| One invoice per order | **Yes, as an enforced invariant.** `sales_service.py:744-762` refuses a second non-void invoice per order with a 409 naming the existing one, described in its own comment as "one order, one invoice (audit #2 D-5)". |
| Drivers do NOT mark stops delivered | **Not recorded anywhere as a Sunnycrest fact.** The *capability* is modelled (`require_driver_status_updates`, the driver portal, `show_delivered_button`) and the setting sits at its default `False`, which is consistent — but nothing states it as Sunnycrest's practice. **Unrecorded premise.** |
| Delivered on the service date | **Implemented, not decided — and not at night.** It is what auto-confirm mode does, at 2 PM Eastern (§2a). No DECISIONS entry chooses it for Sunnycrest; it is the shipped default on a row that has never been edited. |
| Invoiced then | **Half-implemented.** The batch drafts an invoice then; it does not become real until a human approves it. |

### The gaps, listed only

1. ⚠️ **The clock is wrong by 4–5 hours and every comment says otherwise.** The batch
   fires at 2 PM Eastern (1 PM in winter). The behaviour everyone has been reasoning about
   — "end of day", "the night of the service date" — does not exist. This affects all 25
   cron jobs in `scheduler.py`, not just this one (§2a).
2. **"Delivered on the service date" is a default, not a decision.** Sunnycrest's
   `delivery_settings` row has `modified_at = NULL`. Nobody configured it.
3. **The confirm step does no scheduling.** `auto_create_delivery_from_order = False`, so
   a confirmed order produces no `deliveries` row and appears on no dispatch surface. The
   only thing that moves is a dashboard counter. Enabling the flag is not sufficient — the
   hook dates the delivery from `required_date`, which Opas never sets (§1e).
4. **Confirming early is unsafe for a today-or-past service date.** The test is
   `<= today`, so there is no "wait until the service has happened" anywhere.
5. **Nothing distinguishes "the service happened" from "the date arrived."** The order
   carries `delivery_auto_confirmed = True` to mark the assumption, but no surface asks
   anyone to confirm or correct it and no report lists auto-confirmed deliveries. The
   draft-invoice review queue is the closest thing, and it reviews the *invoice*, not the
   *delivery*.
6. **Invoice emailing is suppressed by customer preference, not by policy.** Hopkins is
   `statement_only`. A new funeral home added with a different preference would start
   receiving per-invoice emails, contradicting the statement-only model with nobody having
   changed a setting.
7. **Three doors into `confirmed`, three different sets of side effects.** The PATCH path
   fires the hook and writes audit; the two spring-burial paths do neither (§1c).
8. **No state machine.** `draft → delivered` via PATCH is accepted, skipping confirm
   entirely and landing the order in the batch's net with `delivered_at` still NULL.
9. **The statement run is not gated on the review queue.** A month can close with drafts
   still sitting unreviewed, silently absent from the statement. The two schedules
   (daily 18:00 UTC, monthly ~06:07 UTC) have no relationship.

---

## 5. SO-2026-0001 as each path would see it, if confirmed right now

Production, read-only, probe 1. **Today is 2026-10-16.**

```
number                   SO-2026-0001
status                   draft
order_type               funeral
scheduled_date           2026-10-16        <-- TODAY
required_date            NULL
order_date               2026-10-14 14:35:10 UTC
delivered_at             NULL
delivery_auto_confirmed  False
deceased_name            smith
total                    1550.00
customer                 Hopkins Funeral Home  (invoice_delivery_preference=statement_only,
                                                current_balance 0.00)
lines                    Monticello Burial Vault  1 x 1250.0000 = 1250.00
                         Full Equipment           1 x  300.0000 =  300.00
invoices linked          none
```

It is the only sales order Sunnycrest has on production — the status census returns one
row, `draft / funeral / 1`.

⚠️ **Its service date is today.**

| Path | as a draft | if confirmed right now |
|---|---|---|
| `on_order_confirmed` (`order_integration_service.py:23`) | — | **no-ops** at `:32-34`; `auto_create_delivery_from_order=False`. No delivery. |
| **The batch, 18:00 UTC today** (`draft_invoice_service.py:217`) | excluded — `draft` ∉ allow-list | **SELECTED.** → status rewritten to `delivered`, `delivered_at` set, `delivery_auto_confirmed=True`, and a draft invoice for **$1,550.00** created with `review_due_date = 2026-10-17`. |
| `create_invoice_from_order` (`sales_service.py:724`) | **refuses** — 400, "still a draft" (`:736-740`) | permitted; one invoice, then the 409 guard blocks a second |
| `GET /trigger-auto-delivery` preview (`internal.py:138`) | absent | appears |
| Dashboard counts (`widget_data.py:456-465`) | counted in `unscheduled` | moves to `scheduled` |
| Statement generation (`statement_generation_service.py:24`) | nothing | still nothing today — the invoice is `draft`, which is excluded. It reaches October's statement only if someone approves it before the run. |
| Operations board (`operations_board.py:321`) | already visible | unchanged |

**So confirming SO-2026-0001 today is the live version of the risk in the dispatch**, and
sharper than the dispatch assumes. The service is today; the batch fires at
**18:00 UTC = 2:00 PM Eastern**. Confirmed now, the order would be marked delivered and a
$1,550 invoice drafted this afternoon — not tonight — with nobody having said the vault
was placed.

### Has the batch ever acted on Sunnycrest?

**No.** Production, probe 2, unbounded across all tenants:

| Measure | sunnycrest | testco |
|---|---|---|
| invoices with `generation_reason='end_of_day_batch'` | **0** | **12 draft, $30,612.00** |
| orders with `delivery_auto_confirmed = True` | **0** | **5, all `delivered`** |
| `deliveries` rows | **0** | not probed |
| `order_personalization_tasks` rows | **0** | not probed |

⚠️ **Correction to a claim in our own code.** `session_service.approve`'s docstring says
"12 invoices and 5 rewritten orders on production prove it is live." Those figures are
right and they are **testco's**, not Sunnycrest's. The batch is live and proven on
production — on the development tenant. Sunnycrest has never had a non-draft order due, so
it has never been in the net. The docstring reads as though Sunnycrest had been through
this and should name the tenant.

Sunnycrest's 8 existing invoices (5 paid $10,075.00, 2 partial $7,096.43, 1 sent
$3,750.00) are all `auto_generated = False` with `generation_reason = NULL` — they predate
and bypass this machinery entirely.

Sunnycrest capture sessions on production: 6 abandoned, 1 approved, 1 capturing.

---

## 6. Corrections to the proposed shape of the confirm step

| James's line | Verdict |
|---|---|
| "Approve on the Review confirms the order directly." | **Wrong as a description of today, and the opposite is deliberate.** Approve creates a `draft` by James's own decision D1 of 2026-10-13, documented at `session_service.py:878-900` as a safety mechanism against exactly this batch. Making Approve confirm directly would put every captured order into the net on its service date — which may be right, but it reverses a three-day-old ruling and removes the only guard. |
| "Confirming puts the order on the schedule for the service date." | **Not true today.** The hook is disabled for Sunnycrest, so no `deliveries` row is created and no dispatch surface changes. The only movement is a dashboard counter (`widget_data.py:465`). Enabling the hook is one setting, but it dates the delivery from `required_date`, which Opas leaves NULL — the date source needs fixing too. |
| "If there's personalization, it also starts that work." | **Already happens — one step earlier.** `order_personalization_tasks` rows are written at **Approve** (`session_service.py:997`), not at confirm. |
| "The invoice comes after the service, never at confirmation." | **True of confirmation; not reliably true of the service.** Nothing checks whether the service happened — the batch checks `scheduled_date <= today` and fires at 2 PM Eastern. For an afternoon service the invoice drafts *before* it. |
| "One invoice per order, lands on that month's statement." | **Correct and enforced.** `sales_service.py:744-762`; statements aggregate invoices excluding drafts (`statement_generation_service.py:24`). |
| "Drivers don't mark stops delivered, so the order counts as delivered on the night of the service date." | **The mechanism is real; "the night" is not.** `require_driver_status_updates=False` on an unedited settings row; the rewrite is `draft_invoice_service.py:307-311`; the clock is 2 PM Eastern (§2a). |

### The question I cannot answer from the repo

James asked: *is "delivered on the night of the service date, invoiced then" right for
Sunnycrest, or do you invoice at a different point — like when the office reviews the
day's runs?*

**That is a business-practice question and the repo does not record the answer.** Two
things from this investigation bear on it.

**First, the system already implements a two-stage version**, and James may be describing
stage one while meaning stage two:

- **On the service date (2 PM Eastern):** the order is marked delivered and an invoice is
  **drafted**. No AR movement, no email, no statement eligibility.
- **When the office next reviews:** approval is the posting moment (`approve_invoice` →
  `post_invoice_to_ar`). AR moves, the invoice becomes real, the statement can see it.

So "invoiced when the office reviews the day's runs" is **closer to what already happens**
than "invoiced on the night of the service date". If that is the intent, the current shape
is mostly right, and the gap is that the review queue reviews the *invoice* rather than the
*delivery* — nobody is asked "did these stops actually happen?", only "is this invoice
correct?"

**Second, the 2 PM clock changes the question.** "The night of the service date" is a
defensible policy; "two hours before a 4 PM service" is not, and that is what is running.
Whatever James decides about invoicing timing, the timezone defect wants fixing on its own
merits — and it is not Sunnycrest-specific or batch-specific (all 25 cron jobs, §2a).

Three shapes follow; the choice is James's.

1. **Fix the clock, keep auto-confirm, rename the gate.** Pass the timezone to the
   triggers so 18:00 means 6 PM Eastern. The batch continues to assume delivery and draft;
   the morning queue becomes an explicit "yesterday's deliveries — confirm or correct"
   surface, with invoice approval as its consequence. Smallest change; the assumption
   stays but becomes visible and correctable.
2. **Flip `require_driver_status_updates` to True.** Nothing is invoiced until a human
   marks the order delivered/shipped/completed; unconfirmed services raise a dispatch
   alert. Honest, but somebody has to do the marking daily, and the dispatch says the
   drivers don't.
3. **Gate the batch on the service having passed, not the date having arrived.** Change
   `scheduled_date <= today` to something that accounts for `service_time` — e.g. select
   only orders whose service time is already past at run time. Keeps the automation,
   removes the before-the-service case, and does not need anyone to mark anything.

None is in scope for a read-only investigation.

---

## Appendix: method, and what bounds these findings

- **Code claims:** working tree at `fc9e4334`. The draft→confirmed paths were enumerated
  by grepping `(order|so)\.status\s*=` assignments across `app/`, not by searching the
  string `"confirmed"` — the latter is dominated by non-sales-order consumers (§1d).
- **Production figures:** four scripts via
  `railway run --project ad95792e-… --environment production --service SunnycrestERP`,
  each query on a read-only connection. Credentials were never read; the probes print
  `host/port/db` only. Output was redirected to files and read whole, not piped.
- **Bounds:** no query carried a `LIMIT` except `probe3`'s "5 most recent runs", which is
  marked as such; the aggregate above it is over the whole table. Status censuses, invoice
  censuses, the `job_runs` history and the firing-time table are unbounded.
- **The timezone finding has two independent instruments** — the installed APScheduler
  source (the mechanism) and 23 fixed-hour job types' actual UTC firing times (the
  measurement). They agree, and neither was inferred from the other. All 25 `CronTrigger(`
  constructions in `app/scheduler.py` were enumerated and checked for a `timezone=`
  argument; none has one.
- ⚠️ **A claim in an earlier draft of this document was wrong and is recorded here rather
  than quietly removed.** §2a originally asserted the batch fires at 18:00 Eastern,
  reasoning from `BackgroundScheduler(timezone="America/New_York")` on `scheduler.py:19`.
  That line is real and has no effect. The error was caught by probing `job_runs` to answer
  a different question (had the job ever run?) and noticing the timestamps disagreed.
  Reading the scheduler was not sufficient; only the measurement settled it.
- **Unrecorded premise flagged, not resolved:** "drivers do not mark stops delivered" is
  not written down anywhere in the repo as a Sunnycrest fact. It is consistent with the
  settings, and it is James's to confirm.
- **Not probed:** testco's `deliveries` and `order_personalization_tasks` counts; whether
  any of the 173 historical batch failures (all before 2026-06-25) touched Sunnycrest —
  `job_runs` has no tenant column, only `tenant_count`/`success_count`/`error_count` per
  sweep, so per-tenant failure history is not available from that table.
