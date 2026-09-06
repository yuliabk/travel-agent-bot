import os
from datetime import date, timedelta

import pytest

from src.runtime.flight_capability_runtime_v1 import SandboxFlightCapabilityInvokerV1


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_FLIGHT_BRIDGE") != "1",
    reason="live Travel flight bridge smoke disabled",
)


def test_live_travel_runtime_bridge_returns_observed_flight():
    departure = (date.today() + timedelta(days=45)).isoformat()
    result = SandboxFlightCapabilityInvokerV1().invoke(
        "travel.flight.search",
        {
            "originIata": "TLV",
            "destinationIata": "ATH",
            "departureDate": departure,
            "returnDate": None,
            "tripType": "one-way",
            "adults": 1,
            "children": 0,
            "cabin": "economy",
            "currency": "USD",
            "maxStops": 1,
            "maxResults": 3,
        },
    )

    assert result["status"] == "complete", result["limitations"]
    assert result["options"]
    assert all(option["bookingReady"] is False for option in result["options"])
    assert all(option["evidenceStatus"] == "observed" for option in result["options"])
