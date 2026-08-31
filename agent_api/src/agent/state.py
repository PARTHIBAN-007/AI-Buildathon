from typing import TypedDict, List, Dict, Any


class AgentMessage(TypedDict):
    sender: str
    text: str
    timestamp: str


class CustomerProfile(TypedDict):
    summary: str
    total_orders: int
    max_discount: float


class AgentState(TypedDict):
    messages: List[AgentMessage]
    customer_profile: CustomerProfile | Dict[str, Any]
    checkout_id: str | None
    summary: str | None
