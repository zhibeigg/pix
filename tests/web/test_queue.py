from __future__ import annotations

from types import SimpleNamespace

from PIL import Image

from pix_web.config import WebSettings
from pix_web.db import init_db, make_engine, make_session_factory
from pix_web.jobs import create_job
from pix_web.queue import enqueue_job
from pix_web.rq_worker import process_job_id
from pix_web.schemas import JobCreateRequest
from pix_web.security import hash_password
from pix_web.credits import adjust_credits
from pix_web.models import User


def _settings(tmp_path) -> WebSettings:
    return WebSettings(database_url=f"sqlite:///{tmp_path / 'queue.db'}", jwt_secret="secret", storage_root=tmp_path / "storage")


def test_enqueue_job_database_backend_is_noop(tmp_path) -> None:
    settings = _settings(tmp_path)
    assert enqueue_job(settings, 123) is False


def test_rq_process_job_id_processes_pending_job(tmp_path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    engine = make_engine(settings.database_url)
    init_db(engine)
    session_factory = make_session_factory(engine)
    with session_factory() as db:
        user = User(email="queue@example.com", password_hash=hash_password("password123"), display_name="Queue")
        db.add(user)
        db.flush()
        adjust_credits(db, user, 20)
        job = create_job(db, user, JobCreateRequest(job_type="text_to_image", prompt="pixel cat"))
        job_id = job.id
        db.commit()

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source = run_dir / "01_source.png"
    pixel = run_dir / "03_pixelized.png"
    meta = run_dir / "meta.json"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    Image.new("RGBA", (4, 4), (0, 255, 0, 255)).save(pixel)
    meta.write_text("{}", encoding="utf-8")

    def fake_settings():
        return settings

    def fake_run(_job, _settings, *, cfg=None):
        return SimpleNamespace(
            run_dir=run_dir,
            source_path=source,
            pixel_path=pixel,
            preview_path=None,
            analysis_path=None,
            meta_path=meta,
        )

    monkeypatch.setattr("pix_web.rq_worker.load_web_settings", fake_settings)
    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fake_run)

    assert process_job_id(job_id) == job_id
    assert process_job_id(job_id) is None

    with session_factory() as db:
        processed = db.get(type(job), job_id)
        assert processed is not None
        assert processed.status == "succeeded"
