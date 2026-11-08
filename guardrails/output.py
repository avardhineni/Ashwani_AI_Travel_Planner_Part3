"""An intentionally conservative final-output barrier for unsourced prices."""
import re

# Prices/claims come ONLY from guardrails.budget, never from an LLM narrative.
PRICE_CLAIM = re.compile(r'(?:₹|\bINR\b|\bRs\.?\s*\d|\b\d[\d,]*\s*(?:rupees?|lakh|lakhs)\b)', re.I)
COMPLIANCE_CLAIM = re.compile(r'\b(?:within|under|fits?)\s+(?:the\s+|your\s+)?budget\b', re.I)

def sanitize_itinerary(text: str) -> tuple[str, list[str]]:
    """Drop suspicious monetary/guarantee lines; show cost only from calculator.

    This is a defense-in-depth display filter, not a comprehensive safety filter.
    """
    retained, dropped = [], []
    for line in (text or '').splitlines():
        if PRICE_CLAIM.search(line) or COMPLIANCE_CLAIM.search(line):
            dropped.append(line)
        else:
            retained.append(line)
    return ('\n'.join(retained).strip() or 'Draft contained unsupported monetary claims and was withheld.', dropped)


def final_markdown(query: str, itinerary: str, assessment: dict, *, approved: bool) -> str:
    from guardrails.budget import budget_markdown
    if not approved:
        return 'No approved final plan. The draft remains unapproved.'
    safe, dropped = sanitize_itinerary(itinerary)
    note = ('\n\n> Some unverified cost or affordability claims from the AI narrative were omitted. '
            'Refer only to the deterministic budget table below.' if dropped else '')
    return ('# AI Travel Planner — reviewed itinerary\n\n'
            '## Request\n\n' + query + '\n\n'
            '## Cost and feasibility assessment\n\n' + budget_markdown(assessment) + '\n\n'
            '## Travel itinerary (suggestions, not reservations)\n\n' + safe + note + '\n\n'
            '**Important:** Confirm flight/room availability, visa rules, dates and prices with providers before booking.')
