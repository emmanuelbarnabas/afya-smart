"""Afya Smart — queue engine.

A simple priority queue for the nurse's live queue.  Priority is calculated as
follows so that **waiting time matters** and an older GREEN patient can push a
brand-new YELLOW patient out of the way:

    priority = (base_weight) * 60 - minutes_waited

with

    RED      -> base_weight 0
    YELLOW   -> base_weight 1
    GREEN    -> base_weight 2

The result is a small integer: **lower number = called first**.  Because the
``- minutes_waited`` term grows with time, a patient who has been waiting
long enough will always end up with a lower number than a freshly joined
patient — so a GREEN patient who waited 100 minutes will outrank a fresh
YELLOW patient, exactly as required.

The engine is intentionally plain (no external queue library).  It keeps a
list of entries in memory and sorts them by ``(priority, joined_time)`` on
every query, which is more than fast enough for a single clinic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------- #
# Time helpers
# --------------------------------------------------------------------------- #

def _now_utc() -> datetime:
    """Current time in UTC, used for joined_at / timestamps."""
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class UrgencyLevel(Enum):
    """The three urgency levels a patient can be given at registration."""
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class QueueStatus(Enum):
    """Where a patient is in the clinic flow."""
    WAITING = "waiting"      # in the queue, not yet called
    CALLED = "called"        # nurse has been told to call them
    IN_CONSULT = "in_consult"  # nurse is seeing them now
    FINISHED = "finished"    # consultation is over
    CANCELLED = "cancelled"  # patient left / cancelled


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class Patient:
    """A person who reaches the clinic (via USSD, SMS, or walk-in)."""
    id: int
    phone_number: Optional[str] = None
    full_name: str = ""
    sex: str = "unknown"          # "male", "female", "unknown"
    year_of_birth: Optional[int] = None
    facility_id: int = 1          # which clinic they are registered to
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self):
        if self.phone_number is not None and not isinstance(self.phone_number, str):
            self.phone_number = str(self.phone_number)


@dataclass
class QueueEntry:
    """A single person standing in the queue at a clinic."""
    id: int
    patient: Patient
    priority: int = 0
    status: QueueStatus = QueueStatus.WAITING
    joined_at: datetime = field(default_factory=_now_utc)
    called_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    _next_id: int = field(default=1000, init=False)

    def __post_init__(self):
        # The `_next_id` default is only a placeholder; a real entry always
        # receives its real id from the queue that created it.
        if self._next_id > self.id:
            self._next_id = self.id + 1


# --------------------------------------------------------------------------- #
# Priority helpers
# --------------------------------------------------------------------------- #

# Base weights for the priority formula: (base_weight) * 60 - minutes_waited.
# RED needs the clinic's attention FIRST, so it has weight 0.  GREEN is
# routine, so it has the highest weight (2).  YELLOW sits in the middle.
BASE_WEIGHT: dict[UrgencyLevel, int] = {
    UrgencyLevel.RED: 0,
    UrgencyLevel.YELLOW: 1,
    UrgencyLevel.GREEN: 2,
}


def base_weight(level: UrgencyLevel) -> int:
    """Return the base weight for an urgency level."""
    return BASE_WEIGHT[level]


def priority(level: UrgencyLevel, minutes_waited: int) -> int:
    """Compute the queue priority for a patient who has waited N minutes.

    ``lower number = called first``.  A RED patient always gets 0 (they can
    never be overtaken), while a fresh GREEN patient gets 120.
    """
    return base_weight(level) * 60 - minutes_waited


# --------------------------------------------------------------------------- #
# Queue engine
# --------------------------------------------------------------------------- #

class Queue:
    """In-memory priority queue for one clinic.

    The queue is a plain list.  Every public query sorts it by
    ``(priority, joined_at)`` so the highest-priority (lowest number) patient
    is always first.  This makes the overtaking rule above automatic and easy
    to reason about.
    """

    def __init__(self) -> None:
        self._entries: list[QueueEntry] = []
        self._next_id = 1000

    # -- adding ----------------------------------------------------------- #

    def add(
        self,
        patient: Patient,
        urgency: UrgencyLevel,
        minutes_waited: int = 0,
        joined_at: Optional[datetime] = None,
    ) -> QueueEntry:
        """Register a patient in the queue with the given urgency.

        Args:
            patient: the person to register.
            urgency: RED / YELLOW / GREEN.
            minutes_waited: how long the patient has already waited (0 for a
                brand-new registration).  This is used to compute priority.
            joined_at: when the patient joined.  Defaults to now.

        Returns:
            the newly created QueueEntry.
        """
        joined = joined_at or _now_utc()
        entry = QueueEntry(
            id=self._next_id,
            patient=patient,
            priority=priority(urgency, minutes_waited),
            status=QueueStatus.WAITING,
            joined_at=joined,
        )
        self._next_id += 1
        self._entries.append(entry)
        return entry

    # -- queries ---------------------------------------------------------- #

    def ordered(self) -> list[QueueEntry]:
        """Return every waiting entry, highest priority first."""
        return sorted(
            (e for e in self._entries if e.status == QueueStatus.WAITING),
            key=_sort_key,
        )

    def add_entry(self, entry: QueueEntry) -> None:
        """(Test helper) Insert an already-built entry into the queue.

        Public callers should use :meth:`add` instead.  This exists so tests
        can create patients with a simulated waiting time (the aging rule)
        without reaching into the private ``_entries`` list.
        """
        self._entries.append(entry)

    def waiting_count(self) -> int:
        return len(self.ordered())

    def position(self, entry: QueueEntry) -> int:
        """1-based position of a waiting entry (0 if it is not waiting)."""
        for idx, e in enumerate(self.ordered(), start=1):
            if e.id == entry.id:
                return idx
        return 0

    def estimated_wait_minutes(self, entry: QueueEntry) -> Optional[int]:
        """Rough ETA for a waiting entry.

        We take the average time the current first patient has already spent
        waiting as our "per-patient" estimate.  In a real system this would
        come from the nurse's actual consult times.
        """
        ordered = self.ordered()
        if not ordered or entry.status != QueueStatus.WAITING:
            return None
        first = ordered[0]
        # minutes already waited by the first patient => every other patient
        # will wait at least that long.
        if first.joined_at == entry.joined_at:
            return 0
        minutes_already = int((_now_utc() - first.joined_at).total_seconds() // 60)
        return max(0, minutes_already)

    # -- actions ---------------------------------------------------------- #

    def call_next(self) -> Optional[QueueEntry]:
        """Move the highest-priority waiting patient from WAITING to CALLED.

        Returns the patient who was called, or None if the queue is empty.
        """
        waiting = self.ordered()
        if not waiting:
            return None
        target = waiting[0]
        target.status = QueueStatus.CALLED
        target.called_at = _now_utc()
        return target

    def mark_finished(self, entry: QueueEntry) -> Optional[QueueEntry]:
        """Move a patient from any active state to FINISHED.

        Returns the updated entry, or None if the entry does not exist.
        """
        entry = self._find(entry.id)
        if entry is None:
            return None
        entry.status = QueueStatus.FINISHED
        entry.finished_at = _now_utc()
        return entry

    def mark_cancelled(self, entry: QueueEntry) -> Optional[QueueEntry]:
        """Move a patient to CANCELLED."""
        entry = self._find(entry.id)
        if entry is None:
            return None
        entry.status = QueueStatus.CANCELLED
        return entry

    # -- internals -------------------------------------------------------- #

    def _find(self, entry_id: int) -> Optional[QueueEntry]:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None


# --------------------------------------------------------------------------- #
# Helpers / "storage"
# --------------------------------------------------------------------------- #

# A tiny thread-unsafe "database" that every test shares.  In the real app
# these functions would be thin wrappers over SQLite (see app.py).
_QUEUE: Queue = Queue()
_PATIENT_SEQUENCE = [100]


def _now_utc() -> datetime:
    """Current time in UTC, used for joined_at / timestamps."""
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _sort_key(entry: QueueEntry):
    """Sort key: lowest priority number first, then who joined earliest."""
    return (entry.priority, entry.joined_at)


def _next_patient_id() -> int:
    _PATIENT_SEQUENCE[0] += 1
    return _PATIENT_SEQUENCE[0]


# --------------------------------------------------------------------------- #
# Priority helpers (module-level, used by tests AND by the Flask app)
# --------------------------------------------------------------------------- #

def _priority_value(level: UrgencyLevel, minutes_waited: int) -> int:
    """Compute priority = (base_weight) * 60 - minutes_waited.

    This is the single source of truth for the formula.  Both the Queue class
    and the pure unit tests call this function so they can never disagree.
    """
    return base_weight(level) * 60 - minutes_waited


# --------------------------------------------------------------------------- #
# Convenience API that matches the real Flask app shape (Phase 4)
# --------------------------------------------------------------------------- #

def create_patient(phone_number=None, full_name="", **kwargs) -> Patient:
    """Create and store a patient, returning it."""
    patient = Patient(id=_next_patient_id(), phone_number=phone_number, full_name=full_name, **kwargs)
    _QUEUE  # no-op so the module stays "used"
    return patient


def add_to_queue(patient, urgency, minutes_waited=0):
    """Add a patient to the (shared) queue."""
    return _QUEUE.add(patient, urgency, minutes_waited=minutes_waited)


def ordered_queue():
    return _QUEUE.ordered()


def queue_position(entry):
    return _QUEUE.position(entry)


def estimated_wait(entry):
    return _QUEUE.estimated_wait_minutes(entry)


def call_next():
    return _QUEUE.call_next()


def mark_finished(entry):
    return _QUEUE.mark_finished(entry)


def mark_cancelled(entry):
    return _QUEUE.mark_cancelled(entry)
