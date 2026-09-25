"""Triage session model — one USSD triage interaction (4–6 questions → urgency)."""
import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UrgencyLevel(str, enum.Enum):
    EMERGENCY = "emergency"  # "go now" — refer immediately
    URGENT = "urgent"        # same-day in-person visit
    ROUTINE = "routine"      # book a scheduled slot
    SELF_CARE = "self_care"  # guidance only, no visit needed


class TriageSession(Base):
    __tablename__ = "triage_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))
    at_session_id: Mapped[str | None] = mapped_column(String(100), index=True)  # Africa's Talking sessionId
    answers: Mapped[dict] = mapped_column(JSON, default=dict)
    urgency: Mapped[str] = mapped_column(String(20))  # UrgencyLevel.value
    confidence: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str | None] = mapped_column(String(50), default="rules-v1")
    outcome: Mapped[str | None] = mapped_column(String(50))  # emergency_directed|slot_booked|self_care_given|abandoned
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    patient = relationship("Patient", back_populates="triage_sessions")
