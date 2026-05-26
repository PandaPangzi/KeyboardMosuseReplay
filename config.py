"""
全局配置
"""

import os

# 脚本存储目录（绝对路径，兼容打包后的运行环境）
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")

# 热键：使用组合键，避免与鼠标驱动宏键冲突
# 格式：frozenset，包含所有需同时按住的规范化键名
# 修饰键规范名：ctrl / alt / shift / cmd；普通键：小写字母或 f1~f12
STOP_HOTKEY: frozenset = frozenset({"ctrl", "alt", "r"})   # Ctrl+Alt+R 开始/停止录制
ABORT_HOTKEY: frozenset = frozenset({"ctrl", "alt", "s"})  # Ctrl+Alt+S 中断回放

# 供界面显示用的可读文本（与上面的 frozenset 保持对应）
STOP_HOTKEY_DISPLAY = "Ctrl+Alt+R"
ABORT_HOTKEY_DISPLAY = "Ctrl+Alt+S"

# 鼠标移动采样间隔（毫秒），数值越大录制文件越小，精度越低
MOUSE_MOVE_INTERVAL_MS = 20

# 默认回放参数
DEFAULT_PLAYBACK_SPEED = 1.0     # 速度倍率
DEFAULT_LOOP_COUNT = 1           # 循环次数，0 = 无限
DEFAULT_START_DELAY_SEC = 3      # 回放前等待秒数
