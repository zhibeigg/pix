"""并发任务 worker。"""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import time
import traceback

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload, sessionmaker

from pix_web.config import WebSettings, load_web_settings
from pix_web.credits import consume_reserved, refund_reserved
from pix_web.db import init_db, make_engine, make_session_factory
from pix_web.models import GenerationJob, GenerationOutput, utcnow
from pix_web.pipeline_adapter import run_job_pipeline
from pix_web.retention import prune_user_photos
from pix_web.system_settings import load_effective_web_settings, load_managed_pix_config


def claim_next_job(db: Session) -> GenerationJob | None:
    """原子领取一个 pending job，并把它切换为 running。"""
    while True:
        job_id = db.scalar(
            select(GenerationJob.id)
            .where(GenerationJob.status == "pending")
            .order_by(GenerationJob.queue_priority.desc(), GenerationJob.created_at.asc())
            .limit(1)
        )
        if job_id is None:
            return None

        result = db.execute(
            update(GenerationJob)
            .where(GenerationJob.id == job_id, GenerationJob.status == "pending")
            .values(status="running", started_at=utcnow())
        )
        db.commit()
        if result.rowcount == 1:
            job = db.get(GenerationJob, job_id)
            if job is not None:
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
        prune_user_photos(db, job.user_id, settings)
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


def process_claimed_job(
    session_factory: sessionmaker[Session], job_id: int, settings: WebSettings
) -> GenerationJob | None:
    with session_factory() as db:
        job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id))
        if job is None or job.status != "running":
            return None
        return process_job(db, job, settings)


def process_next_job(session_factory: sessionmaker[Session], settings: WebSettings) -> GenerationJob | None:
    with session_factory() as db:
        job = claim_next_job(db)
        if job is None:
            return None
        job_id = job.id
    return process_claimed_job(session_factory, job_id, settings)


def _collect_finished(futures: set[Future[GenerationJob | None]]) -> None:
    for future in futures:
        try:
            future.result()
        except Exception:  # noqa: BLE001 - worker 主循环需要继续处理后续任务
            traceback.print_exc()


def _claim_job_id(session_factory: sessionmaker[Session]) -> int | None:
    with session_factory() as db:
        job = claim_next_job(db)
        return job.id if job is not None else None


def claim_available_job_ids(session_factory: sessionmaker[Session], limit: int) -> list[int]:
    """按并发空位领取待处理任务；超过 limit 的任务保持 pending。"""
    job_ids: list[int] = []
    for _ in range(max(0, limit)):
        job_id = _claim_job_id(session_factory)
        if job_id is None:
            break
        job_ids.append(job_id)
    return job_ids


def run_loop(session_factory: sessionmaker[Session], settings: WebSettings, *, once: bool = False) -> None:
    if once:
        process_next_job(session_factory, settings)
        return

    concurrency = max(1, settings.worker_concurrency)
    in_flight: set[Future[GenerationJob | None]] = set()
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="pix-web-job") as executor:
        while True:
            for job_id in claim_available_job_ids(session_factory, concurrency - len(in_flight)):
                in_flight.add(executor.submit(process_claimed_job, session_factory, job_id, settings))

            if not in_flight:
                time.sleep(settings.poll_interval_seconds)
                continue

            done, in_flight = wait(
                in_flight,
                timeout=settings.poll_interval_seconds,
                return_when=FIRST_COMPLETED,
            )
            _collect_finished(done)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pix Web 并发任务 worker")
    parser.add_argument("--once", action="store_true", help="只处理一个 pending job 后退出")
    args = parser.parse_args(argv)

    settings = load_web_settings()
    engine = make_engine(settings.database_url)
    init_db(engine, create_schema=settings.auto_create_db)
    session_factory = make_session_factory(engine)
    with session_factory() as db:
        settings = load_effective_web_settings(db, settings)
    run_loop(session_factory, settings, once=args.once)


if __name__ == "__main__":  # pragma: no cover
    main()
