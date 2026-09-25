// App ya Mgonjwa (client) — tofauti na dashibodi ya admin.
// Tabs: Nafasi Yangu (queue kwa namba ya simu) · Miadi (book slot) · USSD (simulator)
import { useCallback, useEffect, useState } from "react";
import MyQueue from "./MyQueue.jsx";
import Booking from "./Booking.jsx";
import UssdSim from "./UssdSim.jsx";

const POLL_MS = 10000;

export default function App() {
  const [tab, setTab] = useState("queue"); // queue | book | ussd
  const [phone, setPhone] = useState(localStorage.getItem("afya_phone") || "");
  const [error, setError] = useState(null);

  useEffect(() => {
    localStorage.setItem("afya_phone", phone);
  }, [phone]);

  const refreshKey = useCallback(() => Math.floor(Date.now() / POLL_MS), []);
  const [tick, setTick] = useState(refreshKey());
  useEffect(() => {
    const t = setInterval(() => setTick(refreshKey()), POLL_MS);
    return () => clearInterval(t);
  }, [refreshKey]);

  return (
    <div className="papp">
      <header className="papp-head">
        <div>
          <h1>Afya Smart</h1>
          <p className="papp-sub">App ya Mgonjwa</p>
        </div>
      </header>

      {error && (
        <div className="papp-error" role="alert">
          {error}
          <button className="papp-error-close" onClick={() => setError(null)} aria-label="Funga">
            ✕
          </button>
        </div>
      )}

      <div className="papp-tabs" role="tablist">
        {[
          { id: "queue", label: "🧍 Nafasi Yangu" },
          { id: "book", label: "📅 Miadi" },
          { id: "ussd", label: "📲 USSD" },
        ].map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={`papp-tab${tab === t.id ? " active" : ""}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <main className="papp-main">
        {tab === "queue" && (
          <MyQueue phone={phone} setPhone={setPhone} tick={tick} setError={setError} />
        )}
        {tab === "book" && <Booking setError={setError} />}
        {tab === "ussd" && <UssdSim />}
      </main>

      <footer className="papp-foot">
        <span>Huduma: *384*37894#</span>
        <span>Afya Smart © 2026</span>
      </footer>
    </div>
  );
}
