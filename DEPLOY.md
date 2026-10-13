# Ku-deploy Afya Smart kwenye cloud (Render)

Hali hii inafanya mfumo wote uwe na **URL za umma** — si `localhost` pekee:

| Huduma | Ina nini | URL ya umma |
|---|---|---|
| `afya-api` | FastAPI platform: API, dashboard ya muuguzi, patient app, mobile PWA, **USSD callback** | `https://afya-api-8sr6.onrender.com` |
| `afya-web` | Flask prototype: USSD simulator, fairness report | `https://afya-web-3ymc.onrender.com` |

Faili zilizotengenezwa kwa ajili ya hii: `backend/Dockerfile`, `Dockerfile.web`,
`.dockerignore`, `backend/start.sh`, `render.yaml`.

## Hatua 1 — Push kwenye GitHub

Repo hii tayari ina remote: `git@github.com:emmanuelbarnabas/afya-smart.git`.

```
git add backend/Dockerfile Dockerfile.web .dockerignore backend/start.sh render.yaml requirements.txt DEPLOY.md
git commit -m "Add Docker + Render deploy for both apps"
git push origin main
```

## Hatua 2 — Tengeneza huduma kwenye Render

1. Fungua https://dashboard.render.com → **New +** → **Blueprint**.
2. Weka GitHub repo `emmanuelbarnabas/afya-smart` (Render itahitaji ruhusa ya
   GitHub app — bonyeza **Connect** na fuata hatua).
3. Render atasoma `render.yaml` na kuunda huduma mbili: `afya-api` na `afya-web`.
   Weka kila **Environment Variable** ulizoomba (`AT_USERNAME`, `AT_API_KEY`,
   `AT_PHONE_NUMBER`) — kama hujaweka bado, weka baadaye kwenye Settings ya
   kila service, kisha **Manual Deploy → Clear cache & deploy**.
4. Suburu jenga (~5–10 dakika mara ya kwanza; dashboard zote zinajengwa ndani
   ya image). Kisha angalia:
   - `https://afya-api-8sr6.onrender.com/api/v1/health`
   - `https://afya-web-3ymc.onrender.com/health`

## Hatua 3 — Callback ya Africa's Talking

1. Fungua https://account.africastalking.com → **Sandbox** → **USSD**.
2. **Callback URL** weka: `https://afya-api-8sr6.onrender.com/api/v1/ussd`
3. Servicing code: `*384#` (au code uliyopewa na AT sandbox).
4. Piga `*384#` kwenye simu ya sandbox na ufuate mfululizo.

## Kumbuka muhimu

- **Free tier** ya Render inazima service baada ya dakika 15 bila matumizi;
   pale mtu anapofungua URL inachukua ~1 dakika kurudi. Kwa demo ya hafla,
   bonyeza **Manual Deploy** kabla au tumia paid instance.
- **Data**: kwenye free tier SQLite iko ndani ya container — data huwekwa upya
   kila deploy mpya. Kwa data ya kudumu: ongeza **disk** kwenye Settings ya
   `afya-api` (mountPath `/app/backend/data`) na badilisha `DATABASE_URL`
   kuwa `sqlite:///./data/afyasmart.db`. Mbora zaidi: tumia PostgreSQL ya
   Render (`External Database` → naa `DATABASE_URL` = `postgresql://...`).
   Ukitumia PostgreSQL unaweza kuongeza `--workers` kwenye `backend/start.sh`.
- **ML model**: `ml/models/triage_model.pkl` iko ndani ya image; kama model
   haifanyi kazi API inarudi kwenye rules engine (ETAT/IMCI) — demo haikati.
- **SMS**: `backend/app/services/notify.py` hutuma SMS halisi kupitia AT
   credentials. Kwa demo weka `AT_USERNAME=sandbox` ili SMS zisikate credits.
- **Prototype** (`afya-web`) ni ya kuonyesha tu — callback halisi ya AT lazima
   iende kwenye `afya-api` (`/api/v1/ussd`).

## Uthibitisho (baada ya deploy)

```
API health      : curl https://afya-api-8sr6.onrender.com/api/v1/health
USSD callback   : curl -X POST https://afya-api-8sr6.onrender.com/api/v1/ussd \
                  -d "phoneNumber=+255712345678" -d "text="
Dashboard       : fungua https://afya-api-8sr6.onrender.com/
Prototype health: curl https://afya-web-3ymc.onrender.com/health
```
