"""历史记录查询对话框。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pix.history import HistoryRecord, scan_history
from pix.i18n import tr


class HistoryDialog(QWidget):
    """扫描 outputs 并展示可加载的历史记录。"""

    record_selected = Signal(object)

    def __init__(self, root: str | Path, *, limit: int = 200, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self.root = Path(root)
        self.limit = max(1, int(limit))
        self._records: list[HistoryRecord] = []
        self._selected: HistoryRecord | None = None
        self._build_ui()
        self._retranslate()
        self.status_label.setText(tr("history_loading"))
        QTimer.singleShot(0, self._refresh)

    @property
    def selected_record(self) -> HistoryRecord | None:
        return self._selected

    def _build_ui(self) -> None:
        self.resize(980, 560)
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self._search_label = QLabel()
        self.search_edit = QLineEdit()
        self.search_edit.returnPressed.connect(self._refresh)
        self.refresh_btn = QPushButton()
        self.refresh_btn.clicked.connect(self._refresh)
        top.addWidget(self._search_label)
        top.addWidget(self.search_edit, 1)
        top.addWidget(self.refresh_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 7)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.doubleClicked.connect(self._accept_current)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.status_label = QLabel()
        self.load_btn = QPushButton()
        self.load_btn.clicked.connect(self._accept_current)
        self.open_dir_btn = QPushButton()
        self.open_dir_btn.clicked.connect(self._open_selected_dir)
        self.close_btn = QPushButton()
        self.close_btn.clicked.connect(self.close)
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(self.open_dir_btn)
        bottom.addWidget(self.load_btn)
        bottom.addWidget(self.close_btn)
        layout.addLayout(bottom)

    def _retranslate(self) -> None:
        self.setWindowTitle(tr("history_title"))
        self._search_label.setText(tr("history_search_label"))
        self.search_edit.setPlaceholderText(tr("history_search_placeholder"))
        self.refresh_btn.setText(tr("history_refresh"))
        self.load_btn.setText(tr("history_load"))
        self.open_dir_btn.setText(tr("history_open_dir"))
        self.close_btn.setText(tr("history_close"))
        self.table.setHorizontalHeaderLabels([
            tr("history_col_time"),
            tr("history_col_prompt"),
            tr("history_col_pixel"),
            tr("history_col_colors"),
            tr("history_col_image_model"),
            tr("history_col_vision_model"),
            tr("history_col_dir"),
        ])

    def _refresh(self) -> None:
        self._records = scan_history(self.root, query=self.search_edit.text(), limit=self.limit)
        self.table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            pixel = f"{record.pixel_size[0]}x{record.pixel_size[1]}" if record.pixel_size else "-"
            values = [
                record.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                record.prompt_summary or "-",
                pixel,
                str(record.colors or "-"),
                record.image_model or "-",
                record.vision_model or "-",
                record.run_dir.name,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(str(record.run_dir) if col == 6 else value)
                if col in (2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)
        if self._records:
            self.table.selectRow(0)
            self.status_label.setText(tr("history_count", count=len(self._records)))
        else:
            self.status_label.setText(tr("history_no_records"))

    def _current_record(self) -> HistoryRecord | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._records):
            return None
        return self._records[row]

    def _accept_current(self) -> None:
        record = self._current_record()
        if record is None:
            QMessageBox.information(self, tr("dlg_title_hint"), tr("history_no_records"))
            return
        self._selected = record
        self.close()
        QTimer.singleShot(0, lambda record=record: self.record_selected.emit(record))

    def _open_selected_dir(self) -> None:
        record = self._current_record()
        if record is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(record.run_dir)))
