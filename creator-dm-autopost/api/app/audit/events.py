from dataclasses import dataclass, field

from fastapi import Request


@dataclass(slots=True)
class AuditEvent:
    action: str
    target_type: str
    target_id: str
    metadata: dict[str, str] = field(default_factory=dict)


def set_audit_event(
    request: Request,
    *,
    action: str,
    target_type: str,
    target_id: str,
    metadata: dict[str, str] | None = None,
) -> None:
    request.state.audit_event = AuditEvent(
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata=metadata or {},
    )
