from dataclasses import dataclass


@dataclass(slots=True)
class DMDeliveryRequest:
    recipient_id: str
    content: str
    idempotency_key: str


@dataclass(slots=True)
class DMDeliveryResult:
    ok: bool
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
