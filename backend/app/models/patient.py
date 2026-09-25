"""Patient model — identified by phone number (USSD/SMS primary key in the field)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # normalized e.g. +2557...
    full_name: Mapped[str | None] = mapped_column(String(200))
    year_of_birth: Mapped[int | None] = mapped_column(Integer)
    is_pregnant: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_language: Mapped[str] = mapped_column(String(2), default="sw")
    facility_id: Mapped[int | None] = mapped_column(ForeignKey("facilities.id"))  # home facility
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    triage_sessions = relationship("TriageSession", back_populates="patient")
