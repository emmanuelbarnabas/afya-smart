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

export default function QueuePanel({ queue, onStatus, busy }) {
  return (
    <section className="panel">
      <h2>Foleni Inayosubiri</h2>
      {queue.length === 0 ? (
        <p className="empty">Hakuna mgonjwa kwenye foleni.</p>
      ) : (
        <ul className="queue-list">
          {queue.map((entry, idx) => (
            <li key={entry.id} className={entry.is_emergency_bypass ? "queue-row row-danger" : "queue-row"}>
              <span className="queue-pos">#{idx + 1}</span>
              <span className="queue-ticket">Tiketi {String(entry.id).padStart(3, "0")}</span>
              {badge(entry)}
              <span className="queue-prio">P{entry.priority}</span>
              <span className="queue-time">
                {new Date(entry.joined_at).toLocaleTimeString("sw-TZ", { hour: "2-digit", minute: "2-digit" })}
              </span>
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
