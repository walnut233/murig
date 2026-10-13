# -*- coding: utf-8 -*-
"""后台线程：文件下载与外部命令执行。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QThread, Signal

from .constants import CURRENT_OS
from .http import get as http_get
from .mirrors import DIRECT, MIRRORS, PROBE_URL
from .utils import ensure_dir, human_size


# ---------------------------------------------------------------------------
# 下载线程
# ---------------------------------------------------------------------------
class DownloadWorker(QThread):
    """使用 requests 流式下载文件的后台线程。"""

    progress = Signal(int, int)  # (downloaded_bytes, total_bytes)
    log = Signal(str, str)  # (level, message)  level in {"info","warn","error","ok"}
    finished_ok = Signal(str)  # 保存的本地文件绝对路径
    finished_fail = Signal(str)  # 错误信息

    def __init__(self, url: str, dest: Path, headers: Optional[Dict[str, str]] = None,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.url = url
        self.dest = dest
        self.headers = headers or None
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    # ------------------------------------------------------------------
    def _channels(self) -> List[Tuple[str, str]]:
        """按优先级给出下载通道 [(名称, URL)]：镜像在前，直连兜底。"""
        mirrors = MIRRORS.candidates(self.url)
        if MIRRORS.mode in ("auto", "") and not MIRRORS.fastest_for(self.url):
            # 首次使用：对真实 URL 抽样测速，自动挑最快的通道
            best = MIRRORS.auto_select(
                self.url, on_note=lambda lv, m: self.log.emit(lv, m)
            )
            if best is not None:
                mirrors = [best, DIRECT]
        return [
            (f"镜像 {m.name}" if m.id != "direct" else "直连", m.url_for(self.url))
            for m in mirrors
        ]

    def _download(self, url: str, note_prefix: str) -> bool:
        """从指定通道下载；失败抛异常，由 run() 切换到下一个通道。"""
        self.log.emit("info", f"开始下载（{note_prefix}）：{url}")
        ensure_dir(self.dest.parent)
        # 走统一入口：MITM 代理/加速器导致证书校验失败时会自动降级重试
        r = http_get(
            url, timeout=30, headers=self.headers, stream=True,
            allow_redirects=True,
            on_note=lambda m: self.log.emit("warn", m),
        )
        with r:
            # 响应阶段也可能收到取消（下载循环开始前只有这里能响应）
            if self._cancel:
                self.log.emit("warn", "已取消下载。")
                self.finished_fail.emit("用户取消")
                return True
            total = int(r.headers.get("Content-Length", 0))
            downloaded = 0
            tmp = self.dest.with_suffix(self.dest.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if self._cancel:
                        self.log.emit("warn", "已取消下载。")
                        f.close()
                        tmp.unlink(missing_ok=True)
                        self.finished_fail.emit("用户取消")
                        return True
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(downloaded, total)
            tmp.replace(self.dest)
        self.log.emit("ok", f"下载完成：{self.dest} ({human_size(self.dest.stat().st_size)})")
        self.finished_ok.emit(str(self.dest))
        return True

    def run(self) -> None:  # noqa: D401
        try:
            channels = self._channels()
            if self._cancel:
                self.log.emit("warn", "已取消下载。")
                self.finished_fail.emit("用户取消")
                return
            last_exc: Optional[Exception] = None
            for idx, (label, url) in enumerate(channels):
                try:
                    self._download(url, label)
                    return
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    if idx + 1 < len(channels):
                        self.log.emit("warn", f"通道「{label}」下载失败，切换下一个：{exc}")
            assert last_exc is not None
            raise last_exc
        except Exception as exc:  # pragma: no cover
            self.log.emit("error", f"下载失败：{exc}")
            self.finished_fail.emit(str(exc))


class MirrorProbeWorker(QThread):
    """镜像测速线程（供设置界面使用），完成后给出各通道速度。"""

    done = Signal(object)  # [(id, 名称, KB/s)]，按速度降序，失败为 -1

    def __init__(self, url: Optional[str] = None,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.url = url

    def run(self) -> None:  # noqa: D401
        self.done.emit(MIRRORS.probe(self.url or PROBE_URL))


class CommandWorker(QThread):
    """在后台执行外部命令（如 npm 便携安装），并把输出实时转发到日志。"""

    log = Signal(str, str)  # (level, message)
    finished_ok = Signal(str)
    finished_fail = Signal(str)

    def __init__(self, cmd: List[str], cwd: Optional[Path] = None,
                 parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.cmd = cmd
        self.cwd = str(cwd) if cwd else None
        self._proc: Optional[subprocess.Popen] = None
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True
        if self._proc is not None and self._proc.poll() is None:
            try:
                if CURRENT_OS == "Windows":
                    self._proc.terminate()
                else:
                    import signal
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except Exception:
                pass

    def run(self) -> None:  # noqa: D401
        try:
            self.log.emit("info", f"执行：{' '.join(self.cmd)}（目录：{self.cwd or os.getcwd()}）")
            kwargs = dict(
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.cwd,
                encoding="utf-8",
                errors="replace",
            )
            if CURRENT_OS != "Windows":
                kwargs["start_new_session"] = True
            self._proc = subprocess.Popen(self.cmd, **kwargs)
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                text = line.rstrip()
                if text:
                    self.log.emit("info", text[:500])
            code = self._proc.wait()
            if self._cancel:
                self.finished_fail.emit("用户取消")
                return
            if code != 0:
                self.finished_fail.emit(f"命令返回非零退出码：{code}")
                return
            self.finished_ok.emit("")
        except Exception as exc:  # pragma: no cover
            self.log.emit("error", f"命令执行失败：{exc}")
            self.finished_fail.emit(str(exc))
