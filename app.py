"""Afya Smart — Flask + SQLite foundation (Phase 1).

Single-file app that creates the SQLite database, registers all tables, and
starts the Flask development server. Everything below lives in the project
root so a beginner can run it with a single command.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Flask, request

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(PROJECT_ROOT, "afyasmart.db")


def _parse_dt(value) -> Optional[datetime]:
    """Parse an ISO-ish timestamp produced by SQLite's ``datetime('now')``.

    SQLite stores ``YYYY-MM-DD HH:MM:SS`` (no timezone).  Our timestamps are
    all naive UTC, so we return a naive datetime.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _median(values: list[float]) -> float:
    """Median of a list of numbers (0.0 when empty)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _log_audit(db, actor, action, table_name, record_id, detail=""):
    """Append one line to the audit trail. Never crashes.

    The audit log is an append-only trail of every important change in the
    system.  We never edit a row in place; the only place a row is touched is
    the same place it was created, so we log what happened.  This function
    never raises, because a live USSD or API session must never die because
    of a logging problem.
    """
    try:
        db.execute(
            "INSERT INTO audit_log (actor, action, table_name, record_id, detail) VALUES (?, ?, ?, ?, ?)",
            (actor, action, table_name, record_id, detail),
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def get_db() -> sqlite3.Connection:
    """Open a connection to the SQLite database.

    ``row_factory`` makes each row behave like a small dict so we can read
    ``row["name"]`` instead of relying on positional indexes.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create every table the system needs. Safe to call many times."""
    with get_db() as conn:
        conn.executescript(
            """
            -- Facilities: the health centres / clinics that patients visit.
            CREATE TABLE IF NOT EXISTS facilities (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                level       TEXT NOT NULL,          -- e.g. "dispensary", "hospital"
                region      TEXT NOT NULL,
                district    TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Patients: one row per person. phone_number links a USSD session
            -- back to the same person; empty means the person registered by
            -- name (intake), or has no SIM.
            CREATE TABLE IF NOT EXISTS patients (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number    TEXT,
                full_name       TEXT,
                sex             TEXT,               -- "male", "female", ""
                year_of_birth   INTEGER,
                facility_id     INTEGER,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (facility_id) REFERENCES facilities(id)
            );

            -- Visits: one record per time a patient reaches the clinic (queue
            -- visit). A person can have several visits across days.
            CREATE TABLE IF NOT EXISTS visits (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                level      TEXT NOT NULL,           -- "RED", "YELLOW", "GREEN"
                reason     TEXT,
                status     TEXT NOT NULL DEFAULT 'waiting',
                joined_at  TEXT NOT NULL DEFAULT (datetime('now')),
                called_at  TEXT,
                completed_at TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            );

            -- audit_log: an append-only trail of every important change. We
            -- never edit rows in place -- the only place a row is touched is
            -- the same place it was created, so we log what happened.
            CREATE TABLE IF NOT EXISTS audit_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                actor      TEXT NOT NULL,           -- who changed something
                action     TEXT NOT NULL,           -- what happened
                table_name TEXT NOT NULL,           -- which table
                record_id  INTEGER,                 -- which row
                detail     TEXT,                     -- small note
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            -- Seed demo data (only if the tables are empty).
            INSERT OR IGNORE INTO facilities (id, name, level, region, district)
            VALUES (1, 'Msasani Dispensary', 'dispensary', 'Kinondoni', 'Ilala');
            """
        )
        # One active visit per phone number: if a patient is not yet finished
        # with their current visit, do not create a second one.
        conn.executescript(
            """
            -- One active visit per phone: we do not use a partial index (SQLite
            -- forbids subqueries in partial-index WHERE clauses). Instead the
            -- one-active-visit rule is enforced in the queue/intake services
            -- (see services/queue.py). All phone_number rows stay unique below.
            CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_phone_number
            ON patients(phone_number);
            """
        )


def create_app() -> Flask:
    """Build and return the Flask application."""
    app = Flask(__name__)
    app.config["DATABASE"] = DATABASE_PATH
    app.secret_key = os.environ.get("SECRET_KEY", "afya-secret-dev-only")

    # Make sure the database (and the demo facility) exist before the first
    # request arrives.
    @app.before_request
    def _ensure_database():
        init_db()

    # Basic health check so we can prove the server is alive.
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "afya-smart", "database": "sqlite"}

    # --------------------------------------------------------------------------
    # USSD entry point (Africa's Talking callback)
    # --------------------------------------------------------------------------
    # Africa's Talking POSTs to this URL with form fields:
    #     phoneNumber, text, sessionId, serviceCode, ...   (application/x-www-form-urlencoded)
    # The reply must start with "CON " (keep the session open) or "END "
    # (close the session).
    # --------------------------------------------------------------------------
    # Import USSD handler module (lazy, after app is configured).
    import ussd as _ussd  # noqa: F401 - no circular import because of lazy load

    @app.route("/ussd", methods=["POST"])
    def ussd_callback():
        # Pull the fields Africa's Talking sends us.
        phone_number = _ussd._get_form_value(request.form, "phoneNumber", "")
        text = _ussd._get_form_value(request.form, "text", "")

        # Turn the patient's answers into a reply.
        reply = _ussd._respond(
            phone_number, text.split("*") if text else []
        )
        return reply

    # --------------------------------------------------------------------------
    # Nurse dashboard
    # --------------------------------------------------------------------------
    # Static HTML + JSON endpoints for the front-desk nurse.  The queue page
    # auto-refreshes every few seconds so the nurse always sees the newest.
    # --------------------------------------------------------------------------

    import json
    from pathlib import Path
    from flask import render_template, request, jsonify

    _TEMPLATE_DIR = Path(__file__).parent / "templates"

    @app.route("/dashboard")
    def dashboard():
        """Render the nurse's live queue page."""
        return render_template("dashboard.html")

    @app.route("/fairness")
    def fairness():
        """Render the fairness report page."""
        return render_template("fairness.html")

    # USSD demo simulator page (the web version of the USSD session).
    _STATIC_DIR = Path(__file__).parent / "static"

    @app.route("/ussd-demo")
    def ussd_demo():
        """Render the USSD simulator demo page."""
        return render_template("ussd-demo.html")

    @app.route("/api/queue", methods=["GET"])
    def api_queue():
        """Return the current queue (all patients, newest first)."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM visits ORDER BY joined_at DESC"
            ).fetchall()
            return jsonify([dict(r) for r in rows])

    @app.route("/api/queue/status", methods=["POST"])
    def api_queue_status():
        """Change a patient's status (arrived / finished / cancelled)."""
        data = request.get_json(force=True) or {}
        entry_id = data.get("entry_id")
        action = data.get("action")
        actor = data.get("actor", "nurse")

        allowed = {"arrived", "finished", "cancelled"}
        if action not in allowed or entry_id is None:
            return jsonify({"error": "bad_request"}), 400

        with get_db() as db:
            row = db.execute(
                "UPDATE visits SET status = ? WHERE id = ?", (action, entry_id)
            ).fetchone()
            if row is None:
                return jsonify({"error": "not_found"}), 404
            _log_audit(
                db, actor, f"status_{action}", "visits", entry_id,
                f"status set to {action}",
            )
            return jsonify({"ok": True, "entry": dict(row)})

    @app.route("/api/queue/override", methods=["POST"])
    def api_queue_override():
        """Let the nurse change a patient's urgency level.

        Also records who did it in the audit log.
        """
        data = request.get_json(force=True) or {}
        entry_id = data.get("entry_id")
        new_level = data.get("new_level")
        actor = data.get("actor", "nurse")

        if new_level not in {"RED", "YELLOW", "GREEN"} or entry_id is None:
            return jsonify({"error": "bad_request"}), 400

        with get_db() as db:
            row = db.execute(
                "SELECT id, patient_id, level, reason FROM visits WHERE id = ?", (entry_id,)
            ).fetchone()
            if row is None:
                return jsonify({"error": "not_found"}), 404

            old_level = row["level"]
            db.execute(
                "UPDATE visits SET level = ?, reason = ? WHERE id = ?",
                (new_level, row["reason"], entry_id),
            )
            db.commit()

            detail = f"level changed from {old_level} to {new_level}"
            _log_audit(db, actor, "override_level", "visits", entry_id, detail)

            return jsonify({
                "ok": True, "entry": dict(row), "new_level": new_level,
            })

    @app.route("/api/facility", methods=["GET"])
    def api_facility():
        """Return the demo facility(s)."""
        with get_db() as db:
            rows = db.execute("SELECT * FROM facilities").fetchall()
            return jsonify([dict(r) for r in rows])

    @app.route("/api/audit", methods=["GET"])
    def api_audit():
        """Return the most recent audit log entries."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT 50"
            ).fetchall()
            return jsonify([dict(r) for r in reversed(rows)])

    @app.route("/api/fairness", methods=["GET"])
    def api_fairness():
        """Return the fairness report (synthetic demo data)."""
        with get_db() as db:
            visits = db.execute("SELECT * FROM visits").fetchall()
            patients = db.execute("SELECT * FROM patients").fetchall()
            facilities = db.execute("SELECT * FROM facilities").fetchall()

        from fairness import compute_fairness, _get

        groups = compute_fairness(visits, patients, facilities)

        # Overall summary.
        completed = [v for v in visits if _get(v, "status", "").lower() == "finished"]
        durations = []
        for v in completed:
            joined = _parse_dt(_get(v, "joined_at"))
            called = _parse_dt(_get(v, "called_at"))
            if joined and called and called > joined:
                durations.append((called - joined).total_seconds() / 60.0)

        overall_avg = sum(durations) / len(durations) if durations else 0.0
        overall_median = _median(durations) if durations else 0.0

        return {
            "groups": [g.to_dict() for g in groups],
            "total_completed": len(completed),
            "overall_avg_minutes": round(overall_avg, 1),
            "overall_median_minutes": round(overall_median, 1),
            "flagged_groups": sum(1 for g in groups if g.flagged),
            "filter": "all",
        }

    return app


app = create_app()


if __name__ == "__main__":
    # Dev convenience: create the DB now (the before_request hook would do it
    # anyway, but this lets us see a startup message). Disables the reloader
    # so pytest and `flask run` share one process.
    os.environ.setdefault("FLASK_ENV", "development")
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)
