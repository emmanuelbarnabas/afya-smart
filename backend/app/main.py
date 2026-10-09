"""
AFYA SMART — AI Powered Triage & Queue Management
FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import analytics, dashboard, demo, health, intake, queue, reminders, slots, ussd
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
                # Dev auto-migrate: kama migrations za mwanzo hazijatumika
                # (DB ya kale), ongeza columns bila kuvunja startup.
                from sqlalchemy import inspect, text

                inspector = inspect(engine)
                table_names = inspector.get_table_names()
                auto_columns = {
                    "triage_sessions": [("clinician_urgency", "VARCHAR(20)")],
                    "queue_entries": [("clinician_urgency", "VARCHAR(20)")],
                    "appointments": [("reminder_sent_at", "TIMESTAMP")],
                    # Intake (mgonjwa bila SIM) alihitaji hii — DB ya kale
                    # ilikuwa bila is_anonymous kwa hivyo INSERT ilikuwa inaanguka.
                    "patients": [("is_anonymous", "BOOLEAN NOT NULL DEFAULT 0")],
                }
                for table, table_columns in auto_columns.items():
                    if table in table_names:
                        cols = {c["name"] for c in inspector.get_columns(table)}
                        for col, col_type in table_columns:
                            if col not in cols:
                                with engine.begin() as conn:
                                    conn.execute(
                                        text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
                                    )

                # Dev auto-migrate: patients.phone_number lazima ipokee NULL kwa
                # mgonjwa bila SIM (intake/anonymous). SQLite haiwezi kubadilisha
                # NOT NULL moja kwa moja — tunatumia alembic batch mode ambayo
                # hujenga table upya kwa data zilizopo (idempotent: hufanywa
                # mara tu ikiwa column bado haijakubali NULL).
                if "patients" in table_names:
                    pcols = {c["name"]: c for c in inspector.get_columns("patients")}
                    phone_col = pcols.get("phone_number", {})
                    if phone_col and not phone_col.get("nullable", True):
                        import sqlalchemy as sa
                        from alembic.migration import MigrationContext
                        from alembic.operations import Operations

                        with engine.begin() as conn:
                            ctx = MigrationContext.configure(conn)
                            operations = Operations(ctx)
                            with operations.batch_alter_table("patients") as batch_op:
                                batch_op.alter_column(
                                    "phone_number",
                                    existing_type=sa.String(20),
                                    nullable=True,
                                )

                facility = ensure_demo_facility(seed_db)
                generate_today_slots(seed_db, facility, days=7)
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
app.include_router(reminders.router, prefix="/api/v1")
app.include_router(demo.router)
app.include_router(intake.router)
app.include_router(dashboard.router)
