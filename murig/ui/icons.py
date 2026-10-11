# -*- coding: utf-8 -*-
"""代码绘制的图标（避免 emoji 在部分系统渲染成空白方格）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap


def folder_icon(size: int = 16) -> QIcon:
    """代码绘制的文件夹图标。

    📁 emoji 在部分系统/字体下会渲染成空白方格，这里用 QPainter 直接画，
    保证任何平台都能正常显示。
    """
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    w = float(size * dpr)
    # 文件夹背板（含左上标签页）
    p.setBrush(QColor("#f9a825"))
    p.drawRoundedRect(QRectF(w * 0.10, w * 0.20, w * 0.42, w * 0.28), w * 0.06, w * 0.06)
    # 文件夹正面
    p.setBrush(QColor("#fbc02d"))
    p.drawRoundedRect(QRectF(w * 0.10, w * 0.34, w * 0.80, w * 0.46), w * 0.08, w * 0.08)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)
