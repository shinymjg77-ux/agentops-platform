from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(slots=True)
class ConsentRecord:
    recipient_id: str
    status: str
    source: str
    proof_ref: str | None
    updated_at: str


class InMemoryConsentStore:
    def __init__(self) -> None:
        self._storage: dict[str, ConsentRecord] = {}

    def upsert(self, recipient_id: str, status: str, source: str, proof_ref: str | None) -> ConsentRecord:
        now = datetime.now(UTC).isoformat()
        record = ConsentRecord(
            recipient_id=recipient_id,
            status=status,
            source=source,
            proof_ref=proof_ref,
            updated_at=now,
        )
        self._storage[recipient_id] = record
        return record

    def get(self, recipient_id: str) -> ConsentRecord | None:
        return self._storage.get(recipient_id)


consent_store = InMemoryConsentStore()
