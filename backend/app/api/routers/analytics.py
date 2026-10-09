"""Analytics endpoints — demand patterns, queue stats, triage outcomes."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.scheduling import Appointment, QueueEntry, QueueStatus, Slot
from app.models.triage import TriageSession, UrgencyLevel
from app.schemas.analytics import (
    DemandPoint,
    QueueSummary,
    TriageAccuracy,
    TriageOutcomes,
    WaitTimes,
)
from app.services import forecast, queue as queue_service

router = APIRouter(prefix="/facilities/{facility_id}/analytics", tags=["analytics"])

# Safety alert: under-triage ya juu ya hii % inaonyesha onyo kwenye dashboard.
# Lengo la Afya Smart ni zero missed emergencies — kipimo hiki ndiyo mlinzi.
UNDERTRIAGE_ALERT_THRESHOLD = 0.15


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


@router.get("/demand", response_model=list[DemandPoint])
def demand(
    facility_id: int,
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Mfumo wa mahitaji: idadi ya wagonjwa kwa saa (walk-ins + appointments).

    Inasaidia kuona peak ya asubuhi (6–9 AM) na kupanga staff.
    """
    today = date.today()
    since = datetime.combine(today - timedelta(days=days - 1), time.min, tzinfo=timezone.utc)

    # Walk-ins / check-ins kutoka queue_entries
    queue_rows = db.execute(
        select(QueueEntry.joined_at).where(
            QueueEntry.facility_id == facility_id, QueueEntry.joined_at >= since
        )
    ).scalars().all()

    # Bookings kutoka appointments via slot date+start_time
    booking_rows = db.execute(
        select(Slot.date, Slot.start_time)
        .join(Appointment, Appointment.slot_id == Slot.id)
        .where(Slot.facility_id == facility_id, Slot.date >= today - timedelta(days=days - 1))
    ).all()

    counts: dict[tuple[date, int], int] = {}
    for joined_at in queue_rows:
        if joined_at is None:
            continue
        aware = joined_at if joined_at.tzinfo else joined_at.replace(tzinfo=timezone.utc)
        key = (aware.date(), aware.hour)
        counts[key] = counts.get(key, 0) + 1
    for slot_date, start_time in booking_rows:
        key = (slot_date, start_time.hour)
        counts[key] = counts.get(key, 0) + 1

    points = [
        DemandPoint(date=d, hour=h, visits=v) for (d, h), v in sorted(counts.items())
    ]
    return points


@router.get("/demand-forecast")
def demand_forecast(
    facility_id: int,
    days_history: int = Query(default=30, ge=7, le=180),
    db: Session = Depends(get_db),
):
    """Profaili ya demand iliyotabiriwa kwa saa — baseline heuristic (ML ijae baadaye)."""
    profile = forecast.forecast_next_day_profile(db, facility_id, days_history)
    return [
        {"hour": hour, "expected_visits": round(rate, 2)}
        for hour, rate in sorted(profile.items())
    ]


@router.get("/queue-summary", response_model=QueueSummary)
def queue_summary(facility_id: int, db: Session = Depends(get_db)):
    day_start, day_end = _day_bounds(date.today())

    def count(status: QueueStatus) -> int:
        return db.scalar(
            select(func.count())
            .select_from(QueueEntry)
            .where(
                QueueEntry.facility_id == facility_id,
                QueueEntry.status == status.value,
                # Bypass za dharura zinahesabiwa kando — zina stream yake
                QueueEntry.is_emergency_bypass.is_(False),
            )
        ) or 0

    done_today = db.scalar(
        select(func.count())
        .select_from(QueueEntry)
        .where(
            QueueEntry.facility_id == facility_id,
            QueueEntry.status == QueueStatus.DONE.value,
            QueueEntry.completed_at >= day_start,
            QueueEntry.completed_at < day_end,
        )
    ) or 0
    bypasses = db.scalar(
        select(func.count())
        .select_from(QueueEntry)
        .where(
            QueueEntry.facility_id == facility_id,
            QueueEntry.is_emergency_bypass.is_(True),
            QueueEntry.joined_at >= day_start,
            QueueEntry.joined_at < day_end,
        )
    ) or 0

    return QueueSummary(
        waiting=count(QueueStatus.WAITING),
        called=count(QueueStatus.CALLED),
        in_consult=count(QueueStatus.IN_CONSULT),
        done_today=done_today,
        emergency_bypasses_today=bypasses,
    )


@router.get("/triage-outcomes", response_model=TriageOutcomes)
def triage_outcomes(
    facility_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Matokeo ya triage — inapima % ya non-urgent zilizopewa self-care/miadi."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(TriageSession.outcome, func.count())
        .where(TriageSession.facility_id == facility_id, TriageSession.created_at >= since)
        .group_by(TriageSession.outcome)
    ).all()
    by_outcome = {outcome or "abandoned": n for outcome, n in rows}
    total = sum(by_outcome.values())
    return TriageOutcomes(
        emergency_directed=by_outcome.get("emergency_directed", 0),
        walk_in_directed=by_outcome.get("walk_in_directed", 0),
        slot_booked=by_outcome.get("slot_booked", 0),
        self_care_given=by_outcome.get("self_care_given", 0),
        abandoned=by_outcome.get("abandoned", 0),
        total=total,
    )


@router.get("/wait-times", response_model=WaitTimes)
def wait_times(
    facility_id: int,
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Muda wa kusubiri (joined_at → called_at) — metric ya #1 ya mafanikio.

    Pamoja na muda wa huduma (called_at → completed_at) unaotumika na ETA.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(QueueEntry.joined_at, QueueEntry.called_at, QueueEntry.completed_at).where(
            QueueEntry.facility_id == facility_id,
            QueueEntry.called_at.is_not(None),
            QueueEntry.called_at >= since,
        )
    ).all()
    waits = sorted(
        (called - joined).total_seconds() / 60.0
        for joined, called, _completed in rows
        if joined is not None and called > joined
    )
    services = sorted(
        (completed - called).total_seconds() / 60.0
        for _joined, called, completed in rows
        if completed is not None and completed > called
    )

    def _avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 1) if values else 0.0

    def _percentile(sorted_vals: list[float], pct: float) -> float:
        if not sorted_vals:
            return 0.0
        idx = min(len(sorted_vals) - 1, int(round(pct / 100 * (len(sorted_vals) - 1))))
        return round(sorted_vals[idx], 1)

    return WaitTimes(
        avg_wait_minutes=_avg(waits),
        median_wait_minutes=_percentile(waits, 50),
        p90_wait_minutes=_percentile(waits, 90),
        avg_service_minutes=_avg(services),
        n_completed=len(waits),
        period_days=days,
    )


@router.get("/triage-accuracy", response_model=TriageAccuracy)
def triage_accuracy(
    facility_id: int,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Usahihi wa triage dhidi ya uamuzi wa clinician (feedback loop).

    undertriage (mfumo ulisema pungufu) ndiyo kipimo muhimu zaidi — kinapaswa
    kuwa karibu na sifuri (zero missed emergencies).
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(TriageSession.urgency, TriageSession.clinician_urgency).where(
            TriageSession.facility_id == facility_id,
            TriageSession.clinician_urgency.is_not(None),
            TriageSession.created_at >= since,
        )
    ).all()

    order = {u.value: i for i, u in enumerate(UrgencyLevel)}
    agrees = over = under = 0
    for system_urgency, clinician_urgency in rows:
        s = order.get(system_urgency or "", None)
        c = order.get(clinician_urgency or "", None)
        if s is None or c is None:
            continue
        if s == c:
            agrees += 1
        elif s < c:  # mfumo uliweka juu zaidi (mf. emergency vs routine)
            over += 1
        else:
            under += 1

    total = agrees + over + under
    rate = round(under / total, 3) if total else 0.0
    return TriageAccuracy(
        total_reviewed=total,
        agrees=agrees,
        overtriaged=over,
        undertriaged=under,
        agreement_rate=round(agrees / total, 3) if total else 0.0,
        undertriage_rate=rate,
        # Safety alert: kipimo cha zero-missed-emergencies. Sehemu ndogo ya
        # under-triage ni ya kawaida (magonjwa yanaweza kubadilika), lakini
        # ikizidi 15% ni onyo la kweli kwa kituo.
        alert=rate >= UNDERTRIAGE_ALERT_THRESHOLD,
        threshold=UNDERTRIAGE_ALERT_THRESHOLD,
    )
