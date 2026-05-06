#!/usr/bin/env bash
#
# R-1.6.4 — Local validation that seed_staging.py + seed_fh_demo.py
# are idempotent across runs.
#
# Pre-R-1.6.3 these scripts could half-seed silently (railway-start.sh
# swallowed errors). Pre-R-1.6.4 seed_staging.py crashed on the second
# run due to UNIQUE collisions on customers / cemeteries / products /
# price_list_versions. R-1.6.4 fixes all 7 substantive steps via
# existing-row + UPDATE pattern. This script catches future regressions
# of the same class before they hit staging.
#
# Usage:
#   DATABASE_URL=postgresql://localhost:5432/bridgeable_dev \
#       backend/scripts/test_seed_idempotency.sh
#
# Pre-conditions:
#   - DATABASE_URL is set + reachable.
#   - alembic upgrade head has run (script does NOT run alembic itself —
#     that's a separate concern).
#   - ENVIRONMENT is unset OR set to a non-production value (production
#     guard inside both seeds aborts otherwise).
#
# Exit codes:
#   0 — both seeds ran twice, both runs succeeded.
#   1 — first run failed (a different bug class — investigate separately).
#   2 — second run failed (idempotency regression).

set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL must be set." >&2
    echo "Usage: DATABASE_URL=postgresql://... $0" >&2
    exit 1
fi

if [ "${ENVIRONMENT:-dev}" = "production" ]; then
    echo "ERROR: refusing to run against production. Unset ENVIRONMENT or set non-prod value." >&2
    exit 1
fi

cd "$(dirname "$0")/.."  # backend/

echo "=== R-1.6.4 idempotency validation ==="
echo ""

run_seed() {
    local label="$1"
    local cmd="$2"
    echo "[$label] $cmd"
    if eval "$cmd"; then
        echo "[$label] OK"
    else
        echo "[$label] FAIL"
        return 1
    fi
}

echo "--- Pass 1: fresh seeds ---"
if ! run_seed "seed_staging-1"  "python -m scripts.seed_staging --idempotent"; then
    echo ""
    echo "FAIL: seed_staging.py first run failed. Different bug class than R-1.6.4 idempotency."
    exit 1
fi
if ! run_seed "seed_fh_demo-1"  "python -m scripts.seed_fh_demo --apply --idempotent"; then
    echo ""
    echo "FAIL: seed_fh_demo.py first run failed. Different bug class than R-1.6.4 idempotency."
    exit 1
fi

echo ""
echo "--- Pass 2: idempotency check (should be no-op or UPDATE-only) ---"
if ! run_seed "seed_staging-2"  "python -m scripts.seed_staging --idempotent"; then
    echo ""
    echo "FAIL: seed_staging.py second run failed — IDEMPOTENCY REGRESSION."
    echo "The R-1.6.4 existing-row + UPDATE pattern was bypassed somewhere."
    exit 2
fi
if ! run_seed "seed_fh_demo-2"  "python -m scripts.seed_fh_demo --apply --idempotent"; then
    echo ""
    echo "FAIL: seed_fh_demo.py second run failed — IDEMPOTENCY REGRESSION."
    echo "Some _ensure_* helper lost its existing-row check, or a new"
    echo "non-idempotent code path landed without the canonical pattern."
    exit 2
fi

echo ""
echo "=== R-1.6.4 idempotency validation: PASS ==="
echo "Both seeds ran twice without error. Re-seed across deploys is safe."
