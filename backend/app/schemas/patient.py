"""Patient schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone_number: str
    full_name: str | None = None
    preferred_language: str
    facility_id: int | None = None
    created_at: datetime


class PatientCreate(BaseModel):
    phone_number: str
    full_name: str | None = None
    preferred_language: str = "sw"
    facility_id: int | None = None
