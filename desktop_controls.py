"""桌面挂件的设置与快捷键输入；窗口层级及偏好持久化由主窗口负责。"""

from __future__ import annotations

import logging
import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


LOGGER = logging.getLogger(__name__)
SHORTCUT_DEFAULTS = {
    "edit": "Ctrl+Shift+Alt+M",
    "hide": "Ctrl+Shift+Alt+H",
    "prev": "Ctrl+Shift+Alt+P",
    "next": "Ctrl+Shift+Alt+N",
    "settings": "Ctrl+Shift+Alt+S",
    "quit": "Ctrl+Shift+Alt+Q",
}
SHORTCUT_LEGACY_DEFAULTS = {
    "edit": "Ctrl+Alt+M",
    "hide": "Ctrl+Alt+H",
    "prev": "Ctrl+Alt+P",
    "next": "Ctrl+Alt+N",
    "settings": "Ctrl+Alt+S",
    "quit": "Ctrl+Alt+Q",
}
SHORTCUT_LABELS = {
    "edit": "进入／退出调整",
    "hide": "显示／隐藏面板",
    "prev": "上一页",
    "next": "下一页",
    "settings": "打开设置",
    "quit": "退出程序",
}
SKIN_LABELS = (
    ("雾白键帽", "skin1"), ("石墨键帽", "skin2"),
    ("夜行分段条", "skin3"), ("冷灰对比横条", "skin4"),
    ("夜行色块条", "skin5"), ("暖沙折线", "skin6"),
)


def _normalize_sequence(value, *, allow_reserved=False):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("快捷键不能为空")
    if any(separator in value for separator in (",", ";", "，", "；")):
        raise ValueError("每项只支持一个组合键，不支持连续按键序列")
    parts = [part.strip() for part in value.split("+")]
    if any(not part for part in parts):
        raise ValueError("快捷键格式无效")
    aliases = {"ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "shift": "Shift"}
    modifiers = set()
    for part in parts[:-1]:
        modifier = aliases.get(part.casefold())
        if modifier is None:
            raise ValueError("修饰键只支持 Ctrl、Alt、Shift，不支持 Win／Meta")
        if modifier in modifiers:
            raise ValueError("快捷键不能重复填写同一个修饰键")
        modifiers.add(modifier)
    if not modifiers.intersection({"Ctrl", "Alt"}):
        raise ValueError("快捷键至少需要包含 Ctrl 或 Alt")
    key = parts[-1].upper()
    if not re.fullmatch(r"[A-Z0-9]|F(?:[1-9]|1[0-2])", key):
        raise ValueError("主键仅支持字母、数字或 F1–F12")
    if not allow_reserved and modifiers == {"Ctrl", "Alt"} and key in "0123456789":
        raise ValueError("Ctrl+Alt+0–9 已保留给固定页和取消固定")
    return "+".join([part for part in ("Ctrl", "Alt", "Shift") if part in modifiers] + [key])


def normalize_shortcuts(bindings):
    """规范六项单组合快捷键；部分字典用默认值补齐，冲突会明确报错。"""
    if bindings is None:
        bindings = {}
    if not isinstance(bindings, dict):
        raise ValueError("快捷键配置必须是字典")
    if set(bindings) - set(SHORTCUT_DEFAULTS):
        raise ValueError("快捷键配置包含不支持的动作")
    result, owners = {}, {}
    for action, default in SHORTCUT_DEFAULTS.items():
        try:
            sequence = _normalize_sequence(bindings.get(action, default))
        except ValueError as error:
            raise ValueError(f"{SHORTCUT_LABELS[action]}：{error}") from error
        if sequence in owners:
            raise ValueError(f"{SHORTCUT_LABELS[action]}与{SHORTCUT_LABELS[owners[sequence]]}使用了相同快捷键")
        result[action] = sequence
        owners[sequence] = action
    return result


def native_shortcut(sequence):
    """只转换修饰位与虚拟键；允许主程序转换固定页保留键，不执行注册。"""
    parts = _normalize_sequence(sequence, allow_reserved=True).split("+")
    modifiers = sum({"Alt": 0x0001, "Ctrl": 0x0002, "Shift": 0x0004}[part] for part in parts[:-1])
    key = parts[-1]
    virtual_key = 0x70 + int(key[1:]) - 1 if key.startswith("F") and len(key) > 1 else ord(key)
    return modifiers, virtual_key


def shortcut_help(bindings=None):
    """返回设置、托盘帮助可共用的说明文本。"""
    shortcuts = normalize_shortcuts(bindings)
    lines = [f"{SHORTCUT_LABELS[action]}：{sequence}" for action, sequence in shortcuts.items()]
    lines.extend((
        "Ctrl+Alt+1–9：跳转并固定对应页；Ctrl+Alt+0：取消固定。",
        "调整模式：Esc 退出；P/N 或左右方向键翻页；滚轮翻页。",
        "调整模式：拖动空白区域移动，拖动边缘缩放；Ctrl+点击选择节点。",
        "调整模式：T 换肤，S 排序，G 分组，C 轮播，[ / ] 调透明度。",
        "全局快捷键可能被其他程序占用；固定页 Ctrl+Alt+0–9 可在设置中关闭，注册冲突会在状态栏提示。",
    ))
    return "\n".join(lines)


class SettingsDialog(QDialog):
    """收集设置草稿，应用成功后再关闭，不自行修改注册表或桌面图层。"""

    def __init__(self, window):
        # 面板本身是Tool窗口，设置必须有独立的普通窗口入口，不能跟随后层一起藏到应用后面。
        super().__init__(None, Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.monitor_window = window
        font = QFont()
        font.setFamilies(["Microsoft YaHei UI", "Segoe UI", "Arial"])
        font.setPixelSize(12)
        self.setFont(font)
        self.setProperty("interactive_control", True)
        self.setWindowTitle("KomariDesktop 设置")
        self.setMinimumSize(360, 300)
        snapshot = window.settings_snapshot()
        if not isinstance(snapshot, dict):
            raise TypeError("settings_snapshot() 必须返回字典")
        self._snapshot = dict(snapshot)
        self._shortcut_load_error = ""
        try:
            initial_shortcuts = normalize_shortcuts(snapshot.get("shortcuts"))
        except ValueError as error:
            initial_shortcuts = dict(SHORTCUT_DEFAULTS)
            self._shortcut_load_error = f"原快捷键配置无效，已在编辑区载入默认值：{error}"
            LOGGER.warning("设置窗口载入的快捷键配置无效：%s", error)

        outer = QVBoxLayout(self)
        self.tabs = QTabWidget(self)
        outer.addWidget(self.tabs, 1)
        self._build_window_tab()
        self._build_paging_tab()
        self._build_nodes_tab()
        self._build_shortcuts_tab(initial_shortcuts)
        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.status_label)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel, self,
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).setText("应用")
        self.button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.button_box.accepted.connect(self._accept_preferences)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply_preferences)
        outer.addWidget(self.button_box)
        screen = window.screen() or QApplication.primaryScreen()
        work = screen.availableGeometry() if screen else None
        self.resize(min(680, max(360, work.width() - 32)) if work else 680,
                    min(650, max(300, work.height() - 32)) if work else 650)
        if work:
            self.move(work.center().x() - self.width() // 2, work.center().y() - self.height() // 2)
        self._sync_page_status()
        status = self._shortcut_load_error
        failures = getattr(window, "_hotkey_failures", {})
        if failures:
            conflict = "当前快捷键冲突：" + ", ".join(sorted(failures)) + "。可修改后点击应用。"
            status = f"{status}\n{conflict}" if status else conflict
        self._set_status(status, error=bool(status))

    def _tab(self, title):
        scroll = QScrollArea(self.tabs)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget(scroll)
        layout = QVBoxLayout(body)
        layout.setSpacing(12)
        scroll.setWidget(body)
        self.tabs.addTab(scroll, title)
        return body, layout

    @staticmethod
    def _description(text, parent):
        label = QLabel(text, parent)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _combo(items, value, parent):
        combo = QComboBox(parent)
        for text, data in items:
            combo.addItem(text, data)
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)
        return combo

    @staticmethod
    def _spin(low, high, value, parent, suffix=""):
        spin = QSpinBox(parent)
        spin.setRange(low, high)
        try:
            spin.setValue(int(value))
        except (TypeError, ValueError, OverflowError):
            spin.setValue(low)
        spin.setKeyboardTracking(False)
        spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        spin.lineEdit().setReadOnly(False)
        spin.setSuffix(suffix)
        return spin

    def _build_window_tab(self):
        body, layout = self._tab("窗口")
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.layer_combo = self._combo((
            ("桌面后层", "desktop"), ("普通窗口", "normal"), ("始终置顶", "topmost"),
        ), self._snapshot.get("layer_mode", "desktop"), body)
        form.addRow("图层", self.layer_combo)
        self.click_through_check = QCheckBox("锁定时鼠标穿透", body)
        self.click_through_check.setChecked(bool(self._snapshot.get("click_through", True)))
        form.addRow("鼠标", self.click_through_check)
        self.opacity_spin = self._spin(40, 100, self._snapshot.get("opacity", 100), body, "%")
        form.addRow("背景透明度", self.opacity_spin)
        self.theme_combo = self._combo(SKIN_LABELS, self._snapshot.get("theme", "skin1"), body)
        form.addRow("皮肤", self.theme_combo)
        dimensions = QWidget(body)
        dimension_layout = QHBoxLayout(dimensions)
        dimension_layout.setContentsMargins(0, 0, 0, 0)
        self.width_spin = self._spin(320, 32768, self._snapshot.get("window_width", 452), dimensions)
        self.height_spin = self._spin(300, 32768, self._snapshot.get("window_height", 538), dimensions)
        dimension_layout.addWidget(QLabel("宽", dimensions))
        dimension_layout.addWidget(self.width_spin, 1)
        dimension_layout.addWidget(QLabel("高", dimensions))
        dimension_layout.addWidget(self.height_spin, 1)
        form.addRow("窗口逻辑尺寸", dimensions)
        screen_items = [("自动（当前屏幕）", "")]
        for screen in QApplication.screens():
            area = screen.availableGeometry()
            screen_items.append((f"{screen.name()} · {area.width()}×{area.height()}", screen.name()))
        stored_screen = str(self._snapshot.get("screen_name") or "")
        if stored_screen and all(data != stored_screen for _, data in screen_items):
            screen_items.append((f"{stored_screen}（当前不可用）", stored_screen))
        self.screen_combo = self._combo(screen_items, stored_screen, body)
        form.addRow("目标屏幕", self.screen_combo)
        self.position_combo = self._combo((
            ("保持当前位置", "keep"), ("右上角", "topright"), ("左上角", "topleft"),
            ("右下角", "bottomright"), ("左下角", "bottomleft"), ("居中", "center"),
        ), self._snapshot.get("position", "keep"), body)
        form.addRow("放置位置", self.position_combo)
        layout.addLayout(form)
        layout.addWidget(self._description(
            "桌面后层用于放在普通工作窗口后面。Win+D、Explorer 重启及不同显示环境仍需实机验收；"
            "这一模式不保证等同于真正嵌入壁纸层。普通窗口遵循正常前后关系，始终置顶会覆盖其他软件。",
            body,
        ))
        layout.addWidget(self._description(
            "透明度40%更透明，100%不透明；文字和指标保持清晰。尺寸采用逻辑像素，系统缩放由Qt处理。"
            "应用时主程序会根据目标屏幕工作区调整位置和尺寸。", body,
        ))
        layout.addStretch(1)

    def _build_paging_tab(self):
        body, layout = self._tab("分页")
        form = QFormLayout()
        self.layout_combo = self._combo((
            ("自动适应（宽窗口允许多列）", "auto"), ("始终单列", "single"),
        ), self._snapshot.get("layout_mode", "auto"), body)
        form.addRow("布局", self.layout_combo)
        self.max_per_page_spin = self._spin(0, 100, self._snapshot.get("max_per_page", 0), body)
        self.max_per_page_spin.setSpecialValueText("自动")
        form.addRow("每页节点上限", self.max_per_page_spin)
        self.refresh_spin = self._spin(5, 300, self._snapshot.get("refresh_seconds", 15), body, " 秒")
        form.addRow("数据刷新间隔", self.refresh_spin)
        self.carousel_check = QCheckBox("自动轮播", body)
        self.carousel_check.setChecked(bool(self._snapshot.get("carousel_enabled", False)))
        form.addRow("轮播", self.carousel_check)
        self.carousel_spin = self._spin(3, 120, self._snapshot.get("carousel_seconds", 15), body, " 秒")
        # 关闭自动轮播只暂停计时，不应阻止用户预先设置下次启用时的间隔。
        form.addRow("轮播间隔", self.carousel_spin)
        self.pin_check = QCheckBox("固定当前内容（暂停自动轮播）", body)
        self.pin_check.setChecked(bool(self._snapshot.get("pin_current", False)))
        form.addRow("固定", self.pin_check)
        self.sort_combo = self._combo((
            ("名称", "name"), ("CPU", "cpu"), ("内存", "memory"), ("延迟", "latency"),
        ), self._snapshot.get("sort_mode", "name"), body)
        form.addRow("排序", self.sort_combo)
        self.group_check = QCheckBox("按地区分组", body)
        self.group_check.setChecked(bool(self._snapshot.get("group_mode", False)))
        form.addRow("分组", self.group_check)
        layout.addLayout(form)
        pager = QGroupBox("立即翻页", body)
        pager_layout = QVBoxLayout(pager)
        self.page_info = QLabel(pager)
        pager_layout.addWidget(self.page_info)
        controls = QHBoxLayout()
        self.prev_button = QPushButton("上一页", pager)
        self.next_button = QPushButton("下一页", pager)
        self.page_spin = self._spin(1, 100000, 1, pager)
        self.jump_button = QPushButton("跳转", pager)
        controls.addWidget(self.prev_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.page_spin, 1)
        controls.addWidget(self.jump_button)
        pager_layout.addLayout(controls)
        self.prev_button.clicked.connect(lambda: self._navigate_page(-1))
        self.next_button.clicked.connect(lambda: self._navigate_page(1))
        self.jump_button.clicked.connect(self._jump_page)
        pager_layout.addWidget(self._description(
            "翻页立即生效，取消设置不会撤销翻页。超过9页时也可输入页码跳转。", pager,
        ))
        layout.addWidget(pager)
        layout.addWidget(self._description(
            "每页上限不会强行压缩字体；实际显示数量仍受窗口空间限制。调整、隐藏或固定内容时暂停轮播。",
            body,
        ))
        layout.addStretch(1)

    def _build_nodes_tab(self):
        body, layout = self._tab("节点")
        self.all_nodes_check = QCheckBox("显示全部节点（包括以后新增的节点）", body)
        self.all_nodes_check.setChecked(bool(self._snapshot.get("show_all_nodes", True)))
        layout.addWidget(self.all_nodes_check)
        self.node_filter = QLineEdit(body)
        self.node_filter.setPlaceholderText("按名称、地区或节点ID筛选")
        self.node_filter.setClearButtonEnabled(True)
        layout.addWidget(self.node_filter)
        actions = QHBoxLayout()
        self.select_all_button = QPushButton("全选", body)
        self.clear_nodes_button = QPushButton("清空", body)
        for button in (self.select_all_button, self.clear_nodes_button):
            button.setToolTip("对完整列表生效，包括当前被筛选隐藏的项目")
            actions.addWidget(button)
        self.node_summary = QLabel(body)
        actions.addWidget(self.node_summary, 1)
        layout.addLayout(actions)
        self.node_list = QListWidget(body)
        self.node_list.setMinimumHeight(160)
        layout.addWidget(self.node_list, 1)
        selected = {str(value) for value in self._snapshot.get("selected_ids", [])}
        records = {}
        samples = self._snapshot.get("samples", [])
        for sample in samples if isinstance(samples, list) else []:
            if isinstance(sample, dict) and sample.get("id"):
                records[str(sample["id"])] = sample
        for node_id in sorted(selected - set(records)):
            records[node_id] = {"id": node_id, "name": node_id, "status": "unavailable", "region": ""}
        states = {"online": "在线", "offline": "离线", "stale": "数据过期", "unavailable": "暂不可用"}
        for node_id, record in records.items():
            name = str(record.get("name") or "未命名节点")
            region = str(record.get("region") or "")
            state = states.get(record.get("status"), "状态未知")
            text = f"{name}  ·  {region}  ·  {state}" if region else f"{name}  ·  {state}"
            item = QListWidgetItem(text, self.node_list)
            item.setData(Qt.ItemDataRole.UserRole, node_id)
            item.setToolTip(f"{text}\n节点ID：{node_id}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = node_id in selected or (self.all_nodes_check.isChecked() and record.get("status") != "unavailable")
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.node_filter.textChanged.connect(self._filter_nodes)
        self.node_list.itemChanged.connect(self._update_node_summary)
        self.all_nodes_check.toggled.connect(self._set_node_selection_enabled)
        self.select_all_button.clicked.connect(lambda: self._set_all_node_checks(True))
        self.clear_nodes_button.clicked.connect(lambda: self._set_all_node_checks(False))
        self._set_node_selection_enabled(self.all_nodes_check.isChecked())
        layout.addWidget(self._description(
            "筛选仅隐藏列表项，不改变勾选状态。已选择但当前数据源没有返回的节点会保留，待其恢复后继续显示。",
            body,
        ))

    def _build_shortcuts_tab(self, initial):
        body, layout = self._tab("快捷键")
        layout.addWidget(self._description(
            "点击输入框后按组合键。每项只支持一个组合，主键限字母、数字或F1–F12，至少含Ctrl或Alt；"
            "不支持Win键。Ctrl+Alt+0–9为固定页功能保留；若与其他软件冲突，可关闭下面的全局固定页快捷键。", body,
        ))
        self.page_hotkeys_check = QCheckBox("启用全局固定页快捷键（Ctrl+Alt+0–9）", body)
        self.page_hotkeys_check.setChecked(bool(self._snapshot.get("page_hotkeys_enabled", True)))
        layout.addWidget(self.page_hotkeys_check)
        form = QFormLayout()
        self.shortcut_edits = {}
        for action, label in SHORTCUT_LABELS.items():
            edit = QKeySequenceEdit(QKeySequence(initial[action], QKeySequence.SequenceFormat.PortableText), body)
            edit.setMaximumSequenceLength(1)
            edit.setClearButtonEnabled(True)
            form.addRow(label, edit)
            self.shortcut_edits[action] = edit
        layout.addLayout(form)
        defaults = QPushButton("恢复默认快捷键", body)
        defaults.clicked.connect(self._restore_default_shortcuts)
        layout.addWidget(defaults, 0, Qt.AlignmentFlag.AlignLeft)
        self.help_label = self._description(shortcut_help(initial), body)
        layout.addWidget(self.help_label)
        layout.addStretch(1)

    def _filter_nodes(self, text):
        query = text.strip().casefold()
        for index in range(self.node_list.count()):
            item = self.node_list.item(index)
            searchable = f"{item.text()} {item.data(Qt.ItemDataRole.UserRole)}".casefold()
            item.setHidden(bool(query) and query not in searchable)

    def _set_node_selection_enabled(self, all_nodes):
        for control in (self.node_list, self.select_all_button, self.clear_nodes_button):
            control.setEnabled(not all_nodes)
        self._update_node_summary()

    def _set_all_node_checks(self, checked):
        self.node_list.blockSignals(True)
        try:
            for index in range(self.node_list.count()):
                self.node_list.item(index).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        finally:
            self.node_list.blockSignals(False)
        self._update_node_summary()

    def _update_node_summary(self, *_):
        if self.all_nodes_check.isChecked():
            self.node_summary.setText("自动显示所有节点")
        else:
            count = sum(self.node_list.item(index).checkState() == Qt.CheckState.Checked
                        for index in range(self.node_list.count()))
            self.node_summary.setText(f"已选 {count} / {self.node_list.count()}")

    def _restore_default_shortcuts(self):
        for action, sequence in SHORTCUT_DEFAULTS.items():
            self.shortcut_edits[action].setKeySequence(QKeySequence(sequence, QKeySequence.SequenceFormat.PortableText))

    def _sync_page_status(self):
        snapshot = self.monitor_window.settings_snapshot()
        count = max(1, int(snapshot.get("page_count", 1)))
        index = max(0, min(count - 1, int(snapshot.get("page_index", 0))))
        self.page_info.setText(f"当前第 {index + 1} / {count} 页")
        self.page_spin.setMaximum(count)
        self.page_spin.setValue(index + 1)
        self.prev_button.setEnabled(count > 1)
        self.next_button.setEnabled(count > 1)

    def _navigate_page(self, step):
        try:
            self.monitor_window.next_page(step)
            self._sync_page_status()
        except (ValueError, TypeError, RuntimeError, OSError) as error:
            LOGGER.exception("设置窗口翻页失败")
            self._set_status(f"翻页失败：{error}", error=True)

    def _jump_page(self):
        try:
            self.monitor_window.jump_to_page(self.page_spin.value())
            self._sync_page_status()
        except (ValueError, TypeError, RuntimeError, OSError) as error:
            LOGGER.exception("设置窗口跳页失败")
            self._set_status(f"跳转失败：{error}", error=True)

    def preferences(self):
        """收集完整草稿；节点按全部列表读取，不能丢掉过滤隐藏的项目。"""
        shortcuts = normalize_shortcuts({
            action: edit.keySequence().toString(QKeySequence.SequenceFormat.PortableText)
            for action, edit in self.shortcut_edits.items()
        })
        selected = [str(self.node_list.item(index).data(Qt.ItemDataRole.UserRole))
                    for index in range(self.node_list.count())
                    if self.node_list.item(index).checkState() == Qt.CheckState.Checked]
        return {
            "layer_mode": self.layer_combo.currentData(),
            "click_through": self.click_through_check.isChecked(),
            "opacity": self.opacity_spin.value(), "theme": self.theme_combo.currentData(),
            "layout_mode": self.layout_combo.currentData(), "max_per_page": self.max_per_page_spin.value(),
            "refresh_seconds": self.refresh_spin.value(), "carousel_seconds": self.carousel_spin.value(),
            "carousel_enabled": self.carousel_check.isChecked(), "sort_mode": self.sort_combo.currentData(),
            "group_mode": self.group_check.isChecked(), "show_all_nodes": self.all_nodes_check.isChecked(),
            "selected_ids": selected, "shortcuts": shortcuts,
            "page_hotkeys_enabled": self.page_hotkeys_check.isChecked(),
            "window_width": self.width_spin.value(), "window_height": self.height_spin.value(),
            "screen_name": self.screen_combo.currentData(), "position": self.position_combo.currentData(),
            "pin_current": self.pin_check.isChecked(),
        }

    def _set_status(self, message, error=False):
        self.status_label.setText(str(message or ""))
        self.status_label.setStyleSheet("color: #b3263e;" if error else "color: #286743;")

    def _apply_preferences(self):
        try:
            values = self.preferences()
            result = self.monitor_window.apply_preferences(values)
            if isinstance(result, str) and result:
                self._set_status(result, error=True)
                return False
            if result is not None and result != "":
                raise TypeError("主程序返回了无法识别的设置应用结果")
            self._snapshot = dict(self.monitor_window.settings_snapshot())
            actual_layer = self._snapshot.get("layer_mode")
            layer_index = self.layer_combo.findData(actual_layer)
            if layer_index >= 0:
                self.layer_combo.setCurrentIndex(layer_index)
            self._sync_page_status()
            self.help_label.setText(shortcut_help(values["shortcuts"]))
            warning = getattr(self.monitor_window, "_layer_error", "")
            self._set_status(f"设置已应用；{warning}" if warning else "设置已应用。")
            return True
        except ValueError as error:
            self._set_status(str(error), error=True)
            return False
        except (TypeError, RuntimeError, OSError) as error:
            LOGGER.exception("应用桌面挂件设置失败")
            self._set_status(f"应用失败：{error}", error=True)
            return False

    def _accept_preferences(self):
        if self._apply_preferences():
            self.accept()
