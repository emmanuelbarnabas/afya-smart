"""Queue service — join, call-next, priority, status transitions na ETA.

ETA ya mgonjwa inatokana na *service time halisi* ya kituo (muda kati ya
called_at → completed_at ya entries zilizopita) — si makadirio ya kimataifa.
Ikiwa hakuna data ya kutosha, tunarudi kwenye default (15 dakika).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.scheduling import QueueEntry, QueueStatus
from app.models.triage import UrgencyLevel

# Priority ramani ya urgency → nafasi kwenye foleni (juu = huduma kwanza).
URGENCY_PRIORITY: dict[UrgencyLevel, int] = {
    UrgencyLevel.EMERGENCY: 100,
    UrgencyLevel.URGENT: 10,
    UrgencyLevel.ROUTINE: 2,
    UrgencyLevel.SELF_CARE: 0,
}


def urgency_priority(urgency: UrgencyLevel) -> int:
    """Ramani ya urgency → priority ya foleni (compat wrapper)."""
    return URGENCY_PRIORITY[urgency]

# Chini ya entries 3 za kihistoria, makadirio hayana msingi — tumia default.
MIN_SAMPLES_FOR_ETA = 3
DEFAULT_SERVICE_MINUTES = 15.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def join_queue(
    db: Session,
    facility_id: int,
    patient_id: int,
    appointment_id: int | None = None,
    is_walk_in: bool = False,
    is_emergency_bypass: bool = False,
    priority: int = 0,
) -> QueueEntry:
    """Ongeza mgonjwa kwenye foleni; emergency bypass inapewa priority ya juu."""
    if is_emergency_bypass:
        priority = max(priority, 100)
    elif priority == 0:
        priority = _default_priority_from_context(db, appointment_id)

    entry = QueueEntry(
        facility_id=facility_id,
        patient_id=patient_id,
        appointment_id=appointment_id,
        is_walk_in=is_walk_in,
        is_emergency_bypass=is_emergency_bypass,
        priority=priority,
        status=QueueStatus.WAITING.value,
        joined_at=_now(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _default_priority_from_context(db: Session, appointment_id: int | None) -> int:
    """Priority ya msingi kutokana na triage urgency ya appointment (kama ipo)."""
    if appointment_id is None:
        return 0
    from app.models.scheduling import Appointment
    from app.models.triage import TriageSession

    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        return 0
    urgency_row = db.execute(
        select(TriageSession.urgency).where(TriageSession.id == appointment.triage_session_id)
    ).scalar_one_or_none()
    return URGENCY_PRIORITY.get(
        UrgencyLevel(urgency_row) if urgency_row else None, 0
    )


def waiting_entries(db: Session, facility_id: int) -> list[QueueEntry]:
    """Foleni inayo-subiri, imepangwa: priority (desc), kisha joined_at (asc)."""
    stmt = (
        select(QueueEntry)
        .where(QueueEntry.facility_id == facility_id, QueueEntry.status == QueueStatus.WAITING.value)
        .order_by(QueueEntry.priority.desc(), QueueEntry.joined_at.asc())
    )
    return list(db.scalars(stmt))


def call_next(db: Session, facility_id: int) -> QueueEntry | None:
    """Piga simu / ita mgonjwa anayefuata kwenye foleni."""
    entry = waiting_entries(db, facility_id)
    if not entry:
        return None
    target = entry[0]
    target.status = QueueStatus.CALLED.value
    target.called_at = _now()
    db.commit()
    db.refresh(target)
    return target


def mark_status(db: Session, entry_id: int, status: QueueStatus) -> QueueEntry | None:
    """Badilisha hali ya queue entry (in_consult, done, left)."""
    entry = db.get(QueueEntry, entry_id)
    if entry is None:
        return None
    entry.status = status.value
    if status == QueueStatus.DONE:
        entry.completed_at = _now()
    db.commit()
    db.refresh(entry)
    return entry


def waiting_count(db: Session, facility_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(QueueEntry)
        .where(QueueEntry.facility_id == facility_id, QueueEntry.status == QueueStatus.WAITING.value)
    ) or 0


def position_of(db: Session, entry: QueueEntry) -> int:
    """Nafasi ya mgonjwa kwenye foleni (1-based)."""
    for idx, candidate in enumerate(waiting_entries(db, entry.facility_id), start=1):
        if candidate.id == entry.id:
            return idx
    return 0


def mean_service_minutes(db: Session, facility_id: int, limit: int = 50) -> float:
    """Wastani wa muda wa huduma (called_at → completed_at) kutoka history.

    Inatumika na ETA; hakuna data ya kutosha → DEFAULT_SERVICE_MINUTES.
    """
    stmt = (
        select(QueueEntry.called_at, QueueEntry.completed_at)
        .where(
            QueueEntry.facility_id == facility_id,
            QueueEntry.called_at.is_not(None),
            QueueEntry.completed_at.is_not(None),
            QueueEntry.completed_at > QueueEntry.called_at,
        )
        .order_by(QueueEntry.completed_at.desc())
        .limit(limit)
    )
    durations = [
        (completed - called).total_seconds() / 60.0
        for called, completed in db.execute(stmt)
        if completed > called
    ]
    if len(durations) < MIN_SAMPLES_FOR_ETA:
        return DEFAULT_SERVICE_MINUTES
    # Punguza athari ya outliers (mgonjwa aliyekuwa anapumzika deskini n.k.)
    durations.sort()
    trimmed = durations[: max(1, int(len(durations) * 0.9))]
    return sum(trimmed) / len(trimmed)


def estimated_wait_minutes(db: Session, entry: QueueEntry) -> int | None:
    """ETA ya mgonjwa: (nafasi yake) × (wastani wa muda wa huduma).

    Return None kama si WAITING (hana nafasi kwenye foleni tena).
    """
    if entry.status != QueueStatus.WAITING.value:
        return None
    pos = position_of(db, entry)
    if pos <= 0:
        return None
    per_patient = mean_service_minutes(db, entry.facility_id)
    # Aliyeko #1 anasubiri dakika chache tu (huduma inayoendelea), wengine zaidi
    return max(0, int(round((pos - 1) * per_patient + min(5.0, per_patient * 0.3))))
