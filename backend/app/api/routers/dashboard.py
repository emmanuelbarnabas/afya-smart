"""Static dashboard ya frontend — imetengenezwa na `npm run build` (dist/).

Vite inaandika assets kwa njia kamili ya mzizi (/assets/...), kwa hiyo tunahudumia:
  GET /                → index.html
  GET /assets/{path}   → dist/assets/* (immutable — zina hash kwenye jina)
  GET /dashboard       → index.html (njia mbadala, compatibility)
  GET /dashboard/{path}→ assets au index.html (SPA fallback)
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

router = APIRouter(include_in_schema=False)

_DIST = Path(__file__).resolve().parents[4] / "dashboard" / "dist"

_NO_CACHE = {"Cache-Control": "no-cache, must-revalidate"}
_IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}


def _serve_asset(asset_path: str):
    target = (_DIST / asset_path).resolve()
    # Zuia path traversal nje ya dist/
    if _DIST.resolve() not in target.parents and target != _DIST.resolve():
        return JSONResponse({"detail": "Not found"}, status_code=404)
    if target.is_file():
        headers = _IMMUTABLE if asset_path.startswith("assets/") else _NO_CACHE
        return FileResponse(target, headers=headers)
    return None


def _serve_index():
    index = _DIST / "index.html"
    if not index.is_file():
        return HTMLResponse(
            "<h2>Dashboard haijajengwa</h2><p>Run: <code>cd dashboard && npm run build</code></p>",
            status_code=404,
        )
    # index.html isiweze ku-cache — rebuild mpya ifike kwenye simu mara moja
    return FileResponse(index, media_type="text/html", headers=_NO_CACHE)


@router.get("/", include_in_schema=False)
def dashboard_root():
    return _serve_index()


@router.get("/assets/{asset_path:path}", include_in_schema=False)
def dashboard_assets_root(asset_path: str):
    # Route inatoa "/assets/" — asset iko dist/assets/<path>
    resp = _serve_asset(f"assets/{asset_path}")
    if resp is not None:
        return resp
    return JSONResponse({"detail": "Not found"}, status_code=404)


@router.get("/dashboard", include_in_schema=False)
def dashboard_index():
    return _serve_index()


@router.get("/dashboard/{asset_path:path}", include_in_schema=False)
def dashboard_assets(asset_path: str):
    resp = _serve_asset(asset_path)
    if resp is not None:
        return resp
    # SPA fallback — rudi index.html
    return _serve_index()
