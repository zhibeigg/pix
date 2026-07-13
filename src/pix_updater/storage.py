from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pix_updater.models import PersistedState


def _atomic_write(path: Path, data: bytes, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


class StateStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.state_file = state_dir / "state.json"
        self.last_good_dir = state_dir / "last-known-good"
        self.previous_good_dir = state_dir / "previous-known-good"

    async def initialize(self) -> None:
        await asyncio.to_thread(self.state_dir.mkdir, parents=True, exist_ok=True)

    async def load(self) -> PersistedState:
        def read() -> PersistedState:
            if not self.state_file.exists():
                return PersistedState()
            return PersistedState.model_validate_json(self.state_file.read_text(encoding="utf-8"))

        return await asyncio.to_thread(read)

    async def save(self, state: PersistedState) -> None:
        data = state.model_dump_json(indent=2).encode("utf-8") + b"\n"
        await asyncio.to_thread(_atomic_write, self.state_file, data)

    async def write_bytes(self, path: Path, data: bytes, mode: int = 0o600) -> None:
        await asyncio.to_thread(_atomic_write, path, data, mode)

    async def read_bytes(self, path: Path) -> bytes:
        return await asyncio.to_thread(path.read_bytes)

    async def snapshot_good(self, release_env: bytes, manifest: bytes) -> None:
        def rotate() -> None:
            self.last_good_dir.mkdir(parents=True, exist_ok=True)
            self.previous_good_dir.mkdir(parents=True, exist_ok=True)
            for name in ("release.env", "manifest.json"):
                current = self.last_good_dir / name
                if current.exists():
                    _atomic_write(self.previous_good_dir / name, current.read_bytes())
            _atomic_write(self.last_good_dir / "release.env", release_env)
            _atomic_write(self.last_good_dir / "manifest.json", manifest)

        await asyncio.to_thread(rotate)

    async def has_previous_good(self) -> bool:
        env_path = self.previous_good_dir / "release.env"
        manifest_path = self.previous_good_dir / "manifest.json"
        return await asyncio.to_thread(lambda: env_path.exists() and manifest_path.exists())

    async def previous_good(self) -> tuple[bytes, bytes]:
        env_path = self.previous_good_dir / "release.env"
        manifest_path = self.previous_good_dir / "manifest.json"
        if not await self.has_previous_good():
            raise RuntimeError("no previous known-good release is available")
        return await asyncio.gather(self.read_bytes(env_path), self.read_bytes(manifest_path))

    async def prune(self, directory: Path, pattern: str, keep: int) -> None:
        def remove_old() -> None:
            directory.mkdir(parents=True, exist_ok=True)
            files = sorted(directory.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
            for path in files[keep:]:
                if path.is_file():
                    path.unlink(missing_ok=True)

        await asyncio.to_thread(remove_old)

    async def append_json_log(self, log_dir: Path, operation_id: str, payload: dict[str, Any]) -> None:
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n"

        def append() -> None:
            log_dir.mkdir(parents=True, exist_ok=True)
            path = log_dir / f"{operation_id}.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)

        await asyncio.to_thread(append)
