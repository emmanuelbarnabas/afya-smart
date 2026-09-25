// Booking — mgonjwa anachagua kituo + slot, kisha book
import { useEffect, useState } from "react";
import { api } from "./api.js";

function dayLabel(d) {
  return new Date(d + "T00:00:00").toLocaleDateString("sw-TZ", {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}

export default function Booking({ setError }) {
  const [facilities, setFacilities] = useState([]);
  const [facilityId, setFacilityId] = useState(null);
  const [day, setDay] = useState(new Date().toISOString().slice(0, 10));
  const [slots, setSlots] = useState([]);
  const [patientId, setPatientId] = useState(
    Number(localStorage.getItem("afya_patient_id")) || null
  );
  const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState(null);

  useEffect(() => {
    api
      .facilities()
      .then((rows) => {
        setFacilities(rows);
        if (rows.length) setFacilityId(rows[0].id);
      })
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!facilityId) return;
    setSlots([]);
    api
      .slots(facilityId, day)
      .then(setSlots)
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facilityId, day]);

  async function book(slotId) {
    if (!patientId) {
      setError("Weka Patient ID yako kwanza (uliyopewa wakati wa triage/registration).");
      return;
    }
    setBusy(true);
    try {
      const appt = await api.book(patientId, slotId);
      setConfirmed(appt);
      setSlots((prev) =>
        prev.map((s) => (s.id === slotId ? { ...s, booked: s.booked + 1 } : s))
      );
      localStorage.setItem("afya_patient_id", String(patientId));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const days = Array.from({ length: 3 }, (_, i) => {
    const d = new Date();
    d.setDate(d.getDate() + i);
    return d.toISOString().slice(0, 10);
  });

  return (
    <section className="pcard">
      <label className="pfield">
        <span>Kituo</span>
        <select
          className="pinput"
          value={facilityId ?? ""}
          onChange={(e) => setFacilityId(Number(e.target.value))}
        >
          {facilities.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}
            </option>
          ))}
        </select>
      </label>

      <div className="pfield">
        <span>Siku</span>
        <div className="pdays">
          {days.map((d, i) => (
            <button
              key={d}
              className={`pday${day === d ? " active" : ""}`}
              onClick={() => setDay(d)}
            >
              {i === 0 ? "Leo" : dayLabel(d)}
            </button>
          ))}
        </div>
      </div>

      <label className="pfield">
        <span>Patient ID (kutoka registration/triage)</span>
        <input
          className="pinput"
          type="number"
          value={patientId ?? ""}
          onChange={(e) => setPatientId(e.target.value ? Number(e.target.value) : null)}
          placeholder="mf. 1"
        />
      </label>

      {confirmed && (
        <div className="pconfirm">
          ✅ Miadi imethibitishwa! Slot #{confirmed.slot_id} — tuma SMS utaipokea.
        </div>
      )}

      <h3 className="ptitle">Nafasi zilizobaki</h3>
      {slots.length === 0 ? (
        <p className="pempty">Hakuna slots za siku hii — jaribu siku nyingine.</p>
      ) : (
        <ul className="pslots">
          {slots.map((s) => {
            const full = s.booked >= s.capacity;
            return (
              <li key={s.id} className={`pslot${full ? " full" : ""}`}>
                <span className="pslot-time">{s.start_time.slice(0, 5)}</span>
                <span className="pslot-wait">~{s.expected_wait_minutes ?? "?"} dk kusubiri</span>
                <span className="pslot-left">
                  {s.capacity - s.booked} nafasi
                </span>
                <button
                  className="pbtn"
                  disabled={busy || full}
                  onClick={() => book(s.id)}
                >
                  {full ? "IMEJAA" : "Weka"}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
