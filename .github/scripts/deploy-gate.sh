#!/usr/bin/env bash
#
# CI deploy-gate — block until staging GENUINELY serves the pushed commit on
# BOTH the backend AND (optionally) the frontend, each a separate Railway
# service that can deploy, lag, or fail to build independently.
#
# Why this exists (witnessed failures this arc):
#   1. FALSE RED / FALSE GREEN from a stale frontend. The old gate polled only
#      the backend /api/health commit. A frontend that LAGGED or FAILED TO
#      BUILD was invisible — CI ran the frontend e2e against a stale bundle.
#      A build-break (an unused import failing `tsc -b`) left the frontend on
#      the prior bundle for two pushes while the gate waved everything through.
#      Fix: poll the frontend's build-stamped /version.json too; require it to
#      match. version.json is emitted only by a successful `vite build` (see
#      vite.config.ts emit-version-json), so a failed build leaves it stale and
#      this gate fails LOUDLY instead of testing the wrong bundle.
#   2. 502-AT-LOGIN false reds. The backend takes >5 min to stabilize after a
#      deploy; a single commit-match could catch it mid-flap (up → 502 → up).
#      Fix: require N CONSECUTIVE healthy matches before proceeding (--settle).
#
# Discipline: FAIL-CLOSED. If a surface never reaches the SHA, time out LOUDLY
# with a surface-specific message — never proceed against a not-ready service.
# (The old "commit is null → proceed anyway after 5 min" bootstrap fallback was
# the thing that ran tests against a broken backend; it is intentionally gone.)
#
# Usage:
#   deploy-gate.sh --sha <full-sha> --backend <url> [--frontend <url>] \
#                  [--settle N] [--timeout SEC] [--interval SEC]
set -euo pipefail

SHA="" BACKEND="" FRONTEND="" SETTLE=2 TIMEOUT=900 INTERVAL=15
while [ $# -gt 0 ]; do
  case "$1" in
    --sha) SHA="$2"; shift 2 ;;
    --backend) BACKEND="$2"; shift 2 ;;
    --frontend) FRONTEND="$2"; shift 2 ;;
    --settle) SETTLE="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    *) echo "deploy-gate: unknown arg: $1" >&2; exit 2 ;;
  esac
done
if [ -z "$SHA" ] || [ -z "$BACKEND" ]; then
  echo "usage: deploy-gate.sh --sha <sha> --backend <url> [--frontend <url>] [--settle N] [--timeout SEC]" >&2
  exit 2
fi

short() { echo "${1:0:7}"; }

# Each reader echoes the served commit, or "null" on any failure (down, 502,
# missing field, non-JSON) — all of which correctly read as "not the SHA".
backend_commit() {
  curl -s -m 8 "${BACKEND}/api/health" 2>/dev/null \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('commit') or 'null')" 2>/dev/null \
    || echo "null"
}
frontend_commit() {
  curl -s -m 8 "${FRONTEND}/version.json" 2>/dev/null \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('commit') or 'null')" 2>/dev/null \
    || echo "null"
}

surfaces="backend"
[ -n "$FRONTEND" ] && surfaces="backend + frontend"
echo "Deploy gate: waiting for staging to stably serve $(short "$SHA") (${surfaces}; ${SETTLE} consecutive healthy; ${TIMEOUT}s budget)."

deadline=$(( $(date +%s) + TIMEOUT ))
consecutive=0
last_be="?" last_fe="?"

while true; do
  be="$(backend_commit)"; last_be="$be"
  be_ok=0; [ "$be" = "$SHA" ] && be_ok=1
  fe_ok=1
  if [ -n "$FRONTEND" ]; then
    fe="$(frontend_commit)"; last_fe="$fe"
    fe_ok=0; [ "$fe" = "$SHA" ] && fe_ok=1
  fi

  if [ "$be_ok" = 1 ] && [ "$fe_ok" = 1 ]; then
    consecutive=$(( consecutive + 1 ))
    echo "  → both serve $(short "$SHA") (${consecutive}/${SETTLE} consecutive healthy)"
    if [ "$consecutive" -ge "$SETTLE" ]; then
      echo "Deploy gate PASSED — staging stably serving $(short "$SHA")."
      exit 0
    fi
  else
    consecutive=0
    fe_disp="n/a"; [ -n "$FRONTEND" ] && fe_disp="$(short "$last_fe")"
    echo "  → not ready: backend=$(short "$last_be") frontend=${fe_disp} (target $(short "$SHA"))"
  fi

  if [ "$(date +%s)" -ge "$deadline" ]; then
    echo "::error::Deploy gate TIMEOUT after ${TIMEOUT}s — staging did not stably serve $(short "$SHA"). Tests were NOT run; this is a DEPLOY problem, not a test failure." >&2
    if [ "$be_ok" != 1 ]; then
      echo "::error::BACKEND never reached $(short "$SHA") (last /api/health commit: $(short "$last_be")). The backend service did not deploy or never stabilized." >&2
    fi
    if [ -n "$FRONTEND" ] && [ "$fe_ok" != 1 ]; then
      echo "::error::FRONTEND never reached $(short "$SHA") (last /version.json commit: $(short "$last_fe")). The frontend bundle did not deploy — its build FAILED or LAGGED. The gate refused to run e2e against a stale bundle." >&2
    fi
    exit 1
  fi
  sleep "$INTERVAL"
done
