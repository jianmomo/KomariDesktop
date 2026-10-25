"""真实只读连接冒烟：临时配置，不改动正在运行程序的偏好。"""

import argparse
import json
from pathlib import Path
import sys
import tempfile
import time

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))
if (APP_ROOT / "main.py").exists():
    import main as monitor
else:
    import qt_main_redesign as monitor


def wait_for(predicate, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("真实连接超时")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview-dir")
    args = parser.parse_args()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    windows = []
    original_factory = monitor.QSettings
    with tempfile.TemporaryDirectory(prefix="komari-live-") as temporary:
        settings_path = str(Path(temporary) / "settings.ini")
        monitor.QSettings = lambda *_: QSettings(settings_path, QSettings.Format.IniFormat)
        try:
            start = time.perf_counter()
            window = monitor.ProbeWindow(live_enabled=True)
            windows.append(window)
            window.show()
            window.resize(392, 520)
            wait_for(lambda: window.source_state in {"ok", "error"} and not window._live_busy)
            assert window.source_state == "ok", window.source_error
            assert window.samples
            cold_ms = round((time.perf_counter() - start) * 1000, 1)
            worker_thread = window._live_thread
            window.timer.stop()
            start = time.perf_counter()
            window._request_live_refresh()
            wait_for(lambda: not window._live_busy)
            assert window.source_state == "ok", window.source_error
            assert window._live_thread is worker_thread
            latest_ms = round((time.perf_counter() - start) * 1000, 1)
            window.timer.stop()
            if args.preview_dir:
                destination = Path(args.preview_dir)
                for width, height in ((392, 520), (640, 720)):
                    window.resize(width, height)
                    for _ in range(8):
                        app.processEvents()
                    assert window.width() == width and window.height() == height
                    window.grab().save(str(destination / f"qt-performance-live-{width}x{height}.png"))
            count = len(window.samples)
            window.close()
            wait_for(lambda: window._live_thread is None)
            app.processEvents()
            start = time.perf_counter()
            cached = monitor.ProbeWindow(live_enabled=True)
            windows.append(cached)
            cache_ms = round((time.perf_counter() - start) * 1000, 1)
            assert cached.source_state == "cached"
            assert len(cached.samples) == count
            assert all(item["status"] == "stale" for item in cached.samples)
            cached.close()
            print(json.dumps({
                "nodes": count, "first_connection_ms": cold_ms,
                "subsequent_refresh_ms": latest_ms, "cache_ready_ms": cache_ms,
                "same_worker_thread": True, "cached_state_is_stale": True,
            }, ensure_ascii=True))
        finally:
            for window in windows:
                window.close()
                wait_for(lambda: window._live_thread is None)
            app.processEvents()
            monitor.QSettings = original_factory


if __name__ == "__main__":
    main()

