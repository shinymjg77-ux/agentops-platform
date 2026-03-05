from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.audit.events import set_audit_event
from app.consent.store import consent_store
from app.security.rbac import Role, require_roles

router = APIRouter(prefix="/consents", tags=["consents"])


class ConsentUpsertRequest(BaseModel):
    status: str = Field(pattern="^(opt_in|opt_out)$")
    source: str = Field(min_length=1, max_length=64)
    proof_ref: str | None = Field(default=None, max_length=500)


class ConsentResponse(BaseModel):
    recipient_id: str
    status: str
    source: str
    proof_ref: str | None
    updated_at: str


@router.post("/{recipient_id}", response_model=ConsentResponse, summary="Upsert recipient consent")
def upsert_consent(
    recipient_id: str,
    payload: ConsentUpsertRequest,
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> ConsentResponse:
    record = consent_store.upsert(recipient_id, payload.status, payload.source, payload.proof_ref)

    set_audit_event(
        request,
        action="consent.upsert",
        target_type="recipient",
        target_id=recipient_id,
        metadata={"role": role, "status": payload.status},
    )

    return ConsentResponse(
        recipient_id=record.recipient_id,
        status=record.status,
        source=record.source,
        proof_ref=record.proof_ref,
        updated_at=record.updated_at,
    )


@router.get("/{recipient_id}", response_model=ConsentResponse, summary="Get recipient consent")
def get_consent(
    recipient_id: str,
    request: Request,
    role: Role = Depends(require_roles(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> ConsentResponse:
    record = consent_store.get(recipient_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="consent_not_found")

    set_audit_event(
        request,
        action="consent.read",
        target_type="recipient",
        target_id=recipient_id,
        metadata={"role": role},
    )

    return ConsentResponse(
        recipient_id=record.recipient_id,
        status=record.status,
        source=record.source,
        proof_ref=record.proof_ref,
        updated_at=record.updated_at,
    )
