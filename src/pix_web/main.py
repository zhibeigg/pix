"""Pix Web FastAPI 应用。"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from pix import __version__
from pix_web.config import WebSettings, load_web_settings
from pix_web.db import init_db, make_engine, make_session_factory
from pix_web.routers import admin, auth, credits, jobs


def create_app(settings: WebSettings | None = None) -> FastAPI:
    settings = settings or load_web_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)

    app = FastAPI(title="Pix Web API", version=__version__)
    app.state.web_settings = settings
    app.state.engine = engine
    app.state.SessionLocal = session_factory

    app.include_router(auth.router)
    app.include_router(credits.router)
    app.include_router(jobs.router)
    app.include_router(admin.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"ok": "true", "version": __version__}

    return app


app = create_app()


def run_dev() -> None:
    uvicorn.run("pix_web.main:app", host="127.0.0.1", port=8000, reload=True)
