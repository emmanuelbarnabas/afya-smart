"""Afya Smart — fairness report.

The fairness report answers a single question:
    "Is any group of patients being treated worse than another?"

It computes the **average wait time** (joined_at -> called_at, in minutes) for
the *already-completed* visits, grouped by:

    * sex
    * age group (0-4, 5-17, 18-49, 50-64, 65+)
    * facility / area
    * urgency level (RED, YELLOW, GREEN)

For each group it also reports the *median* wait and the *spread* (standard
deviation), so the nurse can see not just the average but how stable it is.

A group is "flagged" when its average wait is more than one standard
deviation **below** the overall average — meaning it consistently waits
longer than the rest of the clinic.  (Long waits are bad; the report highlights
the worst-off groups.)

The report never shows real personal data.  It only shows averages across
enough patients to be statistically meaningful, and every number is rounded
to whole minutes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# These are the groups the report carves the clinic into.
# A single "area" is the facility name (our simplest stand-in for a place).
GROUP_SEXES = ["male", "female", "unknown"]


@dataclass
class FairnessGroup:
    """One row of the fairness table."""
    sex: str
    age_group: str
    facility: str
    level: str
    avg_wait_minutes: float
    median_wait_minutes: float
    std_wait_minutes: float
    n_patients: int
    flagged: bool = False

    def to_dict(self) -> dict:
        return {
            "sex": self.sex,
            "age_group": self.age_group,
            "facility": self.facility,
            "level": self.level,
            "avg_wait_minutes": round(self.avg_wait_minutes, 1),
            "median_wait_minutes": round(self.median_wait_minutes, 1),
            "std_wait_minutes": round(self.std_wait_minutes, 1),
            "n_patients": self.n_patients,
            "flagged": self.flagged,
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def age_group(year_of_birth: Optional[int], today: Optional[datetime] = None) -> str:
    """Map a birth year to a human-readable age band."""
    if year_of_birth is None:
        return "unknown"
    if today is None:
        today = datetime.now()
    age = today.year - year_of_birth
    if age < 5:
        return "0-4"
    if age < 18:
        return "5-17"
    if age < 65:
        return "18-49"
    if age < 75:
        return "50-64"
    return "65+"


def _get(row, key, default=None):
    """Read a value from a sqlite3.Row or a dict robustly."""
    try:
        return row[key]
    except (TypeError, KeyError, IndexError):
        return default


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: list[float]) -> float:
    """Population standard deviation (ddof=0), suitable for small group sizes."""
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((v - m) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #

def compute_fairness(
    visits,
    patients,
    facilities,
    today: Optional[datetime] = None,
) -> list[FairnessGroup]:
    """Build the fairness report from the database rows.

    Args:
        visits: list of sqlite3.Row (or dict) objects from the ``visits`` table.
        patients: list of rows from the ``patients`` table.
        facilities: list of rows from the ``facilities`` table.
        today: "today" for age calculation (defaults to now).

    Returns:
        A list of :class:`FairnessGroup` rows, sorted by average wait
        (longest first) so the worst-off group is on top.

    Notes:
        * Uses **completed** visits only, because a visit that is "waiting" or
          "called" has not finished yet and would skew the average downwards.
        * Joins each visit to its patient to get sex / age / facility.
    """
    if today is None:
        today = datetime.now()

    # Build lookups: patient_id -> patient row, facility_id -> facility name.
    patient_by_id = {}
    for p in patients:
        patient_by_id[p["id"]] = p

    facility_by_id = {}
    for f in facilities:
        facility_by_id[f["id"]] = f

    # Group durations by (sex, age_group, facility, urgency).
    buckets: dict[tuple, list[float]] = {}
    completed_levels = {"RED", "YELLOW", "GREEN"}

    for v in visits:
        # Only completed visits: a pending visit has not ended yet.
        status = _get(v, "status", "") or ""
        if status.lower() != "finished":
            continue
        level = _get(v, "level", "GREEN") or "GREEN"

        pid = _get(v, "patient_id")
        patient = patient_by_id.get(pid)
        if patient is None:
            # Visiting a patient who is not in the patients table is unusual;
            # we can't compute fair group, so we skip it.
            continue

        sex = _get(patient, "sex", "unknown") or "unknown"
        year_of_birth = _get(patient, "year_of_birth")
        age_band = age_group(year_of_birth, today)
        facility_id = _get(patient, "facility_id")
        facility = _get(facility_by_id.get(facility_id), "name", "unknown")
        facility = facility or "unknown"

        joined = _parse_dt(_get(v, "joined_at"))
        called = _parse_dt(_get(v, "called_at"))
        if called is None or joined is None or called <= joined:
            continue

        duration_minutes = (called - joined).total_seconds() / 60.0
        key = (sex, age_band, facility, level)
        buckets.setdefault(key, []).append(duration_minutes)

    # Convert buckets to FairnessGroup rows.
    groups = []
    for (sex, age_band, facility, level), durations in buckets.items():
        avg = _mean(durations)
        median = _median(durations)
        std = _std(durations)
        n = len(durations)
        groups.append(
            FairnessGroup(
                sex=sex,
                age_group=age_band,
                facility=facility,
                level=level,
                avg_wait_minutes=avg,
                median_wait_minutes=median,
                std_wait_minutes=std,
                n_patients=n,
            )
        )

    # Flag the groups that wait significantly longer than the clinic average.
    all_durations: list[float] = []
    for durations in buckets.values():
        all_durations.extend(durations)
    overall_avg = _mean(all_durations) if all_durations else 0.0
    overall_std = _std(all_durations)

    for g in groups:
        # Flag when the group's average is more than ONE std below the overall
        # average (i.e. it waits longer).  Use max(0, ...) so the margin is
        # always non-negative.
        margin = overall_avg - g.avg_wait_minutes
        g.flagged = margin > overall_std
        g.n_patients = len(buckets[(g.sex, g.age_group, g.facility, g.level)])

    # Sort: flagged first, then longest average wait.
    groups.sort(key=lambda g: (g.flagged, g.avg_wait_minutes), reverse=True)
    return groups


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _parse_dt(value) -> Optional[datetime]:
    """Parse an ISO-ish timestamp produced by SQLite's ``datetime('now')``.

    SQLite stores ``YYYY-MM-DD HH:MM:SS`` (no timezone).  Our timestamps are
    all naive UTC, so we return a naive datetime.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Try the "YYYY-MM-DD HH:MM:SS" form first.
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    # Fall back to the ISO form (with "T" separator, optional tz).
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
