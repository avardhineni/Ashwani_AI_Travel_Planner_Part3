"""Streamlit app: draft -> possible budget decision -> itinerary approval -> PDF."""
import json
from datetime import datetime
from pathlib import Path
import uuid
import streamlit as st
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from config import BASE_DIR
from graph import create_app
from pdf_export import build_travel_pdf
from guardrails.budget import CATEGORIES, budget_markdown, normalize_quote

st.set_page_config(page_title='AI Travel Planner | LangGraph + MCP', page_icon='✈️', layout='wide')
st.title('✈️ AI Travel Planner')
st.caption('LangGraph • MCP • Supervisor • Budget validation • Human approval • PDF')

@st.cache_resource(show_spinner='Connecting to PostgreSQL...')
def get_graph():
    return create_app()


def new_thread():
    st.session_state.thread_id = uuid.uuid4().hex
    st.session_state.latest_result = None
    st.session_state.approval_payload = None
    st.session_state.saved_pdf_key = None


def session_config():
    return {'configurable': {'thread_id': st.session_state.thread_id}}


def remember_result(result):
    st.session_state.latest_result = result
    items = result.get('__interrupt__', ())
    st.session_state.approval_payload = items[0].value if items else None


if 'thread_id' not in st.session_state:
    new_thread()

with st.sidebar:
    st.header('Session')
    user_id = st.text_input('User ID (display label only)', value='local_demo')
    st.caption('This is NOT authentication. Never deploy with public shared access without user isolation.')
    st.code(st.session_state.thread_id)
    if st.button('New thread / new travel request'):
        new_thread()
        st.rerun()
    st.markdown('**Project stages**')
    st.markdown('1. Guardrail + supervisor\n2. Select MCP specialists\n3. Calculate budget\n4. Optional budget decision\n5. Draft itinerary\n6. Human approval/revision\n7. PDF export')

query = st.text_area('Describe your trip',
                     placeholder='Plan 7 days in Japan from Hyderabad under ₹10,000, including flights, hotels and sightseeing.',
                     height=105)

with st.expander('Optional: enter observed INR price quotes for a cost feasibility calculation', expanded=False):
    st.info('No fabricated fares. Enter actual prices you observed, with source and date where possible. '
            'All 6 cost categories are required to compute a complete quoted trip total. '
            'Use ₹0 explicitly for genuinely free categories. Data is user-supplied and NOT independently verified.')
    if 'quote_rows' not in st.session_state:
        st.session_state.quote_rows = [
            {'category': 'flights', 'label': 'Round-trip fare, incl. baggage/taxes', 'unit_cost_inr': None,
             'quantity': 1, 'source': '', 'observed_at': '', 'source_url': ''},
            {'category': 'accommodation', 'label': 'Accommodation per night', 'unit_cost_inr': None,
             'quantity': 6, 'source': '', 'observed_at': '', 'source_url': ''},
            {'category': 'transport', 'label': 'Ground transport total', 'unit_cost_inr': None,
             'quantity': 1, 'source': '', 'observed_at': '', 'source_url': ''},
            {'category': 'food', 'label': 'Food per day', 'unit_cost_inr': None,
             'quantity': 7, 'source': '', 'observed_at': '', 'source_url': ''},
            {'category': 'activities', 'label': 'Sightseeing, free = 0', 'unit_cost_inr': None,
             'quantity': 1, 'source': '', 'observed_at': '', 'source_url': ''},
            {'category': 'fees', 'label': 'Visa, insurance, other fees', 'unit_cost_inr': None,
             'quantity': 1, 'source': '', 'observed_at': '', 'source_url': ''},
        ]
    edited = st.data_editor(st.session_state.quote_rows, num_rows='dynamic',
                            use_container_width=True, hide_index=True, key='price_editor')
    st.caption('Use another row with the same category to compare options. '
               'For each category, the calculator uses the smallest supplied subtotal. '
               'Check quantities for passengers, nights and days before proceeding.')


def extract_quotes(rows):
    result = []
    for row in rows:
        value = row.get('unit_cost_inr')
        if value in (None, ''):
            continue
        result.append(normalize_quote(row))
    return result


st.divider()
if st.button('🚀 Create Draft Plan', type='primary', use_container_width=True):
    if not query.strip():
        st.warning('Enter a travel-related request.')
    else:
        try:
            quotes = extract_quotes(edited)
            new_thread()  # avoid mixing existing checkpoints with a new request
            app, _ = get_graph()
            initial = {
                'messages': [HumanMessage(content=query)],
                'user_id': user_id,
                'user_query': query,
                'quotes': quotes,
                'approved_budget_inr': None,
                'budget_reviewed': False,
                'budget_decision': '',
                'revision_count': 0,
                'human_feedback': '',
                'approved': False,
                'llm_calls': 0,
            }
            with st.spinner('Running the supervisor and selected agents...'):
                remember_result(app.invoke(initial, config=session_config()))
            st.rerun()
        except Exception as exc:
            st.error(f'Unable to run the planner: {type(exc).__name__}: {exc}')

result = st.session_state.get('latest_result') or {}
if result:
    if result.get('request_status') == 'blocked':
        st.error('Request blocked: ' + result.get('rejection_reason', 'Not a travel request.'))
        st.stop()
    st.subheader('Supervisor decisions')
    st.write(result.get('supervisor_reasoning', ''))
    st.write('Selected specialists:', result.get('selected_agents', []))
    st.caption(f"LLM invocations counted: {result.get('llm_calls', 0)}")
    with st.expander('Specialist findings', expanded=False):
        left, right = st.columns(2)
        with left:
            st.markdown('#### Flights')
            st.markdown(result.get('flight_results', '') or 'Not requested or not available')
            st.markdown('#### Weather')
            st.markdown(result.get('weather_results', '') or 'Not requested or not available')
        with right:
            st.markdown('#### Hotels')
            st.markdown(result.get('hotel_results', '') or 'Not requested or not available')
    if result.get('alternative_plan'):
        st.subheader('Alternative planning guidance')
        st.markdown(result['alternative_plan'])
    if result.get('budget_assessment'):
        st.subheader('Deterministic budget assessment')
        st.markdown(budget_markdown(result['budget_assessment']))

payload = st.session_state.get('approval_payload')
if payload and payload.get('kind') == 'budget_review':
    st.divider()
    st.subheader('Budget decision required before itinerary generation')
    status = payload.get('status')
    if status == 'unknown':
        st.warning('Insufficient or incomplete price evidence. A realistic minimum cannot be established.')
    else:
        st.warning('The supplied cheapest quote combination exceeds the requested budget.')
    display_choices = {
        'continue_preview': 'Continue with a non-bookable planning preview and the warning',
        'show_lowest': 'Plan around the lowest combination of my supplied quotes (may exceed cap)',
        'raise_budget': 'Change my approved INR budget cap',
        'change_trip': 'Change destination/dates (start a new request)',
        'cancel': 'Cancel',
    }
    options = ['continue_preview', 'raise_budget', 'change_trip', 'cancel']
    if status == 'over_budget':
        options.insert(1, 'show_lowest')
    choice = st.radio('Choose what happens next:', options, format_func=lambda x: display_choices[x], key='budget_choice')
    new_cap = st.number_input('New INR budget', min_value=1, value=100000, step=1000) if choice == 'raise_budget' else None
    if st.button('Submit budget decision', type='primary'):
        try:
            app, _ = get_graph()
            with st.spinner('Resuming LangGraph after budget review...'):
                remember_result(app.invoke(Command(resume={'decision': choice, 'new_budget_inr': new_cap}),
                                           config=session_config()))
            st.rerun()
        except Exception as exc:
            st.error(f'Budget decision failed: {type(exc).__name__}: {exc}')

elif payload and payload.get('kind') == 'itinerary_review':
    st.divider()
    st.subheader('Draft itinerary — human approval')
    st.markdown(payload.get('draft_itinerary', '') or '_No draft available_')
    st.caption('The cost assessment above remains authoritative for budget claims, not this AI draft.')
    approved = st.radio('Approve the draft?', ['Yes', 'No — request changes'], horizontal=True)
    feedback = st.text_area('What should change?', disabled=(approved == 'Yes'),
                            placeholder='e.g. Prefer budget hotels and more free attractions.')
    if st.button('Submit human review', type='primary'):
        if approved != 'Yes' and not feedback.strip():
            st.warning('Enter feedback before requesting a revision.')
        else:
            try:
                app, _ = get_graph()
                with st.spinner('Resuming workflow and revising relevant agents if needed...'):
                    remember_result(app.invoke(Command(resume={'approved': approved == 'Yes', 'feedback': feedback}),
                                               config=session_config()))
                st.rerun()
            except Exception as exc:
                st.error(f'Human approval could not be resumed: {type(exc).__name__}: {exc}')

elif result.get('final_status') == 'approved' and result.get('final_response'):
    st.divider()
    st.subheader('✅ Approved final plan')
    st.markdown(result['final_response'])
    stamp = datetime.now()
    key = st.session_state.thread_id
    if st.session_state.get('saved_pdf_key') != key:
        payload_pdf = build_travel_pdf(user_query=result.get('user_query', ''),
                                       thread_id=key, collected={'final_response': result['final_response'],
                                                                  'llm_calls': result.get('llm_calls', 0)},
                                       generated_at=stamp)
        save_dir = BASE_DIR / 'travel_plans'
        save_dir.mkdir(exist_ok=True)
        saved = save_dir / f'travel_plan_{key[:8]}_{stamp:%Y%m%d_%H%M%S}.pdf'
        saved.write_bytes(payload_pdf)
        st.session_state.saved_pdf_key = key
        st.session_state.saved_pdf_bytes = payload_pdf
        st.session_state.saved_pdf_name = saved.name
    st.download_button('⬇️ Download Approved PDF', data=st.session_state.saved_pdf_bytes,
                       file_name=st.session_state.saved_pdf_name, mime='application/pdf')
    st.success('Auto-saved in travel_plans/ (excluded from Git)')

elif result.get('final_status') in ('stopped', 'error'):
    st.info(result.get('final_response') or 'Workflow stopped without an approved plan.')
