// Kadi za takwimu za foleni (kutoka /analytics/queue-summary)
import {
  UsersIcon,
  MegaphoneIcon,
  StethoscopeIcon,
  CheckCircleIcon,
  SirenIcon,
} from "./Icons.jsx";

export default function StatsCards({ summary }) {
  const cards = [
    { key: "waiting", label: "Wanasubiri", Icon: UsersIcon, tone: "wait" },
    { key: "called", label: "Wameitwa", Icon: MegaphoneIcon, tone: "called" },
    { key: "in_consult", label: "Kikitini", Icon: StethoscopeIcon, tone: "consult" },
    { key: "done_today", label: "Wamekwisha leo", Icon: CheckCircleIcon, tone: "done" },
    { key: "emergency_bypasses_today", label: "Dharura leo", Icon: SirenIcon, tone: "danger" },
  ];

  return (
    <section className="stats">
      {cards.map(({ key, label, Icon, tone }) => (
        <div key={key} className={`card card-${tone}`}>
          <span className="card-icon">
            <Icon size={20} />
          </span>
          <span className="card-value">{summary ? summary[key] : "–"}</span>
          <span className="card-label">{label}</span>
        </div>
      ))}
    </section>
  );
}
