"""回归测试：连接池配置 + meta.json 鲁棒读取/缓存。

对应修复：
- /admin/jobs、/jobs 等接口序列化时海量同步读盘长期持有 DB 连接，
  叠加未配置连接池（默认 5+10）导致 QueuePool 耗尽 → API 卡死/500。
- meta.json 含非法 UTF-8 字节时 read_text 抛 UnicodeDecodeError（ValueError），
  原 except 只捕获 OSError/JSONDecodeError → 单个坏文件让整份列表序列化 500。
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pix_web import db as dbmod
from pix_web import schemas


class MakeEnginePoolTests(unittest.TestCase):
    def test_postgres_url_configures_connection_pool(self) -> None:
        with mock.patch.object(dbmod, "create_engine") as create_engine:
            dbmod.make_engine(
                "postgresql+psycopg://u:p@host/db",
                pool_size=7,
                max_overflow=13,
                pool_timeout=15.0,
                pool_recycle=900,
            )
        _, kwargs = create_engine.call_args
        self.assertEqual(kwargs["pool_size"], 7)
        self.assertEqual(kwargs["max_overflow"], 13)
        self.assertEqual(kwargs["pool_timeout"], 15.0)
        self.assertEqual(kwargs["pool_recycle"], 900)
        self.assertTrue(kwargs["pool_pre_ping"])

    def test_sqlite_url_keeps_check_same_thread_and_no_pool_args(self) -> None:
        with mock.patch.object(dbmod, "create_engine") as create_engine:
            dbmod.make_engine("sqlite:///pix_web.db")
        _, kwargs = create_engine.call_args
        self.assertEqual(kwargs["connect_args"], {"check_same_thread": False})
        self.assertNotIn("pool_size", kwargs)


class LoadMetaJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        schemas._load_meta_json_cached.cache_clear()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _write(self, name: str, data: bytes) -> str:
        path = Path(self.tmpdir.name) / name
        path.write_bytes(data)
        return str(path)

    def test_invalid_utf8_returns_empty_without_raising(self) -> None:
        path = self._write("bad.json", b"\xff\xfe\x00 not valid utf-8")
        self.assertEqual(schemas._load_meta_json(path), {})

    def test_corrupt_json_returns_empty(self) -> None:
        path = self._write("corrupt.json", b"{not json")
        self.assertEqual(schemas._load_meta_json(path), {})

    def test_missing_path_returns_empty(self) -> None:
        self.assertEqual(schemas._load_meta_json(None), {})
        self.assertEqual(schemas._load_meta_json(str(Path(self.tmpdir.name) / "nope.json")), {})

    def test_valid_json_is_read_and_cached(self) -> None:
        path = self._write("meta.json", b'{"sprite": {"rows": 4}}')
        first = schemas._load_meta_json(path)
        _second = schemas._load_meta_json(path)
        self.assertEqual(first["sprite"]["rows"], 4)
        # 第二次读取应命中缓存，而非再次解析磁盘。
        self.assertGreaterEqual(schemas._load_meta_json_cached.cache_info().hits, 1)

    def test_cache_invalidates_when_file_changes(self) -> None:
        path = self._write("meta.json", b'{"v": 1}')
        self.assertEqual(schemas._load_meta_json(path)["v"], 1)
        # 改写内容并推进 mtime，缓存应失效返回新值。
        Path(path).write_bytes(b'{"v": 2}')
        future = os.stat(path).st_mtime + 5
        os.utime(path, (future, future))
        self.assertEqual(schemas._load_meta_json(path)["v"], 2)


if __name__ == "__main__":
    unittest.main()
