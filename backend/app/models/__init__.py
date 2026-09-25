"""All ORM models — imported so Alembic autogenerate / create_all see full metadata."""
from app.models.facility import Facility
from app.models.patient import Patient
from app.models.scheduling import (
    Appointment,
    AppointmentStatus,
    QueueEntry,
    QueueStatus,
    Slot,
)
from app.models.triage import TriageSession, UrgencyLevel

__all__ = [
    "Facility",
    "Patient",
    "TriageSession",
    "UrgencyLevel",
    "Slot",
    "Appointment",
    "AppointmentStatus",
    "QueueEntry",
    "QueueStatus",
]
