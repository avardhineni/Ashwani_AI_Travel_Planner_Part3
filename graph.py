"""LangGraph conditional routing with actual block END and HITL feedback loop."""
import psycopg
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from agents import (supervisor_agent, flight_agent, hotel_agent, weather_agent,
                    budget_agent, alternative_planning_agent, budget_review_agent, itinerary_agent,
                    human_approval_agent, revision_agent, final_response_agent)
from config import DATABASE_URL
from state import TravelState

AGENT_ORDER = ['flight_agent', 'hotel_agent', 'weather_agent']
ROUTE_MAP = {name: name for name in AGENT_ORDER}
ROUTE_MAP.update({'budget_agent': 'budget_agent', 'end': END})


def selected_agents(state: TravelState) -> list[str]:
    selected = state.get('selected_agents') or []
    return [name for name in AGENT_ORDER if name in selected]


def first_agent(state: TravelState) -> str:
    if state.get('request_status') == 'blocked':
        return 'end'
    selected = selected_agents(state)
    return selected[0] if selected else 'budget_agent'


def after_specialist(current: str):
    def route(state: TravelState) -> str:
        selected = selected_agents(state)
        for next_agent in AGENT_ORDER[AGENT_ORDER.index(current) + 1:]:
            if next_agent in selected:
                return next_agent
        return 'budget_agent'
    return route


def after_budget(state: TravelState) -> str:
    status = (state.get('budget_assessment') or {}).get('status', 'unknown')
    if status in ('no_budget', 'within_estimate') or state.get('budget_reviewed'):
        return 'itinerary_agent'
    return 'alternative_planning'


def after_budget_review(state: TravelState) -> str:
    decision = state.get('budget_decision')
    if decision == 'raise_budget':
        return 'budget_agent'
    if decision in ('cancel', 'change_trip'):
        return 'end'
    return 'itinerary_agent'


def after_approval(state: TravelState) -> str:
    if state.get('final_status') == 'error':
        return 'end'
    if state.get('approved'):
        return 'final_response'
    if state.get('revision_count', 0) >= 3:
        return 'end'
    return 'revision'


def after_revision(state: TravelState) -> str:
    if state.get('final_status') == 'stopped':
        return 'end'
    selected = selected_agents(state)
    return selected[0] if selected else 'budget_agent'


def build_graph(checkpointer):
    graph = StateGraph(TravelState)
    graph.add_node('supervisor', supervisor_agent)
    graph.add_node('flight_agent', flight_agent)
    graph.add_node('hotel_agent', hotel_agent)
    graph.add_node('weather_agent', weather_agent)
    graph.add_node('budget_agent', budget_agent)
    graph.add_node('alternative_planning', alternative_planning_agent)
    graph.add_node('budget_review', budget_review_agent)
    graph.add_node('itinerary_agent', itinerary_agent)
    graph.add_node('human_approval', human_approval_agent)
    graph.add_node('revision', revision_agent)
    graph.add_node('final_response', final_response_agent)
    graph.add_edge(START, 'supervisor')
    graph.add_conditional_edges('supervisor', first_agent, ROUTE_MAP)
    for agent in AGENT_ORDER:
        graph.add_conditional_edges(agent, after_specialist(agent), ROUTE_MAP)
    graph.add_conditional_edges('budget_agent', after_budget, {'alternative_planning': 'alternative_planning', 'itinerary_agent': 'itinerary_agent'})
    graph.add_edge('alternative_planning', 'budget_review')
    graph.add_conditional_edges('budget_review', after_budget_review, {'budget_agent': 'budget_agent', 'itinerary_agent': 'itinerary_agent', 'end': END})
    graph.add_edge('itinerary_agent', 'human_approval')
    graph.add_conditional_edges('human_approval', after_approval,
                                {'end': END, 'revision': 'revision', 'final_response': 'final_response'})
    graph.add_conditional_edges('revision', after_revision, ROUTE_MAP)
    graph.add_edge('final_response', END)
    return graph.compile(checkpointer=checkpointer)


def create_app():
    """Create a persistent graph. Keep the returned connection alive in the caller."""
    if not DATABASE_URL:
        raise RuntimeError('DATABASE_URL is required for durable Human-in-the-Loop checkpoints')
    conn = psycopg.connect(DATABASE_URL, autocommit=True, row_factory=dict_row)
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    return build_graph(checkpointer), conn
