# -*- coding: utf-8 -*-
"""无头冒烟测试：用 offscreen 平台真实构造主窗口并跑一小会儿事件循环。

用法： python tools/smoke.py
用于验证重构后没有 import / 属性 / 布局层面的运行时错误。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from murig.ui.main_window import MainWindow  # noqa: E402
from murig.ui.theme import apply_theme  # noqa: E402


def run() -> int:
    app = QApplication(sys.argv)
    apply_theme(app)
    win = MainWindow()
    win.show()
    print(f"[smoke] 主窗口已构造，组件卡片 {len(win.cards)} 个")
    QTimer.singleShot(1500, app.quit)
    app.exec()
    print("[smoke] 事件循环正常退出")
    return 0


if __name__ == "__main__":
    sys.exit(run())
