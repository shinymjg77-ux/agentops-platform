from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.alerts.store import alert_store
from app.security.rbac import Role, require_roles

router = APIRouter(prefix="/alerts", tags=["alerts"])


class FailureAlertItem(BaseModel):
    delivery_id: str
    error_code: str
    category: str
    severity: str
    created_at: str


class FailureAlertListResponse(BaseModel):
    alerts: list[FailureAlertItem]


@router.get("/failures", response_model=FailureAlertListResponse, summary="List failure alerts")
def list_failure_alerts(
    _role: Role = Depends(require_roles(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
    limit: int = Query(default=100, ge=1, le=500),
) -> FailureAlertListResponse:
    rows = alert_store.list_failures(limit=limit)
    return FailureAlertListResponse(alerts=[FailureAlertItem(**row) for row in rows])
