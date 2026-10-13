from typing import Annotated, Any, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class State(TypedDict, total=False):
    # --- persisted across turns by the checkpointer (thread_id = Telegram chat id) ---
    messages: Annotated[list[AnyMessage], add_messages]
    booking: Optional[dict[str, Any]]   # {stage, slot, procedure, name, phone}
    offered: Optional[dict[str, Any]]   # {procedure} remembered when slot buttons were shown
    lang: str

    # --- input for this turn ---
    chat_id: int
    update_id: Optional[int]
    username: Optional[str]
    kind: str                           # text | callback | non_text
    text: str
    callback_data: str

    # --- per-turn working fields (reset by `ingest`) ---
    route: str
    trigger: str                        # keyword / pattern that fired a deterministic gate
    turn_start: int
    t0: float
    answer: Optional[dict[str, Any]]    # parsed `Respond` payload
    escalation: Optional[dict[str, str]]
    outbox: list[dict[str, Any]]        # [{chat_id, text, buttons: [[{text, data}]]}] - sent by the transport layer
    layer: str
    category: str
    confidence: float
    escalated: bool
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float
