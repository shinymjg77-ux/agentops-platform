from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.audit.events import set_audit_event
from app.metrics.generation import generation_metrics
from app.posts.draft import PostDraftInput, generate_post_draft
from app.posts.versioning import post_version_store
from app.security.rbac import Role, require_roles
from app.workflow.post_workflow import post_workflow_store

router = APIRouter(prefix="/posts", tags=["posts"])


class PostDraftRequest(BaseModel):
    persona_name: str = Field(min_length=1, max_length=120)
    persona_tone: str = Field(min_length=1, max_length=120)
    persona_topic: str = Field(min_length=1, max_length=255)
    style_sample: str = Field(default="핵심 메시지를 간결하게 전달합니다.", max_length=500)
    template: str = Field(min_length=1, max_length=3000)
    variables: dict[str, str] = Field(default_factory=dict)
    cta: str = Field(default="지금 확인하기", min_length=1, max_length=120)
    banned_keywords: list[str] = Field(default_factory=list)
    max_length: int = Field(default=2000, ge=100, le=4000)


class PostDraftResponse(BaseModel):
    content: str
    character_count: int
    max_length: int
    applied_variables: list[str]
    violations: list[str]


class PostRevisionCreateRequest(BaseModel):
    post_id: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=4000)


class PostRevisionUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class PostRevisionResponse(BaseModel):
    post_id: str
    version: int
    content: str
    edited_by: str
    edited_at: str


class PostRevisionHistoryResponse(BaseModel):
    post_id: str
    revisions: list[PostRevisionResponse]


@router.post("/draft", response_model=PostDraftResponse, summary="Generate post draft")
def generate_post_draft_endpoint(
    payload: PostDraftRequest,
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> PostDraftResponse:
    started_at = perf_counter()
    output = generate_post_draft(
        PostDraftInput(
            persona_name=payload.persona_name,
            persona_tone=payload.persona_tone,
            persona_topic=payload.persona_topic,
            style_sample=payload.style_sample,
            template=payload.template,
            variables=payload.variables,
            cta=payload.cta,
            banned_keywords=payload.banned_keywords,
            max_length=payload.max_length,
        )
    )
    elapsed_ms = int((perf_counter() - started_at) * 1000)
    generation_metrics.record_post(elapsed_ms)

    set_audit_event(
        request,
        action="post.generate_draft",
        target_type="post_draft",
        target_id=payload.persona_name,
        metadata={
            "role": role,
            "max_length": str(payload.max_length),
            "violations": str(len(output.violations)),
            "elapsed_ms": str(elapsed_ms),
        },
    )

    return PostDraftResponse(
        content=output.content,
        character_count=output.character_count,
        max_length=payload.max_length,
        applied_variables=output.applied_variables,
        violations=output.violations,
    )


@router.post("/versioned", response_model=PostRevisionResponse, summary="Create initial post revision")
def create_initial_post_revision(
    payload: PostRevisionCreateRequest,
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> PostRevisionResponse:
    actor_id = request.headers.get("X-Actor-Id", "unknown")
    try:
        revision = post_version_store.create_initial(payload.post_id, payload.content, actor_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    post_workflow_store.ensure_initialized(payload.post_id)

    set_audit_event(
        request,
        action="post.version.create_initial",
        target_type="post",
        target_id=payload.post_id,
        metadata={"role": role, "version": str(revision.version)},
    )

    return PostRevisionResponse(
        post_id=payload.post_id,
        version=revision.version,
        content=revision.content,
        edited_by=revision.edited_by,
        edited_at=revision.edited_at,
    )


@router.post("/{post_id}/revisions", response_model=PostRevisionResponse, summary="Append post revision")
def append_post_revision(
    post_id: str,
    payload: PostRevisionUpdateRequest,
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> PostRevisionResponse:
    actor_id = request.headers.get("X-Actor-Id", "unknown")
    try:
        revision = post_version_store.append_revision(post_id, payload.content, actor_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    set_audit_event(
        request,
        action="post.version.append",
        target_type="post",
        target_id=post_id,
        metadata={"role": role, "version": str(revision.version)},
    )

    return PostRevisionResponse(
        post_id=post_id,
        version=revision.version,
        content=revision.content,
        edited_by=revision.edited_by,
        edited_at=revision.edited_at,
    )


@router.get(
    "/{post_id}/revisions",
    response_model=PostRevisionHistoryResponse,
    summary="Get post revision history",
)
def get_post_revision_history(
    post_id: str,
    request: Request,
    role: Role = Depends(require_roles(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> PostRevisionHistoryResponse:
    try:
        revisions = post_version_store.get_revisions(post_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    set_audit_event(
        request,
        action="post.version.history.read",
        target_type="post",
        target_id=post_id,
        metadata={"role": role, "count": str(len(revisions))},
    )

    return PostRevisionHistoryResponse(
        post_id=post_id,
        revisions=[PostRevisionResponse(post_id=post_id, **item) for item in revisions],
    )
