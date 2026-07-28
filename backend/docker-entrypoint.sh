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

# Trust X-Forwarded-* only from the private network the bundled nginx sits on, NOT
# from every peer ('*'). uvicorn 0.34 accepts CIDR networks, so a client connecting
# directly (public IP) can no longer spoof X-Forwarded-For to forge audit IPs or
# bypass the per-IP login limiter. Override FORWARDED_ALLOW_IPS to your proxy's exact
# subnet for a tighter bound (I-5).
: "${FORWARDED_ALLOW_IPS:=127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16}"

echo "[entrypoint] starting uvicorn on :8000 (workers=${WEB_CONCURRENCY:-2})..."
exec uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers --forwarded-allow-ips="${FORWARDED_ALLOW_IPS}" \
  --no-server-header
