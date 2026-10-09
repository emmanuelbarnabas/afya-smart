// App ya Mgonjwa (client) — tofauti na dashibodi ya admin.
// Kurasa 3 huru zenye utengano: Nafasi Yangu · Miadi · USSD
// Nav ya chini (mtindo wa app ya simu) — kila huduma page yake, bila routing ya URL.
import { useCallback, useEffect, useState } from "react";
import MyQueue from "./MyQueue.jsx";
import Booking from "./Booking.jsx";
import UssdSim from "./UssdSim.jsx";

const POLL_MS = 10000;

const PAGES = [
  { id: "queue", label: "Nafasi", icon: "🧍" },
  { id: "book", label: "Miadi", icon: "📅" },
  { id: "ussd", label: "USSD", icon: "📲" },
];

export default function App() {
  const [page, setPage] = useState("queue"); // queue | book | ussd
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
          <p className="papp-sub">
            {PAGES.find((p) => p.id === page)?.label ?? ""} — App ya Mgonjwa
          </p>
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

      <main className="papp-main">
        {page === "queue" && (
          <MyQueue phone={phone} setPhone={setPhone} tick={tick} setError={setError} />
        )}
        {page === "book" && <Booking setError={setError} />}
        {page === "ussd" && <UssdSim />}
      </main>

      {/* Nav ya chini — kila huduma page yake */}
      <nav className="papp-nav" role="tablist" aria-label="Kurasa za app">
        {PAGES.map((p) => (
          <button
            key={p.id}
            role="tab"
            aria-selected={page === p.id}
            className={`papp-nav-btn${page === p.id ? " active" : ""}`}
            onClick={() => setPage(p.id)}
          >
            <span className="papp-nav-icon">{p.icon}</span>
            <span className="papp-nav-label">{p.label}</span>
          </button>
        ))}
      </nav>

      <footer className="papp-foot">
        <span>Huduma: *384*37894#</span>
        <span>Afya Smart © 2026</span>
      </footer>
    </div>
  );
}
