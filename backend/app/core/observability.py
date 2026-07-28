"""Observability: structured JSON logging, per-request correlation id, and a
clean catch-all 500 handler (no stack traces leaked to clients).

`install(app)` adds a request-context middleware (assigns/propagates an
`X-Request-ID`, logs one structured access line per request with method/path/
status/duration) and an exception handler that logs unhandled errors with the
request id and returns a generic JSON 500.
"""
import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar

from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


def request_id() -> str:
    return _request_id.get()


def client_ip(request: Request) -> str:
    """Best-effort real client IP for rate-limiting and audit.

    Behind a trusted reverse proxy (``TRUST_PROXY=true``) prefer ``X-Real-IP``,
    which nginx sets to the real peer and overwrites for every request — so a
    client cannot spoof it. Without a trusted proxy, forwarded headers are
    ignored and the direct socket peer is used (they would be attacker-controlled
    on a directly-exposed app).
    """
    if settings.TRUST_PROXY:
        xri = request.headers.get("x-real-ip")
        if xri:
            return xri.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", _request_id.get()),
        }
        for key in ("method", "path", "status", "duration_ms", "client"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if not any(getattr(h, "_esf", False) for h in root.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_JsonFormatter())
        handler._esf = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(level)


_access = logging.getLogger("esf.access")
_error = logging.getLogger("esf.error")


def install(app) -> None:
    configure_logging()

    @app.middleware("http")
    async def _request_context(request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        token = _request_id.set(rid)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            dur = round((time.perf_counter() - start) * 1000, 1)
            response.headers["X-Request-ID"] = rid
            _access.info("request", extra={
                "method": request.method, "path": request.url.path,
                "status": response.status_code, "duration_ms": dur,
                "client": request.client.host if request.client else None,
                "request_id": rid,
            })
            return response
        except Exception:
            _error.exception("unhandled exception", extra={
                "method": request.method, "path": request.url.path, "request_id": rid,
            })
            raise  # let ServerErrorMiddleware produce the response (and re-raise in tests)
        finally:
            _request_id.reset(token)

    async def _on_unhandled(request: Request, exc: Exception):
        return JSONResponse(
            {"detail": "Внутренняя ошибка сервера.", "request_id": _request_id.get()},
            status_code=500,
        )

    app.add_exception_handler(Exception, _on_unhandled)
