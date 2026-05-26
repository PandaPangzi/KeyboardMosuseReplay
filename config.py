"""
全局配置
"""

import os
import sys


def _runtime_data_dir() -> str:
    """返回可写的数据目录：开发模式用项目根目录，打包后优先 exe 同目录。"""
    if getattr(sys, "frozen", False):
        # 打包后优先放在 exe 同目录，便于携带与管理
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        base = exe_dir
        # 若目录不可写（例如 Program Files），自动回退到 AppData
        try:
            test_dir = os.path.join(base, "scripts")
            os.makedirs(test_dir, exist_ok=True)
            test_file = os.path.join(test_dir, ".write_test")
            with open(test_file, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test_file)
        except Exception:
            base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KMReasy")
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return base


# 脚本存储目录（打包后写入 AppData，避免 onefile 临时目录不可写）
SCRIPTS_DIR = os.path.join(_runtime_data_dir(), "scripts")

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
