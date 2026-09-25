// Orodha ya foleni hai — priority juu iko juu, emergency inang'aa
const STATUS_ACTIONS = [
  { value: "in_consult", label: "🩺 Kikitini" },
  { value: "done", label: "✅ Maliza" },
  { value: "left", label: "🚪 Aliondoka" },
];

function badge(entry) {
  if (entry.is_emergency_bypass) return <span className="badge badge-danger">DHARURA</span>;
  if (entry.priority >= 10) return <span className="badge badge-warn">HARAKA</span>;
  if (entry.is_walk_in) return <span className="badge badge-info">WALK-IN</span>;
  return <span className="badge badge-plain">MIADI</span>;
}

function waitedLabel(mins) {
  if (mins == null) return null;
  if (mins < 1) return "sasa hivi";
  if (mins < 60) return `amengoja ${mins} dk`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `amengoja ${h} sk ${m} dk` : `amengoja ${h} sk`;
}

export default function QueuePanel({ queue, onStatus, busy }) {
  return (
    <section className="panel">
      <h2>Foleni Inayosubiri</h2>
      {queue.length === 0 ? (
        <p className="empty">Hakuna mgonjwa kwenye foleni.</p>
      ) : (
        <ul className="queue-list">
          {queue.map((entry) => (
            <li
              key={entry.id}
              className={
                entry.is_emergency_bypass
                  ? "queue-row row-danger"
                  : entry.priority >= 10
                    ? "queue-row row-warn"
                    : "queue-row"
              }
            >
              <span className="queue-pos">#{entry.position ?? "?"}</span>
              <div className="queue-who">
                <span className="queue-name">{entry.patient_name || "Mgonjwa (bila jina)"}</span>
                <span className="queue-sub">
                  Tiketi {String(entry.id).padStart(3, "0")} · {badge(entry)}{" "}
                  {waitedLabel(entry.waited_minutes) && (
                    <span className="queue-wait">· {waitedLabel(entry.waited_minutes)}</span>
                  )}
                </span>
              </div>
              <span className="queue-prio">P{entry.priority}</span>
              <span className="queue-actions">
                {STATUS_ACTIONS.map((a) => (
                  <button
                    key={a.value}
                    className="btn btn-sm"
                    disabled={busy}
                    onClick={() => onStatus(entry.id, a.value)}
                  >
                    {a.label}
                  </button>
                ))}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
