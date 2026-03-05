from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class AuditLogEntry:
    actor_id: str
    action: str
    target_type: str
    target_id: str
    timestamp: str
    metadata: dict[str, str]


class InMemoryAuditLogStore:
    def __init__(self) -> None:
        self._entries: list[AuditLogEntry] = []

    def append(
        self,
        *,
        actor_id: str,
        action: str,
        target_type: str,
        target_id: str,
        metadata: dict[str, str],
    ) -> None:
        self._entries.append(
            AuditLogEntry(
                actor_id=actor_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                timestamp=datetime.now(UTC).isoformat(),
                metadata=metadata,
            )
        )

    def list_entries(
        self,
        *,
        limit: int = 100,
        action: str | None = None,
        target_type: str | None = None,
    ) -> list[dict[str, str | dict[str, str]]]:
        filtered = self._entries
        if action:
            filtered = [item for item in filtered if item.action == action]
        if target_type:
            filtered = [item for item in filtered if item.target_type == target_type]

        sliced = filtered[-limit:]
        return [asdict(item) for item in reversed(sliced)]


audit_log_store = InMemoryAuditLogStore()
