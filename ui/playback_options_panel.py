"""
回放选项面板
速度倍率、循环次数、启动延迟配置。
"""

from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QDoubleSpinBox, QSpinBox, QLabel,
)


class PlaybackOptionsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 速度倍率
        self.spin_speed = QDoubleSpinBox()
        self.spin_speed.setRange(0.1, 10.0)
        self.spin_speed.setSingleStep(0.5)
        self.spin_speed.setValue(1.0)
        self.spin_speed.setSuffix(" x")
        layout.addRow("回放速度：", self.spin_speed)

        # 循环次数
        self.spin_loop = QSpinBox()
        self.spin_loop.setRange(0, 9999)
        self.spin_loop.setValue(1)
        self.spin_loop.setSpecialValueText("无限循环")
        layout.addRow("循环次数：", self.spin_loop)

        # 启动延迟
        self.spin_delay = QSpinBox()
        self.spin_delay.setRange(0, 30)
        self.spin_delay.setValue(3)
        self.spin_delay.setSuffix(" 秒")
        layout.addRow("启动延迟：", self.spin_delay)

    @property
    def speed(self) -> float:
        return self.spin_speed.value()

    @property
    def loop_count(self) -> int:
        return self.spin_loop.value()

    @property
    def start_delay(self) -> int:
        return self.spin_delay.value()
