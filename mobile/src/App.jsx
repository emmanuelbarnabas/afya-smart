// Afya Smart USSD — PWA ya simu.
// Simu ya bandia inayoita callback HALISI ya backend (/api/v1/ussd) — flow ileile
// ya AT/SMS gateway, ila ndani ya app yako. Service code inaletwa na /ussd-config.
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
  { k: "0", sub: "+" },
  { k: "#", sub: "\u00a0" },
];

const DEFAULT_CODE = "*384*37894#";
const PHONE_KEY = "afya_ussd_phone";

function buzz(ms) {
  try {
    navigator.vibrate?.(ms);
  } catch {
    /* haitumiki */
  }
}

export default function App() {
  const [serviceCode, setServiceCode] = useState(DEFAULT_CODE);
  const [screen, setScreen] = useState(null); // { text, kind }
  const [session, setSession] = useState(null);
  const [buffer, setBuffer] = useState("");
  const [busy, setBusy] = useState(false);
  const [offline, setOffline] = useState(!navigator.onLine);
  const [splash, setSplash] = useState(true); // splash screen ya kwanza
  const [phone, setPhone] = useState(() => localStorage.getItem(PHONE_KEY) || "+255700000001");
  // Namba ya simu iko wa kwanza: kabla ya kufanya mwonekano wala kufika kwa
  // foleni, mwanafanyakazi anaweza kubadilisha. Utazamisha kwa taarifa hii kwenye
  // msisiti na mteremko ya ftiri. Namba hii inahifadhiwa kwenye simu (localStorage).
  const [showPhone, setShowPhone] = useState(true); // kibadilishi cha namba
  const screenRef = useRef(null);

  // Splash: ficha baada ya kidogo (au tap)
  useEffect(() => {
    const t = setTimeout(() => setSplash(false), 1400);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    fetch("/ussd-config")
      .then((r) => (r.ok ? r.json() : null))
      .then((c) => c?.service_code && setServiceCode(c.service_code))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const on = () => setOffline(false);
    const off = () => setOffline(true);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  useEffect(() => {
    if (screenRef.current) screenRef.current.scrollTop = screenRef.current.scrollHeight;
  }, [screen]);

  async function send(sid, text, p) {
    setBusy(true);
    let raw;
    try {
      const resp = await fetch("/api/v1/ussd", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          sessionId: sid,
          phoneNumber: phone,
          text,
          serviceCode,
        }),
      });
      raw = await resp.text();
    } catch (e) {
      buzz(200);
      setScreen({
        text: `HITILAFI YA MTANDAO:\n${e.message}\n\nSession imekatika.`,
        kind: "end",
      });
      setSession(null);
      setBusy(false);
      return;
    }
    setBusy(false);
    if (raw.startsWith("CON ")) {
      setScreen({ text: raw.slice(4), kind: "con" });
      setBuffer("");
      setPath(p);
    } else if (raw.startsWith("END ")) {
      setScreen({ text: raw.slice(4) + "\n\n— Session imekwisha —", kind: "end" });
      setSession(null);
      setPath([]);
      buzz([80, 60, 80]); // mtetemo wa "imekwisha"
    } else {
      setScreen({ text: "Jibu lisiloeleweka kutoka kwa server.", kind: "end" });
      setSession(null);
    }
  }

  const [path, setPath] = useState([]);

  function dial() {
    if (session) {
      setSession(null);
      setScreen(null);
      setPath([]);
      setBuffer("");
      return;
    }
    buzz(30);
    const sid = `mobile-${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
    setSession({ id: sid });
    setScreen({ text: "...", kind: "con" });
    send(sid, "", []);
  }

  function pressKey(k) {
    if (!session || !screen || screen.kind !== "con") return;
    buzz(12); // mtetemo mfupi kama vitufe vya simu halisi
    setBuffer((b) => b + k);
  }

  function submit() {
    if (!session || !buffer) return;
    const p = [...path, buffer];
    send(session.id, p.join("*"), p);
  }

  function savePhone(v) {
    setPhone(v);
    localStorage.setItem(PHONE_KEY, v);
  }

  const inSession = session && screen?.kind === "con";
  const callLabel = !session
    ? `📞 ${serviceCode}`
    : inSession
      ? "➡️ TUMA"
      : "📞 Piga tena";

  if (splash) {
    return (
      <div className="msplash" onClick={() => setSplash(false)}>
        <span className="msplash-logo">✚</span>
        <h1>Afya Smart</h1>
        <p>USSD Triage — Afya kwa wote</p>
      </div>
    );
  }

  return (
    <div className="mapp">
      <header className="mapp-head">
        <span className="mapp-logo">✚</span>
        <div>
          <h1>Afya Smart</h1>
          <p>USSD Triage</p>
        </div>
        {offline && <span className="mapp-offline">⭯ Offline</span>}
        <button
          className="mapp-phone-btn"
          onClick={() => setShowPhone((v) => !v)}
          title="Badilisha namba ya simu ya session"
        >
          SIM
        </button>
      </header>

      {offline && (
        <div className="mapp-banner" role="alert">
          Hakuna mtandao — session ya USSD inahitaji mtandao.
        </div>
      )}

      {showPhone && (
        <div className="mphone-editor">
          <label>
            Namba ya simu (session hii itatumika nayo):
            <input
              value={phone}
              onChange={(e) => savePhone(e.target.value)}
              inputMode="tel"
              placeholder="+2557..."
            />
          </label>
          <p>Namba inahifadhiwa kwenye simu yako (localStorage). Badilisha hapa,
          kabla ya kufanya mtihani wala kufika kwa foleni.</p>
        </div>
      )}

      <main className="mphone">
        <div className="mphone-notch" />
        <div className="mphone-screen" ref={screenRef}>
          {screen ? (
            <>
              <div className="mscreen-status">
                <span>AFYASMART</span>
                <span>▂▄▆ 📶</span>
              </div>
              <div className={`mscreen-text mscreen-${screen.kind}`}>
                {screen.text}
                {inSession && buffer ? `\n> ${buffer}` : ""}
              </div>
            </>
          ) : (
            <div className="mscreen-idle">
              <span className="mscreen-idle-icon">📲</span>
              Bonyeza kitufe cha kijani
              <br />
              kupiga {serviceCode}
            </div>
          )}
        </div>

        <div className="mkeypad">
          {KEYS.map(({ k, sub }) => (
            <button
              key={k}
              className="mkey"
              onClick={() => pressKey(k)}
              disabled={!inSession}
              aria-label={`Kitufe ${k}`}
            >
              {k}
              <small>{sub}</small>
            </button>
          ))}
        </div>

        <div className="mphone-actions">
          <button className="mcall" onClick={inSession ? submit : dial} disabled={busy}>
            {callLabel}
          </button>
          <button
            className="mdel"
            onClick={() => {
              buzz(12);
              setBuffer((b) => b.slice(0, -1));
            }}
            disabled={!inSession || !buffer}
            aria-label="Futa herufi"
          >
            ⌫
          </button>
        </div>
      </main>

      <footer className="mfoot">
        <a className="mfoot-link" href="/app">
          🧍 Fungua app kamili ya mgonjwa (nafasi yangu · miadi)
        </a>
        <span>Namba: {phone} &bull; Huduma halisi: piga {serviceCode} kwenye simu yako</span>
      </footer>
    </div>
  );
}
