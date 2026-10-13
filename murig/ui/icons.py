# -*- coding: utf-8 -*-
"""代码绘制的矢量图标（线性描边风格，避免 emoji 字体渲染不一致/锯齿）。

统一规范：
- 24x24 逻辑坐标系，2px 圆头描边，按需缩放并做 2x 超采样保证高分屏清晰；
- 颜色可参数化（标题栏浅色 / 卡片主色）；
- QPainter 直接绘制，不依赖系统 emoji 字体。
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

# 标题栏（深色底）上的默认图标色
BAR_FG = "#e6eaf3"
# 卡片 / 浅色底上的默认图标色
BODY_FG = "#4f46e5"


def _icon(size: int, color: str, draw: Callable[[QPainter], None]) -> QIcon:
    """在 24x24 逻辑坐标系里绘制并缩放到 size 像素（2x 超采样）。"""
    dpr = 2.0
    px = max(1, int(size * dpr))
    pm = QPixmap(px, px)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(2.0)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(QBrush())  # NoBrush：仅描边不填充
    scale = px / 24.0
    p.scale(scale, scale)
    draw(p)
    p.end()
    pm.setDevicePixelRatio(px / size)
    return QIcon(pm)


def _polyline(p: QPainter, *pts: tuple[float, float]) -> None:
    path = QPainterPath(QPointF(*pts[0]))
    for x, y in pts[1:]:
        path.lineTo(QPointF(x, y))
    p.drawPath(path)


# --------------------------------------------------------------------------
# 具体图标
# --------------------------------------------------------------------------
def about_icon(size: int = 16, color: str = BAR_FG) -> QIcon:
    """圆圈 + i（关于）。"""
    def draw(p: QPainter) -> None:
        p.drawEllipse(QRectF(3, 3, 18, 18))
        _polyline(p, (12, 11), (12, 16.5))
        p.drawPoint(QPointF(12, 7.6))
    return _icon(size, color, draw)


def refresh_icon(size: int = 16, color: str = BAR_FG) -> QIcon:
    """循环箭头（刷新）。"""
    def draw(p: QPainter) -> None:
        p.drawArc(QRectF(4.5, 4.5, 15, 15), 40 * 16, 280 * 16)
        _polyline(p, (18.2, 3.2), (19.4, 8.0), (14.6, 9.2))
    return _icon(size, color, draw)


def folder_icon(size: int = 16, color: str = BODY_FG) -> QIcon:
    """线性文件夹（卡片目录按钮、标题栏工作空间按钮）。"""
    def draw(p: QPainter) -> None:
        path = QPainterPath(QPointF(3, 6.5))
        path.lineTo(3, 19)
        path.lineTo(21, 19)
        path.lineTo(21, 8)
        path.lineTo(11.5, 8)
        path.lineTo(9.5, 5.5)
        path.lineTo(4.5, 5.5)
        path.quadTo(3, 5.5, 3, 6.5)
        p.drawPath(path)
    return _icon(size, color, draw)


def heart_icon(size: int = 16, color: str = "#ff8f8f") -> QIcon:
    """心形（支持作者）。"""
    def draw(p: QPainter) -> None:
        path = QPainterPath(QPointF(12, 20))
        path.cubicTo(4, 14.5, 3.5, 9.5, 7.2, 7.0)
        path.cubicTo(9.6, 5.4, 11.4, 7.0, 12, 8.6)
        path.cubicTo(12.6, 7.0, 14.4, 5.4, 16.8, 7.0)
        path.cubicTo(20.5, 9.5, 20, 14.5, 12, 20)
        p.drawPath(path)
    return _icon(size, color, draw)


def minimize_icon(size: int = 14, color: str = BAR_FG) -> QIcon:
    def draw(p: QPainter) -> None:
        _polyline(p, (5, 12), (19, 12))
    return _icon(size, color, draw)


def maximize_icon(size: int = 14, color: str = BAR_FG) -> QIcon:
    def draw(p: QPainter) -> None:
        p.drawRoundedRect(QRectF(5.5, 5.5, 13, 13), 2, 2)
    return _icon(size, color, draw)


def restore_icon(size: int = 14, color: str = BAR_FG) -> QIcon:
    def draw(p: QPainter) -> None:
        _polyline(p, (9, 6.5), (17.5, 6.5), (17.5, 15))
        p.drawRoundedRect(QRectF(6.5, 9, 8.5, 8.5), 2, 2)
    return _icon(size, color, draw)


def close_icon(size: int = 14, color: str = BAR_FG) -> QIcon:
    def draw(p: QPainter) -> None:
        _polyline(p, (6.5, 6.5), (17.5, 17.5))
        _polyline(p, (17.5, 6.5), (6.5, 17.5))
    return _icon(size, color, draw)
