from decimal import Decimal
import pytest
from guardrails.budget import (CATEGORIES, parse_budget_inr, assess_budget,
                               normalize_quote, budget_markdown)
from guardrails.output import sanitize_itinerary, final_markdown
from guardrails.alternatives import propose_alternatives


def quotes(flight=40000):
    costs = [flight, 6 * 2000, 3500, 7 * 600, 1500, 2000]
    return [dict(category=category, label=f'SYNTHETIC {category}',
                 unit_cost_inr=cost, quantity=1, source='SYNTHETIC TEST DATA — NOT A REAL PRICE')
            for category, cost in zip(CATEGORIES, costs)]


def test_parse_inr_budget():
    assert parse_budget_inr('7 days Japan under 10000 Rupees') == 10000
    assert parse_budget_inr('Japan trip below ₹10,000') == 10000
    assert parse_budget_inr('Japan under 2 lakhs') == 200000
    assert parse_budget_inr('Under Rs. 1.5 lakh') == 150000
    assert parse_budget_inr('Japan trip for seven days') is None


def test_unrealistic_budget_detected_from_complete_synthetic_quotes():
    report = assess_budget(quotes(), 10000, origin='Hyderabad')
    assert report['status'] == 'over_budget'
    assert Decimal(report['minimum_quoted_total_inr']) == Decimal('63200.00')
    assert Decimal(report['shortfall_inr']) == Decimal('53200.00')
    assert 'not independently verified' in report['note']
    assert 'Over the requested budget' in budget_markdown(report)


def test_complete_within_estimate_is_not_claimed_verified():
    report = assess_budget(quotes(), 70000, origin='Hyderabad')
    assert report['status'] == 'within_estimate'
    assert report['evidence_level'] == 'user_supplied_unverified'


def test_missing_categories_does_not_claim_cheapest_total():
    report = assess_budget(quotes()[:2], 10000, origin='Hyderabad')
    assert report['status'] == 'unknown'
    assert report['minimum_quoted_total_inr'] is None
    assert len(report['missing_categories']) == 4


def test_missing_origin_is_unknown():
    report = assess_budget(quotes(), 10000, origin='')
    assert report['status'] == 'unknown'
    assert report['missing_origin']


def test_choose_lowest_option_per_category():
    alternate = dict(category='flights', label='other option',
                     unit_cost_inr=38000, quantity=1, source='SYNTHETIC TEST DATA')
    report = assess_budget(quotes() + [alternate], 65000, origin='Hyderabad')
    assert report['status'] == 'within_estimate'
    assert Decimal(report['minimum_quoted_total_inr']) == Decimal('61200.00')


def test_quantity_and_unit_cost_multiply_exactly():
    q = normalize_quote(dict(category='accommodation', label='Hotel', quantity=7,
                             unit_cost_inr='2500', source='manual price'))
    assert Decimal(q['subtotal_inr']) == Decimal('17500.00')


@pytest.mark.parametrize('cost,qty', [('-1', 1), ('nan', 1), ('Infinity', 1), (100, 0)])
def test_invalid_quotes_rejected(cost, qty):
    with pytest.raises(ValueError):
        normalize_quote(dict(category='food', unit_cost_inr=cost, quantity=qty))


def test_non_inr_quote_rejected():
    with pytest.raises(ValueError, match='INR'):
        normalize_quote(dict(category='food', unit_cost_inr=100, quantity=1, currency='USD'))


def test_untrusted_cost_claims_removed_before_display():
    safe, dropped = sanitize_itinerary('Day 1: Explore Tokyo\nTotal ₹73,850 and within budget\nDay 2: Museum')
    assert len(dropped) == 1
    assert '₹73,850' not in safe
    assert 'Day 2' in safe


def test_only_approved_plans_may_be_exported():
    result = final_markdown('Trip request', 'Day 1: Japan', assess_budget(quotes(), 10000, origin='Hyderabad'), approved=False)
    assert result.startswith('No approved final plan')


def test_complete_final_report_includes_calculated_amount():
    report = assess_budget(quotes(), 10000, origin='Hyderabad')
    final = final_markdown('Japan under ₹10,000', 'Day 1: Explore Tokyo', report, approved=True)
    assert '63200.00' in final
    assert 'over the requested budget' in final.lower()
    assert 'Day 1: Explore Tokyo' in final


def test_alternative_planner_never_invents_when_missing_evidence():
    report = assess_budget([], 10000, origin="Hyderabad")
    text = propose_alternatives(report)
    assert "cannot be established" in text
    assert "No numeric market minimum is invented" in text
