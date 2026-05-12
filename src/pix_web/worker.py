"""串行任务 worker。"""

from __future__ import annotations

import argparse
import time
import traceback

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from pix_web.config import WebSettings, load_web_settings
from pix_web.credits import consume_reserved, refund_reserved
from pix_web.db import init_db, make_engine, make_session_factory
from pix_web.models import GenerationJob, GenerationOutput, utcnow
from pix_web.pipeline_adapter import run_job_pipeline
from pix_web.system_settings import load_managed_pix_config


def claim_next_job(db: Session) -> GenerationJob | None:
    job = db.scalar(
        select(GenerationJob)
        .where(GenerationJob.status == "pending")
        .order_by(GenerationJob.queue_priority.desc(), GenerationJob.created_at.asc())
        .limit(1)
    )
    if job is None:
        return None
    job.status = "running"
    job.started_at = utcnow()
    db.commit()
    db.refresh(job)
    return job


def process_job(db: Session, job: GenerationJob, settings: WebSettings) -> GenerationJob:
    try:
        cfg = load_managed_pix_config(db, settings)
        result = run_job_pipeline(job, settings, cfg=cfg)
        output = GenerationOutput(
            job_id=job.id,
            run_dir=str(result.run_dir),
            source_path=str(result.source_path),
            pixelized_path=str(result.pixel_path),
            preview_path=str(result.preview_path) if result.preview_path else None,
            analysis_json_path=str(result.analysis_path) if result.analysis_path else None,
            meta_json_path=str(result.meta_path),
        )
        db.add(output)
        job.status = "succeeded"
        job.finished_at = utcnow()
        consume_reserved(db, job)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — worker 必须捕获失败并退款
        db.rollback()
        job = db.get(GenerationJob, job.id)
        if job is None:
            raise
        job.status = "failed"
        job.error_message = f"{exc}\n\n{traceback.format_exc()}"[:8000]
        job.finished_at = utcnow()
        refund_reserved(db, job)
        db.commit()
    return db.scalar(
        select(GenerationJob)
        .options(selectinload(GenerationJob.outputs))
        .where(GenerationJob.id == job.id)
    ) or job


def process_next_job(session_factory: sessionmaker[Session], settings: WebSettings) -> GenerationJob | None:
    with session_factory() as db:
        job = claim_next_job(db)
        if job is None:
            return None
        return process_job(db, job, settings)


def run_loop(session_factory: sessionmaker[Session], settings: WebSettings, *, once: bool = False) -> None:
    while True:
        job = process_next_job(session_factory, settings)
        if once:
            return
        if job is None:
            time.sleep(settings.poll_interval_seconds)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pix Web 串行任务 worker")
    parser.add_argument("--once", action="store_true", help="只处理一个 pending job 后退出")
    args = parser.parse_args(argv)

    settings = load_web_settings()
    engine = make_engine(settings.database_url)
    init_db(engine, create_schema=settings.auto_create_db)
    session_factory = make_session_factory(engine)
    run_loop(session_factory, settings, once=args.once)


if __name__ == "__main__":  # pragma: no cover
    main()
