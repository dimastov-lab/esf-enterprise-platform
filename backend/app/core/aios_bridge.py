"""Single entry-point for all AIOS Core communication inside ESF.

ADR-0015 Decision 3: ESF may not import aios.* directly. All SDK calls go
through this module. Routers and domain services import only `get_bridge()`
— never `aios_sdk` or `httpx` directly.

When AIOS_ENABLED=false (the default) every method is a no-op and returns
None. ESF behaves identically to v1.1.6 in that mode; no AIOS instance is
required in development.

When AIOS_ENABLED=true the bridge makes synchronous calls to AIOS Core via
`aios_sdk.AIOSClient` and logs failures at WARNING level. Errors never
propagate to the caller — all AIOS operations are fire-and-forget.

NOTE — identity_verify: the AIOS SDK does not expose an identity endpoint.
That call uses a *caller-supplied* token (not the service-account token), so
it is implemented directly via httpx and kept isolated here.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_ESF_TASK_TYPE = "esf_document"


class AIOSBridgeService:
    """SDK facade over the AIOS Task / Memory / Health APIs.

    Instantiated once at application startup by `_build_bridge()`.
    The `AIOSClient` instance is held for the application lifetime —
    reusing its connection pool across all requests.
    """

    def __init__(self, base_url: str, token: str, workspace_id: str) -> None:
        from aios_sdk import AIOSClient

        self._sdk = AIOSClient(
            base_url=base_url,
            token=token,
            timeout=httpx.Timeout(5.0),
        )
        self._workspace_id = workspace_id
        self._base = base_url.rstrip("/")  # used only by identity_verify (not in SDK)

    # ── Task lifecycle ─────────────────────────────────────────────────────

    def task_create(self, doc_uuid: str, doc_id: int) -> Optional[str]:
        """Create an AIOS task for a new ESF document. Returns the AIOS task_id."""
        from aios_sdk import CreateTaskRequest

        try:
            req = CreateTaskRequest(
                subject_ref=f"esf:{doc_uuid}",
                title=f"ESF document {doc_id}",
                type=_ESF_TASK_TYPE,
                payload={"esf_uuid": doc_uuid, "esf_id": doc_id},
            )
            resp = self._sdk.tasks.create(
                req, idempotency_key=f"esf-create-{doc_uuid}"
            )
            return resp.data.id
        except Exception as exc:
            logger.warning("AIOS task_create failed for doc %s: %s", doc_id, exc)
            return None

    def task_start(self, task_id: Optional[str]) -> None:
        if not task_id:
            return
        try:
            self._sdk.tasks.start(task_id)
        except Exception as exc:
            logger.warning("AIOS task_start failed for %s: %s", task_id, exc)

    def task_escalate(self, task_id: Optional[str]) -> None:
        if not task_id:
            return
        try:
            self._sdk.tasks.escalate(task_id)
        except Exception as exc:
            logger.warning("AIOS task_escalate failed for %s: %s", task_id, exc)

    def task_complete(self, task_id: Optional[str]) -> None:
        if not task_id:
            return
        try:
            self._sdk.tasks.complete(task_id)
        except Exception as exc:
            logger.warning("AIOS task_complete failed for %s: %s", task_id, exc)

    def task_cancel(self, task_id: Optional[str]) -> None:
        if not task_id:
            return
        try:
            self._sdk.tasks.cancel(task_id)
        except Exception as exc:
            logger.warning("AIOS task_cancel failed for %s: %s", task_id, exc)

    # ── Connectivity ───────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if AIOS is reachable (health endpoint responds without error)."""
        try:
            self._sdk.health.get()
            return True
        except Exception as exc:
            logger.warning("AIOS ping failed: %s", exc)
            return False

    # ── Identity validation (Layer 2) ─────────────────────────────────────

    def identity_verify(self, user_token: str) -> Optional[dict]:
        """Validate a user Bearer token via AIOS Identity.

        The AIOS SDK does not expose an identity endpoint so this call uses
        httpx directly with the *caller's* token (not the service-account
        token). Returns the claims dict on success, None on failure or when
        AIOS is unreachable (ESF falls back to its own JWT path in that case).
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(
                    self._base + "/api/v1/identity/me",
                    headers={
                        "Authorization": f"Bearer {user_token}",
                        "Accept": "application/json",
                    },
                )
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(
                    "AIOS identity_verify returned %s", resp.status_code
                )
                return None
        except Exception as exc:
            logger.warning("AIOS identity_verify failed: %s", exc)
            return None

    # ── Memory lifecycle (Layer 3) ─────────────────────────────────────────

    def memory_create(self, snapshot_uuid: str, sha256: str, payload: dict) -> Optional[str]:
        """Write a published ESF snapshot to AIOS Memories. Returns memory_id.

        Uses snapshot_uuid as the Idempotency-Key so a retry on the same
        snapshot always resolves to the same memory record.

        The snapshot payload is stored as JSON in the memory `content` field.
        Provenance data (sha256, subject_ref) goes into `metadata`.
        """
        from aios_sdk import CreateMemoryRequest

        try:
            content = json.dumps(payload, ensure_ascii=False)
            req = CreateMemoryRequest(
                title=f"ESF Snapshot {snapshot_uuid}",
                kind="esf_snapshot",
                content=content,
                metadata={
                    "sha256": sha256,
                    "subject_ref": f"esf-snapshot:{snapshot_uuid}",
                },
            )
            ik = f"esf-snapshot-{snapshot_uuid}"
            if self._workspace_id:
                resp = self._sdk.memories.create_in_workspace(
                    self._workspace_id, req, idempotency_key=ik
                )
            else:
                resp = self._sdk.memories.create_global(req, idempotency_key=ik)
            return resp.data.id
        except Exception as exc:
            logger.warning(
                "AIOS memory_create failed for snapshot %s: %s", snapshot_uuid, exc
            )
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

    def ping(self) -> bool:
        return False

    def identity_verify(self, *_a, **_kw) -> None:
        return None

    def memory_create(self, *_a, **_kw) -> None:
        return None


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
