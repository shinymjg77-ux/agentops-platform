from abc import ABC, abstractmethod

from app.dm.types import DMDeliveryRequest, DMDeliveryResult


class DMProvider(ABC):
    provider_name: str

    @abstractmethod
    def validate_config(self) -> None:
        """Validate provider credentials/config before runtime use."""

    @abstractmethod
    async def send_dm(self, request: DMDeliveryRequest) -> DMDeliveryResult:
        """Send a direct message through provider API."""
