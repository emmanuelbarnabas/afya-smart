import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import StatsCards from "./components/StatsCards.jsx";
import QueuePanel from "./components/QueuePanel.jsx";
import UssdSim from "./components/UssdSim.jsx";
import AnalyticsPanel from "./components/AnalyticsPanel.jsx";

const POLL_MS = 5000;

export default function App() {
  const [facilities, setFacilities] = useState([]);
  const [facilityId, setFacilityId] = useState(null);
  const [summary, setSummary] = useState(null);
  const [queue, setQueue] = useState([]);
  const [current, setCurrent] = useState(null); // mgonjwa aliyeitwa mwisho
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState("live"); // live | analytics

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
    } catch (e) {
      setError(`Imeshindikana kupakua foleni: ${e.message}`);
    }
  }, [facilityId]);

  // Polling ya live queue
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  async function handleCallNext() {
    setBusy(true);
    try {
      const result = await api.callNext(facilityId);
      setCurrent(result.entry);
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
      await api.joinQueue(facilityId, {
        patient_id: 1, // demo patient
        is_walk_in: true,
        is_emergency_bypass: true,
      });
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
      await api.updateStatus(entryId, status);
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
          <h1>Afya Smart</h1>
          <p className="subtitle">Dashibodi ya Kituo — {facility?.name ?? "..."}</p>
        </div>
        <div className="header-actions">
          <button className="btn btn-danger" onClick={handleEmergency} disabled={busy}>
            🚨 Dharura (Bypass)
          </button>
          <button className="btn btn-primary" onClick={handleCallNext} disabled={busy}>
            📣 Ita Mgonjwa
          </button>
        </div>
      </header>

      {error && (
        <div className="banner-error" role="alert">
          {error}
        </div>
      )}

      {current && (
        <div className="now-serving">
          <span className="now-serving-label">Sasa anaitwa</span>
          <span className="now-serving-number">
            Tiketi #{String(current.id).padStart(3, "0")}
          </span>
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
        <aside className="side-col">
          <UssdSim />
        </aside>
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
