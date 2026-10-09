// Orodha ya foleni hai — priority juu iko juu, emergency inang'aa.
// Pamoja na feedback ya clinician (hali halisi ya mgonjwa baada ya ukaguzi).
import { useState } from "react";
import {
  StethoscopeIcon,
  CheckCircleIcon,
  DoorIcon,
  SirenIcon,
  ClipboardIcon,
} from "./Icons.jsx";

const STATUS_ACTIONS = [
  { value: "in_consult", label: "Kikitini", Icon: StethoscopeIcon },
  { value: "done", label: "Maliza", Icon: CheckCircleIcon },
  { value: "left", label: "Aliondoka", Icon: DoorIcon },
];

const URGENCY_FEEDBACK = [
  { value: "emergency", label: "Dharura" },
  { value: "urgent", label: "Haraka" },
  { value: "routine", label: "Kawaida" },
  { value: "self_care", label: "Nyumbani" },
];

function badge(entry) {
  if (entry.is_emergency_bypass)
    return (
      <span className="badge badge-danger">
        <SirenIcon size={11} /> DHARURA
      </span>
    );
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

function etaLabel(mins) {
  if (mins == null) return null;
  if (mins < 1) return "anaitwa sasa hivi";
  if (mins < 60) return `~${mins} dk`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `~${h} sk ${m} dk` : `~${h} sk`;
}

function FeedbackRow({ entry, onFeedback, busy }) {
  const [open, setOpen] = useState(false);
  if (entry.clinician_urgency) {
    const labels = {
      emergency: "Dharura",
      urgent: "Haraka",
      routine: "Kawaida",
      self_care: "Nyumbani",
    };
    return (
      <span className="feedback-done" title="Uamuzi wa clinician umerekodiwa">
        {labels[entry.clinician_urgency] ?? entry.clinician_urgency}
      </span>
    );
  }
  if (!open) {
    return (
      <button className="btn btn-sm btn-feedback" disabled={busy} onClick={() => setOpen(true)}>
        <ClipboardIcon size={13} />
        Uamuzi wa clinician
      </button>
    );
  }
  return (
    <span className="feedback-options">
      {URGENCY_FEEDBACK.map((u) => (
        <button
          key={u.value}
          className="btn btn-sm"
          disabled={busy}
          onClick={() => {
            setOpen(false);
            onFeedback(entry.id, u.value);
          }}
        >
          {u.label}
        </button>
      ))}
    </span>
  );
}

export default function QueuePanel({ queue, onStatus, onFeedback, busy }) {
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
              {entry.eta_minutes != null && (
                <span className="queue-eta" title="Muda unaotabiriwa wa kusubiri">
                  ⏱ {etaLabel(entry.eta_minutes)}
                </span>
              )}
              <span className="queue-actions">
                {STATUS_ACTIONS.map(({ value, label, Icon }) => (
                  <button
                    key={value}
                    className="btn btn-sm"
                    disabled={busy}
                    onClick={() => onStatus(entry.id, value)}
                  >
                    <Icon size={13} />
                    {label}
                  </button>
                ))}
                <FeedbackRow entry={entry} onFeedback={onFeedback} busy={busy} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
