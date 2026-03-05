from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.audit.events import set_audit_event
from app.consent.store import consent_store
from app.delivery.scheduler import process_due_deliveries
from app.delivery.store import delivery_store
from app.security.rbac import Role, require_roles
from app.workflow.post_workflow import post_workflow_store

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


class DeliveryScheduleRequest(BaseModel):
    post_id: str = Field(min_length=1, max_length=120)
    recipient_id: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=1, max_length=128)
    scheduled_at: str | None = None
    campaign_timezone: str = Field(default="UTC", min_length=1, max_length=64)


class DeliveryResponse(BaseModel):
    delivery_id: str
    post_id: str
    recipient_id: str
    status: str
    error_code: str | None
    attempts: int
    idempotency_key: str
    scheduled_at: str
    next_attempt_at: str
    created_at: str
    sent_at: str | None
    deduplicated: bool = False


class DeliveryProcessRequest(BaseModel):
    force_process: bool = False
    limit: int = Field(default=50, ge=1, le=200)


class DeliveryProcessResponse(BaseModel):
    processed: int
    sent: int
    retrying: int
    failed: int


def _parse_scheduled_at(value: str | None, timezone_name: str) -> datetime:
    if value is None:
        return datetime.now(UTC)

    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)

    if dt.tzinfo is None:
        tz = ZoneInfo(timezone_name)
        dt = dt.replace(tzinfo=tz)

    return dt.astimezone(UTC)


def _to_response(payload: dict[str, str | int | None], *, deduplicated: bool = False) -> DeliveryResponse:
    return DeliveryResponse(
        delivery_id=str(payload["delivery_id"]),
        post_id=str(payload["post_id"]),
        recipient_id=str(payload["recipient_id"]),
        status=str(payload["status"]),
        error_code=payload["error_code"] if payload["error_code"] is None else str(payload["error_code"]),
        attempts=int(payload["attempts"]),
        idempotency_key=str(payload["idempotency_key"]),
        scheduled_at=str(payload["scheduled_at"]),
        next_attempt_at=str(payload["next_attempt_at"]),
        created_at=str(payload["created_at"]),
        sent_at=payload["sent_at"] if payload["sent_at"] is None else str(payload["sent_at"]),
        deduplicated=deduplicated,
    )


@router.post("/schedule", response_model=DeliveryResponse, summary="Schedule DM delivery")
def schedule_delivery(
    payload: DeliveryScheduleRequest,
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> DeliveryResponse:
    try:
        post_state = post_workflow_store.get(payload.post_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if post_state.status != "approved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="approval_required")

    consent = consent_store.get(payload.recipient_id)
    if consent is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="consent_missing")
    if consent.status != "opt_in":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="consent_revoked")

    scheduled_at = _parse_scheduled_at(payload.scheduled_at, payload.campaign_timezone)
    record, dedup = delivery_store.create(
        post_id=payload.post_id,
        recipient_id=payload.recipient_id,
        content=payload.content,
        scheduled_at=scheduled_at,
        idempotency_key=payload.idempotency_key,
    )

    set_audit_event(
        request,
        action="delivery.schedule",
        target_type="delivery",
        target_id=record.delivery_id,
        metadata={"role": role, "deduplicated": str(dedup).lower()},
    )

    return _to_response(delivery_store.as_dict(record), deduplicated=dedup)


@router.post("/process-due", response_model=DeliveryProcessResponse, summary="Process due deliveries")
async def process_due(
    payload: DeliveryProcessRequest,
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> DeliveryProcessResponse:
    summary = await process_due_deliveries(force_process=payload.force_process, limit=payload.limit)

    set_audit_event(
        request,
        action="delivery.process_due",
        target_type="delivery_batch",
        target_id="due",
        metadata={"role": role, "processed": str(summary["processed"])},
    )

    return DeliveryProcessResponse(**summary)


@router.get("/{delivery_id}", response_model=DeliveryResponse, summary="Get delivery by id")
def get_delivery(
    delivery_id: str,
    request: Request,
    role: Role = Depends(require_roles(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> DeliveryResponse:
    try:
        record = delivery_store.get_by_id(delivery_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    set_audit_event(
        request,
        action="delivery.read",
        target_type="delivery",
        target_id=delivery_id,
        metadata={"role": role},
    )

    return _to_response(delivery_store.as_dict(record))


@router.get(
    "/idempotency/{idempotency_key}",
    response_model=DeliveryResponse,
    summary="Get delivery by idempotency key",
)
def get_delivery_by_idempotency(
    idempotency_key: str,
    request: Request,
    role: Role = Depends(require_roles(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> DeliveryResponse:
    try:
        record = delivery_store.get_by_idempotency(idempotency_key)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    set_audit_event(
        request,
        action="delivery.read_by_idempotency",
        target_type="delivery",
        target_id=record.delivery_id,
        metadata={"role": role},
    )

    return _to_response(delivery_store.as_dict(record))
