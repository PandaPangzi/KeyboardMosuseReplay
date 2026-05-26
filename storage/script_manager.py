"""
存储模块 — 脚本文件管理
负责将 Script 对象序列化/反序列化到 JSON 文件
"""

import os
import json
from datetime import datetime
from typing import List, Optional

from core.event_model import Script

# 默认脚本目录由调用方通过 ScriptManager(scripts_dir=...) 指定，
# 也可直接使用 config.SCRIPTS_DIR
DEFAULT_SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


def _dump_compact_events(script_dict: dict) -> str:
    """
    将 Script 字典序列化为 JSON 字符串。
    events 数组中每个事件对象占一行，其余字段正常缩进。
    """
    events = script_dict.pop("events", [])
    # 序列化除 events 之外的字段（带缩进）
    base = json.dumps(script_dict, ensure_ascii=False, indent=2)
    # 去掉最后的 }，准备追加 events
    base = base.rstrip().rstrip("}")
    # 序列化每个 event 为紧凑单行
    event_lines = ",\n    ".join(
        json.dumps(e, ensure_ascii=False, separators=(",", ":")) for e in events
    )
    events_block = f'  "events": [\n    {event_lines}\n  ]' if events else '  "events": []'
    result = base + f',\n{events_block}\n}}'
    # 恢复 events，避免影响原对象
    script_dict["events"] = events
    return result


class ScriptManager:
    def __init__(self, scripts_dir: str = DEFAULT_SCRIPTS_DIR):
        self.scripts_dir = os.path.abspath(scripts_dir)
        os.makedirs(self.scripts_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # 保存
    # ------------------------------------------------------------------
    def save(self, script: Script) -> str:
        """
        将脚本保存为 JSON 文件，返回文件完整路径。
        文件名格式：脚本名称.json（自动替换非法字符）
        """
        if not script.created_at:
            script.created_at = datetime.now().isoformat(timespec="seconds")

        safe_name = self._safe_filename(script.name)
        file_path = os.path.join(self.scripts_dir, f"{safe_name}.json")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(_dump_compact_events(script.to_dict()))

        return file_path

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------
    def load(self, name: str) -> Optional[Script]:
        """按脚本名称加载，返回 Script 对象，不存在则返回 None。"""
        safe_name = self._safe_filename(name)
        file_path = os.path.join(self.scripts_dir, f"{safe_name}.json")
        return self._load_file(file_path)

    def load_by_path(self, file_path: str) -> Optional[Script]:
        """按文件完整路径加载。"""
        return self._load_file(file_path)

    def _load_file(self, file_path: str) -> Optional[Script]:
        if not os.path.isfile(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Script.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"[ScriptManager] 加载文件失败 {file_path}: {e}")
            return None

    # ------------------------------------------------------------------
    # 列表 & 删除
    # ------------------------------------------------------------------
    def list_scripts(self) -> List[dict]:
        """
        返回所有已保存脚本的摘要信息列表：
        [{ name, created_at, duration_ms, event_count, file_path }, ...]
        """
        result = []
        for fname in sorted(os.listdir(self.scripts_dir)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(self.scripts_dir, fname)
            script = self._load_file(fpath)
            if script:
                result.append({
                    "name": script.name,
                    "created_at": script.created_at,
                    "duration_ms": script.duration_ms,
                    "event_count": script.event_count,
                    "file_path": fpath,
                })
        return result

    def delete(self, name: str) -> bool:
        """按名称删除脚本文件，成功返回 True。"""
        safe_name = self._safe_filename(name)
        file_path = os.path.join(self.scripts_dir, f"{safe_name}.json")
        if os.path.isfile(file_path):
            os.remove(file_path)
            return True
        return False

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_filename(name: str) -> str:
        """将名称转换为合法的文件名（替换非法字符）。"""
        illegal = r'\/:*?"<>|'
        for ch in illegal:
            name = name.replace(ch, "_")
        return name.strip() or "unnamed"
