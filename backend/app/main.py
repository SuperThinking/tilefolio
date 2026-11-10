"""FastAPI entrypoint. Serves /api/* and the built Svelte SPA from frontend/dist.

Run:  uv run python -m app.main     (binds 127.0.0.1 by default — keep it behind a reverse proxy)
"""
from __future__ import annotations

import asyncio
import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import db, instruments
from .config import settings
from .http import close_client
from .prices import mfnav
from .routes.api import router
from . import security

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("tilefolio")


async def _background_refresh() -> None:
    """Instrument master once a day; AMFI NAVs every TF_MF_NAV_REFRESH seconds."""
    if settings.load_instruments_on_start:
        try:
            await instruments.refresh_all()
        except Exception as e:
            log.warning("instrument refresh failed: %s", e)
    while True:
        await asyncio.sleep(settings.mf_nav_refresh_seconds)
        try:
            await mfnav.refresh_navall()
            await instruments.refresh_all()
        except Exception as e:
            log.warning("periodic refresh failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(_background_refresh())
    yield
    task.cancel()
    await close_client()


db.init_db()  # idempotent; also covers servers/tests that don't run the lifespan hook

app = FastAPI(title="Tilefolio", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(router)

if settings.cors_origins:
    # No cookies cross-origin → allow_credentials stays False. The client-access
    # header is listed so browsers can complete its CORS preflight.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=[
            "Authorization", "Content-Type", "X-CAS-Password",
            "X-Client-UUID", "X-Tilefolio-Client",
        ],
        allow_credentials=False,
        max_age=600,
    )


@app.middleware("http")
async def request_controls(request: Request, call_next):
    """Require an anonymous client UUID and, in production, the public app token."""
    path = request.url.path
    is_api = path == "/api" or path.startswith("/api/")
    started = time.perf_counter()
    response = None
    status_code = 500
    try:
        # Keep the deployment probe public. CORS preflight must reach
        # CORSMiddleware without an application token or UUID.
        if is_api and path != "/api/health" and request.method != "OPTIONS":
            error = security.access_error(request)
            if error:
                status_code, detail = error
                response = JSONResponse({"detail": detail}, status_code=status_code)
            else:
                response = await call_next(request)
                status_code = response.status_code
        else:
            response = await call_next(request)
            status_code = response.status_code
    finally:
        if is_api and path != "/api/health" and request.method != "OPTIONS":
            try:
                db.record_api_request(
                    security.client_uuid(request), request.method, path, status_code,
                    (time.perf_counter() - started) * 1000,
                )
            except Exception as e:  # analytics must never take the API down
                log.warning("metrics recording failed: %s", e)
    return response


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    return resp


@app.get("/internal/metrics", include_in_schema=False)
def internal_metrics(request: Request) -> PlainTextResponse:
    """Prometheus scrape endpoint; deliberately separate from the public API."""
    token = settings.metrics_token
    presented = request.headers.get("x-metrics-token", "")
    if not token or not presented or not secrets.compare_digest(presented, token):
        raise HTTPException(404, "Not found")
    return PlainTextResponse(db.prometheus_metrics(), media_type="text/plain; version=0.0.4")


_index = settings.static_dir / "index.html"
if (settings.static_dir / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(settings.static_dir / "assets")), name="assets")


@app.get("/{path:path}", include_in_schema=False)
async def spa(path: str):
    """SPA fallback (also handles broker OAuth redirects like /connect/kite?request_token=...)."""
    if path.startswith("api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    f = (settings.static_dir / path).resolve()
    if path and f.is_file() and settings.static_dir.resolve() in f.parents:
        return FileResponse(str(f))
    if _index.exists():
        return FileResponse(str(_index))
    return JSONResponse({"detail": "Frontend not built. Run `npm run build` in frontend/."}, status_code=404)


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, proxy_headers=True,
                forwarded_allow_ips="127.0.0.1")


if __name__ == "__main__":
    run()
