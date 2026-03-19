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

echo ""
echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
