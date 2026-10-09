// RemindersPanel — page ya Kumbusho: orodha ya miadi ijayo (masaa 24) na kitufe
// cha kutuma kumbusho za SMS. Kumbusho zinatumwa mara moja tu (dedup kwa
// reminder_sent_at — zilizotumwa zimekauliwa "imetumwa").
import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import { BellIcon, CheckCircleIcon, ClockIcon, RefreshIcon } from "./Icons.jsx";

export default function RemindersPanel({ busy }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);
  const [notice, setNotice] = useState(null);
  const [dryRun, setDryRun] = useState(false); // hesabu tu — hakuna SMS inayotumwa

  const load = useCallback(() => {
    setLoading(true);
    api
      .upcomingAppointments(24)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const result = await api.runReminders(dryRun);
      setNotice(
        dryRun
          ? `Kumbusho ${result.due} zinazopasa (dry run — hakuna SMS iliyotumwa)`
          : `Zimetumwa: ${result.sent}${result.skipped ? ` · zimeshindikana: ${result.skipped}` : ""}`
      );
      load(); // sasisha orodha — zilizotumwa sasa zimekauliwa "imetumwa"
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="panel reminders">
      <div className="reminders-head">
        <h2 className="panel-title-ico">
          <BellIcon size={18} /> Kumbusho za SMS
        </h2>
        <label className="reminders-dry">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
          />
          Dry run (hesabu tu)
        </label>
      </div>
      <p className="reminders-sub">
        Miadi ya masaa 24 zijazo. Kumbusho inatumwa mara moja tu kwa kila miadi.
      </p>

      {notice && <div className="reminders-notice">{notice}</div>}
      {error && <div className="reminders-error" role="alert">{error}</div>}

      <div className="reminders-actions">
        <button className="btn btn-primary" onClick={run} disabled={running || busy}>
          {running ? "Inatuma…" : dryRun ? "Hesabu zinazopasa" : "Tuma kumbusho sasa"}
        </button>
        <button className="btn" onClick={load} disabled={loading}>
          <RefreshIcon size={14} />
          Sasisha orodha
        </button>
      </div>

      {loading && !data ? (
        <p className="empty">Inapakia…</p>
      ) : !data || data.count === 0 ? (
        <p className="empty">Hakuna miadi ya masaa 24 zijazo.</p>
      ) : (
        <ul className="reminders-list">
          {data.items.map((item) => (
            <li key={item.appointment_id} className="reminders-row">
              <span className="reminders-when">
                {item.date} · {item.start_time}
              </span>
              <span className="reminders-who">
                {item.patient_name || "Mgonjwa (bila jina)"}
                <small> {item.patient_phone}</small>
              </span>
              <span className={item.reminder_sent ? "reminders-sent" : "reminders-pending"}>
                {item.reminder_sent ? (
                  <>
                    <CheckCircleIcon size={12} /> imetumwa
                  </>
                ) : (
                  <>
                    <ClockIcon size={12} /> haijatumwa
                  </>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
