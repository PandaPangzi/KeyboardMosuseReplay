"""
事件数据模型
定义录制过程中所有事件的数据结构
"""

from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


class EventType(str, Enum):
    # 键盘事件
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    # 鼠标事件
    MOUSE_MOVE = "mouse_move"
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    MOUSE_SCROLL = "mouse_scroll"
    MOUSE_DOUBLE_CLICK = "mouse_double_click"


class MouseButton(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


@dataclass
class Event:
    """单个输入事件"""
    type: str                          # EventType 值
    timestamp: float                   # 相对于录制起始的毫秒时间戳

    # 键盘字段
    key: Optional[str] = None          # 按键名称，如 "a", "ctrl", "f1"
    scan_code: Optional[int] = None    # 扫描码（可选，提高回放兼容性）

    # 鼠标字段
    x: Optional[int] = None
    y: Optional[int] = None
    button: Optional[str] = None       # MouseButton 值
    dx: Optional[int] = None           # 滚轮水平滚动量
    dy: Optional[int] = None           # 滚轮垂直滚动量

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @staticmethod
    def from_dict(data: dict) -> "Event":
        return Event(**data)


@dataclass
class Script:
    """录制脚本，包含元数据和事件列表"""
    name: str
    events: list = field(default_factory=list)
    created_at: str = ""
    duration_ms: float = 0.0           # 脚本总时长（毫秒）
    screen_w: int = 0                  # 录制时主屏幕宽度（物理像素）
    screen_h: int = 0                  # 录制时主屏幕高度（物理像素）
    record_mouse_move: bool = False    # 是否录制了鼠标轨迹

    @property
    def event_count(self) -> int:
        return len(self.events)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "duration_ms": self.duration_ms,
            "screen_w": self.screen_w,
            "screen_h": self.screen_h,
            "record_mouse_move": self.record_mouse_move,
            "events": [
                e.to_dict() if isinstance(e, Event) else e
                for e in self.events
            ],
        }

    @staticmethod
    def from_dict(data: dict) -> "Script":
        events = [Event.from_dict(e) for e in data.get("events", [])]
        return Script(
            name=data.get("name", "未命名"),
            events=events,
            created_at=data.get("created_at", ""),
            duration_ms=data.get("duration_ms", 0.0),
            screen_w=data.get("screen_w", 0),
            screen_h=data.get("screen_h", 0),
            record_mouse_move=data.get("record_mouse_move", False),
        )
