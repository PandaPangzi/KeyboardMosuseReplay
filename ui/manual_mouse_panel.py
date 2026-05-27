"""
手动添加事件面板 — 仅在「编辑脚本」模式下生效。

进入编辑模式后，主窗口调用 set_edit_callback(cb) 启用本面板；
每次点击按钮调用 cb(Event) 将对应事件追加到编辑表格中。
退出编辑模式时调用 set_edit_callback(None) 禁用。

「录制鼠标移动」功能：
  1. 点击按钮后显示屏幕顶部悬浮提示
  2. 第一次左键 → 开始记录 mouse_move 事件，提示更新
  3. 第二次左键 → 停止录制，批量追加到编辑表格
"""

import time
import threading

import settings

from PyQt6.QtWidgets import (
    QGroupBox, QGridLayout, QPushButton, QSpinBox,
    QLabel, QHBoxLayout, QVBoxLayout, QLineEdit, QWidget,
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal

from core.event_model import Event, EventType, MouseButton


# ------------------------------------------------------------------
# 跨线程信号（pynput 回调 → Qt 主线程）
# ------------------------------------------------------------------

class _CapSignals(QObject):
    phase_changed = pyqtSignal(int)    # 1 = 录制中
    capture_done  = pyqtSignal(object) # list[Event]


# ------------------------------------------------------------------
# 置顶悬浮提示窗口
# ------------------------------------------------------------------

class _FloatHint(QWidget):
    """录制鼠标轨迹期间，屏幕顶部居中显示的半透明状态提示。"""

    def __init__(self):
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._lbl = QLabel()
        self._lbl.setStyleSheet(
            "background:rgba(20,20,20,240);color:white;border-radius:10px;"
            "padding:14px 28px;font-size:16px;font-weight:bold;"
        )
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._lbl)

    def show_hint(self, text: str):
        self._lbl.setText(text)
        self.adjustSize()
        from PyQt6.QtWidgets import QApplication
        geom = QApplication.primaryScreen().geometry()
        self.move((geom.width() - self.width()) // 2, 80)
        self.show()
        self.raise_()


# ------------------------------------------------------------------
# 主面板
# ------------------------------------------------------------------

class ManualMousePanel(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("手动添加事件（仅编辑模式）", parent)
        self._edit_callback = None
        self._cap_signals   = _CapSignals()
        self._float_hint: _FloatHint | None = None   # 延迟创建
        self._build_ui()
        self._set_enabled(False)

    # ------------------------------------------------------------------
    # 外部接口
    # ------------------------------------------------------------------

    def set_edit_callback(self, callback):
        """callback: Callable[[Event], None] | None"""
        self._edit_callback = callback
        self._set_enabled(callback is not None)

    # ------------------------------------------------------------------
    # UI 构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        tip = QLabel("✏ 编辑脚本时可用：点击按钮将向编辑表格末尾追加事件（间隔默认 60 ms）")
        tip.setStyleSheet("color: gray; font-size: 11px;")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        # ── 鼠标事件 ────────────────────────────────────────────────
        m_grid = QGridLayout()
        m_grid.setSpacing(5)
        self.btn_left_click  = QPushButton("🖱 左键单击")
        self.btn_left_dbl    = QPushButton("🖱 左键双击")
        self.btn_right_click = QPushButton("🖱 右键单击")
        self.btn_mid_click   = QPushButton("🖱 中键单击")
        self.btn_record_move = QPushButton("🖱 录制鼠标移动…")
        self.btn_record_move.setToolTip(
            "启动鼠标轨迹录制：\n"
            "① 在任意位置单击左键 → 开始录制\n"
            "② 再次单击左键 → 结束录制，批量写入编辑表格"
        )
        m_grid.addWidget(self.btn_left_click,  0, 0)
        m_grid.addWidget(self.btn_left_dbl,    0, 1)
        m_grid.addWidget(self.btn_right_click, 1, 0)
        m_grid.addWidget(self.btn_mid_click,   1, 1)
        m_grid.addWidget(self.btn_record_move, 2, 0, 1, 2)
        layout.addLayout(m_grid)

        # ── 插入间隔 ────────────────────────────────────────────────
        delay_row = QHBoxLayout()
        self.spin_gap_ms = QSpinBox()
        self.spin_gap_ms.setRange(1, 60000)
        self.spin_gap_ms.setValue(60)
        self.spin_gap_ms.setFixedWidth(86)
        self.btn_insert_gap = QPushButton("⏱ 插入间隔")
        delay_row.addWidget(self.btn_insert_gap)
        delay_row.addStretch()
        delay_row.addWidget(QLabel("时长"))
        delay_row.addWidget(self.spin_gap_ms)
        delay_row.addWidget(QLabel("ms"))
        layout.addLayout(delay_row)

        # ── 滚轮 ────────────────────────────────────────────────────
        scroll_row = QHBoxLayout()
        self.btn_scroll_up   = QPushButton("↑ 滚轮向上")
        self.btn_scroll_down = QPushButton("↓ 滚轮向下")
        self.spin_scroll = QSpinBox()
        self.spin_scroll.setRange(1, 50)
        self.spin_scroll.setValue(3)
        self.spin_scroll.setFixedWidth(52)
        scroll_row.addWidget(self.btn_scroll_up)
        scroll_row.addWidget(self.btn_scroll_down)
        scroll_row.addStretch()
        scroll_row.addWidget(QLabel("每次"))
        scroll_row.addWidget(self.spin_scroll)
        scroll_row.addWidget(QLabel("格"))
        layout.addLayout(scroll_row)

        # ── 键盘事件 ────────────────────────────────────────────────
        layout.addWidget(QLabel("键盘事件："))
        key_row = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("按键名，如 a / ctrl / f5 / space …")
        self.btn_key_down  = QPushButton("按下")
        self.btn_key_up    = QPushButton("弹起")
        self.btn_key_click = QPushButton("按下后弹起")
        self.btn_key_down.setFixedWidth(54)
        self.btn_key_up.setFixedWidth(54)
        key_row.addWidget(self.key_input, 1)
        key_row.addWidget(self.btn_key_down)
        key_row.addWidget(self.btn_key_up)
        key_row.addWidget(self.btn_key_click)
        layout.addLayout(key_row)

        # ── 组合键 ──────────────────────────────────────────────────
        combo_lbl = QLabel("组合键（最多三键，空白框可留空）：")
        layout.addWidget(combo_lbl)
        combo_grid = QGridLayout()
        combo_grid.setSpacing(4)
        combo_grid.setColumnStretch(0, 1)
        self._combo_inputs: list[list[QLineEdit]] = []
        self._combo_btns: list[QPushButton] = []
        _defaults = ["ctrl+s", "ctrl+c", "ctrl+v", "ctrl+z", "ctrl+a"]
        _saved = settings.load().get("combo_keys", _defaults)
        for _i in range(5):
            _val = _saved[_i] if _i < len(_saved) else _defaults[_i]
            _parts = [p.strip() for p in str(_val).split("+") if p.strip()][:3]
            while len(_parts) < 3:
                _parts.append("")

            _row = QHBoxLayout()
            _row.setContentsMargins(0, 0, 0, 0)
            _row.setSpacing(4)

            _eds: list[QLineEdit] = []
            for _idx in range(3):
                _ed = QLineEdit(_parts[_idx])
                _ed.setPlaceholderText(f"键{_idx + 1}")
                _ed.setFixedWidth(90)
                _ed.editingFinished.connect(self._save_combos)
                _eds.append(_ed)
                _row.addWidget(_ed)
                if _idx < 2:
                    _plus = QLabel("+")
                    _plus.setStyleSheet("color: gray;")
                    _plus.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    _plus.setFixedWidth(12)
                    _row.addWidget(_plus)

            _btn = QPushButton("⌨ 执行")
            _btn.setFixedWidth(64)
            _btn.clicked.connect(lambda _, idx=_i: self._emit_combo(idx))
            _row_wrap = QWidget()
            _row_wrap.setLayout(_row)
            combo_grid.addWidget(_row_wrap, _i, 0)
            combo_grid.addWidget(_btn, _i, 1)
            self._combo_inputs.append(_eds)
            self._combo_btns.append(_btn)
        layout.addLayout(combo_grid)

        # ── 绑定信号 ─────────────────────────────────────────────────
        self.btn_left_click.clicked.connect(
            lambda: self._emit_mouse_click(MouseButton.LEFT, 1)
        )
        self.btn_left_dbl.clicked.connect(
            lambda: self._emit_mouse_click(MouseButton.LEFT, 2)
        )
        self.btn_right_click.clicked.connect(
            lambda: self._emit_mouse_click(MouseButton.RIGHT, 1)
        )
        self.btn_mid_click.clicked.connect(
            lambda: self._emit_mouse_click(MouseButton.MIDDLE, 1)
        )
        self.btn_scroll_up.clicked.connect(lambda: self._emit_scroll(1))
        self.btn_scroll_down.clicked.connect(lambda: self._emit_scroll(-1))
        self.btn_key_down.clicked.connect(
            lambda: self._emit_key(EventType.KEY_DOWN)
        )
        self.btn_key_up.clicked.connect(
            lambda: self._emit_key(EventType.KEY_UP)
        )
        self.btn_key_click.clicked.connect(self._emit_key_click)
        self.btn_record_move.clicked.connect(self._start_move_capture)
        self.btn_insert_gap.clicked.connect(self._emit_delay)

        self._cap_signals.phase_changed.connect(self._on_capture_phase)
        self._cap_signals.capture_done.connect(self._on_capture_done)

    # ------------------------------------------------------------------
    # 批量 enable / disable
    # ------------------------------------------------------------------

    def _set_enabled(self, enabled: bool):
        for w in (
            self.btn_left_click, self.btn_left_dbl,
            self.btn_right_click, self.btn_mid_click,
            self.btn_record_move,
            self.btn_insert_gap,
            self.btn_scroll_up, self.btn_scroll_down,
            self.btn_key_down, self.btn_key_up, self.btn_key_click,
            self.key_input, self.spin_scroll, self.spin_gap_ms,
        ):
            w.setEnabled(enabled)
        # 组合键：输入框始终可编辑（方便预先配置），按钮跟随编辑模式
        for _btn in self._combo_btns:
            _btn.setEnabled(enabled)

    # ------------------------------------------------------------------
    # 鼠标轨迹录制
    # ------------------------------------------------------------------

    def _start_move_capture(self):
        if not self._float_hint:
            self._float_hint = _FloatHint()
        self._float_hint.show_hint("👆 请移动到起始位置，然后单击左键开始录制轨迹")
        # 录制期间禁用所有按钮，防止误触
        self._set_enabled(False)
        threading.Thread(target=self._capture_thread, daemon=True).start()

    def _capture_thread(self):
        """pynput 后台线程：两阶段左键触发的轨迹录制。"""
        from pynput import mouse as _ms
        from pynput.mouse import Button

        phase = 0
        moves: list = []
        start_ts = [0.0]

        def on_move(x: int, y: int):
            if phase == 1:
                ts = round((time.perf_counter() - start_ts[0]) * 1000, 2)
                moves.append(
                    Event(type=EventType.MOUSE_MOVE, timestamp=ts, x=x, y=y)
                )

        def on_click(x: int, y: int, button, pressed: bool):
            nonlocal phase
            if button == Button.left and pressed:
                if phase == 0:
                    phase = 1
                    start_ts[0] = time.perf_counter()
                    self._cap_signals.phase_changed.emit(1)
                elif phase == 1:
                    phase = 2
                    self._cap_signals.capture_done.emit(list(moves))
                    return False   # 停止监听器

        listener = _ms.Listener(on_move=on_move, on_click=on_click)
        listener.daemon = True
        listener.start()
        listener.join()

    def _on_capture_phase(self, phase: int):
        if phase == 1 and self._float_hint:
            self._float_hint.show_hint("🔴 录制中… 再次单击左键结束录制")

    def _on_capture_done(self, moves: list):
        if self._float_hint:
            self._float_hint.hide()
        self._set_enabled(self._edit_callback is not None)
        if not moves:
            print("[ManualMouse] 未录制到任何移动事件")
            return
        # 按相邻事件的真实时间差计算间隔，避免用固定 100ms
        for i, ev in enumerate(moves):
            if i + 1 < len(moves):
                interval_ms = max(1, round(moves[i + 1].timestamp - ev.timestamp))
                interval_str = str(interval_ms)
            else:
                interval_str = "100"
            if self._edit_callback:
                self._edit_callback(ev, interval_str)
        print(f"[ManualMouse] 已添加 {len(moves)} 个鼠标移动事件")

    # ------------------------------------------------------------------
    # 事件发射
    # ------------------------------------------------------------------

    def _emit(self, ev: Event):
        if self._edit_callback:
            self._edit_callback(ev, "60")

    def _emit_delay(self):
        """插入纯间隔，不追加任何真实输入事件。"""
        if not self._edit_callback:
            return
        gap = str(self.spin_gap_ms.value())
        self._edit_callback(Event(type="delay", timestamp=0), gap)

    def _emit_mouse_click(self, button: MouseButton, times: int):
        btn_val = button.value
        for _ in range(times):
            self._emit(Event(type=EventType.MOUSE_DOWN, timestamp=0,
                             button=btn_val, x=0, y=0))
            self._emit(Event(type=EventType.MOUSE_UP,   timestamp=0,
                             button=btn_val, x=0, y=0))

    def _emit_scroll(self, direction: int):
        lines = self.spin_scroll.value()
        for _ in range(lines):
            self._emit(Event(type=EventType.MOUSE_SCROLL, timestamp=0,
                             x=0, y=0, dx=0, dy=direction))

    def _emit_key(self, event_type: str):
        key = self.key_input.text().strip()
        if not key:
            return
        self._emit(Event(type=event_type, timestamp=0, key=key))

    def _emit_key_click(self):
        key = self.key_input.text().strip()
        if not key:
            return
        self._emit(Event(type=EventType.KEY_DOWN, timestamp=0, key=key))
        self._emit(Event(type=EventType.KEY_UP,   timestamp=0, key=key))

    def _save_combos(self):
        """将 5 组自定义组合键保存到 settings.json。"""
        prefs = settings.load()
        combos = []
        for row in self._combo_inputs:
            parts = [ed.text().strip() for ed in row if ed.text().strip()]
            combos.append("+".join(parts))
        prefs["combo_keys"] = combos
        settings.save(prefs)

    def _emit_combo(self, idx: int):
        """向编辑表格追加组合键的 key_down + key_up 事件。"""
        parts = [ed.text().strip() for ed in self._combo_inputs[idx] if ed.text().strip()]
        combo = "+".join(parts)
        if not combo:
            return
        self._emit(Event(type=EventType.KEY_DOWN, timestamp=0, key=combo))
        self._emit(Event(type=EventType.KEY_UP,   timestamp=0, key=combo))
