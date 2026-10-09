"""Patient schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone_number: str
    full_name: str | None = None
    preferred_language: str
    is_anonymous: bool = False
    facility_id: int | None = None
    created_at: datetime

    @field_validator("phone_number", mode="before")
    @classmethod
    def _no_sim_is_empty(cls, value):
        """Mgonjwa bila SIM (phone_number NULL) hupata siru tupu — si NULL.

        Ulinganisho: siru tupu == no SIM, huku "+255..." ukiwa ni mgonjwa
        wa kawaida (nambari ya simu halisi).
        """
        return "" if value is None else value


class PatientCreate(BaseModel):
    phone_number: str
    full_name: str | None = None
    preferred_language: str = "sw"
    facility_id: int | None = None
    is_anonymous: bool = False


class IntakeCreate(BaseModel):
    """Register a patient without a phone number (no-SIM patient).

    The patient is created in the DB and (by itself) cannot join the queue
    until given to the intake endpoint: ``POST /api/v1/intake/{patient_id}/queue``.
    """
    full_name: str
    year_of_birth: int | None = None
    is_pregnant: bool = False
    preferred_language: str = "sw"
    facility_id: int | None = None

