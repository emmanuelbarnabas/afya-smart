"""
AFYA SMART — AI Powered Triage & Queue Management
FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import analytics, dashboard, demo, health, queue, slots, ussd
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience: create tables from ORM metadata on startup.
    # Production should use Alembic migrations instead.
    if settings.environment == "development":
        try:
            from app.core.database import Base, engine
            import app.models  # noqa: F401 — register models on Base.metadata

            Base.metadata.create_all(bind=engine)

            # Dev convenience: hakikisha slots za LEO zinaexist (seed inarun mara moja
            # tu kwenye DB mpya; bila hii slots za siku mpya hazitengenezeki).
            from app.core.database import SessionLocal
            from app.models import Facility
            from app.seed import ensure_demo_facility, generate_today_slots

            seed_db = SessionLocal()
            try:
                facility = ensure_demo_facility(seed_db)
                generate_today_slots(seed_db, facility)
                seed_db.commit()
            finally:
                seed_db.close()
        except Exception as exc:  # DB not reachable yet — API still serves /health
            print(f"[startup] DB init skipped: {exc}")
    yield


app = FastAPI(
    title="Afya Smart API",
    description=(
        "AI Powered Triage & Queue Management for Fairer, Faster Public Healthcare. "
        "USSD/SMS triage, smart queue & slot booking, and demand analytics."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(ussd.router, prefix="/api/v1")
app.include_router(slots.router, prefix="/api/v1")
app.include_router(queue.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(demo.router)
app.include_router(dashboard.router)
