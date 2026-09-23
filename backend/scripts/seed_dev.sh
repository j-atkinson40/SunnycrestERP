#!/usr/bin/env bash
#
# THE answer to "how do I get a working local dev database".
#
# ⚠️ WHY THIS EXISTS. The canonical seed sequence already existed — it is
# `run_canonical_seeds.sh`, which discovers every `seed_*.py` and runs it
# alphabetically. But its locked decision #5 reads "Local dev unaffected
# (this runs from railway-start.sh only)", and CLAUDE.md §7 named only
# `seed_staging` and `seed_fh_demo` for local work. So the complete
# sequence was written down, and nowhere that a person setting up a local
# database would look.
#
# On 2026-09-23 that gap cost a dropped database: three seeds were run,
# they succeeded, and the result was missing the Intelligence prompt
# catalogue that 47 tests require. `ls scripts/seed_*.py` returns 65.
#
# ORDER, and why it is not simply alphabetical:
#   1. alembic upgrade head      — schema, and it SEEDS DATA too (the
#                                  `default` company is created by
#                                  a2f3b4c5d6e7_add_multi_tenancy).
#   2. the fail-loud seeds       — the four `railway-start.sh` runs with
#                                  deploy-aborting discipline, in its order.
#                                  `run_canonical_seeds.sh` skips these by
#                                  name to avoid double-execution.
#   3. run_canonical_seeds.sh    — everything else, alphabetically, minus
#                                  the `manual` tier declared in
#                                  `seed_manifest.py`.
#
# ⚠️ CREDENTIALS. `seed_sunnycrest.py` generates and PRINTS a temp admin
# password when it must create the admin user on a genuinely fresh
# database. This script therefore writes all seed output to a log file and
# prints only a summary. Read the log yourself; do not paste it anywhere.
# An agent running this must not surface the log's contents.
#
# Idempotent: safe to re-run. Refuses anything that is not a local database.
set -uo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${BACKEND_DIR}"

: "${DATABASE_URL:=postgresql://localhost:5432/bridgeable_dev}"
export DATABASE_URL

# ⚠️ REFUSE ANYTHING REMOTE. This script drops nothing, but it writes demo
# data; a DATABASE_URL pointing at Railway would seed a real environment.
case "${DATABASE_URL}" in
  *localhost*|*127.0.0.1*) ;;
  *) echo "[seed-dev] REFUSING: DATABASE_URL is not local: ${DATABASE_URL%%\?*}" >&2
     exit 1 ;;
esac
if [ "${ENVIRONMENT:-dev}" = "production" ]; then
  echo "[seed-dev] REFUSING: ENVIRONMENT=production" >&2
  exit 1
fi

LOG="${SEED_DEV_LOG:-${HOME}/bridgeable-seed-dev-$(date +%Y%m%d-%H%M%S).log}"
echo "[seed-dev] target : ${DATABASE_URL}"
echo "[seed-dev] log    : ${LOG}   (may contain a generated password — do not paste)"

# ⚠️ PREFER THE REPO'S VENV, do not trust whatever `python` is on PATH.
# Measured 2026-09-23: run without the venv active, `command -v python` found
# a system interpreter and THIRTEEN seeds died on `ModuleNotFoundError: No
# module named 'sqlalchemy'` — each logged as a WARN and skipped, the runner
# still exiting 0. Removing that failure mode is most of this script's value.
if [ -x "${BACKEND_DIR}/.venv/bin/python" ]; then
    PY="${BACKEND_DIR}/.venv/bin/python"
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    PY=python3
fi
if ! "$PY" -c "import sqlalchemy, alembic" >/dev/null 2>&1; then
    echo "[seed-dev] REFUSING: ${PY} cannot import sqlalchemy/alembic." >&2
    echo "[seed-dev] Activate the venv, or run from a checkout with backend/.venv." >&2
    exit 1
fi
echo "[seed-dev] python : ${PY}"
# The canonical runner resolves its own interpreter the same fragile way, so
# hand it ours on PATH rather than letting it re-guess.
export PATH="$(dirname "$PY"):${PATH}"

{
  echo "=== alembic upgrade head ==="
  alembic upgrade head
  echo "=== fail-loud seeds (railway-start.sh order) ==="
  "$PY" -m scripts.seed_staging --idempotent
  "$PY" -m scripts.seed_fh_demo --apply --idempotent
  "$PY" -m scripts.seed_dispatch_demo
  "$PY" -m scripts.seed_edge_panel_inheritance
  echo "=== canonical runner (everything else, minus the manual tier) ==="
  env -u RAILWAY_GIT_COMMIT_SHA bash scripts/run_canonical_seeds.sh
} >"${LOG}" 2>&1
rc=$?

# ⚠️ Verify by the STATE PRODUCED, not by exit codes: `$?` after a pipeline
# is the last command's, and the canonical runner exits 0 by design even
# when individual seeds fail.
echo "[seed-dev] --- verification (state, not exit codes) ---"
"$PY" - <<'PYEOF'
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ["DATABASE_URL"])
want = {"companies": 5, "intelligence_prompts": 50}
with e.connect() as c:
    head = c.execute(text("SELECT version_num FROM alembic_version")).scalar()
    print(f"  migration head      {head}")
    ok = True
    for t, floor in want.items():
        n = c.execute(text(f"SELECT count(*) FROM {t}")).scalar()
        flag = "ok" if n >= floor else "TOO LOW"
        if n < floor: ok = False
        print(f"  {t:20}{n:>6}   (expect >= {floor})  {flag}")
    print("  RESULT:", "usable" if ok else "INCOMPLETE — read the log")
PYEOF

echo "[seed-dev] canonical runner summary:"
grep -E "^\[seed-runner\] Done" "${LOG}" | sed 's/^/  /'
grep -E "^\[seed-runner\] WARN" "${LOG}" | sed 's/^/  /'
echo "[seed-dev] done (runner rc=${rc}); full output in ${LOG}"
