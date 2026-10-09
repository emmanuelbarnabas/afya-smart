"""Static frontends — admin dashboard, patient app, na mobile PWA (zinajengwa na `npm run build`).

Admin dashboard (dashboard/dist): inahudumiwa kwenye / na /admin
Patient app (patient/dist):      inahudumiwa kwenye /app
Mobile PWA (mobile/dist):        inahudumiwa kwenye /mobile

Vite ya admin inaandika assets kwa njia ya mzizi (/assets/...);
patient na mobile zina base=/app/ na base=/mobile/ hivyo assets zao ni /app/assets/... na /mobile/assets/...
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

router = APIRouter(include_in_schema=False)

_ROOT = Path(__file__).resolve().parents[4]
_ADMIN_DIST = _ROOT / "dashboard" / "dist"
_PATIENT_DIST = _ROOT / "patient" / "dist"
_MOBILE_DIST = _ROOT / "mobile" / "dist"

_NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}
_IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}

# Mime types zisizogundulika kwenye mifumo yote
_MEDIA_OVERRIDES = {".webmanifest": "application/manifest+json"}


def _serve_asset(dist: Path, asset_path: str):
    """Hudumia dist/<asset_path>; asset_path ni relative kwa dist (mf. assets/x.js)."""
    target = (dist / asset_path).resolve()
    # Zuia path traversal nje ya dist/
    if dist.resolve() not in target.parents and target != dist.resolve():
        return None
    if target.is_file():
        headers = _IMMUTABLE if asset_path.startswith("assets/") else _NO_CACHE
        return FileResponse(target, headers=headers, media_type=_MEDIA_OVERRIDES.get(target.suffix))
    return None


def _serve_index(dist: Path, build_cmd: str = "npm run build"):
    index = dist / "index.html"
    if not index.is_file():
        return HTMLResponse(
            f"<h2>App haijajengwa</h2><p>Run: <code>{build_cmd}</code></p>",
            status_code=404,
        )
    # index.html isiweze ku-cache — rebuild mpya ifike kwenye simu mara moja
    return FileResponse(index, media_type="text/html", headers=_NO_CACHE)


# ---- Admin dashboard (dashboard/dist) ----


@router.get("/", include_in_schema=False)
def dashboard_root():
    return _serve_index(_ADMIN_DIST)


@router.get("/admin", include_in_schema=False)
def dashboard_admin():
    return _serve_index(_ADMIN_DIST)


@router.get("/assets/{asset_path:path}", include_in_schema=False)
def admin_assets_root(asset_path: str):
    # Route inatoa "/assets/" — asset iko dist/assets/<path>
    resp = _serve_asset(_ADMIN_DIST, f"assets/{asset_path}")
    if resp is not None:
        return resp
    return JSONResponse({"detail": "Not found"}, status_code=404)


@router.get("/dashboard", include_in_schema=False)
def dashboard_index():
    return _serve_index(_ADMIN_DIST)


@router.get("/dashboard/{asset_path:path}", include_in_schema=False)
def dashboard_assets(asset_path: str):
    resp = _serve_asset(_ADMIN_DIST, asset_path)
    if resp is not None:
        return resp
    # SPA fallback — rudi index.html
    return _serve_index(_ADMIN_DIST)


# ---- Patient app (patient/dist) ----


@router.get("/app", include_in_schema=False)
def patient_index():
    return _serve_index(_PATIENT_DIST, "cd patient && npm run build")


@router.get("/app/{asset_path:path}", include_in_schema=False)
def patient_assets(asset_path: str):
    resp = _serve_asset(_PATIENT_DIST, asset_path)
    if resp is not None:
        return resp
    # SPA fallback
    return _serve_index(_PATIENT_DIST, "cd patient && npm run build")


# ---- Mobile PWA (mobile/dist) — USSD sim app, inasakinishwa kwenye Home Screen ----


@router.get("/mobile", include_in_schema=False)
def mobile_index_redirect():
    # Redirect kwenda /mobile/ — SW scope ya default (/mobile/) idhibiti page moja kwa moja
    return RedirectResponse(url="/mobile/", status_code=307)


@router.get("/mobile/{asset_path:path}", include_in_schema=False)
def mobile_assets(asset_path: str):
    resp = _serve_asset(_MOBILE_DIST, asset_path)
    if resp is not None:
        return resp
    # SPA fallback
    return _serve_index(_MOBILE_DIST, "cd mobile && npm run build")
