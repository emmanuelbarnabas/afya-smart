# Afya Smart

**AI-powered triage & queue management for fairer, faster public healthcare.**

Afya Smart lets a patient register from **any phone, using USSD — no smartphone,
no internet, no app** — *before* they arrive at the clinic. The system gives them
an urgency level (RED / YELLOW / GREEN) and a queue number, so the nurses see a
**single live queue** on a web dashboard when they walk in. A fairness report
flags any group that is being treated worse than the rest.

- **Patient side:** USSD (Africa's Talking) + a one-page web demo.
- **Nurse side:** a live web dashboard (`/dashboard`) with a single queue.
- **Fairness side:** a web report (`/fairness`) grouped by sex, age, facility
  and urgency level.

> **PROTOTYPE — NOT FOR REAL CLINICAL USE.** Triage rules and the queue engine
> in this codebase are a hackathon prototype. They **must be reviewed and
> signed off by medical professionals** before any real patient is triaged by
> this software. This note is repeated in the USSD menus and the dashboard.

---

## 1. What's in the folder

| File / folder | Purpose |
|---|---|
| `app.py` | The whole Flask + SQLite app. One file to read, one command to run. |
| `database.py` | *(this replaces/rename: the DB is created inside `app.py` with SQLite)* |
| `triage.py` | Rule-based triage → `(RED / YELLOW / GREEN, reason)`. Safety-first: unsure ⇒ escalate. |
| `queue_engine.py` | Priority queue: `priority = base_weight * 60 - minutes_waited`. A GREEN patient who waited long overtakes a fresh YELLOW. |
| `ussd.py` | Africa's Talking USSD handler (Swahili menu, RED immediate END, invalid input → no crash). |
| `fairness.py` | Fairness report: average wait per (sex × age × facility × urgency). |
| `seed_data.py` | Generates ~100 realistic fake patients so the demo looks alive. |
| `templates/dashboard.html` | Nurse's live queue (auto-refresh, Call next, Mark arrived, Finish, level override + audit). |
| `templates/fairness.html` | Fairness report with Chart.js charts. |
| `requirements.txt` | `Flask` + `pytest` (only what this project needs). |
| `tests/` | Pytest suite. |
| `afyasmart.db` | SQLite database (created on first run). |

> **No React, no FastAPI, no PostgreSQL.** Python + Flask + SQLite only.

---

## 2. Install

You need **Python 3.12+**. (If your system Python is older, use `pyenv`,
`apt`, or the Python.org installer.)

```bash
python3 --version          # must be 3.12+
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Run

```bash
python app.py
# or: flask run
```

Open:

- **USSD demo web page:** `http://localhost:5000/ussd-demo`
- **Nurse's live queue:** `http://localhost:5000/dashboard`
- **Fairness report:** `http://localhost:5000/fairness`
- **Health check:** `http://localhost:5000/health`

Everything is SQLite — no server to install, no migration to run.

---

## 4. Seed the demo data (so the queues and reports look alive)

```bash
python seed_data.py --count 100
```

This writes ~100 fake patients and visits across 3 demo facilities. **Never**
use real patient data for the demo (the code never sends real names/phones
outside the clinic).

---

## 5. Test the USSD flow with curl

Africastalking POSTs form fields `phoneNumber` and `text` to `/ussd` with
`application/x-www-form-urlencoded`. Each `text` is a chain of answers joined
with `*` — the whole chain is replayed on every request and the handler reads
the **last** element. The reply must start with **"CON "** (keep the session
open) or **"END "** (close it).

The first element is the **menu choice**: `1` = register/triage, `2` = show
queue position, `3` = unregister. The six triage questions follow it.

```bash
BASE=http://localhost:5000

# 1. Start the USSD session (returns the menu)
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345678" -d "text="

# 2. Menu choice 1 (register) -> sex question
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345678" -d "text=1"

# 3. Sex: 1 = male, 2 = female -> fever question
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345678" -d "text=1*1"

# 4. Fever: 1 = yes, 2 = no -> age question
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345678" -d "text=1*1*2"

# 5. Age (years): any number -> chest-pain question
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345678" -d "text=1*1*2*30"

# 6. Chest pain: 1 = yes (immediate RED END), 2 = no -> breathing question
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345678" -d "text=1*1*2*30*2"

# 7. Breathing difficulty: 1 = yes (immediate RED END), 2 = no
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345678" -d "text=1*1*2*30*2*2"

# 8. Severe bleeding: 1 = yes (immediate RED END), 2 = no
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345678" -d "text=1*1*2*30*2*2*2"

# 9. Facility: 1, 2 or 3 -> END with the real queue position
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345678" -d "text=1*1*2*30*2*2*2*1"
```

**Red flag → immediate `END` message, no queue slot.** Answering chest pain
`1` ends the session at once (the patient is not asked more questions):

```bash
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345679" -d "text=1*1*2*40*1"
```

**Output starts with `END Bahati gracious...` and tells the patient to go to
the hospital NOW.**

**Invalid input (non-numeric age) does not crash — the same question is
repeated:**

```bash
curl -X POST "$BASE/ussd" \
  -d "phoneNumber=+255712345682" -d "text=1*1*2*abc"
```

Output: `CON Umri uliyotoa haufai. Andika umri sahihi (mfano 30).`

---

## 6. Test with Africa's Talking sandbox + ngrok

1. **Sign up** at [Africa's Talking](https://account.africastalking.com) and
   get a **sandbox** username + API key.
2. **Install the Africa's Talking SDK** (optional): `pip install africastalking`.
3. **Expose the local server:**
   ```bash
   # one-time: pip install cloudflared
   ./tunnel.sh
   ```
   This prints a public URL like `https://afya-smart.trycloudflare.com`.
4. In the Africa's Talking sandbox, set the **USSD callback URL** to
   `https://YOUR-TUNNEL.com/api/ussd` (the `POST` endpoint).
5. Set the USSD code in `.env` (optional):
   ```
   USSD_SERVICE_CODE=*384*123#
   AT_USERNAME=sandbox
   AT_API_KEY=<your sandbox api key>
   ```
6. Send a test USSD from your phone. (In sandbox mode it may just echo back
   through the callback URL — check your sandbox logs.)

---

## 7. Demo — 3 minutes

```bash
# 1. fresh demo data
python seed_data.py --count 100

# 2. start the server
python app.py

# 3. (in two more terminals, if you like)
#    a) watch the USSD flow for one patient
#    b) watch the nurse queue at http://localhost:5000/dashboard
#    c) watch the fairness report at http://localhost:5000/fairness
```

**What to show:**

| Step | What happens |
|---|---|
| 1. Nurse opens `/dashboard` | A live queue with a "Call next" button. |
| 2. Patient USSD-registers | 6 questions, Swahili. |
| 3. RED patient | Immediate `END` → "go to hospital NOW", no queue slot. |
| 4. YELLOW patient | Given a queue number + estimated wait. |
| 5. GREEN patient | Given a queue number + estimated wait. |
| 6. Nurse "Call next" / "Mark arrived" / "Finish" | Status changes, `audit_log` grows. |
| 7. Nurse changes level | e.g. YELLOW → RED, logged in `audit_log`. |
| 8. Open `/fairness` | Average wait per group, flagged rows highlight. |

---

## 8. How the priority queue works

```
priority = base_weight × 60 − minutes_waited
```

| Level   | base weight | 0 min wait | 60 min wait | 120 min wait |
|---------|-------------|------------|-------------|--------------|
| RED     | 0           | 0          | 0           | 0            |
| YELLOW  | 1           | 60         | 0           | −60          |
| GREEN   | 2           | 120        | 60          | 0            |

**Lower number = called first.** A GREEN patient who waited 120 minutes has
`priority = 0`, the same as a fresh RED — the "aging" rule in the spec.
`queue_engine.py` has a unit test (`test_queue_engine.py`) proving a GREEN
patient overtakes a fresh YELLOW.

---

## 9. Fairness report

`/fairness` groups completed visits by **sex × age band × facility × urgency**
and computes average / median / standard deviation of wait time. A group is
flagged when its average wait is more than **one standard deviation above the
clinic average**. All demo data is synthetic.

---

## 10. Privacy & safety

- **No real health data** is ever stored or sent outside the clinic.
- **SMS/USSD messages never name a disease.** The RED message is
  `"Hii ni dharura! ... afike kituo cha afya HADI"` — it does not say *what*
  is wrong.
- **Audit trail:** every status change and every level override is logged in
  `audit_log` with who did it, when, and what changed.

---

## 11. Future work

- **Real SMS** via Africa's Talking (async, queue-based, not part of the
  USSD path).
- **ML triage** — train a classifier on clinician feedback (see
  `backend/ml/train_triage.py` in the original repo, re-implemented here as
  `triage.py` rules for the prototype).
- **Hospital integration** — HL7/FHIR feeds for arrival times, bed status.
- **Webhook retries** — Africa's Talking retries POSTs; `ussd.py` currently
  replies idempotently by remembering the last answer-chain + reply per
  phone number (a replayed chain returns the cached reply, no duplicate
  visit). The session store is in-memory — move it to Redis/Postgres before
  running more than one worker process.
- **Multi-facility / address** — add a `facility_id` + district to every row
  so the queue can serve several clinics.

---

## 12. Running the tests

```bash
python -m pytest tests/ -v
```

Everything runs offline, no DB server, no network.

---

## 13. Files at a glance

```
app.py            Flask app + SQLite + routes
database.py       (DB created inside app.py)
triage.py         rule-based triage (RED/YELLOW/GREEN)
queue_engine.py   priority queue engine + tests
ussd.py           Africa's Talking USSD handler
fairness.py       fairness report
seed_data.py      ~100 fake patients
requirements.txt  Flask + pytest
templates/
  dashboard.html  nurse queue (auto-refresh, actions, audit)
  fairness.html   fairness report (Chart.js)
```

> This is a **hackathon prototype** — a working end-to-end demo of the USSD
> → triage → queue → fairness pipeline. It is not production triage software.
