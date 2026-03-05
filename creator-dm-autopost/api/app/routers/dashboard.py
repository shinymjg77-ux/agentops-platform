from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.delivery.store import delivery_store
from app.security.rbac import Role, require_roles

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class FailureItem(BaseModel):
    delivery_id: str
    status: str
    error_code: str
    attempts: int
    created_at: str


class DeliverySummaryResponse(BaseModel):
    total: int
    queued: int
    sending: int
    sent: int
    failed: int
    retrying: int
    cancelled: int
    recent_failures: list[FailureItem]


@router.get("/delivery-summary", response_model=DeliverySummaryResponse, summary="Delivery status summary")
def get_delivery_summary(
    _role: Role = Depends(require_roles(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> DeliverySummaryResponse:
    return DeliverySummaryResponse(**delivery_store.status_summary())
