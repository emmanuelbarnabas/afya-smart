"""Facility model — dispensary / health centre / hospital."""
from datetime import datetime, time

from sqlalchemy import DateTime, Integer, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    level: Mapped[str] = mapped_column(String(50), default="dispensary")  # dispensary|health_centre|hospital
    region: Mapped[str] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    opens_at: Mapped[time] = mapped_column(Time, default=time(8, 0))
    closes_at: Mapped[time] = mapped_column(Time, default=time(17, 0))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
