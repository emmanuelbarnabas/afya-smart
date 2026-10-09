# Afya Smart — API Specification

Base URL (dev): `http://localhost:8000`
Interactive docs: `http://localhost:8000/docs` (Swagger, inatolewa na FastAPI)

Endpoint zote za API ziko chini ya prefix ya `/api/v1`; endpoint za demo (`/ussd-demo`, `/my-queue`, `/ussd-config`) pekee ndizo hazina prefix.

---

## Health

### `GET /api/v1/health`

Hali ya API na ML model ya triage.

**Response 200**

```json
{
  "status": "ok",
  "service": "afya-smart-api",
  "version": "0.1.0",
  "triage_model": {
    "loaded": true,
    "version": "ml-v2",
    "algorithm": "gradient_boosting",
    "trained_at": "2026-09-28T16:48:46Z",
    "accuracy": 0.894,
    "recall_emergency": 0.884,
    "n_samples": 12000
  }
}
```

---

## USSD (Africa's Talking callback)

### `POST /api/v1/ussd`

Callback ya Africa's Talking — `application/x-www-form-urlencoded`:

| Field         | Mfano           |
|---------------|-----------------|
| `sessionId`   | `ATUid_12345`   |
| `phoneNumber` | `+255700111222` |
| `serviceCode` | `*384*37894#`   |
| `text`        | `1*1*2` (path ya majibu, `*`-separated) |

**Response:** `CON <maandishi>` (endelea) au `END <maandishi>` (maliza), `text/plain`.

Mtiririko: lugha (1=Kiswahili, 2=English) → menyu (1=dalili, 2=miadi, 3=nafasi foleni) →
maswali ya triage (6) → outcome:

| Urgency | Outcome | Nini kinatokea |
|---|---|---|
| EMERGENCY | `emergency_directed` | END — agiza afike mara moja / piga 112 |
| URGENT | `walk_in_directed` | END — anaingizwa foleni ya leo yenye kipaumbele (priority 10), nafasi + maagizo |
| ROUTINE | `slot_booked` | CON — menyu ya slots bora (leo, au kesho kama leo imejaa/zimepita) |
| SELF_CARE | `self_care_given` | END — miongozo ya nyumbani + kipimo cha kurudi |

Menyu ya slots inaonyesha expected wait kwa kila slot na inasukuma demand nje ya peak ya 6–9 AM.

---

## Demo (bila prefix `/api/v1`)

| Endpoint                | Maelezo                                            |
|-------------------------|----------------------------------------------------|
| `GET /ussd-demo`        | Ukurasa wa USSD simulator (HTML)                   |
| `GET /ussd-config`      | `{"service_code": "*384*37894#"}`                  |
| `GET /my-queue?phone=`  | Nafasi ya mgonjwa kwa namba ya simu (PWA ya simu)  |

**`GET /my-queue?phone=%2B255700111222` — Response 200**

```json
{ "status": "waiting", "position": 2, "waiting": 5, "priority": 0, "emergency": false, "eta_minutes": 34 }
```

`status` inaweza kuwa `none`, `waiting`, `called`, `in_consult`, `done`, `left`.
`eta_minutes` ni makadirio ya muda wa kusubiri (nafasi × muda wa huduma wa wastani wa kituo, kutoka history).

---

## Facilities & Slots

### `GET /api/v1/facilities`

Orodha ya vituo.

### `GET /api/v1/facilities/{facility_id}/slots?date=2026-09-25&available_only=true`

Slots za siku (available tu kwa default), pamoja na `expected_wait_minutes` kutoka kwenye demand forecast.
Slots za leo zilizopita (start_time < sasa, saa za eneo) hazionekani na haziwezi kubookiwa.

**Response 200** — `[{ "id": 55, "date": "2026-09-25", "start_time": "08:00:00", "end_time": "08:30:00", "capacity": 6, "booked": 0, "expected_wait_minutes": 30 }]`

### `POST /api/v1/bookings` — 201

```json
{ "patient_id": 1, "slot_id": 55, "triage_session_id": null }
```

**Errors:** `404` slot haipo · `409` slot imejaa / mgonjwa ana miadi tayari siku hiyo.

### `DELETE /api/v1/bookings/{appointment_id}` — 200

Ghairi miadi; `booked` count ya slot inapunguzwa.

---

## Queue (dashboard ya front-desk)

### `GET /api/v1/facilities/{facility_id}/queue`

Foleni inayosubiri — `priority` (desc) kisha `joined_at` (asc).

**Response 200** — `QueueEntryOut[]`:

```json
[{
  "id": 12, "facility_id": 1, "patient_id": 1, "appointment_id": null,
  "is_walk_in": true, "is_emergency_bypass": true, "priority": 100,
  "status": "waiting", "joined_at": "2026-09-25T08:12:00Z",
  "called_at": null, "completed_at": null
}]
```

### `POST /api/v1/facilities/{facility_id}/queue` — 201

Check-in (walk-in au appointment → queue entry):

```json
{ "patient_id": 1, "appointment_id": null, "is_walk_in": true, "is_emergency_bypass": false, "priority": 0 }
```

Emergency bypass inapata priority `100` na kurudi mbele ya foleni yote.

### `POST /api/v1/facilities/{facility_id}/queue/call-next` — 200

Kitufe cha "Ita Mgonjwa" — inaita aliye juu wa foleni.

**Response 200**: `{ "entry": QueueEntryOut, "waiting_count": 4 }` · **404** foleni tupu.

### `POST /api/v1/queue/{entry_id}/status?status=in_consult`

Badilisha hali: `in_consult` | `done` | `left`. `done` inaweka `completed_at`.

### `POST /api/v1/queue/{entry_id}/clinician-urgency`

Feedback loop: rekodi uamuzi wa mwisho wa clinician (`emergency|urgent|routine|self_care`).
Inaunganisha na triage session ya mgonjwa — ndiyo data ya `/triage-accuracy` na kufundisha model.

```json
{ "clinician_urgency": "urgent" }
```

**Errors:** `404` entry haipo · `422` value si sahihi.

### `GET /api/v1/reminders/upcoming?hours=24&limit=20`

Miadi ijayo (booked, ndani ya masaa `hours` zijazo) — inatumika na page ya
"📬 Kumbusho" ya dashibodi. Kila item: `appointment_id`, `patient_name`,
`patient_phone`, `date`, `start_time`, `reminder_sent`.

### `POST /api/v1/reminders/run?dry_run=false`

Tuma kumbusho za SMS za miadi ya masaa 24 zijazo (dedup kwa `reminder_sent_at`).
`dry_run=true` inahesabu tu. Inarudisha `{ "sent": 3, "skipped": 0 }`.

### `GET /api/v1/facilities/{facility_id}/queue/count`

`{ "facility_id": 1, "waiting": 3 }`

---

## Analytics

Prefix zote: `/api/v1/facilities/{facility_id}/analytics/...`

### `GET /demand?days=7`

Idadi ya wagonjwa kwa (tarehe, saa) — walk-ins + bookings. Inaonyesha peak ya asubuhi (6–9 AM).

**Response 200**: `[{ "date": "2026-09-25", "hour": 8, "visits": 14 }]`

### `GET /demand-forecast?days_history=30`

Profaili ya demand iliyotabiriwa kwa saa (0–23): `[{ "hour": 8, "expected_visits": 3.0 }]`

### `GET /queue-summary`

```json
{ "waiting": 3, "called": 1, "in_consult": 1, "done_today": 6, "emergency_bypasses_today": 1 }
```

### `GET /triage-outcomes?days=30`

Matokeo ya triage — `%` ya non-urgent zilizopewa self-care/miadi:

```json
{ "emergency_directed": 18, "walk_in_directed": 37, "slot_booked": 88, "self_care_given": 48, "abandoned": 11, "total": 202 }
```

### `GET /wait-times?days=7`

**Metric ya #1 ya mafanikio:** muda wa kusubiri (joined → called) na muda wa huduma (called → completed), kutoka history halisi:

```json
{ "avg_wait_minutes": 43.0, "median_wait_minutes": 20.0, "p90_wait_minutes": 36.0, "avg_service_minutes": 13.5, "n_completed": 115, "period_days": 7 }
```

### `GET /triage-accuracy?days=30`

Usahihi wa triage dhidi ya uamuzi wa clinician (`clinician_urgency` kwenye triage_sessions — feedback loop). `undertriage_rate` ndiyo kipimo muhimu zaidi — inapaswa kufuata sifuri (zero missed emergencies). `alert: true` inapoonekana (under-triage ≥ 15%), dashboard inaonyesha tahadhari ya usalama:

```json
{ "total_reviewed": 179, "agrees": 152, "overtriaged": 6, "undertriaged": 21, "agreement_rate": 0.849, "undertriage_rate": 0.117, "alert": false, "threshold": 0.15 }
```
