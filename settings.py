"""
用户偏好设置持久化（读写 settings.json）
"""

import json
import os
import sys


def _runtime_data_dir() -> str:
    """返回可写的数据目录：开发模式用项目根目录，打包后用 AppData。"""
    if getattr(sys, "frozen", False):
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "KMReasy")
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return base


_FILE = os.path.join(_runtime_data_dir(), "settings.json")


def load() -> dict:
    if os.path.isfile(_FILE):
        try:
            with open(_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save(data: dict):
    try:
        os.makedirs(os.path.dirname(_FILE), exist_ok=True)
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Settings] 保存失败: {e}")
