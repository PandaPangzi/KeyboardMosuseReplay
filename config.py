"""
全局配置
"""

import os

# 脚本存储目录（绝对路径，兼容打包后的运行环境）
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")

# 热键：Shift+Alt+R 开始/停止录制，Shift+Alt+S 开始/停止回放
# frozenset 多元素 = 组合键（所有键同时按住即触发）
RECORD_HOTKEY: frozenset = frozenset({"shift", "alt", "r"})   # Shift+Alt+R
PLAY_HOTKEY:   frozenset = frozenset({"shift", "alt", "s"})   # Shift+Alt+S

RECORD_HOTKEY_DISPLAY = "Shift+Alt+R"
PLAY_HOTKEY_DISPLAY   = "Shift+Alt+S"

# 向后兼容别名
STOP_HOTKEY          = RECORD_HOTKEY
ABORT_HOTKEY         = PLAY_HOTKEY
STOP_HOTKEY_DISPLAY  = RECORD_HOTKEY_DISPLAY
ABORT_HOTKEY_DISPLAY = PLAY_HOTKEY_DISPLAY

# 控制热键键名集合：这些键触发停止录制时会从末尾自动修剪
CONTROL_KEYS: frozenset = RECORD_HOTKEY | PLAY_HOTKEY

# 鼠标移动采样间隔（毫秒），数值越大录制文件越小，精度越低
MOUSE_MOVE_INTERVAL_MS = 20

# 默认回放参数
DEFAULT_PLAYBACK_SPEED = 1.0     # 速度倍率
DEFAULT_LOOP_COUNT = 1           # 循环次数，0 = 无限
DEFAULT_START_DELAY_SEC = 3      # 回放前等待秒数

# UI 预设窗口尺寸 (label, width, height)
UI_SIZES = [
    ("1800×1400", 1800, 1400),
    ("1200×933",  1200, 933),
    ("900×700",   900,  700),
]
UI_DEFAULT_SIZE_INDEX = 1  # 默认 1200×933
