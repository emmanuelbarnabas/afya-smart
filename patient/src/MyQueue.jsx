// MyQueue — nafasi ya mgonjwa kwenye foleni (kwa namba ya simu)
import { useEffect, useState } from "react";
import { fetchMyQueue } from "./api.js";

const STATUS_LABEL = {
  none: { text: "Hujaingia foleni", cls: "idle", hint: "Tumia tab ya USSD au piga *384*37894# kuanza." },
  waiting: { text: "Uko kwenye foleni", cls: "waiting", hint: "Subiri unapoitwa. Usiache eneo." },
  called: { text: "NIMEKUITA — NJOO SASA!", cls: "called", hint: "Nenda kwenye desk ya ukaguzi mara moja." },
  in_consult: { text: "Upo kikitini", cls: "consult", hint: "Daktari anakukaribisha." },
  done: { text: "Umemaliza", cls: "done", hint: "Asante kwa kutumia Afya Smart." },
  left: { text: "Umeondoka kwenye foleni", cls: "done", hint: "Karibu tena." },
};

export default function MyQueue({ phone, setPhone, tick, setError }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const normalized = phone.trim();
    if (normalized.length < 6) {
      setData(null);
      return;
    }
    let alive = true;
    setLoading(true);
    fetchMyQueue(normalized)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phone, tick]);

  const status = STATUS_LABEL[data?.status ?? "none"] ?? STATUS_LABEL.none;

  return (
    <section className="pcard">
      <label className="pfield">
        <span>Namba yako ya simu</span>
        <input
          className="pinput"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="+2557..."
          inputMode="tel"
        />
      </label>

      {!data ? (
        <p className="pempty">
          {phone.trim().length < 6
            ? "Weka namba yako ya simu kuona nafasi yako."
            : loading
              ? "Inatafuta…"
              : "Bado hakuna taarifa za foleni kwa namba hii."}
        </p>
      ) : (
        <div className={`pstatus pstatus-${status.cls}`}>
          <span className="pstatus-icon">
            {status.cls === "called" ? "📣" : status.cls === "waiting" ? "🧍" : status.cls === "consult" ? "🩺" : status.cls === "done" ? "✅" : "ℹ️"}
          </span>
          <span className="pstatus-text">{status.text}</span>
          {data.status === "waiting" && (
            <span className="pstatus-big">Nafasi #{data.position}</span>
          )}
          <span className="pstatus-hint">{status.hint}</span>
          {data.status === "waiting" && (
            <span className="pstatus-meta">
              Wanasubiri kwa jumla: {data.waiting}
              {data.emergency && " · 🚨 kesi ya dharura"}
            </span>
          )}
        </div>
      )}

      <p className="pnote">
        💡 Nafasi inahesabiwa kwa priority — wagonjwa wa dharura wanapewa kipaumbele.
      </p>
    </section>
  );
}
