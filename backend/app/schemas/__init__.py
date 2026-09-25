"""Pydantic schemas — API request/response models."""
from app.schemas.analytics import DemandPoint, QueueSummary, TriageOutcomes
from app.schemas.patient import PatientOut
from app.schemas.scheduling import (
    BookingCreate,
    BookingOut,
    CallNextResult,
    QueueEntryOut,
    QueueJoinRequest,
    SlotOut,
)

__all__ = [
    "PatientOut",
    "SlotOut",
    "BookingCreate",
    "BookingOut",
    "QueueEntryOut",
    "QueueJoinRequest",
    "CallNextResult",
    "DemandPoint",
    "QueueSummary",
    "TriageOutcomes",
]
