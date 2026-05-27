"""
录制模块
同时监听键盘和鼠标事件，将它们按时间戳追加到事件列表中。

使用方式：
    recorder = Recorder()
    recorder.start()
    # ... 用户操作 ...
    script = recorder.stop("我的脚本")
"""

import time
import threading
import ctypes
from datetime import datetime
from typing import Optional

from pynput import keyboard, mouse

from core.event_model import Event, EventType, MouseButton, Script
import config


def _get_screen_size() -> tuple[int, int]:
    """获取主屏幕物理分辨率（Windows DPI 感知）。"""
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080  # fallback


class Recorder:
    def __init__(self):
        self._events: list[Event] = []
        self._start_time: float = 0.0
        self._running: bool = False
        self._lock = threading.Lock()

        self._kb_listener: Optional[keyboard.Listener] = None
        self._ms_listener: Optional[mouse.Listener] = None

        self._record_mouse_move: bool = True
        self._screen_w: int = 0
        self._screen_h: int = 0

        # 鼠标移动节流：记录上次采样的时间
        self._last_mouse_move_ts: float = -9999.0
        # 热键过滤：跟踪当前按住键与需忽略的键
        self._pressed_keys: set[str] = set()
        self._suppressed_keys: set[str] = set()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def start(self, record_mouse_move: bool = True, center_mouse: bool = False):
        """
        开始录制，重置之前的数据。

        Args:
            record_mouse_move: 是否录制鼠标移动轨迹。
            center_mouse: 开录前是否将鼠标移动到屏幕中心。
        """
        if self._running:
            return

        self._record_mouse_move = record_mouse_move
        self._screen_w, self._screen_h = _get_screen_size()

        # 若开启轨迹录制，先将鼠标移到屏幕中心作为基准起点
        if center_mouse and self._screen_w > 0:
            ms_ctrl = mouse.Controller()
            ms_ctrl.position = (self._screen_w // 2, self._screen_h // 2)
            time.sleep(0.15)  # 等待鼠标到位，再开始计时

        self._events = []
        self._start_time = time.perf_counter()
        self._last_mouse_move_ts = -9999.0
        self._pressed_keys.clear()
        self._suppressed_keys.clear()
        self._running = True

        self._kb_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._ms_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll,
        )
        self._kb_listener.start()
        self._ms_listener.start()
        res_info = f"{self._screen_w}x{self._screen_h}" if self._screen_w else "未知"
        print(f"[Recorder] 录制开始 | 鼠标轨迹={'开' if record_mouse_move else '关'} | 屏幕={res_info}")

    def stop(self, name: str = "", trim_key: str | None = None) -> Script:
        """停止录制并返回 Script 对象。

        Args:
            name:     脚本名称。
            trim_key: 若不为空，停止后会自动从事件列表末尾修剪该键的最后一次按下/弹起，
                      即用于剔除触发停止录制的热键本身。
        """
        if not self._running:
            raise RuntimeError("录制未在进行中")
        self._running = False

        if self._kb_listener:
            self._kb_listener.stop()
            self._kb_listener = None
        if self._ms_listener:
            self._ms_listener.stop()
            self._ms_listener = None

        # 修剪触发停止录制的热键事件（如果是热键触发的话）
        if trim_key:
            self._trim_trailing_key(trim_key.lower())

        duration = (time.perf_counter() - self._start_time) * 1000  # ms

        script = Script(
            name=name or f"录制_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            events=list(self._events),
            created_at=datetime.now().isoformat(timespec="seconds"),
            duration_ms=round(duration, 2),
            screen_w=self._screen_w,
            screen_h=self._screen_h,
            record_mouse_move=self._record_mouse_move,
        )
        print(f"[Recorder] 录制停止，共 {len(self._events)} 个事件，时长 {duration:.0f} ms")
        return script

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def event_count(self) -> int:
        return len(self._events)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _ts(self) -> float:
        """返回相对于录制开始的毫秒时间戳。"""
        return round((time.perf_counter() - self._start_time) * 1000, 2)

    def _append(self, event: Event):
        with self._lock:
            self._events.append(event)

    def _trim_trailing_key(self, key_name: str):
        """从事件列表末尾删除最后一次按下该键的 key_down（以及紧接的 key_up）。"""
        events = self._events
        for i in range(len(events) - 1, -1, -1):
            e = events[i]
            if e.type == EventType.KEY_DOWN and e.key == key_name:
                del events[i]
                # 同时删除紧接的 key_up
                if i < len(events) and events[i].type == EventType.KEY_UP and events[i].key == key_name:
                    del events[i]
                break

    def _drop_latest_unpaired_key_down(self, key_name: str):
        """删除最近一个尚未配对 key_up 的 key_down（用于热键过滤）。"""
        balance = 0
        for i in range(len(self._events) - 1, -1, -1):
            e = self._events[i]
            if e.key != key_name:
                continue
            if e.type == EventType.KEY_UP:
                balance += 1
            elif e.type == EventType.KEY_DOWN:
                if balance == 0:
                    del self._events[i]
                    return
                balance -= 1

    def _normalize_for_hotkey(self, key_name: str) -> str:
        """统一键名用于热键匹配（大小写与左右修饰键归一化）。"""
        if len(key_name) == 1:
            key_name = key_name.lower()
        return {
            "ctrl_l": "ctrl", "ctrl_r": "ctrl",
            "alt_l": "alt", "alt_r": "alt", "alt_gr": "alt",
            "shift_l": "shift", "shift_r": "shift",
            "cmd_l": "cmd", "cmd_r": "cmd",
        }.get(key_name, key_name)

    def _detect_hotkey(self) -> frozenset | None:
        """检测当前按住集合是否触发录制/回放热键。"""
        if config.RECORD_HOTKEY.issubset(self._pressed_keys):
            return config.RECORD_HOTKEY
        if config.PLAY_HOTKEY.issubset(self._pressed_keys):
            return config.PLAY_HOTKEY
        return None

    # ------------------------------------------------------------------
    # 键盘回调
    # ------------------------------------------------------------------

    def _on_key_press(self, key):
        if not self._running:
            return
        key_name, scan_code = _parse_key(key)
        norm_key = self._normalize_for_hotkey(key_name)
        self._pressed_keys.add(norm_key)

        hotkey = self._detect_hotkey()
        if hotkey is not None:
            for hk in hotkey:
                self._drop_latest_unpaired_key_down(hk)
            self._suppressed_keys.update(hotkey)

        if norm_key in self._suppressed_keys:
            return

        self._append(Event(
            type=EventType.KEY_DOWN,
            timestamp=self._ts(),
            key=norm_key,
            scan_code=scan_code,
        ))

    def _on_key_release(self, key):
        if not self._running:
            return
        key_name, scan_code = _parse_key(key)
        norm_key = self._normalize_for_hotkey(key_name)
        self._pressed_keys.discard(norm_key)

        if norm_key in self._suppressed_keys:
            self._suppressed_keys.discard(norm_key)
            return

        self._append(Event(
            type=EventType.KEY_UP,
            timestamp=self._ts(),
            key=norm_key,
            scan_code=scan_code,
        ))

    # ------------------------------------------------------------------
    # 鼠标回调
    # ------------------------------------------------------------------

    def _on_mouse_move(self, x, y):
        if not self._running or not self._record_mouse_move:
            return
        ts = self._ts()
        # 节流：控制鼠标移动采样频率
        if ts - self._last_mouse_move_ts < config.MOUSE_MOVE_INTERVAL_MS:
            return
        self._last_mouse_move_ts = ts
        self._append(Event(
            type=EventType.MOUSE_MOVE,
            timestamp=ts,
            x=x,
            y=y,
        ))

    def _on_mouse_click(self, x, y, button, pressed):
        if not self._running:
            return
        btn = _parse_button(button)
        evt_type = EventType.MOUSE_DOWN if pressed else EventType.MOUSE_UP
        self._append(Event(
            type=evt_type,
            timestamp=self._ts(),
            x=x,
            y=y,
            button=btn,
        ))

    def _on_mouse_scroll(self, x, y, dx, dy):
        if not self._running:
            return
        self._append(Event(
            type=EventType.MOUSE_SCROLL,
            timestamp=self._ts(),
            x=x,
            y=y,
            dx=dx,
            dy=dy,
        ))


# ----------------------------------------------------------------------
# 辅助函数
# ----------------------------------------------------------------------

def _parse_key(key) -> tuple[str, Optional[int]]:
    """将 pynput Key/KeyCode 转为可读字符串和扫描码。"""
    scan_code = None
    if isinstance(key, keyboard.KeyCode):
        scan_code = key.vk
        ch = key.char
        # Ctrl+字母 时 key.char 返回 ASCII 控制字符 \x01-\x1a（如 Ctrl+S → \x13）
        # 还原为对应小写字母，使录制结果可读且与 key_up 一致
        if ch and '\x01' <= ch <= '\x1a':
            ch = chr(ord(ch) + 0x60)
        return (ch or f"vk_{key.vk}"), scan_code
    else:
        # pynput Key 枚举（特殊键）
        return key.name, None


def _parse_button(button) -> str:
    """将 pynput Button 转为字符串。"""
    name = button.name  # 'left' / 'right' / 'middle' / 'x1' / 'x2'
    for mb in MouseButton:
        if mb.value == name:
            return mb.value
    return name
