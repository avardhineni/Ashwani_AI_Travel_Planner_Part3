"""Deterministic INR budget assessment using *user-supplied* dated price quotes.

IMPORTANT: This module cannot verify a booking or live airfare. No invented floor prices.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from urllib.parse import urlparse

CATEGORIES = ('flights', 'accommodation', 'transport', 'food', 'activities', 'fees')
MONEY = Decimal('0.01')


def parse_budget_inr(query: str) -> int | None:
    """Extract common INR formats, e.g. `under 10000 Rupees`, `₹2 lakh`.

    Only understands INR, never silently converts foreign currencies.
    """
    patterns = [
        r'(?:₹|\b(?:inr|rs\.?|rupees?)\b)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lakhs|lac|lacs|k|thousand)?',
        r'\b(?:under|below|budget(?:\s+of)?|upto|up\s+to|within)\s*(?:₹|inr\s*|rs\.?\s*)?([\d,]+(?:\.\d+)?)\s*(lakh|lakhs|lac|lacs|k|thousand)?\s*(?:rupees?|inr)?\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if not match:
            continue
        number, suffix = match.groups()
        try:
            val = Decimal(number.replace(',', ''))
        except InvalidOperation:
            continue
        factor = Decimal(100000 if suffix and suffix.lower().startswith(('lac', 'lakh')) else
                         1000 if suffix else 1)
        amount = val * factor
        if 0 < amount <= Decimal('1000000000'):
            return int(amount)
    return None


def _decimal(value, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{field} must be numeric') from None
    if not result.is_finite() or result < 0:
        raise ValueError(f'{field} must be finite and >= 0')
    return result


def _money(value: Decimal) -> str:
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def normalize_quote(item: dict) -> dict:
    if not isinstance(item, dict):
        raise ValueError('Each quote must be a dictionary')
    category = str(item.get('category', '')).lower().strip()
    if category not in CATEGORIES:
        raise ValueError(f'Unknown quote category: {category}. Expected {CATEGORIES}')
    if str(item.get('currency', 'INR')).upper() != 'INR':
        raise ValueError('Quotes must be in INR. Convert externally with a documented FX rate.')
    unit = _decimal(item.get('unit_cost_inr'), 'unit_cost_inr')
    quantity = _decimal(item.get('quantity', 1), 'quantity')
    if quantity == 0:
        raise ValueError('quantity must be > 0; use unit_cost_inr=0 for free items')
    source = str(item.get('source', 'user supplied')).strip()[:180]
    url = str(item.get('source_url', '')).strip()
    if url and urlparse(url).scheme not in ('http', 'https'):
        raise ValueError('source_url must be an http(s) URL')
    observed = str(item.get('observed_at', '')).strip()
    if observed:
        try:
            date.fromisoformat(observed)
        except ValueError:
            raise ValueError('observed_at must use YYYY-MM-DD') from None
    return {
        'category': category,
        'label': str(item.get('label') or category).strip()[:140],
        'unit_cost_inr': _money(unit),
        'quantity': str(quantity),
        'subtotal_inr': _money(unit * quantity),
        'source': source or 'user supplied',
        'source_url': url,
        'observed_at': observed,
    }


def assess_budget(quotes: list[dict], budget_inr: int | None, *, origin: str = '') -> dict:
    """Choose lowest supplied subtotal per category, not an independently verified fare.

    If a category is absent, minimum full-trip cost cannot be established.
    """
    if budget_inr is not None and (not isinstance(budget_inr, int) or budget_inr <= 0):
        raise ValueError('budget_inr must be a positive integer or None')
    normalized = [normalize_quote(q) for q in quotes]
    selected = []
    missing = []
    for category in CATEGORIES:
        candidates = [q for q in normalized if q['category'] == category]
        if not candidates:
            missing.append(category)
        else:
            selected.append(min(candidates, key=lambda x: Decimal(x['subtotal_inr'])))
    subtotal = sum((Decimal(q['subtotal_inr']) for q in selected), Decimal(0))
    complete = not missing
    if budget_inr is None:
        status = 'no_budget'
    elif not complete or not origin.strip():
        status = 'unknown'
    elif subtotal > Decimal(budget_inr):
        status = 'over_budget'
    else:
        status = 'within_estimate'
    return {
        'status': status,
        'requested_budget_inr': budget_inr,
        'minimum_quoted_total_inr': _money(subtotal) if complete else None,
        'known_subtotal_inr': _money(subtotal),
        'shortfall_inr': _money(subtotal - Decimal(budget_inr)) if status == 'over_budget' else None,
        'missing_categories': missing,
        'missing_origin': not bool(origin.strip()),
        'selected_quotes': selected,
        'all_quotes_count': len(normalized),
        'evidence_level': 'user_supplied_unverified',
        'note': ('Quotes and combinations are supplied by the user and are not independently verified. '
                 'The cheapest category combination may not be simultaneously bookable. '
                 'Prices may change; taxes, baggage, visas and fees must be included.'),
    }


def budget_markdown(assessment: dict) -> str:
    if not assessment:
        return 'No budget assessment was completed.'
    status = assessment['status']
    phrases = {
        'no_budget': 'No INR budget was specified.',
        'unknown': 'Budget feasibility **cannot be established** from the supplied information.',
        'over_budget': '**Over the requested budget**, based on the supplied price quotes.',
        'within_estimate': 'The supplied quote combination is **within the stated budget estimate**; booking availability remains unverified.',
    }
    rows = [f"**Status:** {phrases.get(status, status)}"]
    if assessment.get('requested_budget_inr') is not None:
        rows.append(f"**Requested/approved INR cap:** ₹{assessment['requested_budget_inr']:,}")
    if assessment.get('minimum_quoted_total_inr') is not None:
        rows.append(f"**Lowest combined supplied quotes (NOT a verified bookable minimum):** ₹{assessment['minimum_quoted_total_inr']}")
    else:
        rows.append(f"**Subtotal of categories with quotes only:** ₹{assessment['known_subtotal_inr']} (not a trip total)")
    if assessment.get('shortfall_inr'):
        rows.append(f"**Amount over cap:** ₹{assessment['shortfall_inr']}")
    if assessment.get('missing_categories'):
        rows.append('**Missing cost categories:** ' + ', '.join(assessment['missing_categories']))
    if assessment.get('missing_origin'):
        rows.append('**Origin city required:** enter departure location before treating flights as applicable to your trip.')
    if assessment.get('selected_quotes'):
        rows.extend(['', '| Category | Quote | Quantity × Unit INR | Subtotal INR | Date / source |', '|---|---|---:|---:|---|'])
        for q in assessment['selected_quotes']:
            source = q['source'] + (' (' + q['observed_at'] + ')' if q['observed_at'] else '')
            rows.append(f"| {q['category']} | {q['label']} | {q['quantity']} × {q['unit_cost_inr']} | {q['subtotal_inr']} | {source} |")
    rows.append('\n*' + assessment['note'] + '*')
    return '\n\n'.join(rows[:5]) + ('\n' + '\n'.join(rows[5:]) if len(rows) > 5 else '')
