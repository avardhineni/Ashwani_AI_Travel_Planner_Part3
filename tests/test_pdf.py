from datetime import datetime
from io import BytesIO
from pathlib import Path
from guardrails.budget import assess_budget
from guardrails.output import final_markdown
from pdf_export import build_travel_pdf


def test_pdf_is_real_pdf_with_approved_budget_message(tmp_path):
    categories = ('flights', 'accommodation', 'transport', 'food', 'activities', 'fees')
    synthetic = [dict(category=k, unit_cost_inr=11000, quantity=1, source='SYNTHETIC') for k in categories]
    assessment = assess_budget(synthetic, 10000, origin='Hyderabad')
    final = final_markdown('Japan under Rs 10000', '## Day 1\nTokyo sightseeing', assessment, approved=True)
    data = build_travel_pdf(user_query='Japan under Rs 10000', thread_id='test',
                            collected={'final_response': final, 'llm_calls': 5},
                            generated_at=datetime(2026, 11, 8, 12, 0))
    assert data.startswith(b'%PDF-')
    assert len(data) > 1500
    (tmp_path / 'sample.pdf').write_bytes(data)
