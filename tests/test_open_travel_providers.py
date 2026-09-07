import json
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from src.contracts.travel_v1 import (
    ConsentStatus, CreatedByType, CustomerContact, EvidenceSourceStatus,
    EvidenceType, TripRequest,
)
from src.providers.octotrip_rental_cars_v1 import OctoTripRentalCarsClientV1
from src.providers.wikidata_attractions_v1 import WikidataAttractionsClientV1
from src.runtime.planner_v1 import PlannerDay, PlannerNarrative, build_proposal_draft


def request():
    start = date.today() + timedelta(days=30)
    return TripRequest(
        created_by_type=CreatedByType.CUSTOMER,
        customer=CustomerContact(name="Test", email="test@example.com"),
        origin="Tel Aviv", destination="Rome", arrival_airport="FCO",
        departure_date=start, return_date=start + timedelta(days=4),
        budget=Decimal("5000"), currency="EUR",
        consent_status=ConsentStatus.GRANTED,
    )


class Response:
    def __init__(self, data, *, sse=False):
        self.data = data
        self.headers = {"content-type": "text/event-stream" if sse else "application/json"}
        self.text = f"data: {json.dumps(data)}\n\n" if sse else json.dumps(data)

    def json(self):
        return self.data

    def raise_for_status(self):
        return None


def test_octotrip_mcp_normalizes_observed_quotes_and_never_verifies_them():
    data = {
        "results": [
            {"name": "Fiat 500", "vendor": "Vendor", "category": "Mini", "price": 140.5,
             "price_per_day": 35.1, "currency": "EUR", "transmission": "manual",
             "booking_url": "https://example.test/car", "free_cancellation": True},
        ],
        "pickup_location_resolved": "Rome Fiumicino", "dropoff_location_resolved": "Rome Fiumicino",
        "rental_days": 4,
    }
    message = {"jsonrpc": "2.0", "id": "x", "result": {"content": [{"type": "text", "text": json.dumps(data)}]}}
    session = SimpleNamespace(post=lambda *args, **kwargs: Response(message, sse=True))
    records = OctoTripRentalCarsClientV1(session=session).search_rental_cars(request())
    assert len(records) == 1
    assert records[0].type == EvidenceType.TRANSPORT
    assert records[0].source_status == EvidenceSourceStatus.UNVERIFIED
    assert records[0].amount == Decimal("140.5")
    assert records[0].normalized_data["booking_ready"] is False

    from src.contracts.travel_v1 import EvidencePack
    req = request(); records = OctoTripRentalCarsClientV1(session=session).search_rental_cars(req)
    proposal = build_proposal_draft(req, EvidencePack(request_id=req.request_id, records=records), narrative=None, model_version="off")
    assert proposal.transport_options[0]["price_status"] == "observed"
    assert proposal.transport_options[0]["observed_amount"] == "140.5"


def test_wikidata_lookup_returns_official_link_without_inventing_admission_price():
    def get(url, *, params, **kwargs):
        if params["action"] == "wbsearchentities":
            return Response({"search": [{"id": "Q243", "label": "Colosseum", "description": "amphitheatre in Rome"}]})
        return Response({"entities": {"Q243": {"claims": {"P856": [{"mainsnak": {"datavalue": {"value": "https://colosseo.it/"}}}]}}}})

    client = WikidataAttractionsClientV1(session=SimpleNamespace(get=get))
    narrative = PlannerNarrative(summary="Trip", days=[PlannerDay(
        day_number=1, title="Rome", summary="Visit", location="Rome", attractions=["Colosseum"]
    )])
    records = client.search_attractions(request(), narrative)
    assert len(records) == 1
    assert records[0].normalized_data["official_url"] == "https://colosseo.it/"
    assert records[0].normalized_data["admission_price_status"] == "unknown"
    assert records[0].amount is None
