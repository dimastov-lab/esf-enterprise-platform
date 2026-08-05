"""Tests for Settings.validate_for_runtime() — production safety guards."""
import pytest
from app.core.config import Settings


def _prod_settings(**overrides) -> Settings:
    """Build a Settings-like object in production mode with a valid secret."""
    s = Settings.__new__(Settings)
    s.ENVIRONMENT = "production"
    s.SECRET_KEY = "x" * 64          # 64-char secret — passes existing checks
    s.PUBLIC_BASE_URL = "https://esf.example.com"
    s.AIOS_ENABLED = False
    s.AIOS_BASE_URL = "https://localhost:8100"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def test_aios_http_url_rejected_in_production():
    s = _prod_settings(AIOS_ENABLED=True, AIOS_BASE_URL="http://aios.internal")
    with pytest.raises(RuntimeError, match="https://"):
        s.validate_for_runtime()


def test_aios_https_url_accepted_in_production():
    s = _prod_settings(AIOS_ENABLED=True, AIOS_BASE_URL="https://aios.internal")
    s.validate_for_runtime()  # must not raise


def test_aios_http_url_allowed_in_development():
    s = _prod_settings(AIOS_ENABLED=True, AIOS_BASE_URL="http://localhost:8100")
    s.ENVIRONMENT = "development"
    s.validate_for_runtime()  # dev mode exits early — must not raise


def test_aios_http_url_allowed_when_aios_disabled():
    s = _prod_settings(AIOS_ENABLED=False, AIOS_BASE_URL="http://localhost:8100")
    s.validate_for_runtime()  # AIOS disabled — check must not fire
