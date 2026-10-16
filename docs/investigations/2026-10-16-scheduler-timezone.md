# Scheduled jobs run on UTC, not Eastern

James's dispatch, 2026-10-16. Step 1 of three; steps 2 (batch follows the service date) and
3 (the confirm step) are separate.

**Environment naming.** Code citations are `file:line`. "Actual now" figures are from
production `job_runs`, read-only, via `railway run` with
`default_transaction_read_only=on`; target `shuttle.proxy.rlwy.net:57253/railway`. DST
figures are computed locally against the installed `apscheduler 3.11.3` and stdlib
`zoneinfo` — they are predictions about future transitions, not observations, and are
labelled as such.

---

## The defect, in one paragraph

`app/scheduler.py:19` constructs `BackgroundScheduler(timezone="America/New_York")`. That
argument **has no effect on any job in the file.** APScheduler's
`schedulers/base.py::_create_trigger` opens with
`if isinstance(trigger, BaseTrigger): return trigger` — a pre-constructed trigger object is
returned unchanged, so it never reaches
`trigger_args.setdefault("timezone", self.timezone)` (`base.py:1131`), which only runs for
*string* triggers (`add_job(func, "cron", hour=18)`). `CronTrigger.__init__` then falls
through to `self.timezone = get_localzone()` (`triggers/cron/__init__.py:92`), which on the
Railway container is UTC. All **25** `CronTrigger(...)` constructions in the file pass no
`timezone=`, and there are **no** string-trigger `add_job` calls. So every cron job fires on
UTC while its comment claims Eastern — four hours early in EDT, five in EST.

`app/services/workflow_scheduler.py:229` is **not** affected: it already passes
`timezone=tenant_tz` explicitly. The defect is confined to `app/scheduler.py`.

---

## 1. The table

**25 `CronTrigger` constructions → 34 cron registrations** (the nightly block is one
construction registering ten jobs) **+ 3 `"interval"` registrations = 37 scheduled
registrations**, which matches the figure in `CLAUDE.md §10`.

**26 registrations carry an `hour=`** and are therefore wrong by 4–5 hours today. **8 are
minute-only** (`*/15`, `*/5`, `:07`, `:11`, `:23`, `:27`) and fire identically in any
whole-hour-offset zone — measured, see §3.

Of the 37, **30 record a `job_runs` row**; the 7 that do not are the five email/calendar
minute-only sweeps and the two MoC `"interval"` sweeps. None of those 7 is changing.

### Hour-bearing jobs — wrong today, fixed by this change

"actual now" is `distinct_hhmm = 1` in every row below: each has fired at exactly one UTC
time for its whole recorded history.

| registration id | declared | intent per comment | **actual now (UTC)** | after fix (UTC, EDT) | what it does |
|---|---|---|---|---|---|
| `price_version_activation` | `hour=0, minute=1` | midnight ET | **00:01** | 04:01 | activates scheduled price versions whose `effective_date <= today` |
| `ar_balance_reconciliation` | `hour=2, minute=0` | 2am ET | **02:00** | 06:00 | reconciles stored customer AR balances against invoice totals |
| `platform_health_recalculate` | `hour=2, minute=15` | 2:15am ET | **02:15** | 06:15 | recalculates tenant health scores from open incidents |
| `network_snapshot` | `day=1, hour=2, minute=17` | monthly 1st 2am | **02:17** | 06:17 | monthly cross-tenant network snapshot |
| `tax_accumulation` | `hour=2, minute=30` | 2:30am ET, "(idempotent)" | **02:30** | 06:30 | rebuilds the current sales-tax period's accumulator rows |
| `payment_pattern_enrichment` | `day_of_week=sat, hour=2, minute=0` | Sat 2am ET | **02:00** | 06:00 | enriches customer profiles with payment patterns |
| `profile_update` | `day_of_week=sun, hour=3, minute=17` | Sun 3am | **03:17** | 07:17 | funeral-home behavioural profile enrichment |
| `network_readiness` | `day_of_week=sun, hour=3, minute=30` | Sun 3:30am | **03:30** | 07:30 | finds new cemetery tenants, creates connection suggestions |
| `onboarding_pattern` | `day=1, hour=4, minute=13` | monthly 1st 4am | **04:13** | 08:13 | monthly onboarding-pattern analysis |
| `audit_health_tasks` | `hour=4, minute=40` | 4:40am | **04:40** | 08:40 | turns audit health findings into tasks |
| `financial_health_score` | `hour=5, minute=3` | 5am | **05:03** | 09:03 | per-tenant financial health score |
| `cross_system_synthesis` | `hour=6, minute=7` | 6am | **06:07** | 10:07 | cross-system insight synthesis |
| `reorder_suggestion` | `hour=7, minute=0` | 7am | **07:00** | 11:00 | delivery-aware vault reorder suggestions |
| `discount_expiry_monitor` | `hour=8, minute=0` | 8am ET | **08:00** | 12:00 | alerts on early-payment discounts expiring within 3 days |
| **`draft_invoice_generator`** | `hour=18, minute=0` | **6pm ET** | **18:00** = **2 PM EDT** | 22:00 | the end-of-day batch — marks orders delivered, drafts invoices |
| `ar_aging_monitor` | `hour=23, minute=0` | 11pm ET | **23:00** | 03:00 (+1d) | AR aging alerts |
| `collections_sequence` | `hour=23, minute=5` | 11pm ET | **23:05** | 03:05 (+1d) | advances dunning sequences, drafts collection emails |
| `ap_upcoming_payments` | `hour=23, minute=10` | 11pm ET | **23:10** | 03:10 (+1d) | upcoming AP payment alerts |
| `receiving_discrepancy_monitor` | `hour=23, minute=15` | 11pm ET | **23:15** | 03:15 (+1d) | receiving-discrepancy detection |
| `balance_reduction_advisor` | `hour=23, minute=20` | 11pm ET | **23:20** | 03:20 (+1d) | balance-reduction advice |
| `missing_entry_detector` | `hour=23, minute=25` | 11pm ET | **23:25** | 03:25 (+1d) | missing journal-entry detection |
| `tax_filing_prep` | `hour=23, minute=30` | 11pm ET | **23:30** | 03:30 (+1d) | tax filing preparation |
| `uncleared_check_monitor` | `hour=23, minute=35` | 11pm ET | **23:35** | 03:35 (+1d) | uncleared-check monitoring |
| `quote_auto_expiry` | `hour=23, minute=40` | 11pm ET | **23:40** | 03:40 (+1d) | flips sent/draft quotes past `expiry_date` to `expired` |
| `incomplete_customer_profile` | `hour=23, minute=45` | 11pm ET | **23:45** | 03:45 (+1d) | incomplete-customer-profile alerts |

### Hour-bearing, but deliberately UTC — **must NOT become Eastern**

| registration id | declared | why it stays UTC |
|---|---|---|
| `dispatch_auto_finalize` | `hour="13-23", minute="*/15"` | See §2 — changing it would delay every production tenant by 4 hours. |

### Minute-only — behaviour-neutral, declared UTC to preserve today exactly

`platform_incident_dispatcher` (`*/15`), `briefing_sweep` (`*/15`), `note_settling_sweep`
(`*/15`), `email_imap_polling_sweep` (`*/5`), `email_token_refresh_sweep` (`:07`),
`email_subscription_renewal_sweep` (`:23`), `calendar_token_refresh_sweep` (`:11`),
`calendar_subscription_renewal_sweep` (`:27`).

Measured (§3): a minute-only `CronTrigger` produces an **identical fire set** under
`timezone=ET` and `timezone=UTC`, across both DST transitions. The three `*/15` sweeps
resolve per-user / per-tenant local time inside the sweep anyway
(`briefings/scheduler_integration.py`, `note/settling_sweep.py`), so the cron only has to
tick often enough.

### Not `CronTrigger` at all — untouched

`workflow_time_based_check`, `moc_schedule_sweep`, `moc_event_matcher` use
`add_job(..., "interval", minutes=N)`. Interval triggers have no wall-clock anchor and no
timezone to get wrong.

---

## 2. Flags

### ⚠️ F-1 — `dispatch_auto_finalize` is correct as UTC and two comments disagree about why

The registration comment (`scheduler.py:1026-1033`) says *"EVERY 15 MINUTES starting 13:00
UTC … covers every tenant tz from UTC-11 to UTC+13"*. The service's own docstring
(`delivery_schedule_service.py`) says *"Called by the scheduler every 15 min starting at
13:00 tenant-local (the cron in `app/scheduler.py` runs in the scheduler's timezone =
America/New_York by default …)"*.

They contradict each other, and the second is wrong twice over — the scheduler timezone is
inert, and the window is a UTC coverage range rather than a local time.

**What makes this load-bearing:** the real gate is in-service —
`auto_finalize_pending_schedules` resolves each tenant's timezone and **skips any tenant
whose local time is before `AUTO_FINALIZE_HOUR = 13`** (`delivery_schedule_service.py:68`).
The cron window only has to open early enough to catch every tenant's 13:00 local.

**All four production tenants have `companies.timezone = 'UTC'`** (measured). They reach
13:00 local at 13:00 UTC. Today's window opens at 13:00 UTC and catches them on the first
tick. An Eastern window would open at 17:00 UTC — **four hours late for every tenant on
production.** This is the one job where the "wrong" time is the working time.

Resolution: declare `timezone="UTC"` explicitly and reconcile both comments.

### ⚠️ F-2 — Two jobs fail on every run, and have for weeks

Measured on production, scheduled runs in the last 7 days:

| job | last 7 days | last `completed` scheduled run | error |
|---|---|---|---|
| `COLLECTIONS_SEQUENCE` | **7 failed / 7** | 2026-09-10 23:05 UTC | `unsupported operand type(s) for -: 'datetime.date' and 'datetime.datetime'` (1 of 4 tenants succeeds, 3 fail) |
| `REORDER_SUGGESTION` | **7 failed / 7** | 2026-09-11 07:00 UTC | `no vault supplier configured` (3 of 4 tenants succeed, 1 fails) |

Both are pre-existing, **neither is timing-related**, and both are out of scope here ("don't
change what any job does"). Recorded because:

- `COLLECTIONS_SEQUENCE` is the **same defect class `CLAUDE.md §11` already documents for
  `run_ar_aging_monitor`** — a `date` minus a `datetime`. That entry notes the saturated
  signal hid a second bug on the lines past the raise. This one has been red 35 days and
  affects 3 of 4 tenants.
- Both are **saturated signals**: permanently red, so neither can report a new failure.
- They do **not** block this change's verification — a failed run still writes its
  `job_runs` row with `started_at`, which is the only field §6 reads.

### ⚠️ F-3 — Deploy-day double-run risk, and the safe window

The scheduler uses the default in-memory job store and registers every job fresh on boot
with `replace_existing=True`. There is **no persisted `next_run_time` and no "already ran
today" guard** — `_run_per_tenant` / `_run_global` write a `job_runs` row but never consult
one. So on restart each job's next fire is computed from *now* forward.

The fix moves every hour-bearing job **4 hours later in UTC**. A job double-runs on deploy
day iff the deploy lands in `[old_fire, new_fire)` — the 4-hour window after its old fire
time. The union of those windows:

```
[00:01, 12:00)  ∪  [18:00, 22:00)  ∪  [23:00, 03:45 next day)
```

**Safe deploy windows: `[12:00, 18:00)` UTC and `[22:00, 23:00)` UTC** — i.e. 8 AM–2 PM ET,
or 6–7 PM ET.

Deploying at 19:00 UTC would double-run **`draft_invoice_generator`**, the job this whole
arc is about. Deploying at 23:30 UTC would double-run all ten nightly jobs.

Checked against the jobs' own idempotency, for the record:

| job | double-run would | safe? |
|---|---|---|
| `draft_invoice_generator` | re-select; excluded by the already-invoiced check (`draft_invoice_service.py:203-212,245`) | idempotent, but **avoid anyway** — it also rewrites order status |
| `price_version_activation` | re-select nothing; `status == "scheduled"` + `effective_date <= today` | idempotent |
| `tax_accumulation` | rebuild the same rows; documented idempotent | idempotent |
| `collections_sequence` | re-select nothing; `next_scheduled_at = now + 14 days` after processing (`agent_service.py:331`) | idempotent |
| `quote_auto_expiry` | re-expire already-expired quotes | idempotent |
| all others | write `agent_alerts` / analytics rows | duplicate alerts at worst |

**No scheduled job sends email or SMS.** The only external-send paths in
`draft_invoice_service` are at `:700` and `:755`, both inside the human-triggered
`approve_invoice` / `approve_all_no_exceptions`. The batch itself does not email.

### ⚠️ F-4 — `draft_invoice_generator` has fired at 11 distinct UTC times historically

298 of its 321 scheduled runs are at 18:00. The other 23 are all on 2026-04-07 and
2026-04-08 (`23:25`, `11:55`, `21:20`, `12:54`, `16:38`, `14:52`, `21:01`–`21:06`) — the
first two days of its life, when the schedule was evidently being iterated. It has fired at
18:00 UTC every day since 2026-04-08. Noted so the `distinct_hhmm = 11` in the raw census
isn't later read as instability.

---

## 3. DST — what happens to each job

**Method.** Computed locally against `apscheduler 3.11.3` + stdlib `zoneinfo` by walking
`get_next_fire_time` and measuring the **gap between consecutive fires in UTC**. A daily job
should show 24h, or 23h/25h across a transition. 47h means a day was skipped; 1h means it
fired twice.

⚠️ **Arithmetic is done in UTC.** A first attempt advanced the cursor with
`aware_dt + timedelta(seconds=1)`, which is wall-clock arithmetic — it discards `fold` and
jumps *backwards* an hour across a fall-back boundary. That produced an apparent
non-monotonic `get_next_fire_time` and nearly became a reported APScheduler bug. It was my
cursor, not the library. Recorded because the false version was more interesting than the
true one.

**Controls.** Both hazards are reachable by the instrument, so its silence elsewhere means
something:

| control | result |
|---|---|
| hypothetical job at `01:30` ET across 2026-11-01 fall-back | gaps `[1.0, 24, 24, 24]` — **fires twice**, 01:30 EDT = 05:30Z and 01:30 EST = 06:30Z |
| hypothetical job at `00:31` ET across 2027-03-14 spring-forward | gaps `[47.0, 24, 24, 24]` — **skips a day** |

### Fall-back, Sunday 2026-11-01 (02:00 EDT → 01:00 EST; local 01:00–01:59 occurs twice)

**No job is affected.** Every hour-bearing job shows a 25h gap across the transition and one
fire per calendar day. Nov 1 2026 is simultaneously a Sunday and the 1st, so the weekly
(`profile_update`, `network_readiness`) and monthly (`network_snapshot`,
`onboarding_pattern`) jobs all land on it — each fires exactly once.

The reason is simply that **no job sits in 01:00–01:59 ET**. The nearest are
`price_version_activation` at 00:01 and `ar_balance_reconciliation` at 02:00, both clean.

Minute-only sweeps: identical fire sets under ET and UTC (289 fires for `*/15`, 400 for
`*/5`, 72 for `:07`, all monotonic, in a ~3-day window). The repeated *local* wall times
(`01:00`, `01:15`, `01:30`, `01:45`) appear under **both** timezone settings — they are an
artefact of rendering UTC instants into ET during the doubled hour, not a double-fire.

**So for the question as asked — nothing to fix or flag for Nov 1 2026.**

### Spring-forward, Sunday 2027-03-14 (02:00 EST → 03:00 EDT; local 02:00–02:59 does not exist) — ⚠️ one job

| job | ET time | gaps across the transition | verdict |
|---|---|---|---|
| **`price_version_activation`** | **00:01** | **`[47.0, 24, 24, 24]`** | ⚠️ **skips one run** |
| `ar_balance_reconciliation` | 02:00 | `[23.0, 24, 24]` | fires once, slipped to 03:00 EDT |
| `platform_health_recalculate` | 02:15 | `[23.0, 24, 24]` | slipped to 03:15 EDT |
| `tax_accumulation` | 02:30 | `[23.0, 24, 24]` | slipped to 03:30 EDT |
| every other hour-bearing job | 01:xx–23:xx | `[23.0 or 24.0, 24, 24]` | clean |

Only `hour=0` skips. `hour=1` and up are clean; measured `00:01` and `00:31` both skip,
`01:01` does not. The non-existent-local-time jobs (02:00/02:15/02:30) resolve **forward** to
03:xx EDT and fire once — correct behaviour, no skip, no double.

**`price_version_activation` is flagged, not fixed, and the reason is that it self-heals.**
`activate_scheduled_versions` selects `PriceListVersion.effective_date <= today` with
`status == "scheduled"` (`price_increase_service.py`), so a skipped run activates the same
versions one day late on the next run, and already-activated versions are never reselected.
Worst case: a price version whose effective date is exactly Sunday 2027-03-14 goes live at
00:01 ET on 2027-03-15. Once a year, self-correcting.

Moving it to `hour=3` would eliminate the skip and is a one-line change if James wants it —
but it changes *when* a price list becomes effective, which is a business decision rather
than a clock fix, so it is surfaced rather than taken.

---

## 4. The fix

- **Eastern** (`BUSINESS_TZ = "America/New_York"`) on the 16 constructions covering the 25
  hour-bearing registrations in the table's first section.
- **UTC** (`UTC_TZ = "UTC"`) declared explicitly on the 9 constructions that are genuinely
  UTC: `dispatch_auto_finalize` (F-1) and the 8 minute-only sweeps.
- 16 + 9 = 25, matching the construction count.
- `BackgroundScheduler(timezone=BUSINESS_TZ)` is kept with a comment recording that it is
  **inert for pre-constructed triggers** — it still governs string triggers, if any are ever
  added, and deleting it would make the file look as though no business timezone were
  intended.
- Nothing about what any job does is changed. The end-of-day batch's selection logic is
  untouched; that is step 2.

### The guard

`tests/test_scheduler_timezone.py`, two independent assertions:

1. **Static** — AST-parse `app/scheduler.py`, find every `CronTrigger(...)` call, assert
   each carries a `timezone` keyword. Catches the source form a reviewer would scan for.
2. **Runtime** — call `register_all_jobs()` and assert every registered job's trigger
   either has no `timezone` attribute (interval triggers) or carries one that is **not** the
   machine's local zone. Catches a trigger built somewhere the static check does not read.

The runtime check is the stronger of the two: it asserts the jobs that actually exist. It
is also the one that would have caught the original defect, which was invisible in the
source — `CronTrigger(hour=18)` looks fine until you know where its timezone comes from.

---

## 5. Also in this dispatch

Item 5: `session_service.approve`'s docstring cited *"12 invoices and 5 rewritten orders on
production prove it is live"* as evidence the end-of-day batch is live. The figures are
correct and they are **testco's** — production, measured: testco 12 batch invoices and 5
auto-confirmed orders, sunnycrest **0 and 0**. The sentence read as though Sunnycrest had
been through it. Corrected to name the tenant.

---

## 6. Post-deploy observation

*Filled in after the deploy — see the bottom of this document.*
