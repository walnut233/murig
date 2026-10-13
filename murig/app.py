# -*- coding: utf-8 -*-
"""应用入口：组装 QApplication + 主题 + 主窗口。"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# 字体 / 高 DPI 渲染设置（必须在 QApplication 创建之前完成）
# ---------------------------------------------------------------------------
# 启用高 DPI 缩放，避免高分屏整体位图拉伸导致模糊
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

# Windows 默认使用 GDI 字体引擎（灰度抗锯齿，小字号中文发毛/锯齿）。
# 强制切到 DirectWrite：支持亚像素抗锯齿 + 更好的字距，字体边缘明显更干净。
# 可用 MURIG_FONT_ENGINE=gdi|directwrite|freetype 覆盖以做对比。
if sys.platform == "win32":
    _engine = os.environ.get("MURIG_FONT_ENGINE", "directwrite").strip()
    os.environ.setdefault("QT_QPA_PLATFORM", f"windows:fontengine={_engine or 'directwrite'}")

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .core.constants import APP_NAME, CURRENT_OS
from .ui.main_window import MainWindow
from .ui.theme import apply_theme


def _default_font() -> QFont | None:
    """返回平台默认 UI 字体，并显式要求抗锯齿 + 亚像素渲染。"""
    font = QFont()
    if CURRENT_OS == "Windows":
        font.setFamily("Microsoft YaHei UI")  # 雅黑 UI 版字距更松，小字号最清晰
        font.setPointSize(10)
    elif CURRENT_OS == "Darwin":
        font.setFamily("PingFang SC")
        font.setPointSize(13)
    else:
        return None
    # 明确要求抗锯齿与高质量（亚像素）渲染：QSS 只覆盖 family/size，策略会被保留
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.PreferQuality
    )
    # 全量 hinting：字模对齐像素网格，小字号中文笔画更实、不发虚
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    font = _default_font()
    if font is not None:
        app.setFont(font)
    apply_theme(app)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
