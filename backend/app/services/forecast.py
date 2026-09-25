"""Demand forecast service — expected wait per slot kwa kutumia pattern za kihistoria.

Hii ni baseline heuristic (rules-based) inayoweza kubadilishwa na ML model
kutoka ml/ package baadaye. Kazi yake: kusukuma demand kutoka asubuhi (peak
6–9 AM) kwenda nje ya peak kwa kuonyesha expected wait kwa slot.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.scheduling import QueueEntry, QueueStatus, Slot


def _slot_hour(slot: Slot) -> int:
    ref = datetime.combine(date.today(), slot.start_time)
    return ref.hour


def expected_wait_minutes(slot: Slot, base_minutes: int = 15) -> int:
    """Baseline: dakika za kusubiri zinazotabiriwa kwa slot.

    Peak ya asubuhi (6–9) ina wait ndefu; slots za baadaye zina wait fupi —
    hii inawapa watumiaji motisha ya kuchagua off-peak.
    """
    hour = _slot_hour(slot)
    utilization = slot.booked / max(slot.capacity, 1)
    if hour < 9:  # morning peak
        peak_factor = 2.0
    elif hour < 12:
        peak_factor = 1.4
    elif hour < 15:
        peak_factor = 1.0
    else:
        peak_factor = 0.7
    return int(round(base_minutes * peak_factor * (1 + utilization)))


def update_slot_forecasts(db: Session, facility_id: int, day: date) -> list[Slot]:
    """Weka expected_wait_minutes kwenye slots zote za siku hiyo."""
    stmt = select(Slot).where(Slot.facility_id == facility_id, Slot.date == day)
    slots = list(db.scalars(stmt))
    for slot in slots:
        slot.expected_wait_minutes = expected_wait_minutes(slot)
    db.commit()
    return slots


def historical_hourly_demand(db: Session, facility_id: int, days: int = 30) -> dict[int, int]:
    """Jumla ya queue entries kwa kila saa (0–23) kutoka kwenye history."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(QueueEntry.joined_at)
        .where(QueueEntry.facility_id == facility_id, QueueEntry.joined_at >= since)
    )
    counts: dict[int, int] = {h: 0 for h in range(24)}
    for (joined_at,) in db.execute(stmt):
        if joined_at is not None:
            counts[joined_at.hour] += 1
    return counts


def forecast_next_day_profile(db: Session, facility_id: int, days: int = 30) -> dict[int, float]:
    """Profaili ya demand iliyotabiriwa (viwango vya wastani kwa saa).

    Baseline: wastani wa history + smoothing ndogo; ML model inaweza
    kuchukua nafasi yake kwa API ile ile.
    """
    counts = historical_hourly_demand(db, facility_id, days)
    total = sum(counts.values())
    if total == 0:
        # Hakuna history — tumia pattern ya jumla ya facility za umma (peak asubuhi)
        prior = {h: 3.0 if 6 <= h < 9 else 1.0 for h in range(24)}
        return prior
    return {h: counts[h] / days for h in range(24)}


__all__ = [
    "expected_wait_minutes",
    "update_slot_forecasts",
    "historical_hourly_demand",
    "forecast_next_day_profile",
    "QueueStatus",
    "time",
]
