from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.contracts.travel_v1 import (
    ConsentStatus,
    CreatedByType,
    CustomerContact,
    FlightRoutingPreference,
    TripPreferences,
    TripRequest,
)
from src.providers.serpapi_client_v1 import SERPAPI_URL, SerpApiClientV1


def request(routing=FlightRoutingPreference.NONSTOP):
    start = date.today() + timedelta(days=20)
    return TripRequest(
        created_by_type=CreatedByType.CUSTOMER,
        customer=CustomerContact(name="Private Name", email="private@example.com"),
        origin="Tel Aviv",
        destination="Rome",
        departure_date=start,
        return_date=start + timedelta(days=5),
        budget=Decimal("5000"),
        currency="ILS",
        consent_status=ConsentStatus.GRANTED,
        preferences=TripPreferences(flight_routing=routing),
    )


def fake_response(payload):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def test_round_trip_params_and_pii_minimization():
    session = MagicMock()
    session.get.side_effect = [fake_response({"search_metadata": {"id": "f"}, "best_flights": []}), fake_response({"search_metadata": {"id": "h"}, "properties": []})]
    req = request()
    client = SerpApiClientV1("test-key", session=session)
    pack = client.search_evidence(req, origin_iata="TLV", destination_iata="FCO")
    assert pack.request_id == req.request_id
    assert session.get.call_count == 4  # original flight + hotel + relaxed stops + alternate airport
    flight_call = session.get.call_args_list[0]
    assert flight_call.args[0] == SERPAPI_URL
    params = flight_call.kwargs["params"]
    assert params["type"] == 1
    assert params["return_date"] == req.return_date.isoformat()
    assert params["stops"] == 1
    serialized = str(params)
    assert "Private Name" not in serialized
    assert "private@example.com" not in serialized


def test_one_stop_maps_to_serpapi_stops_2():
    session = MagicMock()
    session.get.side_effect = [fake_response({"best_flights": []}), fake_response({"properties": []})]
    req = request(FlightRoutingPreference.ONE_STOP)
    SerpApiClientV1("test-key", session=session).search_evidence(req, origin_iata="TLV", destination_iata="FCO")
    assert session.get.call_args_list[0].kwargs["params"]["stops"] == 2


def test_any_stops_maps_to_zero():
    session = MagicMock()
    session.get.side_effect = [fake_response({"best_flights": []}), fake_response({"properties": []})]
    req = request(FlightRoutingPreference.ANY)
    SerpApiClientV1("test-key", session=session).search_evidence(req, origin_iata="TLV", destination_iata="FCO")
    assert session.get.call_args_list[0].kwargs["params"]["stops"] == 0


def test_invalid_or_same_iata_fails_before_network():
    session = MagicMock()
    client = SerpApiClientV1("test-key", session=session)
    req = request()
    with pytest.raises(ValueError):
        client.search_evidence(req, origin_iata="Tel Aviv", destination_iata="FCO")
    with pytest.raises(ValueError):
        client.search_evidence(req, origin_iata="TLV", destination_iata="TLV")
    session.get.assert_not_called()


def test_api_key_is_not_copied_into_evidence_search_parameters():
    session = MagicMock()
    session.get.side_effect = [fake_response({"search_metadata": {"id": "f"}, "best_flights": [{"price": 100, "flights": []}]}), fake_response({"search_metadata": {"id": "h"}, "properties": []})]
    req = request()
    pack = SerpApiClientV1("super-secret-key", session=session).search_evidence(req, origin_iata="TLV", destination_iata="FCO")
    assert pack.records
    assert "super-secret-key" not in pack.model_dump_json()
