// API client — fetch wrapper kwa backend ya Afya Smart.
// Dev: Vite proxy inapeleka /api → http://localhost:8000
const BASE = "/api/v1";

async function request(path, options = {}) {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* response si JSON — tumia status tu */
    }
    throw new Error(detail);
  }
  return resp.status === 204 ? null : resp.json();
}

export const api = {
  facilities: () => request("/facilities"),
  queueSummary: (facilityId) =>
    request(`/facilities/${facilityId}/analytics/queue-summary`),
  queue: (facilityId) => request(`/facilities/${facilityId}/queue`),
  callNext: (facilityId) =>
    request(`/facilities/${facilityId}/queue/call-next`, { method: "POST" }),
  updateStatus: (entryId, status) =>
    request(`/queue/${entryId}/status`, {
      method: "POST",
      body: JSON.stringify(status),
    }),
  setClinicianUrgency: (entryId, clinician_urgency) =>
    request(`/queue/${entryId}/clinician-urgency`, {
      method: "POST",
      body: JSON.stringify({ clinician_urgency }),
    }),
  runReminders: (dryRun = false) =>
    request(`/reminders/run${dryRun ? "?dry_run=true" : ""}`, { method: "POST" }),
  upcomingAppointments: (hours = 24) =>
    request(`/reminders/upcoming?hours=${hours}`),
  joinQueue: (facilityId, payload) =>
    request(`/facilities/${facilityId}/queue`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  // Analytics
  demand: (facilityId, days = 7) =>
    request(`/facilities/${facilityId}/analytics/demand?days=${days}`),
  demandForecast: (facilityId) =>
    request(`/facilities/${facilityId}/analytics/demand-forecast`),
  triageOutcomes: (facilityId, days = 30) =>
    request(`/facilities/${facilityId}/analytics/triage-outcomes?days=${days}`),
  waitTimes: (facilityId, days = 7) =>
    request(`/facilities/${facilityId}/analytics/wait-times?days=${days}`),
  triageAccuracy: (facilityId, days = 30) =>
    request(`/facilities/${facilityId}/analytics/triage-accuracy?days=${days}`),
};
