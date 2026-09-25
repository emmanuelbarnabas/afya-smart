// UssdSim (patient) — simu ya bandia inayoita callback halisi ya USSD
import { useEffect, useRef, useState } from "react";
import { fetchUssdConfig } from "./api.js";

const KEYS = [
  { k: "1", sub: "\u00a0" },
  { k: "2", sub: "ABC" },
  { k: "3", sub: "DEF" },
  { k: "4", sub: "GHI" },
  { k: "5", sub: "JKL" },
  { k: "6", sub: "MNO" },
  { k: "7", sub: "PQRS" },
  { k: "8", sub: "TUV" },
  { k: "9", sub: "WXYZ" },
  { k: "*", sub: "\u00a0" },
  { k: "0", sub: "\u00a0" },
  { k: "#", sub: "\u00a0" },
];

export default function UssdSim() {
  const [phone, setPhone] = useState(localStorage.getItem("afya_phone") || "+255700000001");
  const [serviceCode, setServiceCode] = useState("*384*37894#");
  const [screen, setScreen] = useState(null);
  const [session, setSession] = useState(null);
  const [path, setPath] = useState([]);
  const [buffer, setBuffer] = useState("");
  const screenRef = useRef(null);

  useEffect(() => {
    fetchUssdConfig()
      .then((c) => c?.service_code && setServiceCode(c.service_code))
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (screenRef.current) screenRef.current.scrollTop = screenRef.current.scrollHeight;
  }, [screen]);

  async function send(sid, phoneNumber, text, p) {
    const body = new URLSearchParams({ sessionId: sid, phoneNumber, text, serviceCode });
    let raw;
    try {
      const resp = await fetch("/api/v1/ussd", { method: "POST", body });
      raw = await resp.text();
    } catch (e) {
      setScreen({ text: `HITILAFI YA MTANDAO:\n${e.message}\n\nSession imekatika.`, kind: "end" });
      setSession(null);
      return;
    }
    if (raw.startsWith("CON ")) {
      setScreen({ text: raw.slice(4), kind: "con" });
      setBuffer("");
      setPath(p);
    } else if (raw.startsWith("END ")) {
      setScreen({ text: raw.slice(4) + "\n\n— Session imekwisha —", kind: "end" });
      setSession(null);
      setPath([]);
    } else {
      setScreen({ text: "Jibu lisiloeleweka kutoka kwa server.", kind: "end" });
      setSession(null);
    }
  }

  function dial() {
    if (session) {
      setSession(null);
      setScreen(null);
      setPath([]);
      setBuffer("");
      return;
    }
    const sid = `pwa-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    const p = phone.trim() || "+255700000001";
    setSession({ id: sid, phone: p });
    setScreen({ text: "...", kind: "con" });
    send(sid, p, "", []);
  }

  function pressKey(k) {
    if (!session || !screen || screen.kind !== "con") return;
    if (k === "*" || k === "#") return;
    setBuffer((b) => b + k);
  }

  function submit() {
    if (!session || !buffer) return;
    const p = [...path, buffer];
    send(session.id, session.phone, p.join("*"), p);
  }

  const inSession = session && screen?.kind === "con";
  const callLabel = !session
    ? `📶 Piga ${serviceCode}`
    : inSession
      ? "➡️ Tuma"
      : "📶 Piga tena";

  return (
    <section className="pcard pcard-ussd">
      <label className="pfield">
        <span>Namba yako ya simu</span>
        <input
          className="pinput"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          inputMode="tel"
        />
      </label>

      <div className="pussd-frame">
        <div className="pussd-screen" ref={screenRef}>
          {screen ? (
            <>
              <div className="pussd-status">
                <span>AFYASMART</span>
                <span>▂▄▆ 📶</span>
              </div>
              <div className={`pussd-text pussd-${screen.kind}`}>
                {screen.text}
                {inSession && buffer ? `\n> ${buffer}` : ""}
              </div>
            </>
          ) : (
            <div className="pussd-idle">
              Bonyeza kitufe cha kijani
              <br />
              kupiga {serviceCode}
            </div>
          )}
        </div>

        <div className="pussd-keypad">
          {KEYS.map(({ k, sub }) => (
            <button
              key={k}
              className="pussd-key"
              onClick={() => pressKey(k)}
              disabled={!inSession}
            >
              {k}
              <small>{sub}</small>
            </button>
          ))}
        </div>

        <button className="pussd-call" onClick={inSession ? submit : dial}>
          {callLabel}
        </button>
        <button
          className="pussd-clear"
          onClick={() => setBuffer((b) => b.slice(0, -1))}
          disabled={!inSession || !buffer}
        >
          Futa input ◂
        </button>
      </div>
    </section>
  );
}
