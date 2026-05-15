#!/usr/bin/env bash
#
# Sub-arc D-1 — shell test for run_canonical_seeds.sh.
#
# Verifies the canonical-seeds runner against synthetic mock seed scripts:
#   1. Discovers all seed_*.py in SEEDS_DIR alphabetically.
#   2. Runs each via `python -m scripts.<name>` (with SEEDS_DIR=tempdir
#      treated as a `scripts` package).
#   3. Logs success/failure per seed.
#   4. Exit code 0 even when one seed fails (non-fatal — locked decision 2).
#   5. SKIP_SEEDS list bypasses listed seeds without execution.
#
# Run from repo root:
#   bash backend/tests/test_canonical_seeds_runner.sh

set -e  # tests themselves fail loud
set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNNER="${REPO_ROOT}/backend/scripts/run_canonical_seeds.sh"

if [ ! -x "${RUNNER}" ]; then
    echo "FAIL: runner not executable at ${RUNNER}"
    exit 1
fi

# Build temp scripts package
TMPDIR=$(mktemp -d)
trap 'rm -rf "${TMPDIR}"' EXIT

mkdir -p "${TMPDIR}/scripts"
touch "${TMPDIR}/scripts/__init__.py"

cat > "${TMPDIR}/scripts/seed_aaa.py" <<'EOF'
print("ran seed_aaa")
EOF

cat > "${TMPDIR}/scripts/seed_bbb.py" <<'EOF'
print("ran seed_bbb")
EOF

cat > "${TMPDIR}/scripts/seed_ccc_broken.py" <<'EOF'
import sys
print("seed_ccc_broken: raising")
sys.exit(2)
EOF

cat > "${TMPDIR}/scripts/seed_ddd.py" <<'EOF'
print("ran seed_ddd")
EOF

# --- Test 1: full run with one failing seed ---
echo "=== Test 1: discover, run alphabetical, non-fatal on failure ==="

OUTPUT=$(SEEDS_DIR="${TMPDIR}/scripts" BACKEND_DIR="${TMPDIR}" bash "${RUNNER}" 2>&1)
RC=$?

if [ ${RC} -ne 0 ]; then
    echo "FAIL: runner exit code ${RC} (want 0 — failures must be non-fatal)"
    echo "${OUTPUT}"
    exit 1
fi

# Alphabetical ordering: aaa < bbb < ccc_broken < ddd
if ! echo "${OUTPUT}" | grep -q "Running seed: seed_aaa"; then
    echo "FAIL: seed_aaa not run"; echo "${OUTPUT}"; exit 1
fi
if ! echo "${OUTPUT}" | grep -q "Running seed: seed_bbb"; then
    echo "FAIL: seed_bbb not run"; echo "${OUTPUT}"; exit 1
fi
if ! echo "${OUTPUT}" | grep -q "Running seed: seed_ccc_broken"; then
    echo "FAIL: seed_ccc_broken not run"; echo "${OUTPUT}"; exit 1
fi
if ! echo "${OUTPUT}" | grep -q "Running seed: seed_ddd"; then
    echo "FAIL: seed_ddd not run (failure earlier broke the loop)"; echo "${OUTPUT}"; exit 1
fi

# Verify alphabetical order by line-position
LINE_AAA=$(echo "${OUTPUT}" | grep -n "Running seed: seed_aaa" | head -1 | cut -d: -f1)
LINE_BBB=$(echo "${OUTPUT}" | grep -n "Running seed: seed_bbb" | head -1 | cut -d: -f1)
LINE_CCC=$(echo "${OUTPUT}" | grep -n "Running seed: seed_ccc_broken" | head -1 | cut -d: -f1)
LINE_DDD=$(echo "${OUTPUT}" | grep -n "Running seed: seed_ddd" | head -1 | cut -d: -f1)

if ! [ "${LINE_AAA}" -lt "${LINE_BBB}" ] || ! [ "${LINE_BBB}" -lt "${LINE_CCC}" ] || ! [ "${LINE_CCC}" -lt "${LINE_DDD}" ]; then
    echo "FAIL: not alphabetical (aaa=${LINE_AAA} bbb=${LINE_BBB} ccc=${LINE_CCC} ddd=${LINE_DDD})"
    echo "${OUTPUT}"
    exit 1
fi

# Verify failure warning logged
if ! echo "${OUTPUT}" | grep -q "WARN: seed_ccc_broken failed with exit code 2"; then
    echo "FAIL: missing failure warning for seed_ccc_broken"
    echo "${OUTPUT}"
    exit 1
fi

# Verify summary
if ! echo "${OUTPUT}" | grep -qE "3 succeeded, 1 failed"; then
    echo "FAIL: summary mismatch"
    echo "${OUTPUT}"
    exit 1
fi

echo "  ok — discover + alphabetical + non-fatal failure + summary"

# --- Test 2: empty seeds dir ---
echo "=== Test 2: empty SEEDS_DIR ==="

EMPTY_DIR=$(mktemp -d)
trap 'rm -rf "${TMPDIR}" "${EMPTY_DIR}"' EXIT
mkdir -p "${EMPTY_DIR}/scripts"
touch "${EMPTY_DIR}/scripts/__init__.py"

OUTPUT2=$(SEEDS_DIR="${EMPTY_DIR}/scripts" BACKEND_DIR="${EMPTY_DIR}" bash "${RUNNER}" 2>&1)
RC2=$?

if [ ${RC2} -ne 0 ]; then
    echo "FAIL: empty dir runner exit ${RC2} (want 0)"
    echo "${OUTPUT2}"
    exit 1
fi
if ! echo "${OUTPUT2}" | grep -qE "0 seeds attempted"; then
    echo "FAIL: empty dir summary mismatch"
    echo "${OUTPUT2}"
    exit 1
fi
echo "  ok — empty dir no-op"

# --- Test 3: SKIP_SEEDS list bypass ---
# The runner's SKIP_SEEDS bypasses seeds already invoked upstream with
# fail-loud discipline. The list is hardcoded in the runner (locked
# decision — explicit upstream invocations should not double-run).
echo "=== Test 3: SKIP_SEEDS bypasses upstream-invoked seeds ==="

SKIP_DIR=$(mktemp -d)
trap 'rm -rf "${TMPDIR}" "${EMPTY_DIR}" "${SKIP_DIR}"' EXIT
mkdir -p "${SKIP_DIR}/scripts"
touch "${SKIP_DIR}/scripts/__init__.py"

# Create one seed matching a SKIP_SEEDS entry + one that doesn't.
cat > "${SKIP_DIR}/scripts/seed_staging.py" <<'EOF'
print("seed_staging should NOT run from canonical runner")
EOF
cat > "${SKIP_DIR}/scripts/seed_xxx.py" <<'EOF'
print("ran seed_xxx")
EOF

OUTPUT3=$(SEEDS_DIR="${SKIP_DIR}/scripts" BACKEND_DIR="${SKIP_DIR}" bash "${RUNNER}" 2>&1)
RC3=$?

if [ ${RC3} -ne 0 ]; then
    echo "FAIL: skip-test runner exit ${RC3}"
    echo "${OUTPUT3}"
    exit 1
fi
if ! echo "${OUTPUT3}" | grep -q "Skip: seed_staging"; then
    echo "FAIL: seed_staging not skipped"
    echo "${OUTPUT3}"
    exit 1
fi
if ! echo "${OUTPUT3}" | grep -q "Running seed: seed_xxx"; then
    echo "FAIL: seed_xxx not run (non-skipped)"
    echo "${OUTPUT3}"
    exit 1
fi
if ! echo "${OUTPUT3}" | grep -qE "1 skipped"; then
    echo "FAIL: skipped count missing"
    echo "${OUTPUT3}"
    exit 1
fi
echo "  ok — SKIP_SEEDS list honored"

echo ""
echo "=== All canonical-seeds-runner tests passed ==="
