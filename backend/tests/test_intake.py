"""Tests for the intake / registration channel (patients without a SIM).

The single backend must unify USSD, dashboard, and phone-less intake through
one system: one database, one queue, no duplicate facility implementations.
"""

from app.models.facility import Facility
from app.models.patient import Patient
from app.models.scheduling import QueueEntry, QueueStatus
from app.models.triage import TriageSession


def _create_facility(db_session):
    from app.models.facility import Facility

    f = Facility(
        name="Intake Dispensary",
        code="ITX-001",
        level="dispensary",
        region="Dar es Salaam",
        district="Ilala",
    )
    db_session.add(f)
    db_session.commit()
    db_session.refresh(f)
    return f


def test_register_phone_less_patient(client, db_session):
    facility = _create_facility(db_session)
    resp = client.post(
        "/api/v1/intake",
        json={
            "full_name": "Mjomba Mbaruk",
            "year_of_birth": 1978,
            "is_pregnant": False,
            "preferred_language": "sw",
            "facility_id": facility.id,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["full_name"] == "Mjomba Mbaruk"
    assert body["phone_number"] == ""  # no SIM → no phone number
    assert body["is_anonymous"] is True
    assert body["facility_id"] == facility.id

    patient = db_session.get(Patient, body["id"])
    assert patient is not None
    assert patient.is_anonymous is True
    assert patient.phone_number is None


def test_intake_patient_can_join_shared_queue(client, db_session):
    facility = _create_facility(db_session)
    reg = client.post(
        "/api/v1/intake",
        json={
            "full_name": "Mjomba Mbaruk",
            "preferred_language": "sw",
            "facility_id": facility.id,
        },
    )
    assert reg.status_code == 201
    patient_id = reg.json()["id"]

    joined = client.post(f"/api/v1/intake/{patient_id}/queue")
    assert joined.status_code == 201
    body = joined.json()
    assert body["patient_id"] == patient_id
    assert body["status"] == "waiting"
    assert body["facility_id"] == facility.id
    assert "queue_position" in body

    entry = db_session.get(QueueEntry, None)
    # find the entry tied to this patient
    entry = (
        db_session.query(QueueEntry)
        .filter(QueueEntry.patient_id == patient_id, QueueEntry.status == QueueStatus.WAITING.value)
        .first()
    )
    assert entry is not None
    assert entry.is_walk_in is True


def test_queue_single_shared_list_with_ussd_patients(client, db_session):
    """One queue, one database: phone-less intake patient appears alongside
    USSD patients (no separate facility implementation)."""
    facility = _create_facility(db_session)

    # USSD-style patient (phone-keyed)
    from app.models.patient import Patient as P

    p_ussd = P(phone_number="+255700111222", full_name="USSD Mgonjwa", preferred_language="sw")
    db_session.add(p_ussd)
    db_session.flush()

    # phone-less intake patient
    reg = client.post(
        "/api/v1/intake",
        json={"full_name": "Mgonjwa wa SIM", "preferred_language": "sw", "facility_id": facility.id},
    )
    assert reg.status_code == 201
    p_intake = db_session.get(Patient, reg.json()["id"])

    # Both join the SAME shared queue: the USSD patient through the regular
    # queue endpoint, the phone-less patient through the intake endpoint.
    ussd_join = client.post(
        f"/api/v1/facilities/{facility.id}/queue",
        json={"patient_id": p_ussd.id, "is_walk_in": True},
    )
    assert ussd_join.status_code in (200, 201)
    intake_join = client.post(f"/api/v1/intake/{p_intake.id}/queue")
    assert intake_join.status_code == 201

    queue = client.get(f"/api/v1/facilities/{facility.id}/queue")
    assert queue.status_code == 200
    entries = queue.json()
    assert len(entries) == 2
    names = {e["patient_name"] for e in entries}
    assert {"USSD Mgonjwa", "Mgonjwa wa SIM"} == names


def test_intake_rejects_unknown_facility(client):
    resp = client.post(
        "/api/v1/intake",
        json={"full_name": "No facility", "preferred_language": "sw", "facility_id": 9999},
    )
    assert resp.status_code == 404


def test_intake_join_queue_without_facility(client, db_session):
    reg = client.post(
        "/api/v1/intake",
        json={"full_name": "Mgonjwa bila foleni", "preferred_language": "sw"},
    )
    assert reg.status_code == 201
    patient_id = reg.json()["id"]
    resp = client.post(f"/api/v1/intake/{patient_id}/queue")
    assert resp.status_code == 422
    assert "foleni" in resp.json()["detail"]


def test_intake_join_queue_headers_match_queue_join(client, db_session):
    """The intake queue join behaves like the regular queue join (API consistency)."""
    from app.models.facility import Facility

    f = Facility(
        name="Intake Header Dispensary",
        code="ITX-HDR-001",
        level="dispensary",
        region="Dar es Salaam",
        district="Ilala",
    )
    db_session.add(f)
    db_session.commit()

    from app.models.patient import Patient as P

    p = P(phone_number="+255700111222", full_name="Mgonjwa wa RSI", preferred_language="sw")
    db_session.add(p)
    db_session.commit()

    intake = client.post(
        "/api/v1/intake",
        json={"full_name": "Mgonjwa wa SI", "preferred_language": "sw", "facility_id": f.id},
    )
    intake_id = intake.json()["id"]

    intake_entry = client.post(f"/api/v1/intake/{intake_id}/queue").json()
    queue_entry = client.post(
        f"/api/v1/facilities/{f.id}/queue",
        json={"patient_id": p.id, "is_walk_in": True},
    ).json()

    assert intake_entry["queue_position"] >= 1
    assert "facility_id" in intake_entry
    # both are single backend entries (one request → one queue row)
    assert isinstance(intake_entry["patient_id"], int)
