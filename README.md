# AFYA SMART

**AI Powered Triage & Queue Management for Fairer, Faster Public Healthcare**

- **Focus Area:** Public Health
- **Track:** Software (Web & Mobile)
- **Owner:** Emmanuel Stephen Barnabas

---

## 1. The Problem

Public health facilities in Tanzania have many problems that make it hard for patients to get
health services quickly:

- Many patients visit dispensaries/hospitals even when their problem could be safely checked
  via phone/online → overcrowding.
- Patients needing in-person care wait in queues **3–6 hours**; some arrive as early as
  **5:00–6:00 AM** to secure a place in the queue.
- Health workers have **no digital system** to know which patients need urgent care before
  they arrive.
- Most patients come in the morning, making the morning peak hard to manage.

## 2. Who It Affects

| Group | How they are affected |
|---|---|
| Patients & caregivers | Lose a full workday for routine care; rural patients can't tell if a visit is necessary before travelling. |
| Triage nurses & clinicians | Sort true emergencies from routine cases manually, with no prior info about who is arriving. |
| Facility administrators | Cannot see demand patterns, so staffing stays flat across peak and quiet hours. |
| Vulnerable groups (elderly, pregnant women, rural poor) | Disproportionately harmed by long physical waits and lack of guidance on where/when to seek care. |

## 3. Solution

Afya Smart is a **USSD/SMS and web platform** that guides a patient from the first symptom to
the point of care — **no smartphone or internet required** for the patient-facing side.

1. **AI Symptom Triage (USSD):** patient answers 4–6 short questions; a lightweight
   classification model estimates urgency and responds with *go now*, *book a routine slot*,
   or *self-care guidance*.
2. **Smart Queue & Slot Booking:** patients pick a time slot; the system uses historical visit
   data to show expected wait per slot and steers demand away from the 6–9 AM peak.
3. **Facility Dashboard:** front-desk staff call the next patient with one click, see live
   queue length, and can bypass the queue instantly for walk-in emergencies.
4. **Demand Analytics:** aggregated, anonymised hourly/daily demand patterns to inform staff
   scheduling (first step toward predictive drug-stock alerts and referral optimisation).

## 4. Technology Stack

| Layer | Technology |
|---|---|
| Patient access (no smartphone needed) | USSD & SMS via **Africa's Talking** API |
| Backend / API | **Python (FastAPI)** |
| AI / ML | **Python** — triage classifier + time-series model for queue demand forecasting |
| Database | **PostgreSQL** |
| Facility dashboard | **React.js**, mobile-first for low-end Android tablets/phones |
| Hosting | Lightweight cloud hosting (Render / Firebase Hosting) |

## 5. Project Structure

```
afya-smart/
├── backend/          # FastAPI application (API, USSD callback, queue logic)
│   ├── app/
│   │   ├── api/          # API routers (health, ussd, queue, slots, analytics)
│   │   ├── core/         # Settings, database connection
│   │   ├── models/       # SQLAlchemy ORM models
│   │   ├── schemas/      # Pydantic schemas
│   │   └── services/     # Business logic (triage, queue, forecasting)
│   └── tests/
├── ml/               # AI/ML: triage model + demand forecasting
├── dashboard/        # ADMIN — React facility dashboard (queue, analytics)
├── patient/          # CLIENT — app ya mgonjwa (nafasi yangu, miadi, USSD)
├── infra/            # docker-compose (PostgreSQL), deployment configs
├── docs/             # Documentation (docs/API.md, docs/DEMO.md)
└── README.md
```

**Platforma mbili:** Admin (`/admin` — kwa front-desk) na Client (`/app` — kwa mgonjwa).
Backend inahudumia zote mbili baada ya build.

## 6. Success Looks Like

- Reduced average physical wait time per patient (baseline vs. post-pilot, in minutes).
- % of USSD triage sessions correctly deferring non-urgent cases (validated by clinician review).
- Flatter demand curve — smaller gap between peak and off-peak patient volume.
- Adoption rate: patients per week using USSD booking vs. walk-in, plus repeat usage.
- **Zero missed emergencies** — no true emergency delayed by the triage/queue flow.

## 7. Getting Started (planned)

```bash
# 1. Database
cd infra && docker compose up -d

# 2. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 3. Dashboard
cd dashboard
npm install && npm run dev
```

Angalia pia: **[docs/API.md](docs/API.md)** (API spec) na **[docs/DEMO.md](docs/DEMO.md)**
(mwongozo wa demo, pamoja na kuunganisha USSD halisi ya Africa's Talking).
