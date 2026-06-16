"""Pix Web FastAPI 应用。"""

from __future__ import annotations

from urllib.parse import urlencode

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from pix import __version__
from pix_web.config import WebSettings, load_web_settings
from pix_web.db import init_db, make_engine, make_session_factory
from pix_web.referrals import frontend_invite_base_url
from pix_web.routers import admin, announcements, auth, batches, billing, credits, files, jobs, packs, pricing, providers, referrals, settings as settings_router, uploads


def create_app(settings: WebSettings | None = None) -> FastAPI:
    settings = settings or load_web_settings()
    engine = make_engine(settings.database_url)
    init_db(engine, create_schema=settings.auto_create_db)
    session_factory = make_session_factory(engine)

    app = FastAPI(title="Pix Web API", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|\[::1\]):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.web_settings = settings
    app.state.engine = engine
    app.state.SessionLocal = session_factory

    app.include_router(auth.router)
    app.include_router(credits.router)
    app.include_router(billing.router)
    app.include_router(jobs.router)
    app.include_router(batches.router)
    app.include_router(packs.router)
    app.include_router(referrals.router)
    app.include_router(uploads.router)
    app.include_router(files.router)
    app.include_router(pricing.router)
    app.include_router(settings_router.router)
    app.include_router(announcements.router)
    app.include_router(admin.router)
    app.include_router(providers.router)

    @app.get("/", include_in_schema=False)
    def referral_root_redirect(request: Request):
        aff = (request.query_params.get("aff") or "").strip()
        if not aff:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        active_settings: WebSettings = request.app.state.web_settings
        frontend_base = frontend_invite_base_url(active_settings.frontend_base_url, active_settings.public_base_url)
        return RedirectResponse(f"{frontend_base}/?{urlencode({'aff': aff})}#auth-panel", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"ok": "true", "version": __version__}

    return app


app = create_app()


def run_dev() -> None:
    uvicorn.run("pix_web.main:app", host="127.0.0.1", port=8000, reload=True)
