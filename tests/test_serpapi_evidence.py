from decimal import Decimal

from src.contracts.travel_v1 import EvidenceSourceStatus, EvidenceType
from src.providers.serpapi_evidence import (
    build_evidence_pack,
    normalize_flights_response,
    normalize_hotels_response,
    normalize_iata_code,
)


def test_invalid_iata_never_falls_back_to_tlv():
    assert normalize_iata_code("Rome") is None
    assert normalize_iata_code("") is None
    assert normalize_iata_code("FCO") == "FCO"


def test_flight_price_becomes_traceable_verified_evidence():
    data = {
        "search_metadata": {"id": "search-123"},
        "search_parameters": {"currency": "USD"},
        "best_flights": [{"price": 510, "total_duration": 225, "flights": [{"airline": "Example Air", "flight_number": "EA100", "departure_airport": {"id": "TLV", "time": "10:00"}, "arrival_airport": {"id": "FCO", "time": "13:45"}}]}],
    }
    record = normalize_flights_response(data)[0]
    assert record.type == EvidenceType.FLIGHT
    assert record.amount == Decimal("510")
    assert record.currency == "USD"
    assert record.source_status == EvidenceSourceStatus.VERIFIED
    assert record.provider_reference == "serpapi:search-123:best_flights:0"
    assert record.is_verified_price is True
    assert record.normalized_data["stops"] == 0


def test_missing_search_id_cannot_be_called_verified():
    data = {"search_parameters": {"currency": "USD"}, "best_flights": [{"price": 510, "flights": []}]}
    record = normalize_flights_response(data)[0]
    assert record.source_status == EvidenceSourceStatus.UNVERIFIED
    assert "provider_reference" in record.missing_fields
    assert record.is_verified_price is False


def test_hotel_rate_keeps_per_night_basis_and_provider_prices():
    data = {
        "search_metadata": {"id": "hotel-search"},
        "search_parameters": {"currency": "EUR"},
        "properties": [{"name": "Hotel Roma", "property_token": "hotel-token", "overall_rating": 4.5, "rate_per_night": {"lowest": "€ 123"}, "prices": [{"source": "Booking.com", "rate_per_night": {"lowest": "€ 130"}}, {"source": "Agoda", "rate_per_night": {"lowest": "€ 125"}}]}],
    }
    record = normalize_hotels_response(data)[0]
    assert record.type == EvidenceType.HOTEL
    assert record.amount == Decimal("123")
    assert record.currency == "EUR"
    assert record.provider_reference == "serpapi:hotel-search:hotel:hotel-token"
    assert record.normalized_data["price_basis"] == "per_night"
    assert len(record.normalized_data["source_prices"]) == 2


def test_missing_price_is_explicit_and_not_inferred():
    data = {"search_metadata": {"id": "hotel-search"}, "search_parameters": {"currency": "USD"}, "properties": [{"name": "No Price Hotel", "property_token": "x"}]}
    record = normalize_hotels_response(data)[0]
    assert record.amount is None
    assert record.currency is None
    assert record.source_status == EvidenceSourceStatus.UNVERIFIED
    assert "price" in record.missing_fields


def test_build_evidence_pack_combines_categories_under_request():
    pack = build_evidence_pack(
        "req_123",
        flights_response={"search_metadata": {"id": "f"}, "search_parameters": {"currency": "USD"}, "best_flights": [{"price": 200, "flights": []}]},
        hotels_response={"search_metadata": {"id": "h"}, "search_parameters": {"currency": "USD"}, "properties": [{"property_token": "p", "rate_per_night": {"lowest": "$80"}}]},
    )
    assert pack.request_id == "req_123"
    assert len(pack.records) == 2
