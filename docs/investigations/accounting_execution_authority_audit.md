# ACCOUNTING EXECUTION-AUTHORITY AUDIT (read-only)

**Date:** 2026-07-17 · **HEAD:** `b0b6b831` (two perf-pass riders past the dispatch's `e65762e8`, same lineage) · **Method:** every cell below witnessed from run provenance, live configs, and one benign write-authority test per class (dev, at the effect, cleaned) — not memory.
**The operator's question:** are the accounting automations transferred to the new system and actually governed by it?
**The short answer:** *half-transferred, cleanly split.* EXECUTION (the engine, params, dry-run, H1 failure routing) is already single-authority — every scheduled accounting fire runs through `workflow_engine.start_run` → `_execute_step`, so the P1 overlays and H1 escalation govern real fires today. SCHEDULE authority is NOT transferred: every firing accounting task fires on its runtime cron via `workflow_scheduler`; the MoC/ponder layer holds zero schedule authority over any of them, and the P1 composer can silently create a teaching-surface divergence (witnessed below).

---

## THE SEVERITY FLAG, FIRST (the latent honesty bug)

**Witnessed on dev (mirror class, benign, cleaned):** composing "the first Monday at 4:00 PM" on Monthly Statement Run through the P1 composer's exact write path:

```
BEFORE  runtime schedule: {'cron': '0 6 1 * *'}   ponder WHEN: 'The 1st of each month at 6:00 AM (tenant-local).'
AFTER   runtime schedule: UNCHANGED               ponder WHEN: 'The first Monday of every month at 4:00 PM.'
sweep go_live: False (unpromoted); if promoted: STILL False  ← the §6 mirror guard
```

The runtime cron keeps firing untouched; the WHEN beat immediately teaches the composed schedule as if it were truth. **Today this divergence is LATENT, not live** — zero accounting tasks carry any MoC trigger (dev AND staging, verified) — but the composer makes it one click away for a platform admin, and P2's fork+composer does the same at tenant scope (a fork's trigger edits are honest for the fork's dry-runs, but the SHARED runtime schedule still fires the real thing for that tenant). Nothing warns. **T-0 below closes this before any transfer work.**

**A second, pre-existing truth divergence, live TODAY:** Cash Receipts Matching's ponder says *"Every night at 11:30 PM."* — but its `time_of_day` trigger fires at **23:30 UTC wall-clock** (≈7:30 PM ET), the known 8b.5-flagged TZ latent bug. The teaching surface repeats the config's claim, not the firing truth. (Also listed per-row below.)

---

## THE AUTHORITY TABLE

**Catalog tasks (type=Accounting, all `vertical_default`, all zero MoC triggers on dev + staging):**

| Task | Fires today? (staging, 30d) | Firing system + schedule truth | §6 status | Ponder WHEN vs firing truth | Composer edit authority | Params/audiences reach fires? |
|---|---|---|---|---|---|---|
| **Monthly Statement Run** | ✅ 3 fires, `trigger_source='schedule'` | runtime scheduler, cron `0 6 1 * *` tenant-tz | **MIRROR** (`wf_sys_statement_run`) — cannot go live via MoC (guard witnessed) | ✅ matches today (beat derives from runtime); diverges the moment a trigger is composed (witnessed) | **display + dry-run preview only** — the real fire is untouched | ✅ engine seam (P1) governs real fires |
| **AR Collections** | ✅ 60 fires | runtime, cron `0 23 * * *` tenant-tz | MIRROR | ✅ today / latent divergence | display-only | ✅ |
| **Expense Categorization** | ✅ 6,020 fires (every 15 min) | runtime, cron `*/15 * * * *` | MIRROR | ✅ today / latent divergence | display-only | ✅ |
| **Cash Receipts Matching** | ✅ 126 fires | runtime, `time_of_day` 23:30 — **fires UTC, not tenant-local** (the 8b.5 TZ bug) | MIRROR | ⚠️ **LIVE divergence**: teaches "11:30 PM" (reads tenant-local); fires ≈7:30 PM ET | display-only | ✅ |
| **Month-End Close** | human-initiated only | `trigger_type='manual'` — the triage/agents surface starts it through the engine | MIRROR | ✅ honest ("When you run it — this one waits for a person") | (nothing scheduled to edit) | ✅ |
| **Funeral Home Billing** | ❌ **never fires anywhere** | none — authored 4-node draft (`invoice_and_statement_run`), no runtime source, never compiled, no triggers | authored draft (compilable) | ⚠️ no WHEN beat (honest) — but the map's Frequency field claims **"End of Month"** with no firing mechanism behind it | a composed trigger WOULD be authoritative (compiled path) — but the task has never been compiled/promoted | n/a (no fires) |

**Off-catalog accounting automations (the third authority system — invisible to the map entirely):**

| Automation | System | Governed by engine/params/H1/ponder? |
|---|---|---|
| AR aging monitor (11:00 PM ET) | **APScheduler direct job** (`scheduler.py` JOB_REGISTRY) | ❌ none of it — own try/except logging, no Decision Triage routing, no catalog row, no ponder, no params |
| Collections sequence (11:05 PM) | APScheduler direct | ❌ |
| **AP upcoming-payments monitor** (11:10 PM) | APScheduler direct (the D-3-rewired `run_ap_upcoming_payments`) | ❌ |
| + 5 proactive accounting jobs (receiving-discrepancy, balance-reduction, missing-entry, tax-filing-prep, uncleared-check) | APScheduler direct | ❌ |

**The compiled precedent (the target state, already proven):** the MoC Witness Marker task — compiled workflow, MoC schedule+event triggers, **143 sweep fires across dev+staging (92+51), all dry-run**, `_resolve_go_live` the sole authority. For compiled tasks the ponder's composer IS already write-authoritative over firing. No accounting task is in this class yet.

**Post-purge content census (the keep-list's accounting receipt):** dev + staging both hold the 6 accounting tasks + 28 mirrors intact; **zero** MoC triggers, **zero** authored captions, **zero** forks, **zero** live param values on accounting rows in either environment (the ponder-arc witnesses were cleaned by design; nothing was lost that existed — the purge receipt's moc rows: 51→51 tasks, 8→8 triggers).

---

## THE TRANSFER PLAN (the §6 dedupe, scoped + sized)

**What single-authority requires:** per task, exactly ONE schedule exists at any instant — the MoC trigger — firing through the sweep + engine (dry-run default, `is_live` promotion, the fire cap, H1 routing: accounting inherits the whole safety architecture it already half-uses). The double-fire hazard closes **by construction**: the adopt is an atomic swap (create the promoted MoC trigger FROM the runtime config + retire the runtime schedule in the same transaction), never a period where both fire.

- **T-0 — THE HONESTY GUARD (do first, ~half session).** Until a task is transferred, a schedule-type MoC trigger on a MIRROR-backed task must not present as firing truth: the WHEN beat badges it ("previewing in dry-run — the standard still fires: *the 1st at 6:00 AM*", both sentences shown), and/or the composer on mirror tasks says so before saving. Kills the witnessed latent lie without touching firing. *(Also fold in: the Cash Receipts live divergence — either fix the `time_of_day` UTC bug (the 8b.5 flag, one matcher change + a config decision) or make the ponder speak UTC truth. The bug fix is the right end; flag the firing-time change to the operator first — statements of fires shifting 4 hours is operator-visible.)*
- **T-1 — THE ADOPT MECHANISM (~1 session).** `adopt_schedule(task_id)`: translate the runtime config (cron → `spec_kind: cron`; `time_of_day` → same, tenant-local FIXED) into a promoted (`is_live=True`) MoC trigger + null the runtime schedule (`trigger_type='manual'` + a `schedule_transferred_at` provenance stamp) in one transaction, behind the GoLiveConfirm evidence pattern (the operator confirms per task; nothing silently changes its firing). **Lift the §6 guard precisely:** replace the blanket mirror-block with "mirror AND its runtime schedule is still active" — a transferred mirror fires live safely because the double-fire source is gone by construction. Invariant test: for every task, `count(active runtime schedule) + count(live MoC schedule triggers) ≤ 1`.
- **T-2 — THE FIVE ADOPTS (~1 witness session, per-task operator confirmation).** Statement Run, AR Collections, Expense Categorization, Cash Receipts (post-TZ-decision), each adopted + witnessed at the next fire's provenance (`trigger_source='moc_task_schedule'`, live). Month-End Close: nothing to transfer (manual is its truth — already honest). After each adopt, the ponder's composer is fully write-authoritative for that task — the P1/P2/P3 grammar becomes real control.
- **T-3 — THE EDGES (scoped, not sized here).** Funeral Home Billing: an owner decision — author + compile + promote its firing, or drop the "End of Month" frequency claim (a task that fires nowhere shouldn't claim a cadence). The APScheduler accounting family (AR aging / collections sequence / AP monitor / 5 proactive): this is the existing **Phase 8f** roadmap (migrate to engine workflows) — once engine-backed, they join the adopt path like the five; until then they remain the third authority, ungoverned and unmapped, and should at least gain catalog rows so the map stops being silent about them.

**Sizing total: ~2.5 sessions to full schedule-authority transfer for the firing five**, with T-0 shippable alone and immediately. The big structural work is already done — the engine, params, dry-run, cap, and H1 all govern real accounting fires today; what transfers is the *clock*.

**STOP-discipline notes:** read-only held except the one witnessed mirror-class write test (cleaned; the compiled class's write authority is witnessed by the marker task's 143 sweep fires rather than a new write). The severity flags above surface ahead of the plan per dispatch: (1) the composer-enabled latent WHEN lie (T-0), (2) Cash Receipts' live UTC divergence (T-0 rider), (3) Funeral Home Billing's cadence claim with no mechanism (T-3).

---

## RESOLUTION (2026-07-17 — the T-2 walk; the table, closed)

The transfer plan executed: T-0 (`1e1274e3`), T-1 (`26e2c0d4`), T-2 (this commit — the operator's guided walk on staging, five adopts + one birth, each behind his explicit confirm). The closing authority table, re-read from staging after the walk:

| Automation | Schedule authority | The schedule (carried/authored) | Adopted/born (UTC) | Fire witnessed |
|---|---|---|---|---|
| Expense Categorization | **moc** (adopted) | Every 15 minutes | 2026-07-17 14:56:52 | ✅ sweep tick 15:07, intended 15:00 window, LIVE, `moc_task_schedule`; 0 runtime fires post-retire |
| Cash Receipts Matching | **moc** (adopted) | Every night at 11:30 PM tenant-local — **the corrected clock** (the T-0 TZ fix's staging graduation) | 2026-07-17 14:57:48 | tonight 11:30 PM ET via the sweep |
| AR Collections | **moc** (adopted) | Every night at 11:00 PM tenant-local | 2026-07-17 ~15:00 | tonight 11:00 PM ET via the sweep |
| Monthly Statement Run | **moc** (adopted) | The 1st of each month at 6:00 AM tenant-local | 2026-07-17 ~15:01 | computed next-fire **2026-08-01 06:00 ET** in-zone (monthly — said honestly at its confirm; the T-1 boundary pins cover the shape) |
| Month-End Close | **moc** (manual — was always honest) | On demand | — (nothing to transfer) | n/a |
| **Funeral Home Billing** | **moc** (BORN NATIVE) | The last day of each month at 6:00 AM tenant-local (`0 6 last * *` — APScheduler's `last`; cleanly expressible) | authored + PROMOTED (operator's call) 2026-07-17 ~15:05 | first fire **2026-07-31 06:00 ET**, live |

Also walked at the operator's per-step confirms (the grouped mirrors, same shape): Document Review Reminder (Mon 8:00 AM), Compliance Sync (daily 3:00 AM), Training Expiry Monitor (Mon 7:00 AM) — all **moc**, carried verbatim. Deliberately left runtime-scheduled per the operator's scope choice: Safety Program Generation, Wilbert Catalog Auto-Fetch (non-accounting; badged honestly; a later walk).

**The closing state:** every accounting WHEN beat badge-free, composer OPEN — the honesty guard with nothing left to guard against in the area. The runtime scheduler's accounting section: retired (six `schedule_retired_at` stamps; the rows' trigger_type/config preserved as authored history). Dev aligned to match (same adopts + the same promoted birth). The third authority (the APScheduler direct family — AR aging, collections sequence, AP monitor, 5 proactive) remains as scoped at T-3 / Phase 8f — outside this walk, still flagged.

**The definition, met (for the walked area):** every accounting automation authored, taught, edited, fired, monitored, and governed by ONE system — the map's trigger through the sweep + engine + params + H1 — the one the operator built.
