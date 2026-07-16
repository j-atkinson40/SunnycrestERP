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
    "seed_full_year_e2e": (
        "local-only",
        "a full 2025 calendar of accounting E2E fixtures (cleanup + rebuild "
        "every run) — dev-scale test data with no staging job",
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
