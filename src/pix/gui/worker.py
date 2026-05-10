"""后台 Worker：把 pipeline 放到 QThread 里跑，不卡 UI。"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from pix.config import AppConfig
from pix.pipeline import PipelineInput, run_pipeline


class PipelineWorker(QObject):
    progress = Signal(str, dict)
    finished = Signal(object)          # PipelineResult
    failed = Signal(str)

    def __init__(self, cfg: AppConfig, inputs: PipelineInput):
        super().__init__()
        self.cfg = cfg
        self.inputs = inputs

    def run(self) -> None:
        try:
            result = run_pipeline(self.cfg, self.inputs, progress=self._on_progress)
            self.finished.emit(result)
        except BaseException as exc:  # noqa: BLE001 — 捕获所有以保证线程不会悄无声息地崩
            import traceback

            self.failed.emit(f"{exc}\n\n{traceback.format_exc()}")

    def _on_progress(self, step: str, payload: dict) -> None:
        self.progress.emit(step, payload)


class WorkerThread(QThread):
    """承载 PipelineWorker 的线程。

    生命周期约定：
      - 构造时 worker.moveToThread(self)
      - started → worker.run 只在一个地方连接（这里），外部不要再 connect
      - worker.finished / worker.failed → self.quit，保证 event loop 干净退出
      - 调用方拿到 worker.finished 后，再 .quit() + .wait() 收尾（幂等）
    """

    def __init__(self, worker: PipelineWorker):
        super().__init__()
        self.worker = worker
        self.worker.moveToThread(self)
        self.started.connect(self.worker.run)
        self.worker.finished.connect(self.quit)
        self.worker.failed.connect(lambda _msg: self.quit())
