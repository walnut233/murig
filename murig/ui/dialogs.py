# -*- coding: utf-8 -*-
"""对话框：关于、设置。"""

from __future__ import annotations

from typing import Dict

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCursor, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..core.constants import CATEGORIES, CATEGORY_ORDER, CONFIG_DIR
from ..core.mirrors import MIRRORS, PRESETS
from ..core.settings import INSTALL
from ..core.utils import human_size, open_in_file_manager
from ..core.workers import MirrorProbeWorker
from ..core.workspace import WS
from ..resources import icon_path
from .widgets import ToggleSwitch


class NoWheelComboBox(QComboBox):
    """未下拉时忽略滚轮：防止在滚动页面时光标扫过下拉框误改选中项。"""

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


# ---------------------------------------------------------------------------
# 关于我们弹窗
# ---------------------------------------------------------------------------
class AboutDialog(QDialog):
    """关于我们：团队介绍 + QQ/微信群/微信联系方式。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("关于我们")
        self.setObjectName("aboutDialog")
        self._build_ui()
        # 内容变长（含支持作者区块）后可能超出屏幕：宽高按内容自适应，
        # 超出屏幕的部分交给滚动条
        hint = self._body.sizeHint()
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            max_w, max_h = int(avail.width() * 0.94), int(avail.height() * 0.9)
        else:
            max_w, max_h = 1000, 860
        # 940：保证 2x2 联系卡完整展示；内容更高时交给滚动条
        self.resize(min(max(940, hint.width()), max_w),
                    min(hint.height() + 12, max(520, max_h)))

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._body = QWidget()
        outer.addWidget(scroll)

        v = QVBoxLayout(self._body)
        v.setContentsMargins(36, 28, 36, 24)
        v.setSpacing(10)
        scroll.setWidget(self._body)

        # 应用图标（与窗口 / 任务栏同一个 icon.ico）
        logo = QLabel()
        logo.setObjectName("aboutLogo")
        logo.setAlignment(Qt.AlignCenter)
        icon_file = icon_path()
        if icon_file.exists():
            pm = QIcon(str(icon_file)).pixmap(72, 72)
            if not pm.isNull():
                logo.setPixmap(pm)
        v.addWidget(logo, alignment=Qt.AlignHCenter)
        v.addSpacing(6)

        # ABOUT US 胶囊
        pill = QLabel("ABOUT US")
        pill.setAlignment(Qt.AlignCenter)
        pill.setFixedSize(120, 34)
        pill.setObjectName("aboutPill")
        v.addWidget(pill, alignment=Qt.AlignHCenter)

        title = QLabel("关于我们")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("aboutTitle")
        v.addWidget(title)

        subtitle = QLabel("一群因为热爱而聚在一起的开源爱好者")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setObjectName("aboutSubtitle")
        v.addWidget(subtitle)
        v.addSpacing(8)

        # 项目溯源：本工具由开源项目 MuRig 二次开发而来
        origin = QFrame()
        origin.setObjectName("aboutCard")
        ol = QVBoxLayout(origin)
        ol.setContentsMargins(32, 22, 32, 20)
        ol.setSpacing(8)

        origin_heading = QLabel("项目溯源")
        origin_heading.setObjectName("aboutHeading")
        ol.addWidget(origin_heading)

        origin_text = QLabel(
            "本工具基于开源项目 "
            '<a href="https://github.com/vfaner/murig" style="color:#5b5bd6;'
            'text-decoration:none;font-weight:600;">MuRig v1.2.0 ↗</a>'
            " 制作演变而来：沿用其组件装配与环境配置的核心能力，并在此基础上"
            "新增、修复了部分功能，让下载安装与环境配置更顺手省心。<br><br>"
            "以下是原作者的「关于我们」内容："
        )
        origin_text.setWordWrap(True)
        origin_text.setOpenExternalLinks(True)
        origin_text.setToolTip("https://github.com/vfaner/murig")
        origin_text.setObjectName("aboutText")
        ol.addWidget(origin_text)

        v.addWidget(origin)
        v.addSpacing(12)

        # 介绍卡片
        card = QFrame()
        card.setObjectName("aboutCard")

        cl = QVBoxLayout(card)
        cl.setContentsMargins(32, 26, 32, 22)
        cl.setSpacing(14)

        heading = QLabel("我们致力于开源项目")
        heading.setObjectName("aboutHeading")
        cl.addWidget(heading)

        p1 = QLabel(
            "我们是一群开源爱好者，专注于分享实用、开箱即用的小工具，"
            "希望能帮你在日常工作中少写一点重复代码、少踩一点坑。"
        )
        p1.setWordWrap(True)
        p1.setObjectName("aboutText")
        cl.addWidget(p1)

        # 产品矩阵导流：点击在浏览器打开 nav.qqmu.com
        p_nav = QLabel(
            '更多开箱即用的小工具（MuOpt、MuAsk、JArgus、Jync 等），'
            '欢迎逛逛我们的产品导航：'
            '<a href="https://nav.qqmu.com" style="color:#5b5bd6;'
            'text-decoration:none;font-weight:600;">nav.qqmu.com ↗</a>'
        )
        p_nav.setWordWrap(True)
        p_nav.setCursor(QCursor(Qt.PointingHandCursor))
        p_nav.setObjectName("aboutText")
        p_nav.linkActivated.connect(
            lambda url: QDesktopServices.openUrl(QUrl(url))
        )
        cl.addWidget(p_nav)

        p2 = QLabel(
            "如果你有更好的建议或想法，想提需求，或者在使用中遇到软件上的问题，"
            "欢迎随时通过下面的方式联系我们 —— 每一条反馈我们都会认真看："
        )
        p2.setWordWrap(True)
        p2.setObjectName("aboutText")
        cl.addWidget(p2)

        # 联系方式 2x2（两行水平布局）
        def contact_row(left_item, right_item) -> QHBoxLayout:
            r = QHBoxLayout()
            r.setSpacing(16)
            r.addWidget(left_item)
            r.addWidget(right_item)
            return r

        cl.addLayout(contact_row(
            self._make_contact_item(
                badge=("QQ", "#e9e8fc", "#5b5bd6"),
                caption="QQ ①",
                value="817094",
                btn_text="点击对话 ↗",
                on_click=lambda: self._open_qq_chat("817094"),
            ),
            self._make_contact_item(
                badge=("QQ", "#e9e8fc", "#5b5bd6"),
                caption="QQ ②",
                value="2912167928",
                btn_text="点击对话 ↗",
                on_click=lambda: self._open_qq_chat("2912167928"),
            ),
        ))
        cl.addSpacing(14)
        cl.addLayout(contact_row(
            self._make_contact_item(
                badge=("群", "#fbeedd", "#d98c2b"),
                caption="QQ 群（点击加群）",
                value="426669837",
                btn_text="点击加群 ↗",
                on_click=lambda: self._copy_contact(
                    "426669837", "QQ 群号已复制，请在 QQ 中搜索群号加入"
                ),
            ),
            self._make_contact_item(
                badge=("微", "#dcf4f4", "#16a3a3"),
                caption="微信（点击复制）",
                value="qqmu66",
                btn_text="复制微信号",
                on_click=lambda: self._copy_contact(
                    "qqmu66", "微信号 qqmu66 已复制，请到微信中添加好友"
                ),
            ),
        ))

        # 操作反馈
        self.hint_label = QLabel("")
        self.hint_label.setWordWrap(True)
        self.hint_label.setAlignment(Qt.AlignCenter)
        self.hint_label.setObjectName("aboutHint")
        cl.addWidget(self.hint_label)

        v.addWidget(card)

    def _make_contact_item(
        self,
        badge: tuple,
        caption: str,
        value: str,
        btn_text: str,
        on_click,
    ) -> QFrame:
        """构造一个联系方式条目（图标 + 名称 + 操作按钮）。"""
        item = QFrame()
        item.setObjectName("contactItem")
        item.setFixedHeight(86)

        h = QHBoxLayout(item)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(12)

        badge_text, badge_bg, badge_fg = badge
        badge_lbl = QLabel(badge_text)
        badge_lbl.setFixedSize(46, 46)
        badge_lbl.setAlignment(Qt.AlignCenter)
        badge_lbl.setObjectName("contactBadge")
        badge_lbl.setStyleSheet(f"background:{badge_bg};color:{badge_fg};")
        h.addWidget(badge_lbl)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        caption_lbl = QLabel(caption)
        caption_lbl.setObjectName("contactCaption")
        value_lbl = QLabel(value)
        value_lbl.setObjectName("contactValue")
        text_col.addWidget(caption_lbl)
        text_col.addWidget(value_lbl)
        h.addLayout(text_col)
        h.addStretch(1)

        btn = QPushButton(btn_text)
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setObjectName("secondaryBtn")
        btn.clicked.connect(on_click)
        h.addWidget(btn)
        return item

    # ------------------------------------------------------------------
    def _copy_to_clipboard(self, text: str) -> None:
        QApplication.clipboard().setText(text)

    def _copy_contact(self, text: str, hint: str) -> None:
        self._copy_to_clipboard(text)
        self.hint_label.setText(f"✓ {hint}：{text}")

    def _open_qq_chat(self, uin: str) -> None:
        """唤起 QQ 临时会话；同时复制 QQ 号，QQ 未安装时可手动添加。"""
        self._copy_to_clipboard(uin)
        QDesktopServices.openUrl(QUrl(f"tencent://message/?uin={uin}&Site=&Menu=yes"))
        self.hint_label.setText(f"✓ 正在唤起 QQ 对话（QQ 号 {uin} 已复制，可手动添加）")


# ---------------------------------------------------------------------------
# 设置对话框
# ---------------------------------------------------------------------------
class WorkspaceDialog(QDialog):
    """设置：工作空间目录 + 下载通道 + 安装选项 + 安装包清理。

    修改即时生效并落盘；关闭时若有过修改则以 Accepted 返回，供主窗口刷新卡片。
    """

    def __init__(self, parent=None, log_cb=None, names=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("设置")
        # 固定合理宽度：路径用省略号截断（tooltip 看全名），不再被长路径撑宽
        self.setObjectName("workspaceDialog")
        self._log_cb = log_cb
        self._names = names or {}
        self.changed = False
        self._build_ui()
        screen = QApplication.primaryScreen()
        max_h = int(screen.availableGeometry().height() * 0.88) if screen else 860
        self.resize(780, min(self._body.sizeHint().height() + 4, max_h))

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 18)
        outer.setSpacing(12)

        tip = QLabel(
            "安装位置解析优先级：组件自定义 ＞ 分类工作空间 ＞ 全局默认 ＞ 内置默认目录。"
            "修改立即生效；已安装的组件保持原地不动，不会自动迁移。"
        )
        tip.setWordWrap(True)
        tip.setObjectName("dialogTip")
        outer.addWidget(tip)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        self._body = body
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)

        # 全局默认
        grp = QGroupBox("全局默认工作空间")
        g = QGridLayout(grp)
        g.setColumnStretch(1, 1)
        g.setHorizontalSpacing(12)
        name = QLabel("所有组件")
        name.setObjectName("pathName")
        name.setMinimumWidth(80)
        g.addWidget(name, 0, 0)
        self._global_label = QLabel()
        self._global_label.setObjectName("pathValue")
        g.addWidget(self._global_label, 0, 1)
        g.addWidget(self._mini_btn(
            "浏览", "选择目录作为全局默认工作空间",
            self._on_browse_global), 0, 2)
        g.addWidget(self._mini_btn(
            "重置", "恢复为内置默认目录",
            lambda *_args: self._reset(
                lambda: WS.set_global(None), "全局默认工作空间")), 0, 3)
        g.addWidget(self._mini_btn(
            "打开", "在系统文件管理器中打开该目录",
            lambda *_args: self._open_dir(WS.global_ws or CONFIG_DIR)), 0, 4)
        v.addWidget(grp)

        # 分类工作空间
        grp = QGroupBox("分类工作空间（留空表示跟随全局）")
        g = QGridLayout(grp)
        g.setColumnStretch(1, 1)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(10)
        self._cat_labels: Dict[str, QLabel] = {}
        for row, cat in enumerate(CATEGORY_ORDER):
            name = QLabel(CATEGORIES[cat])
            name.setObjectName("pathName")
            name.setMinimumWidth(80)
            g.addWidget(name, row, 0)
            lab = QLabel()
            lab.setObjectName("pathValue")
            self._cat_labels[cat] = lab
            g.addWidget(lab, row, 1)
            g.addWidget(self._mini_btn(
                "浏览", f"选择「{CATEGORIES[cat]}」的工作空间目录",
                # clicked 会传入 checked 参数：用 *_args 吃掉，避免覆盖 c 的默认值
                lambda *_args, c=cat: self._browse(
                    f"选择「{CATEGORIES[c]}」的工作空间",
                    str(WS.categories.get(c) or WS.global_ws or CONFIG_DIR),
                    lambda p, c=c: WS.set_category(c, p),
                    f"分类「{CATEGORIES[c]}」工作空间",
                )), row, 2)
            g.addWidget(self._mini_btn(
                "重置", "清除该分类设置，跟随全局",
                lambda *_args, c=cat: self._reset(
                    lambda c=c: WS.set_category(c, None),
                    f"分类「{CATEGORIES[c]}」工作空间")), row, 3)
            g.addWidget(self._mini_btn(
                "打开", "在系统文件管理器中打开该目录",
                lambda *_args, c=cat: self._open_dir(
                    WS.categories.get(c) or WS.global_ws or CONFIG_DIR)), row, 4)
        v.addWidget(grp)

        # 组件自定义覆盖
        grp = QGroupBox("组件自定义目录（在组件卡片点文件夹按钮设置，此处可清除）")
        self._override_box = QVBoxLayout(grp)
        self._override_box.setSpacing(6)
        v.addWidget(grp)

        # 下载加速（镜像源）
        grp = QGroupBox("下载加速（GitHub Release 镜像源）")
        g = QGridLayout(grp)
        g.setColumnStretch(1, 1)
        g.addWidget(QLabel("下载通道"), 0, 0)
        self._mirror_combo = NoWheelComboBox()
        self._mirror_combo.addItem("自动（测速选最快，优势不大则直连）", "auto")
        self._mirror_combo.addItem("直连（不使用镜像）", "direct")
        for m in PRESETS:
            self._mirror_combo.addItem(m.name, m.id)
        self._mirror_combo.addItem("自定义…", "custom")
        idx = self._mirror_combo.findData(MIRRORS.mode)
        self._mirror_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._mirror_combo.currentIndexChanged.connect(self._on_mirror_changed)
        g.addWidget(self._mirror_combo, 0, 1)

        self._probe_btn = QPushButton("测速")
        self._probe_btn.setObjectName("secondaryBtn")
        self._probe_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._probe_btn.clicked.connect(self._start_probe)
        g.addWidget(self._probe_btn, 0, 2)

        self._custom_edit = QLineEdit(MIRRORS.custom)
        self._custom_edit.setPlaceholderText("自定义镜像模板，如 https://your-mirror.com/{url}")
        self._custom_edit.textChanged.connect(self._on_custom_changed)
        # 仅在选择「自定义…」时显示模板行
        self._tmpl_label = QLabel("模板")
        self._tmpl_label.setVisible(MIRRORS.mode == "custom")
        self._custom_edit.setVisible(MIRRORS.mode == "custom")
        g.addWidget(self._tmpl_label, 1, 0)
        g.addWidget(self._custom_edit, 1, 1, 1, 2)

        g.addWidget(QLabel("并行分块"), 3, 0)
        self._parts_combo = NoWheelComboBox()
        for n in (1, 2, 4, 8):
            self._parts_combo.addItem(
                "关闭（单线程）" if n == 1 else f"{n} 段", n)
        pidx = self._parts_combo.findData(MIRRORS.parts)
        self._parts_combo.setCurrentIndex(pidx if pidx >= 0 else 2)
        self._parts_combo.currentIndexChanged.connect(self._on_parts_changed)
        g.addWidget(self._parts_combo, 3, 1)

        # 未测速时不占位显示，点「测速」或出结果后才出现
        self._probe_label = QLabel()
        self._probe_label.setObjectName("pathValue")
        self._probe_label.setWordWrap(True)
        self._probe_label.setVisible(False)
        g.addWidget(self._probe_label, 2, 1, 1, 2)
        v.addWidget(grp)

        # 安装选项
        grp = QGroupBox("安装选项")
        g = QGridLayout(grp)
        g.setColumnStretch(0, 1)
        # 滑动开关：默认复选框样式太淡，看不出是可交互的选项
        self._auto_env_box = ToggleSwitch("安装完成后自动配置环境变量")
        self._auto_env_box.setChecked(INSTALL.auto_env)
        self._auto_env_box.setToolTip(
            "写入 XXX_HOME 与 PATH 会改动系统/用户配置；关闭时只下载解压，"
            "需要时在组件卡片点「配置环境变量」"
        )
        self._auto_env_box.toggled.connect(self._on_auto_env_changed)
        g.addWidget(self._auto_env_box, 0, 0)
        v.addWidget(grp)

        # 安装包清理
        grp = QGroupBox("安装包清理（组件解压安装后压缩包即不再需要）")
        g = QGridLayout(grp)
        g.setColumnStretch(0, 1)
        self._cache_label = QLabel()
        self._cache_label.setObjectName("pathValue")
        self._cache_label.setWordWrap(True)
        g.addWidget(self._cache_label, 0, 0)
        self._clean_btn = QPushButton("立即清理")
        self._clean_btn.setObjectName("secondaryBtn")
        self._clean_btn.setCursor(QCursor(Qt.PointingHandCursor))
        self._clean_btn.setToolTip("删除所有工作空间 downloads 目录里的安装包，已安装组件不受影响")
        self._clean_btn.clicked.connect(self._clean_downloads)
        g.addWidget(self._clean_btn, 0, 1)
        self._refresh_cache_label()
        v.addWidget(grp)

        v.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll, stretch=1)

        btn = QPushButton("关闭")
        btn.setObjectName("primaryBtn")
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setFixedHeight(36)
        btn.clicked.connect(lambda: self.accept() if self.changed else self.reject())
        outer.addWidget(btn, alignment=Qt.AlignRight)

        self._refresh()

    # ------------------------------------------------------------------
    def _on_browse_global(self, *_args) -> None:
        self._browse(
            "选择全局默认工作空间",
            str(WS.global_ws or CONFIG_DIR),
            lambda p: WS.set_global(p),
            "全局默认工作空间",
        )

    @staticmethod
    def _elide_mid(text: str, limit: int = 42) -> str:
        """路径过长时中间省略，保住盘符与末级目录名。"""
        if len(text) <= limit:
            return text
        head = (limit - 1) // 2
        tail = limit - 1 - head
        return f"{text[:head]}…{text[len(text) - tail:]}"

    def _mini_btn(self, text: str, tip: str, cb) -> QPushButton:
        """紧凑的小按钮（浏览/重置/打开），避免行内按钮过宽挤爆布局。"""
        btn = QPushButton(text)
        btn.setObjectName("secondaryBtn")
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.setToolTip(tip)
        btn.clicked.connect(cb)
        return btn

    def _set_path(self, label: QLabel, text: str) -> None:
        label.setText(self._elide_mid(text))
        label.setToolTip(text)

    # ------------------------------------------------------------------
    def _browse(self, title: str, current: str, apply_cb, what: str) -> None:
        chosen = QFileDialog.getExistingDirectory(self, title, current)
        if not chosen:
            return
        apply_cb(chosen)
        self.changed = True
        self._refresh()
        if self._log_cb:
            self._log_cb("ok", f"工作空间已更新：{what} → {chosen}")

    def _reset(self, apply_cb, what: str) -> None:
        apply_cb()
        self.changed = True
        self._refresh()
        if self._log_cb:
            self._log_cb("ok", f"工作空间已恢复默认：{what}")

    # ------------------------------------------------------------------
    # 安装包清理
    # ------------------------------------------------------------------
    def _refresh_cache_label(self) -> None:
        files = [f for f in WS.download_cache_files() if f.exists()]
        if files:
            try:
                total = sum(f.stat().st_size for f in files)
            except OSError:
                total = 0
            self._cache_label.setText(
                f"检测到 {len(files)} 个安装包，共 {human_size(total)}"
                "（各工作空间的 downloads 目录）"
            )
            self._clean_btn.setEnabled(True)
        else:
            self._cache_label.setText("没有可清理的安装包")
            self._clean_btn.setEnabled(False)

    def _clean_downloads(self) -> None:
        files = [f for f in WS.download_cache_files() if f.exists()]
        if not files:
            return
        total = sum(f.stat().st_size for f in files)
        ret = QMessageBox.question(
            self,
            "清理安装包",
            f"确定删除 {len(files)} 个安装包（共 {human_size(total)}）吗？\n\n"
            "已解压安装的组件不受影响；正在下载/安装的任务请先完成。",
        )
        if ret != QMessageBox.Yes:
            return
        ok, freed, failed = 0, 0, 0
        for f in files:
            try:
                freed += f.stat().st_size
                f.unlink()
                ok += 1
            except OSError:
                failed += 1
        if self._log_cb:
            msg = f"已清理 {ok} 个安装包，释放 {human_size(freed)}"
            if failed:
                msg += f"；{failed} 个文件被占用，删除失败（可稍后重试）"
            self._log_cb("ok" if not failed else "warn", msg)
        self._refresh_cache_label()

    # ------------------------------------------------------------------
    def _open_dir(self, path: str) -> None:
        """在系统文件管理器中打开目录（不存在会先创建）。"""
        if open_in_file_manager(path):
            if self._log_cb:
                self._log_cb("ok", f"已打开目录：{path}")
        elif self._log_cb:
            self._log_cb("warn", f"打开目录失败：{path}")

    # ------------------------------------------------------------------
    # 下载镜像
    # ------------------------------------------------------------------
    def _on_mirror_changed(self) -> None:
        mode = self._mirror_combo.currentData() or "auto"
        MIRRORS.mode = mode
        MIRRORS.save()
        self._tmpl_label.setVisible(mode == "custom")
        self._custom_edit.setVisible(mode == "custom")
        if self._log_cb:
            self._log_cb("ok", f"下载通道已切换为：{self._mirror_combo.currentText()}")

    def _on_custom_changed(self, text: str) -> None:
        if MIRRORS.mode != "custom":
            return
        MIRRORS.custom = text.strip()
        MIRRORS.save()

    def _on_parts_changed(self) -> None:
        MIRRORS.parts = int(self._parts_combo.currentData() or 1)
        MIRRORS.save()

    # ------------------------------------------------------------------
    # 安装选项
    # ------------------------------------------------------------------
    def _on_auto_env_changed(self, checked: bool) -> None:
        INSTALL.auto_env = bool(checked)
        INSTALL.save()
        if self._log_cb:
            self._log_cb(
                "ok",
                "环境变量配置：安装后自动写入" if checked
                else "环境变量配置：仅下载解压，需手动点「配置环境变量」",
            )

    def _start_probe(self) -> None:
        self._probe_btn.setEnabled(False)
        self._probe_label.setVisible(True)
        self._probe_label.setText("测速中…（各通道抽样下载 512 KB）")
        self._probe_worker = MirrorProbeWorker(parent=self)
        self._probe_worker.done.connect(self._on_probe_done)
        self._probe_worker.start()

    def _on_probe_done(self, results) -> None:
        lines = []
        for _mid, name, speed in results:
            lines.append(f"{name}：{int(speed)} KB/s" if speed > 0 else f"{name}：不可用")
        self._probe_label.setText("\n".join(lines))
        self._probe_btn.setEnabled(True)

    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        self._set_path(self._global_label,
                       WS.global_ws or f"内置默认（{CONFIG_DIR}）")
        for cat, lab in self._cat_labels.items():
            self._set_path(lab, WS.categories.get(cat) or "跟随全局")
        # 重建覆盖清单
        while self._override_box.count():
            item = self._override_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if not WS.components:
            empty = QLabel("暂无组件自定义目录。")
            empty.setObjectName("pathMuted")
            self._override_box.addWidget(empty)
        for key, path in sorted(WS.components.items()):
            row = QHBoxLayout()
            name = QLabel(self._names.get(key, key))
            name.setObjectName("pathName")
            row.addWidget(name)
            lab = QLabel(self._elide_mid(path))
            lab.setObjectName("pathMuted")
            lab.setToolTip(path)
            row.addWidget(lab, stretch=1)
            btn = QPushButton("清除")
            btn.setObjectName("secondaryBtn")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _=False, k=key: self._reset(
                lambda k=k: WS.set_component(k, None),
                f"组件「{self._names.get(k, k)}」自定义目录"))
            row.addWidget(btn)
            wrap = QWidget()
            wrap.setLayout(row)
            self._override_box.addWidget(wrap)
