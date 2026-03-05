import re
from dataclasses import dataclass


@dataclass(slots=True)
class DraftValidationResult:
    violations: list[str]

    @property
    def is_valid(self) -> bool:
        return not self.violations


def sanitize_banned_keywords(text: str, banned_keywords: list[str]) -> str:
    sanitized = text
    for keyword in banned_keywords:
        token = keyword.strip()
        if not token:
            continue
        sanitized = re.sub(re.escape(token), "[filtered]", sanitized, flags=re.IGNORECASE)
    return sanitized


def validate_draft(
    *,
    content: str,
    banned_keywords: list[str],
    max_length: int,
    expected_tone: str,
) -> DraftValidationResult:
    violations: list[str] = []

    lowered = content.lower()
    for keyword in banned_keywords:
        token = keyword.strip().lower()
        if token and token in lowered:
            violations.append(f"banned_keyword:{token}")

    if len(content) > max_length:
        violations.append("length_exceeded")

    if expected_tone.strip() and expected_tone not in content:
        violations.append("tone_not_reflected")

    return DraftValidationResult(violations=violations)
