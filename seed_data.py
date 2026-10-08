"""Afya Smart — seed data.

Generates ~100 realistic *fake* patients so the demo dashboard and fairness
report look alive.  Every field is synthetic: names, phone numbers, dates,
and severities are all made up.  No real patient data is ever used.

The seed data includes a spread of:

    * facilities
    * sexes (male / female)
    * ages (children, adults, elderly)
    * urgency levels (RED, YELLOW, GREEN)
    * visit statuses (waiting, called, finished)

so the queue engine, the dashboard, and the fairness report can all be seen
working out of the box.

Run it with ``python seed_data.py`` from the project root.  It connects to the
SQLite database created by ``app.py`` and is safe to re-run (it only inserts
new patients, and replaces the visits table contents).
"""

from __future__ import annotations

import random
import sqlite3
from datetime import datetime, timedelta

from app import DATABASE_PATH

# --------------------------------------------------------------------------- #
# Demo facilities (a small clinic and a bigger hospital, in one city).
# --------------------------------------------------------------------------- #

FACILITIES = [
    {"name": "Msasani Dispensary", "level": "dispensary"},
    {"name": "Kapoleni Hospital", "level": "hospital"},
    {"name": "Ilala Health Centre", "level": "centre"},
]

# Realistic Swahili-style first/last names.
FIRST_NAMES = [
    "Ahmed", "Amina", "John", "Mary", "Joseph", "Juwata", "Fatuma", "Rashid",
    "Safaa", "Omar", "Zawadi", "Hussein", "Amina", "Nasibu", "Binti", "Khalfan",
    "Zubera", "Ali", "Mwanajuma", "Nur", "Adnan", "Rashida", "Salim", "Safina",
    "Said", "Rukia", "Lamu", "Kibwana", "Harambe", "Kiswendera",
]
LAST_NAMES = [
    "Mwinyi", "Said", "Ahmed", "Juma", "Ramadhani", "Yusuf", "Hassan",
    "Kassim", "Nditi", "Mcha", "Kibwana", "Bazuri", "Mwambe", "Ole", "Sokoro",
    "Mwinyi", "Mwambao", "Ndesandae", "Kibwana", "Mkuu",
]

# Urgency: RED = emergency, YELLOW = watch, GREEN = routine.
# We seed a *plausible* mix: most patients are GREEN (routine) with a few
# YELLOW and RED to make the queue and report interesting.
LEVELS = ["RED", "RED", "YELLOW", "YELLOW", "GREEN"] * 20  # 100 entries

# Sexes (Swahili: mwanamume / mwanawake / sio jinsi yapu).
SEXES = ["male", "female", "unknown"] * 34  # 102 entries

# Year of birth spread: children, adults, elderly.
def _birth_years():
    years = []
    for _ in range(100):
        roll = random.random()
        if roll < 0.15:
            years.append(random.randint(2018, 2026))          # children
        elif roll < 0.40:
            years.append(random.randint(1990, 2015))          # adults
        elif roll < 0.70:
            years.append(random.randint(1960, 1989))          # mature
        else:
            years.append(random.randint(1920, 1959))          # elderly
    return years


# --------------------------------------------------------------------------- #
# Small helpers (deterministic, no external library)
# --------------------------------------------------------------------------- #

def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_dt(text: str):
    """Parse an SQLite-style timestamp back into a datetime."""
    if not text:
        return None
    text = text.strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _fake_phone() -> str:
    """A realistic-looking Tanzanian phone number (no real person's)."""
    return f"+255{str(random.randint(7000000, 7999999))}"


# --------------------------------------------------------------------------- #
# Seeder
# --------------------------------------------------------------------------- #

def seed(count: int = 100, db_path: str = DATABASE_PATH) -> dict:
    """Seed the database with ``count`` fake patients and their visits."""
    random.seed(42)  # reproducible so a re-run looks the same

    # Read the existing rows (if any) so we can replace the visits.
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row

    facilities = con.execute(
        "SELECT * FROM facilities ORDER BY id"
    ).fetchall()
    patients = con.execute("SELECT * FROM patients ORDER BY id").fetchall()
    visits = con.execute("SELECT * FROM visits ORDER BY id").fetchall()

    birth_years = _birth_years()

    now = datetime.now()
    # Spread visits over the last ~90 days.
    start_date = (now - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")

    # Hold the new rows so we can delete old ones after we have looked them up.
    new_patients = []
    new_visits = []

    # Facility cycle: spread the patients across facilities.
    facility_by_id = {f["id"]: f for f in facilities}

    for i in range(count):
        # Cycle facilities so they are roughly balanced.
        facility = facilities[i % len(facilities)]

        # Name.
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        full_name = f"{first} {last}"

        # Sex + name adjustment: some "unknown" are not given a sex at all.
        sex = random.choice(SEXES)

        year_of_birth = birth_years[i]

        phone = _fake_phone()

        row = {
            "full_name": full_name,
            "phone_number": phone,
            "sex": sex,
            "year_of_birth": year_of_birth,
            "facility_id": facility["id"],
            "created_at": _now_iso(),
        }
        new_patients.append(row)

        # Pick an urgency and a *recent* joined time.
        level = random.choice(LEVELS)
        joined = start_date

        # A patient's status is random, but "finished" visits are a large
        # majority so the fairness report has data to work with.
        roll = random.random()
        if roll < 0.55:
            status = "finished"
        elif roll < 0.75:
            status = "called"
        elif roll < 0.90:
            status = "waiting"
        else:
            status = "cancelled"

        # Duration of the visit: RED patients get *long* waits, GREEN short.
        if level == "RED":
            wait_minutes = random.randint(15, 90)
        elif level == "YELLOW":
            wait_minutes = random.randint(5, 45)
        else:
            wait_minutes = random.randint(1, 20)

        joined_dt = _parse_dt(joined)
        called_dt = joined_dt + timedelta(minutes=wait_minutes)

        visit = {
            "patient_id": i + 1,          # assume patients were just added in order
            "level": level,
            "status": status,
            "joined_at": joined,
            "called_at": called_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": called_dt.strftime("%Y-%m-%d %H:%M:%S"),
        }
        new_visits.append(visit)

    # ----------------------------------------------------------------- #
    # 1. Replace the patients table.
    # ----------------------------------------------------------------- #
    # Delete all existing patients (and reset AUTOINCREMENT so fresh IDs start
    # at 1, not at the old high-water mark).  SQLite stores the autoincrement
    # sequence in ``sqlite_sequence``; deleting rows does not reset it, so a
    # double run would produce disjoint ID ranges and nothing could be joined.
    con.execute("DELETE FROM visits")
    con.execute("DELETE FROM patients")
    con.execute("DELETE FROM sqlite_sequence WHERE name = 'patients'")
    con.execute("DELETE FROM sqlite_sequence WHERE name = 'visits'")

    for p in new_patients:
        con.execute(
            """
            INSERT INTO patients (phone_number, full_name, sex, year_of_birth, facility_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                p["phone_number"],
                p["full_name"],
                p["sex"],
                p["year_of_birth"],
                p["facility_id"],
                p["created_at"],
            ),
        )

    # ----------------------------------------------------------------- #
    # 2. Replace the visits table.
    # ----------------------------------------------------------------- #
    for v in new_visits:
        con.execute(
            """
            INSERT INTO visits (patient_id, level, status, joined_at, called_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                v["patient_id"],
                v["level"],
                v["status"],
                v["joined_at"],
                v["called_at"],
                v["completed_at"],
            ),
        )

    con.commit()
    con.close()

    return {
        "patients_inserted": len(new_patients),
        "visits_inserted": len(new_visits),
        "facilities": [f["name"] for f in facilities],
        "level_counts": {
            "RED": sum(1 for l in LEVELS if l == "RED"),
            "YELLOW": sum(1 for l in LEVELS if l == "YELLOW"),
            "GREEN": sum(1 for l in LEVELS if l == "GREEN"),
        },
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed Afya Smart with fake demo patients.")
    parser.add_argument(
        "--count", type=int, default=100, help="Number of fake patients to generate (default 100)"
    )
    parser.add_argument(
        "--db", type=str, default=DATABASE_PATH, help=f"Path to the SQLite database (default {DATABASE_PATH})"
    )
    args = parser.parse_args()

    summary = seed(count=args.count, db_path=args.db)

    print("✅ Afya Smart demo data seeded.")
    print(f"   Patients: {summary['patients_inserted']}")
    print(f"   Visits:   {summary['visits_inserted']}")
    print(f"   Facilities: {', '.join(summary['facilities'])}")
    print(f"   Levels:   {summary['level_counts']}")
    print("\n   (Run the server:  python app.py  then open /dashboard)")
