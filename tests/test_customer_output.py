from datetime import timedelta
from tests.test_planner_v1 import request, verified_records
from src.runtime.planner_v1 import build_proposal_draft, PlannerNarrative
from src.runtime.renderer_v1 import render_ai_draft_hebrew
from src.providers.serpapi_evidence import normalize_hotels_response
from src.api.v1 import map_points, MapPointsRequest
from src.api.web_gate_v1 import webform_gate_decision


def test_costs_five_nights_and_alternatives_are_not_added():
    req = request()
    req.return_date = req.departure_date + timedelta(days=5)
    pack, _, _ = verified_records(req)
    proposal = build_proposal_draft(req, pack, narrative=PlannerNarrative(summary='טיול'), model_version='test')
    proposal.hotel_options.append(dict(proposal.hotel_options[0], amount='200', currency='ILS'))
    text = render_ai_draft_hebrew(req, proposal)
    assert '600.00 $' in text and '1,000.00 ₪' in text
    assert '× 5 לילות' in text
    assert '1,600.00' not in text
    assert 'עדיין לא ניתן לחשב' in text
    assert 'Evidence' not in text and 'per_night' not in text and 'ev_' not in text


def test_provider_total_overrides_nightly_estimate_and_missing_price_stays_unknown():
    req = request()
    pack, _, _ = verified_records(req)
    proposal = build_proposal_draft(req, pack, narrative=None, model_version='test')
    proposal.hotel_options[0]['stay_total'] = '510'
    proposal.flight_options = []
    text = render_ai_draft_hebrew(req, proposal)
    assert '510.00 $' in text and '480.00' not in text
    assert '| טיסות | חסר מחיר |' in text
    assert 'מחיר לשהות שנמסר מהספק' in text


def test_hotel_total_is_copied_from_provider():
    records = normalize_hotels_response({'search_metadata': {'id': 'fixture'}, 'search_parameters': {'currency': 'ILS'}, 'properties': [{'name': 'Hotel', 'rate_per_night': {'extracted_lowest': 120}, 'total_rate': {'extracted_lowest': 605}}]})
    assert records[0].normalized_data['stay_total'] == '605'
    assert str(records[0].amount) == '120'


def test_map_reuses_backend_key_and_reports_missing(monkeypatch):
    from src.api import v1
    monkeypatch.setattr(v1.config, 'SERPAPI_KEY', 'fixture')
    calls = []
    class Reply:
        def raise_for_status(self): pass
        def json(self): return {'place_results': {'gps_coordinates': {'latitude': 51.1, 'longitude': 17.03}}}
    def get(url, **kwargs):
        calls.append(kwargs)
        if kwargs['params']['q'].startswith('Missing'):
            raise RuntimeError('no result')
        return Reply()
    monkeypatch.setattr(v1.requests, 'get', get)
    result = map_points(MapPointsRequest(destination='Wroclaw, Poland', places=['כיכר השוק (Rynek)', 'כיכר השוק (Rynek)', 'Missing']))
    assert len(result['points']) == 1 and result['missing'] == ['Missing']
    assert calls[0]['params']['q'] == 'Rynek, Wroclaw, Poland'
    assert all(call['params']['api_key'] == 'fixture' and call['timeout'] == (3, 5) for call in calls)
    assert webform_gate_decision('/v1/web/map-points', None, enabled=True, expected_token='fixture')[0] == 401

