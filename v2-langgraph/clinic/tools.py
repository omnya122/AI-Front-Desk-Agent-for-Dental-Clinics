"""Agent tools.

Structured facts (prices, hours, doctors, insurance) come from Postgres tables and are returned whole:
they are tiny, so the model reads the exact rows instead of relying on retrieval. Only prose goes
through the vector store.
"""
from datetime import datetime

from langchain_core.tools import tool

from . import booking, db
from .config import get_settings
from .embeddings import embedder

_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@tool
async def get_price_list() -> str:
    """Full price list: procedure name, price in EGP and duration in minutes. Match the patient's wording
    loosely (e.g. 'checkup' -> 'Checkup & Consultation'; Arabic questions map to the English names)."""
    rows = await db.fetch("SELECT procedure, price_egp, duration_min FROM pricing ORDER BY price_egp")
    if not rows:
        return "NO_RESULTS"
    return "\n".join(f"{r['procedure']}: {r['price_egp']} EGP, {r['duration_min']} min" for r in rows)


@tool
async def get_hours() -> str:
    """Clinic opening and closing hours for every day of the week."""
    rows = await db.fetch("SELECT day_index, opens, closes FROM hours ORDER BY day_index")
    if not rows:
        return "NO_RESULTS"
    return "\n".join(
        f"{_DAYS[r['day_index']]}: " + (f"{r['opens']:%H:%M}-{r['closes']:%H:%M}" if r["opens"] else "closed")
        for r in rows
    )


@tool
async def get_doctors() -> str:
    """Doctors with their specialty and the weekdays they work."""
    rows = await db.fetch("SELECT name, specialty, days FROM doctors ORDER BY name")
    if not rows:
        return "NO_RESULTS"
    return "\n".join(f"{r['name']} - {r['specialty']} - days: {', '.join(r['days'])}" for r in rows)


@tool
async def get_insurance() -> str:
    """Insurance providers the clinic works with and what each one covers."""
    rows = await db.fetch("SELECT provider, coverage, notes FROM insurance ORDER BY provider")
    if not rows:
        return "NO_RESULTS"
    return "\n".join(f"{r['provider']}: {r['coverage']}" + (f" ({r['notes']})" if r["notes"] else "") for r in rows)


@tool
async def search_clinic_docs(query: str) -> str:
    """Search the clinic's written documents: pre-visit instructions, aftercare, cancellation policy,
    location, parking and payment methods. Pass a short, self-contained query in English."""
    s = get_settings()
    vec = db.vector_literal(await embedder("retrieval_query").aembed_query(query))
    rows = await db.fetch(
        """SELECT filename, content, 1 - (embedding <=> %s::vector) AS sim
           FROM doc_chunks ORDER BY embedding <=> %s::vector LIMIT 4""",
        (vec, vec),
    )
    rows = [r for r in rows if float(r["sim"]) >= s.retrieval_min_similarity]
    if not rows:
        return "NO_RESULTS"
    return "\n\n".join(f"[{r['filename']}] {r['content']}" for r in rows)


@tool
async def check_availability(date: str, part_of_day: str = "any") -> str:
    """Find up to 3 free appointment slots on or after `date` (YYYY-MM-DD, clinic local date).
    part_of_day: morning | afternoon | evening | any. Returns slot_id values to copy into offered_slots."""
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return "ERROR: date must be formatted YYYY-MM-DD"
    slots = await booking.free_slots(day, part_of_day.lower())
    if not slots:
        return "NO_RESULTS: no free slots in the next 14 days for that request"
    return "\n".join(f"slot_id={booking.slot_id(s)}  ({booking.fmt_slot(s)})" for s in slots)


TOOLS = [get_price_list, get_hours, get_doctors, get_insurance, search_clinic_docs, check_availability]
