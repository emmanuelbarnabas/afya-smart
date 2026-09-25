"""Test fixtures — in-memory SQLite DB + TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
import app.models  # noqa: F401  # (kwanza — ili jina `app` la chini lisifutwe)
from app.main import app


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    TestSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = TestSession()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client(db_engine, db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def facility(db_session):
    from app.models.facility import Facility

    f = Facility(
        name="Test Dispensary",
        code="TST-001",
        level="dispensary",
        region="Dar es Salaam",
        district="Ilala",
    )
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    return f


@pytest.fixture()
def patient(db_session, facility):
    from app.models.patient import Patient

    p = Patient(phone_number="+255700111222", full_name="Test Patient", preferred_language="sw")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    return p


@pytest.fixture()
def slots_today(db_session, facility):
    """Slots za leo: asubuhi (peak) na mchana."""
    from datetime import date, datetime, time, timedelta

    from app.models.scheduling import Slot

    today = date.today()
    slots = []
    t = datetime.combine(today, time(8, 0))
    for start in (time(8, 0), time(8, 30), time(9, 0), time(12, 0), time(14, 0)):
        t = datetime.combine(today, start)
        slots.append(
            Slot(
                facility_id=facility.id,
                date=today,
                start_time=start,
                end_time=(t + timedelta(minutes=30)).time(),
                capacity=2,
                booked=0,
            )
        )
    db_session.add_all(slots)
    db_session.commit()
    return slots
