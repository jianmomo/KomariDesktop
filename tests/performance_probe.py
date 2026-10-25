"""用相同数据与窗口尺寸比较刷新开销；不读写用户配置。"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time

from PySide6.QtCore import QEvent, QObject, QSettings
from PySide6.QtWidgets import QApplication, QWidget


class EventCounter(QObject):
    def __init__(self):
        super().__init__()
        self.counts = {"paint": 0, "style": 0, "layout": 0}

    def eventFilter(self, watched, event):
        event_key = {
            QEvent.Type.Paint: "paint",
            QEvent.Type.StyleChange: "style",
            QEvent.Type.LayoutRequest: "layout",
        }.get(event.type())
        if event_key and isinstance(watched, QWidget):
            self.counts[event_key] += 1
        return False


def main():
    parser = argparse.ArgumentParser()
    default_source = Path(__file__).resolve().parents[1] / "main.py"
    if not default_source.exists():
        default_source = Path(__file__).resolve().parents[1] / "qt_main_redesign.py"
    parser.add_argument("--source", default=str(default_source))
    parser.add_argument("--cycles", type=int, default=50)
    parser.add_argument("--network", action="store_true")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("perf_main", args.source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    created = [0]
    grid_rebuilds = [0]
    original_init = module.NodeCard.__init__
    original_layout = module.NodeCard._layout_metrics

    def card_init(self, *a, **kw):
        created[0] += 1
        original_init(self, *a, **kw)

    def card_layout(self, *a, **kw):
        grid_rebuilds[0] += 1
        return original_layout(self, *a, **kw)

    module.NodeCard.__init__ = card_init
    module.NodeCard._layout_metrics = card_layout
    with tempfile.TemporaryDirectory(prefix="komari-perf-") as temporary:
        settings_path = str(Path(temporary) / "settings.ini")
        module.QSettings = lambda *_: QSettings(settings_path, QSettings.Format.IniFormat)
        window = module.ProbeWindow(live_enabled=False)
        window.show()
        window.resize(392, 520)
        for _ in range(8):
            app.processEvents()
        window.timer.stop()
        counter = EventCounter()
        app.installEventFilter(counter)
        created[0] = grid_rebuilds[0] = 0
        samples = copy.deepcopy(window.samples)
        cpu0, wall0 = time.process_time(), time.perf_counter()
        for index in range(args.cycles):
            # 每次换新字典，重现网络 JSON 解码后的数据所有权；只改可见 CPU。
            updated = copy.deepcopy(samples)
            updated[0]["cpu"] += (index % 5) * 0.1
            window._on_live_success(updated, "12:00:00")
            app.processEvents()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        result = {
            "cycles": args.cycles,
            "refresh_cpu_ms": round((time.process_time() - cpu0) * 1000, 2),
            "refresh_wall_ms": round((time.perf_counter() - wall0) * 1000, 2),
            "cards_created": created[0],
            "metric_grids_rebuilt": grid_rebuilds[0],
            "events": dict(counter.counts),
        }
        if args.network:
            client = module.KomariClient()
            durations = []
            for _ in range(3):
                start = time.perf_counter()
                nodes = client.fetch_samples()
                durations.append(round((time.perf_counter() - start) * 1000, 1))
            result.update(network_ms=durations, network_nodes=len(nodes))
        app.removeEventFilter(counter)
        window.close()
        app.processEvents()
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()

