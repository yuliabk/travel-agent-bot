import pytest
from unittest.mock import MagicMock
from src.providers.nearby_airports import nearby_airports, airport_index
from src.providers.serpapi_client_v1 import SerpApiClientV1
from tests.test_serpapi_client_v1 import request, fake_response


@pytest.mark.parametrize('arrival,expected', [('SFO','OAK'),('BKK','DMK'),('SYD','NTL'),('JNB','HLA'),('FCO','CIA')])
def test_worldwide_candidates(arrival, expected):
    candidates = nearby_airports(arrival)
    assert expected in [item['code'] for item in candidates]
    assert all(item['code'] != arrival and item['distance_km'] <= 300 for item in candidates)
    assert len(candidates) <= 3
    assert [item['distance_km'] for item in candidates] == sorted(item['distance_km'] for item in candidates)


def test_unknown_radius_exclusions_and_border():
    assert nearby_airports('XXX') == []
    assert nearby_airports('SFO', radius_km=1) == []
    assert 'OAK' not in [x['code'] for x in nearby_airports('SFO', exclude=('OAK',))]
    assert any(x['cross_border'] for x in nearby_airports('GVA'))
    assert len(airport_index()) > 2000


def test_new_destination_fallback_preserves_dates_and_stays():
    req = request()
    req.destination = 'Bangkok, Thailand'
    session = MagicMock()
    def get(url, *, params, timeout):
        if params['engine'] != 'google_flights': return fake_response({})
        return fake_response({'search_metadata': {'id': 'fixture'}, 'best_flights': [] if params['arrival_id'] == 'BKK' else [{'price': 300, 'flights': []}]})
    session.get.side_effect = get
    pack = SerpApiClientV1('fixture', session=session).search_evidence(req, origin_iata='TLV', destination_iata='BKK')
    calls = [c.kwargs['params'] for c in session.get.call_args_list if c.kwargs['params']['engine'] == 'google_flights']
    assert any(p['arrival_id'] == 'DMK' for p in calls)
    assert all(p['outbound_date'] == req.departure_date.isoformat() and p['return_date'] == req.return_date.isoformat() for p in calls)
    assert req.destination == 'Bangkok, Thailand'
    assert any('קו אווירי' in n for n in pack.search_notes)