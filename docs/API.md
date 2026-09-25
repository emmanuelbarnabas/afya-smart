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
    "version": "ml-v1",
    "algorithm": "gradient_boosting",
    "trained_at": "2026-09-24T09:15:04Z",
    "accuracy": 0.93
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
maswali ya triage (4–6) → outcome: *go now* (emergency/urgent) / *book slot* (routine) / *self-care*.

---

## Demo (bila prefix `/api/v1`)

| Endpoint                | Maelezo                                            |
|-------------------------|----------------------------------------------------|
| `GET /ussd-demo`        | Ukurasa wa USSD simulator (HTML)                   |
| `GET /ussd-config`      | `{"service_code": "*384*37894#"}`                  |
| `GET /my-queue?phone=`  | Nafasi ya mgonjwa kwa namba ya simu (PWA ya simu)  |

**`GET /my-queue?phone=%2B255700111222` — Response 200**

```json
{ "status": "waiting", "position": 2, "waiting": 5, "priority": 0, "emergency": false }
```

`status` inaweza kuwa `none`, `waiting`, `called`, `in_consult`, `done`, `left`.

---

## Facilities & Slots

### `GET /api/v1/facilities`

Orodha ya vituo.

### `GET /api/v1/facilities/{facility_id}/slots?date=2026-09-25&available_only=true`

Slots za siku (available tu kwa default), pamoja na `expected_wait_minutes` kutoka kwenye demand forecast.

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
{ "emergency_directed": 2, "slot_booked": 15, "self_care_given": 9, "abandoned": 4, "total": 30 }
```
