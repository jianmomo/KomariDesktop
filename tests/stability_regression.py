"""1.0 稳定性回归：离屏显示、临时设置与回环慢响应，不影响用户实例。"""

from __future__ import annotations

import copy
import ctypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEvent, QObject, QSettings, QTimer, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QWidget

import main as monitor


def wait_for(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("等待状态超时")


class SlowHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        return

    def do_GET(self):
        if self.path == "/api/nodes":
            body = json.dumps({"status": "success", "data": [{"uuid": "node", "name": "test"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.server.entered.set()
        if self.path == "/headers":
            self.server.release.wait(4)
        if self.path == "/large":
            body = b"x" * (4 * 1024 * 1024 + 1)
        elif self.path == "/invalid":
            body = b"not json"
        else:
            body = b'{"status":"success"}'
        self.send_response(503 if self.path == "/error" else 200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            if self.path == "/drip":
                for value in body:
                    self.wfile.write(bytes([value]))
                    self.wfile.flush()
                    if self.server.release.wait(0.15):
                        break
            else:
                self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.entered.set()
        body = b'{"jsonrpc":"2.0","result":{"node":{"online":true,"cpu":0}},"id":"test"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            for value in body:
                self.wfile.write(bytes([value]))
                self.wfile.flush()
                if self.server.release.wait(0.15):
                    break
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            return


class StabilityRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="komari-stability-")
        self.settings_path = str(Path(self.temp.name) / "settings.ini")
        self.install_shell_hook = monitor.ProbeWindow._install_shell_hook
        self.patches = [
            patch.object(monitor, "IS_WINDOWS", False),
            patch.object(monitor, "QSettings", lambda *_: QSettings(
                self.settings_path, QSettings.Format.IniFormat)),
            patch.object(monitor.ProbeWindow, "_register_hotkeys", lambda self: None),
            patch.object(monitor.ProbeWindow, "_unregister_hotkeys", lambda self: None),
            patch.object(monitor.ProbeWindow, "_create_tray", lambda self: None),
            patch.object(monitor.ProbeWindow, "_watch_screens", lambda self, *_: None),
            patch.object(monitor.ProbeWindow, "_install_shell_hook", lambda self: None, create=True),
        ]
        for active in self.patches:
            active.start()
        self.windows = []
        self.server = None

    def tearDown(self):
        if self.server:
            self.server.release.set()
        for window in self.windows:
            window.close()
            wait_for(lambda: window._live_thread is None)
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.serving.join(2)
        for active in reversed(self.patches):
            active.stop()
        self.temp.cleanup()

    def window(self, layer="normal"):
        settings = monitor.QSettings()
        settings.setValue("layerMode", layer)
        window = monitor.ProbeWindow(live_enabled=False)
        self.windows.append(window)
        window.show()
        for _ in range(8):
            self.app.processEvents()
        window.timer.stop()
        return window

    def client(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
        self.server.daemon_threads = True
        self.server.entered = threading.Event()
        self.server.release = threading.Event()
        self.serving = threading.Thread(target=self.server.serve_forever,
                                        kwargs={"poll_interval": 0.05}, daemon=True)
        self.serving.start()
        return monitor.KomariClient(f"http://127.0.0.1:{self.server.server_port}", timeout=2)

    def test_recover_minimized_panel(self):
        window = self.window()
        window.showMinimized()
        self.app.processEvents()
        self.assertTrue(window.isMinimized())
        window.recover_to_screen()
        self.app.processEvents()
        self.assertFalse(window.isMinimized())
        self.assertTrue(window.isVisible())

    def test_show_hotkey_recovers_in_one_press(self):
        window = self.window()
        window.showMinimized()
        self.app.processEvents()
        window.toggle_hidden()
        self.app.processEvents()
        self.assertFalse(window.hidden)
        self.assertFalse(window.isMinimized())

    def test_desktop_minimize_restores_without_switching_layer(self):
        window = self.window("desktop")
        with patch.object(window, "_place_desktop", return_value=True) as place:
            window.showMinimized()
            wait_for(lambda: not window.isMinimized())
            self.assertEqual(window.layer_mode, "desktop")
            self.assertGreaterEqual(place.call_count, 1)

    def test_normal_minimize_pauses_and_restore_resumes_carousel(self):
        window = self.window()
        window.carousel_enabled = True
        window._sync_carousel_timer()
        self.assertTrue(window.carousel_timer.isActive())
        window.showMinimized()
        self.app.processEvents()
        self.assertFalse(window.carousel_timer.isActive())
        self.assertTrue(window.isMinimized())
        window.showNormal()
        self.app.processEvents()
        self.assertTrue(window.carousel_timer.isActive())

    def test_repeated_display_sync_does_not_starve_carousel(self):
        window = self.window()
        self.assertGreater(window.page_count, 1)
        window.carousel_enabled = True
        window.carousel_interval_ms = 150
        window._sync_carousel_timer()
        page = window.page_index
        activity = QTimer(window)
        activity.timeout.connect(window._sync_display_activity)
        activity.start(20)
        try:
            wait_for(lambda: window.page_index != page, timeout=0.8)
        finally:
            activity.stop()

    def test_shell_recovery_is_debounced(self):
        window = self.window("desktop")
        with patch.object(window, "_place_desktop", return_value=True) as place:
            for _ in range(20):
                window._queue_desktop_recovery()
            wait_for(lambda: place.call_count > 0)
            self.assertEqual(place.call_count, 1)

    def test_shell_events_do_not_resurrect_hidden_or_closing_panel(self):
        window = self.window("desktop")
        window.toggle_hidden()
        window._queue_desktop_recovery()
        window._recover_desktop_window()
        self.assertTrue(window.hidden)
        self.assertFalse(window.isVisible())
        window._close_requested = True
        window._recover_desktop_window()
        self.assertFalse(window.isVisible())

    def test_normal_layer_ignores_shell_recovery(self):
        window = self.window()
        with patch.object(window, "_place_desktop", return_value=True) as place:
            window._queue_desktop_recovery()
            window._recover_desktop_window()
            self.assertEqual(place.call_count, 0)

    def test_native_shell_callback_and_cleanup(self):
        window = self.window("desktop")
        native = Mock()
        native.RegisterWindowMessageW.return_value = 0xC001
        native.SetWinEventHook.return_value = 100
        native.UnhookWinEvent.return_value = True

        def class_name(_hwnd, buffer, _size):
            buffer.value = "Progman"
            return len(buffer.value)

        native.GetClassNameW.side_effect = class_name
        with patch.object(monitor, "IS_WINDOWS", True), patch.object(monitor, "_user32", native), \
                patch.object(window, "_place_desktop", return_value=True) as place:
            # setUp 的自动安装已禁用，这里直接验证真实注册和回调路径。
            try:
                self.install_shell_hook(window)
                callback = window._shell_event_callback
                self.assertIsNotNone(callback)
                callback(100, monitor.EVENT_SYSTEM_FOREGROUND, 200, 0, 0, 0, 0)
                wait_for(lambda: place.call_count > 0)
                self.assertEqual(native.SetWinEventHook.call_count, 1)
                window._remove_shell_hook()
                self.assertIsNone(window._shell_event_callback)
                native.UnhookWinEvent.assert_called_once_with(100)
            finally:
                window._remove_shell_hook()

    def test_taskbar_rebuild_message_queues_recovery(self):
        window = self.window("desktop")
        window._taskbar_created_message = 0xC001
        message = monitor._Message()
        message.hwnd = int(window.effectiveWinId())
        message.message = 0xC001
        with patch.object(monitor, "IS_WINDOWS", True), \
                patch.object(window, "_queue_desktop_recovery") as queued:
            window.native_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message))
            queued.assert_called_once()

    def test_returning_to_application_also_repositions_desktop_panel(self):
        window = self.window("desktop")
        with patch.object(monitor, "IS_WINDOWS", True), \
                patch.object(window, "_queue_desktop_recovery") as queued:
            window._on_shell_foreground(123)
            queued.assert_called_once()

    def test_desktop_surface_keeps_controller_and_skips_redundant_recovery(self):
        window = self.window("desktop")
        native = Mock()
        native.FindWindowExW.return_value = 41
        native.IsWindowVisible.return_value = False
        surface = Mock()
        surface.alive.return_value = True
        with patch.object(monitor, "IS_WINDOWS", True), patch.object(monitor, "_user32", native), \
                patch.object(window, "_desktop_anchor", return_value=40), \
                patch.object(monitor, "DesktopSurface", return_value=surface), \
                patch.object(window, "_queue_desktop_recovery") as queued:
            self.assertTrue(window._place_desktop())
            window._on_shell_foreground(123)
            queued.assert_not_called()
            self.assertTrue(window._surface_active)
            window._disable_desktop_surface(restore_window=True)
        surface.update.assert_called_once()
        surface.destroy.assert_called_once()
        self.assertEqual(window.layer_mode, "desktop")
        self.assertEqual(window._layer_error, "")

    def test_desktop_failure_keeps_preferences_and_future_recovery(self):
        window = self.window("desktop")
        window.click_through = True
        window._save_settings()
        native = Mock()
        native.FindWindowExW.return_value = 41
        native.SetWindowPos.return_value = True
        surface = Mock()
        surface.update.side_effect = OSError("模拟桌面宿主消失")
        with patch.object(monitor, "IS_WINDOWS", True), patch.object(monitor, "_user32", native), \
                patch.object(window, "_desktop_anchor", return_value=40), \
                patch.object(monitor, "DesktopSurface", return_value=surface):
            self.assertFalse(window._place_desktop())
        surface.destroy.assert_called_once()
        self.assertEqual(window.layer_mode, "desktop")
        self.assertTrue(window.click_through)
        self.assertEqual(window.settings.value("layerMode"), "desktop")
        self.assertTrue(window.settings.value("clickThrough", type=bool))
        window._queue_desktop_recovery()
        self.assertTrue(window._desktop_recovery_timer.isActive())

    def test_content_changes_are_coalesced_into_one_desktop_redraw(self):
        window = self.window("desktop")
        surface = Mock()
        window._desktop_surface = surface
        window._surface_active = True
        with patch.object(window, "_place_desktop", return_value=True) as place:
            for _ in range(20):
                window._queue_surface_render()
            wait_for(lambda: place.call_count == 1)
        window._disable_desktop_surface(restore_window=False)
        surface.destroy.assert_called_once()

    def test_native_controller_hide_does_not_pause_desktop_updates(self):
        window = self.window("desktop")
        window._surface_active = True
        window._desktop_surface = Mock()
        message = monitor._Message()
        message.hwnd = int(window.effectiveWinId())
        message.message = monitor.WM_SHOWWINDOW
        message.wParam = 0
        with patch.object(monitor, "IS_WINDOWS", True), \
                patch.object(window, "_queue_desktop_recovery") as queued:
            window.native_filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(message))
            self.assertFalse(window._system_hidden)
            self.assertFalse(window._display_paused())
            queued.assert_not_called()
        window._disable_desktop_surface(restore_window=False)

    def test_desktop_surface_refreshes_when_controller_window_is_hidden(self):
        window = self.window("desktop")
        window._surface_active = True
        # 原生桌面层隐藏控制窗口时，Qt 的 hideEvent 可能留下 system_hidden 标记；
        # 只要 DesktopSurface 还活着，屏幕上的面板仍然需要继续刷新。
        window._system_hidden = True
        samples = copy.deepcopy(window.samples)
        samples[0]["cpu"] = 88.8
        with patch.object(window, "isVisible", return_value=False):
            self.assertFalse(window._display_paused())
            window._on_live_success(samples, "12:00:00")
        self.assertFalse(window._view_dirty)
        self.assertEqual(window._cards[0].metric_blocks[0].value_label.text(), "88.8%")

    def test_desktop_surface_repaints_after_controller_window_is_hidden(self):
        window = self.window("desktop")
        native = Mock()
        native.FindWindowExW.return_value = 41
        native.IsWindowVisible.return_value = False
        surface = Mock()
        surface.alive.return_value = True
        window._surface_active = True
        window._desktop_surface = surface
        with patch.object(monitor, "IS_WINDOWS", True), patch.object(monitor, "_user32", native), \
                patch.object(window, "_desktop_anchor", return_value=40), \
                patch.object(window, "isVisible", return_value=False):
            self.assertTrue(window._place_desktop())
        surface.update.assert_called_once()

    def test_global_edit_hotkey_ignores_duplicate_toggle(self):
        window = self.window("desktop")
        window._surface_active = True
        window._system_hidden = True
        window.toggle_editing(source="global-hotkey")
        self.assertTrue(window.editing)
        self.assertFalse(window.locked)
        window.toggle_editing(source="global-hotkey")
        self.assertTrue(window.editing)
        self.assertFalse(window.locked)

    @unittest.skipUnless(sys.platform == "win32", "需要 Windows 原生窗口")
    def test_edit_mode_remaps_native_hidden_controller(self):
        if self.app.platformName() != "windows":
            self.skipTest("需要 Qt Windows 平台插件")

        class VisibilityRecorder(QObject):
            def __init__(self):
                super().__init__()
                self.events = []

            def eventFilter(self, watched, event):
                if event.type() in (QEvent.Type.Hide, QEvent.Type.Show):
                    self.events.append(event.type())
                return False

        window = self.window("desktop")
        window.resize(452, 538)
        self.app.processEvents()
        hwnd = int(window.winId())
        recorder = VisibilityRecorder()
        window.installEventFilter(recorder)
        window._surface_active = True
        window._desktop_surface = Mock()
        window._surface_transition = True
        try:
            monitor._user32.ShowWindow(hwnd, 0)
        finally:
            window._surface_transition = False
        self.assertTrue(window.isVisible())
        self.assertFalse(monitor._user32.IsWindowVisible(hwnd))

        samples = copy.deepcopy(window.samples)
        samples[0]["cpu"] = 88.8
        window._on_live_success(samples, "22:03:10")
        window._surface_render_timer.stop()
        # 模拟桌面层在控制窗口原生隐藏时绘制实时内容。
        from desktop_surface import capture_widget_image
        self.assertFalse(capture_widget_image(window).isNull())
        recorder.events.clear()
        with patch.object(monitor, "IS_WINDOWS", True):
            self.assertTrue(window.toggle_editing(source="global-hotkey"))
            self.app.processEvents()
            self.assertTrue(monitor._user32.IsWindowVisible(hwnd))

        self.assertEqual(recorder.events[:2], [QEvent.Type.Hide, QEvent.Type.Show])
        self.assertEqual(int(window.winId()), hwnd)
        self.assertTrue(window.editing)
        self.assertTrue(window.toolbar.isVisible())
        self.assertTrue(window.action_row.isVisible())
        self.assertEqual(window.mode_label.text(), "调整中 · 可拖动")
        self.assertIn("退出调整", window.header_hint.text())
        self.assertEqual(window._cards[0].metric_blocks[0].value_label.text(), "88.8%")
        self.assertFalse(window._display_paused())

        def place_on_desktop():
            window._desktop_surface = Mock()
            window._surface_active = True
            window._surface_transition = True
            try:
                monitor._user32.ShowWindow(hwnd, 0)
            finally:
                window._surface_transition = False
            return True

        with patch.object(monitor, "IS_WINDOWS", True), \
                patch.object(window, "_place_desktop", side_effect=place_on_desktop):
            self.assertTrue(window.toggle_editing())
            self.assertFalse(monitor._user32.IsWindowVisible(hwnd))
            samples[0]["cpu"] = 33.3
            window._on_live_success(samples, "22:03:25")
            window._surface_render_timer.stop()
            self.assertTrue(window.toggle_editing())
            self.app.processEvents()
            self.assertTrue(monitor._user32.IsWindowVisible(hwnd))
        self.assertEqual(int(window.winId()), hwnd)
        self.assertTrue(window.action_row.isVisible())
        self.assertEqual(window._cards[0].metric_blocks[0].value_label.text(), "33.3%")

    def test_enter_edit_mode_restarts_cached_live_refresh(self):
        window = self.window("desktop")
        window.live_enabled = True
        window.source_state = "cached"
        window._surface_active = True
        with patch.object(window, "_request_live_refresh") as request:
            window.toggle_editing()
        request.assert_called_once()
        self.assertTrue(window.editing)
        self.assertFalse(window._display_paused())

    def test_surface_capture_renders_latest_hidden_widget_content(self):
        from desktop_surface import capture_widget_image

        class ColorWidget(QWidget):
            def __init__(self):
                super().__init__()
                self.color = QColor("#ff0000")

            def paintEvent(self, event):
                painter = QPainter(self)
                painter.fillRect(self.rect(), self.color)
                painter.end()

        widget = ColorWidget()
        widget.resize(80, 40)
        widget.show()
        self.app.processEvents()
        widget.color = QColor("#00ff00")
        widget.hide()
        image = capture_widget_image(widget)
        try:
            self.assertEqual(image.pixelColor(5, 5).name().lower(), "#00ff00")
        finally:
            widget.deleteLater()

    def test_hidden_desktop_surface_is_not_resurrected(self):
        window = self.window("desktop")
        surface = Mock()
        window._surface_active = True
        window._desktop_surface = surface
        window.toggle_hidden()
        self.assertTrue(window.hidden)
        self.assertFalse(window.isVisible())
        self.assertFalse(window._surface_active)
        surface.destroy.assert_called_once()

    def test_minimized_live_data_waits_for_restore(self):
        window = self.window()
        before = window._cards[0].metric_blocks[0].value_label.text()
        window.showMinimized()
        self.app.processEvents()
        window.live_enabled = True
        samples = copy.deepcopy(window.samples)
        samples[0]["cpu"] = 77.7
        window._on_live_success(samples, "12:00:00")
        window._on_live_refresh_finished()
        self.assertTrue(window._view_dirty)
        self.assertEqual(window._cards[0].metric_blocks[0].value_label.text(), before)
        self.assertGreaterEqual(window.timer.interval(), 60000)
        window.live_enabled = False
        window.showNormal()
        self.app.processEvents()
        self.assertFalse(window._view_dirty)
        self.assertEqual(window._cards[0].metric_blocks[0].value_label.text(), "77.7%")

    def test_failed_preferences_are_rolled_back_before_close(self):
        window = self.window()
        original = window.settings_snapshot()
        original_geometry = window.geometry()

        def fail_layer():
            window._layer_error = "模拟图层失败"
            return False

        with patch.object(window, "_place_desktop", side_effect=fail_layer):
            result = window.apply_preferences({"opacity": 65, "theme": "skin6"})
        self.assertTrue(result)
        self.assertEqual(window.opacity_percent, original["opacity"])
        self.assertEqual(window.theme, original["theme"])
        self.assertEqual(window.geometry(), original_geometry)
        window.close()
        self.assertEqual(int(window.settings.value("windowOpacity")), original["opacity"])

    def test_successful_preferences_are_persisted(self):
        window = self.window()
        self.assertIsNone(window.apply_preferences({"opacity": 65, "theme": "skin6"}))
        self.assertEqual(window.opacity_percent, 65)
        self.assertEqual(int(window.settings.value("windowOpacity")), 65)

    def test_invalid_preferences_do_not_touch_native_layer(self):
        window = self.window()
        with patch.object(window, "_place_desktop") as place:
            self.assertTrue(window.apply_preferences({"opacity": 200}))
            place.assert_not_called()

    def test_failed_pin_settings_are_not_saved_indirectly(self):
        window = self.window()
        with patch.object(window, "_place_desktop", return_value=False):
            self.assertTrue(window.apply_preferences({"pin_current": True, "opacity": 65}))
        self.assertFalse(window.page_pinned)
        self.assertEqual(window.opacity_percent, 100)
        window.close()
        self.assertFalse(window._bool_value("pagePinned", True))

    def test_mapping_retains_complete_loss_without_rtt(self):
        sample = monitor.KomariClient._build_samples(
            [{"uuid": "loss-case", "name": "test"}],
            {"loss-case": {"online": True, "ping": {
                "1": {"latest": None, "loss": 100.0},
                "4": {"latest": 5.0, "loss": 0},
            }}},
        )[0]
        self.assertIsNone(sample["latency"]["移动"])
        self.assertEqual(sample["loss"]["移动"], 100.0)

    def test_status_payload_variants_are_classified_without_false_stale(self):
        nodes = [
            {"uuid": "bool", "name": "bool"},
            {"uuid": "number", "name": "number"},
            {"uuid": "string", "name": "string"},
            {"uuid": "missing", "name": "missing"},
        ]
        samples = monitor.KomariClient._build_samples(nodes, {
            "bool": {"online": True},
            "number": {"online": 1},
            "string": {"status": "offline"},
            "missing": {},
        })
        self.assertEqual([sample["status"] for sample in samples],
                         ["online", "online", "offline", "stale"])

    def test_status_result_wrappers_are_supported(self):
        wrapped = monitor.KomariClient._status_entries({
            "data": {"node": {"online": 1}},
        })
        self.assertEqual(wrapped["node"]["online"], 1)

    def test_slow_body_obeys_total_deadline(self):
        client = self.client()
        started = time.monotonic()
        with self.assertRaisesRegex(RuntimeError, "超时"):
            client._request_json("/drip")
        self.assertLess(time.monotonic() - started, 2.8)

    def test_zero_loss_without_rtt_keeps_existing_fallback_task(self):
        sample = monitor.KomariClient._build_samples(
            [{"uuid": "fallback"}],
            {"fallback": {"online": True, "ping": {
                "1": {"latest": None, "loss": 0}, "4": {"latest": 42.0, "loss": 0},
            }}},
        )[0]
        self.assertEqual(sample["latency"]["移动"], 42.0)

    def test_inflight_cancel_interrupts_body(self):
        client = self.client()
        cancellation = threading.Timer(0.2, client.cancel)
        cancellation.start()
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(RuntimeError, "取消"):
                client._request_json("/drip")
            self.assertLess(time.monotonic() - started, 1.0)
        finally:
            cancellation.cancel()
            cancellation.join()

    def test_inflight_cancel_interrupts_headers(self):
        client = self.client()
        cancellation = threading.Timer(0.2, client.cancel)
        cancellation.start()
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(RuntimeError, "取消"):
                client._request_json("/headers")
            self.assertLess(time.monotonic() - started, 1.0)
        finally:
            cancellation.cancel()
            cancellation.join()

    def test_request_errors_stay_explicit(self):
        client = self.client()
        for path, message in (("/large", "响应过大"), ("/invalid", "有效 JSON"), ("/error", "HTTP 503")):
            with self.subTest(path=path), self.assertRaisesRegex(RuntimeError, message):
                client._request_json(path)

    def test_existing_sizes_and_skins_render_without_card_overlap(self):
        sizes = ((320, 360), (360, 420), (392, 520), (500, 520),
                 (640, 720), (760, 640), (1100, 800))
        for theme in monitor.SKIN_NAMES:
            window = self.window()
            window.theme = theme
            window._apply_theme()
            for width, height in sizes:
                with self.subTest(theme=theme, size=(width, height)):
                    window.resize(width, height)
                    for _ in range(8):
                        self.app.processEvents()
                    self.assertFalse(window.grab().isNull())
                    rects = [rect for rect, _ in window._layout_rects]
                    for index, first in enumerate(rects):
                        self.assertFalse(any(first.intersects(second) for second in rects[index + 1:]))

    def test_close_interrupts_running_worker_without_resurrection(self):
        self.client()
        monitor.QSettings().setValue("komariUrl", f"http://127.0.0.1:{self.server.server_port}")
        window = monitor.ProbeWindow(live_enabled=True)
        self.windows.append(window)
        window.show()
        wait_for(self.server.entered.is_set)
        ready = Mock()
        window.shutdown_ready.connect(ready)
        started = time.monotonic()
        window.close()
        wait_for(lambda: window._live_thread is None, timeout=1)
        wait_for(lambda: ready.call_count == 1, timeout=1)
        self.assertLess(time.monotonic() - started, 1)
        self.assertTrue(window._close_requested)
        self.assertFalse(window.isVisible())

    def test_standalone_tool_window_close_exits_entire_process(self):
        script = '''
import sys
from unittest.mock import Mock
sys.path.insert(0, sys.argv[1])
import main as monitor
from PySide6.QtCore import QSettings, QTimer
monitor.IS_WINDOWS = False
monitor._configure_logging = lambda: None
monitor._acquire_instance_lock = lambda: Mock()
monitor.QSettings = lambda *_: QSettings(sys.argv[2], QSettings.Format.IniFormat)
monitor.ProbeWindow._create_tray = lambda self: None
class ClosingWindow(monitor.ProbeWindow):
    def __init__(self):
        super().__init__(live_enabled=False)
        if sys.argv[3] == "hidden":
            QTimer.singleShot(20, self.hide)
        QTimer.singleShot(40, lambda: self.request_close("regression"))
monitor.ProbeWindow = ClosingWindow
raise SystemExit(monitor.main())
'''
        for visibility in ("visible", "hidden"):
            with self.subTest(visibility=visibility):
                result = subprocess.run(
                    [sys.executable, "-B", "-c", script,
                     str(Path(monitor.__file__).resolve().parent), self.settings_path, visibility],
                    timeout=4, capture_output=True, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
                )
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
