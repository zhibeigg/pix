"""Pix Web FastAPI 应用。"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from pix import __version__
from pix_web.config import WebSettings, load_web_settings
from pix_web.db import init_db, make_engine, make_session_factory
from pix_web.rate_limit import limiter, rate_limit_exceeded_handler
from pix_web.referrals import frontend_invite_base_url
from pix_web.release_updates import ReleaseUpdateChecker
from pix_web.routers import admin, admin_shares, admin_updates, announcements, api_keys, auth, batches, billing, characters, credits, external, files, jobs, membership, packs, pricing, providers, referrals, settings as settings_router, shares, uploads
from pix_web.update_agent_client import UpdateAgentClient


def _validate_production_settings(settings: WebSettings) -> None:
    """生产环境（PIX_WEB_ENV=prod）拒绝使用默认/过弱的关键密钥启动；dev 仅告警。"""
    problems: list[str] = []
    if settings.jwt_secret == WebSettings.jwt_secret:
        problems.append("PIX_WEB_JWT_SECRET 仍为默认值")
    elif len(settings.jwt_secret) < 32:
        problems.append("PIX_WEB_JWT_SECRET 长度不足 32 字符")
    if settings.env == "prod" and not settings.session_cookie_secure_enabled():
        problems.append("浏览器会话 Cookie 未启用 Secure")
    if settings.session_cookie_samesite == "none" and not settings.session_cookie_secure_enabled():
        problems.append("SameSite=None 必须同时启用 Secure")
    if not problems:
        return
    detail = "；".join(problems)
    if settings.env == "prod":
        raise RuntimeError(
            f"生产环境启动被拒绝：{detail}。请在 .env.production 中配置强随机密钥后重试。"
        )
    logging.getLogger(__name__).warning("安全配置告警（dev）：%s", detail)


def _security_headers_middleware(app: FastAPI, settings: WebSettings) -> None:
    is_prod = settings.env == "prod"

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if is_prod:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


def create_app(settings: WebSettings | None = None) -> FastAPI:
    settings = settings or load_web_settings()
    _validate_production_settings(settings)
    engine = make_engine(settings.database_url, **settings.engine_pool_kwargs())
    init_db(engine, create_schema=settings.auto_create_db)
    session_factory = make_session_factory(engine)

    app = FastAPI(title="Pix Web API", version=__version__)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_origin_regex=r"^http://(localhost|127\.0\.0\.1|\[::1\]):\d+$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _security_headers_middleware(app, settings)
    app.state.web_settings = settings
    app.state.engine = engine
    app.state.SessionLocal = session_factory
    app.state.release_update_checker = ReleaseUpdateChecker(settings)
    app.state.update_agent_client = UpdateAgentClient(settings)

    app.include_router(auth.router)
    app.include_router(credits.router)
    app.include_router(billing.router)
    app.include_router(membership.router)
    app.include_router(jobs.router)
    app.include_router(shares.router)
    app.include_router(batches.router)
    app.include_router(packs.router)
    app.include_router(characters.router)
    app.include_router(referrals.router)
    app.include_router(uploads.router)
    app.include_router(files.router)
    app.include_router(pricing.router)
    app.include_router(settings_router.router)
    app.include_router(api_keys.router)
    app.include_router(external.router)
    app.include_router(announcements.router)
    app.include_router(admin.router)
    app.include_router(admin_shares.router)
    app.include_router(admin_updates.router)
    app.include_router(providers.router)

    @app.get("/", include_in_schema=False)
    def referral_root_redirect(request: Request):
        aff = (request.query_params.get("aff") or "").strip()
        promo = (request.query_params.get("promo") or "").strip()
        if not aff and not promo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
        active_settings: WebSettings = request.app.state.web_settings
        frontend_base = frontend_invite_base_url(active_settings.frontend_base_url, active_settings.public_base_url)
        params: dict[str, str] = {}
        if aff:
            params["aff"] = aff
        if promo:
            params["promo"] = promo
        return RedirectResponse(f"{frontend_base}/?{urlencode(params)}#auth-panel", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"ok": "true", "version": __version__}

    return app


app = create_app()


def run_dev() -> None:
    uvicorn.run("pix_web.main:app", host="127.0.0.1", port=8000, reload=True)
