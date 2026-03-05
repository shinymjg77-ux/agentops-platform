import re
from dataclasses import dataclass

from app.posts.validation import sanitize_banned_keywords, validate_draft


class _SafeTemplateDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


@dataclass(slots=True)
class PostDraftInput:
    persona_name: str
    persona_tone: str
    persona_topic: str
    style_sample: str
    template: str
    variables: dict[str, str]
    cta: str
    banned_keywords: list[str]
    max_length: int


@dataclass(slots=True)
class PostDraftOutput:
    content: str
    character_count: int
    applied_variables: list[str]
    violations: list[str]


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def generate_post_draft(payload: PostDraftInput) -> PostDraftOutput:
    rendered_template = payload.template.format_map(_SafeTemplateDict(payload.variables))
    rendered_template = _normalize_space(rendered_template)

    draft = (
        f"[{payload.persona_name}] {payload.persona_tone}\n"
        f"주제: {payload.persona_topic}\n"
        f"메시지: {rendered_template}\n"
        f"스타일: {payload.style_sample}\n"
        f"CTA: {payload.cta}"
    )

    sanitized = sanitize_banned_keywords(draft, payload.banned_keywords)
    if len(sanitized) > payload.max_length:
        sanitized = sanitized[: payload.max_length]

    validation = validate_draft(
        content=sanitized,
        banned_keywords=payload.banned_keywords,
        max_length=payload.max_length,
        expected_tone=payload.persona_tone,
    )

    return PostDraftOutput(
        content=sanitized,
        character_count=len(sanitized),
        applied_variables=sorted(payload.variables.keys()),
        violations=validation.violations,
    )
