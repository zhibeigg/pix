"""Pix Web FastAPI 应用。"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pix import __version__
from pix_web.config import WebSettings, load_web_settings
from pix_web.db import init_db, make_engine, make_session_factory
from pix_web.routers import admin, auth, batches, billing, credits, files, jobs, pricing, uploads


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
    app.include_router(uploads.router)
    app.include_router(files.router)
    app.include_router(pricing.router)
    app.include_router(admin.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"ok": "true", "version": __version__}

    return app


app = create_app()


def run_dev() -> None:
    uvicorn.run("pix_web.main:app", host="127.0.0.1", port=8000, reload=True)
