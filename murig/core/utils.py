# -*- coding: utf-8 -*-
"""与 UI 无关的通用小工具。"""

from __future__ import annotations

from pathlib import Path


def human_size(num: float) -> str:
    """把字节数转换为可读字符串。"""
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def ensure_dir(path: Path) -> None:
    """确保目录存在。"""
    path.mkdir(parents=True, exist_ok=True)
