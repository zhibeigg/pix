"""Redis/RQ worker 入口。"""

from __future__ import annotations

import argparse

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from pix_web.config import load_web_settings
from pix_web.db import init_db, make_engine, make_session_factory
from pix_web.models import GenerationJob, utcnow
from pix_web.worker import process_job


def process_job_id(job_id: int) -> int | None:
    """RQ 任务函数：处理指定 pending job。"""
    settings = load_web_settings()
    engine = make_engine(settings.database_url)
    init_db(engine, create_schema=settings.auto_create_db)
    session_factory = make_session_factory(engine)
    with session_factory() as db:
        job = db.scalar(
            select(GenerationJob)
            .options(selectinload(GenerationJob.outputs))
            .where(GenerationJob.id == job_id)
        )
        if job is None or job.status != "pending":
            return None
        job.status = "running"
        job.started_at = utcnow()
        db.commit()
        db.refresh(job)
        processed = process_job(db, job, settings)
        return processed.id


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pix Web Redis/RQ worker")
    parser.parse_args(argv)

    from redis import Redis
    from rq import Queue, SimpleWorker, Worker

    settings = load_web_settings()
    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue(settings.rq_queue_name, connection=redis_conn)
    worker_cls = SimpleWorker if settings.rq_worker_class == "simple" else Worker
    worker = worker_cls([queue], connection=redis_conn)
    worker.work()


if __name__ == "__main__":  # pragma: no cover
    main()
