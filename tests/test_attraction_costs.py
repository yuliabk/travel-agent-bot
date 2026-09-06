from unittest.mock import MagicMock
from src.providers.serpapi_client_v1 import SerpApiClientV1
from src.runtime.planner_v1 import PlannerNarrative, PlannerDay, build_proposal_draft
from src.runtime.attraction_costs_v1 import render_attraction_costs
from src.contracts.travel_v1 import EvidencePack
from tests.test_serpapi_client_v1 import request, fake_response
from tests.test_workflow_v1 import FakeSearch, payload, completion
from src.runtime.workflow_v1 import run_web_draft_workflow


def narrative():
    return PlannerNarrative(summary='טיול', days=[PlannerDay(day_number=1,title='ביקור',summary='ביקור',location='Rome, Italy',attractions=['Museum', 'Park']), PlannerDay(day_number=2,title='חזרה',summary='עוד ביקור',location='Rome, Italy',attractions=['Museum'])])


def test_published_admission_is_not_a_family_quote_and_lookup_deduplicates():
    session = MagicMock()
    session.get.side_effect = lambda url, params, timeout: fake_response({'place_results': {'title': params['q'].split(',')[0], 'place_id':'fixture', 'admission':[{'title':'Official Museum','options':[{'title':'Entrance','price':'€12','official_site':True}]}]}})
    req = request(); plan = narrative()
    records = SerpApiClientV1('fixture',session=session).search_attraction_prices(req,plan)
    assert session.get.call_count == 2
    assert all(r.amount is None and not r.is_verified_price for r in records)
    proposal = build_proposal_draft(req,EvidencePack(request_id=req.request_id,records=records),narrative=plan,model_version='fixture')
    text = '\n'.join(render_attraction_costs(req,proposal))
    assert '€12' in text and 'אטרקציות ביום 2' in text
    assert 'טרם אומתו לתאריך ולגילים' in text and '€24' not in text
    assert proposal.estimated_total == []


def test_ambiguous_or_mismatched_place_is_not_priced():
    session = MagicMock(); session.get.return_value = fake_response({'place_results':{'title':'Other Place','admission':[{'options':[{'price':'20'}]}]}})
    assert SerpApiClientV1('fixture',session=session).search_attraction_prices(request(),narrative()) == []


def test_quota_stops_attractions_and_missing_is_not_free():
    session=MagicMock(); client=SerpApiClientV1('fixture',session=session);client.rate_limited.set()
    req=request();plan=narrative()
    assert client.search_attraction_prices(req,plan)==[]
    session.get.assert_not_called()
    proposal=build_proposal_draft(req,EvidencePack(request_id=req.request_id),narrative=plan,model_version='fixture')
    assert 'אין להסיק שהכניסה חינם' in '\n'.join(render_attraction_costs(req,proposal))


def test_place_lookup_uses_actual_coordinates():
    session=MagicMock()
    session.get.side_effect=[fake_response({'local_results':[{'title':'Museum','data_id':'0xab:0xcd','gps_coordinates':{'latitude':41.9,'longitude':12.5}}]}),fake_response({'place_results':{'title':'Museum'}})]
    plan=narrative();plan.days=plan.days[:1];plan.days[0].attractions=['Museum']
    SerpApiClientV1('fixture',session=session).search_attraction_prices(request(),plan)
    assert '!3d41.9!4d12.5' in session.get.call_args_list[1].kwargs['params']['data']


def test_enrichment_failure_preserves_draft():
    class Search(FakeSearch):
        def search_attraction_prices(self, request, narrative): raise RuntimeError('fixture failure')
    class Planner:
        def generate_narrative(self, request, pack): return narrative()
    result=run_web_draft_workflow(payload(),completion(),origin_iata='TLV',destination_iata='FCO',evidence_searcher=Search(),planner=Planner())
    assert result.status=='AI_DRAFT'
    assert 'חיפוש מחירי האטרקציות לא הושלם' in result.rendered_draft