"""Analytics schemas."""
from datetime import date

from pydantic import BaseModel


class DemandPoint(BaseModel):
    date: date
    hour: int
    visits: int


class QueueSummary(BaseModel):
    waiting: int
    called: int
    in_consult: int
    done_today: int
    emergency_bypasses_today: int


class TriageOutcomes(BaseModel):
    emergency_directed: int
    slot_booked: int
    self_care_given: int
    abandoned: int
    total: int
