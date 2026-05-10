"""主窗口：输入区 + 参数面板 + 三联预览 + 日志。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pix import __version__
from pix.config import AppConfig, load_config
from pix.i18n import add_retranslate_hook, set_language, tr
from pix.pipeline import PipelineInput, PipelineResult
from pix.pixelize.core import PixelizeParams
from pix.pixelize.presets import list_presets
from pix.gui.combo_keys import (
    DITHER_KEYS,
    DITHER_VALUES,
    PRESET_KEYS,
    QUALITY_KEYS,
    QUALITY_VALUES,
)
from pix.gui.preview_panel import ZoomablePreview
from pix.gui.settings_dialog import SettingsDialog
from pix.gui.worker import PipelineWorker, WorkerThread


# combobox 里的「真值」列表；UI 上展示的是翻译文本。
_QUALITY_VALUES = QUALITY_VALUES
_QUALITY_KEYS = QUALITY_KEYS

_DITHER_VALUES = DITHER_VALUES
_DITHER_KEYS = DITHER_KEYS

_PRESET_KEYS = PRESET_KEYS


class MainWindow(QMainWindow):
    def __init__(self, config_file: Optional[Path] = None):
        super().__init__()
        self.resize(1280, 800)

        self.config_file = config_file
        self.cfg: AppConfig = load_config(config_file=config_file)

        # 初始化界面语言
        set_language(self.cfg.ui.language)

        self._worker: Optional[PipelineWorker] = None
        self._thread: Optional[WorkerThread] = None
        self._last_result: Optional[PipelineResult] = None
        # JSON 视图的占位文案（记录已见过的翻译，切语言时判断是否要覆盖）
        self._known_placeholders: set[str] = set()

        self._build_ui()
        self._retranslate_ui()
        # 首次渲染时把 JSON 视图填上占位文案，避免 placeholderText 在某些 Qt 版本下不显
        self.json_view.setPlainText(tr("json_placeholder"))
        self._known_placeholders.add(tr("json_placeholder"))

        # 注册重翻译钩子
        self._unregister_retranslate = add_retranslate_hook(self._retranslate_ui)

    # ---------- UI ----------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)

        splitter_h = QSplitter(Qt.Orientation.Horizontal)
        splitter_h.addWidget(self._build_left_pane())
        splitter_h.addWidget(self._build_right_pane())
        splitter_h.setStretchFactor(0, 1)
        splitter_h.setStretchFactor(1, 2)

        root.addWidget(splitter_h)
        self.setCentralWidget(central)

        # 菜单 —— 文案留到 retranslate 里
        menu = self.menuBar()
        self._file_menu = menu.addMenu("")
        self._act_open = QAction(self)
        self._act_open.triggered.connect(self._on_browse_image)
        self._file_menu.addAction(self._act_open)
        self._act_open_out = QAction(self)
        self._act_open_out.triggered.connect(self._on_open_run_dir)
        self._file_menu.addAction(self._act_open_out)
        self._file_menu.addSeparator()
        self._act_settings = QAction(self)
        self._act_settings.setShortcut("Ctrl+,")
        self._act_settings.triggered.connect(self._on_open_settings)
        self._file_menu.addAction(self._act_settings)

        status = QStatusBar()
        self.setStatusBar(status)
        self._status = status
        self._refresh_status_bar()
        # 若没有配置过 key，主动引导
        self._maybe_prompt_first_time()

    def _build_left_pane(self) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)

        # 输入
        self._input_box = QGroupBox()
        input_lay = QVBoxLayout(self._input_box)
        self.rb_prompt = QRadioButton()
        self.rb_prompt.setChecked(True)
        self.rb_image = QRadioButton()
        self.rb_prompt.toggled.connect(self._on_input_toggle)
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setFixedHeight(100)
        self.image_path_edit = QLineEdit()
        self._browse_btn = QPushButton()
        self._browse_btn.clicked.connect(self._on_browse_image)
        image_row = QHBoxLayout()
        image_row.addWidget(self.image_path_edit, 1)
        image_row.addWidget(self._browse_btn)
        input_lay.addWidget(self.rb_prompt)
        input_lay.addWidget(self.prompt_edit)
        input_lay.addWidget(self.rb_image)
        input_lay.addLayout(image_row)

        # 生图参数
        self._gen_box = QGroupBox()
        gen_lay = QVBoxLayout(self._gen_box)
        self.image_size_edit = QLineEdit(self.cfg.image_gen.size)
        self.image_quality_combo = QComboBox()
        self._fill_quality_combo()
        _select_data(self.image_quality_combo, self.cfg.image_gen.quality)
        self._lbl_image_size = QLabel()
        self._lbl_image_quality = QLabel()
        gen_lay.addWidget(self._labeled(self._lbl_image_size, self.image_size_edit))
        gen_lay.addWidget(self._labeled(self._lbl_image_quality, self.image_quality_combo))

        # 像素化参数
        self._pix_box = QGroupBox()
        pix_lay = QVBoxLayout(self._pix_box)
        self.pixel_size_edit = QLineEdit(f"{self.cfg.pixelize.output_size[0]}x{self.cfg.pixelize.output_size[1]}")
        self.colors_spin = QSpinBox()
        self.colors_spin.setRange(2, 256)
        self.colors_spin.setValue(self.cfg.pixelize.colors)
        self.dither_combo = QComboBox()
        self._fill_dither_combo()
        _select_data(self.dither_combo, self.cfg.pixelize.dither)
        self.preset_combo = QComboBox()
        self._fill_preset_combo()
        _select_data(self.preset_combo, self.cfg.pixelize.preset)
        self.preview_spin = QSpinBox()
        self.preview_spin.setRange(0, 16)
        self.preview_spin.setValue(self.cfg.pixelize.preview_scale)
        self.sat_spin = QDoubleSpinBox()
        self.sat_spin.setRange(0.0, 2.0)
        self.sat_spin.setSingleStep(0.05)
        self.sat_spin.setValue(self.cfg.pixelize.saturation)
        self.edge_spin = QDoubleSpinBox()
        self.edge_spin.setRange(0.0, 1.0)
        self.edge_spin.setSingleStep(0.05)
        self.edge_spin.setValue(self.cfg.pixelize.edge_enhance)
        self._lbl_pixel_size = QLabel()
        self._lbl_colors = QLabel()
        self._lbl_dither = QLabel()
        self._lbl_preset = QLabel()
        self._lbl_preview_scale = QLabel()
        self._lbl_saturation = QLabel()
        self._lbl_edge = QLabel()
        pix_lay.addWidget(self._labeled(self._lbl_pixel_size, self.pixel_size_edit))
        pix_lay.addWidget(self._labeled(self._lbl_colors, self.colors_spin))
        pix_lay.addWidget(self._labeled(self._lbl_dither, self.dither_combo))
        pix_lay.addWidget(self._labeled(self._lbl_preset, self.preset_combo))
        pix_lay.addWidget(self._labeled(self._lbl_preview_scale, self.preview_spin))
        pix_lay.addWidget(self._labeled(self._lbl_saturation, self.sat_spin))
        pix_lay.addWidget(self._labeled(self._lbl_edge, self.edge_spin))

        # VL / 缓存
        self._opt_box = QGroupBox()
        opt_lay = QVBoxLayout(self._opt_box)
        self.vl_model_edit = QLineEdit(self.cfg.vision.model)
        self.no_vl_chk = QCheckBox()
        self.no_cache_chk = QCheckBox()
        self.refresh_chk = QCheckBox()
        self._lbl_vl_model = QLabel()
        opt_lay.addWidget(self._labeled(self._lbl_vl_model, self.vl_model_edit))
        opt_lay.addWidget(self.no_vl_chk)
        opt_lay.addWidget(self.no_cache_chk)
        opt_lay.addWidget(self.refresh_chk)

        # 运行按钮
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton()
        self.run_btn.clicked.connect(self._on_run)
        self.open_dir_btn = QPushButton()
        self.open_dir_btn.clicked.connect(self._on_open_run_dir)
        self.open_dir_btn.setEnabled(False)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.open_dir_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)

        layout.addWidget(self._input_box)
        layout.addWidget(self._gen_box)
        layout.addWidget(self._pix_box)
        layout.addWidget(self._opt_box)
        layout.addLayout(btn_row)
        layout.addWidget(self.progress_bar)
        layout.addStretch(1)
        return wrap

    def _labeled(self, label: QLabel, widget: QWidget) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 0, 0, 0)
        label.setMinimumWidth(96)
        row.addWidget(label)
        row.addWidget(widget, 1)
        return w

    def _build_right_pane(self) -> QWidget:
        wrap = QWidget()
        lay = QVBoxLayout(wrap)

        self.tabs = QTabWidget()
        self.source_panel = ZoomablePreview(pixel_mode=False)
        self.pixel_panel = ZoomablePreview(pixel_mode=True)
        self.json_view = QTextEdit()
        self.json_view.setReadOnly(True)

        self._hint_labels: list[QLabel] = []
        self.tabs.addTab(self._wrap_with_hint(self.source_panel), "")
        self.tabs.addTab(self.json_view, "")
        self.tabs.addTab(self._wrap_with_hint(self.pixel_panel), "")

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(160)
        self._log_title_label = QLabel()

        lay.addWidget(self.tabs, 1)
        lay.addWidget(self._log_title_label)
        lay.addWidget(self.log_view)
        return wrap

    def _wrap_with_hint(self, preview: ZoomablePreview) -> QWidget:
        """给 ZoomablePreview 套一个垂直容器，顶部加操作提示。"""
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        hint = QLabel()
        hint.setStyleSheet("color:#666; padding:2px 6px;")
        self._hint_labels.append(hint)
        v.addWidget(hint)
        v.addWidget(preview, 1)
        return container

    # ---------- combobox 填充 ----------

    def _fill_quality_combo(self) -> None:
        self.image_quality_combo.clear()
        for v in _QUALITY_VALUES:
            self.image_quality_combo.addItem(tr(_QUALITY_KEYS[v]), v)

    def _fill_dither_combo(self) -> None:
        self.dither_combo.clear()
        for v in _DITHER_VALUES:
            self.dither_combo.addItem(tr(_DITHER_KEYS[v]), v)

    def _fill_preset_combo(self) -> None:
        self.preset_combo.clear()
        for name in list_presets():
            key = _PRESET_KEYS.get(name)
            label = tr(key) if key else name
            self.preset_combo.addItem(label, name)

    # ---------- 翻译 ----------

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(tr("app_title", version=__version__))
        self._file_menu.setTitle(tr("menu_file"))
        self._act_open.setText(tr("menu_open_image"))
        self._act_open_out.setText(tr("menu_open_output_dir"))
        self._act_settings.setText(tr("menu_settings"))

        self._input_box.setTitle(tr("group_input"))
        self._gen_box.setTitle(tr("group_gen_params"))
        self._pix_box.setTitle(tr("group_pixelize"))
        self._opt_box.setTitle(tr("group_vl_cache"))

        self.rb_prompt.setText(tr("radio_prompt"))
        self.rb_image.setText(tr("radio_image"))
        self.prompt_edit.setPlaceholderText(tr("prompt_placeholder"))
        self.image_path_edit.setPlaceholderText(tr("image_path_placeholder"))
        self._browse_btn.setText(tr("btn_browse"))

        self._lbl_image_size.setText(tr("field_image_size"))
        self._lbl_image_quality.setText(tr("field_image_quality"))
        self._lbl_pixel_size.setText(tr("field_pixel_size"))
        self._lbl_colors.setText(tr("field_colors"))
        self._lbl_dither.setText(tr("field_dither"))
        self._lbl_preset.setText(tr("field_preset"))
        self._lbl_preview_scale.setText(tr("field_preview_scale"))
        self._lbl_saturation.setText(tr("field_saturation"))
        self._lbl_edge.setText(tr("field_edge_enhance"))
        self._lbl_vl_model.setText(tr("field_vl_model"))

        self.no_vl_chk.setText(tr("chk_skip_vl"))
        self.no_cache_chk.setText(tr("chk_no_cache"))
        self.refresh_chk.setText(tr("chk_refresh_cache"))
        self.run_btn.setText(tr("btn_run"))
        self.open_dir_btn.setText(tr("btn_open_output_dir"))

        # combobox 重填，保留当前选中
        _refill_combo(self.image_quality_combo, lambda v: tr(_QUALITY_KEYS[v]))
        _refill_combo(self.dither_combo, lambda v: tr(_DITHER_KEYS[v]))
        _refill_combo(self.preset_combo, lambda v: tr(_PRESET_KEYS[v]) if v in _PRESET_KEYS else v)

        # 右侧 tabs
        self.tabs.setTabText(0, tr("tab_source"))
        self.tabs.setTabText(1, tr("tab_json"))
        self.tabs.setTabText(2, tr("tab_pixel"))
        for hint in self._hint_labels:
            hint.setText(tr("preview_hint"))
        self.json_view.setPlaceholderText(tr("json_placeholder"))
        # 若 JSON 视图当前是空的或显示的正是旧的占位文案，刷新为新语言的占位文案
        cur = self.json_view.toPlainText().strip()
        if not cur or cur in self._known_placeholders:
            self.json_view.setPlainText(tr("json_placeholder"))
        self._known_placeholders.add(tr("json_placeholder"))
        self._log_title_label.setText(tr("log_title"))

        self._refresh_status_bar()

    # ---------- 交互 ----------

    def _on_input_toggle(self) -> None:
        use_prompt = self.rb_prompt.isChecked()
        self.prompt_edit.setEnabled(use_prompt)
        self.image_path_edit.setEnabled(not use_prompt)

    def _on_browse_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("menu_open_image"), "", "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self.image_path_edit.setText(path)
            self.rb_image.setChecked(True)
            self.source_panel.show_image(Path(path))

    def _on_run(self) -> None:
        try:
            inputs = self._collect_inputs()
        except ValueError as exc:
            QMessageBox.warning(self, tr("dlg_title_param_error"), str(exc))
            return
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(self, tr("dlg_title_running"), tr("dlg_already_running_body"))
            return
        self._log(tr("log_start"))
        self.run_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log_view.clear()
        # 重置 JSON 视图为占位文案；跑的时候如果生成了分析会被覆盖
        self.json_view.setPlainText(tr("json_placeholder"))
        self.pixel_panel.clear_image()

        self._worker = PipelineWorker(self.cfg, inputs)
        self._thread = WorkerThread(self._worker)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._thread.start()

    def _collect_inputs(self) -> PipelineInput:
        use_prompt = self.rb_prompt.isChecked()
        prompt = self.prompt_edit.toPlainText().strip() if use_prompt else None
        image_path_str = self.image_path_edit.text().strip()
        image_path = Path(image_path_str) if (not use_prompt and image_path_str) else None
        if use_prompt and not prompt:
            raise ValueError(tr("err_prompt_empty"))
        if not use_prompt and (image_path is None or not image_path.exists()):
            raise ValueError(tr("err_invalid_image_path"))

        pixel_w, pixel_h = _parse_size(self.pixel_size_edit.text())
        params = PixelizeParams(
            output_size=(pixel_w, pixel_h),
            colors=self.colors_spin.value(),
            dither=self.dither_combo.currentData() or _DITHER_VALUES[0],  # type: ignore[arg-type]
            preset=self.preset_combo.currentData() or "auto",
            preview_scale=self.preview_spin.value(),
            edge_enhance=self.edge_spin.value(),
            saturation=self.sat_spin.value(),
        )
        return PipelineInput(
            prompt=prompt,
            image_path=image_path,
            image_size=self.image_size_edit.text().strip() or None,
            image_quality=self.image_quality_combo.currentData() or _QUALITY_VALUES[2],
            vl_model=self.vl_model_edit.text().strip() or None,
            skip_vl=self.no_vl_chk.isChecked(),
            pixelize_params=params,
            use_cache=not self.no_cache_chk.isChecked(),
            refresh_cache=self.refresh_chk.isChecked(),
        )

    def _on_progress(self, step: str, payload: dict) -> None:
        self._log(f"[{step}] {payload}")
        path_str = payload.get("path") if isinstance(payload, dict) else None
        if step == "source_ready" and path_str:
            self.source_panel.show_image(Path(path_str))
            self.tabs.setCurrentIndex(0)
        elif step == "analysis_ready" and path_str:
            try:
                self.json_view.setText(Path(path_str).read_text(encoding="utf-8"))
                self.tabs.setCurrentIndex(1)
            except Exception:
                pass
        elif step == "analysis_failed":
            err = payload.get("error") if isinstance(payload, dict) else None
            if err:
                self.json_view.setText(tr("json_analysis_failed", error=str(err)))
                self.tabs.setCurrentIndex(1)
        elif step == "pixelize_ready" and path_str:
            p = Path(path_str)
            self.pixel_panel.show_image(p)
            self.tabs.setCurrentIndex(2)

    def _on_finished(self, result: PipelineResult) -> None:
        self._last_result = result
        self.run_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.open_dir_btn.setEnabled(True)
        # 若本次运行没有产生 JSON 分析，给 JSON 标签一个明确的说明
        cur_json = self.json_view.toPlainText().strip()
        if result.analysis is None and (not cur_json or cur_json in self._known_placeholders):
            reason = (
                tr("chk_skip_vl")
                if result.meta.get("vision", {}).get("skipped")
                else tr("dlg_title_run_failed")
            )
            self.json_view.setPlainText(tr("json_analysis_failed", error=reason))
        self._log(tr("log_run_ok", path=str(result.run_dir)))
        self._log(json.dumps(result.meta, ensure_ascii=False, indent=2))
        self._cleanup_thread()

    def _on_failed(self, error: str) -> None:
        self.run_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self._log(tr("log_run_error", error=error))
        QMessageBox.critical(self, tr("dlg_title_run_failed"), error)
        self._cleanup_thread()

    def _on_open_run_dir(self) -> None:
        if self._last_result is None:
            QMessageBox.information(self, tr("dlg_title_hint"), tr("dlg_no_run_yet"))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_result.run_dir)))

    def _on_open_settings(self) -> None:
        dlg = SettingsDialog(self)
        dlg.exec()
        if dlg.was_saved():
            self._reload_config()
            QMessageBox.information(
                self, tr("dlg_title_settings_saved"), tr("dlg_settings_saved_body")
            )

    def _reload_config(self) -> None:
        """重新加载配置：语言同步切换，且输入框/combobox 在未被用户改动时跟随新默认。"""
        old_vision_model = self.cfg.vision.model
        old_size = self.cfg.image_gen.size
        old_quality = self.cfg.image_gen.quality
        old_language = self.cfg.ui.language
        self.cfg = load_config(config_file=self.config_file)

        # 先切语言，retranslate 钩子会帮我们刷新 UI；同时 combobox 的 currentData 保持稳定
        if self.cfg.ui.language != old_language:
            set_language(self.cfg.ui.language)

        if self.vl_model_edit.text().strip() in ("", old_vision_model):
            self.vl_model_edit.setText(self.cfg.vision.model)
        if self.image_size_edit.text().strip() in ("", old_size):
            self.image_size_edit.setText(self.cfg.image_gen.size)
        if (self.image_quality_combo.currentData() or "") == old_quality:
            _select_data(self.image_quality_combo, self.cfg.image_gen.quality)
        self._refresh_status_bar()

    def _refresh_status_bar(self) -> None:
        has_image_key = bool(self.cfg.api.image_api_key)
        has_vl_key = bool(self.cfg.api.vl_api_key)
        parts = [tr("status_base_url", url=self.cfg.api.base_url)]
        if has_image_key and has_vl_key:
            parts.append(tr("status_both_keys"))
        elif has_image_key:
            parts.append(tr("status_only_image_key"))
        elif has_vl_key:
            parts.append(tr("status_only_vl_key"))
        else:
            parts.append(tr("status_no_key"))
        self._status.showMessage(" · ".join(parts))

    def _maybe_prompt_first_time(self) -> None:
        """首次启动若没有任何 key，弹一次温柔提示。"""
        if self.cfg.api.image_api_key or self.cfg.api.vl_api_key:
            return
        import os as _os
        if _os.environ.get("PIX_SUPPRESS_FIRST_RUN_DIALOG") or _os.environ.get("QT_QPA_PLATFORM") in ("minimal", "offscreen"):
            return
        QMessageBox.information(self, tr("dlg_title_first_run"), tr("dlg_first_run_body"))

    def _cleanup_thread(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            if self._thread.wait(5000):
                self._thread = None
                self._worker = None
            else:
                self._log(tr("log_warn_thread_not_exit"))
        else:
            self._worker = None

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(5000)
        try:
            self._unregister_retranslate()
        except Exception:
            pass
        super().closeEvent(event)

    def _log(self, msg: str) -> None:
        self.log_view.appendPlainText(msg)


def _parse_size(s: str) -> tuple[int, int]:
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except Exception as exc:
        raise ValueError(tr("err_invalid_pixel_size", value=s)) from exc


def _select_data(combo: QComboBox, value: str) -> None:
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)


def _refill_combo(combo: QComboBox, text_fn) -> None:
    """不改数据、不改选中索引，仅刷新每一项的显示文本。"""
    for i in range(combo.count()):
        data = combo.itemData(i)
        try:
            combo.setItemText(i, text_fn(data))
        except Exception:
            pass
