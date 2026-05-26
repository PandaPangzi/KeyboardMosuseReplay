"""
热键管理器
全局监听配置中的热键，触发对应动作（开始/停止录制、中断回放）。

使用方式：
    manager = HotkeyManager(
        on_record_toggle=lambda: ...,
        on_playback_abort=lambda: ...,
    )
    manager.start()
    # ... 程序运行 ...
    manager.stop()
"""

import threading
from typing import Optional, Callable

from pynput import keyboard

import config


# 左右修饰键统一为通用名，避免因左右键不同导致组合键匹配失败
_MODIFIER_NORMALIZE = {
    "ctrl_l": "ctrl",  "ctrl_r": "ctrl",
    "alt_l":  "alt",   "alt_r":  "alt",  "alt_gr": "alt",
    "shift_l": "shift", "shift_r": "shift",
    "cmd_l":  "cmd",   "cmd_r":  "cmd",
}

class HotkeyManager:
    def __init__(
        self,
        on_record_toggle: Optional[Callable[[], None]] = None,
        on_play_toggle: Optional[Callable[[], None]] = None,
    ):
        self.on_record_toggle = on_record_toggle
        self.on_play_toggle = on_play_toggle
        self._listener: Optional[keyboard.Listener] = None
        # 当前按住的所有键（规范化名称）
        self._pressed: set = set()

    def start(self):
        if self._listener and self._listener.is_alive():
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()
        print(f"[HotkeyManager] 已启动 "
              f"| 录制: {config.RECORD_HOTKEY_DISPLAY} "
              f"| 回放: {config.PLAY_HOTKEY_DISPLAY}")

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None

    # ------------------------------------------------------------------
    # 内部回调
    # ------------------------------------------------------------------

    def _on_press(self, key):
        key_name = _normalize(_raw_key_name(key))
        if key_name in self._pressed:
            return  # 防止长按连续触发
        self._pressed.add(key_name)

        # 组合键检测：当前按下集合包含热键所有键时触发
        if config.RECORD_HOTKEY.issubset(self._pressed):
            if self.on_record_toggle:
                threading.Thread(target=self.on_record_toggle, daemon=True).start()
        elif config.PLAY_HOTKEY.issubset(self._pressed):
            if self.on_play_toggle:
                threading.Thread(target=self.on_play_toggle, daemon=True).start()

    def _on_release(self, key):
        key_name = _normalize(_raw_key_name(key))
        self._pressed.discard(key_name)


def _raw_key_name(key) -> str:
    """将 pynput Key/KeyCode 转为原始字符串键名。"""
    if isinstance(key, keyboard.KeyCode):
        ch = key.char
        if ch:
            return ch.lower()   # Shift 按住时大写字母需统一为小写
        return f"vk_{key.vk}"
    return key.name


def _normalize(key_name: str) -> str:
    """将左右修饰键统一为通用名，其余键保持不变。"""
    return _MODIFIER_NORMALIZE.get(key_name, key_name)
