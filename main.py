"""
KMReasy — 程序入口
"""

import sys
import os
import traceback
from datetime import datetime


def _runtime_data_dir() -> str:
    """返回可写目录：打包后使用 AppData，开发模式使用项目根目录。"""
    if getattr(sys, "frozen", False):
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KMReasy")
    return os.path.dirname(os.path.abspath(__file__))


def _write_startup_error_log(title: str, detail: str) -> str:
    """写入启动错误日志，返回日志路径。"""
    log_dir = _runtime_data_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "startup_error.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n" + "=" * 72 + "\n")
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
        f.write(title + "\n\n")
        f.write(detail + "\n")
    return log_path


def _show_error_dialog(title: str, message: str):
    """在 Windows 下显示系统弹窗，避免 --windowed 时无控制台输出。"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, title, 0x10)
    except Exception:
        # 最后兜底：尽量输出到 stderr
        print(f"{title}: {message}", file=sys.stderr)


def _handle_fatal_error(title: str, exc: BaseException):
    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_path = _write_startup_error_log(title, detail)
    _show_error_dialog(
        "KMReasy 启动失败",
        f"{title}\n\n{exc}\n\n错误日志：\n{log_path}",
    )


def _global_excepthook(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    detail = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    log_path = _write_startup_error_log("未处理异常", detail)
    _show_error_dialog(
        "KMReasy 运行异常",
        f"程序发生未处理异常：\n{exc_value}\n\n错误日志：\n{log_path}",
    )


sys.excepthook = _global_excepthook

# 确保项目根目录在模块搜索路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    try:
        from ui.main_window import launch
        launch()
    except ImportError as e:
        _handle_fatal_error("依赖导入失败", e)
        sys.exit(1)
    except Exception as e:
        _handle_fatal_error("程序启动异常", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
