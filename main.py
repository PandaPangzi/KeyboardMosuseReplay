"""
KeyboardRecord — 程序入口
"""

import sys
import os

# 确保项目根目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    try:
        from ui.main_window import launch
        launch()
    except ImportError as e:
        print(f"[错误] 依赖缺失：{e}")
        print("请先运行：pip install -r requirements.txt")
        sys.exit(1)


if __name__ == "__main__":
    main()
