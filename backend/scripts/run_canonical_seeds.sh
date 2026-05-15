#!/usr/bin/env bash
#
# Canonical platform seed runner (sub-arc D-1).
#
# Discovers and runs all `seed_*.py` scripts in `backend/scripts/`
# alphabetically. Non-fatal: a seed that fails logs a warning and the
# next seed runs anyway; the runner always exits 0. The application
# starts even if some seeds partially failed — partial state + idempotent
# re-run on the next deploy is preferred over deploy-lockout.
#
# Invoked from `railway-start.sh` after `alembic upgrade head` and
# before the application starts.
#
# Seed scripts ARE expected to be:
#   - Idempotent (slug-lookup short-circuit or equivalent — re-runs
#     no-op when the canonical row already exists).
#   - Self-guarded for production where they ship demo data
#     (ENVIRONMENT=production refusal inside the script).
#   - Invokable via `python -m scripts.<name>` from `backend/` cwd.
#
# Seeds already invoked with FAIL-LOUD discipline by `railway-start.sh`
# (per R-1.6.3) are skipped here via SKIP_SEEDS to avoid double-execution
# and preserve their fail-the-deploy contract. New canonical seeds added
# in future arcs land here automatically by naming convention.
#
# v1 observability: stdout/stderr captured by Railway logs. No separate
# dashboard, no admin UI, no report files. Per-script logging is the
# substrate.
#
# Locked decisions (sub-arc D-1):
#   1. All seed_*.py in backend/scripts/ are canonical (naming-based).
#   2. Failures non-fatal — warn + continue + exit 0.
#   3. Alphabetical execution; no explicit dependency declarations.
#   4. Logging via stdout/stderr to Railway logs.
#   5. Local dev unaffected (this runs from railway-start.sh only).

set +e  # explicitly NOT set -e: seed failures must not abort the loop.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEEDS_DIR="${SEEDS_DIR:-${SCRIPT_DIR}}"
# BACKEND_DIR is the cwd from which `python -m scripts.<name>` resolves
# the `scripts` package. Defaults to parent of SCRIPT_DIR (matching
# repo layout); overridable for tests that synthesize a temp scripts/
# package.
BACKEND_DIR="${BACKEND_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"

# Resolve python invocation: Railway containers expose `python`;
# macOS/dev environments may only have `python3`. Match railway-start.sh
# convention by preferring `python` when available.
if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    echo "[seed-runner] ERROR: neither python nor python3 on PATH — skipping all seeds."
    echo "[seed-runner] Done. 0 seeds attempted, 0 succeeded, 0 failed, 0 skipped."
    exit 0
fi

# Seeds already invoked with fail-loud discipline upstream in
# railway-start.sh. Skip here to avoid double-execution. If you remove
# an entry from railway-start.sh, also remove it here so the canonical
# runner picks it up.
SKIP_SEEDS=(
    "seed_staging"
    "seed_fh_demo"
    "seed_dispatch_demo"
    "seed_edge_panel_inheritance"
)

_is_skipped() {
    local name="$1"
    for s in "${SKIP_SEEDS[@]}"; do
        if [ "${name}" = "${s}" ]; then
            return 0
        fi
    done
    return 1
}

attempted=0
succeeded=0
failed=0
skipped=0

echo "[seed-runner] Discovering canonical seeds in ${SEEDS_DIR}..."

# Discover + iterate seed paths safely under directory names that
# contain spaces. `find -print0 | sort -z` is space-safe; `while read`
# with -d '' parses null-delimited entries. The naive
# `for f in $(ls ...)` form word-splits on whitespace and breaks under
# paths like "/My Drive/Claude Code/...".
SEED_PATHS=()
while IFS= read -r -d '' p; do
    SEED_PATHS+=("$p")
done < <(find "${SEEDS_DIR}" -maxdepth 1 -name 'seed_*.py' -type f -print0 2>/dev/null | sort -z)

for seed_path in "${SEED_PATHS[@]}"; do
    seed_name=$(basename "${seed_path}" .py)

    if _is_skipped "${seed_name}"; then
        echo "[seed-runner] Skip: ${seed_name} (invoked upstream with fail-loud)"
        skipped=$((skipped + 1))
        continue
    fi

    attempted=$((attempted + 1))
    echo "[seed-runner] Running seed: ${seed_name}"

    # Run from backend/ so `python -m scripts.<name>` resolves the
    # scripts package consistently with the explicit invocations in
    # railway-start.sh.
    (cd "${BACKEND_DIR}" && "${PYTHON_BIN}" -m "scripts.${seed_name}")
    rc=$?

    if [ ${rc} -eq 0 ]; then
        echo "[seed-runner] Completed: ${seed_name} (success)"
        succeeded=$((succeeded + 1))
    else
        echo "[seed-runner] WARN: ${seed_name} failed with exit code ${rc} — continuing"
        failed=$((failed + 1))
    fi
done

echo "[seed-runner] Done. ${attempted} seeds attempted, ${succeeded} succeeded, ${failed} failed, ${skipped} skipped."

# Always exit 0 — seed failures are non-fatal (locked decision 2).
exit 0
