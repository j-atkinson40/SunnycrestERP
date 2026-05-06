#!/bin/bash

echo "=== Railway Startup ==="
echo "Current alembic revision:"
alembic current 2>&1 || echo "(could not read current revision)"

echo ""
echo "Running database migrations..."
if alembic upgrade head 2>&1; then
    echo "Migrations completed successfully."
else
    echo "WARNING: Migration failed — server will start anyway."
    echo "Check migration errors and resolve manually."
fi

echo ""
echo "Post-migration alembic revision:"
alembic current 2>&1 || echo "(could not read revision)"

# R-1.6 — Auto-seed staging tenants after migrations.
#
# Both seed scripts are idempotent (safe to re-run on every deploy):
#   - seed_staging.py creates the testco tenant + 4 demo users +
#     products + orders + invoices + KB. Re-runs clean + re-seed for
#     end-state consistency. Skipped in production (ENVIRONMENT guard).
#   - seed_fh_demo.py --idempotent creates Hopkins FH (slug "hopkins-fh")
#     + St. Mary's Cemetery (slug "st-marys") + the demo case
#     FC-2026-0001. Ensure-or-skip semantics — never deletes existing
#     data. Skipped in production (ENVIRONMENT guard inside the script).
#
# Both scripts self-skip in production via the ENVIRONMENT=production
# guard. Staging has ENVIRONMENT=dev (per /api/health output). Production
# Railway env should set ENVIRONMENT=production explicitly.
#
# Failures in either seed log a warning but do NOT block server start.
# The platform must come up even if seed scripting hits a transient
# issue (the auth endpoint must answer for incident reporting).
if [ "${ENVIRONMENT:-dev}" != "production" ]; then
    echo ""
    echo "Running staging seed scripts (R-1.6 — auto-seed on every deploy)..."

    if python -m scripts.seed_staging --idempotent 2>&1; then
        echo "  ✓ seed_staging.py completed."
    else
        echo "  ⚠ seed_staging.py failed (non-blocking; server will start)."
    fi

    if python -m scripts.seed_fh_demo --apply --idempotent 2>&1; then
        echo "  ✓ seed_fh_demo.py completed."
    else
        echo "  ⚠ seed_fh_demo.py failed (non-blocking; server will start)."
    fi
else
    echo ""
    echo "ENVIRONMENT=production — skipping staging seed scripts."
fi

echo ""
echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
