"""Queue service — join, call-next, priority and status transitions."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.scheduling import QueueEntry, QueueStatus
from app.models.triage import UrgencyLevel


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
    """Priority ya msingi kutokana na appointment (triage urgency inaweza kuwa juu zaidi)."""
    if appointment_id is None:
        return 0
    from app.models.scheduling import Appointment

    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        return 0
    # Appointment za triage zenye urgency ya juu zina priority bora
    from sqlalchemy import case

    urgency_stmt = select(
        case(
            (QueueEntry.__table__.c.appointment_id.is_(None), 0),
            else_=0,
        )
    )
    # Simple: appointments zilizounganishwa na triage session za emergency zina priority 10
    from app.models.triage import TriageSession

    urgency_row = db.execute(
        select(TriageSession.urgency).where(TriageSession.id == appointment.triage_session_id)
    ).scalar_one_or_none()
    del urgency_stmt  # not needed; kept simple
    return {"emergency": 10, "urgent": 5}.get(urgency_row or "", 0)


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


def urgency_priority(UrgencyLevel_urgency: UrgencyLevel) -> int:
    """Ramani ya urgency → priority ya foleni."""
    return {
        UrgencyLevel.EMERGENCY: 100,
        UrgencyLevel.URGENT: 10,
        UrgencyLevel.ROUTINE: 2,
        UrgencyLevel.SELF_CARE: 0,
    }[UrgencyLevel_urgency]
