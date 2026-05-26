"""
用户偏好设置持久化（读写 settings.json）
"""

import json
import os

_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")


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
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Settings] 保存失败: {e}")
