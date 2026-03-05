import hashlib
import random
import re
from time import perf_counter

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.audit.events import set_audit_event
from app.metrics.generation import generation_metrics
from app.security.rbac import Role, require_roles

router = APIRouter(prefix="/creators", tags=["creators"])


class CreatorGenerationRequest(BaseModel):
    campaign_goal: str = Field(min_length=1, max_length=500)
    target_segment: str = Field(min_length=1, max_length=200)
    banned_keywords: list[str] = Field(default_factory=list)
    channel_constraints: list[str] = Field(default_factory=list)
    count: int = Field(default=5, ge=1, le=10)
    diversity_mode: str = Field(default="balanced", pattern="^(balanced|wide|focused)$")
    seed: str | None = None


class CreatorPersona(BaseModel):
    name: str
    tone: str
    topic: str
    style_sample: str


class CreatorGenerationResponse(BaseModel):
    requested_count: int
    generated_count: int
    elapsed_ms: int
    personas: list[CreatorPersona]


def _clean_tokens(text: str) -> list[str]:
    return [tok for tok in re.findall(r"[A-Za-z0-9가-힣]+", text.lower()) if len(tok) >= 2]


def _contains_banned(text: str, banned: set[str]) -> bool:
    lowered = text.lower()
    return any(word and word in lowered for word in banned)


def _topic_candidates(goal: str, segment: str, constraints: list[str], banned: set[str]) -> list[str]:
    base = [
        "문제 해결형 가이드",
        "비교/선택 포인트",
        "빠른 시작 체크리스트",
        "실전 사용 시나리오",
        "자주 발생하는 실수와 회피법",
        "성과 개선 팁",
        "초보자 입문 요약",
        "고급 사용자 최적화",
    ]

    tokens = _clean_tokens(goal)[:3] + _clean_tokens(segment)[:2]
    dynamic = [f"{' '.join(tokens)} 핵심 포인트".strip(), f"{segment} 맞춤 운영 팁"]
    if constraints:
        dynamic.append(f"채널 제약 고려: {constraints[0]}")

    candidates: list[str] = []
    for item in dynamic + base:
        if item and not _contains_banned(item, banned):
            candidates.append(item)

    if not candidates:
        candidates = ["일반 운영 가이드", "핵심 요약"]
    return candidates


def _build_rng(payload: CreatorGenerationRequest) -> random.Random:
    seed_text = payload.seed or "|".join(
        [
            payload.campaign_goal,
            payload.target_segment,
            str(payload.count),
            payload.diversity_mode,
        ]
    )
    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _generate_personas(payload: CreatorGenerationRequest) -> list[CreatorPersona]:
    banned = {word.strip().lower() for word in payload.banned_keywords if word.strip()}
    rng = _build_rng(payload)

    first_names = ["Nova", "Rin", "Milo", "Ara", "Juno", "Theo", "Lia", "Kai", "Sora", "Evan"]
    last_names = ["Studio", "Lab", "Works", "Crew", "Flow", "Forge", "Pulse", "Frame", "Spot", "Wave"]

    tones_by_mode: dict[str, list[str]] = {
        "focused": ["직설적", "전문가형", "데이터 중심"],
        "balanced": ["친근한 실무형", "명확한 설명형", "신뢰감 있는 코치형"],
        "wide": ["스토리텔링형", "도발적 인사이트형", "실험가형"],
    }

    tones = tones_by_mode[payload.diversity_mode]
    topics = _topic_candidates(payload.campaign_goal, payload.target_segment, payload.channel_constraints, banned)

    personas: list[CreatorPersona] = []
    used_names: set[str] = set()

    idx = 0
    while len(personas) < payload.count and idx < payload.count * 12:
        idx += 1
        first = first_names[(idx + rng.randint(0, 100)) % len(first_names)]
        last = last_names[(idx + rng.randint(0, 100)) % len(last_names)]
        name = f"{first} {last}"
        if name in used_names:
            continue

        tone = tones[(idx + rng.randint(0, 100)) % len(tones)]
        topic = topics[(idx + rng.randint(0, 100)) % len(topics)]
        style = f"{payload.target_segment}를 위해 핵심만 짧고 명확하게 전달합니다."

        combined = f"{name} {tone} {topic} {style}"
        if _contains_banned(combined, banned):
            continue

        personas.append(
            CreatorPersona(
                name=name,
                tone=tone,
                topic=topic,
                style_sample=style,
            )
        )
        used_names.add(name)

    if len(personas) < payload.count:
        for extra in range(payload.count - len(personas)):
            personas.append(
                CreatorPersona(
                    name=f"Fallback Creator {extra + 1}",
                    tone="실무형",
                    topic="기본 운영 가이드",
                    style_sample="핵심 메시지를 간결하게 전달합니다.",
                )
            )

    return personas


@router.post("/generate", response_model=CreatorGenerationResponse, summary="Generate creator personas")
def generate_creator_personas(
    payload: CreatorGenerationRequest,
    request: Request,
    role: Role = Depends(require_roles(Role.OPERATOR, Role.ADMIN)),
) -> CreatorGenerationResponse:
    started_at = perf_counter()
    personas = _generate_personas(payload)
    elapsed_ms = int((perf_counter() - started_at) * 1000)
    generation_metrics.record_creator(elapsed_ms)

    set_audit_event(
        request,
        action="creator.generate",
        target_type="creator_batch",
        target_id=f"generated:{len(personas)}",
        metadata={
            "role": role,
            "target_segment": payload.target_segment,
            "requested_count": str(payload.count),
        },
    )

    return CreatorGenerationResponse(
        requested_count=payload.count,
        generated_count=len(personas),
        elapsed_ms=elapsed_ms,
        personas=personas,
    )
