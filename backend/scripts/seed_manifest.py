"""The seed tier MANIFEST (perf pass, 2026-07) — declared per seed, with a
one-line justification. Never inferred.

TIERS:
  all         (the default — seeds not listed here run everywhere)
  local-only  runs ONLY on a developer machine. Skipped whenever
              RAILWAY_GIT_COMMIT_SHA is set (any Railway deploy — staging
              AND production). The marker matters: staging deliberately
              runs with ENVIRONMENT=dev, so the ENVIRONMENT variable
              cannot distinguish staging from a laptop — the Railway
              commit marker can (it's also what /api/health reports).
  manual      never run by the canonical runner — ops tools that happen
              to match the seed_*.py naming convention.

The canonical runner (run_canonical_seeds.sh) asks this module once per
boot (`python -m scripts.seed_manifest --skips`) and logs each skip WITH
its declared reason — a skipped seed is visible in every boot log, never
silently absent.
"""
from __future__ import annotations

import os
import sys

# name -> (tier, one-line justification)
TIERS: dict[str, tuple[str, str]] = {
    # ── the five demo seeds that had no production guard (2026-10-24) ──────────
    #
    # ⚠️ THESE RAN ON EVERY PRODUCTION DEPLOY AND NOTHING STOPPED THEM. Measured
    # 2026-10-23 while classifying the boot seeds: `seed_jcf_demo` carries an
    # ENVIRONMENT refusal and these five do not, so the canonical runner started a
    # Python process for each of them on production, 55 seeds deep, to write demo
    # data.
    #
    # ⚠️ AND THE HAZARD IS NOT HYPOTHETICAL, THOUGH IT HAS NOT FIRED. `seed_quotes`
    # and `seed_saved_orders` share a `pick_tenant` that prefers `testco` and
    # otherwise takes THE FIRST ACTIVE COMPANY WITH THE SALES MODULE, under a comment
    # reading "When Sunnycrest onboards, relocate deliberately" — a deferred decision
    # never made, and Sunnycrest is live. On production that fallback resolves to
    # `sunnycrest` (created 2026-03-27). It has not fired only because `testco`
    # exists on production and the preferred branch wins: measured, all 8 quotes and
    # 2 saved orders are in `testco` and none in `sunnycrest`. Deleting `testco`
    # would redirect demo quotes into the real company's books on the next deploy.
    #
    # ⚠️ `manual` RATHER THAN A GUARD INSIDE EACH SCRIPT, for the reason the entry
    # below gives for the demo catalogue: a tier is read ONCE per boot and logged with
    # its reason, where five separate ENVIRONMENT checks are five chances to write one
    # that fails open — which `railway-prep.sh` records having already happened once
    # (`!= "production"` inferred "dev" from a MISSING variable and created
    # `hopkins-fh` on production 73 seconds after that guard was committed).
    "seed_quotes": (
        "manual",
        "4 sample quotes for the Quoting Hub demo. No ENVIRONMENT guard, and its "
        "`pick_tenant` falls back to the first active company with the sales module — "
        "`sunnycrest` on production. Invoked by seed_dev.sh for local dev and CI.",
    ),
    "seed_saved_orders": (
        "manual",
        "2 sample saved orders for the Compose-templates demo. Same unguarded "
        "`pick_tenant` fallback as seed_quotes. Local dev and CI only.",
    ),
    "seed_nl_demo_data": (
        "manual",
        "Phase 4 NL-overlay demo companies and cases, written against `testco` by "
        "default. Nothing for production to do with them.",
    ),
    "seed_demo_artifact_focuses": (
        "manual",
        "MoC option-3 demo artifacts — two focus configs. Demo content by its own "
        "docstring; platform-scope rows, so no tenant fallback, but still not "
        "production's.",
    ),
    "seed_demo_artifact_workflows": (
        "manual",
        "MoC option-3 demo artifact — the Invoice & Statement Run workflow. Same "
        "reasoning as seed_demo_artifact_focuses.",
    ),

    "seed_sunnycrest_demo_catalog": (
        "manual",
        "gives the canonical dev/CI sunnycrest the demo catalogue four tests are "
        "written against. local-only because `run_canonical_seeds.sh` runs on every "
        "production deploy and production's sunnycrest holds the REAL company's real "
        "catalogue — writing demo products there would be a production write nobody "
        "asked for. Backend CI was red from 2026-10-16 to 2026-10-21 for want of this "
        "data; see the seed's own docstring for the reproduction. ⚠️ `manual` RATHER "
        "THAN `local-only` BECAUSE THE RUNNER'S ORDER CANNOT BE RELIED ON: `find | "
        "sort -z` collates ignoring punctuation, so seed_sunnycrest_demo_catalog "
        "sorted BEFORE seed_sunnycrest and found no tenant to attach to — measured, "
        "the seed logged 'nothing to do' and CI stayed red. It is invoked explicitly "
        "at the END of scripts/seed_dev.sh, which local dev and CI both run and no "
        "deploy ever calls.",
    ),

    "seed_full_year_e2e": (
        "local-only",
        "a full 2025 calendar of accounting E2E fixtures (cleanup + rebuild "
        "every run) — dev-scale test data with no staging job",
    ),
    "seed_agent_test": (
        "local-only",
        "a month-end-close agent-test fixture (4 customers with known "
        "anomaly triggers, clean+rebuild every run) — its cleanup FK-fails "
        "on staging where seed_dispatch_demo's deliveries reference its "
        "customers; dev-scale test data with no staging job (the first "
        "staging [seed-timing] profile caught it)",
    ),
    "seed_intelligence_dev_executions": (
        "local-only",
        "synthetic intelligence traffic that samples dev-only entities "
        "(ringcentral_call_log rows exist locally, not on staging — the "
        "FK flip-flop's root)",
    ),
    "seed_staging_api": (
        "manual",
        "an HTTP client aimed at the staging API — boot prep runs BEFORE "
        "the server answers (the order/timing flip-flop's root: it only "
        "passed when the previous container still served); an ops tool, "
        "not a boot seed",
    ),
    "seed_accounting_demo": (
        "manual",
        "an --tenant-slug-REQUIRED ops tool, not a boot seed. It is the only "
        "seed with argparse `required=True`, so the runner's bare invocation "
        "exits rc=2 on EVERY canonical run — including every staging deploy, "
        "where it has been a standing WARN in the boot log. Same shape as "
        "seed_reconciliation_test below: giving it a default tenant would seed "
        "demo accounting data into that tenant on every deploy, which is the "
        "harm that entry exists to prevent. Run it explicitly with a slug.",
    ),
    "seed_reconciliation_test": (
        "manual",
        "W-2 reconciliation matcher test substrate — an on-demand ops tool, "
        "NOT a boot seed. Bare invocation defaults to --tenant-slug sunnycrest "
        "and cleanup+re-seeds (would reset the Books Review Phase 2 queue on "
        "every deploy, and it carries no ENVIRONMENT=production guard). Run "
        "explicitly with a tenant when you want it.",
    ),
    # ── The --apply-gated set: the runner passes no flags, so these have
    # only ever DRY-RUN at boot — a scan that seeds nothing and burns
    # minutes. Each is an explicitly-invoked ops moment, not a boot seed.
    "seed_pending_attention_backfill": (
        "manual",
        "a one-time (c)-arc backfill, --apply-gated — the runner's bare "
        "invocation dry-run-scans EVERY awaiting-attention substrate and "
        "seeds nothing (the sweep's single largest time sink)",
    ),
    "seed_task_substrate_backfill": (
        "manual",
        "a one-time task-substrate backfill, --apply-gated — bare "
        "invocation is a no-op scan",
    ),
    "seed_email_demo": (
        "manual",
        "--apply-gated email demo fixture — bare invocation seeds nothing",
    ),
    "seed_email_inbox_demo": (
        "manual",
        "--apply-gated email demo fixture — bare invocation seeds nothing",
    ),
    "seed_email_labels_demo": (
        "manual",
        "--apply-gated email demo fixture — bare invocation seeds nothing",
    ),
    "seed_email_quote_approval_demo": (
        "manual",
        "--apply-gated email demo fixture — bare invocation seeds nothing "
        "AND exit-4s on its seed_email_demo prereq (the second warn-tally "
        "entry, dead by declaration)",
    ),
}

_VALID_TIERS = {"all", "local-only", "manual"}


def is_deployed() -> bool:
    """A Railway deploy (staging or production) vs a developer machine."""
    return bool(os.environ.get("RAILWAY_GIT_COMMIT_SHA"))


def skips() -> list[tuple[str, str, str]]:
    """The (name, tier, why) list the runner must skip in THIS environment."""
    out = []
    deployed = is_deployed()
    for name, (tier, why) in sorted(TIERS.items()):
        assert tier in _VALID_TIERS, f"{name}: unknown tier {tier!r}"
        if tier == "manual" or (tier == "local-only" and deployed):
            out.append((name, tier, why))
    return out


if __name__ == "__main__":
    if "--skips" in sys.argv:
        for name, tier, why in skips():
            print(f"{name}\t{tier}\t{why}")
    else:
        for name, (tier, why) in sorted(TIERS.items()):
            print(f"{name}\t{tier}\t{why}")
