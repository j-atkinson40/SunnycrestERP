#!/usr/bin/env bash
# Run a command, capture ALL its output, and report the command's OWN exit status.
#
# ⚠️ THIS EXISTS BECAUSE THE RULE DID NOT WORK. CLAUDE.md §11 has said, in capitals
# since 2026-10-03 (635be69f), "NEVER PIPE A COMMAND WHOSE EXIT STATUS YOU INTEND TO
# READ. REDIRECT, READ THE STATUS, THEN READ THE FILE" — and the canon section it sits
# in also records that the shape has recurred at least four times, twice by authors who
# had read the entry that names it. It recurred again on 2026-10-30 while testing the
# refusal paths of a production write script: `script | tail -3; echo "exit=$?"` printed
# tail's status, so three guards that DID fire were reported as untested.
#
# ⚠️ WHAT 635be69f ADDED WAS PROSE PLUS AN EXAMPLE INCANTATION, NOT AN EXECUTABLE — its
# own title is "replace two habits with two commands", and the commands were forms to
# retype rather than things to run. CLAUDE.md's own "Removal before recognition" says a
# method that can be removed should be removed rather than guarded by a rule asking
# people not to use it. This is that removal: there is no pipe left to put between you
# and the status.
#
# USAGE
#     scripts/run_and_report.sh <logfile> <command> [args...]
#
#     scripts/run_and_report.sh /tmp/tsc.out npx tsc -b
#     scripts/run_and_report.sh /tmp/gate.out .venv/bin/python -m pytest tests/foo.py -q
#
# It prints, in this order and always:
#     EXIT=<the command's own status>
#     LINES=<how many lines of output there were>
#     then the last 20 lines
#
# ⚠️ IT PRINTS `LINES` BECAUSE A TRUNCATED READ IS THE OTHER HALF OF THE SAME DEFECT.
# CLAUDE.md: "ANY COMMAND WHOSE OUTPUT FEEDS AN ABSENCE CLAIM GETS ITS FULL LENGTH
# CHECKED BEFORE THE CLAIM IS WRITTEN." A grep over the tail of a 1,900-line log that
# reports nothing is not evidence of nothing. The full output is in <logfile>; read it
# there before claiming an absence.
#
# ⚠️ AND IT EXITS WITH THE COMMAND'S STATUS, so it composes: `scripts/run_and_report.sh
# /tmp/x.out make build && echo ok` behaves the way you meant.
set -u

if [ "$#" -lt 2 ]; then
    echo "usage: $0 <logfile> <command> [args...]" >&2
    exit 2
fi

LOG="$1"
shift

# ⚠️ TRUNCATED FIRST, DELIBERATELY. A stale log read as a fresh result is a measured
# failure in this repo: on 2026-10-30 a gate runner died before pytest started and the
# PREVIOUS run's log was still on disk, so its summary was read as the new one.
: > "$LOG"

"$@" > "$LOG" 2>&1
status=$?

echo "EXIT=${status}"
echo "LINES=$(wc -l < "$LOG" | tr -d ' ')"
echo "LOG=${LOG}"
echo "--- last 20 lines ---"
tail -20 "$LOG"

exit "${status}"
