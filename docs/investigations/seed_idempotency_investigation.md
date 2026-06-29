# Seed Idempotency Arc — Phase 0: Re-run Safety Catalog (read-only)

**Date:** 2026-06-26 · **HEAD:** `8b2fcbd` · **Read-only** — no code, no commit.
**Source of truth:** local source + `bridgeable_dev` (FK introspection + **live re-run reproduction**). Staging deploy log is the symptom source.
**Method:** mapped the boot chain, split fail-loud vs warn-continue, root-caused the 3 witnessed against source, **reproduced the fail-loud chain twice on dirty state**, classified all 42 seeds structurally, checked git history.

---

## HEADLINE — the dispatch's core hypothesis is PARTIALLY REFUTED by reproduction

**The fail-loud seed chain re-runs CLEAN on the current HEAD.** Witnessed: `seed_staging → seed_fh_demo → seed_dispatch_demo` run twice in sequence against a dirty `bridgeable_dev`, **all six invocations `rc=0`, no cemetery FK, no error.** The "seed chain is non-idempotent → a fail-loud seed aborts → the abort/retry IS the 20-min boot" mechanism **does not reproduce at HEAD on a normal dirty state.**

Two corroborating facts:
1. **Git history shows no recent idempotency fix** on any fail-loud seed (dispatch last touched `b1fb6f4` for a slug lookup; `_find_cemetery` last changed in Phase B; seed_staging's idempotency is the old R-1.6.4/5 work; seed_agent_test's cleanup dates to Phase 2). So HEAD ≈ what staging runs — this isn't "fixed at HEAD, broken on staging-behind."
2. **Steady-state idempotency is broadly present.** 35 of 42 seeds carry zero deletes + guarded inserts (the documented Option-A "already exists → noop" pattern; guard counts 7–116). Only 7 seeds DELETE-then-reseed.

**Therefore the 20-min boot is NOT steady-state non-idempotency. It is recovery-from-a-SPECIFIC-dirty-state.** The witnessed cemetery FK ("failed pass 1, succeeded pass 2") fits a **self-perpetuating partial-abort loop**: an aborted deploy leaves partial-commit residue; the next deploy's cleanup — which **SAVEPOINT-swallows every delete failure** (see #1 below) — can't fully clear that specific residue, so it aborts too; occasionally a pass clears enough to succeed ("pass 2"). My local 2-pass starts from a *complete* prior run, not a *partial-abort* one, so it never enters the loop.

**What this means for the fix:** the target is not "make seed X idempotent" (the steady state is fine). It is **"make the cleanup able to recover from ANY partial-abort residue"** — i.e. de-fang the SAVEPOINT-swallow that lets poison rows survive. That single change breaks the loop regardless of which seed first aborts. **Pinning the exact poison row requires staging's failure-state DB / the full deploy traceback — operator's Railway domain, same gate as #3/#4 from the health-triage catalog.**

---

## THE MECHANISM (confirmed)

`railway-start.sh`: migrations (clean) → **FAIL-LOUD seeds** (`if ! …: exit 1` → deploy abort → Railway retry = the 20-min boot) → **`run_canonical_seeds.sh`** (`set +e`, warn-and-continue, always `exit 0`).

- **FAIL-LOUD (4) — the only seeds that can cost the 20-min retry:** `seed_staging`, `seed_fh_demo`, `seed_dispatch_demo`, `seed_edge_panel_inheritance`.
- **WARN-CONTINUE (38) — failures leave data GAPS, never deploy-cost:** every other `seed_*.py`, auto-discovered by `find seed_*.py` in the canonical runner (the 4 fail-loud are explicitly skipped there, run upstream).

**Severity axis = which chain.** A fail-loud failure costs 15-20 min of retry; a warn-continue failure costs a missing demo row. Fix fail-loud first.

---

## THE 3 WITNESSED — root-caused

### #1 — `seed_dispatch_demo` cemetery FK (`sales_orders_cemetery_id_fkey`). FAIL-LOUD. **NOT reproduced at HEAD.**
- **Lifecycle mapped:** `seed_staging` is the sole creator of testco cemeteries (`scripts/seed_staging.py:683`, idempotent: `SELECT by (company_id,name) → UPDATE-or-INSERT`, **ids stable across runs**). `seed_dispatch_demo._find_cemetery` only *reads* them (`:385`), returning a matched cemetery, else fallback `cems[0]`, else `None`; the order sets `cemetery_id=cem.id if cem else None` (`:611`). dispatch's own `_cleanup` deletes its tagged deliveries/orders/schedules (`:429`) — **not** cemeteries.
- **Reproduction: passes both passes, no FK.** On a normal dirty state the chain is idempotent.
- **Verdict:** state-specific to staging. **Latent fragilities that could produce it under partial-abort residue:** (a) `_find_cemetery`'s `cems[0]` fallback returns *any* cemetery — if the matched name's cemetery is absent it silently picks another, masking missing data; (b) the SAVEPOINT-swallow in seed_staging's cleanup (below) lets FK-undeletable rows survive. **Exact poison row needs staging's failure-state — operator/Railway.**

### #2 — `seed_agent_test` `deliveries_customer_id_fkey` on `DELETE FROM customers`. WARN-CONTINUE. **VERIFIED in source.**
- Cleanup (`scripts/seed_agent_test.py:71-82`) deletes `CustomerPaymentApplication → CustomerPayment → Invoice → SalesOrder → Customer` (parent-last ordering is *correct*) but **omits `deliveries`** — and `deliveries.customer_id → customers`. On a dirty re-run where any delivery references an AGTEST customer, the final `DELETE Customer` violates `deliveries_customer_id_fkey`.
- **Fix:** add `db.query(Delivery).filter(Delivery.customer_id.in_(cids)).delete()` (and audit for any other `customer_id` children) **before** the Customer delete. Pure missing-child-delete; warn-continue → gap, not deploy-cost.

### #3 — cataloged `POST /api/v1/cemeteries` UniqueViolation. **Same constraint family, DIFFERENT surface — NOT a seed.**
- Both the seed and the API hit `cemeteries.UniqueConstraint(company_id, name)`. The seed handles it (SELECT-then-UPDATE/INSERT); the **API endpoint does not** (raw INSERT → `UniqueViolation` → 500 on a duplicate name). This is an **application bug, not an idempotency bug** — belongs to whoever owns `POST /cemeteries`, not this arc. Flagged separately.

---

## THE FK-ORDERING-SWALLOW (the real structural culprit behind the loop)

`seed_staging._run_cleanup_deletes` (`:244`) builds deletes as `deep_children` (hardcoded, correct child-first) **+ `fk_deletes` (dynamic FK discovery, ordered `ORDER BY table_name` — ALPHABETICAL).** Each statement is wrapped in `SAVEPOINT … ROLLBACK TO SAVEPOINT` that **swallows every failure silently** (`:288-296`).

- Alphabetical means `DELETE FROM cemeteries` (c) runs **before** `DELETE FROM sales_orders` (s) — but `sales_orders.cemetery_id → cemeteries`. So when orders still reference cemeteries, the cemetery delete **fails and is swallowed** → cemeteries survive (harmless for cemeteries; later `_seed_cemeteries` UPDATEs them). **But the same swallow applies to EVERY table:** any child row the alphabetical order can't delete yet survives silently. On a *normal* dirty state this self-corrects; on a *partial-abort* state it can leave poison rows that break a later insert — and **nothing logs it** (the swallow is total).
- This is why the loop is invisible and self-perpetuating: the cleanup *claims* success (always `flush()`es, never raises) while leaving residue.

---

## FULL PER-SEED CLASSIFICATION (42 seeds)

**IDEMPOTENT — guarded inserts, zero deletes (35):** all `seed_intelligence*` (12), all `seed_email*` (5), all `seed_triage*` (4), all `seed_workflow*` except the prompt-example, `seed_personalization*` (2), `seed_calendar_step51`, `seed_edge_panel_inheritance` (FAIL-LOUD but del=0/guarded → **safe**), `seed_focus_template_inheritance`, `seed_jcf_demo`, `seed_jcf_template`, `seed_moc_manufacturing`, `seed_nl_demo_data`, `seed_pending_attention_backfill`, `seed_quotes`, `seed_saved_orders`, `seed_task_substrate_backfill`, `seed_intake_intelligence_prompts`, `seed_staging_api`. **Proven-safe — do not re-litigate.**

**DELETE-then-reseed — FK-ordering risk (7):**
| Seed | Chain | del / guard | Status |
|---|---|---|---|
| `seed_staging` | FAIL-LOUD | 19 / 113 | Idempotent at HEAD (repro passes); the SAVEPOINT-swallow cleanup is the loop's masking layer — **harden this** |
| `seed_fh_demo` | FAIL-LOUD | 14 / 116 | Heavily guarded; repro passes |
| `seed_dispatch_demo` | FAIL-LOUD | 3 / 12 | #1 — repro passes; `_find_cemetery` fallback latent |
| `seed_agent_test` | warn-continue | 5 / 7 | **#2 verified bug** — missing deliveries-delete |
| `seed_full_year_e2e` | warn-continue | 19 / 44 | Largest delete+insert (28 ins); **audit delete ordering** (not yet root-caused) |
| `seed_intelligence_dev_executions` | warn-continue | 2 / 3 | Low guard + deletes; **audit** |
| `seed_workflow_ai_prompt_example` | warn-continue | 1 / 4 | Minor; audit |

No seed flagged RAW-INSERT-without-guard. **No schema/constraint change needed anywhere.**

---

## RANKED FIX PLAN

**P0 — break the partial-abort loop (reclaims the 20 min). One change, highest leverage.**
- **Make `seed_staging._run_cleanup_deletes` recover from any residue + stop swallowing silently.** Options (pick at fix time): (a) **topologically order** the deletes (children before parents) instead of alphabetical, so no FK-blocked delete needs swallowing; (b) **iterate-to-fixpoint** — re-run the delete set until row counts stabilize, so order-dependence self-resolves; (c) **`TRUNCATE … CASCADE`** scoped to the tenant's tables (most robust, biggest hammer). In all cases, **log swallowed failures** (today they're invisible). This is a *cleanup-ordering/robustness* fix, not an upsert fix. Breaks the loop regardless of which seed first aborts.
- **PRECONDITION (operator):** pull the staging failure-state / full deploy traceback (Railway) to confirm *which* fail-loud seed aborts on staging and *which* residue row poisons it — same gate as health-triage #3/#4. The P0 fix above is robust without it, but the traceback confirms the target + lets us write a regression that reproduces the actual staging state.
- Optionally harden `seed_dispatch_demo._find_cemetery`: log (don't silently `cems[0]`-fallback) when a named cemetery is missing — turns a silent data-mask into a visible signal.

**P1 — warn-continue gaps (data correctness, not deploy-cost):**
- `seed_agent_test`: add the deliveries-delete (and audit other `customer_id` children) before `DELETE Customer`. **#2, verified, clean fix.**
- Audit `seed_full_year_e2e` (19 deletes) + `seed_intelligence_dev_executions` (2 deletes, low guard) cleanup ordering for the same missing-child / wrong-order pattern.

**P2 — not this arc:** the `POST /cemeteries` UniqueViolation 500 (#3) is an API-layer bug (raw insert ignores the unique constraint), owned by whoever owns that route — flag, don't fix here.

**Phasing recommendation:** ship **P0 alone first** (the cleanup-robustness change) — that alone targets the 20-min retry. P1 is a separate, lower-stakes commit (gaps). Do **not** bundle.

---

## STOP — read-only; not committed.

**Honest scope:** #2 root-caused in source; #3 classified (API bug, not seed). **#1 NOT reproduced** — flagged as state-specific with the partial-abort-loop + SAVEPOINT-swallow as the leading mechanism, explicitly needing staging's failure-state to pin (operator/Railway). The dispatch's "non-idempotent chain" framing is **refuted for steady state** (the chain re-runs clean at HEAD) and **redirected** to cleanup-recovery robustness. The chain is NOT larger/more entangled than the sample — 35/42 are proven-safe; the risk concentrates in the one swallowing cleanup + 3 warn-continue delete-seeds. If the staging traceback later shows a *clean* data/schema bug rather than residue, re-open #1 as its own item.
