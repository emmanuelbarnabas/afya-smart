"""Scheduling schemas — slots, bookings, queue."""
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field


class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    start_time: time
    end_time: time
    capacity: int
    booked: int
    expected_wait_minutes: int | None = None

    @property
    def is_full(self) -> bool:
        return self.booked >= self.capacity


class BookingCreate(BaseModel):
    patient_id: int
    slot_id: int
    triage_session_id: int | None = None


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    slot_id: int
    status: str
    created_at: datetime


class QueueJoinRequest(BaseModel):
    patient_id: int
    appointment_id: int | None = None
    is_walk_in: bool = False
    is_emergency_bypass: bool = False
    priority: int = 0


class QueueEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    facility_id: int
    patient_id: int
    is_walk_in: bool
    is_emergency_bypass: bool
    priority: int
    status: str
    joined_at: datetime
    called_at: datetime | None = None
    completed_at: datetime | None = None


class CallNextResult(BaseModel):
    entry: QueueEntryOut
    waiting_count: int
