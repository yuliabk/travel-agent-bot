from src.core import travel_tools
from src.runtime.flight_capability_runtime_v1 import SandboxFlightCapabilityInvokerV1


def test_legacy_channel_flight_function_routes_through_canonical_capability(monkeypatch):
    calls = []

    def fake_invoke(self, capability_ref, payload):
        calls.append((capability_ref, dict(payload)))
        return {
            "status": "complete",
            "searchId": "manual-test-1",
            "observedAt": "2026-09-06T17:30:00Z",
            "options": [
                {
                    "optionId": "opt-1",
                    "carrierText": "Aegean Airlines",
                    "departureText": "2026-10-20 10:00 TLV",
                    "arrivalText": "2026-10-20 12:10 ATH",
                    "durationText": "2h 10m",
                    "stops": 0,
                    "price": {
                        "displayText": "USD 199",
                        "amount": "199",
                        "currency": "USD",
                    },
                    "isBest": True,
                    "bookingReady": False,
                    "evidenceStatus": "observed",
                    "sourceRef": None,
                }
            ],
            "limitations": [],
        }

    monkeypatch.setattr(SandboxFlightCapabilityInvokerV1, "invoke", fake_invoke)

    flights = travel_tools.search_flights_google(
        origin="TLV",
        destination="ATH",
        departure_date="2026-10-20",
        return_date="2026-10-25",
        adults=2,
        children=1,
        currency="USD",
    )

    assert calls[0][0] == "travel.flight.search"
    request = calls[0][1]
    assert request["originIata"] == "TLV"
    assert request["destinationIata"] == "ATH"
    assert request["tripType"] == "round-trip"
    assert request["returnDate"] == "2026-10-25"
    assert request["adults"] == 2
    assert request["children"] == 1
    assert "apiKey" not in request
    assert "provider" not in request

    assert flights == [
        {
            "airline": "Aegean Airlines",
            "price": "USD 199",
            "departure_time": "2026-10-20 10:00 TLV",
            "arrival_time": "2026-10-20 12:10 ATH",
            "type": "טיסה ישירה",
            "booking_ready": False,
            "evidence_status": "observed",
        }
    ]
