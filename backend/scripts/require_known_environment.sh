#!/bin/bash
# Resolve ENVIRONMENT, or REFUSE. Prints the value on stdout; exits 1 unset.
#
# ⚠️ ABSENCE MUST MEAN REFUSE, AND IT USED TO MEAN "dev". The staging-seed
# block in railway-start.sh tested `[ "${ENVIRONMENT:-dev}" != "production" ]`,
# so a deploy where the variable was simply MISSING inferred `dev` and ran the
# demo seeds. On the production service that writes demo tenants into the
# production database.
#
# The fingerprint: the production guard was committed 2026-05-06 18:19:29 UTC
# and the `hopkins-fh` tenant row was created on production at 18:20:42 UTC —
# 73 seconds later, by the very deploy that shipped the guard. `st-marys`
# followed the same evening. Both predate nothing; they were created THROUGH a
# guard that was present in the file and open because the variable was not set.
#
# A guard whose safe state depends on a variable being present is not a guard.
# This refuses instead, and the refusal is loud: an operator sets one Railway
# variable, which is cheap, and the alternative is silent writes to a database
# nobody has identified.
#
# Deliberately does NOT accept a default argument. Every caller wants the same
# answer — "tell me where I am, or stop" — and an overridable default would
# reintroduce exactly the hole this closes.
set -u

if [ -z "${ENVIRONMENT:-}" ]; then
    cat >&2 <<'MSG'
✗ ENVIRONMENT is not set — refusing to guess.

  Scripts gated on this variable decide whether to write demo tenants into
  the database they are pointed at. Unset used to be read as "dev", which is
  how demo tenants reached production. Absence now refuses.

  Set it explicitly: ENVIRONMENT=dev | staging | production
MSG
    exit 1
fi

printf '%s\n' "$ENVIRONMENT"
