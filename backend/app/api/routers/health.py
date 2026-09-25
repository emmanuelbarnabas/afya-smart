"""Health check endpoints."""
from fastapi import APIRouter

from app.services.ml_triage import get_model_info

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "afya-smart-api",
        "version": "0.1.0",
        "triage_model": get_model_info(),
    }
