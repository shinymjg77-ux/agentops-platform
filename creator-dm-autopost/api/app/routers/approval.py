from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.audit.events import set_audit_event
from app.security.rbac import Role, require_roles
from app.workflow.post_workflow import post_workflow_store

router = APIRouter(prefix="/approval", tags=["approval"])


class PostStatusTransitionRequest(BaseModel):
    target_status: str = Field(min_length=1, max_length=32)


class PostApprovalStateResponse(BaseModel):
    post_id: str
    status: str
    approved_by: str | None
    approved_at: str | None
    updated_at: str
    history: list[dict[str, str]]


def _transition_post_status(request: Request, post_id: str, target_status: str) -> PostApprovalStateResponse:
    actor_id = request.headers.get("X-Actor-Id", "unknown")

    try:
        state = post_workflow_store.transition(post_id, target_status, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if detail == "invalid_state_transition":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_status") from exc

    return PostApprovalStateResponse(
        post_id=state.post_id,
        status=state.status,
        approved_by=state.approved_by,
        approved_at=state.approved_at,
        updated_at=state.updated_at,
        history=state.history,
    )


@router.post("/posts/{post_id}/submit", response_model=PostApprovalStateResponse, summary="Submit post for approval")
def submit_post_for_approval(
    post_id: str,
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> PostApprovalStateResponse:
    response = _transition_post_status(request, post_id, "pending_approval")
    set_audit_event(
        request,
        action="post.submit_for_approval",
        target_type="post",
        target_id=post_id,
        metadata={"role": role},
    )
    return response


@router.post("/posts/{post_id}/approve", response_model=PostApprovalStateResponse, summary="Approve post")
def approve_post(
    post_id: str,
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> PostApprovalStateResponse:
    response = _transition_post_status(request, post_id, "approved")
    set_audit_event(
        request,
        action="post.approve",
        target_type="post",
        target_id=post_id,
        metadata={"role": role},
    )
    return response


@router.post(
    "/posts/{post_id}/transition",
    response_model=PostApprovalStateResponse,
    summary="Transition post status (state machine guarded)",
)
def transition_post_status(
    post_id: str,
    payload: PostStatusTransitionRequest,
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> PostApprovalStateResponse:
    response = _transition_post_status(request, post_id, payload.target_status)
    set_audit_event(
        request,
        action="post.transition",
        target_type="post",
        target_id=post_id,
        metadata={"role": role, "target_status": payload.target_status},
    )
    return response


@router.get("/posts/{post_id}", response_model=PostApprovalStateResponse, summary="Get post approval state")
def get_post_approval_state(
    post_id: str,
    request: Request,
    role: Role = Depends(require_roles(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> PostApprovalStateResponse:
    try:
        state = post_workflow_store.get(post_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    set_audit_event(
        request,
        action="post.approval_state.read",
        target_type="post",
        target_id=post_id,
        metadata={"role": role},
    )

    return PostApprovalStateResponse(
        post_id=state.post_id,
        status=state.status,
        approved_by=state.approved_by,
        approved_at=state.approved_at,
        updated_at=state.updated_at,
        history=state.history,
    )
