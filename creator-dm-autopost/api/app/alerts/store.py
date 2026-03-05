from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class FailureAlert:
    delivery_id: str
    error_code: str
    category: str
    severity: str
    created_at: str


def classify_error_code(error_code: str) -> tuple[str, str]:
    if "429" in error_code:
        return "rate_limit", "warning"
    if any(code in error_code for code in ["500", "502", "503", "504", "timeout", "http_error"]):
        return "provider_transient", "warning"
    if "400" in error_code:
        return "provider_fatal", "critical"
    return "unknown", "warning"


class InMemoryAlertStore:
    def __init__(self) -> None:
        self._failure_alerts: list[FailureAlert] = []

    def add_failure(self, *, delivery_id: str, error_code: str) -> FailureAlert:
        category, severity = classify_error_code(error_code)
        item = FailureAlert(
            delivery_id=delivery_id,
            error_code=error_code,
            category=category,
            severity=severity,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._failure_alerts.append(item)
        return item

    def list_failures(self, *, limit: int = 100) -> list[dict[str, str]]:
        return [asdict(item) for item in reversed(self._failure_alerts[-limit:])]


alert_store = InMemoryAlertStore()
