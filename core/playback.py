"""
回放模块
读取 Script 中的事件序列，按时间戳精确还原键盘和鼠标操作。

支持：
- 速度倍率（speed_factor）
- 循环次数（loop_count，0 = 无限）
- 回放前启动延迟（start_delay_sec）
- 热键中断（内部通过 stop() 调用实现）
- 回调钩子：on_event / on_loop_done / on_finish
"""

import time
import threading
import ctypes
from typing import Optional, Callable

from pynput.keyboard import Controller as KbController, Key, KeyCode
from pynput.mouse import Controller as MsController, Button

from core.event_model import Event, EventType, Script
import config


def _get_screen_size() -> tuple[int, int]:
    """获取主屏幕物理分辨率。"""
    try:
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    except Exception:
        return 1920, 1080


class Playback:
    def __init__(
        self,
        script: Script,
        speed_factor: float = config.DEFAULT_PLAYBACK_SPEED,
        loop_count: int = config.DEFAULT_LOOP_COUNT,
        start_delay_sec: float = config.DEFAULT_START_DELAY_SEC,
        on_event: Optional[Callable[[Event, int, int], None]] = None,
        on_loop_done: Optional[Callable[[int], None]] = None,
        on_finish: Optional[Callable[[], None]] = None,
    ):
        """
        参数：
            script          — 要回放的脚本
            speed_factor    — 速度倍率，1.0 = 原速，2.0 = 两倍速
            loop_count      — 循环次数，0 表示无限循环
            start_delay_sec — 开始回放前的等待秒数
            on_event        — 每个事件执行后回调(event, current_index, total)
            on_loop_done    — 每轮循环结束后回调(loop_index)
            on_finish       — 全部回放完成后回调
        """
        self.script = script
        self.speed_factor = max(speed_factor, 0.01)
        self.loop_count = loop_count
        self.start_delay_sec = start_delay_sec
        self.on_event = on_event
        self.on_loop_done = on_loop_done
        self.on_finish = on_finish

        self._kb = KbController()
        self._ms = MsController()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # 当前屏幕分辨率，用于坐标缩放
        self._cur_sw, self._cur_sh = _get_screen_size()

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def start(self, blocking: bool = False):
        """启动回放（默认后台线程运行）。"""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="Playback")
        self._thread.start()
        if blocking:
            self._thread.join()

    def stop(self):
        """请求中断回放（线程安全）。"""
        self._stop_event.set()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # 回放主循环
    # ------------------------------------------------------------------

    def _run(self):
        # 启动延迟
        if self.start_delay_sec > 0:
            print(f"[Playback] {self.start_delay_sec:.0f} 秒后开始回放...")
            for i in range(int(self.start_delay_sec * 10)):
                if self._stop_event.is_set():
                    return
                time.sleep(0.1)

        events = self.script.events
        if not events:
            print("[Playback] 脚本无事件，跳过")
            self._fire_finish()
            return

        loop_index = 0
        while True:
            if self._stop_event.is_set():
                break

            print(f"[Playback] 第 {loop_index + 1} 次回放开始")
            self._play_once(events, loop_index)

            if self._stop_event.is_set():
                break

            loop_index += 1
            if self.on_loop_done:
                self.on_loop_done(loop_index)

            # 判断是否结束循环
            if self.loop_count > 0 and loop_index >= self.loop_count:
                break

        print("[Playback] 回放结束")
        self._fire_finish()

    def _play_once(self, events: list, loop_index: int):
        total = len(events)
        loop_start = time.perf_counter()

        for idx, event in enumerate(events):
            if self._stop_event.is_set():
                return

            # 计算应该在何时（相对于本轮起始）执行该事件
            target_ts = event.timestamp / 1000.0 / self.speed_factor  # 秒
            elapsed = time.perf_counter() - loop_start
            wait = target_ts - elapsed
            if wait > 0:
                # 分段等待以便及时响应 stop()
                end_time = time.perf_counter() + wait
                while time.perf_counter() < end_time:
                    if self._stop_event.is_set():
                        return
                    time.sleep(0.001)

            self._dispatch(event)

            if self.on_event:
                self.on_event(event, idx, total)

    # ------------------------------------------------------------------
    # 事件分发
    # ------------------------------------------------------------------

    def _dispatch(self, event: Event):
        t = event.type
        try:
            if t == EventType.KEY_DOWN:
                for _k in _resolve_combo(event.key):
                    self._kb.press(_k)
            elif t == EventType.KEY_UP:
                for _k in reversed(_resolve_combo(event.key)):
                    self._kb.release(_k)
            elif t == EventType.MOUSE_MOVE:
                x, y = self._scale_coords(event.x, event.y)
                self._ms.position = (x, y)
            elif t == EventType.MOUSE_DOWN:
                self._ms.press(_resolve_button(event.button))
            elif t == EventType.MOUSE_UP:
                self._ms.release(_resolve_button(event.button))
            elif t == EventType.MOUSE_SCROLL:
                self._ms.scroll(event.dx or 0, event.dy or 0)
        except Exception as e:
            print(f"[Playback] 事件执行失败 {event}: {e}")

    def _scale_coords(self, x: int, y: int) -> tuple[int, int]:
        """
        将录制时的坐标缩放到当前屏幕分辨率。
        若录制分辨率未知（screen_w=0）则原样返回。
        """
        rw = self.script.screen_w
        rh = self.script.screen_h
        if rw > 0 and rh > 0 and (rw != self._cur_sw or rh != self._cur_sh):
            x = int(x * self._cur_sw / rw)
            y = int(y * self._cur_sh / rh)
        return x, y

    def _fire_finish(self):
        if self.on_finish:
            self.on_finish()


# ----------------------------------------------------------------------
# 辅助函数
# ----------------------------------------------------------------------

def _resolve_key(key_name: str):
    """将字符串键名还原为 pynput Key 或 KeyCode。"""
    if key_name is None:
        return KeyCode.from_char(" ")
    # 尝试特殊键
    try:
        return Key[key_name]
    except KeyError:
        pass
    # vk_ 前缀的虚拟键码
    if key_name.startswith("vk_"):
        try:
            return KeyCode.from_vk(int(key_name[3:]))
        except (ValueError, TypeError):
            pass
    # 普通字符键
    return KeyCode.from_char(key_name)


def _resolve_combo(key_name: str) -> list:
    """将 'ctrl+s'、'ctrl+shift+z' 等组合键字符串拆分为 pynput key 对象列表。"""
    if key_name and '+' in key_name:
        return [_resolve_key(k.strip()) for k in key_name.split('+')]
    return [_resolve_key(key_name)]


def _resolve_button(button_name: str) -> Button:
    """将字符串按钮名还原为 pynput Button。"""
    try:
        return Button[button_name]
    except KeyError:
        return Button.left
