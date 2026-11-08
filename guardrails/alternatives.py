"""Evidence-bound alternative suggestions; never fabricate a market's cheapest fare."""
from guardrails.budget import budget_markdown


def propose_alternatives(assessment: dict) -> str:
    """Generate useful next steps from known quotes and report missing evidence honestly."""
    status = assessment.get('status', 'unknown')
    if status == 'over_budget':
        return (
            '### Budget-aware alternative planning\n\n'
            'The cheapest **combination in your supplied category quotes** exceeds your INR cap. '
            'This is **not** an independently verified minimum bookable trip.\n\n'
            + budget_markdown(assessment) + '\n\n'
            '**Alternatives to consider:** obtain new dated return-flight quotes for cheaper dates; '
            'compare accommodation in different areas; shorten the duration; reduce paid activities; '
            'or choose another destination after collecting new evidence. '
            'The app will not change destination or raise the budget without your input.'
        )
    if status == 'unknown':
        missing = ', '.join(assessment.get('missing_categories') or [])
        return (
            '### Price evidence needed before claiming a feasible minimum\n\n'
            'A reliable full-trip cost and cheapest realistic itinerary **cannot be established**. '
            + (f'Missing categories: {missing}. ' if missing else '')
            + ('Departure city/origin is missing. ' if assessment.get('missing_origin') else '')
            + 'You can enter missing quoted prices, try less expensive dates/destinations, '
            'or choose an exploratory itinerary preview with an explicit no-price-guarantee warning. '
            'No numeric market minimum is invented.'
        )
    return 'No alternative planning is required for this request.'
