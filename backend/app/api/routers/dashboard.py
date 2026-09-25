"""Static dashboard ya frontend — imetengenezwa na `npm run build` (dist/).

Router hii inahudumia dist ya Vite ikiwa ipo (dev convenience na tunnel ya simu);
kama haipo, inarudisha maelezo ya kujenga.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

router = APIRouter(include_in_schema=False)

_DIST = Path(__file__).resolve().parents[4] / "dashboard" / "dist"


@router.get("/dashboard", include_in_schema=False)
def dashboard_index():
    index = _DIST / "index.html"
    if not index.is_file():
        return HTMLResponse(
            "<h2>Dashboard haijajengwa</h2><p>Run: <code>cd dashboard && npm run build</code></p>",
            status_code=404,
        )
    return FileResponse(index, media_type="text/html")


@router.get("/dashboard/{asset_path:path}", include_in_schema=False)
def dashboard_assets(asset_path: str):
    target = (_DIST / asset_path).resolve()
    # Zuia path traversal nje ya dist/
    if _DIST.resolve() not in target.parents:
        return JSONResponse({"detail": "Not found"}, status_code=404)
    if target.is_file():
        return FileResponse(target)
    # SPA fallback — rudi index.html
    index = _DIST / "index.html"
    if index.is_file():
        return FileResponse(index, media_type="text/html")
    return JSONResponse({"detail": "Not found"}, status_code=404)
