"""Slot, Appointment and QueueEntry models — smart queue & slot booking."""
import enum
from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AppointmentStatus(str, enum.Enum):
    BOOKED = "booked"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class QueueStatus(str, enum.Enum):
    WAITING = "waiting"
    CALLED = "called"
    IN_CONSULT = "in_consult"
    DONE = "done"
    LEFT = "left"


class Slot(Base):
    __tablename__ = "slots"
    __table_args__ = (
        UniqueConstraint("facility_id", "date", "start_time", name="uq_slot_facility_date_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    capacity: Mapped[int] = mapped_column(Integer, default=4)
    booked: Mapped[int] = mapped_column(Integer, default=0)
    expected_wait_minutes: Mapped[int | None] = mapped_column(Integer)  # from demand forecast model

    appointments = relationship("Appointment", back_populates="slot")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), index=True)
    triage_session_id: Mapped[int | None] = mapped_column(ForeignKey("triage_sessions.id"))
    status: Mapped[str] = mapped_column(String(20), default=AppointmentStatus.BOOKED.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    patient = relationship("Patient")
    slot = relationship("Slot", back_populates="appointments")


class QueueEntry(Base):
    __tablename__ = "queue_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("facilities.id"), index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"))
    is_walk_in: Mapped[bool] = mapped_column(Boolean, default=False)
    is_emergency_bypass: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)  # higher = served earlier
    status: Mapped[str] = mapped_column(String(20), default=QueueStatus.WAITING.value)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    called_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    patient = relationship("Patient")
