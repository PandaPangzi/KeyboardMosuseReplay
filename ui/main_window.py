"""
主窗口
整合录制、回放、脚本管理所有功能。
"""

import sys
import os
import io

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QInputDialog, QMessageBox,
    QGroupBox, QStatusBar, QProgressBar, QSplitter,
    QApplication, QCheckBox, QComboBox, QTextEdit,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont

# 确保根目录在 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.recorder import Recorder
from core.playback import Playback
from core.hotkey_manager import HotkeyManager
from storage.script_manager import ScriptManager
from ui.script_list_panel import ScriptListPanel
from ui.playback_options_panel import PlaybackOptionsPanel
from ui.manual_mouse_panel import ManualMousePanel, _FloatHint
import config
import settings


# ------------------------------------------------------------------
# 跨线程信号桥（后台线程 → Qt 主线程）
# ------------------------------------------------------------------
class _Signals(QObject):
    record_toggle    = pyqtSignal()        # F5 热键
    play_toggle      = pyqtSignal()        # F6 热键
    playback_finish  = pyqtSignal()
    playback_progress = pyqtSignal(int, int)   # current, total
    log_message      = pyqtSignal(str)     # stdout 重定向


# ------------------------------------------------------------------
# stdout 重定向流（线程安全：通过信号转发到主线程）
# ------------------------------------------------------------------
class _LogStream(io.TextIOBase):
    def __init__(self, emit_fn):
        super().__init__()
        self._emit = emit_fn

    def write(self, text: str) -> int:
        text = text.rstrip("\n\r")
        if text:
            self._emit(text)
        return len(text)

    def flush(self):
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KMReasy — 键鼠录制与回放")
        self.setMinimumSize(760, 520)

        self._recorder = Recorder()
        self._playback: Playback | None = None
        self._sm = ScriptManager(config.SCRIPTS_DIR)
        self._signals = _Signals()
        self._record_event_timer = QTimer()
        self._record_event_timer.setInterval(200)
        self._record_event_timer.timeout.connect(self._update_record_count)

        self._build_ui()
        self._connect_signals()
        self._init_hotkeys()
        self._set_state_idle()

        # 倒计时悬浮提示（顶部居中）
        self._app_hint = _FloatHint()
        self._countdown_remaining: int = 0
        self._countdown_action: str = ""       # 'record' | 'play'
        self._pending_play_script = None       # 等待倒计时结束后回放的脚本

        # 加载上次窗口尺寸
        self._load_size_setting()
        # 重定向 stdout 到 UI 日志面板
        self._old_stdout = sys.stdout
        sys.stdout = _LogStream(self._signals.log_message.emit)

    # ------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)

        # ── 顶部控制区 ──────────────────────────────────────────────
        ctrl_group = QGroupBox("控制")
        ctrl_layout = QHBoxLayout(ctrl_group)

        self.btn_record = QPushButton("⏺  开始录制")
        self.btn_record.setFixedHeight(40)
        font = QFont()
        font.setPointSize(11)
        self.btn_record.setFont(font)

        self.btn_play = QPushButton("▶  回放")
        self.btn_play.setFixedHeight(40)
        self.btn_play.setFont(font)

        self.btn_stop_play = QPushButton("⏹  停止回放")
        self.btn_stop_play.setFixedHeight(40)
        self.btn_stop_play.setFont(font)
        self.btn_stop_play.setEnabled(False)

        self.lbl_record_count = QLabel("事件数：0")

        ctrl_layout.addWidget(self.btn_record)
        ctrl_layout.addWidget(self.btn_play)
        ctrl_layout.addWidget(self.btn_stop_play)
        ctrl_layout.addStretch()

        # 鼠标轨迹勾选框 + 当前屏幕分辨率提示
        self.chk_mouse_move = QCheckBox("录制鼠标轨迹")
        self.chk_mouse_move.setChecked(False)
        self.chk_mouse_move.setToolTip(
            "勾选后将连续记录鼠标移动轨迹\n"
            "开始录制时鼠标会自动移到屏幕中心"
        )
        ctrl_layout.addWidget(self.chk_mouse_move)
        ctrl_layout.addSpacing(12)
        self._sw, self._sh = self._detect_screen()
        self.lbl_resolution = QLabel(f"🖥 {self._sw}×{self._sh}")
        self.lbl_resolution.setStyleSheet("color: gray; font-size: 11px;")
        ctrl_layout.addWidget(self.lbl_resolution)
        ctrl_layout.addWidget(self.lbl_record_count)
        root.addWidget(ctrl_group)

        # 热键提示
        hint = QLabel(
            f"热键：{config.RECORD_HOTKEY_DISPLAY} 开始/停止录制    "
            f"{config.PLAY_HOTKEY_DISPLAY} 开始/停止回放"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        root.addWidget(hint)

        # ── 主体分割：左=脚本列表，右=选项 ──────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 脚本列表
        list_group = QGroupBox("脚本列表")
        list_vbox = QVBoxLayout(list_group)
        self.script_list = ScriptListPanel(self._sm)
        list_vbox.addWidget(self.script_list)
        splitter.addWidget(list_group)

        # 右侧面板（垂直 QSplitter：上=回放选项+手动鼠标，下=运行日志）
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # 右上区
        right_top = QWidget()
        right_top_vbox = QVBoxLayout(right_top)
        right_top_vbox.setContentsMargins(0, 0, 0, 0)
        right_top_vbox.setSpacing(6)

        opt_group = QGroupBox("回放选项")
        opt_vbox = QVBoxLayout(opt_group)
        self.playback_opts = PlaybackOptionsPanel()
        opt_vbox.addWidget(self.playback_opts)
        right_top_vbox.addWidget(opt_group)

        self.manual_mouse = ManualMousePanel()
        right_top_vbox.addWidget(self.manual_mouse)
        right_top_vbox.addStretch()
        right_splitter.addWidget(right_top)

        # 右下区：运行日志
        log_group = QGroupBox("运行日志")
        log_vbox = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 11px;"
        )
        self.log_text.document().setMaximumBlockCount(500)
        log_vbox.addWidget(self.log_text)
        right_splitter.addWidget(log_group)

        right_splitter.setStretchFactor(0, 2)
        right_splitter.setStretchFactor(1, 1)
        splitter.addWidget(right_splitter)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter, 1)

        # ── 进度条 ────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        # ── 状态栏 ───────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.lbl_status = QLabel("就绪")
        self.status_bar.addWidget(self.lbl_status)
        # 窗口尺寸选择（右对齐）
        lbl_sz = QLabel("窗口尺寸：")
        lbl_sz.setStyleSheet("color: gray; font-size: 11px;")
        self.combo_size = QComboBox()
        for label, _w, _h in config.UI_SIZES:
            self.combo_size.addItem(label)
        self.combo_size.setFixedWidth(95)
        self.status_bar.addPermanentWidget(lbl_sz)
        self.status_bar.addPermanentWidget(self.combo_size)
    # ------------------------------------------------------------------
    # 信号连接
    # ------------------------------------------------------------------

    def _connect_signals(self):
        self.btn_record.clicked.connect(self._on_record_toggle_ui)
        self.btn_play.clicked.connect(self._on_play)
        self.btn_stop_play.clicked.connect(self._on_stop_play)
        self.combo_size.currentIndexChanged.connect(self._on_size_change)

        self._signals.record_toggle.connect(self._on_record_toggle_hotkey)
        self._signals.play_toggle.connect(self._on_play_toggle_hotkey)
        self._signals.playback_finish.connect(self._on_playback_finished)
        self._signals.playback_progress.connect(self._on_playback_progress)
        self._signals.log_message.connect(self._on_log_message)

        # 编辑模式
        self.script_list.sig_edit_started.connect(self._on_edit_started)
        self.script_list.sig_edit_finished.connect(self._on_edit_finished)

    # ------------------------------------------------------------------
    # 屏幕分辨率检测
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_screen() -> tuple[int, int]:
        """获取主屏幕物理分辨率（DPI 感知）。"""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        except Exception:
            return 1920, 1080

    # ------------------------------------------------------------------
    # 热键初始化
    # ------------------------------------------------------------------

    def _init_hotkeys(self):
        self._hk = HotkeyManager(
            on_record_toggle=lambda: self._signals.record_toggle.emit(),
            on_play_toggle=lambda: self._signals.play_toggle.emit(),
        )
        self._hk.start()

    # ------------------------------------------------------------------
    # 録制逻辑
    # ------------------------------------------------------------------

    def _on_record_toggle_ui(self):
        """UI 按鈕触发的录制切换（无需修剪热键事件）。"""
        if self._recorder.is_running:
            self._stop_record(trim_key=None)
        else:
            self._start_record()

    def _on_record_toggle_hotkey(self):
        """热键触发录制切换（停止时从结果中修剪热键的非修饰键）。"""
        if self._recorder.is_running:
            # 找出组合键中的非修饰键（如 Shift+Alt+R 中的 "r"）
            _mods = {"shift", "alt", "ctrl", "cmd"}
            trim = next((k for k in config.RECORD_HOTKEY if k not in _mods), None)
            self._stop_record(trim_key=trim)
        else:
            self._start_record()

    def _start_record(self):
        """带倒计时的录制入口：有延迟则显示悬浮提示，结束后再真正开始。"""
        delay = self.playback_opts.start_delay
        if delay > 0:
            self._countdown_start(delay, "record")
        else:
            self._do_start_record()

    def _do_start_record(self):
        """实际启动录制（不含倒计时）。"""
        record_traj = self.chk_mouse_move.isChecked()
        self._recorder.start(
            record_mouse_move=record_traj,
            center_mouse=record_traj,
        )
        self._record_event_timer.start()
        self._set_state_recording()

    def _stop_record(self, trim_key: str | None = None):
        self._record_event_timer.stop()
        script = self._recorder.stop(trim_key=trim_key)

        if script.event_count == 0:
            QMessageBox.information(self, "提示", "未录制到任何事件。")
            self._set_state_idle()
            return

        name, ok = QInputDialog.getText(
            self, "保存脚本", "请输入脚本名称：", text=script.name
        )
        if ok and name.strip():
            script.name = name.strip()
            path = self._sm.save(script)
            self.script_list.refresh()
            self.lbl_status.setText(f"已保存：{os.path.basename(path)}")
        else:
            self.lbl_status.setText("录制已取消（未保存）")

        self._set_state_idle()

    def _update_record_count(self):
        self.lbl_record_count.setText(f"事件数：{self._recorder.event_count}")

    # ------------------------------------------------------------------
    # 回放逻辑
    # ------------------------------------------------------------------

    def _on_play(self):
        paths = self.script_list.selected_file_paths()
        if not paths:
            QMessageBox.warning(self, "提示", "请先在列表中选中一个脚本。")
            return

        if len(paths) > 1:
            names = [os.path.splitext(os.path.basename(p))[0] for p in paths]
            name, ok = QInputDialog.getItem(
                self, "选择脚本",
                f"检测到 {len(paths)} 个脚本被选中，请选择要回放的脚本：",
                names, 0, False,
            )
            if not ok:
                return
            path = paths[names.index(name)]
        else:
            path = paths[0]

        script = self._sm.load_by_path(path)
        if not script:
            QMessageBox.critical(self, "错误", "脚本加载失败。")
            return

        # 暂存脚本，等倒计时结束后再启动
        self._pending_play_script = script
        delay = self.playback_opts.start_delay
        if delay > 0:
            self._countdown_start(delay, "play")
        else:
            self._do_start_play()

    def _do_start_play(self):
        """实际启动回放（不含倒计时，延迟已在 UI 层处理）。"""
        script = self._pending_play_script
        if not script:
            return
        self._playback = Playback(
            script=script,
            speed_factor=self.playback_opts.speed,
            loop_count=self.playback_opts.loop_count,
            start_delay_sec=0,   # 延迟已由倒计时处理
            on_event=lambda e, i, t: self._signals.playback_progress.emit(i + 1, t),
            on_finish=lambda: self._signals.playback_finish.emit(),
        )
        self._playback.start()
        self.progress_bar.setRange(0, script.event_count)
        self.progress_bar.setValue(0)
        self._set_state_playing()

    def _on_stop_play(self):
        if self._playback:
            self._playback.stop()

    def _on_playback_finished(self):
        self._set_state_idle()
        self.lbl_status.setText("回放完成")

    def _on_playback_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)

    # ------------------------------------------------------------------
    # 新增功能方法
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 编辑模式
    # ------------------------------------------------------------------

    def _on_edit_started(self, add_event_cb):
        """脚本进入编辑模式：启用手动面板，绑定回调。"""
        self.manual_mouse.set_edit_callback(add_event_cb)
        # 编辑期间禁用录制/回放
        self.btn_record.setEnabled(False)
        self.btn_play.setEnabled(False)

    def _on_edit_finished(self):
        """脚本退出编辑模式：禁用手动面板，恢复控制按钮。"""
        self.manual_mouse.set_edit_callback(None)
        self.btn_record.setEnabled(True)
        self.btn_play.setEnabled(True)

    # ------------------------------------------------------------------
    # 倒计时悬浮提示（录制/回放共用）
    # ------------------------------------------------------------------

    def _countdown_start(self, seconds: int, action: str):
        """启动倒计时：action='record' 或 'play'。"""
        self._countdown_remaining = seconds
        self._countdown_action = action
        self._tick_countdown()

    def _tick_countdown(self):
        n = self._countdown_remaining
        if self._countdown_action == "record":
            self._app_hint.show_hint(f"⏺  {n} 秒后开始录制…")
        else:
            self._app_hint.show_hint(f"▶  {n} 秒后开始回放…")
        self._countdown_remaining -= 1
        if self._countdown_remaining > 0:
            QTimer.singleShot(1000, self._tick_countdown)
        else:
            QTimer.singleShot(1000, self._finish_countdown)

    def _finish_countdown(self):
        self._app_hint.hide()
        if self._countdown_action == "record":
            self._do_start_record()
        else:
            self._do_start_play()

    # ------------------------------------------------------------------
    # 新增功能方法
    # ------------------------------------------------------------------

    def _on_play_toggle_hotkey(self):
        """F6 热键：当前回放中则停止，否则尝试开始回放。"""
        if self._recorder.is_running:
            return  # 录制中不允许触发回放
        if self._playback and self._playback.is_running:
            self._on_stop_play()
        else:
            self._on_play()

    def _on_log_message(self, text: str):
        """stdout 转发到 UI 日志面板。"""
        self.log_text.append(text)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_size_change(self, index: int):
        """UI 预设尺寸切换（居中显示）。"""
        if 0 <= index < len(config.UI_SIZES):
            _, w, h = config.UI_SIZES[index]
            self.resize(w, h)
            screen = QApplication.primaryScreen().geometry()
            self.move(
                (screen.width()  - w) // 2,
                (screen.height() - h) // 2,
            )

    def _load_size_setting(self):
        """从 settings.json 还原窗口尺寸。"""
        prefs = settings.load()
        idx = prefs.get("ui_size_index", config.UI_DEFAULT_SIZE_INDEX)
        idx = max(0, min(idx, len(config.UI_SIZES) - 1))
        self.combo_size.blockSignals(True)
        self.combo_size.setCurrentIndex(idx)
        self.combo_size.blockSignals(False)
        if 0 <= idx < len(config.UI_SIZES):
            _, w, h = config.UI_SIZES[idx]
            self.resize(w, h)

    # ------------------------------------------------------------------
    # 状态切换
    # ------------------------------------------------------------------

    def _set_state_idle(self):
        self.btn_record.setText("⏺  开始录制")
        self.btn_record.setEnabled(True)
        self.btn_play.setEnabled(True)
        self.btn_stop_play.setEnabled(False)
        self.chk_mouse_move.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_record_count.setText("事件数：0")
        self.lbl_status.setText("就绪")

    def _set_state_recording(self):
        self.btn_record.setText("⏹  停止录制")
        self.btn_play.setEnabled(False)
        self.btn_stop_play.setEnabled(False)
        self.chk_mouse_move.setEnabled(False)   # 录制中禁止修改
        traj = "（含轨迹）" if self.chk_mouse_move.isChecked() else "（不含轨迹）"
        self.lbl_status.setText(f"● 录制中… {traj}")

    def _set_state_playing(self):
        self.btn_record.setEnabled(False)
        self.btn_play.setEnabled(False)
        self.btn_stop_play.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.lbl_status.setText("▶ 回放中…")

    # ------------------------------------------------------------------
    # 关闭清理
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self._recorder.is_running:
            self._recorder.stop(name="__auto_close__")
        if self._playback and self._playback.is_running:
            self._playback.stop()
        self._hk.stop()
        # 保存窗口尺寸设置
        settings.save({"ui_size_index": self.combo_size.currentIndex()})
        # 恢复 stdout
        if hasattr(self, "_old_stdout") and self._old_stdout is not None:
            sys.stdout = self._old_stdout
        event.accept()


# ------------------------------------------------------------------
# 启动入口
# ------------------------------------------------------------------

def launch():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
