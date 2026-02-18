from typing import TypedDict, Optional, List, Dict

from app.models.schemas import TripRequest, TripPlan, Attraction, Hotel, WeatherInfo
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TripPlanningState(TypedDict, total=False):
    # Inputs
    request: TripRequest
    user_id: str

    # Intermediate results
    attractions: List[Attraction]
    weather: Optional[WeatherInfo]
    hotels: List[Hotel]
    messages: List[BaseMessage]

    # Node execution status
    node_status: Dict[str, str]
    node_errors: Dict[str, List[str]]

    # Outputs
    trip_plan: Optional[TripPlan]

    # Error handling and fallbacks
    error: Optional[str]
    fallback_activated: bool

    # Metadata
    execution_time_ms: Optional[int]
    retry_count: int
    trace_id: Optional[str]
    checkpoint_id: Optional[str]

    # Performance / timing data
    node_timings: Dict[str, float]


def create_initial_state(user_id: str, request: TripRequest) -> TripPlanningState:
    """
    Create and return the initial TripPlanningState for a new planning session.
    """
    return {
        "request": request,
        "user_id": user_id,
        "attractions": [],
        "weather": None,
        "hotels": [],
        "messages": [],
        "node_status": {},
        "node_errors": {},
        "trip_plan": None,
        "error": None,
        "fallback_activated": False,
        "execution_time_ms": None,
        "retry_count": 0,
        "trace_id": None,
        "checkpoint_id": None,
        "node_timings": {},
    }


def update_node_status(
    state: TripPlanningState,
    node: str,
    status: str,
    errors: Optional[List[str]] = None,
    new_messages: Optional[List[BaseMessage]] = None,
) -> TripPlanningState:
    """
    Update the status and optional errors for a given node.
    Optionally append new messages to the state's message list using add_messages.
    """
    if "node_status" not in state or state.get("node_status") is None:
        state["node_status"] = {}
    state["node_status"][node] = status

    if errors is not None:
        if "node_errors" not in state or state.get("node_errors") is None:
            state["node_errors"] = {}
        state["node_errors"][node] = errors

    if new_messages:
        if "messages" not in state or state.get("messages") is None:
            state["messages"] = []
        # mutate in-place using LangGraph helper
        add_messages(state["messages"], new_messages)  # type: ignore[arg-type]

    return state


def is_all_parallel_nodes_completed(state: TripPlanningState, nodes: List[str]) -> bool:
    """
    Check whether all provided parallel nodes have completed execution.
    """
    statuses = state.get("node_status", {})  # type: ignore[assignment]
    return all(statuses.get(n) == "completed" for n in nodes)


def has_critical_errors(state: TripPlanningState) -> bool:
    """
    Determine if any node has reported critical errors.
    """
    node_errors = state.get("node_errors", {})  # type: ignore[assignment]
    for errs in node_errors.values():
        if errs:
            return True
    return False


def get_state_summary(state: TripPlanningState) -> str:
    """
    Produce a concise textual summary of the current state.
    """
    node_status = state.get("node_status", {})  # type: ignore[assignment]
    counts = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0}
    for s in node_status.values():
        if s in counts:
            counts[s] += 1
        else:
            # unknown statuses treated as pending to avoid miscount
            counts["pending"] += 1

    error_flag = "Yes" if (state.get("error") or has_critical_errors(state)) else "No"
    summary = (
        f"Nodes - pending: {counts['pending']}, in_progress: {counts['in_progress']}, "
        f"completed: {counts['completed']}, failed: {counts['failed']}; "
        f"Critical errors: {error_flag}"
    )
    return summary
