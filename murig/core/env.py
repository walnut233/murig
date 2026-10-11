# -*- coding: utf-8 -*-
"""跨平台环境变量读写。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from .constants import CURRENT_OS


# ---------------------------------------------------------------------------
# 环境变量处理
# ---------------------------------------------------------------------------
class EnvManager:
    """跨平台环境变量管理器。"""

    @staticmethod
    def get(name: str) -> Optional[str]:
        return os.environ.get(name)

    @staticmethod
    def is_valid_home(path: str, exec_name: str) -> bool:
        """判断 XXX_HOME 是否有效——检查 bin 目录下是否存在可执行文件。"""
        if not path:
            return False
        p = Path(path)
        bin_dir = p / "bin"
        exe = bin_dir / (exec_name + (".exe" if CURRENT_OS == "Windows" else ""))
        return exe.exists()

    @staticmethod
    def set_windows_user_env(name: str, value: str) -> None:
        """在 Windows 上使用 setx 永久写入用户环境变量。"""
        # setx 会截断超过 1024 字符的 PATH，这里额外用 winreg 直接写注册表
        try:
            import winreg  # type: ignore

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS
            ) as key:
                reg_type = winreg.REG_EXPAND_SZ if "%" in value else winreg.REG_SZ
                winreg.SetValueEx(key, name, 0, reg_type, value)
            # 通知系统刷新
            subprocess.run(
                ["setx", name, value],
                check=False,
                shell=False,
                capture_output=True,
            )
        except Exception as exc:
            raise RuntimeError(f"写入 Windows 环境变量失败：{exc}")

    @staticmethod
    def append_windows_path(entry: str) -> None:
        """把 entry 追加到 Windows 用户 PATH。"""
        import winreg  # type: ignore

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS
        ) as key:
            try:
                current, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current = ""
        parts = [p for p in current.split(";") if p]
        if entry in parts:
            return
        parts.append(entry)
        EnvManager.set_windows_user_env("Path", ";".join(parts))

    @staticmethod
    def _shell_rc_file() -> Path:
        """选择 macOS / Linux 上要写入的 shell 配置文件。"""
        home = Path.home()
        shell = os.environ.get("SHELL", "")
        if shell.endswith("zsh"):
            return home / ".zshrc"
        if shell.endswith("bash"):
            # macOS 上 bash 更常读 ~/.bash_profile
            return home / (".bash_profile" if CURRENT_OS == "Darwin" else ".bashrc")
        return home / ".profile"

    @staticmethod
    def set_unix_env(name: str, value: str) -> Path:
        """在 UNIX 系统上，把 export 语句写入 shell 配置文件；返回被修改的文件路径。"""
        rc = EnvManager._shell_rc_file()
        # 标记保持旧品牌名 env-auto-setup：改名 MuRig 后老用户 rc 文件里的块仍需被识别和幂等更新
        marker_begin = f"# >>> env-auto-setup:{name} >>>"
        marker_end = f"# <<< env-auto-setup:{name} <<<"
        new_block = f'{marker_begin}\nexport {name}="{value}"\n{marker_end}\n'

        text = rc.read_text(encoding="utf-8") if rc.exists() else ""
        if marker_begin in text and marker_end in text:
            pre, rest = text.split(marker_begin, 1)
            _, post = rest.split(marker_end, 1)
            new_text = pre + new_block + post
        else:
            sep = "" if text.endswith("\n") or text == "" else "\n"
            new_text = text + sep + "\n" + new_block
        rc.write_text(new_text, encoding="utf-8")
        return rc

    @staticmethod
    def append_unix_path(entry: str) -> Path:
        """把 entry 追加到 PATH。"""
        rc = EnvManager._shell_rc_file()
        marker_begin = f"# >>> env-auto-setup:PATH:{entry} >>>"
        marker_end = f"# <<< env-auto-setup:PATH:{entry} <<<"
        line = f'{marker_begin}\nexport PATH="{entry}:$PATH"\n{marker_end}\n'
        text = rc.read_text(encoding="utf-8") if rc.exists() else ""
        if marker_begin in text:
            return rc
        sep = "" if text.endswith("\n") or text == "" else "\n"
        rc.write_text(text + sep + "\n" + line, encoding="utf-8")
        return rc
