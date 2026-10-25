from __future__ import annotations

from pathlib import Path
import sys
import tempfile

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))
if (APP_ROOT / "main.py").exists():
    from main import APP_NAME, ProbeWindow
    import main as monitor
else:
    from qt_main_redesign import APP_NAME, ProbeWindow
    import qt_main_redesign as monitor


def main() -> int:
    app = QApplication([])
    results = []
    sizes = [(320, 360), (360, 420), (392, 520), (500, 520), (640, 720), (760, 640), (1100, 800)]
    temporary = tempfile.TemporaryDirectory(prefix="komari-layout-")
    settings_path = str(Path(temporary.name) / "settings.ini")
    original_factory = monitor.QSettings
    monitor.QSettings = lambda *_: QSettings(settings_path, QSettings.Format.IniFormat)
    settings = monitor.QSettings()
    original_settings = {key: settings.value(key) for key in settings.allKeys()}
    try:
        for width, height in sizes:
            settings.clear()
            window = ProbeWindow(live_enabled=False)
            window.show()
            window.resize(width, height)
            for _ in range(8):
                app.processEvents()
            mode, _, total = window._layout()
            expected_cards = min(window.page_size, total)
            pixmap = window.grab()
            # Windows 高 DPI 下 QWidget::grab 返回物理像素，先换算回逻辑尺寸再比较。
            dpr = float(pixmap.devicePixelRatio()) or 1.0
            logical_size = [round(pixmap.width() / dpr), round(pixmap.height() / dpr)]
            painted = not pixmap.isNull() and logical_size == [width, height]
            output = Path(__file__).with_name(f"qt-probe-offscreen-{width}x{height}.png")
            pixmap.save(str(output))
            result = {
                "size": [width, height],
                "mode": mode,
                "cards": len(window._cards),
                "page_size": window.page_size,
                "page_count": window.page_count,
                "painted": painted,
            }
            results.append(result)
            if not painted or len(window._cards) != expected_cards:
                raise SystemExit(f"响应式布局失败: {result}, expected_cards={expected_cards}")
            window.close()
            app.processEvents()
        # 六款皮肤都走同一套自适应布局，切换后不能产生卡片相交或无效颜色。
        for theme in ("skin1", "skin2", "skin3", "skin4", "skin5", "skin6"):
            settings.clear()
            window = ProbeWindow(live_enabled=False)
            window.theme = theme
            window._apply_theme()
            window._refresh_cards(force=True)
            window.show()
            window.resize(392, 520)
            for _ in range(8):
                app.processEvents()
            rects = sorted((rect for rect, _ in window._layout_rects), key=lambda rect: (rect.y(), rect.x()))
            if any(previous.intersects(current) for previous, current in zip(rects, rects[1:])):
                raise SystemExit(f"皮肤布局重叠: {theme}")
            output = Path(__file__).with_name(f"qt-probe-{theme}-392x520.png")
            window.grab().save(str(output))
            window.close()
            app.processEvents()
    finally:
        settings.clear()
        for key, value in original_settings.items():
            settings.setValue(key, value)
        settings.sync()
        monitor.QSettings = original_factory
        temporary.cleanup()
    first = Path(__file__).with_name("qt-probe-offscreen-360x420.png")
    preview = Path(__file__).with_name("qt-probe-offscreen.png")
    if first.exists():
        if preview.exists():
            preview.unlink()
        first.replace(preview)
    print(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

