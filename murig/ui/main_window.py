# -*- coding: utf-8 -*-
"""主窗口（无边框自定义标题栏）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QApplication, QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea, QSizePolicy,
    QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from ..catalog.registry import FETCHERS, VersionFetchWorker, build_components
from ..core.models import Component
from ..core.constants import (
    APP_NAME, APP_VERSION, CATEGORIES, CATEGORY_ORDER, CONFIG_DIR,
    CURRENT_OS, MACHINE, SETTINGS_FILE,
)
from ..core.workspace import WS
from .dialogs import AboutDialog, DonateDialog, WorkspaceDialog
from .icons import folder_icon
from .theme import apply_theme
from .widgets import ComponentCard


# ---------------------------------------------------------------------------
# 主窗口（无边框自定义标题栏）
# ---------------------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1000, 680)
        self.setMinimumSize(880, 560)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self.components = build_components()
        self._drag_pos: Optional[QPoint] = None
        self._fetch_workers: List[VersionFetchWorker] = []
        self._fetch_pending: int = 0
        # 当前选中的分类 key；搜索关键字直接从搜索框读取
        self._current_category: str = "all"

        self._build_ui()
        self._apply_qss()
        self._load_settings()
        self.refresh_status_bar()
        if WS.migrated:
            self._append_log(
                "info",
                f"设置已从旧工作目录迁移到 {SETTINGS_FILE}（旧文件保留未删除）",
            )
        self._start_fetch_versions()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralRoot")
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ------- 自定义标题栏 -------
        self.title_bar = QFrame()
        self.title_bar.setObjectName("titleBar")
        self.title_bar.setFixedHeight(48)
        tb = QHBoxLayout(self.title_bar)
        tb.setContentsMargins(14, 0, 8, 0)
        tb.setSpacing(6)

        title_label = QLabel(APP_NAME)
        title_label.setObjectName("titleText")
        title_label.setFont(QFont("", 12, QFont.Bold))
        tb.addWidget(title_label)
        tb.addStretch(1)

        # 关于我们
        self.btn_about = QPushButton("💡 关于我们")
        self.btn_about.setObjectName("iconBtn")
        self.btn_about.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_about.setToolTip("了解我们 & 联系方式")
        self.btn_about.clicked.connect(self._on_about_clicked)
        tb.addWidget(self.btn_about)

        # 刷新版本列表按钮
        self.btn_refresh = QPushButton("⟳ 刷新版本")
        self.btn_refresh.setObjectName("iconBtn")
        self.btn_refresh.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_refresh.setToolTip("重新从官网抓取所有组件的可用版本列表")
        self.btn_refresh.clicked.connect(self._start_fetch_versions)
        tb.addWidget(self.btn_refresh)

        # 工作空间设置（图标代码绘制，避免 emoji 缺字形显示为方格）
        self.btn_workspace = QPushButton("工作空间")
        self.btn_workspace.setIcon(folder_icon(14))
        self.btn_workspace.setIconSize(QSize(14, 14))
        self.btn_workspace.setObjectName("iconBtn")
        self.btn_workspace.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_workspace.setToolTip("配置全局 / 分类 / 单组件的安装目录")
        self.btn_workspace.clicked.connect(self._on_workspace_clicked)
        tb.addWidget(self.btn_workspace)

        # 捐赠图标（不在 README 中提及）
        self.btn_donate = QPushButton("♥")
        self.btn_donate.setObjectName("donateBtn")
        self.btn_donate.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_donate.setToolTip("支持作者")
        self.btn_donate.clicked.connect(self._on_donate_clicked)
        tb.addWidget(self.btn_donate)

        # 窗口控制按钮
        self.btn_min = QPushButton("—")
        self.btn_min.setObjectName("ctrlBtn")
        self.btn_min.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_min.clicked.connect(self.showMinimized)
        tb.addWidget(self.btn_min)

        self.btn_max = QPushButton("▢")
        self.btn_max.setObjectName("ctrlBtn")
        self.btn_max.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_max.clicked.connect(self._toggle_max)
        tb.addWidget(self.btn_max)

        self.btn_close = QPushButton("×")
        self.btn_close.setObjectName("closeBtn")
        self.btn_close.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_close.clicked.connect(self.close)
        tb.addWidget(self.btn_close)

        outer.addWidget(self.title_bar)

        # ------- 分类筛选 + 搜索栏 -------
        self.filter_bar = QFrame()
        self.filter_bar.setObjectName("filterBar")
        self.filter_bar.setFixedHeight(52)
        fb = QHBoxLayout(self.filter_bar)
        fb.setContentsMargins(18, 8, 18, 8)
        fb.setSpacing(8)

        self.category_buttons: Dict[str, QPushButton] = {}
        for cat in ["all", *CATEGORY_ORDER]:
            chip = QPushButton(CATEGORIES[cat])
            chip.setObjectName("categoryChip")
            chip.setCheckable(True)
            chip.setChecked(cat == "all")
            chip.setCursor(QCursor(Qt.PointingHandCursor))
            chip.clicked.connect(lambda _=False, c=cat: self._on_category_chosen(c))
            fb.addWidget(chip)
            self.category_buttons[cat] = chip
        fb.addSpacing(10)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("searchBox")
        self.search_box.setPlaceholderText("🔍 搜索软件名 / 别名 / 分类名，例如 redis、数据库、kafka、缓存…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setFixedHeight(34)
        self.search_box.textChanged.connect(self._apply_filter)
        fb.addWidget(self.search_box, stretch=1)

        outer.addWidget(self.filter_bar)

        # ------- 主体：卡片列表 + 日志区 -------
        body = QSplitter(Qt.Vertical)
        body.setObjectName("bodySplitter")

        # 卡片滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("cardsScroll")
        cards_wrap = QWidget()
        cards_wrap.setObjectName("cardsWrap")
        cards_layout = QVBoxLayout(cards_wrap)
        cards_layout.setContentsMargins(18, 18, 18, 18)
        cards_layout.setSpacing(14)

        # 按分类分组：每组一个分区标题，其后是该分类的卡片
        by_cat: Dict[str, List[Component]] = {c: [] for c in CATEGORY_ORDER}
        for comp in self.components:
            by_cat[comp.category].append(comp)

        self.cards: List[ComponentCard] = []
        self._cards_by_cat: Dict[str, List[ComponentCard]] = {c: [] for c in CATEGORY_ORDER}
        self.section_headers: Dict[str, QLabel] = {}
        for cat in CATEGORY_ORDER:
            comps = by_cat[cat]
            if not comps:
                continue
            header = QLabel(f"{CATEGORIES[cat]}（{len(comps)}）")
            header.setObjectName("sectionHeader")
            cards_layout.addWidget(header)
            self.section_headers[cat] = header
            for comp in comps:
                card = ComponentCard(comp, self._append_log)
                cards_layout.addWidget(card)
                self.cards.append(card)
                self._cards_by_cat[cat].append(card)
        cards_layout.addStretch(1)
        scroll.setWidget(cards_wrap)
        body.addWidget(scroll)

        # 日志
        log_wrap = QWidget()
        log_wrap.setObjectName("logWrap")
        log_layout = QVBoxLayout(log_wrap)
        log_layout.setContentsMargins(18, 6, 18, 18)
        log_layout.setSpacing(6)
        log_title = QLabel("运行日志")
        log_title.setStyleSheet("font-weight:600;color:#333;")
        log_layout.addWidget(log_title)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("logView")
        log_layout.addWidget(self.log_view)
        body.addWidget(log_wrap)

        body.setStretchFactor(0, 3)
        body.setStretchFactor(1, 2)
        outer.addWidget(body, stretch=1)

        # 底部状态条：左侧系统信息，右侧版本号
        self.status_bar = QFrame()
        self.status_bar.setObjectName("statusBar")
        self.status_bar.setFixedHeight(26)
        sb = QHBoxLayout(self.status_bar)
        sb.setContentsMargins(14, 0, 14, 0)
        sb.setSpacing(0)
        self.status_left = QLabel()
        self.status_left.setStyleSheet("color:#9aa0ad;background:none;border:none;")
        sb.addWidget(self.status_left)
        sb.addStretch(1)
        status_version = QLabel(f"版本号 {APP_VERSION}")
        status_version.setStyleSheet("color:#9aa0ad;background:none;border:none;")
        sb.addWidget(status_version)
        outer.addWidget(self.status_bar)

    # ------------------------------------------------------------------
    def _apply_qss(self) -> None:
        """应用 QSS 样式表。"""
        self.setStyleSheet(
            """
            #centralRoot {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #eef2f7, stop:1 #dee5ee);
            }
            #titleBar {
                background: #2c3e50;
                color: white;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            #titleText { color: white; padding-left: 4px; }
            #iconBtn, #donateBtn, #ctrlBtn, #closeBtn {
                background: transparent;
                color: white;
                border: none;
                padding: 6px 12px;
                font-size: 14px;
                border-radius: 6px;
            }
            #iconBtn:hover, #ctrlBtn:hover, #donateBtn:hover {
                background: rgba(255,255,255,0.15);
            }
            #donateBtn { color: #ff8181; font-size: 18px; }
            #closeBtn:hover { background: #e74c3c; }

            /* ----------------- 分类筛选 / 搜索栏 ----------------- */
            #filterBar {
                background: rgba(255,255,255,0.75);
                border-bottom: 1px solid #dde3ea;
            }
            QPushButton#categoryChip {
                background: #ffffff;
                color: #546e7a;
                border: 1px solid #cfd8dc;
                border-radius: 15px;
                padding: 6px 14px;
                font-size: 12px;
            }
            QPushButton#categoryChip:hover {
                border-color: #90caf9;
                color: #1976d2;
            }
            QPushButton#categoryChip:checked {
                background: #1976d2;
                color: white;
                border-color: #1976d2;
                font-weight: 600;
            }
            #searchBox {
                background: white;
                border: 1px solid #cfd8dc;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                color: #263238;
            }
            #searchBox:hover { border-color: #90caf9; }
            #searchBox:focus { border-color: #1976d2; }
            #sectionHeader {
                color: #37474f;
                font-size: 14px;
                font-weight: 700;
                padding: 4px 2px;
            }

            #cardsScroll { border: none; background: transparent; }
            #cardsWrap { background: transparent; }
            #card {
                background: white;
                border-radius: 12px;
                border: 1px solid #e6ebf1;
            }
            #cardTitle { color: #263238; }
            #statusLabel { font-size: 12px; }
            #fieldLabel { color:#546e7a; font-size:13px; }

            /* ----------------- 下拉框 ----------------- */
            QComboBox {
                padding: 0 34px 0 12px;
                border: 1px solid #cfd8dc;
                border-radius: 8px;
                background: white;
                color: #263238;
                font-size: 13px;
                min-height: 32px;
                selection-background-color: #1976d2;
            }
            QComboBox:hover  { border-color: #90caf9; }
            QComboBox:focus  { border-color: #1976d2; }
            QComboBox:on     { border-color: #1976d2; }
            QComboBox QLineEdit {
                border: none;
                background: transparent;
                padding: 0;
                margin: 0;
                color: #263238;
                font-size: 13px;
                selection-background-color: #1976d2;
                selection-color: white;
            }
            QComboBox QLineEdit:focus { outline: none; }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 30px;
                border: none;
                background: transparent;
            }
            QComboBox::down-arrow {
                image: none;
                width: 0;
                height: 0;
            }
            #comboArrow {
                color: #78909c;
                font-size: 14px;
                background: transparent;
                border: none;
                padding-right: 6px;
            }
            QComboBox:hover #comboArrow { color: #1976d2; }
            QComboBox:focus #comboArrow { color: #1976d2; }
            QComboBox QAbstractItemView {
                border: 1px solid #cfd8dc;
                border-radius: 8px;
                background: white;
                padding: 6px;
                outline: 0;
                selection-background-color: #1976d2;
                selection-color: white;
            }
            QComboBox QAbstractItemView::item {
                padding: 8px 14px;
                border-radius: 6px;
                min-height: 24px;
                color: #263238;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #e3f2fd;
                color: #0d47a1;
            }
            QComboBox QAbstractItemView::item:selected {
                background: #1976d2;
                color: white;
            }

            QPushButton#primaryBtn {
                background: #1976d2;
                color: white;
                border: none;
                padding: 6px 18px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton#primaryBtn:hover { background: #1e88e5; }
            QPushButton#primaryBtn:pressed { background: #1565c0; }
            QPushButton#primaryBtn:disabled { background: #b0bec5; color:#eceff1; }

            QPushButton#secondaryBtn {
                background: #ffffff;
                color: #1976d2;
                border: 1px solid #1976d2;
                padding: 6px 16px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton#secondaryBtn:hover { background: #e3f2fd; }
            QPushButton#secondaryBtn:pressed { background: #bbdefb; }
            QPushButton#secondaryBtn:disabled {
                color: #b0bec5;
                border-color: #cfd8dc;
                background: #f5f7fa;
            }

            QPushButton#dangerBtn {
                background: #ffffff;
                color: #c62828;
                border: 1px solid #c62828;
                padding: 6px 16px;
                border-radius: 8px;
                font-size: 13px;
            }
            QPushButton#dangerBtn:hover { background: #ffebee; }
            QPushButton#dangerBtn:disabled { color:#e0a4a4; border-color:#e0a4a4; }

            QProgressBar {
                background: #eceff1;
                border: none;
                border-radius: 6px;
                height: 14px;
                text-align: center;
                color: #263238;
                font-size: 11px;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #26c6da, stop:1 #1976d2);
            }

            #logWrap { background: transparent; }
            #logView {
                background: #1e1e2e;
                color: #dcdcdc;
                border-radius: 8px;
                padding: 6px;
                font-family: Menlo, Consolas, "Courier New", monospace;
                font-size: 12px;
            }
            #statusBar {
                background: #eceff1;
                color: #455a64;
                font-size: 12px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 3px 0;
            }
            QScrollBar::handle:vertical {
                background: #e53935;
                border-radius: 3px;
                min-height: 24px;
            }
            QScrollBar::handle:vertical:hover { background: #c62828; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

            QScrollBar:horizontal {
                background: transparent;
                height: 6px;
                margin: 0 3px;
            }
            QScrollBar::handle:horizontal {
                background: #e53935;
                border-radius: 3px;
                min-width: 24px;
            }
            QScrollBar::handle:horizontal:hover { background: #c62828; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

            QToolTip {
                background: #37474f;
                color: white;
                border: 1px solid #263238;
                padding: 6px 10px;
                border-radius: 6px;
            }
            """
        )

    # ------------------------------------------------------------------
    # 无边框窗口拖动
    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.title_bar.underMouse():
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        if self.title_bar.underMouse():
            self._toggle_max()

    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self.btn_max.setText("▢")
        else:
            self.showMaximized()
            self.btn_max.setText("❐")

    # ------------------------------------------------------------------
    # 分类筛选 & 搜索
    # ------------------------------------------------------------------
    def _on_category_chosen(self, cat: str) -> None:
        """点击分类胶囊：更新选中态并重新过滤卡片。"""
        self._current_category = cat
        for c, chip in self.category_buttons.items():
            chip.setChecked(c == cat)
        self._apply_filter()

    def _match_keyword(self, comp: Component, keyword: str) -> bool:
        """关键字在 显示名 / key / 分类名 / 别名 中做大小写不敏感的包含匹配。"""
        haystack = [comp.display_name, comp.key, CATEGORIES.get(comp.category, ""), *comp.aliases]
        return any(keyword in str(x).lower() for x in haystack)

    def _apply_filter(self) -> None:
        """分类与关键字取交集；某个分类下没有可见卡片时连分区标题一起隐藏。"""
        keyword = self.search_box.text().strip().lower()
        for cat, header in self.section_headers.items():
            any_visible = False
            for card in self._cards_by_cat[cat]:
                ok_category = self._current_category in ("all", cat)
                ok_keyword = (not keyword) or self._match_keyword(card.component, keyword)
                visible = ok_category and ok_keyword
                card.setVisible(visible)
                if visible:
                    any_visible = True
            header.setVisible(any_visible)

    # ------------------------------------------------------------------
    def _start_fetch_versions(self) -> None:
        """从各官网并发拉取版本列表。可反复调用（刷新）。"""
        # 若有 worker 仍在运行，等它跑完再触发新一轮
        alive = [w for w in self._fetch_workers if w.isRunning()]
        if alive:
            self._append_log("warn", f"仍有 {len(alive)} 个抓取任务在进行，请稍候…")
            return
        # 清理已完成的 worker
        for w in self._fetch_workers:
            w.deleteLater()
        self._fetch_workers.clear()

        if hasattr(self, "btn_refresh"):
            self.btn_refresh.setEnabled(False)
            self.btn_refresh.setText("⟳ 抓取中…")
        self._fetch_pending = 0
        self._append_log("info", "正在从各官网获取最新版本列表…")
        for card in self.cards:
            fetcher = FETCHERS.get(card.component.key)
            if not fetcher:
                continue
            w = VersionFetchWorker(card.component.key, fetcher, self)
            w.done.connect(self._on_versions_fetched)
            self._fetch_workers.append(w)
            self._fetch_pending += 1
            w.start()

    def _on_versions_fetched(self, key: str, versions) -> None:
        card = next((c for c in self.cards if c.component.key == key), None)
        if card:
            if versions is None:
                self._append_log("warn", f"[{card.component.display_name}] 官网版本获取失败，使用内置默认列表")
            else:
                card.set_versions(versions)
        self._fetch_pending -= 1
        if self._fetch_pending <= 0 and hasattr(self, "btn_refresh"):
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("⟳ 刷新版本")
            self._append_log("info", "版本列表获取完成。")

    # ------------------------------------------------------------------
    def _on_donate_clicked(self) -> None:
        DonateDialog(self).exec()

    # ------------------------------------------------------------------
    def _on_about_clicked(self) -> None:
        AboutDialog(self).exec()

    # ------------------------------------------------------------------
    def _on_workspace_clicked(self) -> None:
        names = {c.key: c.display_name for c in self.components}
        dlg = WorkspaceDialog(self, self._append_log, names)
        if dlg.exec() == QDialog.Accepted:
            # 有过修改：刷新全部卡片徽章与安装位置提示
            for card in self.cards:
                card._detect_status()
            self.refresh_status_bar()

    # ------------------------------------------------------------------
    def refresh_status_bar(self) -> None:
        self.status_left.setText(
            f"系统：{CURRENT_OS} ({MACHINE})   工作目录：{WS.global_ws or CONFIG_DIR}"
            "（可在「工作空间」修改）"
        )

    # ------------------------------------------------------------------
    def _append_log(self, level: str, msg: str) -> None:
        color = {
            "info": "#dcdcdc",
            "ok": "#7CFC7C",
            "warn": "#FFB347",
            "error": "#FF6B6B",
        }.get(level, "#dcdcdc")
        self.log_view.append(f'<span style="color:{color};">{msg}</span>')

    # ------------------------------------------------------------------
    def _load_settings(self) -> None:
        """加载上次选择的版本。"""
        if not SETTINGS_FILE.exists():
            return
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            selections = data.get("selections", {})
            for card in self.cards:
                v = selections.get(card.component.key)
                if v:
                    idx = card.version_combo.findText(v)
                    if idx >= 0:
                        card.version_combo.setCurrentIndex(idx)
        except Exception:
            pass

    def _save_settings(self) -> None:
        # 与 workspace 段同存于 ~/.murig/config.json
        WS.save({
            card.component.key: card.version_combo.currentText()
            for card in self.cards
        })

    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)
