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

# Perf pass (2026-07) — THE SEED MANIFEST: declared tiers per seed
# (local-only / manual), each with a one-line justification. The manifest
# is asked once per boot; every skip is logged WITH its reason — a
# skipped seed is visible in the boot log, never silently absent.
# See scripts/seed_manifest.py for the tier semantics.
MANIFEST_SKIPS=""
if [ -f "${SEEDS_DIR}/seed_manifest.py" ]; then
    MANIFEST_SKIPS=$(cd "${BACKEND_DIR}" && "${PYTHON_BIN}" -m scripts.seed_manifest --skips 2>/dev/null)
fi

_manifest_skip_reason() {
    # Prints "tier<TAB>why" when the seed is manifest-skipped; rc 1 otherwise.
    local name="$1"
    [ -z "${MANIFEST_SKIPS}" ] && return 1
    local line
    line=$(printf '%s\n' "${MANIFEST_SKIPS}" | awk -F'\t' -v n="${name}" '$1 == n {print $2 "\t" $3; exit}')
    [ -z "${line}" ] && return 1
    printf '%s' "${line}"
    return 0
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

    if [ "${seed_name}" = "seed_manifest" ]; then
        continue  # the manifest itself is not a seed
    fi
    manifest_reason=$(_manifest_skip_reason "${seed_name}")
    if [ $? -eq 0 ] && [ -n "${manifest_reason}" ]; then
        tier="${manifest_reason%%$'\t'*}"
        why="${manifest_reason#*$'\t'}"
        echo "[seed-runner] Skip: ${seed_name} (tier ${tier} — ${why})"
        skipped=$((skipped + 1))
        continue
    fi

    attempted=$((attempted + 1))
    echo "[seed-runner] Running seed: ${seed_name}"

    # Run from backend/ so `python -m scripts.<name>` resolves the
    # scripts package consistently with the explicit invocations in
    # railway-start.sh.
    seed_start=$(date +%s)
    (cd "${BACKEND_DIR}" && "${PYTHON_BIN}" -m "scripts.${seed_name}")
    rc=$?
    seed_secs=$(( $(date +%s) - seed_start ))

    # Perf pass (2026-07): the PERMANENT per-seed timing — one line per
    # seed in every boot log, so any future sweep regression is
    # diagnosable from the log alone (grep '\[seed-timing\]').
    if [ ${rc} -eq 0 ]; then
        echo "[seed-timing] ${seed_name}: ${seed_secs}s (ok)"
        echo "[seed-runner] Completed: ${seed_name} (success)"
        succeeded=$((succeeded + 1))
    elif [ ${rc} -eq 3 ]; then
        # Exit 3 = the seed's own DECLARED skip (tier-scoped or
        # prereq-absent — the reason is in the seed's own output).
        # Counted separately: a skip is never a failure and never
        # inflates the warn tally.
        echo "[seed-timing] ${seed_name}: ${seed_secs}s (skipped by seed)"
        echo "[seed-runner] Skipped by seed: ${seed_name} (declared skip, exit 3)"
        skipped=$((skipped + 1))
    else
        echo "[seed-timing] ${seed_name}: ${seed_secs}s (FAILED rc=${rc})"
        echo "[seed-runner] WARN: ${seed_name} failed with exit code ${rc} — continuing"
        failed=$((failed + 1))
    fi
done

echo "[seed-runner] Done. ${attempted} seeds attempted, ${succeeded} succeeded, ${failed} failed, ${skipped} skipped."

# Always exit 0 — seed failures are non-fatal (locked decision 2).
exit 0
