// API client ya patient app
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
      /* si JSON */
    }
    throw new Error(detail);
  }
  return resp.json();
}

export const api = {
  facilities: () => request("/facilities"),
  slots: (facilityId, day) =>
    request(
      `/facilities/${facilityId}/slots?date=${day}${day ? "" : "&available_only=true"}`
    ),
  book: (patientId, slotId) =>
    request("/bookings", {
      method: "POST",
      body: JSON.stringify({ patient_id: patientId, slot_id: slotId }),
    }),
  queue: (facilityId) => request(`/facilities/${facilityId}/queue`),
  queueCount: (facilityId) => request(`/facilities/${facilityId}/queue/count`),
};

// Nafasi ya mgonjwa kwa namba ya simu (endpoint ya demo, bila /api/v1)
export async function fetchMyQueue(phone) {
  const resp = await fetch(`/my-queue?phone=${encodeURIComponent(phone)}`);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json();
}

export async function fetchUssdConfig() {
  const resp = await fetch("/ussd-config");
  if (!resp.ok) throw new Error("ussd-config haipatikani");
  return resp.json();
}
