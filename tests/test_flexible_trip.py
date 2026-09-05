from datetime import timedelta
from unittest.mock import MagicMock
import pytest
from src.contracts.travel_v1 import StaySegment, TripRequest, EvidenceType
from src.providers.serpapi_client_v1 import SerpApiClientV1
from src.runtime.planner_v1 import build_proposal_draft, PlannerNarrative, build_planning_context
from src.runtime.renderer_v1 import render_ai_draft_hebrew
from src.api.v1 import destination_lookup, DestinationLookupRequest
from tests.test_serpapi_client_v1 import request, fake_response


def split_request():
    req = request()
    return TripRequest.model_validate({**req.model_dump(), 'arrival_airport': 'WAW', 'stays': [
        {'destination': 'Wroclaw, Poland', 'check_in': req.departure_date, 'check_out': req.departure_date + timedelta(days=2)},
        {'destination': 'Krakow, Poland', 'check_in': req.departure_date + timedelta(days=2), 'check_out': req.return_date},
    ]})


def test_stays_cover_window_without_overlap_or_gaps():
    req = split_request()
    bad = req.model_dump()
    bad['stays'][1]['check_in'] += timedelta(days=1)
    with pytest.raises(ValueError): TripRequest.model_validate(bad)
    bad = req.model_dump(); bad['stays'][0]['check_out'] += timedelta(days=1)
    with pytest.raises(ValueError): TripRequest.model_validate(bad)


def test_flight_failure_keeps_two_hotel_searches_and_labeled_alternatives():
    req = split_request(); session = MagicMock()
    def get(url, *, params, timeout):
        if params['engine'] == 'google_hotels':
            return fake_response({'search_metadata': {'id': params['q']}, 'properties': [{'name': params['q'], 'rate_per_night': {'extracted_lowest': 100}}]})
        if params['arrival_id'] == 'WAW':
            raise RuntimeError('flight provider failure')
        return fake_response({'search_metadata': {'id': 'alternative'}, 'best_flights': [{'price': 700, 'flights': [{'airline': 'Fixture', 'arrival_airport': {'id': params['arrival_id']}}]}]})
    session.get.side_effect = get
    pack = SerpApiClientV1('fixture', session=session).search_evidence(req, origin_iata='TLV', destination_iata='WAW', alternative_airports=['WRO'])
    hotels = [r for r in pack.records if r.type == EvidenceType.HOTEL]
    flights = [r for r in pack.records if r.type == EvidenceType.FLIGHT]
    assert len(hotels) == 2 and len(flights) == 1
    assert flights[0].normalized_data['alternative'] is True
    assert flights[0].normalized_data['arrival_iata'] == 'WRO'
    hotel_params = [call.kwargs['params'] for call in session.get.call_args_list if call.kwargs['params']['engine'] == 'google_hotels']
    assert {p['q'] for p in hotel_params} == {'Hotels in Wroclaw, Poland', 'Hotels in Krakow, Poland'}
    assert {p['check_in_date'] for p in hotel_params} == {s.check_in.isoformat() for s in req.stays}
    assert all(call.kwargs['params'].get('outbound_date', req.departure_date.isoformat()) == req.departure_date.isoformat() for call in session.get.call_args_list)
    proposal = build_proposal_draft(req, pack, narrative=PlannerNarrative(summary='טיול'), model_version='fixture')
    text = render_ai_draft_hebrew(req, proposal)
    assert '200.00 ₪' in text and '300.00 ₪' in text and '500.00 ₪' in text
    assert '1,000.00' not in text
    assert 'חלופות טיסה לבחירתכם' in text and 'WRO' in text and 'טרם אומתו' in text
    context = build_planning_context(req, pack)
    assert context['request']['arrival_airport'] == 'WAW' and len(context['request']['stays']) == 2


def test_destination_lookup_filters_regions_and_invalid_airport_codes(monkeypatch):
    from src.api import v1
    monkeypatch.setattr(v1.config, 'SERPAPI_KEY', 'fixture')
    monkeypatch.setattr(v1.SerpApiClientV1, '_get', lambda self, params: {'suggestions': [
        {'name': 'Country', 'type': 'region'},
        {'name': 'City, Country', 'type': 'city', 'airports': [{'id': 'WRO', 'name': 'Airport'}, {'id': '/m/abc'}]},
    ]})
    result = destination_lookup(DestinationLookupRequest(query='City'))
    assert len(result['suggestions']) == 1
    assert result['suggestions'][0]['airports'] == [{'code': 'WRO', 'name': 'Airport'}]

def test_price_above_whole_budget_triggers_fallback():
    req = request(); session = MagicMock()
    def get(url, *, params, timeout):
        if params['engine'] == 'google_hotels': return fake_response({'properties': []})
        return fake_response({'search_metadata': {'id': params['arrival_id']}, 'best_flights': [{'price': 9000 if params['arrival_id'] == 'FCO' else 1000, 'flights': []}]})
    session.get.side_effect = get
    pack = SerpApiClientV1('fixture', session=session).search_evidence(req, origin_iata='TLV', destination_iata='FCO')
    assert any(r.normalized_data.get('alternative') and r.normalized_data.get('arrival_iata') == 'CIA' for r in pack.records)
