"""并发任务 worker。"""

from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import json
import time
import traceback

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload, sessionmaker

from pix.api.image_dispatcher import image_provider_history
from pix_web.config import WebSettings, load_web_settings
from pix_web.character_library import auto_save_character_for_job
from pix_web.credits import consume_reserved, refund_reserved, settle_partial_reserved
from pix_web.db import init_db, make_engine, make_session_factory
from pix_web.job_observability import (
    apply_failure_info,
    build_error_diagnostics,
    classify_failure,
    cleanup_timed_out_running_jobs,
    record_policy_event,
    update_job_diagnostics,
    user_message_for_failure,
)
from pix_web.models import GenerationJob, GenerationOutput, utcnow
from pix.sprite_video_bridge import VideoBridgeWaiting, is_waiting_state_due
from pix_web.pipeline_adapter import run_job_pipeline
from pix_web.retention import prune_user_photos
from pix_web.system_settings import load_effective_web_settings, load_managed_pix_config


def _video_bridge_state_from_params(params: object) -> dict | None:
    if not isinstance(params, dict):
        return None
    sprite = params.get("sprite") if isinstance(params.get("sprite"), dict) else None
    state = sprite.get("video_bridge_state") if isinstance(sprite, dict) else None
    if isinstance(state, dict):
        return state
    legacy_state = params.get("video_bridge_state")
    return legacy_state if isinstance(legacy_state, dict) else None


def _waiting_job_due(job: GenerationJob) -> bool:
    return (state := _video_bridge_state_from_params(job.params_json or {})) is not None and is_waiting_state_due(state)


def _next_claimable_job_id(db: Session) -> tuple[int, str] | None:
    pending_id = db.scalar(
        select(GenerationJob.id)
        .where(GenerationJob.status == "pending")
        .order_by(GenerationJob.queue_priority.desc(), GenerationJob.created_at.asc())
        .limit(1)
    )
    if pending_id is not None:
        return int(pending_id), "pending"
    waiting_jobs = list(
        db.scalars(
            select(GenerationJob)
            .where(GenerationJob.status == "waiting")
            .order_by(GenerationJob.queue_priority.desc(), GenerationJob.created_at.asc())
            .limit(50)
        )
    )
    for job in waiting_jobs:
        if _waiting_job_due(job):
            return job.id, "waiting"
    return None


def claim_next_job(db: Session) -> GenerationJob | None:
    """原子领取一个 pending / 到期 waiting job，并把它切换为 running。"""
    while True:
        claim = _next_claimable_job_id(db)
        if claim is None:
            return None
        job_id, expected_status = claim

        result = db.execute(
            update(GenerationJob)
            .where(GenerationJob.id == job_id, GenerationJob.status == expected_status)
            .values(status="running", started_at=utcnow())
        )
        db.commit()
        if result.rowcount == 1:
            job = db.get(GenerationJob, job_id)
            if job is not None:
                return job


def _provider_from_history(history: object) -> str:
    """从 dispatcher 的 provider 调用历史取最后一次尝试的 provider（成功或失败均适用）。"""
    if isinstance(history, list) and history:
        last = history[-1]
        if isinstance(last, dict):
            return str(last.get("provider") or "")[:32]
    return ""


def _persist_result_diagnostics(job: GenerationJob, result_meta: dict) -> None:
    diagnostics = update_job_diagnostics(job, result_meta)
    result_meta["diagnostics"] = {
        "candidate_failure_count": diagnostics.candidate_failure_count,
        "pipeline_warning_count": diagnostics.pipeline_warning_count,
    }


def _write_meta_with_diagnostics(meta_path: object, result_meta: dict) -> None:
    try:
        meta_path.write_text(json.dumps(result_meta, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        return


def _size_retry_actual_attempts(result_meta: dict) -> int | None:
    """从结果 meta 提取尺寸重试实际尝试次数；未启用 / 缓存命中（无 size_retry 块）返回 None。"""
    image_gen = result_meta.get("image_gen")
    if not isinstance(image_gen, dict):
        return None
    size_retry = image_gen.get("size_retry")
    if not isinstance(size_retry, dict) or not size_retry.get("enabled"):
        return None
    try:
        return max(1, int(size_retry.get("actual_attempts") or 1))
    except (TypeError, ValueError):
        return 1


def _settle_credits_on_success(db: Session, job: GenerationJob, result_meta: dict) -> None:
    """任务成功后结算预扣点数。

    启用尺寸重试时按实际尝试次数结算（实扣 per_attempt × actual_attempts，退还其余）；
    否则（普通任务 / 缓存命中无 size_retry meta）全额确认消费。
    """
    actual_attempts = _size_retry_actual_attempts(result_meta)
    params = job.params_json or {}
    retry_cfg = params.get("size_retry") if isinstance(params, dict) else None
    if actual_attempts is not None and isinstance(retry_cfg, dict):
        try:
            per_attempt = max(0, int(retry_cfg.get("per_attempt") or 0))
        except (TypeError, ValueError):
            per_attempt = 0
        if per_attempt > 0:
            settle_partial_reserved(
                db,
                job,
                consume_amount=per_attempt * actual_attempts,
                note=f"尺寸重试成功，实际尝试 {actual_attempts} 次，单次 {per_attempt} 点",
            )
            return
    consume_reserved(db, job)


def process_job(db: Session, job: GenerationJob, settings: WebSettings) -> GenerationJob:
    try:
        cfg = load_managed_pix_config(db, settings)
        result = run_job_pipeline(job, settings, cfg=cfg)
        db.refresh(job)
        if job.status != "running":
            db.rollback()
            return db.scalar(
                select(GenerationJob)
                .options(selectinload(GenerationJob.outputs))
                .where(GenerationJob.id == job.id)
            ) or job
        _persist_result_diagnostics(job, result.meta)
        _write_meta_with_diagnostics(result.meta_path, result.meta)
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
        job.provider = _provider_from_history(image_provider_history())
        auto_save_character_for_job(db, job, output)
        _settle_credits_on_success(db, job, result.meta)
        db.commit()
        prune_user_photos(db, job.user_id, settings)
        db.commit()
    except VideoBridgeWaiting as waiting:
        db.rollback()
        job = db.get(GenerationJob, job.id)
        if job is None:
            raise
        params = dict(job.params_json or {})
        sprite = dict(params.get("sprite") or {})
        sprite["video_bridge_state"] = waiting.state
        params["sprite"] = sprite
        params.pop("video_bridge_state", None)
        job.params_json = params
        job.status = "waiting"
        job.started_at = None
        job.provider = "ark_video"
        job.error_message = str(waiting)[:8000]
        job.user_error_message = "视频补间任务正在生成，请稍后查看结果"
        db.commit()
    except Exception as exc:  # noqa: BLE001 — worker 必须捕获失败并退款
        db.rollback()
        job = db.get(GenerationJob, job.id)
        if job is None:
            raise
        if job.status != "running":
            db.rollback()
            return job
        failure = classify_failure(exc)
        provider_history = image_provider_history()
        traceback_text = traceback.format_exc()
        job.status = "failed"
        job.error_message = f"{exc}\n\n{traceback_text}"[:8000]
        job.user_error_message = user_message_for_failure(failure)
        job.error_diagnostics_json = build_error_diagnostics(
            exc,
            failure=failure,
            provider_history=provider_history,
            traceback_text=traceback_text,
        )
        job.finished_at = utcnow()
        job.provider = _provider_from_history(provider_history)
        apply_failure_info(job, failure)
        if failure.failure_type == "policy_blocked":
            record_policy_event(
                db,
                user_id=job.user_id,
                job_id=job.id,
                job_type=job.job_type,
                reason=str(exc),
                prompt=job.prompt,
                source="worker",
            )
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
        cleanup_timed_out_running_jobs(db, timeout_minutes=settings.running_job_timeout_minutes)
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
    cleanup_interval = max(1, int(settings.running_job_cleanup_interval_seconds))
    last_cleanup_at = 0.0
    in_flight: set[Future[GenerationJob | None]] = set()
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="pix-web-job") as executor:
        while True:
            now = time.monotonic()
            if now - last_cleanup_at >= cleanup_interval:
                with session_factory() as db:
                    cleanup_timed_out_running_jobs(db, timeout_minutes=settings.running_job_timeout_minutes)
                last_cleanup_at = now

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
    engine = make_engine(settings.database_url, **settings.engine_pool_kwargs())
    init_db(engine, create_schema=settings.auto_create_db)
    session_factory = make_session_factory(engine)
    with session_factory() as db:
        settings = load_effective_web_settings(db, settings)
    run_loop(session_factory, settings, once=args.once)


if __name__ == "__main__":  # pragma: no cover
    main()
