"""可选任务队列后端。"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status

from pix_web.config import WebSettings


def enqueue_job(settings: WebSettings, job_id: int) -> bool:
    """根据配置把 job 推入外部队列。database 后端返回 False。"""
    if settings.queue_backend == "database":
        return False
    if settings.queue_backend != "rq":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="未知队列后端")

    try:
        from redis import Redis
        from rq import Queue
    except ImportError as exc:  # pragma: no cover - 依赖安装由 web extra 保证
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="RQ 队列依赖未安装") from exc

    try:
        redis_conn = Redis.from_url(settings.redis_url)
        queue = Queue(settings.rq_queue_name, connection=redis_conn)
        queue.enqueue(
            "pix_web.rq_worker.process_job_id",
            job_id,
            job_timeout=f"{max(1, int(settings.running_job_timeout_minutes))}m",
        )
    except Exception as exc:  # noqa: BLE001 - API 需要把队列不可用转成明确错误
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"队列不可用: {exc}") from exc
    return True


def enqueue_jobs(settings: WebSettings, job_ids: Iterable[int]) -> int:
    count = 0
    for job_id in job_ids:
        if enqueue_job(settings, job_id):
            count += 1
    return count
