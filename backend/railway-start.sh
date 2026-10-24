#!/bin/bash
#
# The service container's CMD. It starts the server and does nothing else.
#
# ⚠️ EVERYTHING THAT USED TO BE HERE IS NOW IN `railway-prep.sh`, WHICH RAILWAY RUNS
# AS `preDeployCommand` (see railway.toml). This file was 195 lines of migrations and
# seeding, and the port was not bound until all of it had finished — measured at
# 537-552 s on 2026-10-23, which was a hard outage of at least 329 s per deploy before
# the healthcheck and an invisible nine-minute lag after it.
#
# ⚠️ KEEP IT THIS SMALL. The next person to need "just one thing before the server
# starts" is the reason the old file grew to 195 lines, and every line of it delayed
# the first request. Boot work goes in `railway-prep.sh`, where it delays the DEPLOY
# instead of the SERVER and where a failure fails the deploy loudly.
#
# ⚠️ AND IF PREP DID NOT RUN, THIS STILL STARTS. Railway will not start the service
# container when `preDeployCommand` fails, so that case cannot arise through the
# supported path — but a `railway.toml` that lost the key, or a service whose
# config-file path was changed in the dashboard, would silently serve without
# migrating. The deployment object echoes what it read from the file, so that is
# checkable without reading logs:
#
#     railway deployment list --service SunnycrestERP --environment production --json
#     -> meta.serviceManifest.deploy.preDeployCommand   must be the prep command
#     -> meta.propertyFileMapping                       must list it as file-sourced
#
# That check is asserted by tests/test_deploy_config.py so it cannot quietly lapse.

set -u

echo "=== Railway start: serving ==="
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
