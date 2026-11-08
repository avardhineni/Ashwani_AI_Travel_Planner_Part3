"""Shared graph state, not the same as Streamlit session state."""
from typing import Annotated, Any, TypedDict
import operator
from langchain_core.messages import AnyMessage

class TravelState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], operator.add]
    user_id: str
    user_query: str
    request_status: str
    rejection_reason: str
    trip_constraints: dict[str, Any]
    selected_agents: list[str]
    supervisor_reasoning: str
    flight_results: str
    hotel_results: str
    weather_results: str
    budget_results: str
    alternative_plan: str
    budget_assessment: dict[str, Any]
    quotes: list[dict[str, Any]]
    approved_budget_inr: int | None
    budget_reviewed: bool
    budget_decision: str
    itinerary: str
    approval_request: str
    human_feedback: str
    approved: bool
    revision_count: int
    final_response: str
    final_status: str
    llm_calls: Annotated[int, operator.add]
