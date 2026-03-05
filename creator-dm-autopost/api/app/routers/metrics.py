from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.metrics.generation import generation_metrics
from app.security.rbac import Role, require_roles

router = APIRouter(prefix="/metrics", tags=["metrics"])


class GenerationMetricsResponse(BaseModel):
    creator_count: int
    creator_p95_ms: int
    post_count: int
    post_p95_ms: int


@router.get("/generation", response_model=GenerationMetricsResponse, summary="Generation metrics snapshot")
def get_generation_metrics(
    _role: Role = Depends(require_roles(Role.VIEWER, Role.OPERATOR, Role.ADMIN)),
) -> GenerationMetricsResponse:
    return GenerationMetricsResponse(**generation_metrics.snapshot())
