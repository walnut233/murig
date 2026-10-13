# -*- coding: utf-8 -*-
"""可复用 UI 控件：可搜索下拉框、组件卡片。"""

from __future__ import annotations

import os
import shutil
import subprocess
import traceback
from pathlib import Path, PurePosixPath
from typing import Callable, List, Optional
from urllib.parse import urlparse

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction, QColor, QCursor, QFontMetrics, QPainter, QPainterPath, QPen,
)
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QFileDialog, QFrame, QHBoxLayout, QLabel, QMenu,
    QMessageBox, QProgressBar, QPushButton, QSizePolicy, QVBoxLayout,
)

from ..core.archive import extract_archive, extract_rpm
from ..core.constants import CURRENT_OS
from ..core.env import EnvManager
from ..core.models import Component, ComponentVersion
from ..core.utils import ensure_dir, human_size
from ..core.workers import CommandWorker, DownloadWorker
from ..core.workspace import WS
from .icons import folder_icon


# ---------------------------------------------------------------------------
# UI 组件：可搜索下拉框
# ---------------------------------------------------------------------------
class SearchableComboBox(QComboBox):
    """支持关键字过滤的下拉框。

    交互设计：
    - 点击输入框任意位置 → 弹出下拉列表（默认显示全部）
    - 输入关键字 → 实时过滤下拉列表中的项
    - 点击某项即选中（也可按回车 / 上下键选择）
    - 无效输入 → 失焦时回滚到上一次选中的值
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)  # 用户输入不添加到列表
        self.lineEdit().setPlaceholderText("点击选择或输入关键字…")

        # 自定义下拉箭头 —— 用 QLabel 显示 unicode 字符，避免 CSS border-hack 渲染问题
        # WA_TransparentForMouseEvents 使鼠标事件穿透到底层 QComboBox drop-down 区域，
        # 让 Qt 自己处理 toggle（点击展开、再次点击关闭），我们不干预。
        self._arrow_label = QLabel("▾", self)
        self._arrow_label.setObjectName("comboArrow")
        self._arrow_label.setAlignment(Qt.AlignCenter)
        self._arrow_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._arrow_label.setFixedWidth(28)

        # 在 lineEdit 上安装 event filter：点击文本区时也弹出下拉
        self.lineEdit().installEventFilter(self)

        # completer：让 QCompleter 也做 contains 匹配（无所谓，主要靠 view 过滤）
        completer = QCompleter(self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        completer.setModel(self.model())
        # 不使用 completer 的独立 popup，直接使用 combo 自带 view，避免视觉重叠
        self.setCompleter(None)

        # 记录当前有效选中项
        self._committed_text: str = ""

        # 连接信号
        self.currentIndexChanged.connect(self._on_index_changed)
        self.lineEdit().textEdited.connect(self._on_text_edited)
        self.lineEdit().editingFinished.connect(self._restore_if_invalid)

    # ------------------------------------------------------------------
    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        # 让箭头 label 始终贴在右侧
        w = self._arrow_label.width()
        self._arrow_label.setGeometry(self.width() - w - 2, 0, w, self.height())

    # ------------------------------------------------------------------
    def eventFilter(self, obj, event) -> bool:
        """点击输入框任何位置 → 弹出下拉。

        直接在 MousePress 阶段接管事件（return True），不让 QLineEdit 后续
        的 press/release 处理进入 QComboBox 内部的 toggle 逻辑 —— 那会导致
        我们刚弹出的 popup 被立即隐藏。
        """
        if obj is self.lineEdit() and event.type() == QEvent.MouseButtonPress:
            self.lineEdit().setFocus()
            if self.view().isVisible():
                self.hidePopup()
            else:
                self.showPopup()
            return True  # 吞掉事件，QLineEdit 不再处理
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    def focusInEvent(self, e) -> None:
        super().focusInEvent(e)
        # 全选文本，方便直接输入替换
        self.lineEdit().selectAll()

    # ------------------------------------------------------------------
    def showPopup(self) -> None:  # noqa: D401
        """展开前先按当前输入过滤，空输入则展示全部。"""
        text = self.lineEdit().text().strip()
        if not text or text == self._committed_text:
            self._set_all_items_visible()
        else:
            self._filter_items(text)
        self._arrow_label.setText("▴")
        super().showPopup()

    # ------------------------------------------------------------------
    def hidePopup(self) -> None:  # noqa: D401
        self._arrow_label.setText("▾")
        super().hidePopup()

    # ------------------------------------------------------------------
    def _on_text_edited(self, text: str) -> None:
        """用户在输入框中键入时：实时过滤 + 展开下拉。"""
        # 展开下拉（若尚未展开）
        if not self.view().isVisible():
            super().showPopup()
        # 过滤
        keyword = text.strip()
        if not keyword:
            self._set_all_items_visible()
        else:
            self._filter_items(keyword)

    # ------------------------------------------------------------------
    def _filter_items(self, keyword: str) -> None:
        keyword = keyword.lower()
        view = self.view()
        first_visible = -1
        for i in range(self.count()):
            visible = keyword in self.itemText(i).lower()
            view.setRowHidden(i, not visible)
            if visible and first_visible < 0:
                first_visible = i
        # 把第一条匹配项高亮，方便回车直接选中
        if first_visible >= 0:
            view.setCurrentIndex(self.model().index(first_visible, 0))

    def _set_all_items_visible(self) -> None:
        view = self.view()
        for i in range(self.count()):
            view.setRowHidden(i, False)

    # ------------------------------------------------------------------
    def _on_index_changed(self, idx: int) -> None:
        if idx >= 0:
            self._committed_text = self.itemText(idx)

    def _restore_if_invalid(self) -> None:
        """失焦时若输入内容并不精确匹配某项，则回滚到上一次选中值。"""
        text = self.lineEdit().text().strip()
        for i in range(self.count()):
            if self.itemText(i).lower() == text.lower():
                self.setCurrentIndex(i)
                return
        if self._committed_text:
            self.lineEdit().setText(self._committed_text)

    # ------------------------------------------------------------------
    def repopulate(self, items: List[str], preferred: Optional[str] = None) -> None:
        """清空后重新加载列表；尽量保持之前选中值。"""
        prev = preferred or self.currentText()
        self.blockSignals(True)
        self.clear()
        self.addItems(items)
        idx = self.findText(prev) if prev else -1
        self.setCurrentIndex(idx if idx >= 0 else 0)
        self.blockSignals(False)
        if self.count():
            self._committed_text = self.currentText()
        self._set_all_items_visible()


# ---------------------------------------------------------------------------
# UI 组件：卡片
# ---------------------------------------------------------------------------
class ComponentCard(QFrame):
    """展示一个组件的卡片。"""

    request_log = Signal(str, str)

    def __init__(self, component: Component, log_cb: Callable[[str, str], None], parent=None) -> None:
        super().__init__(parent)
        self.component = component
        self.log_cb = log_cb
        self.worker: Optional[DownloadWorker] = None
        self.cmd_worker: Optional[CommandWorker] = None
        self._extracted_path: Optional[Path] = None

        self.setObjectName("card")
        self.setFrameShape(QFrame.NoFrame)
        # 说明：这里刻意不使用 QGraphicsDropShadowEffect —— Qt 图形特效会把卡片
        # 整体渲染到带 alpha 的离屏表面，导致卡内文字的亚像素抗锯齿退化为灰度
        # 抗锯齿（发灰、毛边）。
        # 背景 / 边框 / hover 高亮全部由 paintEvent 自绘（QPainter 抗锯齿），
        # 因为 QSS 的圆角边框不做抗锯齿，1px 逻辑边框在 150% 缩放下还会
        # 变成 1.5 物理像素，圆角处锯齿非常明显。
        self._hovered = False
        # 任务代号：每次启动新任务 +1；信号回调携带启动时的代号，
        # 不匹配即为已取消/被替代的旧任务的迟到信号，直接忽略
        self._task_epoch = 0

        self._build_ui()
        self._detect_status()

    # ------------------------------------------------------------------
    def _busy(self) -> bool:
        """是否有下载/命令任务正在运行（以线程真实状态为准）。"""
        return bool(
            (self.worker and self.worker.isRunning())
            or (self.cmd_worker and self.cmd_worker.isRunning())
        )

    def _reset_progress(self) -> None:
        """复位并收起进度条。"""
        self.progress.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")

    # ------------------------------------------------------------------
    # 自绘卡片外观（替代 QSS 边框，圆角平滑无锯齿）
    # ------------------------------------------------------------------
    def enterEvent(self, event) -> None:  # noqa: N802
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # 半径与内缩：留出笔宽空间，避免高缩放下边缘被裁剪
        radius = 13.0
        inset = 0.75
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)

        if self._hovered:
            fill = QColor("#fbfbff")          # 极浅的靛蓝色调
            border = QColor("#818cf8")
            accent = QColor("#c7d2fe")        # 底部落影边
        else:
            fill = QColor("#ffffff")
            border = QColor("#e7ebf2")
            accent = QColor("#eef1f7")

        # 背景
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, radius, radius)

        # 底部“落影边”：裁剪进圆角内，增加层次感（替代 QSS 的 border-bottom）
        painter.save()
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.setClipPath(path)
        painter.setBrush(accent)
        painter.drawRect(QRectF(rect.left(), rect.bottom() - 3.0, rect.width(), 3.0))
        painter.restore()

        # 边框；hover 时叠加一圈内侧光晕（不用 graphics effect，避免文字退化）
        painter.setBrush(Qt.NoBrush)
        if self._hovered:
            glow_pen = QPen(QColor(99, 102, 241, 34), 5.0)
            painter.setPen(glow_pen)
            glow_rect = rect.adjusted(2.5, 2.5, -2.5, -2.5)
            painter.drawRoundedRect(glow_rect, radius - 2.5, radius - 2.5)
            painter.setPen(QPen(border, 1.4))
        else:
            painter.setPen(QPen(border, 1.2))
        painter.drawRoundedRect(rect, radius, radius)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        # 顶部：名称 & 状态
        top = QHBoxLayout()
        top.setSpacing(10)
        title = QLabel(self.component.display_name)
        title.setObjectName("cardTitle")
        # 注意：不要在这里 setFont —— 空家族的 QFont 会绕开全局字体策略
        # （DirectWrite/FullHinting），小字重合成加粗还会发虚；样式交给 QSS
        top.addWidget(title)

        self.status_label = QLabel("检测中…")
        self.status_label.setObjectName("statusLabel")
        top.addWidget(self.status_label)
        top.addStretch(1)
        root.addLayout(top)

        # 中部：版本选择 + 按钮
        mid = QHBoxLayout()
        mid.setSpacing(10)
        version_label = QLabel("版本")
        version_label.setObjectName("fieldLabel")
        version_label.setFixedWidth(36)
        mid.addWidget(version_label)

        self.version_combo = SearchableComboBox()
        self.version_combo.setObjectName("versionCombo")
        self.version_combo.setCursor(QCursor(Qt.PointingHandCursor))
        self._reload_combo_items()
        # 固定宽度，避免抢占按钮空间
        self.version_combo.setFixedWidth(220)
        self.version_combo.setFixedHeight(34)
        self.version_combo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        mid.addWidget(self.version_combo)

        mid.addSpacing(8)

        self.btn_install = QPushButton("安装" if self.component.npm_package else "下载并安装")
        self.btn_install.setObjectName("primaryBtn")
        self.btn_install.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_install.setFixedHeight(34)
        self.btn_install.clicked.connect(self.on_install_clicked)
        mid.addWidget(self.btn_install)

        self.btn_configure = QPushButton("配置环境变量")
        self.btn_configure.setObjectName("secondaryBtn")
        self.btn_configure.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_configure.setFixedHeight(34)
        self.btn_configure.clicked.connect(self.on_configure_clicked)
        mid.addWidget(self.btn_configure)

        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.setObjectName("dangerBtn")
        self.btn_cancel.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_cancel.setFixedHeight(34)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setVisible(False)  # 默认隐藏；开始下载时才显示
        self.btn_cancel.clicked.connect(self.on_cancel_clicked)
        mid.addWidget(self.btn_cancel)

        # 工作空间入口：左键改目录，右键清除该组件的自定义目录
        # 图标为代码绘制（📁 emoji 在部分系统渲染为空白方格）
        self.btn_dir = QPushButton()
        self.btn_dir.setIcon(folder_icon(16))
        self.btn_dir.setIconSize(QSize(16, 16))
        self.btn_dir.setObjectName("secondaryBtn")
        self.btn_dir.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_dir.setFixedSize(34, 34)
        self.btn_dir.clicked.connect(self._on_dir_clicked)
        self.btn_dir.setContextMenuPolicy(Qt.CustomContextMenu)
        self.btn_dir.customContextMenuRequested.connect(self._on_dir_menu)
        mid.addWidget(self.btn_dir)

        mid.addStretch(1)  # 右侧留空，避免下拉框被拉伸
        root.addLayout(mid)

        # 安装位置提示行：跟随工作空间配置实时刷新
        self.dir_label = QLabel()
        self.dir_label.setObjectName("dirHint")
        root.addWidget(self.dir_label)

        # 底部：进度条（仅下载/安装任务进行时显示，平时收起）
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(True)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

    # ------------------------------------------------------------------
    def _show_progress(self) -> None:
        """任务开始：显示进度条。"""
        self.progress.setVisible(True)

    def _finish_progress(self, failed: bool = False) -> None:
        """任务结束：复位并收起进度条。

        成功时保留 2 秒让用户看到 100%，再自动收起；
        期间若用户又启动了新任务则不收起。
        """
        def _reset() -> None:
            if not self._busy():
                self._reset_progress()
        if failed:
            _reset()
        else:
            QTimer.singleShot(2000, _reset)

    # ------------------------------------------------------------------
    def _log(self, level: str, msg: str) -> None:
        self.log_cb(level, f"[{self.component.display_name}] {msg}")

    # ------------------------------------------------------------------
    def refresh_workspace_label(self) -> None:
        """刷新「安装到：…」提示行与 📁 按钮 tooltip（不启动探测子进程）。"""
        comp = self.component
        target = comp.workspace_root() / comp.key
        text = f"安装到：{target}"
        fm = QFontMetrics(self.dir_label.font())
        width = max(self.width() - 80, 120)
        self.dir_label.setText(fm.elidedText(text, Qt.ElideMiddle, width))
        self.dir_label.setToolTip(text)
        tip = f"{text}（点击修改）"
        if comp.key in WS.components:
            tip += "；右键清除该组件的自定义目录"
        self.btn_dir.setToolTip(tip)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "dir_label"):
            self.refresh_workspace_label()

    # ------------------------------------------------------------------
    def _on_dir_clicked(self) -> None:
        """卡片 📁 按钮：为该组件单独指定安装目录（覆盖分类与全局）。"""
        comp = self.component
        current = comp.workspace_root()
        chosen = QFileDialog.getExistingDirectory(
            self, f"选择 {comp.display_name} 的安装目录", str(current)
        )
        if not chosen:
            return
        if Path(chosen) == current:
            # 选回当前解析目录：已有覆盖则视为清除，否则无操作
            if comp.key in WS.components:
                self._clear_dir_override()
            return
        WS.set_component(comp.key, chosen)
        self._log("ok", f"已设置自定义安装目录：{chosen}")
        self.refresh_workspace_label()
        self._detect_status()

    def _on_dir_menu(self, pos) -> None:
        if self.component.key not in WS.components:
            return
        menu = QMenu(self)
        act = QAction("清除自定义目录（回退分类/全局）", self)
        act.triggered.connect(self._clear_dir_override)
        menu.addAction(act)
        menu.exec(self.btn_dir.mapToGlobal(pos))

    def _clear_dir_override(self) -> None:
        comp = self.component
        WS.set_component(comp.key, None)
        self._log("ok", f"已清除自定义目录，回退到 {comp.workspace_root()}")
        self.refresh_workspace_label()
        self._detect_status()

    # ------------------------------------------------------------------
    def _detect_status(self) -> None:
        """检测该组件当前是否已安装、已配置。

        - 若系统 PATH 或 XXX_HOME 已能找到可执行文件，则视为「已配置」，禁用
          「仅配置环境变量」按钮，避免重复写入。
        - 若本地已解压但未配置，则允许点击「仅配置环境变量」。
        - 若未安装，两个按钮均可用。
        """
        self.refresh_workspace_label()
        result = self.component.detect()
        if result.installed:
            # GUI 应用不执行探测（否则会弹窗），版本留空属正常
            ver = result.version_text or "已安装"
            where = result.source or "系统"
            self._set_status("ok", f"✓ 已配置（{where}） · {ver}")
            # 已可用 —— 禁用「仅配置环境变量」按钮
            self.btn_configure.setEnabled(False)
            self.btn_configure.setToolTip(
                f"系统已能检测到 {self.component.display_name}"
                f"（{result.exe_path or where}），无需再次配置。"
            )
            return

        # 尝试查找本地已解压目录（当前工作空间优先，兼容默认根里的旧安装）
        local_found = False
        for root in WS.roots_for(self.component.key, self.component.category):
            install_root = root / self.component.key
            if install_root.exists() and any(
                p for p in install_root.iterdir()
                if p.is_dir() and not p.name.startswith(".") and p.name != "downloads"
            ):
                local_found = True
                break
        if local_found:
            self._set_status("warn", "● 已下载，未配置")
            self.btn_configure.setEnabled(True)
            self.btn_configure.setToolTip("将已下载的版本写入 XXX_HOME 与 PATH")
            return

        self._set_status("idle", "○ 未安装")
        self.btn_configure.setEnabled(True)
        self.btn_configure.setToolTip("将已下载的版本写入 XXX_HOME 与 PATH")

    # ------------------------------------------------------------------
    def _set_status(self, state: str, text: str) -> None:
        """设置状态标签文案，并切换 QSS 属性选择器对应的配色。

        state: ok / warn / idle，对应 theme.qss 中的 #statusLabel[state="..."]。
        """
        label = self.status_label
        label.setText(text)
        label.setProperty("state", state)
        label.style().unpolish(label)
        label.style().polish(label)

    # ------------------------------------------------------------------
    def _display_label(self, cv: ComponentVersion) -> str:
        return getattr(cv, "display_label", None) or cv.version

    def _reload_combo_items(self, preferred: Optional[str] = None) -> None:
        """把 self.component.versions 灌进下拉框。"""
        labels = [self._display_label(v) for v in self.component.versions]
        # 若首次调用（combo 里还没内容），走普通 addItems 路径
        if self.version_combo.count() == 0:
            self.version_combo.blockSignals(True)
            self.version_combo.addItems(labels)
            self.version_combo.setCurrentIndex(0)
            self.version_combo.blockSignals(False)
            self.version_combo._committed_text = self.version_combo.currentText()
            return
        self.version_combo.repopulate(labels, preferred=preferred)

    def set_versions(self, versions: List[ComponentVersion]) -> None:
        """外部（抓取线程）用新版本列表替换现有列表。"""
        if not versions:
            return
        prev_ver = self._current_version().version if self.component.versions else None
        self.component.versions = versions
        preferred_label = None
        if prev_ver:
            for cv in versions:
                if cv.version == prev_ver:
                    preferred_label = self._display_label(cv)
                    break
        self._reload_combo_items(preferred=preferred_label)
        self._log("ok", f"已从官网获取 {len(versions)} 个版本")

    # ------------------------------------------------------------------
    def _current_version(self) -> ComponentVersion:
        """按显示 label 反查真实版本，兼容 SearchableComboBox 的可编辑文本。"""
        text = self.version_combo.currentText().strip()
        for cv in self.component.versions:
            if self._display_label(cv) == text or cv.version == text:
                return cv
        idx = max(0, self.version_combo.currentIndex())
        return self.component.versions[min(idx, len(self.component.versions) - 1)]

    # ------------------------------------------------------------------
    def on_install_clicked(self) -> None:
        cv = self._current_version()

        # npm 便携安装模式（如 Claude Code）：不走下载流程
        if self.component.npm_package:
            self._start_npm_install(cv)
            return

        url = cv.url_for_current()
        if not url:
            self._log("error", f"当前系统 {CURRENT_OS} 无可用下载地址。")
            return

        # 决定下载文件后缀
        if self.component.installer_mode:
            # 从 archive_map 取扩展名（exe / sh），其次从 URL 推断
            ext = cv.archive_map.get(CURRENT_OS, "")
            if not ext:
                if url.endswith(".exe"):
                    ext = "exe"
                elif url.endswith(".sh"):
                    ext = "sh"
                else:
                    ext = "bin"
            suffix = f".{ext}"
        else:
            archive_ext = cv.archive_for_current()
            if archive_ext == "zip":
                suffix = ".zip"
            elif archive_ext == "tar.gz":
                suffix = ".tar.gz"
            elif archive_ext == "tar":
                suffix = ".tar"
            elif archive_ext == "rpm":
                suffix = ".rpm"
            elif archive_ext == "exe":
                suffix = ".exe"
            else:
                # 独立可执行文件（如 AppImage）：保留原始后缀，没有则用 .bin
                suffix = "".join(PurePosixPath(urlparse(url).path).suffixes) or ".bin"

        download_dir = self.component.workspace_root() / self.component.key / "downloads"
        ensure_dir(download_dir)
        dest = download_dir / f"{self.component.key}-{cv.version}{suffix}"

        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        self.progress.setVisible(True)
        self.btn_install.setEnabled(False)
        self.btn_configure.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)

        # 任务代号守卫：取消/重开后，旧任务的迟到信号（progress/fail）直接丢弃，
        # 防止把已复位的进度条又改回旧值（"进度缓存"残留的根因）
        self._task_epoch += 1
        epoch = self._task_epoch

        self.worker = DownloadWorker(url, dest, self.component.download_headers)
        self.worker.progress.connect(
            lambda d, t, e=epoch: self._on_progress(d, t) if e == self._task_epoch else None
        )
        self.worker.log.connect(self._log)
        self.worker.finished_ok.connect(
            lambda p, e=epoch: self._on_download_ok(Path(p), cv) if e == self._task_epoch else None
        )
        self.worker.finished_fail.connect(
            lambda m, e=epoch: self._on_download_fail(m) if e == self._task_epoch else None
        )
        self.worker.start()

    # ------------------------------------------------------------------
    def _on_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self.progress.setValue(int(downloaded * 100 / total))
            self.progress.setFormat(f"{human_size(downloaded)} / {human_size(total)}")
        else:
            # 未知总长度
            self.progress.setRange(0, 0)
            self.progress.setFormat(f"{human_size(downloaded)}")

    # ------------------------------------------------------------------
    def _on_download_ok(self, path: Path, cv: ComponentVersion) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self._finish_progress()
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setVisible(False)

        try:
            target_root = self.component.workspace_root() / self.component.key
            ensure_dir(target_root)
            final = self.component.install_dir(cv.version)

            if self.component.installer_mode:
                # 安装器模式：静默执行安装
                self._log("info", "开始运行安装器（静默安装）…")
                if final.exists():
                    shutil.rmtree(final, ignore_errors=True)
                self._run_installer(path, final)
                self._log("ok", f"安装完成：{final}")
            else:
                archive_ext = cv.archive_for_current()
                if archive_ext == "rpm":
                    # RPM：纯 Python 解析（xz/lzma + cpio newc），直接解到 final
                    self._log("info", "开始解包 RPM（cpio）…")
                    if final.exists():
                        shutil.rmtree(final, ignore_errors=True)
                    ensure_dir(final)
                    extract_rpm(path, final)
                    self._log("ok", f"解包完成：{final}")
                elif archive_ext in ("bin", "exe"):
                    # 独立可执行文件（Linux AppImage / Windows 引导程序 .exe）：放入安装目录
                    if final.exists():
                        shutil.rmtree(final, ignore_errors=True)
                    ensure_dir(final)
                    raw_name = self.component.raw_bin_name or path.name
                    raw = final / raw_name
                    shutil.move(str(path), str(raw))
                    try:
                        raw.chmod(0o755)
                    except OSError:
                        pass
                    self._log("ok", f"可执行文件已就绪：{raw}")
                else:
                    self._log("info", "开始解压…")
                    # 解压到临时目录
                    tmp_dir = target_root / f".extract-{cv.version}"
                    if tmp_dir.exists():
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                    ensure_dir(tmp_dir)
                    root = extract_archive(path, tmp_dir)

                    if final.exists():
                        shutil.rmtree(final, ignore_errors=True)
                    shutil.move(str(root), str(final))
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                    self._log("ok", f"解压完成：{final}")

            # 源码类组件的编译步骤（如 Redis 执行 make）
            if self.component.after_extract:
                self._run_after_extract(final)

            self._extracted_path = final
            # 自动尝试配置环境变量
            self._configure_env(final)
            for note in self.component.post_notes:
                self._log("warn", note)
        except Exception as exc:
            self._log("error", f"安装/配置失败：{exc}\n{traceback.format_exc()}")
        finally:
            self.btn_install.setEnabled(True)
            self.btn_configure.setEnabled(True)
            # _detect_status 会根据探测结果再决定 btn_configure 是否禁用
            self._detect_status()

    # ------------------------------------------------------------------
    def _run_installer(self, installer_path: Path, target_dir: Path) -> None:
        """静默运行安装器（用于 Miniconda 之类）。"""
        comp = self.component
        args = list(comp.installer_args.get(CURRENT_OS, []))
        ensure_dir(target_dir.parent)

        if CURRENT_OS == "Windows":
            # Windows Miniconda: 参数末尾 /D=path 不允许带引号
            cmd = [str(installer_path)] + args + [f"/D={target_dir}"]
            self._log("info", f"运行：{' '.join(cmd)}")
            proc = subprocess.run(cmd, check=False)
        else:
            # macOS / Linux: bash installer.sh -b -f -p <path>
            os.chmod(installer_path, 0o755)
            cmd = ["bash", str(installer_path)] + args + [str(target_dir)]
            self._log("info", f"运行：{' '.join(cmd)}")
            proc = subprocess.run(cmd, check=False, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
            if proc.stdout:
                self._log("info", proc.stdout.strip()[:500])
            if proc.stderr:
                self._log("warn", proc.stderr.strip()[:500])

        if proc.returncode != 0:
            raise RuntimeError(f"安装器返回非零退出码：{proc.returncode}")

    # ------------------------------------------------------------------
    def _run_after_extract(self, home: Path) -> None:
        """在安装目录内依次执行组件声明的编译/初始化命令（失败只告警，不中断流程）。"""
        for raw_cmd in self.component.after_extract or []:
            # 支持 {home} 占位符（如 ./configure --prefix={home}）
            cmd = [arg.replace("{home}", str(home)) for arg in raw_cmd]
            self._log("info", f"执行：{' '.join(cmd)}（目录：{home}）")
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(home),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=900,
                    check=False,
                )
                if proc.stdout:
                    self._log("info", proc.stdout.strip()[:400])
                if proc.stderr:
                    self._log("info", proc.stderr.strip()[:400])
                if proc.returncode != 0:
                    self._log(
                        "warn",
                        f"命令返回非零退出码 {proc.returncode}，可尝试在 {home} 手动执行。",
                    )
            except Exception as exc:
                self._log("warn", f"命令执行失败：{exc}")

    # ------------------------------------------------------------------
    def _on_download_fail(self, msg: str) -> None:
        self.btn_install.setEnabled(True)
        self.btn_configure.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._finish_progress(failed=True)
        if msg and msg != "用户取消":
            QMessageBox.warning(self, "下载失败", f"{self.component.display_name} 下载失败：\n{msg}")

    # ------------------------------------------------------------------
    def _start_npm_install(self, cv: ComponentVersion) -> None:
        """使用本机 npm 把包便携安装到独立目录（不污染全局）。"""
        comp = self.component
        npm = shutil.which("npm.cmd" if CURRENT_OS == "Windows" else "npm") or shutil.which("npm")
        if not npm:
            self._log("error", "未检测到 npm，请先通过本工具安装 Node.js（或自行安装 Node.js）。")
            return
        final = comp.install_dir(cv.version)
        ensure_dir(final)
        spec = f"{comp.npm_package}@{cv.version}"
        args = ["install", "--prefix", str(final), "--no-fund", "--no-audit", spec]
        if CURRENT_OS == "Windows" and npm.lower().endswith((".cmd", ".bat")):
            # .cmd / .bat 不能被 CreateProcess 直接执行，需要经 cmd /c 调起
            cmd = ["cmd", "/c", npm, *args]
        else:
            cmd = [npm, *args]

        # 忙碌状态（npm 安装无精确进度，进度条滚动）
        self.progress.setRange(0, 0)
        self.progress.setFormat("npm 安装中…")
        self.progress.setVisible(True)
        self.btn_install.setEnabled(False)
        self.btn_configure.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.btn_cancel.setEnabled(True)

        self._task_epoch += 1
        epoch = self._task_epoch

        self.cmd_worker = CommandWorker(cmd)
        self.cmd_worker.log.connect(self._log)
        self.cmd_worker.finished_ok.connect(
            lambda _, e=epoch: self._on_npm_ok(final) if e == self._task_epoch else None
        )
        self.cmd_worker.finished_fail.connect(
            lambda m, e=epoch: self._on_command_fail(m) if e == self._task_epoch else None
        )
        self.cmd_worker.start()

    # ------------------------------------------------------------------
    def _on_npm_ok(self, final: Path) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.progress.setFormat("%p%")
        self._finish_progress()
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setVisible(False)
        self._log("ok", f"npm 安装完成：{final}")
        self._extracted_path = final
        self._configure_env(final)
        self.btn_install.setEnabled(True)
        self.btn_configure.setEnabled(True)
        self._detect_status()

    # ------------------------------------------------------------------
    def _on_command_fail(self, msg: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("%p%")
        self._finish_progress(failed=True)
        self.btn_install.setEnabled(True)
        self.btn_configure.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setVisible(False)
        if msg and msg != "用户取消":
            self._log("error", f"命令执行失败：{msg}")

    # ------------------------------------------------------------------
    def on_cancel_clicked(self) -> None:
        cancelled = False
        if self.cmd_worker and self.cmd_worker.isRunning():
            self.cmd_worker.cancel()
            cancelled = True
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            cancelled = True
        if cancelled:
            # 立即复位进度条：不等后台线程收尾（socket 可能阻塞在最后一个
            # chunk 上），避免取消后进度条残留旧的下载值
            self._reset_progress()
            self._log("warn", "正在取消任务…")

    # ------------------------------------------------------------------
    def on_configure_clicked(self) -> None:
        """仅配置环境变量：从本地已存在的安装目录中选择最新一个。

        扫描顺序为当前工作空间优先、默认根兜底，旧位置的安装仍可被配置。
        """
        for root in WS.roots_for(self.component.key, self.component.category):
            install_root = root / self.component.key
            if not install_root.exists():
                continue
            candidates = [p for p in install_root.iterdir() if p.is_dir() and not p.name.startswith(".")
                          and p.name != "downloads"]
            if not candidates:
                continue
            candidates.sort()
            self._configure_env(candidates[-1])
            self._detect_status()
            return
        self._log("warn", "未找到已解压的安装目录，请先执行“下载并安装”。")

    # ------------------------------------------------------------------
    def _configure_env(self, install_path: Path) -> None:
        """根据组件类型写入 XXX_HOME 与 PATH。"""
        try:
            comp = self.component
            bin_dir = install_path / comp.path_subdir
            # 若能在安装目录中找到可执行文件，PATH 以它实际所在目录为准
            exe = comp.exec_path_in_home(str(install_path))
            if exe is not None:
                bin_dir = exe.parent
            if comp.env_var:
                if CURRENT_OS == "Windows":
                    EnvManager.set_windows_user_env(comp.env_var, str(install_path))
                    EnvManager.append_windows_path(str(bin_dir))
                else:
                    rc = EnvManager.set_unix_env(comp.env_var, str(install_path))
                    EnvManager.append_unix_path(str(bin_dir))
                    self._log("info", f"已写入 {rc}")
                self._log("ok", f"设置 {comp.env_var}={install_path}")
                self._log("ok", f"追加 PATH：{bin_dir}")
            else:
                if CURRENT_OS == "Windows":
                    EnvManager.append_windows_path(str(bin_dir))
                else:
                    rc = EnvManager.append_unix_path(str(bin_dir))
                    self._log("info", f"已写入 {rc}")
                self._log("ok", f"追加 PATH：{bin_dir}")

            if CURRENT_OS != "Windows":
                self._log("warn", "请打开新的终端或执行 `source ~/.zshrc` 让环境变量生效。")
            else:
                # Windows 合并 PATH 时系统变量在前：若系统里还装着旧版本，
                # 新开的终端会优先用旧版。这里提示用户处理
                stale = EnvManager.system_path_exec_dirs(comp.exec_name)
                if stale:
                    self._log(
                        "warn",
                        f"系统 PATH 中仍存在 {comp.display_name}：{'、'.join(stale)}"
                        "；新开的终端可能优先使用旧版本，建议从系统 PATH 移除旧条目"
                        "（需管理员权限）",
                    )
        except Exception as exc:
            self._log("error", f"环境变量配置失败：{exc}")
