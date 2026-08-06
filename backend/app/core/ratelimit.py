"""Rate limiting with a pluggable store (anti-brute-force + public-route throttle).

Two independent bucket families, both keyed by client IP:
- login lockout: a fixed window of FAILED attempts triggers a temporary lockout;
- public throttle: a fixed window of ALL requests to the open verification
  routes (`/esf/check-esf`, `/qr/*.png`) caps scraping/enumeration (TD-013).

Store backends (RATE_LIMIT_BACKEND, default by environment):
- ``memory``   — per-process dict; development/tests only.
- ``postgres`` — shared fixed-window counters in the ``rate_limits`` table,
  incremented atomically (INSERT .. ON CONFLICT .. RETURNING), so limits hold
  across uvicorn workers and app replicas and survive restarts. Production
  default — the in-process store would multiply every limit by the worker count.

Counting is fixed-window (window boundary at epoch-multiples of the window
length): marginally more permissive around a boundary than the previous sliding
window, but atomically enforceable in one statement with no unbounded state.
"""
import time

from app.core.config import settings

WINDOW_SECONDS = 300
MAX_FAILURES = 5

PUBLIC_WINDOW_SECONDS = 60
PUBLIC_MAX_REQUESTS = 30

API_WINDOW_SECONDS = 60
API_MAX_REQUESTS = 20

# Bucket-name prefixes keep the limiter families from colliding on one IP.
_LOGIN_PREFIX = "login:"
_PUBLIC_PREFIX = "public:"
_API_PREFIX = "api:"


def _bucket(prefix: str, key: str) -> str:
    # Postgres string literals cannot contain NUL; the login key uses "\x00" as
    # an (ip, username) separator. Map it to the unit-separator control char,
    # which is equally unambiguous and storable.
    return prefix + key.replace("\x00", "\x1f")


def _window_start(now: float, window_seconds: int) -> int:
    return int(now) - int(now) % window_seconds


class MemoryStore:
    """Per-process fixed-window counters. Not shared — dev/tests only."""

    def __init__(self) -> None:
        self._buckets: dict = {}  # bucket -> (window_start, count)

    def incr(self, bucket: str, window_seconds: int) -> int:
        ws = _window_start(time.time(), window_seconds)
        cur_ws, count = self._buckets.get(bucket, (ws, 0))
        if cur_ws != ws:
            count = 0
        count += 1
        self._buckets[bucket] = (ws, count)
        return count

    def count(self, bucket: str, window_seconds: int) -> int:
        ws = _window_start(time.time(), window_seconds)
        cur_ws, count = self._buckets.get(bucket, (ws, 0))
        return count if cur_ws == ws else 0

    def reset(self, bucket: str) -> None:
        self._buckets.pop(bucket, None)

    def clear_all(self) -> None:
        self._buckets.clear()


class PostgresStore:
    """Shared fixed-window counters in the ``rate_limits`` table.

    Uses short independent connections from the app engine pool (never the
    request's transactional session — counts must commit even when the request
    rolls back). DB errors propagate: every guarded route needs the database
    anyway, so failing closed here does not reduce availability.
    """

    def incr(self, bucket: str, window_seconds: int) -> int:
        from sqlalchemy import text

        from app.db.session import engine

        ws = _window_start(time.time(), window_seconds)
        with engine.begin() as conn:
            count = conn.execute(
                text(
                    "INSERT INTO rate_limits (bucket, window_start, count) "
                    "VALUES (:b, :w, 1) "
                    "ON CONFLICT (bucket, window_start) "
                    "DO UPDATE SET count = rate_limits.count + 1 "
                    "RETURNING count"
                ),
                {"b": bucket, "w": ws},
            ).scalar_one()
            # Expired windows for this bucket are garbage — drop them in the same
            # transaction so the table stays one live row per active bucket.
            conn.execute(
                text("DELETE FROM rate_limits WHERE bucket = :b AND window_start < :w"),
                {"b": bucket, "w": ws},
            )
        return count

    def count(self, bucket: str, window_seconds: int) -> int:
        from sqlalchemy import text

        from app.db.session import engine

        ws = _window_start(time.time(), window_seconds)
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT count FROM rate_limits "
                    "WHERE bucket = :b AND window_start = :w"
                ),
                {"b": bucket, "w": ws},
            ).scalar()
        return int(row or 0)

    def reset(self, bucket: str) -> None:
        from sqlalchemy import text

        from app.db.session import engine

        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM rate_limits WHERE bucket = :b"), {"b": bucket}
            )

    def clear_all(self) -> None:
        from sqlalchemy import text

        from app.db.session import engine

        with engine.begin() as conn:
            conn.execute(text("DELETE FROM rate_limits"))


def backend_for(environment_is_production: bool) -> str:
    """Default backend by environment; RATE_LIMIT_BACKEND overrides explicitly."""
    import os

    explicit = os.getenv("RATE_LIMIT_BACKEND", "").strip().lower()
    if explicit in ("memory", "postgres"):
        return explicit
    return "postgres" if environment_is_production else "memory"


def _make_store():
    if backend_for(settings.is_production) == "postgres":
        return PostgresStore()
    return MemoryStore()


_store = _make_store()


# ---- public module API (call sites in routers stay unchanged) ----------------

def is_locked(key: str) -> bool:
    return _store.count(_bucket(_LOGIN_PREFIX, key), WINDOW_SECONDS) >= MAX_FAILURES


def record_failure(key: str) -> None:
    _store.incr(_bucket(_LOGIN_PREFIX, key), WINDOW_SECONDS)


def reset(key: str) -> None:
    _store.reset(_bucket(_LOGIN_PREFIX, key))


def throttle_public(key: str) -> bool:
    """Record one public-route request; True when the caller must get a 429."""
    return _store.incr(_bucket(_PUBLIC_PREFIX, key), PUBLIC_WINDOW_SECONDS) > PUBLIC_MAX_REQUESTS


def throttle_api(key: str) -> bool:
    """Record one API-credential request; True when the caller must get a 429.

    Applied per IP on all /auth/credentials endpoints. Caps the rate at which
    an attacker can trigger AIOS identity_verify calls via bearer tokens.
    """
    return _store.incr(_bucket(_API_PREFIX, key), API_WINDOW_SECONDS) > API_MAX_REQUESTS


def clear_all() -> None:
    _store.clear_all()
