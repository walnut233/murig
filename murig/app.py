# -*- coding: utf-8 -*-
"""应用入口：组装 QApplication + 主题 + 主窗口。"""

from __future__ import annotations

import os
import sys

# 必须在 QApplication 创建之前设置：启用高 DPI 缩放，避免高分屏文字模糊/锯齿
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .core.constants import APP_NAME, CURRENT_OS
from .ui.main_window import MainWindow
from .ui.theme import apply_theme


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    # 显式指定各平台默认 UI 字体：Windows 用微软雅黑（ClearType 渲染最干净），
    # macOS / Linux 交给 Qt 自动选择系统默认字体
    if CURRENT_OS == "Windows":
        app.setFont(QFont("Microsoft YaHei UI", 10))
    apply_theme(app)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
