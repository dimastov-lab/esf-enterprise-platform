"""Single entry-point for all AIOS Core communication inside ESF.

ADR-0015 Decision 3: ESF may not import aios.* directly. All SDK / HTTP
calls go through this module. Routers and domain services import only
`get_bridge()` — never `aios_sdk` or `httpx` directly.

When AIOS_ENABLED=false (the default) every method is a no-op and returns
None. ESF behaves identically to v1.1.6 in that mode; no AIOS instance is
required in development.

When AIOS_ENABLED=true the bridge makes synchronous HTTPS calls to
AIOS Core and logs failures at WARNING level. Errors never propagate to
the caller — Layer 1 is fire-and-forget (temporary; becomes mandatory in
Layer 2).

Note on SDK vs HTTP: aios_sdk requires Python ≥ 3.10 (ParamSpec in typing);
ESF's local dev venv is Python 3.9. The bridge calls the AIOS HTTP API
directly via httpx. When ESF's runtime is upgraded to 3.11+ the bridge can
be rewritten to use AIOSClient without any caller changes.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_ESF_TASK_TYPE = "esf_document"


class AIOSBridgeService:
    """Thin HTTP facade over the AIOS Task API.

    Instantiated once at application startup by `_build_bridge()`.
    """

    def __init__(self, base_url: str, token: str, workspace_id: str) -> None:
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self._workspace_id = workspace_id

    # ── Task lifecycle ────────────────────────────────────────────────────

    def task_create(self, doc_uuid: str, doc_id: int) -> Optional[str]:
        """Create an AIOS task for a new ESF document. Returns the AIOS task_id."""
        body = {
            "subject_ref": f"esf:{doc_uuid}",
            "title": f"ESF document {doc_id}",
            "type": _ESF_TASK_TYPE,
            "payload": {"esf_uuid": doc_uuid, "esf_id": doc_id},
        }
        resp = self._post("/api/v1/tasks", body,
                          idempotency_key=f"esf-create-{doc_uuid}")
        if resp is None:
            return None
        return resp.get("id") or resp.get("task_id")

    def task_start(self, task_id: Optional[str]) -> None:
        """DRAFT → VALIDATED: mark the AIOS task as started."""
        if task_id:
            self._post(f"/api/v1/tasks/{task_id}/start", None)

    def task_escalate(self, task_id: Optional[str]) -> None:
        """VALIDATED → SNAPSHOT_CREATED: escalate the AIOS task."""
        if task_id:
            self._post(f"/api/v1/tasks/{task_id}/escalate", None)

    def task_complete(self, task_id: Optional[str]) -> None:
        """SNAPSHOT_CREATED → PUBLISHED: complete the AIOS task."""
        if task_id:
            self._post(f"/api/v1/tasks/{task_id}/complete", None)

    def task_cancel(self, task_id: Optional[str]) -> None:
        """PUBLISHED → CANCELLED: cancel the AIOS task."""
        if task_id:
            self._post(f"/api/v1/tasks/{task_id}/cancel", None)

    # ── Internal ──────────────────────────────────────────────────────────

    def _post(self, path: str, body: Optional[dict],
              idempotency_key: Optional[str] = None) -> Optional[dict]:
        headers = dict(self._headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    self._base + path,
                    json=body,
                    headers=headers,
                )
                if resp.status_code >= 400:
                    logger.warning(
                        "AIOS %s returned %s: %s", path, resp.status_code, resp.text[:200]
                    )
                    return None
                return resp.json() if resp.content else None
        except Exception as exc:
            logger.warning("AIOS request to %s failed: %s", path, exc)
            return None


class _NoOpBridge:
    """Returned when AIOS_ENABLED=false. Every call is a silent no-op."""

    def task_create(self, *_a, **_kw) -> None:
        return None

    def task_start(self, *_a, **_kw) -> None:
        pass

    def task_escalate(self, *_a, **_kw) -> None:
        pass

    def task_complete(self, *_a, **_kw) -> None:
        pass

    def task_cancel(self, *_a, **_kw) -> None:
        pass


def _build_bridge():
    if not settings.AIOS_ENABLED:
        return _NoOpBridge()
    token = settings.effective_aios_token
    if not token:
        logger.error(
            "AIOS_ENABLED=true but no token configured (AIOS_TOKEN / AIOS_TOKEN_FILE). "
            "Falling back to no-op bridge."
        )
        return _NoOpBridge()
    return AIOSBridgeService(
        base_url=settings.AIOS_BASE_URL,
        token=token,
        workspace_id=settings.AIOS_WORKSPACE_ID,
    )


_bridge = None


def get_bridge():
    """Return the singleton bridge instance (initialized lazily on first call)."""
    global _bridge
    if _bridge is None:
        _bridge = _build_bridge()
    return _bridge


def reset_bridge(instance=None) -> None:
    """Replace the singleton — used in tests to inject a mock."""
    global _bridge
    _bridge = instance
