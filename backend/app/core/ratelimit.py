"""Minimal in-process rate limiters (anti-brute-force + public-route throttle).

Per-process only — for multi-worker/production use a shared store (Redis).
Two independent buckets, both keyed by client IP:
- login lockout: a sliding window of FAILED attempts triggers a temporary lockout;
- public throttle: a sliding window of ALL requests to the open verification
  routes (`/esf/check-esf`, `/qr/*.png`) caps scraping/enumeration (TD-013).
"""
import time

WINDOW_SECONDS = 300
MAX_FAILURES = 5

PUBLIC_WINDOW_SECONDS = 60
PUBLIC_MAX_REQUESTS = 30

_failures: dict = {}
_public_requests: dict = {}


def _recent(key: str) -> list:
    now = time.time()
    xs = [t for t in _failures.get(key, []) if now - t < WINDOW_SECONDS]
    _failures[key] = xs
    return xs


def is_locked(key: str) -> bool:
    return len(_recent(key)) >= MAX_FAILURES


def record_failure(key: str) -> None:
    _recent(key).append(time.time())


def reset(key: str) -> None:
    _failures.pop(key, None)


def throttle_public(key: str) -> bool:
    """Record one public-route request; True when the caller must get a 429.

    Rejected requests are NOT recorded, so the window tracks allowed traffic
    and the bucket cannot grow unbounded under a flood.
    """
    now = time.time()
    xs = [t for t in _public_requests.get(key, []) if now - t < PUBLIC_WINDOW_SECONDS]
    if len(xs) >= PUBLIC_MAX_REQUESTS:
        _public_requests[key] = xs
        return True
    xs.append(now)
    _public_requests[key] = xs
    return False


def clear_all() -> None:
    _failures.clear()
    _public_requests.clear()
