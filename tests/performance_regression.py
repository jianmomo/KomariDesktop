"""资源/连接回归：本地 HTTP 替身模拟故障，不修改用户配置或真实服务器。"""

from __future__ import annotations

import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

from PySide6.QtCore import QEvent, QSettings
from PySide6.QtWidgets import QApplication

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))
if (APP_ROOT / "main.py").exists():
    import main as monitor
else:
    import qt_main_redesign as monitor


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, payload, code=200):
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        self.server.calls.append(self.path)
        if self.server.mode == "error":
            self.reply({"status": "error"}, 503)
        elif self.server.mode == "empty":
            self.reply({"status": "success", "data": []})
        else:
            self.reply({"status": "success", "data": [{
                "uuid": "test-node", "name": "回归节点", "group": "测试", "region": "🇩🇪",
                "mem_total": 1000, "traffic_limit": 2048, "expired_at": "2027-01-01T00:00:00Z",
                "ip": "203.0.113.1", "private_probe": "fixture-not-persisted",
            }]})

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.calls.append(self.path)
        if self.server.mode == "slow":
            self.server.entered.set()
            self.server.release.wait(2)
        if self.server.mode == "error":
            self.reply({"status": "error"}, 503)
            return
        result = [] if self.server.mode == "malformed" else {"test-node": {
            "online": True, "cpu": 12.5 + self.server.calls.count("/api/rpc2"),
            "ram": 250, "ram_total": 1000, "net_in": 2048, "net_out": 1024,
            "net_total_up": 100, "net_total_down": 200,
            "ping": {"1": {"latest": 42, "loss": 0}, "2": {"latest": 75, "loss": 1.1}},
        }}
        self.reply({"jsonrpc": "2.0", "result": result, "id": "komari-desktop-status"})


def wait_for(predicate, timeout=4):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError("等待条件超时")


class Regression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.daemon_threads = True
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        cls.server_thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.original_settings = monitor.QSettings

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(2)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="komari-regression-")
        path = str(Path(self.temporary.name) / "settings.ini")
        self.settings = QSettings(path, QSettings.Format.IniFormat)
        self.settings.setValue("komariUrl", self.url)
        monitor.QSettings = lambda *_: QSettings(path, QSettings.Format.IniFormat)
        self.windows = []
        self.server.mode = "ok"
        self.server.calls = []
        self.server.entered = threading.Event()
        self.server.release = threading.Event()

    def tearDown(self):
        self.server.release.set()
        for window in self.windows:
            window.close()
            wait_for(lambda: window._live_thread is None)
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        monitor.QSettings = self.original_settings
        self.temporary.cleanup()

    def window(self, live=False):
        window = monitor.ProbeWindow(live_enabled=live)
        self.windows.append(window)
        window.show()
        window.resize(392, 520)
        for _ in range(8):
            QApplication.processEvents()
        return window

    def loaded(self, window):
        wait_for(lambda: window.source_state == "ok" and not window._live_busy)
        window.timer.stop()

    def test_metadata_cached_but_latest_status_keeps_refreshing(self):
        client = monitor.KomariClient(self.url)
        first = client.fetch_samples()
        second = client.fetch_samples()
        self.assertEqual(self.server.calls.count("/api/nodes"), 1)
        self.assertEqual(self.server.calls.count("/api/rpc2"), 2)
        self.assertGreater(second[0]["cpu"], first[0]["cpu"])
        client._nodes_updated_at -= monitor.KOMARI_NODES_TTL_SECONDS + 1
        client.fetch_samples()
        self.assertEqual(self.server.calls.count("/api/nodes"), 2)

    def test_invalid_rpc_is_failure_not_zero_or_offline(self):
        self.server.mode = "malformed"
        with self.assertRaisesRegex(RuntimeError, "实时状态格式异常"):
            monitor.KomariClient(self.url).fetch_samples()

    def test_reuse_card_and_apply_new_dictionary_without_page_reset(self):
        window = self.window()
        window.timer.stop()
        before = tuple(id(card) for card in window._cards)
        samples = copy.deepcopy(window.samples)
        samples[0]["cpu"] = 77.7
        window._on_live_success(samples, "12:00:00")
        self.assertEqual(tuple(id(card) for card in window._cards), before)
        card = next(card for card in window._cards if card.item["id"] == samples[0]["id"])
        self.assertEqual(card.metric_blocks[0].value_label.text(), "77.7%")
        window.next_page()
        page = window.page_index
        window._on_live_success(copy.deepcopy(samples), "12:00:15")
        self.assertEqual(window.page_index, page)

    def test_failure_preserves_values_and_backs_off_then_recovers(self):
        window = self.window(live=True)
        self.loaded(window)
        old_cpu = window.samples[0]["cpu"]
        saved_thread = window._live_thread
        self.server.mode = "error"
        for failures, delay in enumerate((15000, 30000, 60000, 120000, 240000, 300000, 300000), 1):
            window._request_live_refresh()
            wait_for(lambda: not window._live_busy)
            self.assertEqual(window.source_state, "error")
            self.assertEqual(window._next_refresh_ms, delay)
            self.assertEqual(window.samples[0]["cpu"], old_cpu)
            self.assertEqual(window.samples[0]["status"], "stale")
            window.timer.stop()
        self.server.mode = "ok"
        window._request_live_refresh()
        self.loaded(window)
        self.assertIs(window._live_thread, saved_thread)
        self.assertEqual(window._retry_failures, 0)
        self.assertEqual(window._next_refresh_ms, 15000)
        self.assertEqual(window.samples[0]["status"], "online")

    def test_single_inflight_and_close_during_slow_request(self):
        self.server.mode = "slow"
        window = self.window(live=True)
        wait_for(self.server.entered.is_set)
        for _ in range(20):
            window._request_live_refresh()
        self.assertEqual(self.server.calls.count("/api/rpc2"), 1)
        window.close()
        self.assertFalse(window.isVisible())
        self.server.release.set()
        wait_for(lambda: window._live_thread is None)
        self.assertFalse(window.timer.isActive())

    def test_restart_shows_stale_cache_without_saving_raw_sensitive_fields(self):
        window = self.window(live=True)
        self.loaded(window)
        raw = str(window.settings.value("liveSnapshot"))
        self.assertNotIn("203.0.113.1", raw)
        self.assertNotIn("fixture-not-persisted", raw)
        expected_cpu = window.samples[0]["cpu"]
        window.close()
        wait_for(lambda: window._live_thread is None)
        cached = monitor.ProbeWindow(live_enabled=True)
        self.windows.append(cached)
        self.assertEqual(cached.source_state, "cached")
        self.assertEqual(cached.samples[0]["status"], "stale")
        self.assertEqual(cached.samples[0]["cpu"], expected_cpu)
        self.assertIn("上次", cached.footer_label.text())
        cached.close()

    def test_corrupt_cache_is_ignored_and_saved_selection_survives_first_load(self):
        self.settings.setValue("liveSnapshot", "{bad json")
        self.settings.setValue("selectedIds", '["test-node"]')
        window = self.window(live=True)
        self.loaded(window)
        self.assertEqual(window.selected_ids, {"test-node"})

    def test_no_nodes_is_not_connection_failure(self):
        self.server.mode = "empty"
        window = self.window(live=True)
        self.loaded(window)
        self.assertEqual(window.samples, [])
        self.assertIn("暂无节点", window.summary_label.text())
        self.assertNotIn("连接中断", window.footer_label.text())

    def test_total_loss_survives_missing_latency(self):
        window = self.window()
        chip = window._cards[0].carrier_chips[0]
        chip.set_values(None, 100)
        self.assertIn("100.0%", chip.loss_label.text())

    def test_hidden_updates_model_then_renders_latest_on_show(self):
        window = self.window(live=True)
        self.loaded(window)
        window.toggle_hidden()
        self.assertGreaterEqual(window.timer.interval(), 60000)
        before = window._cards[0].metric_blocks[0].value_label.text()
        updated = copy.deepcopy(window.samples)
        updated[0]["cpu"] = 88.8
        window._on_live_success(updated, "12:00:00")
        self.assertEqual(window._cards[0].metric_blocks[0].value_label.text(), before)
        window.toggle_hidden()
        self.assertEqual(window._cards[0].metric_blocks[0].value_label.text(), "88.8%")
        self.assertFalse(window._view_dirty)

    def test_repeated_refresh_keeps_widget_count_stable(self):
        window = self.window()
        window.timer.stop()
        initial = len(window.findChildren(monitor.QWidget))
        for index in range(200):
            updated = copy.deepcopy(window.samples)
            updated[0]["cpu"] = index % 100
            window._on_live_success(updated, "12:00:00")
            QApplication.processEvents()
            QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertEqual(len(window.findChildren(monitor.QWidget)), initial)

    def test_live_carousel_pauses_in_editing_and_hidden_modes(self):
        self.settings.setValue("carouselEnabled", True)
        window = self.window(live=True)
        self.loaded(window)
        self.assertTrue(window.carousel_timer.isActive())
        window.toggle_editing()
        self.assertFalse(window.carousel_timer.isActive())
        window.toggle_editing()
        self.assertTrue(window.carousel_timer.isActive())
        geometry = window.geometry()
        window.toggle_hidden()
        self.assertFalse(window.carousel_timer.isActive())
        window.toggle_hidden()
        self.assertTrue(window.carousel_timer.isActive())
        self.assertEqual(window.geometry(), geometry)


if __name__ == "__main__":
    unittest.main(verbosity=2)

