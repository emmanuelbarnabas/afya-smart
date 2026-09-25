// Kadi za takwimu za foleni (kutoka /analytics/queue-summary)
export default function StatsCards({ summary }) {
  const cards = [
    { key: "waiting", label: "Wanasubiri", icon: "🧍", tone: "wait" },
    { key: "called", label: "Wameitwa", icon: "📣", tone: "called" },
    { key: "in_consult", label: "Kikitini", icon: "🩺", tone: "consult" },
    { key: "done_today", label: "Wamekwisha leo", icon: "✅", tone: "done" },
    { key: "emergency_bypasses_today", label: "Dharura leo", icon: "🚨", tone: "danger" },
  ];

  return (
    <section className="stats">
      {cards.map((c) => (
        <div key={c.key} className={`card card-${c.tone}`}>
          <span className="card-icon">{c.icon}</span>
          <span className="card-value">{summary ? summary[c.key] : "–"}</span>
          <span className="card-label">{c.label}</span>
        </div>
      ))}
    </section>
  );
}
