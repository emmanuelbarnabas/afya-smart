import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api.js";
import StatsCards from "./components/StatsCards.jsx";
import QueuePanel from "./components/QueuePanel.jsx";
import AnalyticsPanel from "./components/AnalyticsPanel.jsx";

const POLL_MS = 5000;

function fmtTicket(id) {
  return String(id).padStart(3, "0");
}

export default function App() {
  const [facilities, setFacilities] = useState([]);
  const [facilityId, setFacilityId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [queue, setQueue] = useState([]);
  const [current, setCurrent] = useState(null); // mgonjwa aliyeitwa mwisho
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null); // ujumbe wa mafanikio
  const [busy, setBusy] = useState(false);
  const [soundOn, setSoundOn] = useState(false); // lazima iwashwe na user (autoplay policy)
  const [view, setView] = useState("live"); // live | analytics
  const toastTimer = useRef(null);
  const prevTopId = useRef(null);

  // Chagua facility ya kwanza mara moja
  useEffect(() => {
    api
      .facilities()
      .then((rows) => {
        setFacilities(rows);
        if (rows.length > 0) setFacilityId((prev) => prev ?? rows[0].id);
      })
      .catch((e) => setError(`Imeshindikana kupata facilities: ${e.message}`));
  }, []);

  const refresh = useCallback(async () => {
    if (!facilityId) return;
    try {
      const [s, q] = await Promise.all([
        api.queueSummary(facilityId),
        api.queue(facilityId),
      ]);
      setSummary(s);
      setQueue(q);
      setError(null);

      // Tangaza mgonjwa mpya aliyeitwa (kama sauti imewashwa)
      const top = q.find((e) => e.status === "called");
      if (top && prevTopId.current !== null && top.id !== prevTopId.current) {
        announce(top);
      }
      if (top) prevTopId.current = top.id;
    } catch (e) {
      setError(`Imeshindikana kupakua foleni: ${e.message}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [facilityId, soundOn]);

  // Polling ya live queue
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  function announce(entry) {
    // Sauti: tangaza tiketi kwa Kiswahili (Web Speech API — hakuna dependency)
    if (!soundOn || typeof window === "undefined" || !window.speechSynthesis) return;
    try {
      const name = entry.patient_name ? ` ${entry.patient_name}` : "";
      const u = new SpeechSynthesisUtterance(
        `Mgonjwa wa tiketi namba ${fmtTicket(entry.id)}${name}, karibu kwenye desk.`
      );
      u.lang = "sw-TZ";
      u.rate = 0.95;
      window.speechSynthesis.speak(u);
    } catch {
      /* speech haipatikani — kimya */
    }
  }

  function showToast(msg) {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3500);
  }

  async function handleCallNext() {
    setBusy(true);
    try {
      const result = await api.callNext(facilityId);
      setCurrent(result.entry);
      prevTopId.current = result.entry.id; // usitangaze mara mbili
      announce(result.entry);
      showToast(`📣 Tiketi ${fmtTicket(result.entry.id)} imeitwa`);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleEmergency() {
    setBusy(true);
    try {
      // Walk-in ya dharura: bypass ya foleni na priority ya juu
      const entry = await api.joinQueue(facilityId, {
        patient_id: 1, // demo patient
        is_walk_in: true,
        is_emergency_bypass: true,
      });
      showToast(`🚨 Dharura imeongezwa — Tiketi ${fmtTicket(entry.id)} (priority ${entry.priority})`);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleStatus(entryId, status) {
    setBusy(true);
    try {
      const updated = await api.updateStatus(entryId, status);
      const labels = { in_consult: "🩺 kikitini", done: "✅ imemaliza", left: "🚪 aliondoka" };
      showToast(`Tiketi ${fmtTicket(entryId)}: ${labels[status] ?? status}`);
      if (status === "in_consult") setCurrent(updated);
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const facility = facilities.find((f) => f.id === facilityId);

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Afya Smart — Admin</h1>
          <p className="subtitle">Dashibodi ya Kituo — {facility?.name ?? "..."}</p>
        </div>
        <div className="header-actions">
          {facilities.length > 1 && (
            <select
              className="facility-picker"
              value={facilityId ?? ""}
              onChange={(e) => setFacilityId(Number(e.target.value))}
              aria-label="Chagua kituo"
            >
              {facilities.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          )}
          <button
            className={`btn btn-sound${soundOn ? " on" : ""}`}
            onClick={() => setSoundOn((v) => !v)}
            title={soundOn ? "Zima sauti ya kutangaza" : "Washa sauti ya kutangaza tiketi"}
            aria-pressed={soundOn}
          >
            {soundOn ? "🔊 Sauti imewaka" : "🔇 Sauti imezimwa"}
          </button>
          <button className="btn btn-danger" onClick={handleEmergency} disabled={busy}>
            🚨 Dharura (Bypass)
          </button>
          <button className="btn btn-primary" onClick={handleCallNext} disabled={busy}>
            📣 Ita Mgonjwa
          </button>
        </div>
      </header>

      {toast && (
        <div className="banner-toast" role="status">
          {toast}
        </div>
      )}
      {error && (
        <div className="banner-error" role="alert">
          {error}
          <button className="banner-close" onClick={() => setError(null)} aria-label="Funga">
            ✕
          </button>
        </div>
      )}

      {current && (
        <div className="now-serving">
          <span className="now-serving-label">Sasa anaitwa</span>
          <span className="now-serving-number">
            Tiketi #{fmtTicket(current.id)}
          </span>
          {current.patient_name && (
            <span className="now-serving-name">{current.patient_name}</span>
          )}
          <span className="now-serving-meta">
            {current.is_emergency_bypass ? "🚨 DHARURA" : "Kawaida"} · Priority {current.priority}
          </span>
        </div>
      )}

      <div className="view-tabs" role="tablist">
        {[
          { id: "live", label: "🔴 Live Queue" },
          { id: "analytics", label: "📈 Analytics" },
        ].map((v) => (
          <button
            key={v.id}
            role="tab"
            aria-selected={view === v.id}
            className={`view-tab${view === v.id ? " active" : ""}`}
            onClick={() => setView(v.id)}
          >
            {v.label}
          </button>
        ))}
      </div>

      <div className="main-grid">
        <div className="main-col">
          {view === "live" ? (
            <>
              <StatsCards summary={summary} />
              <QueuePanel queue={queue} onStatus={handleStatus} busy={busy} />
            </>
          ) : (
            <AnalyticsPanel facilityId={facilityId} />
          )}
        </div>
      </div>

      <footer className="footer">
        <span>Hurejeshwa kila {POLL_MS / 1000} sekunde</span>
        {facility && (
          <span>
            {facility.region} · {facility.district} · {facility.code}
          </span>
        )}
      </footer>
    </div>
  );
}
