"""基于 sha256 的简单缓存。"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


class Cache:
    def __init__(self, root: str | Path, enabled: bool = True):
        self.root = Path(root)
        self.enabled = enabled
        if self.enabled:
            self.root.mkdir(parents=True, exist_ok=True)

    def _key(self, material: dict[str, Any]) -> str:
        payload = json.dumps(material, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _path(self, kind: str, key: str, ext: str) -> Path:
        # 前两位做分桶，避免单目录文件过多
        bucket = key[:2]
        return self.root / kind / bucket / f"{key}.{ext}"

    def lookup(self, kind: str, material: dict[str, Any], ext: str) -> Path | None:
        if not self.enabled:
            return None
        key = self._key(material)
        path = self._path(kind, key, ext)
        return path if path.exists() else None

    def store(self, kind: str, material: dict[str, Any], ext: str, data: bytes | str) -> Path | None:
        if not self.enabled:
            return None
        key = self._key(material)
        path = self._path(kind, key, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            path.write_text(data, encoding="utf-8")
        else:
            path.write_bytes(data)
        return path

    def store_copy(self, kind: str, material: dict[str, Any], ext: str, src: Path) -> Path | None:
        if not self.enabled:
            return None
        key = self._key(material)
        path = self._path(kind, key, ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, path)
        return path

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
            if self.enabled:
                self.root.mkdir(parents=True, exist_ok=True)
