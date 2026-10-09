# Afya Smart — Demo Guide (Mwongozo wa Demo)

Mwongozo wa kukimbia demo kamili: USSD halisi (Africa's Talking), dashibodi ya kituo,
na API. Chukua dakika ~10 kuandaa kabla ya kuanza kuwasilisha.

---

## 0. Mahitaji ya awali

- Docker (kwa PostgreSQL)
- Terminal moja ya bash

## 1. Anzisha kila kitu (dakika 2)

```bash
# 1a. Database (Postgres kwenye port 5433)
docker compose -f infra/docker-compose.yml up -d

# 1b. Backend (port 8000) — inatengeneza tables + seed za slots za leo
cd backend
setsid nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/afya_api.log 2>&1 < /dev/null &
cd ..

# 1c. Dashboard (port 5173)
cd dashboard
npm install   # mara ya kwanza tu
npm run dev
```

Thibitisha:

```bash
curl http://localhost:8000/api/v1/health          # status: ok + triage_model (ml-v2)
curl http://localhost:8000/api/v1/facilities      # demo dispensary
```

## 2. Demo ya ndani (bila simu halisi)

Platforma ni mbili, zinatofautishwa:

| Platform | URL (dev) | Kwa nani |
|---|---|---|
| **Admin** (dashibodi ya kituo) | http://localhost:5173 au `:8000/admin` | Front-desk: foleni hai, dharura bypass, ita mgonjwa, analytics, kumbusho — kurasa 3 huru (Foleni · Analytics · Kumbusho) |
| **Client** (app ya mgonjwa) | `:8000/app` | Mgonjwa: nafasi yangu, miadi, USSD simulator |
| **Mobile PWA** (USSD app ya simu) | `:8000/mobile/` | App ndogo ya simu: USSD sim tu — "Add to Home Screen" kusakinisha |
| USSD simulator (ya kale) | http://localhost:8000/ussd-demo | Demo ya callback halisi |
| API docs (Swagger) | http://localhost:8000/docs | Developers |

Apps mbili zinajengwa tofauti: `cd dashboard && npm run build` (admin) na `cd patient && npm run build` (client). Backend inazihudumia zote mbili. PWA ya mobile inajengwa kwa `cd mobile && npm run build`.

### Kufungua kwenye SIMU (portalaini)

1. Anzisha tunnel: `./tunnel.sh` → `https://<something>.trycloudflare.com`
2. Simu (karibu na PC kwa WiFi au data):
   - **App ya mgonjwa:** `https://<tunnel-url>/app`
   - **Dashibodi ya admin:** `https://<tunnel-url>/admin`
   - **PWA ya USSD (kusakinisha):** fungua `https://<tunnel-url>/mobile/` → menyu ya
     browser → **Add to Home Screen** — app inasakinishwa, inafunguka full-screen
     kama app halisi (manifest + service worker zimepangwa tayari).
3. USSD *halisi* kwa dial pad: fuata sehemu ya 3 hapa chini.

Mwilikio wa haraka wa USSD (screen ya kwanza):

```bash
curl -X POST http://localhost:8000/api/v1/ussd \
  -d "sessionId=demo1&phoneNumber=%2B255700111222&text=&serviceCode=*384*37894#"
# CON Karibu AFYA SMART ...
```

## 3. USSD halisi kutoka simu (Africa's Talking)

1. **Anzisha tunnel ya umma:**

   ```bash
   ./tunnel.sh          # inatoa https://<something>.trycloudflare.com
   ```

2. **Weka credentials za AT** (sandbox au production):

   ```bash
   ./at-setup.sh        # inaomba AT_USERNAME, AT_API_KEY, AT_PHONE_NUMBER
   ./test-at-key.sh <username>   # kuhakiki key (bure, hakuna salio)
   ```

3. **Kwenye dashi ya Africa's Talking:**
   - USSD → Create channel → Callback URL:
     `https://<tunnel-url>/api/v1/ussd`
   - Service code itakuwa `*384*<channelID>#`

4. **Piga `*384*<channelID>#` kwenye simu** — utaona menyu ya Afya Smart.

> Sandbox: namba ya simu lazima iwekwe kwenye "Test Phone Numbers" ya sandbox.

## 4. Script ya demo (dakika 5)

1. **Tatizo (30s):** foleni ndefu asubuhi, hakuna mfumo wa kujua dharura kabla ya ufika.
2. **USSD triage (90s):** piga *384*... kwenye simu → jibu maswali 6 → onyesha outcome:
   EMERGENCY (enda sasa/112), URGENT (nafasi foleni + kipaumbele), ROUTINE (book slot),
   au SELF-CARE (miongozo ya nyumbani). Emphasize: **hakuna smartphone e hitaji la internet.**
3. **Smart booking (60s):** routine case inapata slots 3 bora zenye expected wait fupi —
   demand inasukumwa nje ya peak ya 6–9 AM (kama slots za leo zimejaa → kesho).
4. **Dashibodi (90s):** kurasa huru kwenye nav ya juu. **🔴 Foleni:** onyesha foleni hai
   (kila mgonjwa ana ⏱ ETA ya kusubiri), bonyeza "Dharura (Bypass)" — mgonjwa anaruka
   foleni yote (priority 100); kisha "Ita Mgonjwa"; badilisha status kikitini/maliza.
   Onyesha "📋 Uamuzi wa clinician" — feedback loop inayopima usahihi wa triage.
   **📬 Kumbusho:** orodha ya miadi ya masaa 24 + kitufe cha kutuma SMS (dry run inapatikana).
   **📲 USSD upande wa client:** piga triage kutoka app ya mgonjwa (`/app`) au PWA ya
   simu (`/mobile/`): mgonjwa anaonekana kwenye foleni hai mara tu anapomaliza maswali
   (dashibodi iko wazi kando — ona foleni ikijaa mbele ya macho).
5. **Analytics (60s):** tab ya Analytics → Triage — **wait times** (avg/median/p90 —
   metric ya #1), **triage accuracy** (under-triage rate karibu na sifuri; ikizidi 15%
   dashibodi inaonyesha tahadhari ya usalama), triage outcomes, demand curve.
6. **Mwisho (30s):** success metrics kutoka README §6 — zero missed emergencies,
   flatter demand curve, less time lost for patients.

## 5. Tatua matatizo (troubleshooting)

| Tatizo | Suluhisho |
|---|---|
| `/api/v1/facilities` inarudisha 500 "Connection refused :5433" | Docker DB haiwaki → `docker compose -f infra/docker-compose.yml up -d` |
| Slots za leo ni `[]` | Anzisha upya backend (seed inarun kwenye startup) |
| AT callback haifiki | Thibitisha tunnel ipo (`tail -f /tmp/afya_tunnel.log`) na URL iko sahihi kwenye dashi ya AT |
| USSD inarudisha 500 | Angalia `tail -30 /tmp/afya_api.log` |
| Dashboard haitumii API sahihi | Thibitisha `VITE_API_URL` (au default) inaelekeza kwa `http://localhost:8000` |
