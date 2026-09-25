"""API routers."""
from app.api.routers import analytics, health, queue, slots, ussd

__all__ = ["health", "ussd", "slots", "queue", "analytics"]
