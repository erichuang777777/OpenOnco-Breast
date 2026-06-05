#!/bin/sh
set -e

# Run Alembic migrations on every startup (idempotent)
echo "[entrypoint] Running database migrations…"
alembic upgrade head

echo "[entrypoint] Starting server…"
exec "$@"
