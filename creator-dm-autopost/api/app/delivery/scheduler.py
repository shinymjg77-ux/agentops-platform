from datetime import UTC, datetime

from app.alerts.store import alert_store
from app.delivery.store import delivery_store
from app.dm.discord import DiscordDMProvider
from app.dm.types import DMDeliveryRequest


def _is_retryable_error(error_code: str | None) -> bool:
    if not error_code:
        return False
    return (
        "_429" in error_code
        or "_500" in error_code
        or "_502" in error_code
        or "_503" in error_code
        or "_504" in error_code
        or error_code in {"discord_timeout", "discord_http_error", "dispatch_error"}
    )


async def process_due_deliveries(*, force_process: bool = False, limit: int = 50) -> dict[str, int]:
    now = datetime.now(UTC)
    due = delivery_store.list_due(now, force_process=force_process, limit=limit)

    provider = DiscordDMProvider()
    summary = {"processed": 0, "sent": 0, "retrying": 0, "failed": 0}

    for record in due:
        summary["processed"] += 1
        if record.status == "retrying":
            delivery_store.mark_queued_from_retrying(record)
        delivery_store.mark_sending(record)

        try:
            result = await provider.send_dm(
                DMDeliveryRequest(
                    recipient_id=record.recipient_id,
                    content=record.content,
                    idempotency_key=record.idempotency_key,
                )
            )
        except Exception:
            result = None

        if result and result.ok:
            delivery_store.mark_sent(record)
            summary["sent"] += 1
            continue

        error_code = (result.error_code if result else None) or "dispatch_error"

        if _is_retryable_error(error_code) and record.attempts < 2:
            delivery_store.mark_retrying(record, error_code)
            summary["retrying"] += 1
        else:
            delivery_store.mark_failed(record, error_code)
            alert_store.add_failure(delivery_id=record.delivery_id, error_code=error_code)
            summary["failed"] += 1

    return summary
