"""The LangGraph: deterministic safety gates around a tool-calling agent, plus a booking state machine.

                         ┌─ non_text / start / rate_limited ─────────────┐
   ingest ──route──┬─ emergency  (deterministic, bypasses everything)    │
                   ├─ clinical   (deterministic keyword gate, no LLM)    ├─► log_turn ─► END
                   ├─ callback ► booking_callback  (slot / confirm / cancel buttons)
                   ├─ booking_input (collecting name / phone)            │
                   └─ agent ► prepare_agent ► agent_llm ⇄ tools          │
                                                 └► finalize ─┬► agent_reply    ──┤
                                                              └► agent_escalate ──┘

Nodes never talk to Telegram. They append to `state["outbox"]`, which the transport layer sends - so the
whole graph can be driven from tests / the eval harness without a bot.
"""
import logging
import re
import time
from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
    trim_messages,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import ValidationError

from . import booking, db, safety
from .config import get_settings
from .i18n import CANCEL_WORDS, detect_lang, t
from .prompts import build_system_prompt
from .schemas import Respond
from .state import State
from .tools import TOOLS

log = logging.getLogger(__name__)

MAX_TOOL_MESSAGES = 6  # hard cap on tool calls per patient message (cost + loop guard)


# --------------------------------------------------------------------------- helpers

def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return "".join(p if isinstance(p, str) else p.get("text", "") for p in content if isinstance(p, (str, dict)))


def _say(state: State, text: str, buttons: list | None = None, **update: Any) -> dict[str, Any]:
    out = {"chat_id": state["chat_id"], "text": text, "buttons": buttons or []}
    return {"outbox": [out], **update}


async def _escalate(state: State, *, layer: str, category: str, reason: str, user_key: str) -> dict[str, Any]:
    """Log, alert staff with context, and reply with a canned message - never model-generated text."""
    s = get_settings()
    question = state.get("text") or state.get("callback_data", "")
    await db.log_escalation(state["chat_id"], question, category, layer, reason)
    who = f"@{state['username']}" if state.get("username") else "(no username)"
    outbox = [{"chat_id": state["chat_id"], "text": t(user_key, state.get("lang", "en")), "buttons": []}]
    if s.staff_chat_id:
        outbox.append({
            "chat_id": s.staff_chat_id,
            "text": f"🚨 {category} escalation ({layer})\nPatient: {who}, chat_id {state['chat_id']}\n"
                    f"Reason: {reason}\nMessage: {question}",
            "buttons": [],
        })
    return {"outbox": outbox, "escalated": True, "layer": layer, "category": category}


def _repair_history(messages: list) -> list[RemoveMessage]:
    """A crash between `agent_llm` and `tools` leaves an AI tool-call with no result, which the Gemini API
    rejects on every later turn. Drop such dangling calls (and any orphaned results) before continuing."""
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    bad_ai = [
        m for m in messages
        if isinstance(m, AIMessage) and any(c["id"] not in answered for c in (m.tool_calls or []))
    ]
    bad_ids = {c["id"] for m in bad_ai for c in m.tool_calls}
    orphans = [m for m in messages if isinstance(m, ToolMessage) and m.tool_call_id in bad_ids]
    return [RemoveMessage(id=m.id) for m in [*bad_ai, *orphans]]


# --------------------------------------------------------------------------- entry + deterministic gates

async def ingest(state: State) -> dict[str, Any]:
    s = get_settings()
    text = (state.get("text") or "").strip()
    kind = state["kind"]
    update: dict[str, Any] = {
        "t0": time.time(), "text": text, "outbox": [], "layer": "", "category": "", "confidence": 0.0,
        "escalated": False, "answer": None, "escalation": None, "trigger": "",
        "tokens_in": 0, "tokens_out": 0,
    }
    if kind == "text":
        update["lang"] = detect_lang(text)

    stage = (state.get("booking") or {}).get("stage")
    if kind == "non_text":
        route = "non_text"
    elif kind == "callback":
        route = "callback"
    elif text.split("@")[0].lower() == "/start":
        route = "start"
    elif safety.is_emergency(text):
        route = "emergency"
    elif await db.hit_rate_limit(state["chat_id"], s.rate_limit_per_hour):
        route = "rate_limited"
    elif hit := safety.clinical_match(text):
        route, update["trigger"] = "clinical", hit
    elif stage in ("await_name", "await_phone"):
        route = "booking_input"
    else:
        route = "agent"
    update["route"] = route
    return update


async def welcome(state: State) -> dict[str, Any]:
    return _say(state, t("welcome", state.get("lang", "en")), booking=None, layer="static")


async def non_text(state: State) -> dict[str, Any]:
    return _say(state, t("non_text", state.get("lang", "en")), layer="static")


async def rate_limited(state: State) -> dict[str, Any]:
    return _say(state, t("rate_limited", state.get("lang", "en")), layer="rate_limit")


async def emergency(state: State) -> dict[str, Any]:
    return await _escalate(state, layer="emergency_gate", category="Emergency",
                           reason="emergency pattern matched", user_key="emergency") | {"booking": None}


async def clinical(state: State) -> dict[str, Any]:
    return await _escalate(state, layer="keyword_gate", category="Clinical",
                           reason=f"keyword: {state.get('trigger')}", user_key="escalated")


# --------------------------------------------------------------------------- booking state machine

async def booking_callback(state: State) -> dict[str, Any]:
    action, _, arg = state.get("callback_data", "").partition(":")
    lang, chat_id = state.get("lang", "en"), state["chat_id"]
    pending = state.get("booking") or {}
    base = {"layer": "booking", "category": "booking"}

    if action == "slot":
        slot = booking.parse_slot(arg)
        if not slot or not await booking.is_bookable(slot):
            return _say(state, t("slot_gone", lang), **base)
        procedure = (state.get("offered") or {}).get("procedure")
        return _say(state, t("ask_name", lang), **base,
                    booking={"stage": "await_name", "slot": arg, "procedure": procedure})

    if action == "confirm":
        # A double-tap lands here a second time with booking already cleared -> "expired", no second insert.
        slot = booking.parse_slot(arg)
        if pending.get("stage") != "await_confirm" or pending.get("slot") != arg or not slot:
            return _say(state, t("expired", lang), **base)
        result = await booking.create_booking(chat_id, slot, pending["name"], pending["phone"], pending.get("procedure"))
        when = booking.fmt_slot(slot)
        key = {"created": "booked", "duplicate": "already_booked", "taken": "slot_gone"}[result]
        return _say(state, t(key, lang, when=when), **base, booking=None)

    if action == "cancel":
        return _say(state, t("booking_cancelled", lang), **base, booking=None)
    return _say(state, t("expired", lang), **base)


async def booking_input(state: State) -> dict[str, Any]:
    lang, text = state.get("lang", "en"), state["text"]
    b = dict(state["booking"])
    base = {"layer": "booking", "category": "booking"}

    if text.lower() in CANCEL_WORDS:
        return _say(state, t("booking_cancelled", lang), **base, booking=None)

    if b["stage"] == "await_name":
        if not (2 <= len(text) <= 60) or any(c.isdigit() for c in text) or "?" in text:
            return _say(state, t("bad_name", lang), **base)
        b.update(name=text, stage="await_phone")
        return _say(state, t("ask_phone", lang), **base, booking=b)

    phone = booking.normalize_phone(text)
    if not phone:
        return _say(state, t("bad_phone", lang), **base)
    b.update(phone=phone, stage="await_confirm")
    slot = booking.parse_slot(b["slot"])
    summary = t("confirm_summary", lang, when=booking.fmt_slot(slot),
                procedure=b.get("procedure") or t("default_procedure", lang), name=b["name"], phone=phone)
    buttons = [[
        {"text": t("btn_confirm", lang), "data": f"confirm:{b['slot']}"},
        {"text": t("btn_cancel", lang), "data": "cancel:x"},
    ]]
    return _say(state, summary, buttons, **base, booking=b)


# --------------------------------------------------------------------------- agent path

async def prepare_agent(state: State) -> dict[str, Any]:
    msgs = state.get("messages", [])
    fixes = _repair_history(msgs)
    return {"messages": [*fixes, HumanMessage(content=state["text"])], "turn_start": len(msgs) - len(fixes)}


def after_llm(state: State) -> str:
    calls = getattr(state["messages"][-1], "tool_calls", None) or []
    if not calls or any(c["name"] == Respond.__name__ for c in calls):
        return "finalize"
    used = sum(isinstance(m, ToolMessage) for m in state["messages"][state["turn_start"]:])
    return "finalize" if used >= MAX_TOOL_MESSAGES else "tools"


def _window(messages: list) -> list:
    return trim_messages(
        messages, max_tokens=get_settings().memory_window, token_counter=len,
        strategy="last", start_on="human", include_system=False,
    )


async def finalize(state: State, structured=None) -> dict[str, Any]:
    """Parse the structured answer, apply agent-level + output-level gates, and clean the memory."""
    msgs = state["messages"]
    last = msgs[-1]
    answer: Respond | None = None
    for call in getattr(last, "tool_calls", None) or []:
        if call["name"] == Respond.__name__:
            try:
                answer = Respond.model_validate(call["args"])
            except ValidationError as exc:
                log.warning("Invalid Respond payload: %s", exc)

    plain = _text(last.content).strip()
    if answer is None and structured is not None and not getattr(last, "tool_calls", None):
        # The model replied in free text (or wrote the Respond call as text). Ask once for a proper structured answer.
        try:
            answer = await structured.ainvoke([
                SystemMessage(content=build_system_prompt()), *_window(msgs),
                HumanMessage(content="Now give your final reply to the patient."),
            ])
        except Exception:
            log.warning("Structured fallback failed", exc_info=True)
    if answer is None:  # still nothing usable, or the tool cap was hit
        looks_broken = "Respond{" in plain or "default_api" in plain
        usable = plain and not looks_broken
        if not usable:
            log.warning("No usable model answer. Last message: %r | tool_calls=%r | finish=%r",
                        plain[:500], getattr(last, "tool_calls", None), getattr(last, "response_metadata", {}))
        answer = Respond(
            answer=plain if usable else "I'm sorry, I couldn't find that information. Please contact the clinic directly.",
            category="other", confidence=0.3 if usable else 0.0, clinical_flag=False, needs_staff=False,
        )

    tokens_in = tokens_out = 0
    for m in msgs[state["turn_start"]:]:
        if isinstance(m, AIMessage) and m.usage_metadata:
            tokens_in += m.usage_metadata.get("input_tokens", 0)
            tokens_out += m.usage_metadata.get("output_tokens", 0)

    escalation = None
    if answer.clinical_flag:
        escalation = {"layer": "agent", "category": "Clinical", "reason": "agent set clinical_flag"}
    elif answer.needs_staff:
        escalation = {"layer": "agent", "category": "Other", "reason": f"agent set needs_staff ({answer.category})"}
    elif hit := safety.output_violation(answer.answer):
        escalation = {"layer": "output_guard", "category": "Clinical", "reason": f"output matched: {hit}"}

    # Replace the last AI message (which may hold a Respond tool-call with no result) by plain text, so the
    # stored history is always valid - and never contains a blocked answer.
    kept = "" if escalation else answer.answer
    return {
        "answer": answer.model_dump(),
        "escalation": escalation,
        "category": answer.category,
        "confidence": max(0.0, min(1.0, float(answer.confidence))),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "messages": [AIMessage(id=last.id, content=kept or t("escalated", state.get("lang", "en")))],
    }


def after_finalize(state: State) -> str:
    return "agent_escalate" if state.get("escalation") else "agent_reply"


async def agent_escalate(state: State) -> dict[str, Any]:
    e = state["escalation"]
    return await _escalate(state, layer=e["layer"], category=e["category"], reason=e["reason"], user_key="escalated")


async def agent_reply(state: State) -> dict[str, Any]:
    answer = state["answer"]
    slots = []
    for raw in answer.get("offered_slots", [])[:3]:
        slot = booking.parse_slot(raw)
        if slot and await booking.is_bookable(slot):  # never show a slot the model invented
            slots.append(slot)
    buttons = [[{"text": f"📅 {booking.fmt_slot(s)}", "data": f"slot:{booking.slot_id(s)}"}] for s in slots]
    update: dict[str, Any] = {"layer": "agent"}
    if slots:
        update["offered"] = {"procedure": answer.get("procedure")}
    return _say(state, answer["answer"], buttons, **update)


# --------------------------------------------------------------------------- audit

async def log_turn(state: State) -> dict[str, Any]:
    s = get_settings()
    latency_ms = int((time.time() - state.get("t0", time.time())) * 1000)
    cost = (state.get("tokens_in", 0) * s.price_in_per_m + state.get("tokens_out", 0) * s.price_out_per_m) / 1e6
    try:
        await db.log_turn({
            "chat_id": state["chat_id"], "update_id": state.get("update_id"),
            "question": state.get("text") or state.get("callback_data", ""),
            "route": state.get("route"), "layer": state.get("layer"), "category": state.get("category"),
            "confidence": state.get("confidence", 0.0), "escalated": state.get("escalated", False),
            "tokens_in": state.get("tokens_in", 0), "tokens_out": state.get("tokens_out", 0),
            "cost_usd": cost, "latency_ms": latency_ms,
        })
    except Exception:  # an audit failure must never block the patient's reply
        log.exception("Failed to write turn log")
    return {"latency_ms": latency_ms, "cost_usd": cost}


# --------------------------------------------------------------------------- assembly

def build_graph(checkpointer=None):
    s = get_settings()
    base = ChatGoogleGenerativeAI(model=s.chat_model, temperature=0)
    llm = base.bind_tools([*TOOLS, Respond])
    structured = base.with_structured_output(Respond)

    async def agent_llm(state: State) -> dict[str, Any]:
        reply = await llm.ainvoke([SystemMessage(content=build_system_prompt()), *_window(state["messages"])])
        return {"messages": [reply]}

    async def finalize_node(state: State) -> dict[str, Any]:
        return await finalize(state, structured)

    g = StateGraph(State)
    g.add_node("ingest", ingest)
    g.add_node("welcome", welcome)
    g.add_node("non_text", non_text)
    g.add_node("rate_limited", rate_limited)
    g.add_node("emergency", emergency)
    g.add_node("clinical", clinical)
    g.add_node("booking_callback", booking_callback)
    g.add_node("booking_input", booking_input)
    g.add_node("prepare_agent", prepare_agent)
    g.add_node("agent_llm", agent_llm)
    g.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))
    g.add_node("finalize", finalize_node)
    g.add_node("agent_reply", agent_reply)
    g.add_node("agent_escalate", agent_escalate)
    g.add_node("log_turn", log_turn)

    g.add_edge(START, "ingest")
    g.add_conditional_edges("ingest", lambda st: st["route"], {
        "non_text": "non_text", "start": "welcome", "emergency": "emergency", "rate_limited": "rate_limited",
        "clinical": "clinical", "callback": "booking_callback", "booking_input": "booking_input",
        "agent": "prepare_agent",
    })
    g.add_edge("prepare_agent", "agent_llm")
    g.add_conditional_edges("agent_llm", after_llm, {"tools": "tools", "finalize": "finalize"})
    g.add_edge("tools", "agent_llm")
    g.add_conditional_edges("finalize", after_finalize, {"agent_reply": "agent_reply", "agent_escalate": "agent_escalate"})
    for node in ("welcome", "non_text", "rate_limited", "emergency", "clinical", "booking_callback",
                 "booking_input", "agent_reply", "agent_escalate"):
        g.add_edge(node, "log_turn")
    g.add_edge("log_turn", END)
    return g.compile(checkpointer=checkpointer)
