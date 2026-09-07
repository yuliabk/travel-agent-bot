"""Config-driven provider selection for ``travel.hotel.search@1``."""

from __future__ import annotations

from typing import Optional

from src.capabilities.hotel_search_v1 import HotelSearchConsumerV1
from src.core import config
from src.providers.booking_mcp_provider_v1 import BookingMcpProvider


def configured_hotel_search() -> Optional[HotelSearchConsumerV1]:
    """Return the configured hotel capability consumer or fail closed.

    Provider choice is deployment configuration only. Callers never pass a
    provider selector through the public travel request.
    """
    provider = config.HOTEL_PROVIDER.strip().lower()
    if provider in {"", "none", "disabled"}:
        return None
    if provider == "booking_mcp":
        if not config.BOOKING_MCP_API_KEY:
            return None
        return HotelSearchConsumerV1(
            BookingMcpProvider(
                config.BOOKING_MCP_API_KEY,
                endpoint=config.BOOKING_MCP_URL,
                timeout=config.BOOKING_MCP_TIMEOUT_SECONDS,
            )
        )
    raise ValueError(f"unsupported hotel provider configuration: {provider}")
