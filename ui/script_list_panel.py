"""
脚本列表面板
支持：多选、刷新、批量删除、右键菜单、HTML表格预览、脚本编辑模式。
"""

import os
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QAbstractItemView,
    QSplitter, QTextEdit, QMenu, QStackedWidget, QComboBox, QInputDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal

from core.event_model import Event, EventType


# ------------------------------------------------------------------
# 日期格式化
# ------------------------------------------------------------------

def _fmt_datetime(s: str) -> str:
    """'2024-01-15T14:30:45' → '2024-01-15 14:30'"""
    if not s:
        return ""
    return s.replace("T", " ")[:16]


# ------------------------------------------------------------------
# HTML 预览表格
# ------------------------------------------------------------------

_ACT = {
    "key_down": "按下", "key_up": "弹起",
    "mouse_down": "按下", "mouse_up": "弹起",
    "mouse_move": "移动", "mouse_double_click": "双击",
}


def _event_cells(ev: Event) -> tuple[str, str, str]:
    """返回 (动作, 对象, 坐标) 适用于预览表格。"""
    t = ev.type
    if t == "mouse_scroll":
        action = "滚轮↑" if (ev.dy or 0) > 0 else "滚轮↓"
    else:
        action = _ACT.get(t, t)

    if t in ("key_down", "key_up"):
        obj   = f"{ev.key}键" if ev.key else "-"
        coord = "-"
    elif t in ("mouse_down", "mouse_up", "mouse_double_click"):
        obj   = f"{ev.button or '?'}键"
        coord = f"({ev.x}, {ev.y})" if ev.x is not None else "-"
    else:
        obj   = "-"
        coord = f"({ev.x}, {ev.y})" if ev.x is not None else "-"

    return action, obj, coord


def _build_preview_html(script) -> str:
    events = script.events

    # ── 折叠连续 mouse_move 段（只保留首尾两行）────────────────────
    # display 元素格式: {"idx": int, "ev": Event, 可选 "fold_start": int, "fold_end": True}
    display = []
    i = 0
    while i < len(events):
        ev = events[i]
        if ev.type == "mouse_move":
            j = i
            while j + 1 < len(events) and events[j + 1].type == "mouse_move":
                j += 1
            count = j - i + 1
            if count <= 2:
                for k in range(i, j + 1):
                    display.append({"idx": k, "ev": events[k]})
            else:
                display.append({"idx": i, "ev": events[i], "fold_start": count})
                display.append({"idx": j, "ev": events[j], "fold_end": True, "fold_count": count})
            i = j + 1
        else:
            display.append({"idx": i, "ev": ev})
            i += 1

    MAX  = 300
    rows = []
    for di, item in enumerate(display[:MAX]):
        ev      = item["ev"]
        orig_no = item["idx"] + 1
        action, obj, coord = _event_cells(ev)

        # 时间间隔：到下一个展示行
        if di + 1 < len(display):
            delta = round(display[di + 1]["ev"].timestamp - ev.timestamp)
            dt = f"{delta}&nbsp;ms"
        else:
            dt = "-"

        bg = " bgcolor='#f0f4f8'" if di % 2 == 0 else ""

        fold_note = ""
        if "fold_start" in item:
            fold_note = (
                f"&nbsp;<span style='color:#999;font-size:10px'>"
                f"▼&nbsp;轨迹开始，共&nbsp;{item['fold_start']}&nbsp;个点</span>"
            )
        elif item.get("fold_end"):
            fold_note = (
                "&nbsp;<span style='color:#999;font-size:10px'>▲&nbsp;轨迹结束</span>"
            )

        rows.append(
            f"<tr{bg}><td align='center'>{orig_no}</td>"
            f"<td>{action}{fold_note}</td>"
            f"<td>{obj}</td><td>{coord}</td>"
            f"<td align='right'>{dt}</td></tr>"
        )

    if len(display) > MAX:
        rows.append(
            f"<tr><td colspan='5' align='center' style='color:gray'>"
            f"… 仅显示前 {MAX} 行（原始事件 {len(events)} 个）</td></tr>"
        )

    meta = (
        f"<p style='font-size:11px;color:#555;margin:4px 0'>"
        f"脚本：<b>{script.name}</b> &nbsp;|&nbsp; "
        f"共 {script.event_count} 个事件 &nbsp;|&nbsp; "
        f"{script.duration_ms/1000:.2f}s &nbsp;|&nbsp; "
        f"{'含轨迹' if script.record_mouse_move else '不含轨迹'}"
        f"{'&nbsp;|&nbsp;' + str(script.screen_w) + '×' + str(script.screen_h) if script.screen_w else ''}"
        f"</p>"
    )
    header = (
        "<tr style='background:#4a7fc1;color:white;font-weight:bold'>"
        "<th width='36'>#</th><th>动作</th><th>对象</th>"
        "<th>坐标&nbsp;(x,&nbsp;y)</th><th width='90'>间隔时间&nbsp;(Δt)</th></tr>"
    )
    table = (
        "<table border='1' cellspacing='0' cellpadding='4' width='100%' "
        "style='border-collapse:collapse;font-family:Consolas,monospace;font-size:12px;"
        "border-color:#ccc'>"
        f"{header}{''.join(rows)}</table>"
    )
    return meta + table


# ------------------------------------------------------------------
# 编辑模式常量
# ------------------------------------------------------------------

_EDIT_TYPES = [
    "key_down", "key_up",
    "mouse_down", "mouse_up", "mouse_move",
    "mouse_scroll_up", "mouse_scroll_down",
]
_EDIT_LABEL = {
    "key_down":          "按键按下",
    "key_up":            "按键弹起",
    "mouse_down":        "鼠标按下",
    "mouse_up":          "鼠标弹起",
    "mouse_move":        "鼠标移动",
    "mouse_scroll_up":   "滚轮↑",
    "mouse_scroll_down": "滚轮↓",
}
_LABEL_TO_TYPE = {v: k for k, v in _EDIT_LABEL.items()}
_EDIT_COLS = ["#", "类型", "按键/按钮", "X", "Y", "间隔(ms)"]


class ScriptListPanel(QWidget):
    # 进入/退出编辑模式通知主窗口（主窗口控制手动面板）
    sig_edit_started  = pyqtSignal(object)   # arg: add_event callable
    sig_edit_finished = pyqtSignal()

    def __init__(self, script_manager, parent=None):
        super().__init__(parent)
        self.sm = script_manager
        self._edit_script    = None
        self._edit_file_path = None
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # 构建 UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── 上半：脚本表格 ──────────────────────────────────────────
        top = QWidget()
        top_vbox = QVBoxLayout(top)
        top_vbox.setContentsMargins(0, 0, 0, 0)
        top_vbox.setSpacing(4)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["脚本名称", "事件数", "时长(s)", "创建时间"])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 130)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        top_vbox.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.btn_new     = QPushButton("✚  新建脚本")
        self.btn_refresh = QPushButton("刷新")
        self.btn_delete  = QPushButton("删除")
        self.btn_delete.setEnabled(False)
        btn_row.addWidget(self.btn_new)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_refresh)
        btn_row.addWidget(self.btn_delete)
        top_vbox.addLayout(btn_row)
        splitter.addWidget(top)

        # ── 下半：QStackedWidget（预览 / 编辑 切换） ──────────────
        self._stack = QStackedWidget()

        # Page 0: HTML 预览 ─────────────────────────────────────────
        preview_page = QWidget()
        pv_vbox = QVBoxLayout(preview_page)
        pv_vbox.setContentsMargins(0, 0, 0, 0)
        pv_vbox.setSpacing(4)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("选中脚本后在此显示事件预览…")
        pv_vbox.addWidget(self.preview)

        pv_btn_row = QHBoxLayout()
        pv_btn_row.addStretch()
        self.btn_edit_script = QPushButton("✏  编辑脚本")
        self.btn_edit_script.setEnabled(False)
        pv_btn_row.addWidget(self.btn_edit_script)
        pv_vbox.addLayout(pv_btn_row)
        self._stack.addWidget(preview_page)   # index 0

        # Page 1: 事件编辑表格 ──────────────────────────────────────
        edit_page = QWidget()
        ed_vbox = QVBoxLayout(edit_page)
        ed_vbox.setContentsMargins(0, 0, 0, 0)
        ed_vbox.setSpacing(4)

        self.edit_table = QTableWidget(0, 6)
        self.edit_table.setHorizontalHeaderLabels(_EDIT_COLS)
        eh = self.edit_table.horizontalHeader()
        eh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        eh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.edit_table.setColumnWidth(1, 95)
        eh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        eh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.edit_table.setColumnWidth(3, 65)
        eh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.edit_table.setColumnWidth(4, 65)
        eh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.edit_table.setColumnWidth(5, 80)
        self.edit_table.setAlternatingRowColors(True)
        ed_vbox.addWidget(self.edit_table)

        ed_btn_row = QHBoxLayout()
        self.btn_add_row    = QPushButton("+  添加行")
        self.btn_del_row    = QPushButton("-  删除行")
        self.btn_save_edit  = QPushButton("💾  保存")
        self.btn_cancel_edit = QPushButton("✖  取消")
        self.btn_save_edit.setStyleSheet(
            "background:#4caf50;color:white;font-weight:bold;padding:4px 12px;"
        )
        self.btn_cancel_edit.setStyleSheet(
            "background:#f44336;color:white;padding:4px 12px;"
        )
        ed_btn_row.addWidget(self.btn_add_row)
        ed_btn_row.addWidget(self.btn_del_row)
        ed_btn_row.addStretch()
        ed_btn_row.addWidget(self.btn_save_edit)
        ed_btn_row.addWidget(self.btn_cancel_edit)
        ed_vbox.addLayout(ed_btn_row)
        self._stack.addWidget(edit_page)   # index 1

        splitter.addWidget(self._stack)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        # 信号
        self.btn_new.clicked.connect(self._new_script)
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_delete.clicked.connect(self._delete_selected)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)

        self.btn_edit_script.clicked.connect(self._enter_edit_mode)
        self.btn_add_row.clicked.connect(self._add_blank_row)
        self.btn_del_row.clicked.connect(self._del_edit_row)
        self.btn_save_edit.clicked.connect(self._save_edit)
        self.btn_cancel_edit.clicked.connect(self._cancel_edit)

    # ------------------------------------------------------------------
    # 数据操作
    # ------------------------------------------------------------------

    def refresh(self):
        self.table.setRowCount(0)
        for info in self.sm.list_scripts():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(info["name"]))
            self.table.setItem(row, 1, QTableWidgetItem(str(info["event_count"])))
            self.table.setItem(row, 2, QTableWidgetItem(f"{info['duration_ms'] / 1000:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(_fmt_datetime(info.get("created_at", ""))))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, info["file_path"])
        self.btn_delete.setEnabled(False)
        self.btn_edit_script.setEnabled(False)
        self.preview.clear()

    def selected_file_path(self) -> str | None:
        paths = self.selected_file_paths()
        return paths[0] if paths else None

    def selected_file_paths(self) -> list[str]:
        result = []
        for idx in self.table.selectionModel().selectedRows():
            item = self.table.item(idx.row(), 0)
            if item:
                p = item.data(Qt.ItemDataRole.UserRole)
                if p:
                    result.append(p)
        return result

    # ------------------------------------------------------------------
    # 事件预览（HTML 表格）
    # ------------------------------------------------------------------

    def _on_selection(self):
        rows = self.table.selectionModel().selectedRows()
        self.btn_delete.setEnabled(bool(rows))
        single = len(rows) == 1
        self.btn_edit_script.setEnabled(single)
        if single:
            path = self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
            self._update_preview(path)
        else:
            self.preview.clear()
            if len(rows) > 1:
                self.preview.setHtml(
                    f"<p style='color:gray'>已选中 {len(rows)} 个脚本（单选时显示预览）</p>"
                )

    def _update_preview(self, file_path: str):
        script = self.sm.load_by_path(file_path)
        if not script:
            self.preview.setPlainText("无法加载脚本。")
            return
        self.preview.setHtml(_build_preview_html(script))

    # ------------------------------------------------------------------
    # 右键菜单（无终端弹窗）
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        path = self.table.item(self.table.row(item), 0).data(Qt.ItemDataRole.UserRole)
        if not path or not os.path.isfile(path):
            return

        menu = QMenu(self)
        act_file = menu.addAction("📄  打开文件")
        act_dir  = menu.addAction("📁  打开所在目录")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))

        if action == act_file:
            os.startfile(path)
        elif action == act_dir:
            # CREATE_NO_WINDOW 避免弹出控制台窗口
            subprocess.Popen(
                ["explorer.exe", f"/select,{path}"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

    # ------------------------------------------------------------------
    # 删除
    # ------------------------------------------------------------------

    def _delete_selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        names = [self.table.item(r.row(), 0).text() for r in rows]
        msg = (
            f"确定删除脚本「{names[0]}」？"
            if len(names) == 1
            else f"确定删除以下 {len(names)} 个脚本？\n" + "\n".join(f"  · {n}" for n in names)
        )
        if (
            QMessageBox.question(
                self, "确认删除", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            for name in names:
                self.sm.delete(name)
            self.refresh()

    # ------------------------------------------------------------------
    # 新建空脚本
    # ------------------------------------------------------------------

    def _new_script(self):
        from datetime import datetime
        from core.event_model import Script
        name, ok = QInputDialog.getText(self, "新建脚本", "请输入脚本名称：")
        if not ok or not name.strip():
            return
        script = Script(
            name=name.strip(),
            events=[],
            created_at=datetime.now().isoformat(timespec="seconds"),
        )
        # 先保存一个空文件，再进入编辑模式
        path = self.sm.save(script)
        self.refresh()
        # 找到新行并选中，再进入编辑
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == path:
                self.table.selectRow(row)
                break
        self._edit_script    = script
        self._edit_file_path = path
        self._populate_edit_table(script)
        self._stack.setCurrentIndex(1)
        self.table.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.sig_edit_started.emit(self._add_event_from_panel)

    # ------------------------------------------------------------------
    # 编辑模式 — 进入 / 退出
    # ------------------------------------------------------------------

    def _enter_edit_mode(self):
        path = self.selected_file_path()
        if not path:
            return
        script = self.sm.load_by_path(path)
        if not script:
            return
        self._edit_script    = script
        self._edit_file_path = path
        self._populate_edit_table(script)
        self._stack.setCurrentIndex(1)
        # 禁用上半列表，防止编辑中途切换脚本
        self.table.setEnabled(False)
        self.btn_refresh.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.sig_edit_started.emit(self._add_event_from_panel)

    def _cancel_edit(self):
        self._stack.setCurrentIndex(0)
        self.table.setEnabled(True)
        self.btn_refresh.setEnabled(True)
        self._on_selection()
        self._edit_script    = None
        self._edit_file_path = None
        self.sig_edit_finished.emit()

    def _save_edit(self):
        script = self._build_script_from_table()
        if script is None:
            return
        script.name             = self._edit_script.name
        script.created_at       = self._edit_script.created_at
        script.screen_w         = self._edit_script.screen_w
        script.screen_h         = self._edit_script.screen_h
        script.record_mouse_move = self._edit_script.record_mouse_move
        self.sm.save(script)
        self._cancel_edit()
        self.refresh()

    # ------------------------------------------------------------------
    # 编辑模式 — 表格操作
    # ------------------------------------------------------------------

    def _populate_edit_table(self, script):
        self.edit_table.setRowCount(0)
        events = script.events
        for i, ev in enumerate(events):
            if i + 1 < len(events):
                delta = round(events[i + 1].timestamp - ev.timestamp)
                interval_str = str(max(0, delta))
            else:
                interval_str = "-"
            self._insert_edit_row(ev, interval_str)

    def _insert_edit_row(self, ev: Event, interval_str: str = "100"):
        """在编辑表格末尾插入一行。"""
        row = self.edit_table.rowCount()
        self.edit_table.insertRow(row)

        # 列 0: # (只读)
        num_item = QTableWidgetItem(str(row + 1))
        num_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.edit_table.setItem(row, 0, num_item)

        # 列 1: 类型下拉
        combo = QComboBox()
        for k in _EDIT_TYPES:
            combo.addItem(_EDIT_LABEL[k])
        t = ev.type
        if t == "mouse_scroll":
            lookup = "mouse_scroll_up" if (ev.dy or 0) >= 0 else "mouse_scroll_down"
        else:
            lookup = t
        if lookup in _EDIT_LABEL:
            combo.setCurrentText(_EDIT_LABEL[lookup])
        self.edit_table.setCellWidget(row, 1, combo)

        # 列 2: 按键/按钮名
        self.edit_table.setItem(row, 2, QTableWidgetItem(ev.key or ev.button or ""))

        # 列 3: X
        self.edit_table.setItem(row, 3, QTableWidgetItem(
            str(ev.x) if ev.x is not None else "0"
        ))

        # 列 4: Y
        self.edit_table.setItem(row, 4, QTableWidgetItem(
            str(ev.y) if ev.y is not None else "0"
        ))

        # 列 5: 间隔
        self.edit_table.setItem(row, 5, QTableWidgetItem(interval_str))

    def _add_blank_row(self):
        from core.event_model import EventType
        dummy = Event(type=EventType.KEY_DOWN, timestamp=0)
        self._insert_edit_row(dummy, "100")
        self._renumber_edit_rows()

    def _del_edit_row(self):
        rows = sorted(
            {idx.row() for idx in self.edit_table.selectedIndexes()},
            reverse=True,
        )
        for r in rows:
            self.edit_table.removeRow(r)
        self._renumber_edit_rows()

    def _renumber_edit_rows(self):
        for r in range(self.edit_table.rowCount()):
            item = self.edit_table.item(r, 0)
            if item:
                item.setText(str(r + 1))

    def _build_script_from_table(self):
        """将编辑表格内容重建为 Script，验证失败返回 None。"""
        from core.event_model import Script, Event
        from datetime import datetime

        events = []
        ts = 0.0
        for row in range(self.edit_table.rowCount()):
            combo = self.edit_table.cellWidget(row, 1)
            if not combo:
                continue
            label    = combo.currentText()
            etype    = _LABEL_TO_TYPE.get(label, "key_down")
            name_val = (self.edit_table.item(row, 2) or QTableWidgetItem("")).text().strip()
            try:
                x_val = int((self.edit_table.item(row, 3) or QTableWidgetItem("0")).text())
            except ValueError:
                x_val = 0
            try:
                y_val = int((self.edit_table.item(row, 4) or QTableWidgetItem("0")).text())
            except ValueError:
                y_val = 0
            interval_text = (self.edit_table.item(row, 5) or QTableWidgetItem("-")).text().strip()
            interval_ms = 0 if interval_text == "-" else max(0, _parse_int(interval_text, 0))

            kw = {"type": etype, "timestamp": round(ts, 2)}
            if etype in ("key_down", "key_up"):
                kw["key"] = name_val or "unknown"
            elif etype in ("mouse_down", "mouse_up"):
                kw.update(button=name_val or "left", x=x_val, y=y_val)
            elif etype == "mouse_move":
                kw.update(x=x_val, y=y_val)
            elif etype in ("mouse_scroll_up", "mouse_scroll_down"):
                kw["type"] = "mouse_scroll"
                kw.update(x=x_val, y=y_val, dy=1 if etype == "mouse_scroll_up" else -1, dx=0)
            events.append(Event(**kw))
            ts += interval_ms

        return Script(
            name="__tmp__",
            events=events,
            created_at=self._edit_script.created_at if self._edit_script else "",
            duration_ms=round(ts, 2),
        )

    # ------------------------------------------------------------------
    # 从手动面板添加事件（编辑模式回调）
    # ------------------------------------------------------------------

    def _add_event_from_panel(self, ev: Event, interval_str: str = "100"):
        """由 ManualMousePanel 调用，将事件追加到编辑表格末尾。"""
        if self._stack.currentIndex() != 1:
            return
        self._insert_edit_row(ev, interval_str)
        self._renumber_edit_rows()
        self.edit_table.scrollToBottom()


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------

def _parse_int(s: str, default: int = 0) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return default
