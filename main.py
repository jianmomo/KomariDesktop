from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
from datetime import date, datetime
import json
import math
import os
import ssl
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from PySide6.QtCore import (
    QAbstractNativeEventFilter,
    QEvent,
    QLockFile,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QTimer,
    QObject,
    QThread,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QStyle,
    QSystemTrayIcon,
    QToolButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
# 便携嵌入式Python的._pth可能不包含脚本目录，只加入程序自身目录，避免依赖当前工作目录。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from desktop_controls import SettingsDialog, SHORTCUT_DEFAULTS, native_shortcut, normalize_shortcuts


APP_NAME = "KomariDesktop Qt Probe"
APP_VERSION = "1.0.0"
WINDOW_TITLE = "KomariDesktop Qt Probe"
KOMARI_BASE_URL = "https://vps.beihai.xyz"
KOMARI_REFRESH_MS = 15_000
KOMARI_NODES_TTL_SECONDS = 300
KOMARI_MAX_RETRY_MS = 300_000
HOTKEY_EDIT, HOTKEY_HIDE, HOTKEY_NEXT, HOTKEY_QUIT = 0x4B01, 0x4B02, 0x4B03, 0x4B04
HOTKEY_PREV, HOTKEY_PAGE_BASE, HOTKEY_PAGE_RESET = 0x4B05, 0x4B10, 0x4B1A
HOTKEY_SETTINGS = 0x4B06
WM_HOTKEY, WM_NCHITTEST, HTTRANSPARENT = 0x0312, 0x0084, -1
WM_APP_WAKE = 0x8065
MOD_ALT, MOD_CONTROL = 0x0001, 0x0002
# v6 用 452×538 窗口承载稿件的 440×526 面板，字号统一采用逻辑像素。
SETTINGS_VERSION = 7
REFERENCE_CARD_HEIGHTS = {"skin1": 178, "skin2": 178, "skin3": 186,
                          "skin4": 186, "skin5": 162, "skin6": 180}
MIN_REFRESH_SECONDS, MAX_REFRESH_SECONDS = 5, 300
MIN_CAROUSEL_SECONDS, MAX_CAROUSEL_SECONDS = 5, 120
SKIN_NAMES = {
    "skin1": "雾白蜡棕", "skin2": "石墨键帽", "skin3": "夜行分段",
    "skin4": "冷灰对比", "skin5": "夜行色块", "skin6": "暖沙折线",
}
# 参考稿的几何和文字基线。颜色仍由 ``_colors`` 提供，避免视觉令牌和
# 数据/交互逻辑混在一起；不同皮肤可以独立调整字号、内边距和延迟区高度。
SKIN_LAYOUTS = {
    "skin1": {
        "panel_radius": 14, "window_min": (360, 430), "window_preferred": (452, 538),
        "panel_margins": (18, 14, 18, 10),
        "node_padding": (12, 7, 12, 7), "node_spacing": 3,
        "metric_hspacing": 7, "metric_vspacing": 3, "details_spacing": 4,
        "title": 16, "summary": 10, "node_name": 15, "region": 10,
        "metric_label": 11, "metric_value": 16, "metric_unit": 11,
        "metric_height": 47, "chip_name": 10, "chip_value": 16,
        "chip_meta": 11, "chip_height": 72, "detail": 11,
    },
    "skin2": {
        "panel_radius": 14, "window_min": (360, 430), "window_preferred": (452, 538),
        "panel_margins": (18, 14, 18, 10),
        "node_padding": (12, 8, 12, 8), "node_spacing": 3,
        "metric_hspacing": 7, "metric_vspacing": 3, "details_spacing": 4,
        "title": 16, "summary": 10, "node_name": 15, "region": 10,
        "metric_label": 11, "metric_value": 16, "metric_unit": 11,
        "metric_height": 47, "chip_name": 10, "chip_value": 16,
        "chip_meta": 11, "chip_height": 64, "detail": 11,
    },
    "skin3": {
        "panel_radius": 14, "window_min": (380, 450), "window_preferred": (452, 538),
        "panel_margins": (18, 14, 18, 10),
        "node_padding": (12, 6, 12, 6), "node_spacing": 2,
        "metric_hspacing": 7, "metric_vspacing": 3, "details_spacing": 4,
        "title": 16, "summary": 10, "node_name": 15, "region": 10,
        "metric_label": 11, "metric_value": 16, "metric_unit": 11,
        "metric_height": 43, "row_name": 10, "row_value": 10,
        "row_meta": 10, "row_height": 26, "detail": 11,
    },
    "skin4": {
        "panel_radius": 14, "window_min": (380, 450), "window_preferred": (452, 538),
        "panel_margins": (18, 14, 18, 10),
        "node_padding": (12, 6, 12, 6), "node_spacing": 2,
        "metric_hspacing": 7, "metric_vspacing": 3, "details_spacing": 4,
        "title": 16, "summary": 10, "node_name": 15, "region": 10,
        "metric_label": 11, "metric_value": 16, "metric_unit": 11,
        "metric_height": 43, "row_name": 10, "row_value": 10,
        "row_meta": 10, "row_height": 26, "detail": 11,
    },
    "skin5": {
        "panel_radius": 14, "window_min": (380, 440), "window_preferred": (452, 538),
        "panel_margins": (18, 14, 18, 10),
        "node_padding": (12, 8, 12, 8), "node_spacing": 3,
        "metric_hspacing": 7, "metric_vspacing": 3, "details_spacing": 4,
        "title": 16, "summary": 10, "node_name": 15, "region": 10,
        "metric_label": 11, "metric_value": 16, "metric_unit": 11,
        "metric_height": 47, "block_name": 11, "block_value": 15,
        "block_meta": 11, "block_height": 42, "detail": 11,
    },
    "skin6": {
        "panel_radius": 14, "window_min": (380, 460), "window_preferred": (452, 538),
        "panel_margins": (18, 14, 18, 10),
        "node_padding": (12, 6, 12, 6), "node_spacing": 2,
        "metric_hspacing": 7, "metric_vspacing": 3, "details_spacing": 4,
        "title": 16, "summary": 10, "node_name": 15, "region": 10,
        "metric_label": 11, "metric_value": 16, "metric_unit": 11,
        "metric_height": 43, "trend_meta": 10, "trend_height": 56, "detail": 11,
    },
}
GWL_EXSTYLE = -20
WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = 0x20, 0x80
WS_EX_APPWINDOW, WS_EX_NOACTIVATE = 0x40000, 0x08000000
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x0001, 0x0002, 0x0010, 0x0040
SWP_NOZORDER, SWP_NOOWNERZORDER, SWP_FRAMECHANGED = 0x0004, 0x0200, 0x0020
HWND_TOP, HWND_BOTTOM = 0, 1
HWND_TOPMOST, HWND_NOTOPMOST, GW_HWNDPREV = -1, -2, 3
SW_RESTORE = 9
IS_WINDOWS = sys.platform == "win32"


def normalize_komari_url(value, *, allow_insecure_http=False):
    """校验监控地址，默认只接受 HTTPS；仅回环地址允许本地 HTTP 测试。"""
    candidate = str(value or KOMARI_BASE_URL).strip().rstrip("/")
    if len(candidate) > 2048:
        return KOMARI_BASE_URL
    try:
        parsed = urlsplit(candidate)
        host = (parsed.hostname or "").lower().rstrip(".")
    except (TypeError, ValueError):
        return KOMARI_BASE_URL
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or not host
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return KOMARI_BASE_URL
    loopback = host in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme == "http" and not (allow_insecure_http or loopback):
        return KOMARI_BASE_URL
    return candidate

if IS_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    _user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    _user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _user32.SetWindowPos.restype = wintypes.BOOL
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _user32.RegisterHotKey.restype = wintypes.BOOL
    _user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    _user32.UnregisterHotKey.restype = wintypes.BOOL
    _user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetShellWindow.restype = wintypes.HWND
    _user32.FindWindowExW.restype = wintypes.HWND
    _user32.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
    _user32.GetClassNameW.restype = ctypes.c_int
    _user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.ShowWindow.restype = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.BringWindowToTop.restype = wintypes.BOOL
    _user32.BringWindowToTop.argtypes = [wintypes.HWND]
    _user32.SetForegroundWindow.restype = wintypes.BOOL
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.GetWindow.restype = wintypes.HWND
    _user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    _user32.PostMessageW.restype = wintypes.BOOL
    _user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]


def fit_geometry(rect, available):
    """所有尺寸使用Qt逻辑坐标；支持负坐标显示器及工作区缩小。"""
    width = min(max(1, rect.width()), max(1, available.width()))
    height = min(max(1, rect.height()), max(1, available.height()))
    x = max(available.left(), min(rect.left(), available.right() - width + 1))
    y = max(available.top(), min(rect.top(), available.bottom() - height + 1))
    return QRect(x, y, width, height)


class _Message(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


class HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, window):
        super().__init__()
        self.window = window

    def nativeEventFilter(self, event_type, message):
        if IS_WINDOWS and event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            try:
                msg = ctypes.cast(int(message), ctypes.POINTER(_Message)).contents
                # native过滤期间不能用winId()懒创建句柄，否则会再次进入本过滤器。
                if int(msg.hwnd or 0) != int(self.window.effectiveWinId() or 0):
                    return False, 0
                if msg.message == WM_APP_WAKE:
                    if self.window.hidden:
                        self.window.toggle_hidden()
                    self.window.open_settings()
                    return True, 0
                if msg.message == WM_HOTKEY:
                    actions = {
                        HOTKEY_EDIT: self.window.toggle_editing,
                        HOTKEY_HIDE: self.window.toggle_hidden,
                        HOTKEY_PREV: lambda: self.window.next_page(-1),
                        HOTKEY_NEXT: lambda: self.window.next_page(1),
                        HOTKEY_PAGE_RESET: self.window.clear_page_pin,
                        HOTKEY_QUIT: self.window.close,
                        HOTKEY_SETTINGS: self.window.open_settings,
                    }
                    for page_number in range(1, 10):
                        actions[HOTKEY_PAGE_BASE + page_number - 1] = (
                            lambda page_number=page_number: self.window.jump_to_page(page_number, pin=True)
                        )
                    action = actions.get(int(msg.wParam))
                    if action:
                        action()
                        return True, 0
                elif msg.message == WM_NCHITTEST and self.window.locked and self.window.click_through:
                    return True, HTTRANSPARENT
            except (TypeError, ValueError, OSError):
                pass
        return False, 0


def _qcolor(value, alpha=None):
    result = QColor(value)
    if alpha is not None:
        result.setAlpha(max(0, min(255, int(alpha))))
    return result


class KomariClient:
    """Komari 游客只读客户端；只调用公开节点和批量状态接口。"""

    def __init__(self, base_url=KOMARI_BASE_URL, timeout=8, allow_insecure_http=False):
        self.base_url = normalize_komari_url(
            base_url,
            allow_insecure_http=allow_insecure_http or "--allow-insecure-http" in sys.argv,
        )
        self.timeout = max(2, int(timeout))
        self._nodes = None
        self._nodes_updated_at = 0.0
        self._cancelled = threading.Event()
        self._opener = None

    def cancel(self):
        self._cancelled.set()

    def _request_json(self, path, payload=None):
        if self._cancelled.is_set():
            raise RuntimeError("请求已取消")
        body = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "KomariDesktop/0.1 (guest-readonly)",
        }
        method = "GET"
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
            method = "POST"
        request = urllib.request.Request(
            f"{self.base_url}{path}", headers=headers, data=body, method=method
        )
        try:
            if self._opener is None:
                context = ssl.create_default_context()
                context.set_alpn_protocols(["http/1.1"])
                self._opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
            with self._opener.open(request, timeout=self.timeout) as response:
                # 限制异常响应的大小，避免错误页面或损坏接口无限占用内存。
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise RuntimeError("接口响应过大")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("网络连接失败") from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("接口返回不是有效 JSON") from exc
        if not isinstance(data, dict):
            raise RuntimeError("接口返回格式异常")
        if data.get("status") == "error":
            raise RuntimeError(str(data.get("message") or "接口返回错误"))
        if "error" in data:
            error = data.get("error")
            message = error.get("message") if isinstance(error, dict) else error
            raise RuntimeError(str(message or "RPC 返回错误"))
        return data

    def fetch_samples(self):
        now = time.monotonic()
        if self._nodes is None or now - self._nodes_updated_at >= KOMARI_NODES_TTL_SECONDS:
            nodes_payload = self._request_json("/api/nodes")
            nodes = nodes_payload.get("data")
            if not isinstance(nodes, list):
                raise RuntimeError("节点列表格式异常")
            self._nodes = nodes
            self._nodes_updated_at = time.monotonic()
        nodes = self._nodes
        node_ids = [str(node.get("uuid")) for node in nodes if isinstance(node, dict) and node.get("uuid")]
        statuses = {}
        if node_ids:
            status_payload = self._request_json(
                "/api/rpc2",
                {
                    "jsonrpc": "2.0",
                    "method": "common:getNodesLatestStatus",
                    "params": {"uuids": node_ids},
                    "id": "komari-desktop-status",
                },
            )
            result = status_payload.get("result", {})
            if not isinstance(result, dict):
                raise RuntimeError("实时状态格式异常")
            statuses = result
        return self._build_samples(nodes, statuses)

    @staticmethod
    def _number(value):
        return float(value) if (
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        ) else None

    @staticmethod
    def _safe_text(value, fallback="", limit=256):
        if value is None:
            text = fallback
        else:
            text = str(value).strip()
        return text[:limit]

    @staticmethod
    def _format_bytes(value):
        value = KomariClient._number(value)
        if value is None or value < 0:
            return None
        units = ("B", "KiB", "MiB", "GiB", "TiB")
        index = 0
        while value >= 1024 and index < len(units) - 1:
            value /= 1024
            index += 1
        precision = 0 if value >= 100 else 1
        return f"{value:.{precision}f} {units[index]}"

    @staticmethod
    def _region_code(value):
        """把 Komari 的国旗区域字符转换为稳定的 ASCII 两字母代码。"""
        text = str(value or "").strip()[:32]
        letters = []
        for char in text:
            codepoint = ord(char)
            if 0x1F1E6 <= codepoint <= 0x1F1FF:
                letters.append(chr(ord("A") + codepoint - 0x1F1E6))
        if len(letters) == 2:
            return "".join(letters)
        ascii_text = "".join(char for char in text if char.isascii() and char.isalnum())
        return ascii_text[:4].upper()

    @classmethod
    def _build_samples(cls, nodes, statuses):
        samples = []
        carrier_ids = {"移动": (1, 4), "联通": (2, 5), "电信": (3, 6)}
        for node in nodes:
            if not isinstance(node, dict) or not node.get("uuid"):
                continue
            node_id = cls._safe_text(node["uuid"], "", 128)
            if not node_id:
                continue
            status = statuses.get(node_id, {}) if isinstance(statuses, dict) else {}
            if not isinstance(status, dict):
                status = {}
            online = status.get("online")
            status_key = "online" if online is True else "offline" if online is False else "stale"

            ram_used = cls._number(status.get("ram"))
            ram_total = cls._number(status.get("ram_total")) or cls._number(node.get("mem_total"))
            memory = 100 * ram_used / ram_total if ram_used is not None and ram_total and ram_total > 0 else None

            network = status.get("network") if isinstance(status.get("network"), dict) else {}
            upload_raw = status.get("net_out", network.get("up"))
            download_raw = status.get("net_in", network.get("down"))
            upload = cls._number(upload_raw)
            download = cls._number(download_raw)
            upload = upload / 1024 if upload is not None and upload >= 0 else None
            download = download / 1024 if download is not None and download >= 0 else None

            total_up = cls._number(status.get("net_total_up", network.get("totalUp")))
            total_down = cls._number(status.get("net_total_down", network.get("totalDown")))
            limit = cls._number(node.get("traffic_limit"))
            traffic = "—"
            traffic_label = "已用"
            if total_up is not None and total_down is not None and limit is not None and limit > 0:
                used = cls._format_bytes(total_up + total_down)
                limit_text = cls._format_bytes(limit)
                if used and limit_text:
                    # 公开字段只保证是累计上下行计数，不假定一定按月重置。
                    traffic = f"{used} / {limit_text}"
                    traffic_label = "累计"

            expires_at = node.get("expired_at")
            expires_text = cls._safe_text(expires_at, "", 32)
            expires = expires_text[:10] if expires_text else "—"
            group = cls._safe_text(node.get("group"), "", 128)
            region = group or cls._safe_text(node.get("region"), "—", 128)
            code = cls._region_code(node.get("region"))
            pings = status.get("ping") if isinstance(status.get("ping"), dict) else {}
            latency, loss = {}, {}
            for carrier, task_ids in carrier_ids.items():
                entry = None
                for task_id in task_ids:
                    candidate = pings.get(str(task_id), pings.get(task_id))
                    if isinstance(candidate, dict) and cls._number(candidate.get("latest")) is not None:
                        entry = candidate
                        break
                if entry is not None:
                    # 保留接口精度给趋势图，整数化只在文字展示时进行。
                    latency[carrier] = cls._number(entry.get("latest"))
                    loss_value = cls._number(entry.get("loss"))
                    loss[carrier] = loss_value if loss_value is not None and loss_value >= 0 else None
                else:
                    latency[carrier] = None
                    loss[carrier] = None

            samples.append(
                {
                    "id": node_id,
                    "name": cls._safe_text(node.get("name"), node_id, 160) or node_id,
                    "region": region,
                    "code": code,
                    "status": status_key,
                    "cpu": cls._number(status.get("cpu")),
                    "memory": memory,
                    "upload": upload,
                    "download": download,
                    "traffic": traffic,
                    "traffic_label": traffic_label,
                    "expires": expires,
                    "latency": latency,
                    "loss": loss,
                    "updated_at": cls._safe_text(
                        status.get("time") or status.get("updated_at"), "", 64
                    ) or None,
                }
            )
        return samples


class LiveRefreshWorker(QObject):
    succeeded = Signal(object, str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, base_url, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.client = KomariClient(base_url)

    @Slot()
    def run(self):
        try:
            samples = self.client.fetch_samples()
            self.succeeded.emit(samples, datetime.now().strftime("%H:%M:%S"))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            self.finished.emit()


class SurfaceFrame(QFrame):
    """只负责绘制稳定的桌面控件表面，排版交给 Qt Layout。"""

    def __init__(self, role, parent=None):
        super().__init__(parent)
        self.role = role
        self.colors = {}
        self.opacity_percent = 90
        self.selected = False
        self.status_key = "online"
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_surface(self, colors, opacity_percent=90, selected=False, status_key="online"):
        if (self.colors is colors and self.opacity_percent == opacity_percent
                and self.selected == selected and self.status_key == status_key):
            return
        self.colors = colors
        self.opacity_percent = opacity_percent
        self.selected = selected
        self.status_key = status_key
        self.update()

    def paintEvent(self, event):
        del event
        if not self.colors:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        skin1 = self.colors.get("skin") == "skin1"
        if self.role == "panel":
            radius = float(SKIN_LAYOUTS.get(self.colors.get("skin"), SKIN_LAYOUTS["skin1"])["panel_radius"])
            base_alpha = round(255 * self.opacity_percent / 100)
            painter.setPen(QPen(_qcolor(self.colors["panel_border"], min(210, base_alpha + 20)), 1.0))
            # 样例图六款面板均为平面底色；桌面透明度由 alpha 单独控制，
            # 不再用渐变改变设计稿的色相。
            gradient = QLinearGradient(0, 0, 0, self.height())
            gradient.setColorAt(0, _qcolor(self.colors["panel_top"], base_alpha))
            gradient.setColorAt(1, _qcolor(self.colors["panel_bottom"], base_alpha))
            painter.setBrush(gradient)
            painter.drawRoundedRect(rect, radius, radius)
            if not skin1:
                painter.setPen(QPen(_qcolor(self.colors["panel_highlight"], min(100, base_alpha)), 1))
                painter.drawLine(rect.left() + radius, rect.top() + 1, rect.right() - radius, rect.top() + 1)
        elif self.role == "toolbar":
            if skin1:
                painter.setPen(QPen(_qcolor(self.colors["rule"], 180), 1))
                painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
                painter.end()
                return
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(_qcolor(self.colors["toolbar"], 225))
            painter.drawRoundedRect(rect, 10, 10)
            painter.setPen(QPen(_qcolor(self.colors["rule"], 110), 1))
            painter.drawRoundedRect(rect, 10, 10)
        elif self.role == "card":
            # 参考图中的 VPS 节点不是独立浮动卡片，而是统一面板中的
            # 分隔区域；只有三网指标块使用圆角色块。所有皮肤统一用
            # 低对比度分隔线，避免出现与参考图不符的“卡片套卡片”。
            painter.setPen(QPen(_qcolor(self.colors["rule"], 175), 1))
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        elif self.role == "metric":
            # 六款参考图的 CPU/内存/速率都是“文字 + 细进度线”，
            # 不使用四个独立的圆角盒子。
            painter.end()
            return
        elif self.role == "chip":
            if skin1:
                fill = getattr(self, "fill_color", self.accent)
                painter.setPen(QPen(_qcolor(self.colors.get("chip_border", self.colors["rule"]), 120), 1))
                painter.setBrush(_qcolor(fill, 245))
                painter.drawRoundedRect(rect, 10, 10)
                painter.end()
                return
            if getattr(self, "dark_chip", False):
                fill = getattr(self, "fill_color", self.accent)
                painter.setPen(QPen(_qcolor(self.colors["card_border"], 150), 1))
                painter.setBrush(_qcolor(fill, 238))
                painter.drawRoundedRect(rect, 9, 9)
                painter.setPen(QPen(_qcolor(fill, 255), 1))
                painter.drawLine(rect.left() + 9, rect.top() + 1, rect.right() - 9, rect.top() + 1)
                painter.end()
                return
            radius = 6.0
            painter.setPen(Qt.PenStyle.NoPen)
            chip_key = getattr(self, "carrier", "")
            chip_fill = self.colors.get(f"chip_{chip_key}", self.colors["chip"])
            painter.setBrush(_qcolor(chip_fill, 224))
            painter.drawRoundedRect(rect, radius, radius)
            painter.setPen(QPen(_qcolor(self.accent, 130), 1))
            painter.drawRoundedRect(rect, radius, radius)
            painter.setPen(QPen(_qcolor(self.accent, 225), 3))
            painter.drawLine(rect.left() + 1.5, rect.top() + radius, rect.left() + 1.5, rect.bottom() - radius)
        painter.end()


class DashboardHeader(QFrame):
    """标题区自身绘制分隔线，避免额外 QFrame 改变分页可用高度。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rule_color = QColor(0, 0, 0, 0)
        self.rule_enabled = False
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_rule(self, color, enabled=True):
        color = color if isinstance(color, QColor) else QColor(color)
        if self.rule_color == color and self.rule_enabled == bool(enabled):
            return
        self.rule_color = color
        self.rule_enabled = bool(enabled)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.rule_enabled:
            return
        painter = QPainter(self)
        painter.setPen(QPen(self.rule_color, 1))
        y = max(0, self.height() - 1)
        painter.drawLine(0, y, max(0, self.width() - 1), y)
        painter.end()


class StatusSummaryLabel(QLabel):
    """按稿件绘制 8px 状态符号，避免文本圆点受字体和行高影响。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.states = None
        self._states_key = None

    def set_states(self, counts=None, colors=None):
        if counts is None:
            if self.states is None:
                return
            self.states = None
            self._states_key = None
            self.update()
            return
        counts_key = tuple(counts)
        states_key = (counts_key, id(colors))
        if self._states_key == states_key:
            return
        self.states = (counts_key, colors)
        self._states_key = states_key
        self.update()

    def paintEvent(self, event):
        if self.states is None:
            super().paintEvent(event)
            return
        counts, colors = self.states
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(_font(11))
        x = 0.0
        for index, (count, text, key) in enumerate(zip(counts, ("在线", "离线", "数据过期"),
                                                      ("online", "muted", "stale"))):
            circle = QRectF(x + 0.5, (self.height() - 8) / 2, 8, 8)
            painter.setPen(QPen(colors[key], 1))
            painter.setBrush(colors[key] if index == 0 else Qt.BrushStyle.NoBrush)
            painter.drawEllipse(circle)
            if index == 2:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(colors[key])
                painter.drawPie(circle, 90 * 16, 180 * 16)
            label = f"{count} {text}"
            advance = QFontMetrics(painter.font()).horizontalAdvance(label)
            painter.setPen(colors["muted"])
            painter.drawText(QRectF(x + 12, 0, advance + 1, self.height()),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            x += 12 + advance + 10
        painter.end()


class MetricBlock(SurfaceFrame):
    def __init__(self, label, accent, parent=None):
        super().__init__("metric", parent)
        self.label_text = label
        self.accent = accent
        self.compact = False
        self.skin1 = False
        self.value = None
        self.metric_key = ""
        self.design_spec = {}
        self._value_key = None
        self.title_label = QLabel(label, self)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.value_label = QLabel("—", self)
        self.value_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.unit_label = QLabel("", self)
        self.unit_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.progress = QProgressBar(self)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setFixedHeight(4)
        self.progress.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 6, 8, 6)
        layout.setSpacing(1)
        layout.addWidget(self.title_label)
        self.value_row = QHBoxLayout()
        self.value_row.setContentsMargins(0, 0, 0, 0)
        self.value_row.setSpacing(2)
        self.value_row.addWidget(self.value_label)
        self.value_row.addWidget(self.unit_label)
        self.value_row.addStretch(1)
        layout.addLayout(self.value_row)
        layout.addWidget(self.progress)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(44)

    def set_design(self, spec):
        self.design_spec = spec or {}

    def set_compact(self, compact):
        self.compact = compact
        is_rate = self.metric_key in {"upload", "download"}
        label_size = int(self.design_spec.get("metric_label", 10 if compact else 11))
        value_size = int(self.design_spec.get("metric_value", 16 if not compact else 15))
        unit_size = int(self.design_spec.get("metric_unit", 10 if compact else 11))
        if compact:
            # 参考稿在 440px 基准宽度下仍保持清晰字号；只压缩速率单位，
            # 不把标题和值整体缩小，避免“控件还在但文字看不见”。
            label_size = max(10, label_size)
            value_size = max(14, value_size)
            unit_size = max(9, unit_size - 1 if is_rate else unit_size)
        self.title_label.setFont(_font(label_size, QFont.Weight.Medium))
        self.value_label.setFont(_font(value_size, QFont.Weight.DemiBold))
        self.unit_label.setFont(_font(unit_size, QFont.Weight.Normal))
        self.title_label.setStyleSheet(f"color: {_qcolor(self.colors.get('muted', '#8095a4')).name()};")
        self.value_label.setStyleSheet(f"color: {_qcolor(self.colors.get('fg', '#edf4f6')).name()};")
        self.unit_label.setStyleSheet(f"color: {_qcolor(self.colors.get('muted', '#8095a4')).name()};")
        self.value_row.setSpacing(1 if compact and is_rate else 2 if compact else 3)
        horizontal_margin = 4 if compact and is_rate else 5 if compact else 8
        vertical_margin = 3 if self.skin1 else 5
        metric_height = int(self.design_spec.get("metric_height", 47))
        if compact:
            metric_height = max(44, metric_height - 2)
        self.layout().setContentsMargins(horizontal_margin, vertical_margin, horizontal_margin, vertical_margin)
        self.setFixedHeight(metric_height)

    def set_value(self, value, unit=""):
        value_key = (value, unit, self.compact, id(self.colors))
        if self._value_key == value_key:
            return
        self._value_key = value_key
        self.value = value
        if isinstance(value, (int, float)) and math.isfinite(value):
            if unit == " KiB/s":
                # 紧凑卡片给单位预留空间；三位整数速率省略小数，避免数值和单位挤压。
                precision = 0 if self.compact and abs(value) >= 100 else 1
                self.value_label.setText(f"{value:.{precision}f}")
                self.unit_label.setText("KiB/s")
            else:
                self.value_label.setText(f"{value:.1f}{unit}")
                self.unit_label.setText("")
            value_style = f"color: {self.accent.name()};"
            if self.value_label.styleSheet() != value_style:
                self.value_label.setStyleSheet(value_style)
            if unit == "%":
                self.progress.setValue(max(0, min(100, int(value))))
                self.progress.show()
            else:
                self.progress.hide()
        else:
            self.value_label.setText("—")
            self.unit_label.setText("")
            value_style = f"color: {_qcolor(self.colors.get('subtle', '#8095a4')).name()};"
            if self.value_label.styleSheet() != value_style:
                self.value_label.setStyleSheet(value_style)
            self.progress.hide()

    def apply_theme(self, colors):
        if self.colors is colors:
            return
        self._value_key = None
        self.skin1 = colors.get("skin") == "skin1"
        self.accent = colors.get(f"metric_{self.metric_key}_accent", self.accent)
        self.set_surface(colors)
        self.title_label.setStyleSheet(f"color: {colors['muted'].name()};")
        self.value_label.setStyleSheet(
            f"color: {self.accent.name() if self.value is not None else colors['subtle'].name()};"
        )
        self.unit_label.setStyleSheet(f"color: {colors['muted'].name()};")
        self.progress.setStyleSheet(
            "QProgressBar { background: %s; border: 0; border-radius: 2px; }"
            "QProgressBar::chunk { background: %s; border-radius: 2px; }"
            % (colors["track"].name(), self.accent.name())
        )
        self.set_compact(self.compact)


class CarrierChip(SurfaceFrame):
    def __init__(self, carrier, accent, parent=None):
        super().__init__("chip", parent)
        self.carrier = carrier
        self.accent = accent
        self.fill_color = accent
        self.level_key = "unknown"
        self.skin1 = False
        self.dark_chip = False
        self.compact = False
        self.design_spec = {}
        self.latency_style = "chips"
        self.current_latency = None
        self.current_loss = None
        self.unavailable = True
        self._values_key = None
        self.name_label = QLabel(carrier, self)
        self.name_label.setTextFormat(Qt.TextFormat.RichText)
        self.name_label.setTextFormat(Qt.TextFormat.RichText)
        self.latency_label = QLabel("—", self)
        self.loss_label = QLabel("丢包 —", self)
        for label in (self.name_label, self.latency_label, self.loss_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.name_label.setFont(_font(10, QFont.Weight.DemiBold))
        self.latency_label.setFont(_font(14, QFont.Weight.DemiBold))
        self.loss_label.setFont(_font(10, QFont.Weight.Normal))
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(4)
        top.addWidget(self.name_label)
        top.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 4, 6, 4)
        layout.setSpacing(0)
        layout.addLayout(top)
        layout.addWidget(self.latency_label)
        layout.addWidget(self.loss_label)
        self.setMinimumHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_values(self, latency, loss, status_key="online"):
        self.current_latency = latency if isinstance(latency, (int, float)) else None
        self.current_loss = loss if isinstance(loss, (int, float)) else None
        values_key = (latency, loss, status_key, self.compact, id(self.colors))
        if self._values_key == values_key:
            return
        self._values_key = values_key
        unavailable = status_key == "offline" or not isinstance(latency, (int, float)) or latency <= 0
        self.unavailable = unavailable
        if self.skin1 or self.dark_chip:
            carrier_dot = {"移动": "#e84d9a", "联通": "#4c8fe9", "电信": "#8e63e8"}.get(self.carrier, "#7d7d7d")
            self.name_label.setText(f'<span style="color:{carrier_dot};">●</span> {self.carrier}')
            if unavailable:
                self.level_key = "unknown"
                self.fill_color = self.colors.get(
                    "level_unknown", self.colors.get("card_muted", self.colors.get("chip", self.accent))
                )
                self.latency_label.setText("—")
                loss_text = f" · 丢 {loss:.1f}%" if isinstance(loss, (int, float)) and loss > 0 else ""
                self.loss_label.setText(f"丢 {loss:.1f}%" if loss_text else "暂无延迟")
            else:
                latency_value = int(round(latency))
                level_text, self.level_key = _latency_grade(latency, loss)
                dark_level_fill = {
                    "excellent": "#34bf92", "good": "#8acb3f", "normal": "#f0c21b",
                    "poor": "#f28a32", "bad": "#d92f50", "unknown": "#51565e",
                }
                self.fill_color = self.colors.get(
                    f"level_{self.level_key}", QColor(dark_level_fill.get(self.level_key, "#51565e"))
                )
                self.latency_label.setText(f"{latency_value} ms")
                loss_text = f" · 丢 {loss:.1f}%" if isinstance(loss, (int, float)) and loss > 0 else ""
                self.loss_label.setText(f"{level_text}{loss_text}")
            text_color = self.colors.get(
                f"level_{self.level_key}_text",
                QColor("#ffffff") if self.level_key == "bad" else
                QColor("#26302d") if self.dark_chip else self.colors.get("fg", self.accent),
            )
            for label in (self.latency_label, self.loss_label):
                style = f"color: {text_color.name()};"
                if label.styleSheet() != style:
                    label.setStyleSheet(style)
            self.update()
            return
        if unavailable:
            self.latency_label.setText("—")
            self.loss_label.setText("丢 —" if self.compact else "丢包 —")
            self.update()
            return
        self.latency_label.setText(f"{int(round(latency))}ms" if self.compact else f"{int(round(latency))} ms")
        self.loss_label.setText(
            ("丢 —" if self.compact else "丢包 —")
            if loss is None else
            (f"丢{loss:.1f}%" if self.compact else f"丢包 {loss:.1f}%")
        )
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.skin1 or self.unavailable or self.latency_style in {"chips", "blocks"}:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, right = 8.0, max(8.0, float(self.width() - 8))
        y = float(self.height() - 7)
        track = _qcolor(self.colors.get("track", "#7b8490"), 145)
        accent = _qcolor(self.accent, 235)
        latency = max(0.0, min(600.0, float(self.current_latency or 0.0)))
        ratio = max(0.0, min(1.0, latency / 300.0))
        if self.latency_style == "segments":
            count = 12
            gap = 3.0
            segment_width = max(3.0, (right - left - gap * (count - 1)) / count)
            filled = max(1, min(count, int(round((1.0 - ratio) * count))))
            for index in range(count):
                x = left + index * (segment_width + gap)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(accent if index < filled else track)
                painter.drawRoundedRect(QRectF(x, y - 4, segment_width, 4), 1.5, 1.5)
        elif self.latency_style == "bars":
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(track)
            painter.drawRoundedRect(QRectF(left, y - 4, right - left, 4), 2, 2)
            painter.setBrush(accent)
            painter.drawRoundedRect(QRectF(left, y - 4, (right - left) * (1.0 - ratio), 4), 2, 2)
        elif self.latency_style == "trend":
            spread = min(5.0, 1.5 + latency / 120.0)
            points = (
                (left, y - 2 - spread),
                (left + (right - left) * 0.35, y - 2 + spread * 0.5),
                (left + (right - left) * 0.68, y - 2 - spread * 0.35),
                (right, y - 2 + spread * 0.2),
            )
            painter.setPen(QPen(accent, 1.6))
            for first, second in zip(points, points[1:]):
                painter.drawLine(QPoint(int(first[0]), int(first[1])), QPoint(int(second[0]), int(second[1])))
        painter.end()

    def set_compact(self, compact):
        self.compact = compact
        name_size = int(self.design_spec.get("chip_name", 10))
        value_size = int(self.design_spec.get("chip_value", 16))
        meta_size = int(self.design_spec.get("chip_meta", 10))
        if compact:
            name_size = max(10, name_size)
            value_size = max(15, value_size)
            meta_size = max(9, meta_size)
        if self.skin1 or self.dark_chip:
            self.name_label.setFont(_font(name_size, QFont.Weight.DemiBold))
            self.latency_label.setFont(_font(value_size, QFont.Weight.DemiBold))
            self.loss_label.setFont(_font(meta_size, QFont.Weight.DemiBold))
            self.layout().setContentsMargins(7 if compact else 8, 5, 7 if compact else 8, 5)
            base_height = int(self.design_spec.get("chip_height", 72))
            if compact:
                base_height = max(58 if self.dark_chip else 66, base_height - 4)
            self.setMinimumHeight(base_height)
            return
        self.name_label.setFont(_font(name_size, QFont.Weight.DemiBold))
        self.latency_label.setFont(_font(max(14, value_size - 1), QFont.Weight.DemiBold))
        self.loss_label.setFont(_font(meta_size, QFont.Weight.Normal))
        self.layout().setContentsMargins(6 if compact else 7, 4, 5 if compact else 6, 4)
        self.setMinimumHeight(48 if compact else 52)

    def set_design(self, spec):
        self.design_spec = spec or {}
        self.set_compact(self.compact)

    def apply_theme(self, colors):
        if self.colors is colors:
            return
        self._values_key = None
        self.skin1 = colors.get("skin") == "skin1"
        self.dark_chip = colors.get("skin") == "skin2"
        self.latency_style = colors.get("latency_style", "chips")
        self.accent = colors.get(f"carrier_{self.carrier}", self.accent)
        self.fill_color = colors.get("level_unknown", self.accent) if self.skin1 else self.accent
        self.set_surface(colors)
        if self.skin1 or self.dark_chip:
            self.name_label.setTextFormat(Qt.TextFormat.RichText)
            self.name_label.setStyleSheet(f"color: {colors['fg'].name()};")
            self.latency_label.setStyleSheet(f"color: {colors['fg'].name()};")
            self.loss_label.setStyleSheet(f"color: {colors['fg'].name()};")
            self.set_compact(self.compact)
            return
        self.name_label.setStyleSheet(f"color: {self.accent.name()};")
        self.latency_label.setStyleSheet(f"color: {self.accent.name()};")
        self.loss_label.setStyleSheet(f"color: {colors['muted'].name()};")


def _font(size, weight=QFont.Weight.Normal):
    # 参考稿按 Windows 中文桌面字体设计；显式声明回退顺序，避免仅依赖
    # Segoe UI 的系统临时回退造成字宽、字重和基线在不同机器上漂移。
    font = QFont()
    try:
        font.setFamilies(["Segoe UI", "Microsoft YaHei UI", "Microsoft YaHei", "Arial"])
    except AttributeError:  # 兼容极少数旧 Qt 构建
        font.setFamily("Segoe UI")
    font.setPixelSize(int(size))
    font.setWeight(weight)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def _number_font(size, stretch=100):
    """稿件使用紧凑数字；独立于中文回退字体，避免字宽和字重失真。"""
    font = _font(size, QFont.Weight.DemiBold)
    font.setFamilies(["Bahnschrift", "Segoe UI", "Arial"])
    font.setStretch(stretch)
    return font


def _latency_grade(latency, loss):
    """把已有延迟/丢包数据转换为展示等级，不为缺失数据补造数值。"""
    if isinstance(loss, (int, float)) and math.isfinite(loss) and loss >= 3:
        return "差", "bad"
    if not isinstance(latency, (int, float)) or not math.isfinite(latency) or latency <= 0:
        return "未知", "unknown"
    if latency < 60:
        return "优秀", "excellent"
    if latency < 120:
        return "很好", "good"
    if latency < 200:
        return "一般", "normal"
    if latency < 300:
        return "较差", "poor"
    return "差", "bad"


class LatencyRow(QWidget):
    """皮肤 3/4 使用的全宽运营商延迟行。"""

    def __init__(self, carrier, accent, visual_style="segments", parent=None):
        super().__init__(parent)
        self.carrier = carrier
        self.accent = accent
        self.visual_style = visual_style
        self.colors = {}
        self.latency = None
        self.loss = None
        self.unavailable = True
        self.level_key = "unknown"
        self.fill_color = accent
        self.design_spec = {}
        self.compact = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.name_label = QLabel(carrier, self)
        self.name_label.setTextFormat(Qt.TextFormat.RichText)
        self.name_label.setFixedWidth(42)
        self.name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.latency_label = QLabel("—", self)
        self.latency_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.latency_label.setFixedWidth(56)
        self.latency_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.quality_label = QLabel("暂无", self)
        self.quality_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.quality_label.setMinimumWidth(66)
        self.quality_label.setMaximumWidth(110)
        self.quality_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(5)
        layout.addWidget(self.name_label)
        layout.addStretch(1)
        layout.addWidget(self.latency_label)
        layout.addWidget(self.quality_label)

    def set_compact(self, compact):
        base_height = int(self.design_spec.get("row_height", 30))
        self.setMinimumHeight(max(24, base_height - (2 if compact else 0)))
        name_size = int(self.design_spec.get("row_name", 10))
        value_size = int(self.design_spec.get("row_value", 10))
        meta_size = int(self.design_spec.get("row_meta", 10))
        self.name_label.setFont(_font(max(9, name_size), QFont.Weight.DemiBold))
        self.latency_label.setFont(_font(max(10, value_size), QFont.Weight.DemiBold))
        self.quality_label.setFont(_font(max(9, meta_size), QFont.Weight.Normal))

    def set_design(self, spec):
        self.design_spec = spec or {}
        self.set_compact(self.height() < 32)

    def apply_theme(self, colors):
        self.colors = colors
        self.visual_style = colors.get("latency_style", self.visual_style)
        self.accent = colors.get(f"carrier_{self.carrier}", self.accent)
        self.name_label.setText(f'<span style="color:{self.accent.name()};">●</span> {self.carrier}')
        self.name_label.setStyleSheet(f"color: {colors['fg'].name()};")
        self.latency_label.setStyleSheet(f"color: {colors['fg'].name()};")
        self.quality_label.setStyleSheet(f"color: {colors['muted'].name()};")
        self.update()

    def set_values(self, latency, loss, status_key="online"):
        self.latency = latency if isinstance(latency, (int, float)) else None
        self.loss = loss if isinstance(loss, (int, float)) else None
        self.unavailable = status_key == "offline" or self.latency is None or self.latency <= 0
        if self.unavailable:
            self.level_key = "unknown"
            self.fill_color = self.colors.get("level_unknown", self.accent)
            self.latency_label.setText("—")
            self.quality_label.setText("暂无" if status_key != "offline" else "离线")
            self.quality_label.setStyleSheet(f"color: {self.colors.get('muted', self.accent).name()};")
        else:
            level_text, level_key = _latency_grade(self.latency, self.loss)
            self.level_key = level_key
            self.fill_color = self.colors.get(f"level_{level_key}", self.accent)
            self.latency_label.setText(f"{int(round(self.latency))} ms")
            loss_text = f" · 丢 {self.loss:.1f}%" if self.loss is not None and self.loss > 0 else ""
            self.quality_label.setText(f"{level_text}{loss_text}")
            level_color = self.colors.get(f"level_{level_key}", self.accent)
            if isinstance(level_color, QColor):
                self.quality_label.setStyleSheet(f"color: {level_color.name()};")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = self.colors or {}
        track = _qcolor(colors.get("track", "#68727c"), 150)
        left = 54.0
        right = max(left + 20.0, float(self.width() - 174))
        y = float(self.height() / 2 + 4)
        if not self.unavailable:
            latency = max(0.0, min(600.0, float(self.latency or 0.0)))
            ratio = max(0.0, min(1.0, latency / 300.0))
            painter.setPen(Qt.PenStyle.NoPen)
            if self.visual_style == "bars":
                painter.setBrush(track)
                painter.drawRoundedRect(QRectF(left, y - 3, right - left, 6), 3, 3)
                painter.setPen(QPen(_qcolor(colors.get("subtle", "#8a929d"), 150), 1))
                for marker in (0.25, 0.5, 0.75):
                    marker_x = left + (right - left) * marker
                    painter.drawLine(QPoint(int(marker_x), int(y - 7)), QPoint(int(marker_x), int(y + 7)))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(_qcolor(self.fill_color, 225))
                painter.drawRoundedRect(QRectF(left, y - 3, (right - left) * (1 - ratio), 6), 3, 3)
            else:
                count = 12
                gap = 3.0
                segment_width = max(3.0, (right - left - gap * (count - 1)) / count)
                filled = max(1, min(count, int(round((1 - ratio) * count))))
                for index in range(count):
                    x = left + index * (segment_width + gap)
                    painter.setBrush(_qcolor(self.fill_color, 225) if index < filled else track)
                    painter.drawRoundedRect(QRectF(x, y - 3, segment_width, 6), 2, 2)
        else:
            painter.setPen(QPen(track, 1))
            painter.drawLine(QPoint(int(left), int(y)), QPoint(int(right), int(y)))
        painter.end()
        super().paintEvent(event)


class LatencyBlock(QWidget):
    """皮肤 5 使用的紧凑彩色延迟色块。"""

    def __init__(self, carrier, accent, parent=None):
        super().__init__(parent)
        self.carrier = carrier
        self.accent = accent
        self.colors = {}
        self.latency = None
        self.loss = None
        self.unavailable = True
        self.level_key = "unknown"
        self.fill_color = accent
        self.design_spec = {}
        self.compact = False
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumHeight(38)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.name_label = QLabel(carrier, self)
        self.name_label.setTextFormat(Qt.TextFormat.RichText)
        self.value_label = QLabel("—", self)
        self.quality_label = QLabel("暂无", self)
        for label in (self.name_label, self.value_label, self.quality_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.quality_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(3)
        layout.addWidget(self.name_label)
        layout.addWidget(self.value_label)
        layout.addStretch(1)
        layout.addWidget(self.quality_label)

    def set_compact(self, compact):
        base_height = int(self.design_spec.get("block_height", 38))
        self.setMinimumHeight(max(32, base_height - (2 if compact else 0)))
        name_size = int(self.design_spec.get("block_name", 10))
        value_size = int(self.design_spec.get("block_value", 15))
        meta_size = int(self.design_spec.get("block_meta", 10))
        # 皮肤 5 三个色块同排，设计稿使用紧凑的单行文字；
        # 不允许某一列的长数值把运营商名或等级挤成空白。
        name_size = min(10, name_size)
        value_size = min(13, value_size)
        meta_size = min(10, meta_size)
        if compact:
            name_size = max(9, min(10, name_size))
            value_size = max(12, min(14, value_size - 1))
            meta_size = max(9, min(10, meta_size))
            self.layout().setContentsMargins(5, 3, 5, 3)
            self.layout().setSpacing(4)
        else:
            self.layout().setContentsMargins(7, 4, 7, 4)
            self.layout().setSpacing(5)
        dot = f'<span style="color:{self.accent.name()};">●</span>'
        self.name_label.setText(f"{dot}{self.carrier}")
        self.name_label.setFont(_font(name_size, QFont.Weight.DemiBold))
        self.value_label.setFont(_font(value_size, QFont.Weight.DemiBold))
        self.quality_label.setFont(_font(meta_size, QFont.Weight.DemiBold))

    def set_design(self, spec):
        self.design_spec = spec or {}
        self.set_compact(self.height() < 38)

    def apply_theme(self, colors):
        self.colors = colors
        self.accent = colors.get(f"carrier_{self.carrier}", self.accent)
        self.fill_color = self.accent
        self.name_label.setText(f'<span style="color:{self.accent.name()};">●</span>{self.carrier}')
        self.name_label.setStyleSheet(f"color: {colors['fg'].name()};")
        self.value_label.setStyleSheet(f"color: {colors['fg'].name()};")
        self.quality_label.setStyleSheet(f"color: {colors['fg'].name()};")
        self.update()

    def set_values(self, latency, loss, status_key="online"):
        self.latency = latency if isinstance(latency, (int, float)) else None
        self.loss = loss if isinstance(loss, (int, float)) else None
        self.unavailable = status_key == "offline" or self.latency is None or self.latency <= 0
        self.value_label.setText("—" if self.unavailable else f"{int(round(self.latency))}ms")
        if self.unavailable:
            self.level_key = "unknown"
            self.fill_color = self.colors.get("card_muted", self.accent)
            self.quality_label.setText("离线" if status_key == "offline" else "暂无")
        else:
            level_text, self.level_key = _latency_grade(self.latency, self.loss)
            self.fill_color = self.colors.get(f"level_{self.level_key}", self.accent)
            # 皮肤 5 的丢包统一放在色块下方的摘要行，保证每个色块的
            # 名称、数值和等级始终完整显示，不因宽度不足被挤没。
            self.quality_label.setText(level_text)
        text_color = self.colors.get(f"level_{self.level_key}_text", self.colors.get("fg", self.accent))
        for label in (self.name_label, self.value_label, self.quality_label):
            label.setStyleSheet(f"color: {text_color.name()};")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        fill = self.fill_color if not self.unavailable else self.colors.get("card_muted", "#2a2d32")
        painter.setPen(QPen(_qcolor(self.colors.get("rule", "#68727c"), 145), 1))
        # 参考稿中的色块是实体色，不应因为窗口整体透明度再次被洗灰；
        # 透明度只作用于面板背景，数据色块保持足够对比度。
        painter.setBrush(_qcolor(fill, 92 if self.unavailable else 250))
        painter.drawRoundedRect(rect, 8, 8)
        painter.end()
        super().paintEvent(event)


class LatencyTrendPanel(QWidget):
    """皮肤 6 的真实历史趋势线，只使用已收到的采样值。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = {}
        self.values = {carrier: None for carrier in ("移动", "联通", "电信")}
        self.loss = {carrier: None for carrier in ("移动", "联通", "电信")}
        self.history = {carrier: [] for carrier in ("移动", "联通", "电信")}
        self.accents = {"移动": QColor("#e84d9a"), "联通": QColor("#4c8fe9"), "电信": QColor("#8e63e8")}
        self.design_spec = {}
        self.setMinimumHeight(68)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_design(self, spec):
        self.design_spec = spec or {}
        self.setMinimumHeight(int(self.design_spec.get("trend_height", 68)))

    def apply_theme(self, colors):
        if self.colors is colors:
            return
        self.colors = colors
        self.accents = {
            carrier: colors.get(f"carrier_{carrier}", self.accents[carrier])
            for carrier in self.accents
        }
        self.update()

    def set_values(self, latency_values, loss_values, status_key="online"):
        for carrier in self.values:
            value = latency_values.get(carrier) if isinstance(latency_values, dict) else None
            loss = loss_values.get(carrier) if isinstance(loss_values, dict) else None
            self.values[carrier] = value if isinstance(value, (int, float)) and value > 0 else None
            self.loss[carrier] = loss if isinstance(loss, (int, float)) else None
            if status_key == "online" and self.values[carrier] is not None:
                history = self.history[carrier]
                history.append(float(self.values[carrier]))
                del history[:-24]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        colors = self.colors or {}
        painter.setPen(QPen(_qcolor(colors.get("rule", "#bf8b67"), 150), 1))
        painter.setBrush(_qcolor(colors.get("metric", "#f0d2ba"), 150))
        painter.drawRoundedRect(rect, 7, 7)
        # 给右侧运营商标签预留固定逻辑宽度，避免“丢1.1%”在窄面板被裁切。
        label_width = 132.0
        left, right = 8.0, max(90.0, float(self.width() - label_width))
        top, bottom = 10.0, float(self.height() - 10)
        for grid_y in (top, (top + bottom) / 2, bottom):
            painter.setPen(QPen(_qcolor(colors.get("track", "#dcb59a"), 125), 1))
            painter.drawLine(QPoint(int(left), int(grid_y)), QPoint(int(right), int(grid_y)))
        for index, carrier in enumerate(("移动", "联通", "电信")):
            value = self.values[carrier]
            accent = self.accents[carrier]
            painter.setPen(QPen(_qcolor(accent, 225), 1.8))
            history = self.history[carrier]
            points = history[-24:] if len(history) >= 2 else ([value] if value is not None else [])
            if points:
                if len(points) == 1:
                    points = [points[0], points[0]]
                span = max(1, len(points) - 1)
                for point_index in range(span):
                    first_value = max(0.0, min(300.0, float(points[point_index])))
                    second_value = max(0.0, min(300.0, float(points[point_index + 1])))
                    x1 = left + (right - left) * point_index / span
                    x2 = left + (right - left) * (point_index + 1) / span
                    y1 = bottom - (bottom - top) * first_value / 300.0
                    y2 = bottom - (bottom - top) * second_value / 300.0
                    painter.drawLine(QPoint(int(x1), int(y1)), QPoint(int(x2), int(y2)))
            # 参考稿右侧标签用数值表达，单位由趋势区域上下文承载；
            # 省掉重复的“ms”后，丢包信息在窄面板仍能完整显示。
            label_value = "—" if value is None else f"{int(round(value))}"
            loss = self.loss[carrier]
            loss_text = "" if loss is None or loss <= 0 else f" · 丢{loss:.1f}%"
            painter.setPen(QPen(_qcolor(accent, 235), 1))
            painter.setFont(_font(int(self.design_spec.get("trend_meta", 10)), QFont.Weight.DemiBold))
            painter.drawText(QRectF(right + 8, 3 + index * 20, max(40.0, self.width() - right - 10), 18),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             f"{carrier} {label_value}{loss_text}")
        painter.end()
        super().paintEvent(event)


class ActionButton(QToolButton):
    """调整模式中的轻量控件按钮；锁定模式隐藏并保持鼠标穿透。"""

    def __init__(self, text, tooltip, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setToolTip(tooltip)
        self.setProperty("interactive_control", True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(27, 24)

    def apply_theme(self, colors):
        self.setFont(_font(11, QFont.Weight.DemiBold))
        self.setStyleSheet(
            "QToolButton { color: %s; background: %s; border: 1px solid %s; border-radius: 7px; padding: 0; }"
            "QToolButton:hover { color: %s; background: %s; border-color: %s; }"
            "QToolButton:pressed { color: %s; background: %s; }"
            "QToolButton:disabled { color: %s; background: transparent; border-color: transparent; }"
            % (
                colors["fg"].name(),
                _qcolor(colors["metric"], 190).name(QColor.NameFormat.HexArgb),
                _qcolor(colors["rule"], 180).name(QColor.NameFormat.HexArgb),
                colors["accent"].name(),
                _qcolor(colors["accent"], 35).name(QColor.NameFormat.HexArgb),
                _qcolor(colors["accent"], 210).name(QColor.NameFormat.HexArgb),
                colors["fg"].name(),
                _qcolor(colors["accent"], 85).name(QColor.NameFormat.HexArgb),
                colors["subtle"].name(),
            )
        )


class NodeCard(SurfaceFrame):
    def __init__(self, item, colors, mode, selected=False, parent=None):
        super().__init__("card", parent)
        self.item = item
        self.colors = colors
        self.skin = colors.get("skin", "skin1")
        self.skin1 = self.skin == "skin1"
        self.mode = mode
        self.selected = selected
        # 参考稿模式：节点卡片由固定设计坐标绘制，避免通用 Qt Layout
        # 在不同字号/DPI 下重新分配空间造成字体、间距和色块漂移。
        self.reference_paint = True
        self.compact_vertical = False
        self.status_key = "online"
        self._status_layout_key = None
        self.metric_blocks = []
        self.carrier_chips = []
        self.latency_rows = []
        self.latency_blocks = []
        self.trend_panel = None
        self._presentation_key = None
        self._display_key = None
        self._legacy_widgets_hidden = False
        self._build()
        self.update_item(item, mode, colors, selected)

    def _build(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        # 窗口最小宽度为 320 时，单列卡片仍能容纳两列指标和三网卡片。
        self.setMinimumWidth(260)
        self.main_layout = QVBoxLayout(self)
        if self.skin1:
            self.main_layout.setContentsMargins(0, 6, 0, 6)
            self.main_layout.setSpacing(3)
        else:
            self.main_layout.setContentsMargins(12, 10, 12, 9)
            self.main_layout.setSpacing(5)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(7)
        self.status_dot = QLabel(self)
        self.status_dot.setFixedSize(8, 8)
        self.status_dot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.name_label = QLabel(self)
        self.name_label.setTextFormat(Qt.TextFormat.PlainText)
        self.name_label.setMinimumWidth(0)
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.region_label = QLabel(self)
        self.region_label.setTextFormat(Qt.TextFormat.PlainText)
        self.region_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.region_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.status_label = QLabel(self)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setMinimumWidth(48)
        self.status_label.setFixedHeight(21)
        self.status_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        header.addWidget(self.status_dot)
        header.addWidget(self.name_label, 1)
        header.addWidget(self.region_label)
        header.addWidget(self.status_label)
        self.main_layout.addLayout(header)

        self.metrics_widget = QWidget(self)
        self.metrics_layout = QGridLayout(self.metrics_widget)
        self.metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.metrics_layout.setHorizontalSpacing(7)
        self.metrics_layout.setVerticalSpacing(5)
        metric_defs = [
            ("CPU", "cpu", "%", "#6bd7c9"),
            ("内存", "memory", "%", "#f0bd72"),
            ("↑ 上传", "upload", " KiB/s", "#6bd7c9"),
            ("↓ 下载", "download", " KiB/s", "#af9be3"),
        ]
        for label, key, unit, accent in metric_defs:
            block = MetricBlock(label, QColor(accent), self.metrics_widget)
            block.data_key = key
            block.metric_key = key
            block.unit = unit
            self.metric_blocks.append(block)
        self.main_layout.addWidget(self.metrics_widget)

        self.details_widget = QWidget(self)
        self.details_layout = QHBoxLayout(self.details_widget)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details_layout.setSpacing(6)
        self.details_label = QLabel(self.details_widget)
        self.details_label.setTextFormat(Qt.TextFormat.PlainText)
        self.details_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.details_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.details_label.setMinimumWidth(0)
        self.expires_label = QLabel(self.details_widget)
        self.expires_label.setTextFormat(Qt.TextFormat.PlainText)
        self.expires_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.expires_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.expires_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.details_layout.addWidget(self.details_label, 1)
        self.details_layout.addWidget(self.expires_label)
        self.latency_widget = QWidget(self)
        self.latency_layout = QHBoxLayout(self.latency_widget)
        self.latency_layout.setContentsMargins(0, 0, 0, 0)
        self.latency_layout.setSpacing(6)
        for carrier, accent in (
            ("移动", "#77cfd3"),
            ("联通", "#b796e5"),
            ("电信", "#e4b66f"),
        ):
            chip = CarrierChip(carrier, QColor(accent), self.latency_widget)
            self.carrier_chips.append(chip)
            self.latency_layout.addWidget(chip, 1)
        self.main_layout.addWidget(self.latency_widget)

        # 皮肤 3/4：每个运营商占一整行，分别使用分段或横条表达延迟。
        self.latency_rows_widget = QWidget(self)
        self.latency_rows_layout = QVBoxLayout(self.latency_rows_widget)
        self.latency_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.latency_rows_layout.setSpacing(4)
        for carrier, accent in (
            ("移动", "#e84d9a"), ("联通", "#4c8fe9"), ("电信", "#8e63e8")
        ):
            row = LatencyRow(carrier, QColor(accent), parent=self.latency_rows_widget)
            self.latency_rows.append(row)
            self.latency_rows_layout.addWidget(row)
        self.main_layout.addWidget(self.latency_rows_widget)

        # 皮肤 5：单行彩色运营商色块，优先保留数值和等级。
        self.latency_blocks_widget = QWidget(self)
        self.latency_blocks_layout = QHBoxLayout(self.latency_blocks_widget)
        self.latency_blocks_layout.setContentsMargins(0, 0, 0, 0)
        self.latency_blocks_layout.setSpacing(6)
        for carrier, accent in (
            ("移动", "#f18b36"), ("联通", "#e03b60"), ("电信", "#f0c62e")
        ):
            block = LatencyBlock(carrier, QColor(accent), parent=self.latency_blocks_widget)
            self.latency_blocks.append(block)
            self.latency_blocks_layout.addWidget(block, 1)
        self.main_layout.addWidget(self.latency_blocks_widget)

        # 皮肤 6：单独的真实采样趋势区域，不把当前值伪装成历史数据。
        self.trend_panel = LatencyTrendPanel(self)
        self.main_layout.addWidget(self.trend_panel)
        self.loss_summary_label = QLabel(self)
        self.loss_summary_label.setTextFormat(Qt.TextFormat.PlainText)
        self.loss_summary_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.loss_summary_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.main_layout.addWidget(self.loss_summary_label)
        self.main_layout.addWidget(self.details_widget)
        self._apply_layout_template()
        self._hide_legacy_widgets()

    def _hide_legacy_widgets(self):
        if not self.reference_paint:
            return
        if self._legacy_widgets_hidden:
            return
        # 保留旧控件对象及其数据接口，供回归测试和后续调试读取；
        # 但它们不参与绘制。根控件保持可见状态并压到 0×0，避免
        # 旧 Layout 覆盖参考稿画布，同时不破坏 isVisible()/文本接口。
        roots = {
            self.metrics_widget, self.latency_widget, self.latency_rows_widget,
            self.latency_blocks_widget, self.trend_panel, self.loss_summary_label,
            self.details_widget,
        }
        for child in self.findChildren(QWidget):
            if child in roots:
                child.setGeometry(0, 0, 0, 0)
                child.show()
            else:
                child.hide()
        self.main_layout.setEnabled(False)
        self._legacy_widgets_hidden = True

    def _sync_reference_legacy_visibility(self):
        if not self.reference_paint:
            return
        available = self.status_key == "online" or (self.status_key == "stale" and self.has_readings(self.item))
        visible = {
            self.metrics_widget: available,
            self.latency_widget: available and self.skin in {"skin1", "skin2"},
            self.latency_rows_widget: available and self.skin in {"skin3", "skin4"},
            self.latency_blocks_widget: available and self.skin == "skin5",
            self.trend_panel: available and self.skin == "skin6",
            self.loss_summary_label: available and self.skin == "skin5",
            self.details_widget: True,
        }
        for widget, state in visible.items():
            widget.setGeometry(0, 0, 0, 0)
            # 使用 isHidden 而不是 isVisible：新卡片在加入可见布局前，
            # isVisible() 会因父控件尚未显示而返回 False，导致应隐藏的
            # 兼容控件在首帧被误认为已经处于目标状态。
            if widget.isHidden() == state:
                widget.setVisible(state)

    def _sync_reference_compat_controls(self, item, status_key):
        """同步保留给测试/调试读取的控件，避免刷新不可见的全部皮肤控件。

        参考稿实际由 NodeCard.paintEvent 绘制；这些 Qt 子控件保持数据接口，
        但只更新当前皮肤所需的延迟控件，避免隐藏控件每轮触发布局和重绘。
        """
        latency_values = item.get("latency", {}) if isinstance(item.get("latency"), dict) else {}
        loss_values = item.get("loss", {}) if isinstance(item.get("loss"), dict) else {}
        for block in self.metric_blocks:
            block.apply_theme(self.colors)
            block.set_value(item.get(block.data_key), block.unit)
        if self.skin in {"skin1", "skin2"}:
            for chip, carrier in zip(self.carrier_chips, ("移动", "联通", "电信")):
                chip.apply_theme(self.colors)
                chip.set_values(latency_values.get(carrier), loss_values.get(carrier), status_key)
        elif self.skin in {"skin3", "skin4"}:
            for row, carrier in zip(self.latency_rows, ("移动", "联通", "电信")):
                row.apply_theme(self.colors)
                row.set_values(latency_values.get(carrier), loss_values.get(carrier), status_key)
        elif self.skin == "skin5":
            for block, carrier in zip(self.latency_blocks, ("移动", "联通", "电信")):
                block.apply_theme(self.colors)
                block.set_values(latency_values.get(carrier), loss_values.get(carrier), status_key)
        elif self.trend_panel is not None:
            self.trend_panel.apply_theme(self.colors)
            self.trend_panel.set_values(latency_values, loss_values, status_key)

    def _reference_height(self):
        return self.reference_height_for(self.width(), self.skin, self.status_key, self.item, self.compact_vertical)

    @staticmethod
    def has_readings(item):
        if not isinstance(item, dict):
            return False
        values = [item.get(key) for key in ("cpu", "memory", "upload", "download")]
        latency = item.get("latency")
        if isinstance(latency, dict):
            values.extend(latency.values())
        return any(KomariClient._number(value) is not None for value in values)

    @staticmethod
    def reference_height_for(width, skin, status, item=None, compact=False):
        available = status == "online" or (status == "stale" and NodeCard.has_readings(item))
        if not available:
            return 78 if 0 < width < 340 else 62
        if compact:
            return 94
        extra = 0
        if 0 < width < 340:
            extra = 18 + (14 if skin in {"skin1", "skin2"} else 16 if skin == "skin5" else 0)
        return REFERENCE_CARD_HEIGHTS.get(skin, 178) + extra

    def _reference_color(self, key, fallback):
        value = self.colors.get(key, fallback)
        return value if isinstance(value, QColor) else QColor(value)

    @staticmethod
    def _reference_text(painter, rect, text, size, color, weight=QFont.Weight.Normal,
                        alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        elide=True, fit=False, min_size=8):
        """按稿件基线绘制文字；关键字段优先缩小字号，不省略数值。"""
        value = str(text)
        font_size = int(size)
        font = _font(font_size, weight)
        if fit:
            while font_size > int(min_size) and QFontMetrics(font).horizontalAdvance(value) > max(1, int(rect.width())):
                font_size -= 1
                font = _font(font_size, weight)
            elide = False
        painter.setFont(font)
        painter.setPen(color)
        if elide:
            value = QFontMetrics(font).elidedText(value, Qt.TextElideMode.ElideRight, max(1, int(rect.width())))
        painter.drawText(rect, alignment, value)

    @staticmethod
    def _reference_number(value, suffix="", precision=1):
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return "—"
        return f"{value:.{precision}f}{suffix}"

    def _reference_level(self, carrier):
        latency = self.item.get("latency", {}).get(carrier)
        loss = self.item.get("loss", {}).get(carrier)
        if not isinstance(latency, (int, float)) or not math.isfinite(latency) or latency <= 0:
            latency = None
        if not isinstance(loss, (int, float)) or not math.isfinite(loss):
            loss = None
        label, key = _latency_grade(latency, loss)
        return latency, loss, label, key

    def _draw_reference_header(self, painter, width):
        fg = self._reference_color("fg", "#2c2c2a")
        muted = self._reference_color("muted", "#7a766d")
        # 参考稿的离线节点使用中性灰徽标；离线计数在顶部摘要里才使用主题警示色。
        state_color = muted if self.status_key == "offline" else self._reference_color(self.status_key, "#9aa0a8")
        name = str(self.item.get("name") or "未命名节点")
        name_font = _font(15, QFont.Weight.DemiBold)
        name_width = QFontMetrics(name_font).horizontalAdvance(name)
        # 设计稿把地区代码放在节点名称后面，而不是把它推到右侧状态徽标前。
        name_rect = QRectF(0, 6, max(40.0, min(width - 110.0, name_width + 2.0)), 24)
        self._reference_text(painter, name_rect, name, 15, fg, QFont.Weight.DemiBold,
                             elide=True)
        code = str(self.item.get("code") or "").strip()
        region = str(self.item.get("region") or "—")
        region_text = code or region
        status_text = {"online": "在线", "offline": "离线", "stale": "数据过期"}.get(self.status_key, "未知")
        status_width = 76 if status_text == "数据过期" else 51
        status_x = width - status_width
        code_x = min(name_rect.right() + 7, status_x - 31)
        self._reference_text(painter, QRectF(code_x, 6, max(24.0, status_x - code_x - 5), 24),
                             region_text, 11, muted)
        pill = QRectF(status_x, 10, status_width, 18)
        if self.status_key == "online":
            pill_fill = self._reference_color("status_online_fill", _qcolor(state_color, 42))
            pill_text = self._reference_color("status_online_text", state_color)
            painter.setBrush(pill_fill)
            painter.setPen(Qt.PenStyle.NoPen)
        elif self.status_key == "stale":
            painter.setBrush(_qcolor(state_color, 28))
            painter.setPen(QPen(_qcolor(state_color, 210), 0.5, Qt.PenStyle.DotLine))
            pill_text = state_color
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(_qcolor(state_color, 210), 0.5, Qt.PenStyle.DotLine))
            pill_text = state_color
        painter.drawRoundedRect(pill, 10, 10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(pill_text)
        if self.status_key == "online":
            painter.drawEllipse(QRectF(pill.left() + 9, pill.top() + 6, 6, 6))
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(pill_text, 1))
            painter.drawEllipse(QRectF(pill.left() + 9, pill.top() + 6, 6, 6))
        self._reference_text(painter, QRectF(pill.left() + 20, pill.top(), pill.width() - 22, pill.height()),
                             status_text, 11, pill_text, QFont.Weight.DemiBold,
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             elide=False)

    def _draw_reference_value(self, painter, x, y, available, number, unit, size, color,
                              unit_color=None):
        """数字与单位共用基线，保留稿件中小号 ms/%/KiB/s 的层级。"""
        number_font = _number_font(size, 98 if size == 15 else 100)
        unit_weight = QFont.Weight.DemiBold if unit in {"%", "KiB/s", "MiB/s", "GiB/s"} else QFont.Weight.Normal
        unit_font = _font(11, unit_weight)
        metrics = QFontMetrics(number_font)
        unit_width = QFontMetrics(unit_font).horizontalAdvance(unit) if unit else 0
        while size > 15 and metrics.horizontalAdvance(number) + unit_width + 3 > available:
            size -= 1
            number_font = _number_font(size, 98 if size == 15 else 100)
            metrics = QFontMetrics(number_font)
        number_width = metrics.horizontalAdvance(number)
        painter.setFont(number_font)
        painter.setPen(color)
        painter.drawText(QRectF(x, y, min(available, number_width + 1), 25),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, number)
        if unit:
            self._reference_text(painter, QRectF(x + number_width + 2, y + 2,
                                                max(1, available - number_width - 2), 23),
                                 unit, 11, unit_color or color, unit_weight, elide=False)

    def _draw_reference_metrics(self, painter, width):
        fg = self._reference_color("fg", "#2c2c2a")
        muted = self._reference_color("muted", "#7a766d")
        labels = ("CPU", "内存", "↑ 上传", "↓ 下载")
        keys = ("cpu", "memory", "upload", "download")
        # 样稿前两列是窄进度列，上下行列留出更多单位空间。
        positions = (0.0, width * 0.224, width * 0.448, width * 0.742)
        widths = (width * 0.194, width * 0.194, width * 0.268, width * 0.258)
        for index, (label, key) in enumerate(zip(labels, keys)):
            x, col_width = positions[index], widths[index]
            self._reference_text(painter, QRectF(x, 34, col_width, 16), label, 11, muted,
                                 QFont.Weight.Normal)
            value = self.item.get(key)
            if key in {"cpu", "memory"}:
                value_text = self._reference_number(value)
                unit_text = "%" if value_text != "—" else ""
            else:
                unit_text = "KiB/s"
                if isinstance(value, (int, float)) and math.isfinite(value):
                    value = float(value)
                    if abs(value) >= 1024:
                        value /= 1024
                        unit_text = "MiB/s"
                    if abs(value) >= 1024:
                        value /= 1024
                        unit_text = "GiB/s"
                value_text = self._reference_number(value)
                if value_text == "—":
                    unit_text = ""
            self._draw_reference_value(painter, x, 47, col_width, value_text, unit_text,
                                       15, fg if value_text != "—" else muted, muted)
            if key in {"cpu", "memory"}:
                track = self._reference_color("track", "#d8d8d2")
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(track)
                painter.drawRoundedRect(QRectF(x, 74, col_width, 3), 1.5, 1.5)
                if isinstance(value, (int, float)) and math.isfinite(value):
                    painter.setBrush(fg)
                    painter.drawRoundedRect(QRectF(x, 74, max(2, col_width * max(0, min(100, value)) / 100.0), 3), 1.5, 1.5)

    def _draw_reference_chips(self, painter, width):
        gap = 12.0 if width >= 340 else 7.0
        chip_y, chip_height = 86.0, 78.0 if width < 340 else 64.0
        chip_width = (width - gap * 2) / 3.0
        fg = self._reference_color("fg", "#2c2c2a")
        for index, carrier in enumerate(("移动", "联通", "电信")):
            x = index * (chip_width + gap)
            latency, loss, quality, level = self._reference_level(carrier)
            fill = self._reference_color(f"level_{level}", "#e2e1db")
            text = self._reference_color(f"level_{level}_text", fg.name())
            # 参考稿的色块有非常轻的下沿阴影和顶部高光；保留实体色，
            # 只增加一层低对比度深度，不让透明桌面背景把指标洗灰。
            shadow = QColor("#000000")
            painter.setPen(Qt.PenStyle.NoPen)
            for blur in (4, 3, 2, 1):
                painter.setBrush(_qcolor(shadow, 4 if blur > 2 else 7))
                painter.drawRoundedRect(QRectF(x - blur, chip_y + 3 - blur,
                                                chip_width + 2 * blur, chip_height + 2 * blur),
                                        10 + blur, 10 + blur)
            gradient = QLinearGradient(0, chip_y, 0, chip_y + chip_height)
            # 设计稿的色块从原色平滑过渡到明显更深的下沿；
            # 不能用轻微 darker(108)，否则橙/红/黄会整体发亮。
            bottom = self._reference_color(f"level_{level}_bottom", fill.darker(125))
            gradient.setColorAt(0.0, self._reference_color(f"level_{level}_top", fill))
            gradient.setColorAt(1.0, _qcolor(bottom, 255))
            painter.setBrush(gradient)
            painter.setPen(QPen(_qcolor(fill.darker(115), 190), 1))
            painter.drawRoundedRect(QRectF(x, chip_y, chip_width, chip_height), 10, 10)
            painter.setPen(QPen(_qcolor(fill.lighter(128), 110), 1))
            painter.drawLine(QPointF(x + 9, chip_y + 1), QPointF(x + chip_width - 9, chip_y + 1))
            carrier_color = self._reference_color(f"carrier_{carrier}", fg.name())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(carrier_color)
            painter.setBrush(QColor("#f7f5ef"))
            painter.drawEllipse(QRectF(x + 8, chip_y + 8, 10, 10))
            painter.setBrush(carrier_color)
            painter.drawEllipse(QRectF(x + 10, chip_y + 10, 6, 6))
            self._reference_text(painter, QRectF(x + 21, chip_y + 4, chip_width - 26, 18), carrier, 11,
                                 text, QFont.Weight.DemiBold, fit=True, min_size=9)
            value_text = "—" if latency is None else str(int(round(latency)))
            self._draw_reference_value(painter, x + 10, chip_y + 17, chip_width - 18,
                                       value_text, "ms" if latency is not None else "", 19, text)
            loss_text = "暂无" if latency is None else quality
            if isinstance(loss, (int, float)) and loss > 0:
                loss_text += ("\n" if width < 340 else " · ") + f"丢{loss:.1f}%"
            self._reference_text(painter, QRectF(x + 10, chip_y + 43, chip_width - 18, chip_height - 45), loss_text, 11,
                                 text, QFont.Weight.DemiBold,
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                                 elide=False)

    def _draw_reference_rows(self, painter, width, bars=False):
        fg = self._reference_color("fg", "#2c2c2a")
        muted = self._reference_color("muted", "#7a766d")
        row_y, row_height, gap = 84.0, 22.0, 3.0
        quality_width = max(
            QFontMetrics(_font(11)).horizontalAdvance(
                quality + (f" · 丢{loss:.1f}%" if loss is not None and loss > 0 else "")
            ) for _, loss, quality, _ in (self._reference_level(carrier) for carrier in ("移动", "联通", "电信"))
        )
        bar_left, bar_right = 56.0, width - max(139.0, quality_width + 68)
        carrier_colors = {carrier: self._reference_color(f"carrier_{carrier}", fg.name())
                          for carrier in ("移动", "联通", "电信")}
        for index, carrier in enumerate(("移动", "联通", "电信")):
            y = row_y + index * (row_height + gap)
            latency, loss, quality, level = self._reference_level(carrier)
            fill = self._reference_color(f"level_{level}", carrier_colors[carrier].name())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(carrier_colors[carrier])
            painter.drawEllipse(QRectF(0, y + 7, 8, 8))
            self._reference_text(painter, QRectF(14, y, 34, row_height), carrier, 11, fg)
            # 文本绘制会改变 pen，图形必须显式清除，避免继承深色/白色外轮廓。
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._reference_color("track", "#d8d8d2"))
            if bars:
                painter.drawRoundedRect(QRectF(bar_left, y + 7, bar_right - bar_left, 9), 1.5, 1.5)
                ratio = 0 if latency is None else max(0.0, min(1.0, latency / 400.0))
                painter.setBrush(fill)
                painter.drawRoundedRect(QRectF(bar_left, y + 7, (bar_right - bar_left) * ratio, 9), 1.5, 1.5)
                for tick in (0.30, 0.75):
                    painter.setBrush(_qcolor(muted, 110))
                    painter.drawRect(QRectF(bar_left + (bar_right - bar_left) * tick, y + 5, 0.7, 13))
            else:
                count, segment_gap = 12, 1.5
                segment_width = (bar_right - bar_left - segment_gap * (count - 1)) / count
                filled = count if latency is not None else 0
                history = self.item.get("_demo_segments", {}).get(carrier, [])
                if not history and self.trend_panel is not None:
                    history = list(self.trend_panel.history.get(carrier, []))[-count:]
                for part in range(count):
                    segment_fill = fill
                    if len(history) >= count:
                        _, history_level = _latency_grade(history[-count + part], None)
                        segment_fill = self._reference_color(f"level_{history_level}", fill)
                    painter.setBrush(segment_fill if part < filled else self._reference_color("track", "#394554"))
                    painter.drawRoundedRect(QRectF(bar_left + part * (segment_width + segment_gap), y + 7, segment_width, 9), 1.5, 1.5)
            value_text = "—" if latency is None else str(int(round(latency)))
            painter.setFont(_number_font(15))
            painter.setPen(fg)
            painter.drawText(QRectF(bar_right + 9, y, 32, row_height),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, value_text)
            self._reference_text(painter, QRectF(bar_right + 46, y + 1, 17, row_height),
                                 "ms" if latency is not None else "", 11, muted)
            quality_text = quality
            if isinstance(loss, (int, float)) and loss > 0:
                quality_text += f" · 丢{loss:.1f}%"
            quality_x = bar_right + 66
            self._reference_text(painter, QRectF(quality_x, y, width - quality_x, row_height), quality_text, 11,
                                 muted, fit=True, min_size=11)

    def _draw_reference_blocks(self, painter, width):
        gap, y, height = (8.0 if width >= 340 else 6.0), 86.0, 44.0 if width < 340 else 28.0
        block_width = (width - gap * 2) / 3.0
        fg = self._reference_color("fg", "#2c2c2a")
        for index, carrier in enumerate(("移动", "联通", "电信")):
            x = index * (block_width + gap)
            latency, loss, quality, level = self._reference_level(carrier)
            fill = self._reference_color(f"level_{level}", "#e2e1db")
            text = self._reference_color(f"level_{level}_text", fg.name())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(QRectF(x, y, block_width, height), 6, 6)
            value = "—" if latency is None else str(int(round(latency)))
            self._reference_text(painter, QRectF(x + 8, y + 1, 24, 26), carrier, 11,
                                 text, QFont.Weight.DemiBold, elide=False)
            value_x = x + 36 if width >= 340 else x + 8
            self._draw_reference_value(painter, value_x, y + (1 if width >= 340 else 18),
                                       max(35, block_width - (68 if width >= 340 else 16)),
                                       value, "ms" if latency is not None else "", 15, text)
            self._reference_text(painter, QRectF(x + block_width - 31, y + 1, 23, 26), quality, 11,
                                 text, QFont.Weight.DemiBold,
                                 Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 elide=False)
        loss_parts = []
        for carrier in ("移动", "联通", "电信"):
            loss = self.item.get("loss", {}).get(carrier)
            if isinstance(loss, (int, float)) and loss > 0:
                loss_parts.append(f"{carrier} {loss:.1f}%")
        self._reference_text(painter, QRectF(0, 118 + (16 if width < 340 else 0), width, 16),
                             "丢包  " + "  ".join(loss_parts) if loss_parts else "丢包  —",
                             11, self._reference_color("muted", fg.name()))

    @staticmethod
    def _reference_bytes(value):
        """只解析已存在的“已用 / 限额”显示字段，用于画极细的用量提示线。"""
        if not isinstance(value, str):
            return None
        parts = value.strip().split()
        if len(parts) < 2:
            return None
        try:
            number = float(parts[0])
        except (TypeError, ValueError):
            return None
        units = {
            "B": 1, "KB": 1000, "MB": 1000**2, "GB": 1000**3, "TB": 1000**4,
            "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4,
        }
        factor = units.get(parts[1])
        return number * factor if factor else None

    def _reference_traffic_ratio(self):
        traffic = str(self.item.get("traffic") or "")
        if "/" not in traffic:
            return None
        used_text, limit_text = (part.strip() for part in traffic.split("/", 1))
        used = self._reference_bytes(used_text)
        limit = self._reference_bytes(limit_text)
        if used is None or limit is None or limit <= 0:
            return None
        return max(0.0, min(1.0, used / limit))

    def _draw_reference_details(self, painter, width, y):
        muted = self._reference_color("muted", "#7a766d")
        fg = self._reference_color("fg", "#2c2c2a")
        traffic = str(self.item.get("traffic") or "—")
        traffic_label = str(self.item.get("traffic_label") or "已用")
        self._reference_text(painter, QRectF(0, y, 26, 18), traffic_label, 11, muted)
        ratio = self._reference_traffic_ratio()
        track_x = 28.0
        track_width = 34.0
        if ratio is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._reference_color("track", "#d8d8d2"))
            painter.drawRoundedRect(QRectF(track_x, y + 9, track_width, 3), 1.5, 1.5)
            painter.setBrush(fg)
            painter.drawRoundedRect(QRectF(track_x, y + 9, max(2.0, track_width * ratio), 3), 1.5, 1.5)
            traffic_x = 68.0
        else:
            traffic_x = 32.0
        traffic_width = width - traffic_x if width < 340 else max(100.0, width * 0.50 - traffic_x)
        self._reference_text(painter, QRectF(traffic_x, y, traffic_width, 18), traffic, 11, muted,
                             elide=True)

        expires = str(self.item.get("expires") or "—")
        remaining = ""
        try:
            if expires != "—":
                days = max(0, (date.fromisoformat(expires) - date.today()).days)
                remaining = f"剩 {days} 天"
        except (TypeError, ValueError):
            pass
        if width < 340:
            y += 18
        expiry_text = f"到期 {expires}"
        if remaining:
            rem_font = _font(11, QFont.Weight.DemiBold)
            rem_width = QFontMetrics(rem_font).horizontalAdvance(remaining) + 2
            expiry_width = QFontMetrics(_font(11)).horizontalAdvance(expiry_text) + 2
            right_x = max(0, width - rem_width - expiry_width - 7)
            self._reference_text(painter, QRectF(right_x, y, expiry_width, 18), expiry_text, 11, muted,
                                 alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 elide=False)
            self._reference_text(painter, QRectF(width - rem_width, y, rem_width, 18), remaining, 11, fg,
                                 QFont.Weight.DemiBold, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 elide=False)
        else:
            self._reference_text(painter, QRectF(width * 0.55, y, width * 0.45, 18), expiry_text, 11, muted,
                                 alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 elide=False)

    def _draw_reference_trend(self, painter, width):
        carriers = ("移动", "联通", "电信")
        labels, series = {}, {}
        for carrier in carriers:
            value, loss, _, _ = self._reference_level(carrier)
            labels[carrier] = f"{carrier} {int(round(value)) if value is not None else '—'}"
            if isinstance(loss, (int, float)) and loss > 0:
                labels[carrier] += f" · 丢{loss:.1f}%"
            history = []
            demo_trend = self.item.get("_demo_trend", {})
            if isinstance(demo_trend, dict) and isinstance(demo_trend.get(carrier), (list, tuple)):
                history = list(demo_trend[carrier])[-24:]
            session_history = self.item.get("_latency_history", {})
            if isinstance(session_history, dict) and carrier in session_history:
                history = list(session_history[carrier])[-24:]
            elif not history and self.trend_panel is not None:
                history = list(self.trend_panel.history.get(carrier, []))[-24:]
            series[carrier] = history if history else ([value] if value is not None else [])
        # 正常范围沿用原稿0–400ms；真实数据超过400时共用扩展量程，不能截成顶端直线。
        peak = max((point for points in series.values() for point in points
                    if isinstance(point, (int, float)) and math.isfinite(point) and point > 0), default=0)
        axis_max = max(400.0, math.ceil(peak / 100.0) * 100.0)
        if not math.isfinite(axis_max):
            axis_max = peak
        # 按实际字宽为丢包和长延迟预留空间，不靠缩小字体藏住溢出。
        label_metrics = QFontMetrics(_font(11, QFont.Weight.DemiBold))
        label_width = max(120.0, max(label_metrics.horizontalAdvance(label) for label in labels.values()) + 2)
        graph_left, graph_right = 30.0, width - label_width - 14.0
        graph_top, graph_bottom = 88.0, 138.0
        label_min, label_max, label_height = 82.0, 139.0, 14.0
        grid_pen = QPen(self._reference_color("rule", "#d6c4a8"), 1)
        grid_pen.setDashPattern([3.0, 3.0])
        grid_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(grid_pen)
        for grid in (0.25, 0.70):
            y = graph_top + (graph_bottom - graph_top) * grid
            painter.drawLine(QPointF(graph_left, y), QPointF(graph_right, y))
        colors = {carrier: self._reference_color(f"carrier_{carrier}", "#777777") for carrier in carriers}
        ordered = sorted(
            carriers,
            key=lambda carrier: self._reference_level(carrier)[0] if isinstance(self._reference_level(carrier)[0], (int, float)) else -1,
            reverse=True,
        )
        label_tops = []
        for carrier in ordered:
            latency = self._reference_level(carrier)[0]
            label_tops.append(max(label_min, min(label_max,
                graph_bottom - (graph_bottom - graph_top) * (latency or 0) / axis_max - 7)))
        # 标签跟随曲线端点；相邻端点过近时只挪动标签，保留真实曲线高度。
        for index in range(1, len(label_tops)):
            label_tops[index] = max(label_tops[index], label_tops[index - 1] + label_height)
        if label_tops and label_tops[-1] > label_max:
            label_tops[-1] = label_max
            for index in range(len(label_tops) - 2, -1, -1):
                label_tops[index] = min(label_tops[index], label_tops[index + 1] - label_height)
        sampling = False
        for index, carrier in enumerate(ordered):
            latency, _, _, _ = self._reference_level(carrier)
            value = None if not isinstance(latency, (int, float)) else float(latency)
            points = series[carrier]
            painter.setPen(QPen(colors[carrier], 1.8))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if points:
                path = QPainterPath()
                # 采样不足24点时右对齐，单点只画端点；不能把单次观测伪装成整段历史。
                previous_valid = False
                for point_index, point in enumerate(points):
                    if not isinstance(point, (int, float)) or not math.isfinite(point) or point <= 0:
                        previous_valid = False
                        continue
                    point_value = float(point)
                    px = graph_right - (graph_right - graph_left) * (len(points) - 1 - point_index) / 23
                    py = graph_bottom - (graph_bottom - graph_top) * (point_value / axis_max)
                    if not previous_valid:
                        path.moveTo(QPointF(px, py))
                    else:
                        path.lineTo(QPointF(px, py))
                    previous_valid = True
                painter.drawPath(path)
            previous_value = KomariClient._number(points[-2]) if len(points) >= 2 else None
            isolated_latest = value is not None and (previous_value is None or previous_value <= 0)
            sampling |= isolated_latest
            if isolated_latest:
                endpoint_y = graph_bottom - (graph_bottom - graph_top) * (value / axis_max)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(colors[carrier])
                painter.drawEllipse(QPointF(graph_right, endpoint_y), 1.6, 1.6)
            _, _, _, level = self._reference_level(carrier)
            label_color = self._reference_color(f"quality_{level}", self.colors.get(f"level_{level}", colors[carrier]))
            self._reference_text(painter, QRectF(graph_right + 14, label_tops[index], label_width, label_height),
                                 labels[carrier], 11, label_color, QFont.Weight.DemiBold, elide=False)
        if sampling:
            self._reference_text(painter, QRectF(graph_left, graph_top, max(1, graph_right - graph_left - 4), 16),
                                 "采样中", 11, self._reference_color("muted", "#64513d"))
        if axis_max > 400:
            self._reference_text(painter, QRectF(graph_left, 139, max(1, graph_right - graph_left), 14),
                                 f"0–{axis_max:g} ms", 11, self._reference_color("muted", "#64513d"))

    def paintEvent(self, event):
        if not self.reference_paint:
            super().paintEvent(event)
            return
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Qt 已经按屏幕 DPR 处理物理像素；这里始终使用实际逻辑尺寸，
        # 不再二次等比放大字体和绘制内容。
        width = float(self.width())
        height = float(self.height())
        self._draw_reference_header(painter, width)
        available = self.status_key == "online" or (self.status_key == "stale" and self.has_readings(self.item))
        if not available:
            muted = self._reference_color("muted", "#7a766d")
            summary = "CPU — · 内存 — · 上传 — · 下载 — · 延迟 —"
            if width < 340:
                summary = "CPU — · 内存 — · 上传 —\n下载 — · 延迟 —"
            self._reference_text(
                painter, QRectF(0, 33, width - (0 if width < 340 else 76), 35 if width < 340 else 20),
                summary, 11, muted, elide=False,
                alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            )
            self._reference_text(
                painter, QRectF(width - 70, 50 if width < 340 else 33, 70, 20),
                f"到期 {self.item.get('expires') or '—'}", 11, muted,
                alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                fit=True, min_size=8,
            )
        else:
            self._draw_reference_metrics(painter, width)
            if self.compact_vertical:
                painter.setPen(QPen(self._reference_color("rule", "#d8d3c8"), 0.6))
                painter.drawLine(QPointF(0, height - 1), QPointF(width, height - 1))
                painter.end()
                return
            if self.skin in {"skin1", "skin2"}:
                self._draw_reference_chips(painter, width)
            elif self.skin == "skin3":
                self._draw_reference_rows(painter, width, bars=False)
            elif self.skin == "skin4":
                self._draw_reference_rows(painter, width, bars=True)
            elif self.skin == "skin5":
                self._draw_reference_blocks(painter, width)
            else:
                self._draw_reference_trend(painter, width)
            details_y = {
                "skin1": 153, "skin2": 153, "skin3": 161,
                "skin4": 161, "skin5": 139, "skin6": 155,
            }.get(self.skin, 153)
            if width < 340:
                details_y += 14 if self.skin in {"skin1", "skin2"} else 16 if self.skin == "skin5" else 0
            self._draw_reference_details(painter, width, details_y)
        if available:
            painter.setPen(QPen(self._reference_color("rule", "#d8d3c8"), 0.6))
            painter.drawLine(QPointF(0, height - 1), QPointF(width, height - 1))
        painter.end()

    def _apply_status_layout(self, status_key):
        """离线/过期节点按参考稿收缩为摘要行，避免空指标撑大面板。"""
        available = status_key == "online"
        for widget in (
            self.metrics_widget, self.latency_widget, self.latency_rows_widget,
            self.latency_blocks_widget, self.trend_panel, self.loss_summary_label,
        ):
            widget.setVisible(available and widget is not self.loss_summary_label)
        self.loss_summary_label.setVisible(available and self.skin == "skin5")
        if not available:
            self.details_label.setText("CPU —  ·  内存 —  ·  上传 —  ·  下载 —  ·  延迟 —")
            self.expires_label.setText("到期 —")
        self._status_layout_key = (status_key, self.skin)

    def _apply_layout_template(self):
        """按参考图切换真正的卡片排版，而不是只替换颜色。"""
        self.skin = self.colors.get("skin", self.skin if hasattr(self, "skin") else "skin1")
        self.skin1 = self.skin == "skin1"
        if self.skin == "skin1":
            margins, spacing = (0, 6, 0, 6), 3
        elif self.skin == "skin2":
            margins, spacing = (12, 10, 12, 9), 5
        elif self.skin in {"skin3", "skin4"}:
            margins, spacing = (10, 8, 10, 8), 4
        elif self.skin == "skin5":
            margins, spacing = (10, 8, 10, 8), 4
        else:  # skin6
            margins, spacing = (10, 8, 10, 8), 4
        spec = SKIN_LAYOUTS.get(self.skin, SKIN_LAYOUTS["skin1"])
        margins = tuple(spec.get("node_padding", margins))
        spacing = int(spec.get("node_spacing", spacing))
        self.main_layout.setContentsMargins(*margins)
        self.main_layout.setSpacing(spacing)
        self.metrics_layout.setHorizontalSpacing(int(spec.get("metric_hspacing", 7)))
        self.metrics_layout.setVerticalSpacing(int(spec.get("metric_vspacing", 3)))
        self.details_layout.setSpacing(int(spec.get("details_spacing", 4)))

        self.name_label.setFont(_font(spec["node_name"], QFont.Weight.DemiBold))
        self.region_label.setFont(_font(spec["region"], QFont.Weight.Normal))
        self.details_label.setFont(_font(spec["detail"], QFont.Weight.Normal))
        self.expires_label.setFont(_font(spec["detail"], QFont.Weight.Normal))
        self.loss_summary_label.setFont(_font(spec.get("detail", 10), QFont.Weight.Normal))
        for block in self.metric_blocks:
            block.set_design(spec)
        for chip in self.carrier_chips:
            chip.set_design(spec)
        for row in self.latency_rows:
            row.set_design(spec)
        for block in self.latency_blocks:
            block.set_design(spec)
        if self.trend_panel is not None:
            self.trend_panel.set_design(spec)

        available = getattr(self, "status_key", "online") == "online"
        show_chips = available and self.skin in {"skin1", "skin2"}
        show_rows = available and self.skin in {"skin3", "skin4"}
        show_blocks = available and self.skin == "skin5"
        show_trend = available and self.skin == "skin6"
        self.latency_widget.setVisible(show_chips)
        self.latency_rows_widget.setVisible(show_rows)
        self.latency_blocks_widget.setVisible(show_blocks)
        self.trend_panel.setVisible(show_trend)
        self.loss_summary_label.setVisible(available and self.skin == "skin5")
        self.details_widget.setVisible(True)

        self.latency_layout.setSpacing(6 if self.mode == "wide" else 4)
        self.latency_rows_layout.setSpacing(3)
        self.latency_blocks_layout.setSpacing(5 if self.mode == "wide" else 3)
        for row in self.latency_rows:
            row.set_compact(self.mode != "wide")
        for block in self.latency_blocks:
            block.set_compact(self.mode != "wide")
        if self.trend_panel is not None:
            self.trend_panel.setMinimumHeight(68 if self.mode == "wide" else 62)

    def _clear_grid(self):
        while self.metrics_layout.count():
            self.metrics_layout.takeAt(0)

    def _layout_metrics(self):
        self._clear_grid()
        columns = 2 if self.mode == "narrow" else 4
        for index, block in enumerate(self.metric_blocks):
            self.metrics_layout.addWidget(block, index // columns, index % columns)
            block.set_compact(self.mode != "wide")
            block.set_value(self.item.get(block.data_key), block.unit)
        self.metrics_layout.setColumnStretch(0, 1)
        self.metrics_layout.setColumnStretch(1, 1)
        if columns == 4:
            self.metrics_layout.setColumnStretch(2, 1)
            self.metrics_layout.setColumnStretch(3, 1)
        self.details_label.setVisible(True)
        status_key = self.item.get("status", "stale") if isinstance(self.item, dict) else "stale"
        for chip, carrier in zip(self.carrier_chips, ("移动", "联通", "电信")):
            chip.set_compact(self.mode != "wide")
            chip.set_values(self.item.get("latency", {}).get(carrier), self.item.get("loss", {}).get(carrier), status_key)
        self._preferred_height = self._base_height()
        self._sync_metric_widths()
        self._fit_to_content()

    def _base_height(self):
        if self.status_key != "online":
            unavailable_heights = {
                "skin1": 78, "skin2": 78, "skin3": 80,
                "skin4": 80, "skin5": 80, "skin6": 84,
            }
            return unavailable_heights.get(self.skin, 78)
        heights = {
            # 参考稿的节点高度：指标区固定，延迟区由皮肤决定，
            # 不能再用旧版“所有主题一套卡片高度”的预算。
            "skin1": {"narrow": 170, "compact": 177, "wide": 177},
            "skin2": {"narrow": 170, "compact": 177, "wide": 177},
            "skin3": {"narrow": 174, "compact": 180, "wide": 180},
            "skin4": {"narrow": 174, "compact": 180, "wide": 180},
            "skin5": {"narrow": 158, "compact": 164, "wide": 164},
            "skin6": {"narrow": 174, "compact": 180, "wide": 180},
        }
        return heights.get(self.skin, heights["skin1"])[self.mode]

    def _sync_metric_widths(self):
        """按卡片当前内容宽度给指标列统一宽度，避免速率单位挤出卡片。"""
        columns = 2 if self.mode == "narrow" else 4
        margins = self.main_layout.contentsMargins()
        available = max(0, self.width() - margins.left() - margins.right())
        spacing = max(0, self.metrics_layout.horizontalSpacing())
        target = max(0, int((available - spacing * (columns - 1)) / columns))
        for column in range(4):
            self.metrics_layout.setColumnMinimumWidth(column, target if column < columns else 0)
        for block in self.metric_blocks:
            block.setMinimumWidth(target)
        self.metrics_layout.activate()

    def _fit_to_content(self):
        """内容高度增加时扩展卡片，避免固定高度把三网控件压到下一层。"""
        if self.reference_paint:
            preferred = self._reference_height()
            self._preferred_height = preferred
            if self.height() != preferred:
                self.setFixedHeight(preferred)
            return
        self.main_layout.activate()
        # 标签在父布局完成宽度分配后可能发生一次换行/字体回退重算，
        # 预留少量缓冲，避免首帧高度比最终 sizeHint 小 1–3px。
        hint = self.main_layout.sizeHint().height() + 4
        preferred = max(getattr(self, "_preferred_height", 0), hint)
        if self.height() != preferred:
            self.setFixedHeight(preferred)

    def update_item(self, item, mode=None, colors=None, selected=None):
        self.item = item
        if mode is not None:
            self.mode = mode
        if colors is not None:
            self.colors = colors
            self.skin = colors.get("skin", self.skin)
            self.skin1 = self.skin == "skin1"
        if selected is not None:
            self.selected = selected
        presentation_key = (self.mode, self.skin, id(self.colors), self.compact_vertical)
        presentation_changed = self._presentation_key != presentation_key
        display_key = (
            tuple(item.get(key) for key in (
                "name", "region", "code", "status", "cpu", "memory", "upload", "download",
                "traffic", "traffic_label", "expires",
            )),
            tuple(item.get("latency", {}).get(key) for key in ("移动", "联通", "电信")),
            tuple(item.get("loss", {}).get(key) for key in ("移动", "联通", "电信")),
            self.selected, date.today(), item.get("_latency_revision") if self.skin == "skin6" else None,
        )
        if not presentation_changed and display_key == self._display_key:
            return
        if self.reference_paint:
            self._presentation_key = presentation_key
            self._display_key = display_key
            self.status_key = {
                "online": "online", "offline": "offline", "stale": "stale",
            }.get(item.get("status"), "stale")
            self._status_layout_key = (self.status_key, self.skin)
            # 参考绘制层不依赖旧控件，但继续同步它们的数据，保证
            # 现有只读接口、自动化回归和调试工具看到的值保持有效。
            self._sync_reference_compat_controls(item, self.status_key)
            loss_values = item.get("loss", {}) if isinstance(item.get("loss"), dict) else {}
            self.details_label.setText(
                f"{item.get('traffic_label') or '已用'}  ·  {item.get('traffic') or '—'}"
            )
            self.expires_label.setText(f"到期 {item.get('expires') or '—'}")
            loss_parts = [
                f"{carrier} {loss_values[carrier]:.1f}%"
                for carrier in ("移动", "联通", "电信")
                if isinstance(loss_values.get(carrier), (int, float)) and loss_values[carrier] > 0
            ]
            self.loss_summary_label.setText("丢包  " + "  ".join(loss_parts) if loss_parts else "丢包  —")
            self._preferred_height = self._reference_height()
            self.setFixedHeight(self._preferred_height)
            self._hide_legacy_widgets()
            self._sync_reference_legacy_visibility()
            self.update()
            return
        status_changed = presentation_changed or self._display_key is None or self._display_key[0][3] != item.get("status")
        self._presentation_key = presentation_key
        self._display_key = display_key
        status_text, status_key = {
            "online": ("在线", "online"),
            "offline": ("离线", "offline"),
            "stale": ("数据过期", "stale"),
        }.get(item.get("status"), ("未知", "stale"))
        status_layout_changed = self._status_layout_key != (status_key, self.skin)
        self.status_key = status_key
        state_color = self.colors[status_key]
        if status_changed:
            self.status_dot.setStyleSheet(f"background: {state_color.name()}; border-radius: 4px;")
        self.name_label.setText(str(item.get("name") or "未命名节点"))
        region = str(item.get("region") or "—")
        code = str(item.get("code") or "").strip()
        if self.skin1:
            # 参考皮肤把地区放进节点名，右侧只保留国家/地区代码，避免重复显示。
            self.region_label.setText(code or region)
        else:
            self.region_label.setText(f"{code} · {region}" if code else region)
        self.status_label.setText(status_text)
        if status_changed:
            self.status_label.setStyleSheet(
                "QLabel { color: %s; background: %s; border: 1px solid %s; border-radius: 10px; padding: 0 7px; }"
                % (state_color.name(), _qcolor(state_color, 38).name(QColor.NameFormat.HexArgb),
                   _qcolor(state_color, 110).name(QColor.NameFormat.HexArgb))
            )
        if presentation_changed:
            self.name_label.setFont(_font(13 if self.mode == "narrow" else 14, QFont.Weight.DemiBold))
            self.region_label.setFont(
                _font(8 if self.mode == "narrow" else 9, QFont.Weight.DemiBold if self.skin1 else QFont.Weight.Normal)
            )
            self.name_label.setStyleSheet(f"color: {self.colors['fg'].name()};")
            self.region_label.setStyleSheet(f"color: {self.colors['muted'].name()};")
        for block in self.metric_blocks:
            block.apply_theme(self.colors)
            block.set_value(item.get(block.data_key), block.unit)
        traffic = item.get("traffic") or "—"
        expires = item.get("expires") or "—"
        traffic_label = str(item.get("traffic_label") or "已用")
        remaining = ""
        try:
            if expires != "—":
                remaining = f"  剩 {max(0, (date.fromisoformat(str(expires)) - date.today()).days)} 天"
        except (TypeError, ValueError):
            remaining = ""
        # 六张参考图都保留流量/到期信息；布局差异由对应的延迟面板承担。
        self.details_label.setText(f"{traffic_label}  ·  {traffic}")
        self.expires_label.setVisible(True)
        self.expires_label.setText(f"到期 {expires}{remaining}")
        if presentation_changed:
            self.details_label.setFont(_font(8 if self.mode != "wide" else 9, QFont.Weight.Normal))
            self.details_label.setStyleSheet(f"color: {self.colors['muted'].name()};")
            self.expires_label.setFont(_font(8 if self.mode != "wide" else 9, QFont.Weight.Normal))
            self.expires_label.setStyleSheet(f"color: {self.colors['muted'].name()};")
            self.loss_summary_label.setFont(_font(8 if self.mode != "wide" else 9, QFont.Weight.Normal))
            self.loss_summary_label.setStyleSheet(f"color: {self.colors['muted'].name()};")
        for chip, carrier in zip(self.carrier_chips, ("移动", "联通", "电信")):
            chip.apply_theme(self.colors)
            chip.set_values(item.get("latency", {}).get(carrier), item.get("loss", {}).get(carrier), status_key)
        latency_values = item.get("latency", {}) if isinstance(item.get("latency"), dict) else {}
        loss_values = item.get("loss", {}) if isinstance(item.get("loss"), dict) else {}
        for row, carrier in zip(self.latency_rows, ("移动", "联通", "电信")):
            row.apply_theme(self.colors)
            row.set_values(latency_values.get(carrier), loss_values.get(carrier), status_key)
        for block, carrier in zip(self.latency_blocks, ("移动", "联通", "电信")):
            block.apply_theme(self.colors)
            block.set_values(latency_values.get(carrier), loss_values.get(carrier), status_key)
        if self.trend_panel is not None:
            self.trend_panel.apply_theme(self.colors)
            self.trend_panel.set_values(latency_values, loss_values, status_key)
        loss_parts = []
        for carrier in ("移动", "联通", "电信"):
            value = loss_values.get(carrier)
            if isinstance(value, (int, float)) and value > 0:
                loss_parts.append(f"{carrier} {value:.1f}%")
        self.loss_summary_label.setText("丢包  " + "  ".join(loss_parts) if loss_parts else "丢包  —")
        if status_layout_changed:
            self._apply_status_layout(status_key)
        self.set_surface(self.colors, selected=self.selected, status_key=status_key)
        if presentation_changed or status_layout_changed:
            self._apply_layout_template()
            self._layout_metrics()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.reference_paint:
            # 卡片在首次创建时可能还没有父布局分配宽度；尺寸变化后
            # 必须按新的设计基准重新固定高度，否则不同卡片会沿用
            # 创建时的旧高度，造成皮肤 5/6 的重叠或大片空白。
            preferred = self._reference_height()
            self._preferred_height = preferred
            if self.height() != preferred:
                self.setFixedHeight(preferred)
            self.update()
            return
        self._sync_metric_widths()
        self._fit_to_content()

    def install_input_filter(self, target):
        self.installEventFilter(target)
        for child in self.findChildren(QWidget):
            child.installEventFilter(target)

    def sizeHint(self):
        if self.reference_paint:
            return QSize(404, self._reference_height())
        # ``_fit_to_content`` 可能因为字体回退、DPI 或较长数据把卡片固定到
        # 高于基础 sizeHint 的高度。若仍返回旧的基础值，QGridLayout 会按较
        # 小的行高排版，导致下一张卡片覆盖当前卡片。返回当前实际固定高度
        # 让网格布局使用真实行高。
        preferred = getattr(self, "_preferred_height", self._base_height())
        actual = max(preferred, self.height(), self.minimumHeight())
        return QSize(350, actual)


class ProbeWindow(QWidget):
    MIN_WIDTH, MIN_HEIGHT = 320, 300
    refresh_requested = Signal()

    def __init__(self, live_enabled=None):
        super().__init__(None)
        self.setWindowTitle(WINDOW_TITLE)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, True)
        # 透明窗口是默认视觉；透明合成异常时可用 --opaque 进行可见性回退诊断。
        self.opaque_fallback = "--opaque" in sys.argv
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, not self.opaque_fallback)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, not self.opaque_fallback)
        if self.opaque_fallback:
            self.setAutoFillBackground(True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)

        self.settings = QSettings("KomariDesktop", APP_NAME)
        self._migrate_settings()
        self.editing = False
        self.locked = True
        self.hidden = False
        self.layer_mode = str(self.settings.value("layerMode", "desktop"))
        if self.layer_mode not in {"desktop", "normal", "topmost"}:
            self.layer_mode = "normal"
        self.click_through = self._bool_value("clickThrough", True)
        self.layout_mode = str(self.settings.value("layoutMode", "auto"))
        if self.layout_mode not in {"auto", "single"}:
            self.layout_mode = "auto"
        self.max_per_page = self._number(self.settings.value("maxPerPage", 0), 0, 100, 0)
        self.pinned_node_ids = self._json_list("pinnedNodeIds")
        self._page_anchor = str(self.settings.value("pageAnchor", ""))[:128]
        self._restore_page_pending = True
        self._settings_dialog = None
        self.tray = None
        self._screen_connections = set()
        try:
            self.shortcuts = normalize_shortcuts(json.loads(str(self.settings.value("shortcuts", "{}"))))
        except (ValueError, TypeError, json.JSONDecodeError):
            self.shortcuts = dict(SHORTCUT_DEFAULTS)
        # 参考稿接近不透明；桌面叠加仍可在调整模式中降低透明度。
        self.opacity_percent = self._number(self.settings.value("windowOpacity", 100), 40, 100, 100)
        self.live_enabled = ("--demo" not in sys.argv) if live_enabled is None else bool(live_enabled)
        self.komari_url = normalize_komari_url(
            self.settings.value("komariUrl", KOMARI_BASE_URL),
            allow_insecure_http="--allow-insecure-http" in sys.argv,
        )
        self.source_state = "loading" if self.live_enabled else "demo"
        self.source_error = ""
        self._live_thread = None
        self._live_worker = None
        self._live_busy = False
        self._close_requested = False
        self._initial_show_done = False
        self._retry_failures = 0
        self.refresh_interval_ms = self._number(
            self.settings.value("refreshSeconds", 15), MIN_REFRESH_SECONDS, MAX_REFRESH_SECONDS, 15
        ) * 1000
        self.carousel_interval_ms = self._number(
            self.settings.value("carouselSeconds", 15), MIN_CAROUSEL_SECONDS, MAX_CAROUSEL_SECONDS, 15
        ) * 1000
        self._next_refresh_ms = self.refresh_interval_ms
        self._last_snapshot_save = 0.0
        self._last_live_success_at = 0.0
        self._view_dirty = False
        # 兼容旧版本主题名称，同时保留用户已选择的六款参考皮肤。
        stored_theme = str(self.settings.value("theme", "skin1"))
        theme_aliases = {"mist": "skin4", "graphite": "skin2", "warm": "skin6"}
        stored_theme = theme_aliases.get(stored_theme, stored_theme)
        self.theme = stored_theme if stored_theme in {f"skin{index}" for index in range(1, 7)} else "skin1"
        self.sort_mode = str(self.settings.value("sortMode", "cpu"))
        if self.sort_mode not in {"name", "cpu", "memory", "latency"}:
            self.sort_mode = "name"
        self.group_mode = self._bool_value("groupMode", False if not self.live_enabled else True)
        self.carousel_enabled = self._bool_value("carouselEnabled", False)
        self.page_pinned = self._bool_value("pagePinned", False)
        self.samples = [] if self.live_enabled else self._demo_samples()
        # 会话历史独立于卡片生命周期，翻页/换肤/隐藏不会丢掉已观测到的延迟。
        self._latency_histories = {}
        self._latency_revision = 0
        self.last_update_text = "等待" if self.live_enabled else "刚刚"
        if self.live_enabled:
            self._load_live_snapshot()
        self.selected_ids = set(self._json_list("selectedIds"))
        self.show_all_nodes = self._bool_value("showAllNodes", not bool(self.selected_ids))
        if not self.live_enabled:
            self.selected_ids &= {x["id"] for x in self.samples}
        if self.show_all_nodes:
            self.selected_ids = {x["id"] for x in self.samples}
        try:
            self.page_index = max(0, int(self.settings.value("pageIndex", 0)))
        except (TypeError, ValueError):
            self.page_index = 0
        self._pending_page_index = self.page_index
        self._pending_page_anchor = self._page_anchor
        self.page_count = 1
        self.page_size = 1
        self._page_ranges = [(0, 0)]
        self.phase = 0
        self._layout_rects = []
        self._cards = []
        self._card_ids = ()
        self._card_mode = None
        self._card_columns = None
        self._card_skin = None
        self._hotkey_registered = set()
        self._hotkey_failures = {}
        self.drag_origin = self.drag_geometry = None
        self.resize_origin = self.resize_geometry = None
        self.resize_edge = None
        self._refresh_scheduled = False
        self._edit_mouse_grabbed = False
        self._panel_filters_installed = False
        self._compact_vertical = False
        self._page_content_height = 0

        self._build_shell()
        self.timer = QTimer(self)
        self.timer.setSingleShot(self.live_enabled)
        self.timer.setInterval(self.refresh_interval_ms if self.live_enabled else 1800)
        self.timer.timeout.connect(self._on_refresh_timer)
        if self.live_enabled:
            QTimer.singleShot(0, self._request_live_refresh)
        else:
            self.timer.start()
        self.carousel_timer = QTimer(self)
        self.carousel_timer.setInterval(15_000)
        self.carousel_timer.timeout.connect(self._advance_carousel)
        self._sync_carousel_timer()
        self.native_filter = HotkeyFilter(self)
        QApplication.instance().installNativeEventFilter(self.native_filter)
        QApplication.instance().aboutToQuit.connect(self._shutdown_live_thread)

    @staticmethod
    def _number(value, low, high, fallback):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = fallback
        return max(low, min(high, value))

    def _migrate_settings(self):
        """为历史版本设置补上版本号，但不清理用户已有的可复用偏好。"""
        try:
            version = int(self.settings.value("settingsVersion", 0))
        except (TypeError, ValueError):
            version = 0
        self._geometry_reference_migration = version < SETTINGS_VERSION
        if version < 4 and str(self.settings.value("sortMode", "")) in {"", "name"}:
            # 旧版本默认按名称，而六款设计稿的底部说明统一按 CPU；
            # 用户仍可在调整模式中切回其它排序。
            self.settings.setValue("sortMode", "cpu")
        if version < 6 and self._number(self.settings.value("windowOpacity", 96), 40, 100, 96) == 96:
            # 仅迁移旧版默认值；用户自行选用的其它透明度继续保留。
            self.settings.setValue("windowOpacity", 100)
        if version != SETTINGS_VERSION:
            self.settings.setValue("settingsVersion", SETTINGS_VERSION)

    def _bool_value(self, key, fallback):
        value = self.settings.value(key, fallback)
        return value.strip().lower() in {"1", "true", "yes", "on"} if isinstance(value, str) else bool(value)

    def _json_list(self, key):
        raw = self.settings.value(key, "[]")
        try:
            value = json.loads(raw) if isinstance(raw, str) else list(raw)
            if not isinstance(value, list):
                return []
            return [str(item)[:128] for item in value[:500]
                    if isinstance(item, (str, int)) and not isinstance(item, bool)]
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    def _on_refresh_timer(self):
        if self.live_enabled:
            self._request_live_refresh()
        else:
            self._tick()

    def _load_live_snapshot(self):
        raw = self.settings.value("liveSnapshot", "")
        if not isinstance(raw, str) or not raw or len(raw) > 512_000:
            return
        try:
            snapshot = json.loads(raw)
            if not isinstance(snapshot, dict) or snapshot.get("url") != self.komari_url:
                return
            saved_at = snapshot.get("saved_at")
            if (not isinstance(saved_at, (int, float)) or not math.isfinite(saved_at)
                    or not 0 <= time.time() - saved_at <= 7 * 86400):
                return
            samples = snapshot.get("samples")
            if not isinstance(samples, list) or len(samples) > 500:
                return
            numeric_keys = ("cpu", "memory", "upload", "download")
            text_limits = {"id": 128, "name": 160, "region": 128, "code": 16,
                           "traffic": 96, "expires": 32, "traffic_label": 16}
            for item in samples:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"]:
                    return
                if any(not isinstance(item.get(key), str) for key in ("name", "region", "code", "traffic", "expires")):
                    return
                if any(len(str(item.get(key, ""))) > limit for key, limit in text_limits.items()):
                    return
                if any(item.get(key) is not None and KomariClient._number(item[key]) is None for key in numeric_keys):
                    return
                for key in ("latency", "loss"):
                    values = item.get(key)
                    if (not isinstance(values, dict) or any(
                        value is not None and KomariClient._number(value) is None for value in values.values()
                    )):
                        return
                item["_last_status"] = item.get("status", "stale")
                item["status"] = "stale"
            self.samples = samples
            self.last_update_text = datetime.fromtimestamp(saved_at).strftime("%m-%d %H:%M")
            self.source_state = "cached"
        except (TypeError, ValueError, OSError, OverflowError, json.JSONDecodeError):
            return

    def _save_live_snapshot(self):
        # 仅保存界面已使用的白名单字段，不持久化接口原始响应、公网 IP 或凭据。
        now = time.monotonic()
        if self._last_snapshot_save and now - self._last_snapshot_save < 60:
            return
        keys = ("id", "name", "region", "code", "status", "cpu", "memory", "upload", "download",
                "traffic", "traffic_label", "expires", "latency", "loss", "updated_at")
        snapshot = {
            "url": self.komari_url, "saved_at": time.time(),
            "samples": [{key: item.get(key) for key in keys} for item in self.samples[:500]],
        }
        raw = json.dumps(snapshot, ensure_ascii=False, allow_nan=False)
        if len(raw) <= 512_000:
            self.settings.setValue("liveSnapshot", raw)
            self.settings.sync()
            self._last_snapshot_save = now

    def _request_live_refresh(self):
        if not self.live_enabled or self._close_requested or self._live_busy:
            return
        self.timer.stop()
        if self._live_thread is None:
            thread = QThread(self)
            worker = LiveRefreshWorker(self.komari_url)
            worker.moveToThread(thread)
            self.refresh_requested.connect(worker.run)
            worker.succeeded.connect(self._on_live_success, Qt.ConnectionType.QueuedConnection)
            worker.failed.connect(self._on_live_failure, Qt.ConnectionType.QueuedConnection)
            worker.finished.connect(self._on_live_refresh_finished, Qt.ConnectionType.QueuedConnection)
            thread.finished.connect(worker.deleteLater)
            thread.finished.connect(self._on_live_thread_finished, Qt.ConnectionType.QueuedConnection)
            thread.finished.connect(thread.deleteLater)
            self._live_thread = thread
            self._live_worker = worker
            thread.start()
        self._live_busy = True
        self.refresh_requested.emit()

    @Slot()
    def _on_live_refresh_finished(self):
        self._live_busy = False
        if self._close_requested:
            if self._live_thread:
                self._live_thread.quit()
            return
        if self.live_enabled:
            self.timer.start(max(60_000, self._next_refresh_ms) if self.hidden else self._next_refresh_ms)

    @Slot()
    def _on_live_thread_finished(self):
        self._live_thread = None
        # 保留 Python 包装对象至窗口释放；原生 worker 由 thread.finished/deleteLater
        # 在所属线程销毁，不能同时从主线程丢弃最后一个 Python 引用。
        self._live_busy = False
        if self._close_requested:
            QTimer.singleShot(0, self.close)

    @Slot(object, str)
    def _on_live_success(self, samples, updated_at):
        if self._close_requested:
            return
        if not isinstance(samples, list):
            self._on_live_failure("节点数据格式异常")
            return
        self._record_latency_history(samples)
        self.samples = samples
        self.source_state = "ok"
        self.source_error = ""
        self._retry_failures = 0
        self._next_refresh_ms = self.refresh_interval_ms
        self.last_update_text = updated_at or "刚刚"
        self._last_live_success_at = time.monotonic()
        available = {str(item.get("id")) for item in samples if item.get("id")}
        if self.show_all_nodes:
            self.selected_ids = set(available)
        if self._restore_page_pending and samples:
            self.page_index = self._pending_page_index
            self._page_anchor = self._pending_page_anchor
            self._restore_page_pending = False
        if self.hidden:
            self._view_dirty = True
        else:
            self._refresh_cards()
        if self.live_enabled:
            self._save_live_snapshot()

    def _record_latency_history(self, samples):
        """每轮成功请求只记一次；未显示节点也采样，缺失/离线留断点。"""
        self._latency_revision += 1
        available = {item.get("id") for item in samples if item.get("id")}
        self._latency_histories = {
            key: history for key, history in self._latency_histories.items() if key in available
        }
        for item in samples:
            node_id = item.get("id")
            if not node_id:
                continue
            history = self._latency_histories.setdefault(node_id, {})
            latency = item.get("latency") if isinstance(item.get("latency"), dict) else {}
            for carrier in ("移动", "联通", "电信"):
                value = KomariClient._number(latency.get(carrier)) if item.get("status") == "online" else None
                points = history.setdefault(carrier, [])
                points.append(value if value is not None and value > 0 else None)
                del points[:-24]
            item["_latency_history"] = {carrier: tuple(points) for carrier, points in history.items()}
            item["_latency_revision"] = self._latency_revision

    @Slot(str)
    def _on_live_failure(self, message):
        if self._close_requested:
            return
        self.source_state = "error"
        self.source_error = str(message or "连接失败")[:120]
        self._retry_failures += 1
        self._next_refresh_ms = min(
            KOMARI_MAX_RETRY_MS, self.refresh_interval_ms * 2 ** min(self._retry_failures - 1, 8)
        )
        if self.samples:
            for item in self.samples:
                if item.get("status") != "stale":
                    item["_last_status"] = item.get("status")
                item["status"] = "stale"
            if self._retry_failures == 1:
                self._record_latency_history(self.samples)
            if self.hidden:
                self._view_dirty = True
            else:
                self._refresh_cards(force=False)
        else:
            self._update_header_labels()
            self._refresh_visual_size()

    def _sync_carousel_timer(self):
        self.carousel_timer.setInterval(self.carousel_interval_ms)
        if (self.carousel_enabled and not self.page_pinned
                and not self.editing and not self.hidden and self._settings_dialog is None
                and not self._close_requested):
            self.carousel_timer.start()
        else:
            self.carousel_timer.stop()

    def _advance_carousel(self):
        if self.page_count > 1 and not self.page_pinned and not self.editing and not self.hidden:
            self.next_page()

    @staticmethod
    def _demo_samples():
        def node(id_, name, region, code, status, cpu, memory, upload, download, traffic, expires, latency, loss):
            # 仅供演示皮肤 6 的静态回归图使用；真实数据不会携带此字段。
            trend_offsets = {
                "移动": (0, -3, 2, -2, 3, -1, 1, -2, 2, 0, -1, 1),
                "联通": (0, 4, -3, 5, -2, 3, -4, 2, -1, 3, -2, 0),
                "电信": (0, -2, 3, -1, 2, -3, 1, -2, 2, -1, 1, 0),
            }
            demo_trend = {}
            for carrier, value in (latency or {}).items():
                if isinstance(value, (int, float)) and math.isfinite(value) and value > 0:
                    amplitude = 4.0 if value >= 120 else 0.5
                    anchors = [max(1.0, float(value) + offset * amplitude)
                               for offset in trend_offsets.get(carrier, (0, 1, -1, 0))]
                    # 演示补足同一24点采样窗，绘制代码与真实历史共用横向映射。
                    demo_trend[carrier] = []
                    for index in range(24):
                        position = index * (len(anchors) - 1) / 23
                        left = int(position)
                        right = min(left + 1, len(anchors) - 1)
                        ratio = position - left
                        demo_trend[carrier].append(anchors[left] * (1 - ratio) + anchors[right] * ratio)
            demo_segments = {carrier: [float(value)] * 12 for carrier, value in (latency or {}).items()
                             if isinstance(value, (int, float)) and math.isfinite(value) and value > 0}
            if id_ == "nl-nat":
                demo_segments["电信"] = [195, 213, 195, 195, 208, 195, 195, 195, 195, 195, 195, 195]
            return {
                "id": id_,
                "name": name,
                "region": region,
                "code": code,
                "status": status,
                "cpu": cpu,
                "memory": memory,
                "upload": upload,
                "download": download,
                "traffic": traffic,
                "expires": expires,
                "latency": latency,
                "loss": loss,
                "_demo_trend": demo_trend,
                "_demo_segments": demo_segments,
            }

        return [
            node("nl-nat", "荷兰 · NAT", "荷兰", "NL", "online", 58.9, 8.7, 1.7, 1.0,
                 "184.9 MiB / 1 TiB", "2027-08-15",
                 {"移动": 243, "联通": 373, "电信": 195},
                 {"移动": 0.0, "联通": 1.1, "电信": 0.0}),
            node("hk-bgp", "香港 · BGP", "香港", "HK", "online", 17.1, 47.0, 68.2, 99.6,
                 "2.4 TiB / 5 TiB", "2027-01-26",
                 {"移动": 42, "联通": 31, "电信": 39},
                 {"移动": 0.0, "联通": 0.0, "电信": 0.4}),
            node("us-c", "洛杉矶 · C", "美国", "US", "offline", None, None, None, None,
                 None, None,
                 {"移动": 188, "联通": 0, "电信": 214},
                 {"移动": 0.0, "联通": None, "电信": 0.0}),
            node("de-9929", "德国 · 9929线路", "德国", "DE", "online", 1.2, 23.8, 35.2, 32.7,
                 "114.4 GiB / 1.2 TiB", "2027-08-01",
                 {"移动": 146, "联通": 121, "电信": 186},
                 {"移动": 0.0, "联通": 0.0, "电信": 0.0}),
            node("de-max", "德国 · MAX", "德国", "DE", "online", 3.2, 38.4, 4.0, 6.2,
                 "1.69 TiB / 10 TiB", "2027-03-13",
                 {"移动": 239, "联通": 161, "电信": 199},
                 {"移动": 0.0, "联通": 0.2, "电信": 0.0}),
            node("jp-lite", "日本 · Lite", "日本", "JP", "stale", None, None, None, None,
                 None, None,
                 {"移动": None, "联通": None, "电信": None},
                 {"移动": None, "联通": None, "电信": None}),
        ]

    def _build_shell(self):
        self.panel = SurfaceFrame("panel", self)
        self.panel.setObjectName("panel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(0)
        outer.addWidget(self.panel)

        self.panel_layout = QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(18, 14, 18, 10)
        # 参考图的标题、节点区和底部图例之间间隔很紧；
        # 过大的公共 spacing 会在 440×540 基准下挤掉第三个节点。
        self.panel_layout.setSpacing(0)

        header = DashboardHeader(self.panel)
        self.header = header
        self.header_layout = QVBoxLayout(header)
        self.header_layout.setContentsMargins(0, 0, 0, 7)
        self.header_layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        self.title_label = QLabel("VPS 监控", header)
        self.title_label.setFixedHeight(24)
        self.mode_label = QLabel(header)
        self.mode_label.setFixedHeight(24)
        self.mode_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        title_row.addWidget(self.title_label, 1)
        title_row.addWidget(self.mode_label)
        self.header_layout.addLayout(title_row)

        summary_row = QHBoxLayout()
        summary_row.setContentsMargins(0, 0, 0, 0)
        summary_row.setSpacing(8)
        self.summary_label = StatusSummaryLabel(header)
        self.summary_label.setFixedHeight(16)
        self.summary_label.setTextFormat(Qt.TextFormat.RichText)
        self.header_hint = QLabel(header)
        self.header_hint.setFixedHeight(16)
        self.header_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        summary_row.addWidget(self.summary_label, 1)
        summary_row.addWidget(self.header_hint)
        self.header_layout.addLayout(summary_row)
        self.panel_layout.addWidget(header)

        self.toolbar = SurfaceFrame("toolbar", self.panel)
        toolbar_layout = QHBoxLayout(self.toolbar)
        toolbar_layout.setContentsMargins(11, 5, 11, 5)
        toolbar_layout.setSpacing(8)
        self.page_label = QLabel(self.toolbar)
        self.page_label.setToolTip(
            "Ctrl+Alt+P / Ctrl+Alt+N 翻页；Ctrl+Alt+1–9 跳转并固定；Ctrl+Alt+0 取消固定"
        )
        self.view_label = QLabel(self.toolbar)
        self.toolbar_hint = QLabel(self.toolbar)
        self.toolbar_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.action_row = QWidget(self.toolbar)
        action_layout = QHBoxLayout(self.action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(4)
        self.prev_button = ActionButton("‹", "上一页", self.action_row)
        self.next_button = ActionButton("›", "下一页", self.action_row)
        self.pin_button = ActionButton("锁", "固定当前页（锁定后自动轮播不会切页）", self.action_row)
        self.carousel_button = ActionButton("停", "开启或关闭自动轮播", self.action_row)
        self.refresh_spin = QSpinBox(self.action_row)
        self.carousel_spin = QSpinBox(self.action_row)
        for spin, low, high, value, tooltip in (
            (self.refresh_spin, MIN_REFRESH_SECONDS, MAX_REFRESH_SECONDS,
             self.refresh_interval_ms // 1000, "实时数据刷新间隔（秒）"),
            (self.carousel_spin, MIN_CAROUSEL_SECONDS, MAX_CAROUSEL_SECONDS,
             self.carousel_interval_ms // 1000, "自动轮播翻页间隔（秒）"),
        ):
            spin.setRange(low, high)
            spin.setValue(value)
            spin.setSuffix("s")
            spin.setToolTip(tooltip)
            spin.setKeyboardTracking(False)
            spin.setFixedSize(52, 24)
            spin.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            spin.setProperty("interactive_control", True)
        self.theme_button = ActionButton("T", "切换主题", self.action_row)
        self.opacity_down_button = ActionButton("−", "降低透明度", self.action_row)
        self.opacity_up_button = ActionButton("+", "提高透明度", self.action_row)
        self.settings_button = ActionButton("设", "打开设置", self.action_row)
        for button in (
            self.prev_button,
            self.next_button,
            self.pin_button,
            self.carousel_button,
            self.theme_button,
            self.opacity_down_button,
            self.opacity_up_button,
            self.settings_button,
        ):
            action_layout.addWidget(button)
        action_layout.addWidget(self.refresh_spin)
        action_layout.addWidget(self.carousel_spin)
        self.prev_button.clicked.connect(lambda: self.next_page(-1))
        # clicked 会附带 checked 布尔值，不能直接传给带 step 参数的 next_page。
        self.next_button.clicked.connect(lambda: self.next_page(1))
        self.pin_button.clicked.connect(self.toggle_page_pin)
        self.carousel_button.clicked.connect(self.toggle_carousel)
        self.refresh_spin.valueChanged.connect(self.set_refresh_seconds)
        self.carousel_spin.valueChanged.connect(self.set_carousel_seconds)
        self.theme_button.clicked.connect(self.cycle_theme)
        self.opacity_down_button.clicked.connect(lambda: self.adjust_opacity(-5))
        self.opacity_up_button.clicked.connect(lambda: self.adjust_opacity(5))
        self.settings_button.clicked.connect(self.open_settings)
        self.action_row.hide()
        toolbar_layout.addWidget(self.page_label)
        toolbar_layout.addWidget(self.view_label)
        toolbar_layout.addStretch(1)
        toolbar_layout.addWidget(self.action_row)
        toolbar_layout.addWidget(self.toolbar_hint)
        self.panel_layout.addWidget(self.toolbar)

        self.cards_scroll = QScrollArea(self.panel)
        self.cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: 0; }")
        self.cards_scroll.viewport().setAutoFillBackground(False)
        self.cards_scroll.verticalScrollBar().setProperty("interactive_control", True)
        self.cards_scroll.viewport().installEventFilter(self)
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setHorizontalSpacing(0)
        self.cards_layout.setVerticalSpacing(0)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cards_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.cards_scroll.setWidget(self.cards_container)
        self.empty_state = QLabel(self.cards_scroll.viewport())
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setWordWrap(True)
        self.empty_state.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.panel_layout.addWidget(self.cards_scroll, 1)

        self.footer_row = QWidget(self.panel)
        footer_layout = QHBoxLayout(self.footer_row)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(8)
        self.footer_label = QLabel(self.footer_row)
        self.footer_page_label = QLabel(self.footer_row)
        self.footer_page_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        footer_layout.addWidget(self.footer_label, 1)
        footer_layout.addWidget(self.footer_page_label)
        self.footer_row.setFixedHeight(16)
        self.panel_layout.addWidget(self.footer_row)
        self._apply_theme()
        self._refresh_cards(force=True)

    def settings_snapshot(self):
        return {
            "layer_mode": self.layer_mode, "click_through": self.click_through,
            "opacity": self.opacity_percent, "theme": self.theme, "layout_mode": self.layout_mode,
            "max_per_page": self.max_per_page, "refresh_seconds": self.refresh_interval_ms // 1000,
            "carousel_seconds": self.carousel_interval_ms // 1000, "carousel_enabled": self.carousel_enabled,
            "sort_mode": self.sort_mode, "group_mode": self.group_mode, "show_all_nodes": self.show_all_nodes,
            "selected_ids": sorted(self.selected_ids), "shortcuts": dict(self.shortcuts),
            "window_width": self.width(), "window_height": self.height(),
            "screen_name": self.screen().name() if self.screen() else "", "position": "keep",
            "pin_current": self.page_pinned, "page_count": self.page_count,
            "page_index": self.page_index, "samples": list(self.samples),
        }

    def apply_preferences(self, values):
        """全部校验后才应用；快捷键注册失败恢复原组合，禁止半保存草稿。"""
        preferences = self.settings_snapshot()
        preferences.update(values)
        try:
            for key, choices in {
                "layer_mode": {"desktop", "normal", "topmost"}, "theme": set(SKIN_NAMES),
                "layout_mode": {"auto", "single"}, "sort_mode": {"name", "cpu", "memory", "latency"},
                "position": {"keep", "topright", "topleft", "bottomright", "bottomleft", "center"},
            }.items():
                if preferences[key] not in choices:
                    raise ValueError(f"{key} 设置值无效")
            for key, low, high in (("opacity", 40, 100), ("max_per_page", 0, 100),
                                   ("refresh_seconds", 5, 300), ("carousel_seconds", 5, 120),
                                   ("window_width", 320, 32768), ("window_height", 300, 32768)):
                if type(preferences[key]) is not int or not low <= preferences[key] <= high:
                    raise ValueError(f"{key} 必须在 {low}–{high} 范围内")
            for key in ("click_through", "carousel_enabled", "group_mode", "show_all_nodes", "pin_current"):
                if type(preferences[key]) is not bool:
                    raise ValueError(f"{key} 必须为开关值")
            selected = preferences["selected_ids"]
            if not isinstance(selected, list) or len(selected) > 500 or any(
                not isinstance(value, str) or not value or len(value) > 128 for value in selected):
                raise ValueError("节点选择格式无效")
            shortcuts = normalize_shortcuts(preferences["shortcuts"])
            screens = QApplication.screens()
            target_screen = next((screen for screen in screens if screen.name() == preferences["screen_name"]), None)
            if preferences["screen_name"] and target_screen is None:
                raise ValueError("目标显示器已断开，请重新选择")
        except (ValueError, TypeError, KeyError) as error:
            return str(error)
        if shortcuts != self.shortcuts and self._initial_show_done:
            previous = self.shortcuts
            self._unregister_hotkeys()
            self.shortcuts = shortcuts
            self._register_hotkeys()
            if self._hotkey_failures:
                failed = ", ".join(self._hotkey_failures)
                self._unregister_hotkeys()
                self.shortcuts = previous
                self._register_hotkeys()
                return f"快捷键被占用：{failed}。已恢复原快捷键，本次设置未保存。"
        self.shortcuts = shortcuts
        selection_changed = self.selected_ids != set(selected) or self.show_all_nodes != preferences["show_all_nodes"]
        self.selected_ids = set(selected)
        self.show_all_nodes = preferences["show_all_nodes"]
        self.click_through = preferences["click_through"]
        self.layer_mode = preferences["layer_mode"]
        self.layout_mode = preferences["layout_mode"]
        self.max_per_page = preferences["max_per_page"]
        self.opacity_percent = preferences["opacity"]
        self.theme = preferences["theme"]
        self.sort_mode = preferences["sort_mode"]
        self.group_mode = preferences["group_mode"]
        self.carousel_enabled = preferences["carousel_enabled"]
        self.refresh_interval_ms = preferences["refresh_seconds"] * 1000
        self.carousel_interval_ms = preferences["carousel_seconds"] * 1000
        self._next_refresh_ms = max(self._next_refresh_ms, self.refresh_interval_ms) if self.source_state == "error" else self.refresh_interval_ms
        if selection_changed:
            self.pinned_node_ids = []
            self.page_pinned = False
            self._page_anchor = ""
            self.page_index = 0
        if not preferences["pin_current"]:
            self.page_pinned = False
            self.pinned_node_ids = []
        self.resize(preferences["window_width"], preferences["window_height"])
        if preferences["position"] != "keep" or (target_screen and target_screen != self.screen()):
            work = (target_screen or self.screen() or QApplication.primaryScreen()).availableGeometry()
            position = preferences["position"]
            x, y = work.right() - self.width() - 18, work.top() + 18
            if position in {"topleft", "bottomleft"}:
                x = work.left() + 18
            if position in {"bottomleft", "bottomright"}:
                y = work.bottom() - self.height() - 18
            if position == "center":
                x, y = work.center().x() - self.width() // 2, work.center().y() - self.height() // 2
            self.setGeometry(fit_geometry(QRect(x, y, self.width(), self.height()), work))
        self._apply_theme()
        self._clamp_to_screens()
        self._refresh_cards(force=True)
        if preferences["pin_current"] and not self.page_pinned:
            self.toggle_page_pin()
        self._set_locked(self.locked)
        if not self.editing and not self._place_desktop():
            return getattr(self, "_layer_error", "图层应用失败")
        self._sync_carousel_timer()
        if self.live_enabled and not self._live_busy:
            self.timer.start(max(60_000, self._next_refresh_ms) if self.hidden else self._next_refresh_ms)
        self._save_settings()
        return None

    def open_settings(self):
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self)
            self._settings_dialog.finished.connect(self._settings_closed)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()
        self._sync_carousel_timer()

    def _settings_closed(self, *_):
        dialog, self._settings_dialog = self._settings_dialog, None
        if dialog is not None:
            dialog.deleteLater()
        self._sync_carousel_timer()

    def _create_tray(self):
        if self.tray is not None or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon), self)
        self.tray.setToolTip(f"KomariDesktop {APP_VERSION}")
        self.tray_menu = QMenu()
        self.tray_menu.aboutToShow.connect(self._build_tray_menu)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(lambda reason: self.open_settings()
                                   if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def _build_tray_menu(self):
        menu = self.tray_menu
        menu.clear()
        def action(label, callback, check=None, target=menu):
            item = target.addAction(label)
            if check is not None:
                item.setCheckable(True)
                item.setChecked(check)
            item.triggered.connect(lambda checked=False: callback())
            return item
        action("显示面板" if self.hidden else "隐藏面板", self.toggle_hidden)
        action("退出调整" if self.editing else "调整位置和大小", self.toggle_editing)
        action("设置…", self.open_settings)
        layer_menu = menu.addMenu("图层")
        for mode, label in (("desktop", "桌面后层"), ("normal", "普通非置顶"), ("topmost", "始终置顶")):
            action(label, lambda mode=mode: self.set_layer_mode(mode), self.layer_mode == mode, layer_menu)
        menu.addSeparator()
        action("上一页", lambda: self.next_page(-1)).setEnabled(self.page_count > 1)
        action("下一页", lambda: self.next_page(1)).setEnabled(self.page_count > 1)
        action("取消固定节点" if self.page_pinned else "固定当前节点", self.toggle_page_pin)
        action("自动轮播", self.toggle_carousel, self.carousel_enabled)
        action("立即刷新", self._request_live_refresh).setEnabled(self.live_enabled and not self._live_busy)
        action("找回面板到当前屏幕", self.recover_to_screen)
        menu.addSeparator()
        action("退出", self.close)

    def recover_to_screen(self):
        if self.hidden:
            self.toggle_hidden()
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen:
            work = screen.availableGeometry()
            self.setGeometry(fit_geometry(QRect(work.right() - self.width() - 24, work.top() + 24,
                                                self.width(), self.height()), work))
        self.toggle_editing() if self.locked else self._place_editing()
        self._save_settings()

    @staticmethod
    def _gradient(top, bottom, alpha=255):
        from PySide6.QtGui import QLinearGradient

        gradient = QLinearGradient(0, 0, 0, 1)
        gradient.setCoordinateMode(QLinearGradient.CoordinateMode.ObjectBoundingMode)
        gradient.setColorAt(0, _qcolor(top, alpha))
        gradient.setColorAt(1, _qcolor(bottom, alpha))
        return gradient

    def _colors(self):
        themes = {
            "skin4": {
                "panel_top": "#ecedef", "panel_bottom": "#ecedef", "panel_border": "#d7dce3",
                "panel_highlight": "#ffffff", "toolbar": "#e7e9ee", "card_top": "#ecedef",
                "card_bottom": "#ecedef", "card_muted": "#e5e7ec", "card_border": "#d4dae2",
                "card_highlight": "#ffffff", "metric": "#ecedef", "chip": "#e6e8ed",
                "fg": "#29313c", "muted": "#71808f", "subtle": "#8e99a5", "accent": "#29313c",
                "accent_2": "#d18b24", "track": "#d4d9e1", "rule": "#d4dae2",
                "online": "#2f8c63", "offline": "#a84e5c", "stale": "#9a7125",
                "status_online_fill": "#dcefe0", "status_online_text": "#216c49", "status_online_border": "#8fcaa5",
                "shadow": "#566166", "mobile": "#167e78", "unicom": "#7357a1",
                "telecom": "#a86b25", "latency_style": "bars",
                "metric_cpu_accent": "#29313c", "metric_memory_accent": "#29313c",
                "metric_upload_accent": "#29313c", "metric_download_accent": "#29313c",
                "carrier_移动": "#e84d9a", "carrier_联通": "#458bf4", "carrier_电信": "#8e63e8",
                "chip_移动": "#f4dce7", "chip_联通": "#dce8fb", "chip_电信": "#f8edc7",
            },
            "skin2": {
                "panel_top": "#212227", "panel_bottom": "#212227", "panel_border": "#3b3e46",
                "panel_highlight": "#5d626c", "toolbar": "#27292e", "card_top": "#212227",
                "card_bottom": "#212227", "card_muted": "#282a30", "card_border": "#41444c",
                "card_highlight": "#676c75", "metric": "#242529", "chip": "#303238",
                "fg": "#f1f6fb", "muted": "#a9b9ca", "subtle": "#7b8fa5", "accent": "#78d9cf",
                "accent_2": "#f2bd68", "track": "#474a52", "rule": "#3e4048",
                "online": "#79dda2", "offline": "#f1848e", "stale": "#f0c66e",
                "status_online_fill": "#1d5a42", "status_online_text": "#8ee2b6", "status_online_border": "#2b875f",
                "shadow": "#080b11", "mobile": "#79ccd5", "unicom": "#b58ae8",
                "telecom": "#e9bb70", "latency_style": "chips",
                "metric_cpu": "#2a3039", "metric_memory": "#2d3340",
                "metric_upload": "#303039", "metric_download": "#29363b",
                "metric_cpu_accent": "#f1f6fb", "metric_memory_accent": "#f1f6fb",
                "metric_upload_accent": "#f1f6fb", "metric_download_accent": "#f1f6fb",
                "carrier_移动": "#ef6aa5", "carrier_联通": "#62a9ff", "carrier_电信": "#8e63e8",
                "chip_移动": "#4a3025", "chip_联通": "#422530", "chip_电信": "#484022",
            },
            "skin6": {
                "panel_top": "#efe6d9", "panel_bottom": "#efe6d9", "panel_border": "#ded2bf",
                "panel_highlight": "#fffaf2", "toolbar": "#ece2d1", "card_top": "#efe6d9",
                "card_bottom": "#efe6d9", "card_muted": "#ebe2d4", "card_border": "#ded2bf",
                "card_highlight": "#fffaf2", "metric": "#efe6d9", "chip": "#eee4d5",
                "metric_cpu": "#e7c0a4", "metric_memory": "#d8c6d4", "metric_upload": "#e6bdb2", "metric_download": "#c4d0cc",
                "metric_cpu_accent": "#bd6738", "metric_memory_accent": "#72579c", "metric_upload_accent": "#b85a47", "metric_download_accent": "#367c98",
                "chip_移动": "#d7dfd4", "chip_联通": "#d9c9d3", "chip_电信": "#d9d4c8",
                "fg": "#4b4035", "muted": "#806f60", "subtle": "#988a79", "accent": "#8f5c43",
                "accent_2": "#b87946", "track": "#ddcfbc", "rule": "#ded2bf",
                "online": "#2e7a5a", "offline": "#a74e55", "stale": "#a6782e",
                "status_online_fill": "#dcefe0", "status_online_text": "#286d4d", "status_online_border": "#8fc4a2",
                "shadow": "#5e4035", "mobile": "#2f8178", "unicom": "#795b9b",
                "telecom": "#8e63e8", "carrier_移动": "#e84d9a", "carrier_联通": "#458bf4",
                "carrier_电信": "#8e63e8",
                "latency_style": "trend",
                "metric_cpu_accent": "#4b4035", "metric_memory_accent": "#4b4035",
                "metric_upload_accent": "#4b4035", "metric_download_accent": "#4b4035",
            },
            "skin3": {
                "panel_top": "#26272b", "panel_bottom": "#26272b", "panel_border": "#3d4149",
                "panel_highlight": "#656a74", "toolbar": "#292b30", "card_top": "#26272b",
                "card_bottom": "#26272b", "card_muted": "#2b2d33", "card_border": "#424750",
                "card_highlight": "#6b717a", "metric": "#26272b", "chip": "#2a2e34",
                "metric_cpu": "#273340", "metric_memory": "#273340",
                "metric_upload": "#273340", "metric_download": "#273340",
                "metric_cpu_accent": "#f1f4f7", "metric_memory_accent": "#d6e1ef",
                "metric_upload_accent": "#7bd5c8", "metric_download_accent": "#78b9ff",
                "fg": "#f0f1f2", "muted": "#abb0b8", "subtle": "#7b818b", "accent": "#78b9ff",
                "accent_2": "#f1c75b", "track": "#394554", "rule": "#3b4655",
                "online": "#52d39b", "offline": "#f18791", "stale": "#e8c15a",
                "status_online_fill": "#1d5a42", "status_online_text": "#9be7be", "status_online_border": "#2d8c66",
                "shadow": "#0c1016", "mobile": "#ef6aa5", "unicom": "#62a9ff", "telecom": "#f0c95b",
                "carrier_移动": "#ef6aa5", "carrier_联通": "#62a9ff", "carrier_电信": "#8e63e8",
                "chip_移动": "#38283a", "chip_联通": "#25364b", "chip_电信": "#3b3524",
                "latency_style": "segments",
            },
            "skin5": {
                "panel_top": "#202126", "panel_bottom": "#202126", "panel_border": "#3d4149",
                "panel_highlight": "#626872", "toolbar": "#27282d", "card_top": "#202126",
                "card_bottom": "#202126", "card_muted": "#282b30", "card_border": "#424750",
                "card_highlight": "#6b717a", "metric": "#292d33", "chip": "#2a2e34",
                "metric_cpu": "#2d3035", "metric_memory": "#2d3035",
                "metric_upload": "#2d3035", "metric_download": "#2d3035",
                "metric_cpu_accent": "#f0f1f2", "metric_memory_accent": "#f0f1f2",
                "metric_upload_accent": "#f0f1f2", "metric_download_accent": "#f0f1f2",
                "fg": "#f0f1f2", "muted": "#abb0b8", "subtle": "#7b818b", "accent": "#76d5c5",
                "accent_2": "#f2c554", "track": "#454a52", "rule": "#3b3f46",
                "online": "#55d49b", "offline": "#f4878c", "stale": "#e4bd52",
                "status_online_fill": "#1d5a42", "status_online_text": "#8ee2b6", "status_online_border": "#2d8c66",
                "shadow": "#0b0c0f", "mobile": "#f18b36", "unicom": "#e03b60", "telecom": "#f0c62e",
                "carrier_移动": "#ef6aa5", "carrier_联通": "#62a9ff", "carrier_电信": "#8e63e8",
                "chip_移动": "#754323", "chip_联通": "#6b2437", "chip_电信": "#6d5b1d",
                "latency_style": "blocks",
            },
            "skin1": {
                "panel_top": "#F2EEE6", "panel_bottom": "#F2EEE6", "panel_border": "#DDD7CB",
                "panel_highlight": "#FFFFFF", "toolbar": "#F2EEE6", "card_top": "#F2EEE6",
                "card_bottom": "#F2EEE6", "card_muted": "#EEEAE1", "card_border": "#D8D2C6",
                "card_highlight": "#FFFFFF", "metric": "#F2EEE6", "chip": "#E5E5DE",
                "metric_cpu": "#F2EEE6", "metric_memory": "#F2EEE6",
                "metric_upload": "#F2EEE6", "metric_download": "#F2EEE6",
                "metric_cpu_accent": "#2D2E32", "metric_memory_accent": "#2D2E32",
                "metric_upload_accent": "#2D2E32", "metric_download_accent": "#2D2E32",
                "chip_移动": "#E5E5DE", "chip_联通": "#E5E5DE", "chip_电信": "#E5E5DE",
                "fg": "#2C2C2A", "muted": "#7A766D", "subtle": "#9A958A", "accent": "#2D2E32",
                "accent_2": "#C28B2C", "track": "#D8D8D2", "rule": "#D8D3C8",
                "online": "#2DB77A", "offline": "#8D8D86", "stale": "#D09B1C",
                "status_online_fill": "#dcefe0", "status_online_text": "#216c49", "status_online_border": "#8fcaa5",
                "shadow": "#B5AEA2", "mobile": "#E84D9A", "unicom": "#4C8FE9", "telecom": "#8E63E8",
                "carrier_移动": "#E84D9A", "carrier_联通": "#4C8FE9", "carrier_电信": "#8E63E8",
                "chip_border": "#D6D1C6",
                "level_excellent": "#36BC86", "level_good": "#8ACB3F", "level_normal": "#F1C21B",
                "level_poor": "#F28A32", "level_bad": "#D92F50", "level_unknown": "#E2E1DB",
                "level_excellent_text": "#183C2C", "level_good_text": "#25341D",
                "level_normal_text": "#44370A", "level_poor_text": "#4C260D",
                "level_bad_text": "#FFFFFF", "level_unknown_text": "#6F6B63",
                "latency_style": "chips",
            },
        }
        theme_aliases = {"mist": "skin4", "graphite": "skin2", "warm": "skin6"}
        theme_key = theme_aliases.get(self.theme, self.theme)
        raw = dict(themes.get(theme_key, themes["skin1"]))
        # 以下令牌取自用户 @2x 原稿的文字内部、徽标和图例实色；
        # 将运营商标识色与延迟质量色分开，避免趋势标签误用粉/蓝/紫。
        reference_palette = {
            "skin1": {
                "panel_top": "#f2eee6", "panel_bottom": "#f1ede5",
                "fg": "#262420", "muted": "#5e574d", "track": "#ddd6ca", "rule": "#d6cec0",
                "status_online_fill": "#dcebd8", "status_online_text": "#245c3e",
            },
            "skin2": {
                "panel_top": "#222328", "panel_bottom": "#212227",
                "fg": "#eceef2", "muted": "#b0b6c0", "track": "#3a3f48", "rule": "#363b44",
                "status_online_fill": "#1f4a38", "status_online_text": "#8fe0b6",
            },
            "skin3": {
                "panel_top": "#26272b", "panel_bottom": "#25262b",
                "fg": "#efede9", "muted": "#b3b0aa", "track": "#403f44", "rule": "#3a393e",
                "status_online_fill": "#25402f", "status_online_text": "#a6dcb0",
            },
            "skin4": {
                "panel_top": "#ecedef", "panel_bottom": "#ebecee",
                "fg": "#1f2430", "muted": "#525a68", "track": "#d9dde4", "rule": "#d9dde4",
                "status_online_fill": "#dcebdf", "status_online_text": "#235a3a",
            },
            "skin5": {
                "panel_top": "#212227", "panel_bottom": "#1f2126",
                "fg": "#eceef2", "muted": "#b0b6c0", "track": "#3a3f48", "rule": "#363b44",
                "status_online_fill": "#1f4a38", "status_online_text": "#8fe0b6",
            },
            "skin6": {
                "panel_top": "#efe6da", "panel_bottom": "#eee5d9",
                "fg": "#33281f", "muted": "#64513d", "track": "#e1d3bd", "rule": "#d6c4a8",
                "status_online_fill": "#dcebd8", "status_online_text": "#245c3e",
            },
        }
        raw.update(reference_palette.get(theme_key, reference_palette["skin1"]))
        raw.update({
            "subtle": raw["muted"],
            "online": "#3ec28a", "offline": raw["muted"], "stale": "#e0a82a",
            "status_online_border": raw["status_online_fill"],
            "carrier_移动": "#e0559a", "carrier_联通": "#4b8df0", "carrier_电信": "#9a6bf0",
            "mobile": "#e0559a", "unicom": "#4b8df0", "telecom": "#9a6bf0",
            "level_excellent": "#3ec28a", "level_good": "#9bd24a",
            "level_normal": "#f0c230", "level_poor": "#f28c3a", "level_bad": "#d93a56",
            "level_excellent_text": "#06281b", "level_normal_text": "#35280a",
            "level_poor_text": "#3a1d05", "level_bad_text": "#ffffff",
            "level_excellent_top": "#3ec28a", "level_normal_top": "#f0c230",
            "level_poor_top": "#f28c3a", "level_bad_top": "#d93a56",
            "level_excellent_bottom": "#27976a", "level_normal_bottom": "#c49a14",
            "level_poor_bottom": "#c86a1c", "level_bad_bottom": "#a82840",
            "quality_excellent": "#27976a", "quality_good": "#65a932",
            "quality_normal": "#c49a14", "quality_poor": "#c86a1c", "quality_bad": "#a82840",
        })
        for metric in ("cpu", "memory", "upload", "download"):
            raw[f"metric_{metric}_accent"] = raw["fg"]
        raw["card_top"] = raw["panel_top"]
        raw["card_bottom"] = raw["panel_bottom"]
        metadata_keys = {"latency_style"}
        colors = {
            key: value if key in metadata_keys else QColor(value)
            for key, value in raw.items()
        }
        level_defaults = {
            "level_excellent": "#36bc86", "level_good": "#8acb3f", "level_normal": "#f1c21b",
            "level_poor": "#f28a32", "level_bad": "#d92f50", "level_unknown": "#9aa0a8",
            "level_excellent_text": "#183c2c", "level_good_text": "#25341d",
            "level_normal_text": "#44370a", "level_poor_text": "#4c260d",
            "level_bad_text": "#ffffff", "level_unknown_text": "#6f6b63",
        }
        level_bottom_defaults = {
            "level_excellent_bottom": "#27986b", "level_good_bottom": "#65a932",
            "level_normal_bottom": "#c49a14", "level_poor_bottom": "#c86a1c",
            "level_bad_bottom": "#a82840", "level_unknown_bottom": "#c9c4b9",
        }
        for key, value in level_defaults.items():
            colors.setdefault(key, QColor(value))
        for key, value in level_bottom_defaults.items():
            colors.setdefault(key, QColor(value))
        colors["skin"] = theme_key
        colors["panel_gradient"] = self._gradient(colors["panel_top"], colors["panel_bottom"])
        colors["card_gradient"] = self._gradient(colors["card_top"], colors["card_bottom"])
        return colors

    def _apply_label_style(self, label, color, size, weight=QFont.Weight.Normal, align=None):
        label.setFont(_font(size, weight))
        label.setStyleSheet(f"color: {color.name()};")
        if align is not None:
            label.setAlignment(align)

    def _apply_theme(self):
        colors = self._colors()
        self._theme_colors = colors
        spec = SKIN_LAYOUTS.get(self.theme, SKIN_LAYOUTS["skin1"])
        self._apply_window_constraints(grow=getattr(self, "_initial_show_done", False))
        if self.opaque_fallback:
            palette = self.palette()
            palette.setColor(QPalette.ColorRole.Window, colors["panel_bottom"])
            palette.setColor(QPalette.ColorRole.Base, colors["panel_bottom"])
            self.setPalette(palette)
        self.panel.set_surface(colors, self.opacity_percent)
        self.toolbar.set_surface(colors)
        if hasattr(self, "header"):
            self.header.set_rule(_qcolor(colors["rule"], 185), not self.editing)
        self.cards_layout.setHorizontalSpacing(0)
        self.cards_layout.setVerticalSpacing(0)
        # 工具栏只在调整模式出现；锁定模式保持参考图中的纯净面板。
        self.toolbar.setVisible(self.editing)
        self._apply_label_style(self.title_label, colors["fg"], spec["title"], QFont.Weight.DemiBold)
        self._apply_label_style(self.summary_label, colors["muted"], 11, QFont.Weight.Normal)
        self._apply_label_style(self.mode_label, colors["muted"], 11, QFont.Weight.Normal,
                                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self._apply_label_style(self.header_hint, colors["muted"], 11, QFont.Weight.Normal, Qt.AlignmentFlag.AlignRight)
        self._apply_label_style(self.page_label, colors["fg"], 9, QFont.Weight.DemiBold)
        self._apply_label_style(self.view_label, colors["muted"], 9)
        self._apply_label_style(self.toolbar_hint, colors["subtle"], 9, QFont.Weight.Normal, Qt.AlignmentFlag.AlignRight)
        self._apply_label_style(self.footer_label, colors["muted"], 11)
        self._apply_label_style(self.footer_page_label, colors["muted"], 11)
        self._apply_label_style(self.empty_state, colors["muted"], 11)
        for button in (
            self.prev_button,
            self.next_button,
            self.pin_button,
            self.carousel_button,
            self.theme_button,
            self.opacity_down_button,
            self.opacity_up_button,
            self.settings_button,
        ):
            button.apply_theme(colors)
        spin_style = (
            "QSpinBox { color: %s; background: %s; border: 1px solid %s; border-radius: 7px; "
            "padding: 0 4px; }"
            "QSpinBox:focus { border-color: %s; }"
            "QSpinBox::up-button, QSpinBox::down-button { width: 12px; border: 0; }"
            % (
                colors["fg"].name(),
                _qcolor(colors["metric"], 190).name(QColor.NameFormat.HexArgb),
                _qcolor(colors["rule"], 180).name(QColor.NameFormat.HexArgb),
                _qcolor(colors["accent"], 210).name(QColor.NameFormat.HexArgb),
            )
        )
        self.refresh_spin.setStyleSheet(spin_style)
        self.carousel_spin.setStyleSheet(spin_style)
        if self._card_skin == self.theme:
            for card in self._cards:
                card.update_item(card.item, self._card_mode, colors, card.item["id"] in self.selected_ids)
        self._update_header_labels()
        self._refresh_visual_size()

    def _apply_window_constraints(self, grow=False):
        """让皮肤切换和旧版保存尺寸不会把参考稿内容压扁。"""
        spec = SKIN_LAYOUTS.get(self.theme, SKIN_LAYOUTS["skin1"])
        min_width, min_height = (int(value) for value in spec.get("window_min", (self.MIN_WIDTH, self.MIN_HEIGHT)))
        # 保留原有 320×300 的可缩小能力；用户手动缩小时由响应式布局
        # 减少信息，而不是让 Qt 的硬最小尺寸阻止调整。
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        # 换肤/调透明度不擅自恢复大尺寸；过矮时由摘要与滚动兜底。

    def _update_header_labels(self):
        online = sum(x["status"] == "online" for x in self.samples)
        offline = sum(x["status"] == "offline" for x in self.samples)
        stale = sum(x["status"] == "stale" for x in self.samples)
        total = len(self.samples)
        colors = getattr(self, "_theme_colors", None) or self._colors()
        if self.live_enabled and not total:
            message = {
                "loading": "正在读取节点…", "ok": "数据已连接 · 暂无节点",
            }.get(self.source_state, "连接中断 · 尚未获取数据")
            self.summary_label.setText(f'<span style="color:{colors["muted"].name()};">{message}</span>')
            self.summary_label.set_states()
        else:
            # 参考稿把总数放在底部页码，标题摘要只保留三类状态，
            # 否则在窄宽度或 Windows 缩放下会把“数据过期”挤成省略号。
            self.summary_label.setText(
                f'<span style="color:{colors["online"].name()}; font-size:14px;">●</span> {online} 在线'
                f'&nbsp;&nbsp;<span style="color:{colors["muted"].name()}; font-size:14px;">○</span> {offline} 离线'
                f'&nbsp;&nbsp;<span style="color:{colors["stale"].name()}; font-size:14px;">◐</span> {stale} 数据过期'
            )
            self.summary_label.set_states((online, offline, stale), colors)
        if self.editing:
            self.mode_label.setText("调整中 · 可拖动")
            source_color = colors["accent"]
        elif not self.live_enabled:
            self.mode_label.setText(f"演示数据 · {self.last_update_text}更新")
            source_color = colors["muted"]
        elif self.source_state == "loading":
            self.mode_label.setText("实时数据 · 读取中")
            source_color = colors["muted"]
        elif self.source_state == "cached":
            self.mode_label.setText("数据过期 · 正在连接")
            source_color = colors["stale"]
        elif self.source_state == "error":
            self.mode_label.setText("数据过期 · 保留上次" if total else "连接中断 · 暂无数据")
            source_color = colors["stale"]
        else:
            self.mode_label.setText(f"实时数据 · {self.last_update_text}更新")
            source_color = colors["online"]
        source_style = f"color: {source_color.name()}; padding-bottom: 3px;"
        if self.mode_label.styleSheet() != source_style:
            self.mode_label.setStyleSheet(source_style)
        if self.source_state == "error":
            self.mode_label.setToolTip(
                f"{self.source_error}\n上次更新：{self.last_update_text}\n{self._next_refresh_ms // 1000} 秒后重试"
            )
        else:
            self.mode_label.setToolTip(f"上次更新：{self.last_update_text}")
        self.header_hint.setText("Esc 退出调整" if self.editing else f"{self.shortcuts['edit']} 调整")
        if self._hotkey_failures:
            failed_keys = ", ".join(sorted(self._hotkey_failures))
            self.header_hint.setToolTip(f"快捷键未注册（可能被其他程序占用）：{failed_keys}")
            hotkey_warning = f" · {len(self._hotkey_failures)} 个快捷键冲突"
        else:
            self.header_hint.setToolTip(f"{self.shortcuts['prev']} / {self.shortcuts['next']} 翻页；"
                                       f"{self.shortcuts['settings']} 设置；Ctrl+Alt+1–9 固定节点；Ctrl+Alt+0 取消固定")
            hotkey_warning = ""
        shown_total = len(self._items())
        if shown_total and self._page_ranges:
            start_index, end_index = self._page_ranges[min(self.page_index, len(self._page_ranges) - 1)]
            start = start_index + 1
            end = min(shown_total, end_index)
        else:
            start = end = 0
        self.page_label.setText(f"{start}–{end} / {shown_total}")
        grouping = "分组" if self.group_mode else "平铺"
        sort_text = {"name": "名称", "cpu": "CPU", "memory": "内存", "latency": "延迟"}[self.sort_mode]
        page_lock_text = f" · 固定第 {self.page_index + 1} 页" if self.page_pinned else ""
        self.view_label.setText(f"{grouping} · 按{sort_text}{page_lock_text}")
        if hasattr(self, "action_row"):
            self.action_row.setVisible(self.editing)
        if hasattr(self, "header") and hasattr(self, "_theme_colors"):
            self.header.set_rule(_qcolor(self._theme_colors["rule"], 185), not self.editing)
            # 调整模式把空间让给可操作控件，操作说明保留在底部状态栏，
            # 避免窄窗口下按钮和秒数输入框被布局压缩或互相覆盖。
            self.toolbar_hint.setVisible(not self.editing)
            self.toolbar.setVisible(self.editing)
            self.prev_button.setEnabled(self.page_count > 1)
            self.next_button.setEnabled(self.page_count > 1)
            self.pin_button.setText("解" if self.page_pinned else "锁")
            self.pin_button.setToolTip("取消固定节点集合" if self.page_pinned else "固定当前节点（排序变化不替换；缩小时在集合内翻页）")
            self.carousel_button.setText("轮" if self.carousel_enabled else "停")
            self.carousel_button.setToolTip(
                "关闭自动轮播" if self.carousel_enabled else "开启自动轮播"
            )
            self.theme_button.setToolTip(f"切换皮肤（当前：{SKIN_NAMES.get(self.theme, self.theme)}）")
            for spin, value in (
                (self.refresh_spin, self.refresh_interval_ms // 1000),
                (self.carousel_spin, self.carousel_interval_ms // 1000),
            ):
                spin.blockSignals(True)
                spin.setValue(value)
                spin.blockSignals(False)
        narrow_toolbar = self.width() < 360
        self.refresh_spin.setVisible(not narrow_toolbar and self.editing)
        self.carousel_spin.setVisible(self.width() >= 500 and self.editing)
        if self.width() < 360:
            self.toolbar_hint.setText("P/N 翻页 · 1–9 固定 · 0 取消" + hotkey_warning)
        elif self.width() < 500:
            self.toolbar_hint.setText("P/N 翻页 · 1–9 固定 · 0 取消" + hotkey_warning)
        else:
            self.toolbar_hint.setText("P/N 翻页 · 1–9 固定 · 0 取消" + hotkey_warning)
        self.footer_page_label.clear()
        self.footer_page_label.setVisible(False)
        if not self.editing:
            if self.live_enabled and not total:
                footer = {"loading": "正在读取节点…", "ok": "数据已连接 · 暂无节点"}.get(
                    self.source_state, "连接中断 · 尚未获取数据"
                )
            else:
                footer = (
                    f'<span style="color:{colors["level_excellent"].name()};">■</span> 优秀&nbsp;&nbsp;'
                    f'<span style="color:{colors["level_good"].name()};">■</span> 很好&nbsp;&nbsp;'
                    f'<span style="color:{colors["level_normal"].name()};">■</span> 一般&nbsp;&nbsp;'
                    f'<span style="color:{colors["level_poor"].name()};">■</span> 较差&nbsp;&nbsp;'
                    f'<span style="color:{colors["level_bad"].name()};">■</span> 差'
                )
                self.footer_page_label.setText(f"{start}–{end} / {shown_total} · 按{sort_text}")
                self.footer_page_label.setVisible(True)
                if self.page_pinned:
                    self.footer_page_label.setText(self.footer_page_label.text() + f" · 固定{self.page_index + 1}")
                if self.live_enabled and self.source_state in {"error", "cached"}:
                    connection_note = "正在连接" if self.source_state == "cached" else f"{self._next_refresh_ms // 1000} 秒后重试"
                    footer = f"数据过期 · 上次 {self.last_update_text} · {connection_note}"
                    if self.page_pinned:
                        footer += f" · 固定第 {self.page_index + 1} 页"
                    self.footer_page_label.setVisible(False)
                elif self.width() < 380:
                    self.footer_page_label.setText(f"{start}–{end}/{shown_total}")
            self.footer_label.setTextFormat(Qt.TextFormat.RichText)
        else:
            footer = ("调整中 · 拖动/拉伸 · F2 设置" if self.width() < 500 else
                      f"调整中 · Ctrl+点击选节点 · P/N 翻页 · F2 设置 · 背景 {self.opacity_percent}%")
            self.footer_label.setTextFormat(Qt.TextFormat.PlainText)
        self.footer_label.setText(footer)
        if not self.editing and self.footer_page_label.isVisible():
            # 空间不足时先省去排序描述，固定页状态不能因窄窗而消失。
            lock_note = f" · 固定{self.page_index + 1}" if self.page_pinned else ""
            full_page_text = f"{start}–{end} / {shown_total} · 按{sort_text}{lock_note}"
            page_variants = (full_page_text, f"{start}–{end}/{shown_total}{lock_note}",
                             f"{self.page_index + 1}/{self.page_count}{lock_note}")
            remaining_width = self.footer_row.width() - self.footer_label.sizeHint().width() - 8
            metrics = QFontMetrics(self.footer_page_label.font())
            self.footer_page_label.setText(next(
                (value for value in page_variants if metrics.horizontalAdvance(value) + 2 <= remaining_width),
                page_variants[-1],
            ))
        if hasattr(self, "carousel_timer"):
            should_run = (self.carousel_enabled and not self.page_pinned
                          and not self.hidden and not self.editing and self._settings_dialog is None
                          and not self._close_requested)
            if self.carousel_timer.isActive() != should_run:
                self._sync_carousel_timer()

    def _mode_for_width(self):
        card_width = self._reference_content_width()
        if card_width < 320:
            return "narrow"
        # 440px 是设计稿的逻辑基准宽度；在这个尺寸下应使用完整字号和
        # 完整间距，不能被旧版 500px 阈值误判成紧凑模式。
        if card_width < 400:
            return "compact"
        return "wide"

    def _column_count(self):
        if self.layout_mode == "single":
            return 1
        # 单卡保持设计稿的可读宽度，足够宽才增加列，最多3列。
        return max(1, min(3, int((self._available_card_width() + 16) // 420)))

    def _available_card_width(self):
        return max(1, self.cards_scroll.viewport().width())

    def _estimated_card_height(self, mode):
        return NodeCard.reference_height_for(self._reference_content_width(), self.theme, "online",
                                             compact=self._compact_vertical)

    def _reference_content_width(self):
        if hasattr(self, "cards_scroll"):
            columns = self._column_count()
            return max(1, (self._available_card_width() - 16 * (columns - 1)) // columns)
        return max(240, self.width() - 48)

    def _reference_pagination_scale(self):
        return 1.0

    def _estimated_item_height(self, item, mode, online_height=None):
        return NodeCard.reference_height_for(self._reference_content_width(), self.theme,
                                             item.get("status"), item, self._compact_vertical)

    def _layout(self, items=None):
        mode = self._mode_for_width()
        container_height = self.cards_scroll.viewport().height()
        chrome = 104 if mode != "narrow" else 98
        available = container_height if container_height > 0 else max(1, self.height() - chrome)
        full_height = NodeCard.reference_height_for(self._reference_content_width(), self.theme, "online")
        self._compact_vertical = available < full_height
        card_height = self._estimated_card_height(mode)
        columns = self._column_count()
        if items is None:
            items = self._items()
        # 参考稿中的离线/过期节点是摘要高度，不能按在线节点的高度
        # 把它们一起算成整张卡，否则底部会留下大块空白。
        self._page_ranges = []
        if items:
            start = 0
            while start < len(items):
                end = start
                used = 0
                while end < len(items):
                    row_end = min(len(items), end + columns)
                    if self.max_per_page:
                        row_end = min(row_end, start + self.max_per_page)
                    if row_end <= end:
                        break
                    row_height = max(self._estimated_item_height(item, mode, card_height) for item in items[end:row_end])
                    if end > start and used + row_height > available:
                        break
                    used += row_height
                    end = row_end
                self._page_ranges.append((start, max(start + 1, end)))
                start = max(start + 1, end)
        if not self._page_ranges:
            self._page_ranges = [(0, 0)]
        self.page_count = len(self._page_ranges)
        if items:
            anchor_index = next((index for index, item in enumerate(items) if item["id"] == self._page_anchor), None)
            # 只有显式翻页才环绕；刷新/状态/容量变化保留当前首节点锚点。
            if anchor_index is not None:
                self.page_index = next(index for index, (start, end) in enumerate(self._page_ranges)
                                       if start <= anchor_index < end)
            else:
                self.page_index = min(self.page_index, self.page_count - 1)
            if self.source_state not in {"loading", "cached"}:
                self._restore_page_pending = False
            if not self._restore_page_pending:
                start, end = self._page_ranges[self.page_index]
                self._page_anchor = items[start]["id"] if start < end else ""
        elif not self._restore_page_pending:
            self.page_index = 0
        display_page_index = min(self.page_index, self.page_count - 1)
        page_start, page_end = self._page_ranges[display_page_index]
        page = items[page_start:page_end]
        self.page_size = max(1, page_end - page_start)
        rects = []
        gap = 16 if columns > 1 else 0
        card_width = self._reference_content_width()
        y = float(chrome)
        used = 0
        for row_start in range(0, len(page), columns):
            row_items = page[row_start:row_start + columns]
            for col, item in enumerate(row_items):
                item_height = self._estimated_item_height(item, mode, card_height)
                rects.append((QRectF(22 + col * (card_width + gap), y + used, card_width, item_height), item))
            used += max(self._estimated_item_height(item, mode, card_height) for item in row_items)
        self._page_content_height = used
        return mode, rects, len(items)

    def _items(self):
        items = [item for item in self.samples if self.show_all_nodes or item["id"] in self.selected_ids]
        if self.page_pinned and self.pinned_node_ids:
            by_id = {item["id"]: item for item in items}
            return [by_id[node_id] for node_id in self.pinned_node_ids if node_id in by_id]
        # 视觉回归使用设计稿中固定的演示顺序（荷兰、香港、洛杉矶）；
        # 只在测试夹具显式打开时生效，真实数据和用户排序不受影响。
        if getattr(self, "_force_reference_order", False) and not self.live_enabled:
            demo_order = {item["id"]: index for index, item in enumerate(self.samples)}
            key = lambda item: demo_order.get(item["id"], 99999)
        elif self.sort_mode == "cpu":
            key = lambda item: -(item["cpu"] if isinstance(item["cpu"], (int, float)) else -1)
        elif self.sort_mode == "memory":
            key = lambda item: -(item["memory"] if isinstance(item["memory"], (int, float)) else -1)
        elif self.sort_mode == "latency":
            def key(item):
                values = [value for value in item.get("latency", {}).values()
                          if KomariClient._number(value) is not None and value > 0]
                return sum(values) / len(values) if values else float("inf")
        else:
            if not self.live_enabled:
                demo_order = {item["id"]: index for index, item in enumerate(self.samples)}
                key = lambda item: demo_order.get(item["id"], 99999)
            else:
                key = lambda item: item["name"]
        return sorted(items, key=(lambda item: (item["region"], key(item))) if self.group_mode else key)

    def _refresh_cards(self, force=False):
        items = self._items()
        mode, _, total = self._layout(items)
        page_start, page_end = self._page_ranges[min(self.page_index, self.page_count - 1)]
        page = items[page_start:page_end]
        if self.page_pinned and not self.pinned_node_ids and page and self.source_state not in {"loading", "cached"}:
            self.pinned_node_ids = [item["id"] for item in page]
            self.page_index = 0
            self._page_anchor = self.pinned_node_ids[0]
            items = self._items()
            mode, _, total = self._layout(items)
            start, end = self._page_ranges[0]
            page = items[start:end]
        self.empty_state.setGeometry(self.cards_scroll.viewport().rect())
        self.empty_state.setText("未选择节点\n打开设置 → 节点，勾选要显示的 VPS" if not self.show_all_nodes and not self.selected_ids
                                 else "固定的节点暂不可用\n可在设置中取消固定" if self.page_pinned and self.pinned_node_ids
                                 else "正在读取节点…" if self.source_state == "loading" else "暂无可显示节点")
        self.empty_state.setVisible(not bool(page))
        if not page:
            self.empty_state.raise_()
        ids = tuple(item["id"] for item in page)
        columns = self._column_count()
        skin = self._theme_colors.get("skin")
        if (ids == self._card_ids and mode == self._card_mode
                and columns == self._card_columns and skin == self._card_skin):
            geometry_changed = False
            for card, item in zip(self._cards, page):
                # JSON 每次返回新的字典，不能继续用 card.item 指向的旧一轮数据。
                old_geometry = (card.height(), card.minimumHeight(), card.maximumHeight(), card.status_key,
                                card.compact_vertical)
                card.compact_vertical = self._compact_vertical
                card.update_item(item, mode, self._theme_colors, item["id"] in self.selected_ids)
                new_geometry = (card.height(), card.minimumHeight(), card.maximumHeight(), card.status_key,
                                card.compact_vertical)
                geometry_changed |= old_geometry != new_geometry
            if geometry_changed:
                self._fit_card_grid()
                self.cards_layout.invalidate()
                self.cards_layout.activate()
                self._capture_card_rects()
            if force:
                self._refresh_visual_size()
            self._update_header_labels()
            return
        self._card_ids = ids
        self._card_mode = mode
        self._card_columns = columns
        previous = {card.item["id"]: card for card in self._cards} if skin == self._card_skin else {}
        self._card_skin = skin
        old_cards = self._cards
        self._cards = []
        while self.cards_layout.count():
            self.cards_layout.takeAt(0)
        retained_ids = set(ids)
        for card in old_cards:
            if card.item["id"] not in retained_ids or card.item["id"] not in previous:
                card.hide()
                card.removeEventFilter(self)
                card.deleteLater()
        for column in range(3):
            self.cards_layout.setColumnStretch(column, 1 if column < columns else 0)
            self.cards_layout.setColumnMinimumWidth(column, 0)
        self.cards_layout.setHorizontalSpacing(16 if columns > 1 else 0)
        for index, item in enumerate(page):
            card = previous.get(item["id"])
            if card is None:
                card = NodeCard(item, self._theme_colors, mode, item["id"] in self.selected_ids, self.cards_container)
                card.install_input_filter(self)
            else:
                card.compact_vertical = self._compact_vertical
                card.update_item(item, mode, self._theme_colors, item["id"] in self.selected_ids)
            # 新卡片在 Qt 布局分配宽度前默认只有260px；先按容器宽度定高，
            # 避免窄版初始高度把宽屏分页预算撑大并反复销毁/重建同一张卡。
            if card.reference_paint:
                card.compact_vertical = self._compact_vertical
                height = NodeCard.reference_height_for(self._reference_content_width(), self.theme,
                                                       card.status_key, item, self._compact_vertical)
                card.resize(self._reference_content_width(), height)
                card.setFixedHeight(height)
            self._cards.append(card)
            row, col = divmod(index, columns)
            self.cards_layout.addWidget(card, row, col)
        self._fit_card_grid()
        self.cards_layout.invalidate()
        self.cards_layout.activate()
        self._refresh_visual_size()
        self._update_header_labels()
        # 卡片真实 sizeHint 只有在布局激活后才可得；再走一帧重算，
        # 避免首帧按旧预算只显示两张、随后留下大片空白。
        QTimer.singleShot(0, self._settle_card_page)

    def _settle_card_page(self):
        if self._close_requested or not self._cards:
            return
        items = self._items()
        mode, _, _ = self._layout(items)
        start, end = self._page_ranges[min(self.page_index, self.page_count - 1)]
        ids = tuple(item["id"] for item in items[start:end])
        if (ids != self._card_ids or mode != self._card_mode or self._column_count() != self._card_columns
                or any(card.compact_vertical != self._compact_vertical for card in self._cards)):
            self._refresh_cards(force=True)
            return
        self._capture_card_rects()
        self._update_header_labels()

    def _fit_card_grid(self):
        # 仅在高度极端不足时启用滚动兜底；正常窗口保持设计稿的无滚动条外观。
        available = max(1, self.cards_scroll.viewport().height())
        self.cards_container.setMinimumHeight(self._page_content_height)
        self.cards_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded if self._page_content_height > available
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        columns = self._column_count()
        for row in range(max(getattr(self, "_grid_rows", 0), (len(self._cards) + columns - 1) // columns)):
            row_cards = self._cards[row * columns:(row + 1) * columns]
            self.cards_layout.setRowMinimumHeight(row, max((card.height() for card in row_cards), default=0))
            self.cards_layout.setRowStretch(row, 0)
        self._grid_rows = (len(self._cards) + columns - 1) // columns

    def _capture_card_rects(self):
        self._layout_rects = []
        for card in self._cards:
            local = self.cards_container.mapTo(self, card.pos())
            self._layout_rects.append((QRectF(local.x(), local.y(), card.width(), card.height()), card.item))

    def _refresh_visual_size(self):
        self._apply_responsive_text()
        self._capture_card_rects()
        self.update()

    def _apply_responsive_text(self):
        mode = self._mode_for_width()
        spec = SKIN_LAYOUTS.get(self.theme, SKIN_LAYOUTS["skin1"])
        narrow = mode == "narrow"
        self.title_label.setFont(_font(max(14, int(spec["title"]) - (1 if narrow else 0)), QFont.Weight.DemiBold))
        self.summary_label.setFont(_font(11))
        self.header_hint.setFont(_font(11))
        self.mode_label.setFont(_font(11))
        self.header_hint.setVisible(self.width() >= 380 or self.editing)
        narrow = self.width() < 360
        compact = mode != "wide"
        self.theme_button.setVisible(not narrow)
        self.settings_button.setVisible(True)
        self.view_label.setVisible(self.width() >= 700)
        self.page_label.setVisible(self.width() >= 500)
        self.opacity_down_button.setVisible(not compact)
        self.opacity_up_button.setVisible(not compact)
        if hasattr(self, "refresh_spin"):
            self.refresh_spin.setVisible(not narrow and self.editing)
            self.carousel_spin.setVisible(self.width() >= 500 and self.editing)
        left, top, right, bottom = tuple(spec.get("panel_margins", (16, 14, 16, 12)))
        if mode == "narrow":
            left = right = max(11, left - 4)
            top = max(10, top - 2)
            bottom = max(8, bottom - 2)
        self.panel_layout.setContentsMargins(left, top, right, bottom)

    def _queue_refresh(self):
        if self._refresh_scheduled:
            return
        self._refresh_scheduled = True

        def refresh():
            self._refresh_scheduled = False
            self._refresh_cards(force=True)

        QTimer.singleShot(0, refresh)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._initial_show_done:
            self._initial_show_done = True
            self._restore_geometry()
            QTimer.singleShot(0, self._after_show)

    def _after_show(self):
        self._register_hotkeys()
        self._create_tray()
        self._watch_screens()
        self._set_locked(True)
        self._place_desktop()
        self._queue_refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._queue_refresh()

    def closeEvent(self, event):
        self._close_requested = True
        if hasattr(self, "timer"):
            self.timer.stop()
        self.carousel_timer.stop()
        if self._live_thread and self._live_thread.isRunning():
            # 网络请求在工作线程中执行，不能在窗口析构时直接销毁 QThread。
            # 先隐藏窗口并等待线程自然结束，避免退出时出现
            # ``QThread: Destroyed while thread is still running``。
            self._live_worker.client.cancel()
            self._live_thread.quit()
            event.ignore()
            self.hide()
            return
        self._unregister_hotkeys()
        if self.tray is not None:
            self.tray.hide()
        if self._settings_dialog is not None:
            self._settings_dialog.close()
        self._save_settings()
        QApplication.instance().removeNativeEventFilter(self.native_filter)
        super().closeEvent(event)

    def _shutdown_live_thread(self):
        self._close_requested = True
        self.timer.stop()
        self.carousel_timer.stop()
        if self._live_thread and self._live_thread.isRunning():
            self._live_worker.client.cancel()
            self._live_thread.quit()
            # 常规退出在 closeEvent 异步等待；外部 app.quit 也须完成工作线程收尾。
            self._live_thread.wait((self._live_worker.client.timeout * 2 + 1) * 1000)

    def _save_settings(self):
        self.settings.setValue("settingsVersion", SETTINGS_VERSION)
        self.settings.setValue("geometry", self.geometry())
        self.settings.setValue("windowOpacity", self.opacity_percent)
        self.settings.setValue("theme", self.theme)
        self.settings.setValue("komariUrl", self.komari_url)
        self.settings.setValue("refreshSeconds", self.refresh_interval_ms // 1000)
        self.settings.setValue("carouselSeconds", self.carousel_interval_ms // 1000)
        self.settings.setValue("sortMode", self.sort_mode)
        self.settings.setValue("groupMode", self.group_mode)
        self.settings.setValue("carouselEnabled", self.carousel_enabled)
        self.settings.setValue("pagePinned", self.page_pinned)
        self.settings.setValue("pageIndex", self._pending_page_index if self._restore_page_pending else self.page_index)
        self.settings.setValue("pageAnchor", self._pending_page_anchor if self._restore_page_pending else self._page_anchor)
        self.settings.setValue("pinnedNodeIds", json.dumps(self.pinned_node_ids, ensure_ascii=False))
        self.settings.setValue("showAllNodes", self.show_all_nodes)
        self.settings.setValue("layerMode", self.layer_mode)
        self.settings.setValue("clickThrough", self.click_through)
        self.settings.setValue("layoutMode", self.layout_mode)
        self.settings.setValue("maxPerPage", self.max_per_page)
        self.settings.setValue("shortcuts", json.dumps(self.shortcuts, ensure_ascii=False))
        self.settings.setValue("selectedIds", json.dumps(sorted(self.selected_ids), ensure_ascii=False))
        self.settings.sync()

    def _restore_geometry(self):
        saved = self.settings.value("geometry")
        spec = SKIN_LAYOUTS.get(self.theme, SKIN_LAYOUTS["skin1"])
        min_width, min_height = (int(value) for value in spec.get("window_min", (self.MIN_WIDTH, self.MIN_HEIGHT)))
        preferred_width, preferred_height = (
            int(value) for value in spec.get("window_preferred", (min_width, min_height))
        )
        self.setMinimumSize(self.MIN_WIDTH, self.MIN_HEIGHT)
        migrate_legacy_size = (
            getattr(self, "_geometry_reference_migration", False)
            and isinstance(saved, QRect)
            and ((saved.width() <= 400 and saved.height() <= 540)
                 or (saved.width(), saved.height()) in {(440, 540), (450, 540)})
        )
        if (
            isinstance(saved, QRect)
            and saved.width() >= self.MIN_WIDTH
            and saved.height() >= self.MIN_HEIGHT
            and not migrate_legacy_size
        ):
            areas = [screen.availableGeometry() for screen in QApplication.screens()]
            screen = QApplication.screenAt(QCursor.pos()) or self.screen() or QApplication.primaryScreen()
            target = max(areas, key=lambda area: area.intersected(saved).width() * area.intersected(saved).height(),
                         default=None)
            if target is not None and not target.intersects(saved):
                target = None
            target = target or (screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080))
            self.setGeometry(fit_geometry(saved, target))
            return
        # 首次启动跟随鼠标所在屏幕，避免双屏时默认落到用户当前未查看的主屏。
        screen = QApplication.screenAt(QCursor.pos()) or self.screen() or QApplication.primaryScreen()
        work = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        self.resize(min(max(preferred_width, min_width), work.width()),
                    min(max(preferred_height, min_height), work.height()))
        self.move(work.right() - self.width() - 24, work.top() + 24)
        if migrate_legacy_size:
            self.settings.setValue("geometry", self.geometry())
            self.settings.sync()
            self._geometry_reference_migration = False

    def _register_hotkeys(self):
        if not IS_WINDOWS:
            return
        hwnd = int(self.winId())
        self._hotkey_registered.clear()
        self._hotkey_failures.clear()
        hotkeys = [
            (HOTKEY_EDIT, self.shortcuts["edit"]),
            (HOTKEY_HIDE, self.shortcuts["hide"]),
            (HOTKEY_PREV, self.shortcuts["prev"]),
            (HOTKEY_NEXT, self.shortcuts["next"]),
            (HOTKEY_SETTINGS, self.shortcuts["settings"]),
            (HOTKEY_QUIT, self.shortcuts["quit"]),
            (HOTKEY_PAGE_RESET, "Ctrl+Alt+0"),
        ]
        hotkeys.extend((HOTKEY_PAGE_BASE + page_number - 1, f"Ctrl+Alt+{page_number}") for page_number in range(1, 10))
        for hotkey_id, key in hotkeys:
            _user32.UnregisterHotKey(hwnd, hotkey_id)
            modifiers, virtual_key = native_shortcut(key)
            if _user32.RegisterHotKey(hwnd, hotkey_id, modifiers | 0x4000, virtual_key):
                self._hotkey_registered.add(hotkey_id)
            else:
                self._hotkey_failures[key] = ctypes.get_last_error()
        if hasattr(self, "header_hint"):
            self._update_header_labels()

    def _unregister_hotkeys(self):
        if IS_WINDOWS:
            hwnd = int(self.winId())
            for hotkey_id in tuple(self._hotkey_registered):
                _user32.UnregisterHotKey(hwnd, hotkey_id)
            self._hotkey_registered.clear()

    def _style_update(self, add=0, remove=0):
        if not IS_WINDOWS:
            return
        hwnd = int(self.winId())
        old = int(_user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)) & 0xFFFFFFFFFFFFFFFF
        new = (old | add) & ~remove
        if new == old:
            return
        ctypes.set_last_error(0)
        _user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, ctypes.c_ssize_t(new))
        if ctypes.get_last_error():
            return
        _user32.SetWindowPos(
            hwnd,
            None,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER | SWP_FRAMECHANGED,
        )

    def _install_mouse_filters(self):
        if self._panel_filters_installed:
            return
        self.panel.installEventFilter(self)
        for child in self.panel.findChildren(QWidget):
            child.installEventFilter(self)
        self._panel_filters_installed = True

    def _set_locked(self, locked):
        self.locked = bool(locked)
        self.editing = not self.locked
        if IS_WINDOWS:
            if self.locked:
                self._style_update(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | (WS_EX_TRANSPARENT if self.click_through else 0),
                                   WS_EX_APPWINDOW | (0 if self.click_through else WS_EX_TRANSPARENT))
            else:
                self._style_update(WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_APPWINDOW)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, self.locked and self.click_through)
        if hasattr(self, "action_row"):
            self.action_row.setVisible(self.editing)
        self._sync_carousel_timer()
        self._update_header_labels()
        self.update()

    def toggle_editing(self):
        if self.hidden:
            self.toggle_hidden()
        if self.locked:
            self._set_locked(False)
            self._place_editing()
            self._install_mouse_filters()
        else:
            self._save_settings()
            self.releaseMouse()
            self._set_locked(True)
            self._place_desktop()

    def toggle_hidden(self):
        if self.hidden:
            self.hidden = False
            self.show()
            self._clamp_to_screens()
            self._set_locked(True)
            self._place_desktop()
            if self._view_dirty:
                self._view_dirty = False
                self._refresh_cards()
        else:
            if not self.locked:
                self._set_locked(True)
            self._save_settings()
            self.hidden = True
            self.hide()
        self._sync_carousel_timer()
        if self.live_enabled and not self._live_busy:
            if not self.hidden and time.monotonic() - self._last_live_success_at >= self.refresh_interval_ms / 1000:
                self._request_live_refresh()
            else:
                self.timer.start(max(60_000, self._next_refresh_ms) if self.hidden else self._next_refresh_ms)

    def _desktop_anchor(self):
        if not IS_WINDOWS:
            return 0
        shell = _user32.GetShellWindow()
        if not shell:
            # 某些替代桌面、远程会话或定制 Shell 不提供 GetShellWindow。
            # HWND_BOTTOM 可能落到壁纸合成层下面，导致进程存在但完全不可见；
            # HWND_TOP 不激活窗口，普通工作窗口获得焦点后仍可自然覆盖它。
            return HWND_TOP
        pid_shell = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(shell, ctypes.byref(pid_shell))
        found = []
        enum_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def locate(hwnd, _):
            pid = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value != pid_shell.value:
                return True
            name = ctypes.create_unicode_buffer(128)
            _user32.GetClassNameW(hwnd, name, len(name))
            if name.value in ("Progman", "WorkerW") and _user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None):
                found.append(hwnd)
                return False
            return True

        _user32.EnumWindows(enum_type(locate), 0)
        return found[0] if found else shell

    def set_layer_mode(self, mode):
        if mode not in {"desktop", "normal", "topmost"}:
            raise ValueError("图层模式无效")
        self.layer_mode = mode
        if not self.editing:
            self._place_desktop()
        self._save_settings()

    def _place_desktop(self):
        # 只在启动、显式切换/恢复时调整一次层级；数据刷新和桌面点击不抢层。
        # 桌面后层仍是顶级窗口，不重挂WorkerW以避免已知不可见/闪烁回归。
        if IS_WINDOWS and self.isVisible():
            hwnd = int(self.winId())
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER | SWP_SHOWWINDOW
            target = HWND_TOPMOST if self.layer_mode == "topmost" else HWND_NOTOPMOST
            if not _user32.SetWindowPos(hwnd, target, 0, 0, 0, 0, flags):
                self._layer_error = f"Windows图层切换失败：{ctypes.get_last_error()}"
                return False
            if self.layer_mode == "desktop":
                anchor = self._desktop_anchor()
                if anchor and anchor != hwnd:
                    previous = _user32.GetWindow(anchor, GW_HWNDPREV)
                    if int(previous or 0) != hwnd:
                        if not _user32.SetWindowPos(hwnd, previous or HWND_TOP, 0, 0, 0, 0, flags):
                            self._layer_error = f"Windows桌面后层放置失败：{ctypes.get_last_error()}"
                            return False
            self._layer_error = ""
            self.update()
        return True

    def _place_editing(self):
        if IS_WINDOWS:
            _user32.SetWindowPos(
                int(self.winId()),
                HWND_TOPMOST,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER,
            )
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _tick(self):
        self.phase += 1
        for item in self.samples:
            if item["status"] != "online":
                continue
            item["cpu"] = max(0.1, min(98.0, item["cpu"] + math.sin(self.phase * 0.7 + len(item["id"])) * 0.35))
            item["memory"] = max(0.1, min(98.0, item["memory"] + math.sin(self.phase * 0.3 + len(item["name"])) * 0.12))
            item["upload"] = max(0.0, item["upload"] + math.sin(self.phase * 0.5 + 1) * 0.45)
            item["download"] = max(0.0, item["download"] + math.cos(self.phase * 0.4 + 2) * 0.60)
        self.last_update_text = "刚刚"
        for card in self._cards:
            card.update_item(card.item, self._card_mode, self._theme_colors, card.item["id"] in self.selected_ids)
        self._update_header_labels()
        self.update()

    def _toggle_selected(self, item):
        if not item:
            return
        if self.show_all_nodes:
            self.selected_ids = {entry["id"] for entry in self.samples}
            self.show_all_nodes = False
        if item["id"] in self.selected_ids and len(self.selected_ids) > 1:
            self.selected_ids.remove(item["id"])
        else:
            self.selected_ids.add(item["id"])
        self.page_index = 0
        self._page_anchor = ""
        self.page_pinned = False
        self.pinned_node_ids = []
        self._save_settings()
        self._refresh_cards(force=True)

    def _node_at(self, point):
        return next((item for rect, item in self._layout_rects if rect.contains(point)), None)

    def _edge(self, point):
        if not self.editing:
            return None
        n = 10
        h = "left" if point.x() <= n else "right" if point.x() >= self.width() - n else ""
        v = "top" if point.y() <= n else "bottom" if point.y() >= self.height() - n else ""
        return f"{v}-{h}" if h and v else h or v or None

    def _begin_edit_mouse(self, global_point, modifiers=Qt.KeyboardModifier.NoModifier):
        if not self.editing:
            return
        point = self.mapFromGlobal(global_point)
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            self._toggle_selected(self._node_at(point))
            return
        self.resize_edge = self._edge(point)
        self.resize_origin = global_point
        self.resize_geometry = self.geometry()
        if not self.resize_edge:
            self.drag_origin, self.drag_geometry = global_point, self.geometry()
        self.grabMouse()
        self._edit_mouse_grabbed = True

    def _move_edit_mouse(self, global_point):
        if not self.editing:
            return
        point = self.mapFromGlobal(global_point)
        if self.resize_edge:
            self._resize_to(global_point)
        elif self.drag_origin is not None:
            self.setGeometry(self.drag_geometry.translated(global_point - self.drag_origin))
        else:
            cursors = {
                "top": Qt.CursorShape.SizeVerCursor,
                "bottom": Qt.CursorShape.SizeVerCursor,
                "left": Qt.CursorShape.SizeHorCursor,
                "right": Qt.CursorShape.SizeHorCursor,
                "top-left": Qt.CursorShape.SizeFDiagCursor,
                "bottom-right": Qt.CursorShape.SizeFDiagCursor,
                "top-right": Qt.CursorShape.SizeBDiagCursor,
                "bottom-left": Qt.CursorShape.SizeBDiagCursor,
            }
            self.setCursor(cursors.get(self._edge(point), Qt.CursorShape.OpenHandCursor))

    def _end_edit_mouse(self):
        if self._edit_mouse_grabbed:
            self.releaseMouse()
        self._edit_mouse_grabbed = False
        self._clamp_to_screens()
        self._save_settings()
        self.drag_origin = self.drag_geometry = None
        self.resize_origin = self.resize_geometry = self.resize_edge = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    @staticmethod
    def _is_interactive_control(widget):
        current = widget
        while current is not None:
            if current.property("interactive_control"):
                return True
            current = current.parentWidget()
        return False

    def eventFilter(self, watched, event):
        if self.editing and event.type() == QEvent.Type.Wheel and self.cards_scroll.verticalScrollBar().maximum() > 0:
            bar = self.cards_scroll.verticalScrollBar()
            bar.setValue(bar.value() - event.angleDelta().y() // 2)
            return True
        if self.editing and watched is not self and not self._is_interactive_control(watched) and event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonRelease,
        ):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._begin_edit_mouse(event.globalPosition().toPoint(), event.modifiers())
                return True
            if event.type() == QEvent.Type.MouseMove:
                self._move_edit_mouse(event.globalPosition().toPoint())
                return True
            if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._end_edit_mouse()
                return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event):
        if not self.editing or event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self._begin_edit_mouse(event.globalPosition().toPoint(), event.modifiers())
        event.accept()

    def mouseMoveEvent(self, event):
        if self.editing:
            self._move_edit_mouse(event.globalPosition().toPoint())
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._end_edit_mouse()
            event.accept()
        else:
            event.ignore()

    def wheelEvent(self, event):
        if self.editing:
            self.next_page(-1 if event.angleDelta().y() > 0 else 1)
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape and self.editing:
            self.toggle_editing()
            event.accept()
            return
        elif self.editing and key in (Qt.Key.Key_BracketLeft, Qt.Key.Key_BracketRight):
            self.adjust_opacity(-5 if key == Qt.Key.Key_BracketLeft else 5)
        elif self.editing and key == Qt.Key.Key_C:
            self.toggle_carousel()
        elif self.editing and key == Qt.Key.Key_G:
            self.group_mode = not self.group_mode
        elif self.editing and key == Qt.Key.Key_S:
            modes = ("name", "cpu", "memory", "latency")
            self.sort_mode = modes[(modes.index(self.sort_mode) + 1) % len(modes)]
        elif self.editing and key == Qt.Key.Key_T:
            self.cycle_theme()
        elif self.editing and key in (Qt.Key.Key_N, Qt.Key.Key_Right):
            self.next_page()
        elif self.editing and key in (Qt.Key.Key_P, Qt.Key.Key_Left):
            self.next_page(-1)
        elif self.editing and Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            self.jump_to_page(key - Qt.Key.Key_0, pin=True)
        elif self.editing and key == Qt.Key.Key_0:
            self.clear_page_pin()
        elif self.editing and key == Qt.Key.Key_F2:
            self.open_settings()
        else:
            super().keyPressEvent(event)
            return
        self._save_settings()
        self._apply_theme()
        self._refresh_cards(force=True)
        event.accept()

    def next_page(self, step=1):
        self._layout()
        self.page_index = (self.page_index + step) % max(1, self.page_count)
        self._page_anchor = ""
        self._restore_page_pending = False
        self.cards_scroll.verticalScrollBar().setValue(0)
        self._refresh_cards(force=True)
        self._sync_carousel_timer()
        self._save_settings()

    def toggle_carousel(self):
        self.carousel_enabled = not self.carousel_enabled
        self._sync_carousel_timer()
        self._save_settings()
        self._update_header_labels()

    def set_refresh_seconds(self, seconds):
        seconds = self._number(seconds, MIN_REFRESH_SECONDS, MAX_REFRESH_SECONDS, 15)
        self.refresh_interval_ms = seconds * 1000
        self._next_refresh_ms = self.refresh_interval_ms
        self._retry_failures = 0
        if self.live_enabled and not self._live_busy:
            self.timer.start(max(60_000, self._next_refresh_ms) if self.hidden else self._next_refresh_ms)
        self._save_settings()
        self._update_header_labels()

    def set_carousel_seconds(self, seconds):
        seconds = self._number(seconds, MIN_CAROUSEL_SECONDS, MAX_CAROUSEL_SECONDS, 15)
        self.carousel_interval_ms = seconds * 1000
        self._sync_carousel_timer()
        self._save_settings()
        self._update_header_labels()

    def toggle_page_pin(self):
        if self.page_pinned:
            self.clear_page_pin()
            return
        self.pinned_node_ids = list(self._card_ids)
        if not self.pinned_node_ids:
            return
        self.page_pinned = True
        self._page_anchor = self.pinned_node_ids[0]
        self.page_index = 0
        self._refresh_cards(force=True)
        self._save_settings()
        self._sync_carousel_timer()
        self._update_header_labels()

    def clear_page_pin(self):
        if not self.page_pinned:
            return
        self.page_pinned = False
        self.pinned_node_ids = []
        self._refresh_cards(force=True)
        self._save_settings()
        self._sync_carousel_timer()
        self._update_header_labels()

    def jump_to_page(self, page_number, pin=False):
        previous = (self.page_pinned, list(self.pinned_node_ids), self.page_index, self._page_anchor)
        if pin and self.page_pinned:
            self.page_pinned = False
            self.pinned_node_ids = []
            self._page_anchor = ""
        self._layout()
        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            self.page_pinned, self.pinned_node_ids, self.page_index, self._page_anchor = previous
            self._layout()
            return
        if page_number < 1 or page_number > self.page_count:
            self.page_pinned, self.pinned_node_ids, self.page_index, self._page_anchor = previous
            self._layout()
            return
        self.page_index = page_number - 1
        self._page_anchor = ""
        self._restore_page_pending = False
        self._refresh_cards(force=True)
        if pin:
            self.toggle_page_pin()
        self._save_settings()
        self._sync_carousel_timer()
        self._refresh_cards(force=True)

    def cycle_theme(self):
        skins = tuple(f"skin{index}" for index in range(1, 7))
        try:
            current = skins.index(self.theme)
        except ValueError:
            current = 0
        self.theme = skins[(current + 1) % len(skins)]
        self._apply_theme()
        self._refresh_cards(force=True)
        self._save_settings()

    def adjust_opacity(self, delta):
        self.opacity_percent = max(40, min(100, self.opacity_percent + int(delta)))
        self.panel.set_surface(self._theme_colors, self.opacity_percent)
        self._update_header_labels()
        self._save_settings()
        self.update()

    def _resize_to(self, point):
        if not self.resize_origin or not self.resize_geometry or not self.resize_edge:
            return
        base, delta = self.resize_geometry, point - self.resize_origin
        left, top, width, height = base.x(), base.y(), base.width(), base.height()
        if "left" in self.resize_edge:
            width = max(self.minimumWidth(), base.width() - delta.x())
            left = base.right() - width + 1
        elif "right" in self.resize_edge:
            width = max(self.minimumWidth(), base.width() + delta.x())
        if "top" in self.resize_edge:
            height = max(self.minimumHeight(), base.height() - delta.y())
            top = base.bottom() - height + 1
        elif "bottom" in self.resize_edge:
            height = max(self.minimumHeight(), base.height() + delta.y())
        self.setGeometry(left, top, width, height)

    def _clamp_to_screens(self):
        if not self.isVisible():
            return
        rect = self.geometry()
        screens = QApplication.screens()
        screen = max(screens, key=lambda candidate: (
            candidate.availableGeometry().intersected(rect).width()
            * candidate.availableGeometry().intersected(rect).height()), default=None)
        screen = screen or self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        work = screen.availableGeometry()
        self.setMinimumSize(min(self.MIN_WIDTH, work.width()), min(self.MIN_HEIGHT, work.height()))
        fitted = fit_geometry(rect, work)
        if fitted != rect:
            self.setGeometry(fitted)
            self._save_settings()

    def _watch_screens(self, *_):
        if not hasattr(self, "_screen_timer"):
            self._screen_timer = QTimer(self)
            self._screen_timer.setSingleShot(True)
            self._screen_timer.setInterval(150)
            self._screen_timer.timeout.connect(self._screen_environment_changed)
            app = QApplication.instance()
            app.screenAdded.connect(self._watch_screens)
            app.screenRemoved.connect(self._schedule_screen_check)
            if self.windowHandle():
                self.windowHandle().screenChanged.connect(self._schedule_screen_check)
        for screen in QApplication.screens():
            if screen not in self._screen_connections:
                self._screen_connections.add(screen)
                screen.availableGeometryChanged.connect(self._schedule_screen_check)
                screen.geometryChanged.connect(self._schedule_screen_check)
                screen.logicalDotsPerInchChanged.connect(self._schedule_screen_check)
        self._schedule_screen_check()

    def _schedule_screen_check(self, *_):
        if hasattr(self, "_screen_timer") and not self._close_requested:
            self._screen_timer.start()

    def _screen_environment_changed(self):
        if self._close_requested:
            return
        if not self.drag_origin and not self.resize_origin:
            self._clamp_to_screens()
        self._queue_refresh()


def _enable_dpi_awareness():
    if not IS_WINDOWS:
        return
    try:
        api = ctypes.WinDLL("user32", use_last_error=True)
        function = getattr(api, "SetProcessDpiAwarenessContext", None)
        if function is not None:
            function.restype, function.argtypes = wintypes.BOOL, [ctypes.c_void_p]
            if function(ctypes.c_void_p(-4)):
                return
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        function = shcore.SetProcessDpiAwareness
        function.restype, function.argtypes = wintypes.LONG, [ctypes.c_int]
        function(2)
    except (AttributeError, OSError, OverflowError):
        pass


def _acquire_instance_lock():
    """避免重复启动造成多个面板和全局快捷键互相争用。"""
    lock_path = os.path.join(tempfile.gettempdir(), "KomariDesktop-QtProbe.lock")
    lock = QLockFile(lock_path)
    if not lock.tryLock(100):
        return None
    return lock


def _bring_existing_window_to_front():
    """重复启动时唤醒已有面板，避免用户误以为程序启动后立即退出。"""
    if not IS_WINDOWS:
        return False
    found = []
    enum_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def locate(hwnd, _):
        title = ctypes.create_unicode_buffer(256)
        _user32.GetWindowTextW(hwnd, title, len(title))
        if title.value == WINDOW_TITLE:
            found.append(hwnd)
            return False
        return True

    try:
        _user32.EnumWindows(enum_type(locate), 0)
        if not found:
            return False
        hwnd = found[0]
        # 已有实例自行恢复隐藏状态/打开设置，不从第二个进程强行改窗口层级。
        return bool(_user32.PostMessageW(hwnd, WM_APP_WAKE, 0, 0))
    except (TypeError, ValueError, OSError):
        return False


def main():
    _enable_dpi_awareness()
    instance_lock = _acquire_instance_lock()
    if instance_lock is None:
        shown = _bring_existing_window_to_front()
        if "--debug" in sys.argv:
            print("KomariDesktop Qt Probe 已经在运行。" + (" 已唤醒现有窗口。" if shown else " 未找到现有窗口。"))
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(True)
    window = ProbeWindow()
    # 设计稿面板约为 440×526 逻辑像素；窗口保留少量透明外边距，
    # 首次运行/旧版尺寸会在
    # _restore_geometry 中迁移，用户手动调整后的尺寸不会被覆盖。
    window.resize(452, 538)
    window.show()
    if "--settings" in sys.argv:
        QTimer.singleShot(250, window.open_settings)
    # 保持锁对象存活到事件循环退出。
    app._komari_instance_lock = instance_lock
    exit_code = app.exec()
    instance_lock.unlock()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())


