# TD-025: AIOS Identity — Distinguish Explicit Rejection from Unavailability

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When AIOS explicitly rejects a bearer token (4xx), raise `AIOSTokenRejectedError` so `get_current_api_user` returns 401 immediately — no fallback to ESF JWT; when AIOS is unreachable (network error / 5xx), keep returning `None` so the ESF JWT fallback still works.

**Architecture:** Two-step change. First, add `AIOSTokenRejectedError` to `aios_bridge.py` and wire it in both `identity_verify` and `async_identity_verify`: 4xx → raise, 5xx/network error → return `None`. Second, update `get_current_api_user` in `security.py` to catch `AIOSTokenRejectedError` before the generic `Exception` handler and immediately raise HTTP 401 without touching the ESF JWT path.

**Tech Stack:** Python 3.12, FastAPI, httpx, pytest/anyio, `unittest.mock`

## Global Constraints

- Layered architecture: Controller → Service → Repository. Bridge lives in `app/core/`, not in routers or services.
- No TODO/FIXME/HACK in production code.
- All AIOS operations remain fire-and-forget for non-identity paths (task_*, memory_create, ping). Only `identity_verify` / `async_identity_verify` gain the new exception.
- `_NoOpBridge` (returned when `AIOS_ENABLED=false`) must still return `None` from both methods — it never raises `AIOSTokenRejectedError`.
- The `except AIOSTokenRejectedError: raise` re-raise clause MUST appear BEFORE the generic `except Exception` clause in both bridge methods; Python checks except clauses in order.
- Existing test `test_aios_unavailable_falls_back_to_esf_jwt` must continue to pass (bridge returning `None` → fallback unchanged).
- Run tests from `backend/` with `uv run python -m pytest tests/ -q`.

---

### Task 1: `AIOSTokenRejectedError` + bridge 4xx distinction

**Files:**
- Modify: `backend/app/core/aios_bridge.py`
- Modify: `backend/tests/test_aios_identity.py` (add new test class at the bottom)

**Interfaces:**
- Produces:
  - `AIOSTokenRejectedError(status_code: int)` — module-level exception class, exported from `aios_bridge.py`
  - `AIOSBridgeService.identity_verify(user_token)` — raises `AIOSTokenRejectedError` when `400 <= status_code < 500`; returns `None` for 5xx and network errors (unchanged)
  - `AIOSBridgeService.async_identity_verify(user_token)` — same contract, async

- [ ] **Step 1: Write failing tests for the bridge (add to `backend/tests/test_aios_identity.py`)**

Add these imports at the top of the file (after the existing imports):

```python
import httpx
from unittest.mock import patch
from app.core.aios_bridge import AIOSBridgeService, AIOSTokenRejectedError
```

Then add this class at the bottom of the file:

```python
# ---------------------------------------------------------------------------
# AIOSBridgeService.identity_verify — unit tests for 4xx distinction
# ---------------------------------------------------------------------------

class TestBridgeIdentityVerifyRejection:
    """Unit tests: 4xx → raise AIOSTokenRejectedError; 5xx/network → return None."""

    def _make_bridge(self):
        bridge = AIOSBridgeService.__new__(AIOSBridgeService)
        bridge._base = "http://fakehost"
        return bridge

    def _mock_sync_client(self, status_code: int):
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_resp
        return mock_client

    @pytest.mark.parametrize("status_code", [401, 403, 404, 422])
    def test_identity_verify_raises_on_4xx(self, status_code):
        bridge = self._make_bridge()
        mock_client = self._mock_sync_client(status_code)
        with patch("app.core.aios_bridge.httpx.Client", return_value=mock_client):
            with pytest.raises(AIOSTokenRejectedError) as exc_info:
                bridge.identity_verify("some-token")
        assert exc_info.value.status_code == status_code

    @pytest.mark.parametrize("status_code", [500, 502, 503])
    def test_identity_verify_returns_none_on_5xx(self, status_code):
        bridge = self._make_bridge()
        mock_client = self._mock_sync_client(status_code)
        with patch("app.core.aios_bridge.httpx.Client", return_value=mock_client):
            result = bridge.identity_verify("some-token")
        assert result is None

    def test_identity_verify_returns_none_on_network_error(self):
        bridge = self._make_bridge()
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.ConnectError("timeout")
        with patch("app.core.aios_bridge.httpx.Client", return_value=mock_client):
            result = bridge.identity_verify("some-token")
        assert result is None

    @pytest.mark.anyio
    async def test_async_identity_verify_raises_on_4xx(self):
        bridge = self._make_bridge()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("app.core.aios_bridge.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(AIOSTokenRejectedError) as exc_info:
                await bridge.async_identity_verify("some-token")
        assert exc_info.value.status_code == 401

    @pytest.mark.anyio
    async def test_async_identity_verify_returns_none_on_network_error(self):
        bridge = self._make_bridge()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        with patch("app.core.aios_bridge.httpx.AsyncClient", return_value=mock_client):
            result = await bridge.async_identity_verify("some-token")
        assert result is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
uv run python -m pytest tests/test_aios_identity.py::TestBridgeIdentityVerifyRejection -v
```

Expected: `ImportError: cannot import name 'AIOSTokenRejectedError'`.

- [ ] **Step 3: Add `AIOSTokenRejectedError` and update `identity_verify` + `async_identity_verify`**

In `backend/app/core/aios_bridge.py`:

After the `logger = logging.getLogger(__name__)` line (line 29), add:

```python

class AIOSTokenRejectedError(Exception):
    """Raised by identity_verify when AIOS explicitly rejects a token (4xx).

    Distinct from unavailability (network errors / 5xx), which returns None
    to allow ESF JWT fallback for graceful degradation.
    """
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"AIOS rejected token with status {status_code}")
```

Then replace the entire `identity_verify` method body (currently lines 127–144) with:

```python
    def identity_verify(self, user_token: str) -> Optional[dict]:
        """Validate a user Bearer token via AIOS Identity (synchronous).

        Returns the claims dict on 200. Raises AIOSTokenRejectedError on 4xx
        (AIOS explicitly rejected the token — do not fall back to ESF JWT).
        Returns None on 5xx or network errors (AIOS unreachable — fall back).
        """
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(
                    self._base + "/api/v1/identity/me",
                    headers={
                        "Authorization": f"Bearer {user_token}",
                        "Accept": "application/json",
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
                if 400 <= resp.status_code < 500:
                    raise AIOSTokenRejectedError(resp.status_code)
                logger.warning(
                    "AIOS identity_verify returned %s", resp.status_code
                )
                return None
        except AIOSTokenRejectedError:
            raise
        except Exception as exc:
            logger.warning("AIOS identity_verify failed: %s", exc)
            return None
```

Then replace the entire `async_identity_verify` method body (currently lines 146–170) with:

```python
    async def async_identity_verify(self, user_token: str) -> Optional[dict]:
        """Async variant of identity_verify — same contract, uses AsyncClient.

        Raises AIOSTokenRejectedError on 4xx; returns None on 5xx/network errors.
        """
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(
                    self._base + "/api/v1/identity/me",
                    headers={
                        "Authorization": f"Bearer {user_token}",
                        "Accept": "application/json",
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
                if 400 <= resp.status_code < 500:
                    raise AIOSTokenRejectedError(resp.status_code)
                logger.warning(
                    "AIOS async_identity_verify returned %s", resp.status_code
                )
                return None
        except AIOSTokenRejectedError:
            raise
        except Exception as exc:
            logger.warning("AIOS async_identity_verify failed: %s", exc)
            return None
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
uv run python -m pytest tests/test_aios_identity.py::TestBridgeIdentityVerifyRejection -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Run full suite to check no regressions**

```bash
uv run python -m pytest tests/ -q
```

Expected: same count as before + 8 new tests, all green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/aios_bridge.py backend/tests/test_aios_identity.py
git commit -m "feat(aios): AIOSTokenRejectedError — raise on 4xx, return None on 5xx/network (TD-025)"
```

---

### Task 2: Wire `AIOSTokenRejectedError` into `get_current_api_user`; update docs

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/tests/test_aios_identity.py` (add 1 integration test to `TestAIOSIdentityEnabled`)
- Modify: `TECHNICAL_DEBT.md` (mark TD-025 RESOLVED)

**Interfaces:**
- Consumes: `AIOSTokenRejectedError` from Task 1

- [ ] **Step 1: Write the failing integration test**

In `backend/tests/test_aios_identity.py`, inside the `TestAIOSIdentityEnabled` class (after the last existing test method), add:

```python
    def test_aios_explicit_rejection_blocks_esf_jwt_fallback(
        self, anon, override_db, seed_users
    ):
        """AIOS 4xx → AIOSTokenRejectedError → HTTP 401; valid ESF JWT is NOT tried."""
        from app.core.aios_bridge import AIOSTokenRejectedError
        spy = MagicMock()
        spy.async_identity_verify = AsyncMock(
            side_effect=AIOSTokenRejectedError(401)
        )
        reset_bridge(spy)
        # Issue a fully valid ESF JWT — fallback would succeed if allowed
        token = _jwt_for(anon)
        c = TestClient(app)
        c.headers["Authorization"] = f"Bearer {token}"
        resp = c.get("/auth/credentials")
        assert resp.status_code == 401
        assert "AIOS" in resp.json().get("detail", "")
```

- [ ] **Step 2: Verify the test fails**

```bash
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
uv run python -m pytest tests/test_aios_identity.py::TestAIOSIdentityEnabled::test_aios_explicit_rejection_blocks_esf_jwt_fallback -v
```

Expected: FAIL — status 200 (fallback succeeds, but we expect 401).

- [ ] **Step 3: Update `get_current_api_user` in `backend/app/core/security.py`**

In `get_current_api_user`, find the AIOS identity block (around line 91). Replace this:

```python
    if _settings.AIOS_ENABLED:
        from app.core.aios_bridge import get_bridge
        try:
            claims = await get_bridge().async_identity_verify(raw)
        except Exception as exc:  # bridge is already fire-and-forget; guard the call site too
            _log.warning("AIOS async_identity_verify raised: %s", exc)
            claims = None
```

With this:

```python
    if _settings.AIOS_ENABLED:
        from app.core.aios_bridge import AIOSTokenRejectedError, get_bridge
        try:
            claims = await get_bridge().async_identity_verify(raw)
        except AIOSTokenRejectedError as exc:
            raise HTTPException(
                status_code=401,
                detail=f"AIOS identity service rejected this token (HTTP {exc.status_code})",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as exc:
            _log.warning("AIOS async_identity_verify raised: %s", exc)
            claims = None
```

Also update the comment on the fallthrough line (around line 123) from:

```python
        # claims is None: AIOS unavailable or token not recognized by AIOS.
        # Fall through to ESF JWT so local tokens keep working.
```

To:

```python
        # claims is None: AIOS unreachable (network error / 5xx).
        # Fall through to ESF JWT for graceful degradation when AIOS is down.
```

- [ ] **Step 4: Run the new integration test**

```bash
cd /Users/dmitrijcernikov/Desktop/ESF-Enterprise-Clean-Starter/backend
uv run python -m pytest tests/test_aios_identity.py::TestAIOSIdentityEnabled::test_aios_explicit_rejection_blocks_esf_jwt_fallback -v
```

Expected: PASS.

- [ ] **Step 5: Run the full suite**

```bash
uv run python -m pytest tests/ -q
```

Expected: all tests pass (200 + 9 new = 209 total). Specifically verify that `test_aios_unavailable_falls_back_to_esf_jwt` still passes — that test uses `AsyncMock(return_value=None)` (bridge returns None for "unavailable"), which does NOT raise `AIOSTokenRejectedError`, so fallback still works.

- [ ] **Step 6: Update `TECHNICAL_DEBT.md`**

Find the `TD-025` entry and replace its `**Status:**` line:

```
- **Status:** Open. Accepted design tradeoff of the hybrid approach.
```

With:

```
- **Status:** ✅ RESOLVED (v1.2.4, 2026-08-06) — `AIOSTokenRejectedError` added to
  `aios_bridge.py`; `identity_verify` and `async_identity_verify` raise it on 4xx
  responses (AIOS explicitly rejected the token) and return `None` for 5xx / network
  errors (AIOS unreachable). `get_current_api_user` catches `AIOSTokenRejectedError`
  before the generic handler and raises HTTP 401 immediately — no ESF JWT fallback.
  Graceful degradation (AIOS down → ESF JWT still works) is preserved. 9 new tests.
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/security.py \
        backend/tests/test_aios_identity.py \
        TECHNICAL_DEBT.md
git commit -m "feat(security): catch AIOSTokenRejectedError in get_current_api_user — no JWT fallback on AIOS 4xx (TD-025)"
```

---
