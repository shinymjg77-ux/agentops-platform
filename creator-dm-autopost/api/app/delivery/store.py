from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from itertools import count

from app.workflow.state_machine import DeliveryStatus, validate_delivery_transition


@dataclass(slots=True)
class DeliveryRecord:
    delivery_id: str
    post_id: str
    recipient_id: str
    content: str
    status: str
    error_code: str | None
    attempts: int
    idempotency_key: str
    scheduled_at: datetime
    next_attempt_at: datetime
    created_at: datetime
    sent_at: datetime | None


class InMemoryDeliveryStore:
    def __init__(self) -> None:
        self._counter = count(1)
        self._by_id: dict[str, DeliveryRecord] = {}
        self._by_idempotency: dict[str, str] = {}

    def create(
        self,
        *,
        post_id: str,
        recipient_id: str,
        content: str,
        scheduled_at: datetime,
        idempotency_key: str,
    ) -> tuple[DeliveryRecord, bool]:
        existing_id = self._by_idempotency.get(idempotency_key)
        if existing_id:
            return self._by_id[existing_id], True

        now = datetime.now(UTC)
        delivery_id = f"d-{next(self._counter)}"
        record = DeliveryRecord(
            delivery_id=delivery_id,
            post_id=post_id,
            recipient_id=recipient_id,
            content=content,
            status=DeliveryStatus.QUEUED,
            error_code=None,
            attempts=0,
            idempotency_key=idempotency_key,
            scheduled_at=scheduled_at,
            next_attempt_at=scheduled_at,
            created_at=now,
            sent_at=None,
        )
        self._by_id[delivery_id] = record
        self._by_idempotency[idempotency_key] = delivery_id
        return record, False

    def get_by_id(self, delivery_id: str) -> DeliveryRecord:
        found = self._by_id.get(delivery_id)
        if not found:
            raise KeyError("delivery_not_found")
        return found

    def get_by_idempotency(self, idempotency_key: str) -> DeliveryRecord:
        delivery_id = self._by_idempotency.get(idempotency_key)
        if not delivery_id:
            raise KeyError("delivery_not_found")
        return self._by_id[delivery_id]

    def list_due(self, now: datetime, *, force_process: bool = False, limit: int = 50) -> list[DeliveryRecord]:
        due: list[DeliveryRecord] = []
        for record in self._by_id.values():
            if record.status not in {DeliveryStatus.QUEUED, DeliveryStatus.RETRYING}:
                continue
            if force_process or (record.scheduled_at <= now and record.next_attempt_at <= now):
                due.append(record)
            if len(due) >= limit:
                break
        return due

    def mark_sending(self, record: DeliveryRecord) -> None:
        validate_delivery_transition(record.status, DeliveryStatus.SENDING)
        record.status = DeliveryStatus.SENDING

    def mark_queued_from_retrying(self, record: DeliveryRecord) -> None:
        validate_delivery_transition(record.status, DeliveryStatus.QUEUED)
        record.status = DeliveryStatus.QUEUED

    def mark_sent(self, record: DeliveryRecord) -> None:
        validate_delivery_transition(record.status, DeliveryStatus.SENT)
        record.status = DeliveryStatus.SENT
        record.sent_at = datetime.now(UTC)
        record.error_code = None

    def mark_retrying(self, record: DeliveryRecord, error_code: str) -> None:
        validate_delivery_transition(record.status, DeliveryStatus.RETRYING)
        record.attempts += 1
        record.status = DeliveryStatus.RETRYING
        record.error_code = error_code
        backoff_seconds = 2 ** record.attempts
        record.next_attempt_at = datetime.now(UTC) + timedelta(seconds=backoff_seconds)

    def mark_failed(self, record: DeliveryRecord, error_code: str) -> None:
        validate_delivery_transition(record.status, DeliveryStatus.FAILED)
        record.attempts += 1
        record.status = DeliveryStatus.FAILED
        record.error_code = error_code

    @staticmethod
    def as_dict(record: DeliveryRecord) -> dict[str, str | int | None]:
        payload = asdict(record)
        payload["scheduled_at"] = record.scheduled_at.isoformat()
        payload["next_attempt_at"] = record.next_attempt_at.isoformat()
        payload["created_at"] = record.created_at.isoformat()
        payload["sent_at"] = record.sent_at.isoformat() if record.sent_at else None
        return payload

    def status_summary(self, *, failure_limit: int = 20) -> dict[str, object]:
        counts = {
            DeliveryStatus.QUEUED: 0,
            DeliveryStatus.SENDING: 0,
            DeliveryStatus.SENT: 0,
            DeliveryStatus.FAILED: 0,
            DeliveryStatus.RETRYING: 0,
            DeliveryStatus.CANCELLED: 0,
        }

        failures: list[dict[str, object]] = []
        for record in self._by_id.values():
            counts[record.status] += 1
            if record.error_code:
                failures.append(
                    {
                        "delivery_id": record.delivery_id,
                        "status": record.status,
                        "error_code": record.error_code,
                        "attempts": record.attempts,
                        "created_at": record.created_at.isoformat(),
                    }
                )

        failures.sort(key=lambda item: str(item["created_at"]), reverse=True)
        total = sum(counts.values())
        return {
            "total": total,
            "queued": counts[DeliveryStatus.QUEUED],
            "sending": counts[DeliveryStatus.SENDING],
            "sent": counts[DeliveryStatus.SENT],
            "failed": counts[DeliveryStatus.FAILED],
            "retrying": counts[DeliveryStatus.RETRYING],
            "cancelled": counts[DeliveryStatus.CANCELLED],
            "recent_failures": failures[:failure_limit],
        }


delivery_store = InMemoryDeliveryStore()
