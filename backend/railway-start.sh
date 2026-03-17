#!/bin/bash

echo "Running database migrations..."
if alembic upgrade head; then
    echo "Migrations completed successfully."
else
    echo "WARNING: Migration failed — server will start anyway."
    echo "Check migration errors and resolve manually."
fi

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
