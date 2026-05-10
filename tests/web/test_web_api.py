from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from pix_web.config import WebSettings
from pix_web.main import create_app
from pix_web.worker import process_next_job


@pytest.fixture()
def client(tmp_path):
    settings = WebSettings(
        database_url=f"sqlite:///{tmp_path / 'pix_web_test.db'}",
        jwt_secret="test-secret",
        storage_root=tmp_path / "storage",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def _register_and_login(client: TestClient, email: str = "admin@example.com") -> tuple[dict, dict]:
    user = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "display_name": "Admin"},
    ).json()
    token = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"},
    ).json()
    headers = {"Authorization": f"Bearer {token['access_token']}"}
    return user, headers


def test_register_login_and_admin_adjust_credits(client: TestClient) -> None:
    user, headers = _register_and_login(client)

    assert user["role"] == "admin"
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"

    adjusted = client.post(
        f"/admin/users/{user['id']}/adjust-credits",
        headers=headers,
        json={"amount": 50, "note": "seed credits"},
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["amount"] == 50

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 50
    assert balance["reserved_credits"] == 0


def test_create_job_reserves_credits_idempotently(client: TestClient) -> None:
    user, headers = _register_and_login(client)
    client.post(
        f"/admin/users/{user['id']}/adjust-credits",
        headers=headers,
        json={"amount": 50},
    )

    payload = {
        "job_type": "text_to_image",
        "prompt": "pixel cat",
        "client_request_id": "same-click",
        "pixelize": {"output_size": [16, 16], "colors": 4, "preview_scale": 0},
    }
    first = client.post("/jobs", headers=headers, json=payload)
    second = client.post("/jobs", headers=headers, json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["price_credits"] == 20
    assert first.json()["reserved_credits"] == 20

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 30
    assert balance["reserved_credits"] == 20


def test_worker_success_consumes_reserved_credits(client: TestClient, tmp_path, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    created = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "text_to_image", "prompt": "pixel cat"},
    ).json()

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source = run_dir / "01_source.png"
    pixel = run_dir / "03_pixelized.png"
    meta = run_dir / "meta.json"
    Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(source)
    Image.new("RGBA", (4, 4), (0, 255, 0, 255)).save(pixel)
    meta.write_text("{}", encoding="utf-8")

    def fake_run(_job, _settings):
        return SimpleNamespace(
            run_dir=run_dir,
            source_path=source,
            pixel_path=pixel,
            preview_path=None,
            analysis_path=None,
            meta_path=meta,
        )

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fake_run)
    processed = process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)

    assert processed is not None
    assert processed.id == created["id"]
    assert processed.status == "succeeded"
    assert processed.outputs[0].pixelized_path == str(pixel)

    fetched_job = client.get(f"/jobs/{created['id']}", headers=headers).json()
    assert fetched_job["outputs"][0]["pixelized_url"].startswith("/files?path=")
    assert fetched_job["outputs"][0]["source_url"].startswith("/files?path=")

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 30
    assert balance["reserved_credits"] == 0
    assert balance["total_consumed"] == 20

    txs = client.get("/credits/transactions", headers=headers).json()
    assert [tx["type"] for tx in txs][:2] == ["consume", "reserve"]


def test_worker_failure_refunds_reserved_credits(client: TestClient, monkeypatch) -> None:
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    client.post("/jobs", headers=headers, json={"job_type": "text_to_image", "prompt": "pixel cat"})

    def fail(_job, _settings):
        raise RuntimeError("boom")

    monkeypatch.setattr("pix_web.worker.run_job_pipeline", fail)
    processed = process_next_job(client.app.state.SessionLocal, client.app.state.web_settings)

    assert processed is not None
    assert processed.status == "failed"
    assert "boom" in processed.error_message

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 50
    assert balance["reserved_credits"] == 0
    assert balance["total_consumed"] == 0


def test_upload_image_requires_auth_and_stores_file(client: TestClient) -> None:
    image = Image.new("RGB", (4, 4), (20, 30, 40))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()

    unauthorized = client.post(
        "/uploads/image",
        files={"file": ("icon.png", data, "image/png")},
    )
    assert unauthorized.status_code == 401

    _user, headers = _register_and_login(client)
    uploaded = client.post(
        "/uploads/image",
        headers=headers,
        files={"file": ("icon.png", data, "image/png")},
    )
    assert uploaded.status_code == 200
    body = uploaded.json()
    assert body["filename"] == "icon.png"
    assert body["content_type"] == "image/png"
    assert body["size_bytes"] == len(data)
    assert body["url"].startswith("/files?path=")
    assert client.app.state.web_settings.storage_root in Path(body["path"]).parents
    assert Path(body["path"]).exists()

    unauthorized_file = client.get(body["url"])
    assert unauthorized_file.status_code == 401
    fetched = client.get(body["url"], headers=headers)
    assert fetched.status_code == 200
    assert fetched.content == data


def test_file_access_rejects_unsafe_paths(client: TestClient) -> None:
    _user, headers = _register_and_login(client)
    forbidden = client.get("/files", headers=headers, params={"path": ".env"})
    assert forbidden.status_code == 403


def test_uploaded_image_can_create_image_jobs(client: TestClient) -> None:
    image = Image.new("RGB", (4, 4), (40, 50, 60))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    data = buffer.getvalue()
    user, headers = _register_and_login(client)
    client.post(f"/admin/users/{user['id']}/adjust-credits", headers=headers, json={"amount": 50})
    uploaded = client.post(
        "/uploads/image",
        headers=headers,
        files={"file": ("batch.png", data, "image/png")},
    ).json()

    image_to_image = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "image_to_image", "prompt": "make it icy", "input_image_path": uploaded["path"]},
    )
    assert image_to_image.status_code == 200
    assert image_to_image.json()["price_credits"] == 20

    local = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "local_pixelize", "input_image_path": uploaded["path"]},
    )
    assert local.status_code == 200
    assert local.json()["price_credits"] == 0


def test_upload_rejects_non_image_extension(client: TestClient) -> None:
    _user, headers = _register_and_login(client)
    uploaded = client.post(
        "/uploads/image",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert uploaded.status_code == 400


def test_public_pricing_and_repixelize_are_free(client: TestClient, tmp_path) -> None:
    _user, headers = _register_and_login(client)

    pricing = client.get("/pricing")
    assert pricing.status_code == 200
    rules = {rule["key"]: rule for rule in pricing.json()}
    assert rules["text_to_image"]["price_credits"] == 20
    assert rules["repixelize"]["price_credits"] == 0

    image_path = tmp_path / "source.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(image_path)
    created = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "repixelize", "input_image_path": str(image_path)},
    )
    assert created.status_code == 200
    assert created.json()["price_credits"] == 0
    assert created.json()["reserved_credits"] == 0


def test_local_pixelize_job_is_free_and_requires_image(client: TestClient, tmp_path) -> None:
    _user, headers = _register_and_login(client)
    image_path = tmp_path / "input.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(image_path)

    created = client.post(
        "/jobs",
        headers=headers,
        json={"job_type": "local_pixelize", "input_image_path": str(image_path)},
    )
    assert created.status_code == 200
    assert created.json()["price_credits"] == 0
    assert created.json()["reserved_credits"] == 0

    balance = client.get("/credits/balance", headers=headers).json()
    assert balance["available_credits"] == 0
    assert balance["reserved_credits"] == 0
