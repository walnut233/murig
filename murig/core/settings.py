# -*- coding: utf-8 -*-
"""通用安装行为设置。

目前只有一个开关：是否在安装完成后自动写入环境变量。写入 XXX_HOME / PATH
会改动用户配置，属于副作用操作，因此默认关闭，由用户在需要时手动点
「配置环境变量」或打开开关。

设置落在 SETTINGS_FILE 的 "install" 段，与工作空间、下载设置同一文件。
"""

from __future__ import annotations

import json
import os
from typing import Dict

from .constants import SETTINGS_DIR, SETTINGS_FILE
from .utils import ensure_dir


class InstallSettings:
    """安装行为设置。"""

    def __init__(self) -> None:
        # 安装完成后自动配置环境变量；关闭时仅解压，配置留给用户决定
        self.auto_env: bool = False

    # ------------------------------------------------------------------
    @classmethod
    def load(cls) -> "InstallSettings":
        s = cls()
        try:
            if SETTINGS_FILE.exists():
                data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                d = data.get("install") or {}
                s.auto_env = bool(d.get("auto_env"))
        except Exception:
            pass
        # 环境变量方便临时对比：MURIG_AUTO_ENV=1 打开
        env = os.environ.get("MURIG_AUTO_ENV")
        if env:
            s.auto_env = env.strip().lower() in ("1", "true", "yes", "on")
        return s

    def save(self) -> None:
        try:
            ensure_dir(SETTINGS_DIR)
            data: Dict = {}
            if SETTINGS_FILE.exists():
                try:
                    data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            data["install"] = {"auto_env": self.auto_env}
            SETTINGS_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass


# 全局单例：启动时加载一次，UI 修改后即时 save
INSTALL = InstallSettings.load()
