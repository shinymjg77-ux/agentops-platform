from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel

from app.audit.events import set_audit_event
from app.audit.store import audit_log_store
from app.security.rbac import Role, require_roles

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditLogEntryResponse(BaseModel):
    actor_id: str
    action: str
    target_type: str
    target_id: str
    timestamp: str
    metadata: dict[str, str]


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogEntryResponse]


@router.post("/approve", summary="Mock post approval action")
def mock_approve_action(
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> dict[str, str]:
    set_audit_event(
        request,
        action="post.approve",
        target_type="post",
        target_id="mock-post-1",
        metadata={"source": "phase1_mock", "role": role},
    )
    return {"status": "approved", "role": role}


@router.post("/send", summary="Mock delivery send action")
def mock_send_action(
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> dict[str, str]:
    set_audit_event(
        request,
        action="delivery.send",
        target_type="delivery",
        target_id="mock-delivery-1",
        metadata={"source": "phase1_mock", "role": role},
    )
    return {"status": "sent", "role": role}


@router.get("/logs", response_model=AuditLogListResponse, summary="List audit logs")
def list_audit_logs(
    _request: Request,
    _role: Role = Depends(require_roles(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
    limit: int = Query(default=100, ge=1, le=500),
    action: str | None = None,
    target_type: str | None = None,
) -> AuditLogListResponse:
    logs = audit_log_store.list_entries(limit=limit, action=action, target_type=target_type)
    return AuditLogListResponse(logs=[AuditLogEntryResponse(**item) for item in logs])
