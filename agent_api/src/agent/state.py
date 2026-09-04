from typing import Annotated, Any, Dict, Optional, TypedDict
from langgraph.graph.message import add_messages


class CustomerProfile(TypedDict, total=False):
    summary: str
    total_orders: int
    max_discount: float


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    customer_profile: CustomerProfile
    checkout_id: Optional[str]
    summary: Optional[str]
    context: Dict[str, Any]
