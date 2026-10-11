# -*- coding: utf-8 -*-
"""对话框：打赏、关于、工作空间设置。"""

from __future__ import annotations

from typing import Dict, List

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCursor, QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ..core.constants import CATEGORIES, CATEGORY_ORDER, CONFIG_DIR
from ..core.workspace import WS
from ..resources import assets_dir


# ---------------------------------------------------------------------------
# 捐赠弹窗（不出现在文档中；仅代码内实现）
# ---------------------------------------------------------------------------
class DonateDialog(QDialog):
    """支持作者：微信 / 支付宝 / QQ，各渠道展示对应二维码。"""

    # 每个渠道对应的品牌色、二维码文件名
    CHANNELS = [
        ("微信", "#07C160", "wechat.png"),
        ("支付宝", "#1677FF", "alipay.png"),
        ("QQ", "#EB1923", "qq.png"),
    ]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("支持作者")
        self.setFixedSize(380, 402)
        self.setObjectName("donateDialog")
        self._assets_dir = assets_dir()
        self._build_ui()
        # 默认展示第一个渠道
        self._show_qr(*self.CHANNELS[0])

    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 16)
        v.setSpacing(10)

        tip = QLabel("如果本工具对你有所帮助，欢迎请作者一杯咖啡 ☕")
        tip.setAlignment(Qt.AlignCenter)
        tip.setObjectName("donateTip")
        v.addWidget(tip)

        # 渠道切换按钮行
        row = QHBoxLayout()
        row.setSpacing(10)
        self._buttons: List[QPushButton] = []
        for name, color, filename in self.CHANNELS:
            btn = QPushButton(name)
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.setCheckable(True)
            btn.setObjectName("channelBtn")
            # 仅保留动态渠道色，其余外观交给 theme.qss
            btn.setStyleSheet(f"background:{color};")
            btn.clicked.connect(lambda _=False, n=name, c=color, f=filename: self._show_qr(n, c, f))
            row.addWidget(btn)
            self._buttons.append(btn)
        v.addLayout(row)

        # 当前渠道标签
        self._channel_label = QLabel("")
        self._channel_label.setAlignment(Qt.AlignCenter)
        self._channel_label.setObjectName("channelLabel")
        v.addWidget(self._channel_label)

        # 二维码展示区（固定尺寸，整体弹窗更紧凑）
        self.qr_view = QLabel("请选择下方渠道")
        self.qr_view.setAlignment(Qt.AlignCenter)
        self.qr_view.setFixedHeight(214)
        self.qr_view.setObjectName("qrView")
        v.addWidget(self.qr_view, alignment=Qt.AlignHCenter)

        # 底部备注
        note = QLabel("扫码打赏，感谢您的支持！")
        note.setAlignment(Qt.AlignCenter)
        note.setObjectName("donateNote")
        v.addWidget(note)

    def _show_qr(self, channel: str, color: str = "", filename: str = "") -> None:
        # 更新按钮 checked 状态
        for btn in self._buttons:
            btn.setChecked(btn.text() == channel)

        self._channel_label.setText(f"【{channel}】收款码")
        if color:
            self._channel_label.setStyleSheet(f"color:{color};")

        if not filename:
            # 兼容旧调用：仅传 channel 时按 CHANNELS 查
            for n, c, f in self.CHANNELS:
                if n == channel:
                    filename = f
                    break

        # 尝试加载二维码图片
        qr_path = self._assets_dir / filename
        if qr_path.exists():
            pixmap = QPixmap(str(qr_path))
            if not pixmap.isNull():
                # 等比缩小到固定边长，整体弹窗更短更美观
                scaled = pixmap.scaled(
                    196, 196,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                self.qr_view.setPixmap(scaled)
                return

        # 加载失败：显示占位文字
        self.qr_view.clear()
        self.qr_view.setText(
            f"未找到二维码文件：\n\n{qr_path}\n\n请将 {filename} 放入 assets 目录后重启。"
        )


# ---------------------------------------------------------------------------
# 关于我们弹窗
# ---------------------------------------------------------------------------
class AboutDialog(QDialog):
    """关于我们：团队介绍 + QQ/微信群/微信联系方式。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("关于我们")
        self.setMinimumWidth(760)
        self.setObjectName("aboutDialog")
        self._build_ui()
        self.adjustSize()

    def _build_ui(self) -> None:
        v = QVBoxLayout(self)
        v.setContentsMargins(36, 28, 36, 24)
        v.setSpacing(10)

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
# 工作空间设置对话框
# ---------------------------------------------------------------------------
class WorkspaceDialog(QDialog):
    """工作空间设置：全局默认 + 分类目录 + 组件自定义覆盖清单。

    修改即时生效并落盘；关闭时若有过修改则以 Accepted 返回，供主窗口刷新卡片。
    """

    def __init__(self, parent=None, log_cb=None, names=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("工作空间")
        self.setMinimumWidth(660)
        self.setObjectName("workspaceDialog")
        self._log_cb = log_cb
        self._names = names or {}
        self.changed = False
        self._build_ui()
        self.adjustSize()

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
        v = QVBoxLayout(body)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)

        # 全局默认
        grp = QGroupBox("全局默认工作空间")
        g = QGridLayout(grp)
        g.setColumnStretch(1, 1)
        self._global_label = QLabel()
        self._global_label.setObjectName("pathValue")
        g.addWidget(QLabel("所有组件"), 0, 0)
        g.addWidget(self._global_label, 0, 1)
        btn = QPushButton("浏览…")
        btn.setObjectName("secondaryBtn")
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.clicked.connect(lambda: self._browse(
            "选择全局默认工作空间",
            str(WS.global_ws or CONFIG_DIR),
            lambda p: WS.set_global(p),
            "全局默认工作空间",
        ))
        g.addWidget(btn, 0, 2)
        btn = QPushButton("恢复默认")
        btn.setObjectName("secondaryBtn")
        btn.setCursor(QCursor(Qt.PointingHandCursor))
        btn.clicked.connect(lambda: self._reset(
            lambda: WS.set_global(None), "全局默认工作空间"))
        g.addWidget(btn, 0, 3)
        v.addWidget(grp)

        # 分类工作空间
        grp = QGroupBox("分类工作空间（留空表示跟随全局）")
        g = QGridLayout(grp)
        g.setColumnStretch(1, 1)
        self._cat_labels: Dict[str, QLabel] = {}
        for row, cat in enumerate(CATEGORY_ORDER):
            g.addWidget(QLabel(CATEGORIES[cat]), row, 0)
            lab = QLabel()
            lab.setObjectName("pathValue")
            self._cat_labels[cat] = lab
            g.addWidget(lab, row, 1)
            btn = QPushButton("浏览…")
            btn.setObjectName("secondaryBtn")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _=False, c=cat: self._browse(
                f"选择「{CATEGORIES[c]}」的工作空间",
                str(WS.categories.get(c) or WS.global_ws or CONFIG_DIR),
                lambda p, c=c: WS.set_category(c, p),
                f"分类「{CATEGORIES[c]}」工作空间",
            ))
            g.addWidget(btn, row, 2)
            btn = QPushButton("跟随全局")
            btn.setObjectName("secondaryBtn")
            btn.setCursor(QCursor(Qt.PointingHandCursor))
            btn.clicked.connect(lambda _=False, c=cat: self._reset(
                lambda c=c: WS.set_category(c, None), f"分类「{CATEGORIES[c]}」工作空间"))
            g.addWidget(btn, row, 3)
        v.addWidget(grp)

        # 组件自定义覆盖
        grp = QGroupBox("组件自定义目录（在组件卡片点文件夹按钮设置，此处可清除）")
        self._override_box = QVBoxLayout(grp)
        self._override_box.setSpacing(6)
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
    def _refresh(self) -> None:
        self._global_label.setText(WS.global_ws or f"内置默认（{CONFIG_DIR}）")
        for cat, lab in self._cat_labels.items():
            lab.setText(WS.categories.get(cat) or "跟随全局")
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
            lab = QLabel(path)
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
