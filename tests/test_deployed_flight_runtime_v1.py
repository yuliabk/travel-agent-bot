from types import SimpleNamespace

import pytest

from src.runtime import flight_capability_runtime_v1 as runtime


class ResultList(list):
    pass


def payload():
    return {
        "originIata": "TLV",
        "destinationIata": "ATH",
        "departureDate": "2026-10-20",
        "returnDate": "2026-10-25",
        "tripType": "round-trip",
        "adults": 1,
        "children": 0,
        "cabin": "economy",
        "currency": "USD",
        "maxStops": 1,
        "maxResults": 3,
    }


def test_bridge_invokes_only_canonical_flight_capability(monkeypatch):
    with pytest.raises(ValueError):
        runtime.SandboxFlightCapabilityInvokerV1().invoke("web.search", payload())

    segment = SimpleNamespace(
        from_airport=SimpleNamespace(code="TLV", name="Ben Gurion"),
        to_airport=SimpleNamespace(code="ATH", name="Athens"),
        departure=SimpleNamespace(date=(2026, 10, 20), time=(10, 0)),
        arrival=SimpleNamespace(date=(2026, 10, 20), time=(12, 10)),
        duration=130,
    )
    option = SimpleNamespace(
        price=199,
        airlines=["A3"],
        flights=[segment],
        rank=0,
    )
    result_list = ResultList([option])
    result_list.metadata = SimpleNamespace(
        airlines=[SimpleNamespace(code="A3", name="Aegean Airlines")]
    )
    monkeypatch.setattr(runtime, "get_flights", lambda query: result_list)

    result = runtime.SandboxFlightCapabilityInvokerV1().invoke(
        "travel.flight.search",
        payload(),
    )

    assert result["status"] == "complete"
    assert len(result["options"]) == 1
    observed = result["options"][0]
    assert observed["carrierText"] == "Aegean Airlines"
    assert observed["price"]["amount"] == "199"
    assert observed["price"]["currency"] == "USD"
    assert observed["bookingReady"] is False
    assert observed["evidenceStatus"] == "observed"
    assert "temporary in-process flight capability bridge" in " ".join(result["limitations"])
