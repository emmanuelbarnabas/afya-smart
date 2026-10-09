"""Analytics schemas — demand, queue, wait times, triage outcomes/accuracy."""
from datetime import date, datetime

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
    walk_in_directed: int
    slot_booked: int
    self_care_given: int
    abandoned: int
    total: int


class WaitTimes(BaseModel):
    """Muda wa kusubiri — metric ya #1 ya mafanikio ya Afya Smart."""

    avg_wait_minutes: float
    median_wait_minutes: float
    p90_wait_minutes: float
    avg_service_minutes: float
    n_completed: int
    period_days: int


class TriageAccuracy(BaseModel):
    """Usahihi wa triage dhidi ya uamuzi wa clinician (feedback loop)."""

    total_reviewed: int
    agrees: int
    overtriaged: int  # mfumo ulisema dharura zaidi kuliko clinician
    undertriaged: int  # mfumo ulisema pungufu — HATARI, lazima iwe ndogo
    agreement_rate: float
    undertriage_rate: float
    alert: bool = False  # True = under-triage imezidi kikomo (safety alert)
    threshold: float = 0.15
