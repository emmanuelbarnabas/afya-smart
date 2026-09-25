"""Tests za forecast service — expected wait na demand profile."""
from datetime import date, datetime, time, timedelta, timezone

from app.models.scheduling import QueueEntry, Slot
from app.services.forecast import expected_wait_minutes, forecast_next_day_profile


def _slot(hour: int, booked: int = 0, capacity: int = 4) -> Slot:
    return Slot(
        facility_id=1,
        date=date.today(),
        start_time=time(hour, 0),
        end_time=time(hour, 30),
        capacity=capacity,
        booked=booked,
    )


def test_morning_peak_has_longest_wait():
    assert expected_wait_minutes(_slot(7)) > expected_wait_minutes(_slot(14))
    assert expected_wait_minutes(_slot(8)) > expected_wait_minutes(_slot(11))


def test_utilization_increases_wait():
    empty = expected_wait_minutes(_slot(10, booked=0))
    full = expected_wait_minutes(_slot(10, booked=4))
    assert full > empty


def test_forecast_profile_default_prior_has_morning_peak():
    """Hakuna history → prior ina peak asubuhi (6–9)."""
    from app.services import forecast as f

    class FakeDB:
        def execute(self, stmt):
            return []

    profile = f.forecast_next_day_profile(FakeDB(), facility_id=1, days=30)
    assert isinstance(profile, dict)
    assert set(profile.keys()) == set(range(24))
    # Peak ya asubuhi iko juu zaidi ya saa za mchana
    assert profile[7] > profile[15]
    assert profile[8] > profile[15]


def test_forecast_profile_with_history(db_session, facility):
    from app.models.scheduling import QueueEntry

    now = datetime.now(timezone.utc)
    for _ in range(10):
        db_session.add(
            QueueEntry(
                facility_id=facility.id,
                patient_id=1,
                joined_at=now - timedelta(days=1),
            )
        )
    db_session.commit()

    profile = forecast_next_day_profile(db_session, facility.id, days=30)
    assert isinstance(profile, dict)
    assert set(profile.keys()) == set(range(24))
