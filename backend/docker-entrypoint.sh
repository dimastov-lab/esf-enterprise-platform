#!/bin/sh
# Production entrypoint: apply DB migrations, then start the app (no reload, no debug).
set -e

echo "[entrypoint] applying database migrations (alembic upgrade head)..."
n=0
until alembic upgrade head; do
  n=$((n + 1))
  if [ "$n" -ge 10 ]; then
    echo "[entrypoint] migrations failed after $n attempts" >&2
    exit 1
  fi
  echo "[entrypoint] database not ready yet, retry $n/10 in 3s..."
  sleep 3
done
echo "[entrypoint] migrations OK."

echo "[entrypoint] starting uvicorn on :8000 (workers=${WEB_CONCURRENCY:-2})..."
exec uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers --forwarded-allow-ips='*' \
  --no-server-header
