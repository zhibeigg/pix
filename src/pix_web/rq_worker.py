"""Redis/RQ worker 入口。"""

from __future__ import annotations

import argparse
from multiprocessing import Process
import time

from sqlalchemy import select
from pix_web.config import WebSettings, load_web_settings
from pix_web.db import init_db, make_engine, make_session_factory
from pix.sprite_video_bridge import is_waiting_state_due
from pix_web.job_observability import cleanup_timed_out_running_jobs
from pix_web.models import GenerationJob, utcnow
from pix_web.system_settings import load_effective_web_settings
from pix_web.worker import _video_bridge_state_from_params, process_job


def process_job_id(job_id: int) -> int | None:
    """RQ 任务函数：处理指定 pending job。"""
    settings = load_web_settings()
    engine = make_engine(settings.database_url)
    init_db(engine, create_schema=settings.auto_create_db)
    session_factory = make_session_factory(engine)
    with session_factory() as db:
        settings = load_effective_web_settings(db, settings)
        cleanup_timed_out_running_jobs(db, timeout_minutes=settings.running_job_timeout_minutes)
        job = db.scalar(select(GenerationJob).where(GenerationJob.id == job_id))
        if job is None:
            return None
        if job.status == "waiting":
            state = _video_bridge_state_from_params(job.params_json or {})
            if state is None or not is_waiting_state_due(state):
                return None
        elif job.status != "pending":
            return None
        job.status = "running"
        job.started_at = utcnow()
        db.commit()
        db.refresh(job)
        processed = process_job(db, job, settings)
        return processed.id


def load_effective_rq_settings() -> WebSettings:
    settings = load_web_settings()
    engine = make_engine(settings.database_url)
    init_db(engine, create_schema=settings.auto_create_db)
    session_factory = make_session_factory(engine)
    with session_factory() as db:
        return load_effective_web_settings(db, settings)


def run_rq_worker(settings: WebSettings) -> None:
    """运行一个 RQ worker；每个进程独立创建 Redis 连接。"""
    from redis import Redis
    from rq import Queue, SimpleWorker, Worker

    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue(settings.rq_queue_name, connection=redis_conn)
    worker_cls = SimpleWorker if settings.rq_worker_class == "simple" else Worker
    worker = worker_cls([queue], connection=redis_conn)
    worker.work()


def _due_waiting_job_ids(db, limit: int = 100) -> list[int]:
    jobs = list(
        db.scalars(
            select(GenerationJob)
            .where(GenerationJob.status == "waiting")
            .order_by(GenerationJob.created_at.asc())
            .limit(max(1, int(limit)))
        )
    )
    ids: list[int] = []
    for job in jobs:
        state = _video_bridge_state_from_params(job.params_json or {})
        if state is not None and is_waiting_state_due(state):
            ids.append(job.id)
    return ids


def run_timeout_cleanup_loop(settings: WebSettings) -> None:
    """RQ 后端的独立超时清理循环。"""
    from pix_web.queue import enqueue_jobs

    engine = make_engine(settings.database_url)
    init_db(engine, create_schema=settings.auto_create_db)
    session_factory = make_session_factory(engine)
    interval = max(1, int(settings.running_job_cleanup_interval_seconds))
    while True:
        with session_factory() as db:
            effective = load_effective_web_settings(db, settings)
            cleanup_timed_out_running_jobs(db, timeout_minutes=effective.running_job_timeout_minutes)
            due_ids = _due_waiting_job_ids(db)
            if due_ids:
                enqueue_jobs(effective, due_ids)
            interval = max(1, int(effective.running_job_cleanup_interval_seconds))
        time.sleep(interval)


def _terminate_processes(processes: list[Process]) -> None:
    for process in processes:
        if process.is_alive():
            process.terminate()
    for process in processes:
        process.join(timeout=5)


def run_worker_pool(settings: WebSettings) -> None:
    """按 worker_concurrency 在当前容器内启动多个独立 RQ worker 进程。"""
    concurrency = max(1, int(settings.worker_concurrency))
    worker_processes = [
        Process(target=run_rq_worker, args=(settings,), name=f"pix-rq-worker-{index}")
        for index in range(1, concurrency + 1)
    ]
    cleanup_process = Process(target=run_timeout_cleanup_loop, args=(settings,), name="pix-rq-timeout-cleaner")
    processes = [*worker_processes, cleanup_process]
    try:
        for process in processes:
            process.start()
        while any(process.is_alive() for process in worker_processes):
            for process in worker_processes:
                process.join(timeout=0.5)
    except KeyboardInterrupt:
        _terminate_processes(processes)
        raise
    finally:
        _terminate_processes(processes)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Pix Web Redis/RQ worker")
    parser.parse_args(argv)

    settings = load_effective_rq_settings()
    run_worker_pool(settings)


if __name__ == "__main__":  # pragma: no cover
    main()
