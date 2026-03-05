import json
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.audit.events import AuditEvent
from app.audit.store import audit_log_store

logger = logging.getLogger("audit")


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        event: AuditEvent | None = getattr(request.state, "audit_event", None)
        if event is None:
            return response

        actor_id = request.headers.get("X-Actor-Id", "unknown")
        role = request.headers.get("X-Role", "unknown")
        payload = {
            "actor_id": actor_id,
            "role": role,
            "action": event.action,
            "target_type": event.target_type,
            "target_id": event.target_id,
            "metadata": event.metadata,
        }
        audit_log_store.append(
            actor_id=actor_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            metadata={"role": role, **event.metadata},
        )
        logger.info("audit_event=%s", json.dumps(payload, ensure_ascii=True))
        response.headers["X-Audit-Logged"] = "1"
        return response
