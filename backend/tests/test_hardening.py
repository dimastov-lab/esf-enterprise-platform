"""Hardening sprint v1.1.5 — shared-store rate limiting (TD-013/TD-019 remainder).

The in-process limiter windows are per-worker; production runs uvicorn with
``--workers 2``, so the effective limits were N×configured and lockouts did not
survive a worker restart. These tests cover the shared Postgres-backed store:
fixed-window counters in the ``rate_limits`` table, atomic upsert, visible to
every worker/replica that shares the database.
"""
import time

import pytest

from app.core import ratelimit


@pytest.fixture
def pg_store():
    """A PostgresStore wired to the dev engine; rows are cleaned up after."""
    store = ratelimit.PostgresStore()
    store.clear_all()
    yield store
    store.clear_all()


class TestPostgresStore:
    def test_incr_counts_within_window(self, pg_store):
        assert pg_store.incr("t:a", 60) == 1
        assert pg_store.incr("t:a", 60) == 2
        assert pg_store.incr("t:a", 60) == 3

    def test_buckets_are_independent(self, pg_store):
        pg_store.incr("t:a", 60)
        assert pg_store.incr("t:b", 60) == 1

    def test_count_does_not_increment(self, pg_store):
        pg_store.incr("t:a", 60)
        assert pg_store.count("t:a", 60) == 1
        assert pg_store.count("t:a", 60) == 1

    def test_count_empty_bucket_is_zero(self, pg_store):
        assert pg_store.count("t:none", 60) == 0

    def test_reset_clears_bucket(self, pg_store):
        pg_store.incr("t:a", 60)
        pg_store.reset("t:a")
        assert pg_store.count("t:a", 60) == 0

    def test_window_rollover_starts_fresh(self, pg_store):
        pg_store.incr("t:roll", 1)
        time.sleep(1.1)
        assert pg_store.incr("t:roll", 1) == 1

    def test_two_store_instances_share_state(self, pg_store):
        """Two instances = two uvicorn workers: counts must be shared."""
        other = ratelimit.PostgresStore()
        pg_store.incr("t:shared", 60)
        assert other.incr("t:shared", 60) == 2


class TestModuleApiOnPostgres:
    """The public module API (used by routers) against the shared store."""

    @pytest.fixture(autouse=True)
    def _use_postgres(self, monkeypatch):
        store = ratelimit.PostgresStore()
        store.clear_all()
        monkeypatch.setattr(ratelimit, "_store", store)
        yield
        store.clear_all()

    def test_lockout_after_max_failures(self):
        key = "t:1.2.3.4\x00admin"
        assert not ratelimit.is_locked(key)
        for _ in range(ratelimit.MAX_FAILURES):
            ratelimit.record_failure(key)
        assert ratelimit.is_locked(key)

    def test_is_locked_does_not_consume_attempts(self):
        key = "t:1.2.3.4\x00probe"
        for _ in range(ratelimit.MAX_FAILURES - 1):
            ratelimit.record_failure(key)
        for _ in range(10):                       # polling must not lock
            assert not ratelimit.is_locked(key)

    def test_reset_unlocks(self):
        key = "t:1.2.3.4\x00admin"
        for _ in range(ratelimit.MAX_FAILURES):
            ratelimit.record_failure(key)
        ratelimit.reset(key)
        assert not ratelimit.is_locked(key)

    def test_public_throttle_allows_then_rejects(self):
        key = "t:5.6.7.8"
        for _ in range(ratelimit.PUBLIC_MAX_REQUESTS):
            assert not ratelimit.throttle_public(key)
        assert ratelimit.throttle_public(key)


def test_backend_selection_defaults():
    """development → memory; production → postgres (shared, multi-worker-safe)."""
    assert ratelimit.backend_for(environment_is_production=False) == "memory"
    assert ratelimit.backend_for(environment_is_production=True) == "postgres"


def test_qr_storage_dir_is_injectable(tmp_path, monkeypatch):
    """TD-016: publish must not write QR PNGs into the working tree when a
    dedicated storage dir is configured (tests point it at a tmp dir)."""
    from app.core.config import settings
    from app.services import qr_service

    monkeypatch.setattr(settings, "QR_STORAGE_DIR", str(tmp_path))
    out = qr_service.write_qr_file("test-uuid-123")
    assert out == str(tmp_path / "test-uuid-123.png")
    assert (tmp_path / "test-uuid-123.png").exists()


class TestStyledErrorPages:
    """Browser/JSON split for 404s is covered in test_regression
    (test_error_pages_are_styled_for_browsers); here only the header
    pass-through that the styled surface must not lose."""

    def test_429_html_keeps_retry_after(self, override_db):
        from fastapi.testclient import TestClient

        from app.core import ratelimit
        from app.main import app

        c = TestClient(app)
        for _ in range(ratelimit.PUBLIC_MAX_REQUESTS):
            ratelimit.throttle_public("testclient")
        r = c.get("/esf/check-esf?documentUUID=00000000-0000-0000-0000-000000000000",
                  headers={"Accept": "text/html"})
        assert r.status_code == 429
        assert r.headers.get("Retry-After") == str(ratelimit.PUBLIC_WINDOW_SECONDS)
        assert r.headers["content-type"].startswith("text/html")


class TestEnvOrFile:
    """Docker-secrets support: NAME_FILE points at a mounted secret file whose
    content is used when the plain NAME env var is absent."""

    def test_plain_env_wins(self, tmp_path, monkeypatch):
        from app.core import config

        f = tmp_path / "s"
        f.write_text("from-file")
        monkeypatch.setenv("ESF_T_SETTING", "plain")
        monkeypatch.setenv("ESF_T_SETTING_FILE", str(f))
        assert config.env_or_file("ESF_T_SETTING", "d") == "plain"

    def test_file_used_when_env_absent(self, tmp_path, monkeypatch):
        from app.core import config

        f = tmp_path / "s"
        f.write_text("from-file\n")           # trailing newline must be stripped
        monkeypatch.delenv("ESF_T_SETTING", raising=False)
        monkeypatch.setenv("ESF_T_SETTING_FILE", str(f))
        assert config.env_or_file("ESF_T_SETTING", "d") == "from-file"

    def test_default_when_neither_set(self, monkeypatch):
        from app.core import config

        monkeypatch.delenv("ESF_T_SETTING", raising=False)
        monkeypatch.delenv("ESF_T_SETTING_FILE", raising=False)
        assert config.env_or_file("ESF_T_SETTING", "d") == "d"
