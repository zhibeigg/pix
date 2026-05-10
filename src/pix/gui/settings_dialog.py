"""设置对话框：一站式管理提供商、API key、默认模型、界面语言。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import httpx
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from pix import __version__
from pix.i18n import (
    LANGUAGES,
    add_retranslate_hook,
    get_language,
    set_language,
    tr,
)
from pix.gui.combo_keys import QUALITY_KEYS, QUALITY_VALUES
from pix.settings import (
    PROVIDERS,
    Provider,
    UserSettings,
    get_provider,
    load_settings,
    save_settings,
)


class _ConnectionTester(QThread):
    finished_with = Signal(bool, str)

    def __init__(self, base_url: str, api_key: str, timeout: float = 15.0):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def run(self) -> None:
        url = f"{self.base_url}/v1/models"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Accept": "application/json",
                    },
                )
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    count = len(data.get("data", [])) if isinstance(data, dict) else 0
                    self.finished_with.emit(True, tr("test_ok_with_count", count=count))
                except Exception:
                    self.finished_with.emit(True, tr("test_ok_no_count"))
            else:
                self.finished_with.emit(
                    False,
                    tr("test_failed_http", status=resp.status_code, body=resp.text[:200]),
                )
        except Exception as exc:  # pragma: no cover
            self.finished_with.emit(False, tr("test_failed_exception", error=str(exc)))


_PROVIDER_LABEL_KEYS = {
    "packy": "provider_packy",
    "openai": "provider_openai",
    "custom": "provider_custom",
}
_PROVIDER_DESC_KEYS = {
    "packy": "provider_packy_desc",
    "openai": "provider_openai_desc",
    "custom": "provider_custom_desc",
}


class SettingsDialog(QDialog):
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        env_path: Path = Path(".env"),
        config_path: Path = Path("config.toml"),
    ):
        super().__init__(parent)
        self.resize(560, 600)
        self.env_path = env_path
        self.config_path = config_path

        self._current = load_settings(env_path, config_path)
        self._tester: Optional[_ConnectionTester] = None
        self._saved: bool = False

        self._build_ui()
        self._apply_to_ui(self._current)
        self._retranslate_ui()

        self._unregister_retranslate = add_retranslate_hook(self._retranslate_ui)

    # ---------- UI ----------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)

        self.provider_combo = QComboBox()
        for p in PROVIDERS:
            key = _PROVIDER_LABEL_KEYS.get(p.key, p.key)
            self.provider_combo.addItem(tr(key), p.key)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        self.base_url_edit = QLineEdit()
        self.image_key_edit = QLineEdit()
        self.image_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.vl_key_edit = QLineEdit()
        self.vl_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self.show_keys_chk = QCheckBox()
        self.show_keys_chk.toggled.connect(self._on_toggle_show_keys)

        self.image_model_edit = QLineEdit()
        self.image_size_edit = QLineEdit()
        self.image_quality_combo = QComboBox()
        for v in QUALITY_VALUES:
            self.image_quality_combo.addItem(tr(QUALITY_KEYS[v]), v)

        self.vision_model_edit = QLineEdit()

        self.language_combo = QComboBox()
        for lang in LANGUAGES:
            # 语言下拉以各语言「自身」的 native 名称展示，不随 UI 切换而翻译
            self.language_combo.addItem(lang.label, lang.code)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)

        self._lbl_provider = QLabel()
        self._lbl_base_url = QLabel()
        self._lbl_image_key = QLabel()
        self._lbl_vl_key = QLabel()
        self._lbl_image_model = QLabel()
        self._lbl_image_size = QLabel()
        self._lbl_image_quality = QLabel()
        self._lbl_vision_model = QLabel()
        self._lbl_language = QLabel()
        self._lbl_separator = QLabel()

        form.addRow(self._lbl_provider, self.provider_combo)
        form.addRow(self._lbl_base_url, self.base_url_edit)
        form.addRow(self._lbl_image_key, self.image_key_edit)
        form.addRow(self._lbl_vl_key, self.vl_key_edit)
        form.addRow("", self.show_keys_chk)
        form.addRow(self._lbl_language, self.language_combo)
        form.addRow(self._lbl_separator)
        form.addRow(self._lbl_image_model, self.image_model_edit)
        form.addRow(self._lbl_image_size, self.image_size_edit)
        form.addRow(self._lbl_image_quality, self.image_quality_combo)
        form.addRow(self._lbl_vision_model, self.vision_model_edit)

        layout.addLayout(form)

        self.provider_hint = QLabel()
        self.provider_hint.setWordWrap(True)
        self.provider_hint.setStyleSheet("color:#666;")
        layout.addWidget(self.provider_hint)

        test_row = QHBoxLayout()
        self.test_image_btn = QPushButton()
        self.test_vl_btn = QPushButton()
        self.test_image_btn.clicked.connect(lambda: self._on_test(self.image_key_edit.text()))
        self.test_vl_btn.clicked.connect(
            lambda: self._on_test(self.vl_key_edit.text() or self.image_key_edit.text())
        )
        test_row.addWidget(self.test_image_btn)
        test_row.addWidget(self.test_vl_btn)
        test_row.addStretch(1)
        layout.addLayout(test_row)

        self.test_log = QTextEdit()
        self.test_log.setReadOnly(True)
        self.test_log.setFixedHeight(90)
        layout.addWidget(self.test_log)

        # 关于 / 开发者署名
        self._about_box = QWidget()
        about_lay = QVBoxLayout(self._about_box)
        about_lay.setContentsMargins(0, 8, 0, 0)
        about_lay.setSpacing(2)
        self._about_title = QLabel()
        self._about_title.setStyleSheet("font-weight:600;")
        self._about_app = QLabel()
        self._about_app.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._about_developer = QLabel()
        # 支持富文本 + 外链点击
        self._about_developer.setTextFormat(Qt.TextFormat.RichText)
        self._about_developer.setOpenExternalLinks(True)
        self._about_developer.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self._about_project = QLabel()
        self._about_project.setWordWrap(True)
        self._about_project.setStyleSheet("color:#666;")
        about_lay.addWidget(self._about_title)
        about_lay.addWidget(self._about_app)
        about_lay.addWidget(self._about_developer)
        about_lay.addWidget(self._about_project)
        layout.addWidget(self._about_box)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self._save_btn = self.button_box.button(QDialogButtonBox.StandardButton.Save)
        self._cancel_btn = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self._on_save)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    # ---------- 回填 / 切换 ----------

    def _apply_to_ui(self, s: UserSettings) -> None:
        idx = max(0, self.provider_combo.findData(s.provider_key))
        self.provider_combo.setCurrentIndex(idx)
        self.base_url_edit.setText(s.base_url)
        self.image_key_edit.setText(s.image_api_key)
        self.vl_key_edit.setText(s.vl_api_key)
        self.image_model_edit.setText(s.image_model)
        self.image_size_edit.setText(s.image_size)
        _select_data(self.image_quality_combo, s.image_quality)
        self.vision_model_edit.setText(s.vision_model)
        _select_data(self.language_combo, s.language or get_language())

    def _on_provider_changed(self, index: int) -> None:
        key = self.provider_combo.itemData(index)
        provider = get_provider(str(key) if key else "custom")
        self._update_provider_hint(provider)
        if provider.key == "custom":
            return
        if not self.base_url_edit.text().strip() or _is_known_base_url(self.base_url_edit.text()):
            self.base_url_edit.setText(provider.base_url)
        if not self.image_model_edit.text().strip() or _is_known_model(self.image_model_edit.text()):
            self.image_model_edit.setText(provider.default_image_model)
        if not self.vision_model_edit.text().strip() or _is_known_model(self.vision_model_edit.text()):
            self.vision_model_edit.setText(provider.default_vision_model)

    def _update_provider_hint(self, provider: Provider) -> None:
        key = _PROVIDER_DESC_KEYS.get(provider.key, provider.key)
        self.provider_hint.setText(tr(key))

    def _on_toggle_show_keys(self, shown: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        self.image_key_edit.setEchoMode(mode)
        self.vl_key_edit.setEchoMode(mode)

    def _on_language_changed(self, _index: int) -> None:
        """语言下拉改变 → 即时切换对话框 / 主窗口语言，仅预览。真正持久化要靠保存按钮。"""
        code = self.language_combo.currentData()
        if code:
            set_language(str(code))

    # ---------- 翻译 ----------

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(tr("settings_title"))
        self._lbl_provider.setText(tr("settings_provider"))
        self._lbl_base_url.setText(tr("settings_base_url"))
        self._lbl_image_key.setText(tr("settings_image_key"))
        self._lbl_vl_key.setText(tr("settings_vl_key"))
        self._lbl_image_model.setText(tr("settings_image_model"))
        self._lbl_image_size.setText(tr("settings_image_size"))
        self._lbl_image_quality.setText(tr("settings_image_quality"))
        self._lbl_vision_model.setText(tr("settings_vision_model"))
        self._lbl_language.setText(tr("settings_language"))
        self._lbl_separator.setText(tr("settings_default_models_separator"))

        self.show_keys_chk.setText(tr("settings_show_keys"))
        self.base_url_edit.setPlaceholderText(tr("settings_base_url_placeholder"))
        self.image_key_edit.setPlaceholderText(tr("settings_image_key_placeholder"))
        self.vl_key_edit.setPlaceholderText(tr("settings_vl_key_placeholder"))
        self.test_log.setPlaceholderText(tr("settings_test_log_placeholder"))

        self.test_image_btn.setText(tr("settings_test_image_key"))
        self.test_vl_btn.setText(tr("settings_test_vl_key"))
        if self._save_btn is not None:
            self._save_btn.setText(tr("settings_save"))
        if self._cancel_btn is not None:
            self._cancel_btn.setText(tr("settings_cancel"))

        # provider 下拉文本重刷
        for i in range(self.provider_combo.count()):
            data = self.provider_combo.itemData(i)
            key = _PROVIDER_LABEL_KEYS.get(str(data), str(data))
            self.provider_combo.setItemText(i, tr(key))

        # 质量 combobox 重刷
        for i in range(self.image_quality_combo.count()):
            data = self.image_quality_combo.itemData(i)
            k = QUALITY_KEYS.get(str(data))
            if k:
                self.image_quality_combo.setItemText(i, tr(k))

        # 更新当前提供商描述
        current_provider = get_provider(str(self.provider_combo.currentData() or "custom"))
        self._update_provider_hint(current_provider)

        # 关于块
        self._about_title.setText(tr("about_title"))
        self._about_app.setText(tr("about_app", version=__version__))
        github_link = (
            '<a href="https://github.com/zhibeigg" '
            'style="color:#3b82f6; text-decoration:none;">zhibeigg</a>'
        )
        self._about_developer.setText(
            tr("about_developer", name=tr("about_developer_name"), link=github_link)
        )
        self._about_project.setText(tr("about_project_desc"))

    # ---------- 动作 ----------

    def _current_from_ui(self) -> UserSettings:
        key = self.provider_combo.currentData() or "custom"
        return UserSettings(
            provider_key=str(key),
            base_url=self.base_url_edit.text().strip(),
            image_api_key=self.image_key_edit.text().strip(),
            vl_api_key=self.vl_key_edit.text().strip(),
            image_model=self.image_model_edit.text().strip(),
            image_size=self.image_size_edit.text().strip(),
            image_quality=str(self.image_quality_combo.currentData() or "high"),
            vision_model=self.vision_model_edit.text().strip(),
            language=str(self.language_combo.currentData() or "zh-CN"),
        )

    def _on_test(self, api_key: str) -> None:
        base = self.base_url_edit.text().strip()
        if not base:
            self._log(tr("test_please_fill_url"))
            return
        if not api_key:
            self._log(tr("test_please_fill_key"))
            return
        self._log(tr("test_trying", url=base))
        self.test_image_btn.setEnabled(False)
        self.test_vl_btn.setEnabled(False)
        self._tester = _ConnectionTester(base, api_key)
        self._tester.finished_with.connect(self._on_test_done)
        self._tester.start()

    def _on_test_done(self, ok: bool, msg: str) -> None:
        self.test_image_btn.setEnabled(True)
        self.test_vl_btn.setEnabled(True)
        prefix = tr("test_ok_prefix") if ok else tr("test_fail_prefix")
        self._log(f"{prefix} {msg}")
        if self._tester is not None:
            self._tester.deleteLater()
            self._tester = None

    def _on_save(self) -> None:
        settings = self._current_from_ui()
        errors = _validate(settings)
        if errors:
            QMessageBox.warning(self, tr("dlg_title_settings_incomplete"), "\n".join(errors))
            return
        try:
            result = save_settings(settings, self.env_path, self.config_path)
        except Exception as exc:
            QMessageBox.critical(self, tr("dlg_title_save_failed"), str(exc))
            return
        self._saved = True
        self._log(tr("test_saved_to", env=str(result.env_path), config=str(result.config_path)))
        self.accept()

    def was_saved(self) -> bool:
        return self._saved

    def reject(self) -> None:  # type: ignore[override]
        """取消时恢复为打开对话框前的语言，不保留临时预览。"""
        if self.language_combo.currentData() != self._current.language:
            set_language(self._current.language)
        super().reject()

    def _log(self, line: str) -> None:
        self.test_log.append(line)

    def done(self, result: int) -> None:  # type: ignore[override]
        try:
            self._unregister_retranslate()
        except Exception:
            pass
        super().done(result)


def _validate(s: UserSettings) -> list[str]:
    errs: list[str] = []
    if not s.base_url:
        errs.append(tr("settings_err_base_url"))
    if not s.image_api_key and not s.vl_api_key:
        errs.append(tr("settings_err_no_api_key"))
    if not s.image_model:
        errs.append(tr("settings_err_image_model"))
    if not s.vision_model:
        errs.append(tr("settings_err_vision_model"))
    return errs


def _is_known_base_url(url: str) -> bool:
    u = url.rstrip("/")
    return any(p.base_url and p.base_url.rstrip("/") == u for p in PROVIDERS)


def _is_known_model(name: str) -> bool:
    if not name:
        return False
    for p in PROVIDERS:
        if name in (p.default_image_model, p.default_vision_model):
            return True
    return False


def _select_data(combo: QComboBox, value: str) -> None:
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)
