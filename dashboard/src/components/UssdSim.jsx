// UssdSim — simu ya bandia ya USSD ndani ya dashibodi.
// Inaita callback halisi ya backend (/api/v1/ussd) — flow ileile ya AT,
// ila bila simulator ya nje. Service code inaletwa na /ussd-config.
import { useEffect, useRef, useState } from "react";

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
  const [phone, setPhone] = useState("+255700000001");
  const [serviceCode, setServiceCode] = useState("*384*123#");
  const [screen, setScreen] = useState(null); // { text, kind }
  const [session, setSession] = useState(null);
  const [path, setPath] = useState([]);
  const [buffer, setBuffer] = useState("");
  const screenRef = useRef(null);

  // Pata service code halisi ya channel kutoka kwa backend
  useEffect(() => {
    fetch("/ussd-config")
      .then((r) => r.json())
      .then((c) => c?.service_code && setServiceCode(c.service_code))
      .catch(() => {});
  }, []);

  // Scroll screen to the bottom on new content
  useEffect(() => {
    if (screenRef.current) screenRef.current.scrollTop = screenRef.current.scrollHeight;
  }, [screen]);

  async function send(sid, phoneNumber, text, p) {
    const body = new URLSearchParams({
      sessionId: sid,
      phoneNumber,
      text,
      serviceCode,
    });
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
      // kitufe kinawa maliza session
      setSession(null);
      setScreen(null);
      setPath([]);
      setBuffer("");
      return;
    }
    const sid = `dash-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    const p = phone.trim() || "+255700000001";
    setSession({ id: sid, phone: p });
    setScreen({ text: "...", kind: "con" });
    send(sid, p, "", []);
  }

  function pressKey(k) {
    if (!session || !screen || screen.kind !== "con") return;
    if (k === "*" || k === "#") return; // hazitumiki kwenye menyu hizi
    setBuffer((b) => b + k);
  }

  function submit() {
    if (!session || !buffer) return;
    const p = [...path, buffer];
    send(session.id, session.phone, p.join("*"), p);
  }

  function backspace() {
    if (session && buffer) setBuffer((b) => b.slice(0, -1));
  }

  const inSession = session && screen?.kind === "con";
  const callLabel = !session
    ? `📶 Piga ${serviceCode}`
    : inSession
      ? "➡️ Tuma"
      : "📶 Piga tena " + serviceCode;

  return (
    <div className="ussd-sim">
      <div className="ussd-sim-head">
        <h2>📲 Kivinjari cha USSD</h2>
        <input
          className="ussd-phone"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          inputMode="tel"
          aria-label="Namba ya simu"
        />
      </div>

      <div className="ussd-phone-frame">
        <div className="ussd-screen" ref={screenRef}>
          {screen ? (
            <>
              <div className="ussd-status">
                <span>AFYASMART</span>
                <span>▂▄▆ 📶</span>
              </div>
              <div className={`ussd-text ussd-${screen.kind}`}>
                {screen.text}
                {inSession && buffer ? `\n> ${buffer}` : ""}
              </div>
            </>
          ) : (
            <div className="ussd-idle">
              Bonyeza kitufe cha kijani
              <br />
              kupiga {serviceCode}
            </div>
          )}
        </div>

        <div className="ussd-keypad">
          {KEYS.map(({ k, sub }) => (
            <button
              key={k}
              className="ussd-key"
              onClick={() => pressKey(k)}
              disabled={!inSession}
            >
              {k}
              <small>{sub}</small>
            </button>
          ))}
        </div>

        <button className="ussd-call" onClick={inSession ? submit : dial}>
          {callLabel}
        </button>
        <button className="ussd-clear" onClick={backspace} disabled={!inSession || !buffer}>
          Futa input ◂
        </button>
      </div>

      <div className="ussd-session-info">
        {session ? `Session: ${session.id.slice(0, 22)}… · ${session.phone}` : "Hakuna session"}
      </div>
    </div>
  );
}
