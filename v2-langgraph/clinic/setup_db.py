"""Create tables and load the structured clinic data from data/sheets/*.csv.   Run: python -m clinic.setup_db

The CSVs are the source of truth: each run replaces the table contents, so edit a CSV and re-run to update.
"""
import asyncio
import csv
import sys
from datetime import datetime, time
from pathlib import Path

from . import db

ROOT = Path(__file__).resolve().parent.parent
SHEETS = ROOT / "data" / "sheets"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]  # index = weekday()


def _rows(name: str) -> list[dict[str, str]]:
    with open(SHEETS / name, encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): v.strip() for k, v in row.items()} for row in csv.DictReader(f)]


def _clock(value: str) -> time | None:
    return None if value.lower() == "closed" else datetime.strptime(value, "%I:%M %p").time()


async def main() -> None:
    await db.init_pool()
    await db.run_script((ROOT / "schema.sql").read_text(encoding="utf-8"))
    for table in ("pricing", "hours", "doctors", "insurance"):
        await db.execute(f"DELETE FROM {table}")

    for r in _rows("Pricing.csv"):
        await db.execute("INSERT INTO pricing VALUES (%s, %s, %s)",
                         (r["Procedure"], int(r["Price (EGP)"]), int(r["Duration (min)"])))
    for r in _rows("Hours.csv"):
        await db.execute("INSERT INTO hours VALUES (%s, %s, %s, %s)",
                         (DAYS.index(r["Day"]), r["Day"], _clock(r["Open"]), _clock(r["Close"])))
    for r in _rows("Doctors.csv"):
        days = [d.strip() for d in r["Days Available"].split(",")]
        await db.execute("INSERT INTO doctors VALUES (%s, %s, %s)", (r["Name"], r["Specialty"], days))
    for r in _rows("Insurance.csv"):
        await db.execute("INSERT INTO insurance VALUES (%s, %s, NULL)", (r["Provider"], r["Coverage Notes"]))

    await db.close_pool()
    print("Database ready: schema applied and clinic data loaded from data/sheets/*.csv")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
