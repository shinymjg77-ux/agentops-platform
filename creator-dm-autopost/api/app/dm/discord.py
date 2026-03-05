import asyncio

import httpx

from app.core.config import settings
from app.dm.provider import DMProvider
from app.dm.types import DMDeliveryRequest, DMDeliveryResult


class DiscordDMProvider(DMProvider):
    provider_name = "discord"

    def __init__(self) -> None:
        self._base_url = settings.discord_api_base_url.rstrip("/")
        self._bot_token = settings.discord_bot_token
        self._dry_run = settings.discord_dm_dry_run

    def validate_config(self) -> None:
        if self._dry_run:
            return
        if not self._bot_token:
            raise ValueError("discord_bot_token_missing")

    async def send_dm(self, request: DMDeliveryRequest) -> DMDeliveryResult:
        self.validate_config()

        # Deterministic test hooks for retry/failure behavior.
        if "[force:429]" in request.content:
            return DMDeliveryResult(ok=False, error_code="discord_send_429")
        if "[force:500]" in request.content:
            return DMDeliveryResult(ok=False, error_code="discord_send_500")
        if "[force:fatal]" in request.content:
            return DMDeliveryResult(ok=False, error_code="discord_send_400")

        if self._dry_run:
            await asyncio.sleep(0)
            return DMDeliveryResult(ok=True, provider_message_id=f"dryrun:{request.idempotency_key}")

        headers = {
            "Authorization": f"Bot {self._bot_token}",
            "Content-Type": "application/json",
            "X-Audit-Log-Reason": f"idempotency:{request.idempotency_key}",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                channel_res = await client.post(
                    f"{self._base_url}/users/@me/channels",
                    headers=headers,
                    json={"recipient_id": request.recipient_id},
                )
                if channel_res.status_code >= 400:
                    return DMDeliveryResult(
                        ok=False,
                        error_code=f"discord_channel_create_{channel_res.status_code}",
                        error_message=channel_res.text[:500],
                    )

                channel_id = channel_res.json().get("id")
                if not channel_id:
                    return DMDeliveryResult(ok=False, error_code="discord_channel_id_missing")

                message_res = await client.post(
                    f"{self._base_url}/channels/{channel_id}/messages",
                    headers=headers,
                    json={"content": request.content},
                )
                if message_res.status_code >= 400:
                    return DMDeliveryResult(
                        ok=False,
                        error_code=f"discord_send_{message_res.status_code}",
                        error_message=message_res.text[:500],
                    )

                message_id = message_res.json().get("id")
                return DMDeliveryResult(ok=True, provider_message_id=message_id)
        except httpx.TimeoutException as exc:
            return DMDeliveryResult(ok=False, error_code="discord_timeout", error_message=str(exc))
        except httpx.HTTPError as exc:
            return DMDeliveryResult(ok=False, error_code="discord_http_error", error_message=str(exc))
