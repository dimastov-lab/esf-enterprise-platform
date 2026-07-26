"""Minimal in-process login rate limiter (anti-brute-force).

Per-process only — for multi-worker/production use a shared store (Redis). Keyed
by client IP; a sliding window of failed attempts triggers a temporary lockout.
"""
import time

WINDOW_SECONDS = 300
MAX_FAILURES = 5

_failures: dict = {}


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


def clear_all() -> None:
    _failures.clear()
