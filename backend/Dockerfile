# Production image for the ESF Enterprise Platform.
# Build context = ./backend (see docker-compose.prod.yml).
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# WeasyPrint runtime native libraries (pango/cairo/gdk-pixbuf) + curl for healthcheck.
# DejaVu Sans is bundled in app/static/fonts, but fonts-dejavu-core helps fontconfig too.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 libcairo2 \
        libgdk-pixbuf-2.0-0 libffi8 shared-mime-info fonts-dejavu-core curl tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Deterministic dependencies first (better layer caching). No dev/test deps.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code
COPY . /app

# Non-root user; storage must be writable (generated QR PNGs)
RUN useradd --system --uid 10001 appuser \
    && mkdir -p /app/storage/qr \
    && chown -R appuser:appuser /app/storage \
    && chmod +x docker-entrypoint.sh

USER appuser
EXPOSE 8000

# Container-level liveness (compose adds a richer /readyz DB-connectivity probe).
# curl is installed above; the root health route always returns 200.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://localhost:8000/ || exit 1

# Runs migrations, then starts the production server (no reload, no debug).
ENTRYPOINT ["./docker-entrypoint.sh"]
