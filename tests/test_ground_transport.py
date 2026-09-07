from src.runtime.ground_transport_v1 import ground_transport_plan, render_ground_transport
from src.runtime.planner_v1 import build_planning_context, build_proposal_draft, PlannerNarrative, PlannerDay
from src.runtime.renderer_v1 import render_ai_draft_hebrew
from src.contracts.travel_v1 import EvidencePack, EvidenceRecord, EvidenceSourceStatus, EvidenceType
from tests.test_flexible_trip import split_request
from tests.test_serpapi_client_v1 import request


def test_multistay_and_conditional_airports_have_both_directions():
    req = split_request()
    plan = ground_transport_plan(req, ['WAW', 'WRO', 'WRO', None])
    assert len(plan['legs']) == 5
    assert any(l['origin'] == 'WAW' and l['destination'] == req.stays[0].destination and not l['conditional'] for l in plan['legs'])
    assert any(l['origin'] == req.stays[-1].destination and l['destination'] == 'WRO' and l['conditional'] for l in plan['legs'])
    move = next(l for l in plan['legs'] if l['kind'] == 'between_stays')
    assert move['date'] == req.stays[1].check_in.isoformat()
    assert move['origin'] == req.stays[0].destination
    assert not plan['prices_and_schedules_verified']


def test_planner_and_output_consider_modes_without_inventing_total():
    req = split_request(); pack = EvidencePack(request_id=req.request_id)
    context = build_planning_context(req, pack)
    assert context['ground_transport']['modes_to_compare'] == ['public_transport','rental_car','mixed']
    narrative = PlannerNarrative(summary='טיול', days=[PlannerDay(day_number=1,title='הגעה',summary='מנוחה',transport_notes='יש לבדוק רכבת בשעת הנחיתה.')])
    proposal = build_proposal_draft(req,pack,narrative=narrative,model_version='fixture')
    rendered = render_ai_draft_hebrew(req,proposal)
    assert 'איך מתניידים' in rendered and 'רכבת בשעת הנחיתה' in rendered
    assert 'בוחרים תרחיש אחד' in rendered and 'דלק' in rendered and 'החזרה במקום אחר' in rendered
    assert 'אין מחיר כולל מאומת לתחבורה כרגע' in rendered
    assert proposal.estimated_total == []


def test_missing_airport_is_explicit_and_city_names_are_not_markup():
    req = request(); req.destination = 'City | Extra\nName'
    text = '\n'.join(render_ground_transport(req, []))
    assert 'חסר שדה תעופה' in text
    assert 'City | Extra' not in text


def test_observed_rental_quote_is_visible_but_not_counted_as_verified_total():
    req = split_request()
    rental = EvidenceRecord(
        type=EvidenceType.TRANSPORT,
        provider='octotrip/rental-cars',
        provider_reference='https://example.test/car',
        raw_reference='https://example.test/car',
        amount=250,
        currency='EUR',
        source_status=EvidenceSourceStatus.UNVERIFIED,
        normalized_data={
            'kind': 'rental_car', 'evidence_status': 'observed', 'booking_ready': False,
            'name': 'Economy car', 'vendor': 'Vendor', 'category': 'Economy',
            'transmission': 'automatic', 'booking_url': 'https://example.test/car',
            'price_basis': 'total_rental_observed',
        },
    )
    pack = EvidencePack(request_id=req.request_id, records=[rental])
    proposal = build_proposal_draft(req, pack, narrative=None, model_version='off')
    rendered = render_ai_draft_hebrew(req, proposal)
    assert 'מחירי רכב שנצפו' in rendered
    assert '250 EUR' in rendered
    assert proposal.estimated_total == []
