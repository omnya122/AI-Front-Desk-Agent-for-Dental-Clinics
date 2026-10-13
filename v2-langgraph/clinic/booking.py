"""Availability + idempotent booking against Postgres.

Slots are fixed 30-minute blocks inside the clinic's opening hours (single chair). A slot is identified
everywhere (tool output, button callback_data, DB) by its clinic-local `YYYY-MM-DDTHH:MM` string.
"""
import re
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from . import db
from .config import get_settings

SLOT = timedelta(minutes=30)
LEAD = timedelta(hours=2)       # no bookings starting sooner than this
HORIZON_DAYS = 14
_PARTS = {"morning": (0, 12), "afternoon": (12, 17), "evening": (17, 24)}


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_phone(raw: str) -> str | None:
    """Egyptian mobile (010/011/012/015 + 8 digits, with optional +20 / 0020 prefix) -> '01XXXXXXXXX'.
    Other countries must be written with a leading '+'. Returns None if the number is not valid."""
    s = re.sub(r"[ \-().]", "", raw.translate(_AR_DIGITS))
    if s.startswith("00"):
        s = "+" + s[2:]
    if m := re.fullmatch(r"\+?20(1[0125]\d{8})", s):
        return "0" + m.group(1)
    if re.fullmatch(r"01[0125]\d{8}", s):
        return s
    if re.fullmatch(r"\+(?!20)[1-9]\d{7,14}", s):
        return s
    return None


def slot_id(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def parse_slot(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M").replace(tzinfo=tz())
    except (ValueError, TypeError):
        return None


def fmt_slot(dt: datetime) -> str:
    return dt.strftime("%a %d %b, %H:%M")


def _in_part(dt: datetime, part: str) -> bool:
    lo, hi = _PARTS.get(part, (0, 24))
    return lo <= dt.hour < hi


async def free_slots(start: date, part: str = "any", limit: int = 3) -> list[datetime]:
    hours = {r["day_index"]: r for r in await db.fetch("SELECT day_index, opens, closes FROM hours")}
    now = datetime.now(tz())
    earliest = now + LEAD
    booked = {
        r["slot_start"] for r in await db.fetch("SELECT slot_start FROM bookings WHERE slot_start >= %s", (earliest,))
    }
    out: list[datetime] = []
    day = max(start, now.date())
    end_day = day + timedelta(days=HORIZON_DAYS)
    while day < end_day and len(out) < limit:
        h = hours.get(day.weekday())
        if h and h["opens"] and h["closes"]:
            t = datetime.combine(day, h["opens"], tz())
            close = datetime.combine(day, h["closes"], tz())
            while t + SLOT <= close and len(out) < limit:
                if t >= earliest and t not in booked and _in_part(t, part):
                    out.append(t)
                t += SLOT
        day += timedelta(days=1)
    return out


async def is_bookable(slot: datetime) -> bool:
    """Re-validated at offer time AND at confirm time - never trust the model or a stale button."""
    rows = await db.fetch("SELECT opens, closes FROM hours WHERE day_index = %s", (slot.weekday(),))
    if not rows or not rows[0]["opens"] or not rows[0]["closes"]:
        return False
    opens = datetime.combine(slot.date(), rows[0]["opens"], tz())
    close = datetime.combine(slot.date(), rows[0]["closes"], tz())
    if slot < opens or slot + SLOT > close or (slot - opens) % SLOT:
        return False
    if slot < datetime.now(tz()) + LEAD:
        return False
    return not await db.fetch("SELECT 1 FROM bookings WHERE slot_start = %s", (slot,))


async def create_booking(
    chat_id: int, slot: datetime, name: str, phone: str, procedure: str | None
) -> Literal["created", "duplicate", "taken"]:
    rows = await db.fetch(
        """INSERT INTO bookings (chat_id, slot_start, procedure, patient_name, phone)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (slot_start) DO NOTHING RETURNING id""",
        (chat_id, slot, procedure, name, phone),
    )
    if rows:
        return "created"
    owner = await db.fetch("SELECT chat_id FROM bookings WHERE slot_start = %s", (slot,))
    return "duplicate" if owner and owner[0]["chat_id"] == chat_id else "taken"
