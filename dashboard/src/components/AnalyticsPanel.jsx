// AnalyticsPanel — chatu za demand, forecast, na matokeo ya triage.
// Chatu ni SVG safi (hakuna dependencies mpya — chart.js n.k. hazihitajiki).
import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

const HOURS = Array.from({ length: 24 }, (_, i) => i);

function fmtHour(h) {
  const period = h < 12 ? "AM" : "PM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}${period}`;
}

/* ---------- Chatu ya nguzo (SVG) ---------- */
function BarChart({ points, height = 170 }) {
  const data = useMemo(() => {
    const byHour = new Map();
    for (const p of points) {
      byHour.set(p.hour, (byHour.get(p.hour) ?? 0) + p.visits);
    }
    return HOURS.map((h) => ({ hour: h, visits: byHour.get(h) ?? 0 }));
  }, [points]);

  const W = 700;
  const H = height;
  const PAD_B = 22;
  const PAD_T = 12;
  const max = Math.max(1, ...data.map((d) => d.visits));
  const bw = W / 24;
  const chartH = H - PAD_B - PAD_T;

  return (
    <svg
      className="chart"
      viewBox={`0 0 ${W} ${H}`}
      role="img"
      aria-label="Wagonjwa kwa saa"
    >
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <line
          key={f}
          x1="0"
          x2={W}
          y1={PAD_T + chartH * (1 - f)}
          y2={PAD_T + chartH * (1 - f)}
          className="chart-grid"
        />
        ))}
      {data.map(({ hour, visits }) => {
        const h = (visits / max) * chartH;
        const isPeak = hour >= 6 && hour < 9;
        return (
          <g key={hour}>
            <rect
              x={hour * bw + 1.5}
              y={PAD_T + chartH - h}
              width={bw - 3}
              height={h}
              className={isPeak ? "chart-bar chart-bar-peak" : "chart-bar"}
            >
              <title>{`${fmtHour(hour)} — wagonjwa: ${visits}`}</title>
            </rect>
            {hour % 3 === 0 && (
              <text
                x={hour * bw + bw / 2}
                y={H - 6}
                textAnchor="middle"
                className="chart-xlabel"
              >
                {fmtHour(hour)}
              </text>
              )}
          </g>
        );
      })}
    </svg>
  );
}

/* ---------- Chatu ya mstari (SVG) ---------- */
function LineChart({ profile, height = 150 }) {
  const W = 700;
  const H = height;
  const PAD_B = 22;
  const PAD_T = 10;
  const chartH = H - PAD_B - PAD_T;
  const max = Math.max(0.5, ...profile.map((p) => p.expected_visits));
  const step = W / 23;

  const pts = profile.map((p) => ({
    x: p.hour * step,
    y: PAD_T + chartH - (p.expected_visits / max) * chartH,
  }));

  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const area = `${path} L${W},${PAD_T + chartH} L0,${PAD_T + chartH} Z`;

  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Demand iliyotabiriwa">
      {[0.5, 1].map((f) => (
        <line
          key={f}
          x1="0"
          x2={W}
          y1={PAD_T + chartH * (1 - f)}
          y2={PAD_T + chartH * (1 - f)}
          className="chart-grid"
        />
      ))}
      <path d={area} className="chart-area" />
      <path d={path} className="chart-line" />
      {pts
        .filter((_, i) => i % 3 === 0)
        .map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="2.5" className="chart-dot" />
        ))}
      {profile
        .filter((p) => p.hour % 3 === 0)
        .map((p) => (
          <text
            key={p.hour}
            x={p.hour * step}
            y={H - 6}
            textAnchor="middle"
            className="chart-xlabel"
          >
            {fmtHour(p.hour)}
          </text>
        ))}
    </svg>
  );
}

/* ---------- Triage outcomes ---------- */
function TriageOutcomes({ outcomes }) {
  const rows = [
    { key: "emergency_directed", label: "Elekeza dharura", icon: "🚨", tone: "danger" },
    { key: "slot_booked", label: "Slot imewekwa", icon: "📅", tone: "info" },
    { key: "self_care_given", label: "Self-care", icon: "🏠", tone: "ok" },
    { key: "abandoned", label: "Zilizoachwa", icon: "🚪", tone: "muted" },
  ];
  const total = Math.max(1, outcomes.total);
  return (
    <div className="triage-grid">
      {rows.map((r) => {
        const n = outcomes[r.key] ?? 0;
        const pct = Math.round((n / total) * 100);
        return (
          <div key={r.key} className={`triage-card triage-${r.tone}`}>
            <span className="triage-icon">{r.icon}</span>
            <span className="triage-value">{n}</span>
            <span className="triage-label">{r.label}</span>
            <div className="triage-bar">
              <div className="triage-bar-fill" style={{ width: `${pct}%` }} />
            </div>
            <span className="triage-pct">{pct}%</span>
          </div>
        );
      })}
    </div>
  );
}

/* ---------- Panel kuu ---------- */
export default function AnalyticsPanel({ facilityId }) {
  const [tab, setTab] = useState("demand"); // demand | forecast | triage
  const [demand, setDemand] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [outcomes, setOutcomes] = useState(null);
  const [days, setDays] = useState(7);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!facilityId) return;
    let alive = true;
    setError(null);
    Promise.all([
      api.demand(facilityId, days),
      api.demandForecast(facilityId),
      api.triageOutcomes(facilityId),
    ])
      .then(([d, f, o]) => {
        if (!alive) return;
        setDemand(d);
        setForecast(f);
        setOutcomes(o);
      })
      .catch((e) => alive && setError(e.message));
    return () => {
      alive = false;
    };
  }, [facilityId, days]);

  if (error) {
    return (
      <section className="panel analytics">
        <h2>📈 Analytics</h2>
        <p className="empty">Imeshindikana kupakua analytics: {error}</p>
      </section>
      );
  }

  return (
    <section className="panel analytics">
      <div className="analytics-head">
        <h2>📈 Analytics</h2>
        <div className="analytics-tabs" role="tablist">
          {[
            { id: "demand", label: "Demand" },
            { id: "forecast", label: "Forecast" },
            { id: "triage", label: "Triage" },
          ].map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              className={`analytics-tab${tab === t.id ? " active" : ""}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        {tab === "demand" && (
          <select
            className="analytics-days"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            aria-label="Idadi ya siku"
          >
            <option value={1}>Leo</option>
            <option value={7}>Siku 7</option>
            <option value={30}>Siku 30</option>
          </select>
        )}
      </div>

      {tab === "demand" && (
        demand && demand.length > 0 ? (
          <BarChart points={demand} />
        ) : (
          <p className="empty">
            Hakuna data ya demand bado — itajaa kadiri wagonjwa wanavyo-check-in.
          </p>
        )
      )}

      {tab === "forecast" && (
        forecast && forecast.length > 0 ? (
          <LineChart profile={forecast} />
        ) : (
          <p className="empty">Forecast haipatikani bado.</p>
        )
      )}

      {tab === "triage" && (
        outcomes ? <TriageOutcomes outcomes={outcomes} /> : <p className="empty">Inapakia…</p>
      )}

      {tab === "demand" && demand?.length > 0 && (
        <p className="analytics-note">
          Nguzo za kijani ni peak ya asubuhi (6–9 AM) — lengo ni kusukuma demand kwenda
          saa zisizo za peak kupitia slot booking.
        </p>
      )}
    </section>
  );
}
