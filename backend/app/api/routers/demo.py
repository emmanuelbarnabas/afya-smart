"""Demo router — ukurasa wa USSD simulator + PWA ya simu (hautumii /api/v1 prefix)."""
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.patient import Patient
from app.models.scheduling import QueueEntry, QueueStatus
from app.services import queue as queue_service

router = APIRouter(tags=["demo"])

_STATIC = Path(__file__).resolve().parents[2] / "static"


@router.get("/ussd-demo", response_class=HTMLResponse, include_in_schema=False)
def ussd_demo():
    """Simulator ya USSD — inaita /api/v1/ussd halisi (works via tunnel pia)."""
    return FileResponse(_STATIC / "ussd-demo.html", media_type="text/html")


@router.get("/ussd-config", include_in_schema=False)
def ussd_config():
    """Service code halisi ya channel (kwa simulator ya demo/dashibodi)."""
    return {"service_code": settings.ussd_service_code}


@router.get("/my-queue", include_in_schema=False)
def my_queue(phone: str = Query(..., min_length=6), db: Session = Depends(get_db)):
    """Nafasi ya mgonjwa kwenye foleni kwa namba ya simu — inatumika na PWA ya simu.

    Inarudisha entry ya WAITING ya hivi karibuni; kama ipo CALLED/IN_CONSULT/DONE
    (ya hivi karibuni) inaonyesha hali yake ili app ionyeshe 'inaitwa' n.k.
    """
    normalized = phone.strip()
    if not normalized.startswith("+"):
        normalized = f"+{normalized}"

    patient = db.scalar(select(Patient).where(Patient.phone_number == normalized))
    if patient is None:
        return {"status": "none", "position": 0, "waiting": 0}

    entry = db.scalar(
        select(QueueEntry)
        .where(QueueEntry.patient_id == patient.id)
        .order_by(QueueEntry.joined_at.desc())
        .limit(1)
    )
    if entry is None:
        return {"status": "none", "position": 0, "waiting": 0}

    waiting = queue_service.waiting_count(db, entry.facility_id)
    if entry.status == QueueStatus.WAITING.value:
        return {
            "status": entry.status,
            "position": queue_service.position_of(db, entry),
            "waiting": waiting,
            "priority": entry.priority,
            "emergency": entry.is_emergency_bypass,
        }

    # CALLED / IN_CONSULT / DONE / LEFT — onyesha hali tu, nafasi haipo tena
    return {
        "status": entry.status,
        "position": 0,
        "waiting": waiting,
        "emergency": entry.is_emergency_bypass,
    }
