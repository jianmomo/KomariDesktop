from pathlib import Path
import sys
import tempfile

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings, Qt
APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))
if (APP_ROOT / "main.py").exists():
    from main import APP_NAME, KomariClient, ProbeWindow
    import main as monitor
else:
    from qt_main_redesign import APP_NAME, KomariClient, ProbeWindow
    import qt_main_redesign as monitor

mapped = KomariClient._build_samples(
    [{
        "uuid": "live-1", "name": "测试节点", "group": "测试", "region": "🇨🇳",
        "mem_total": 1000, "traffic_limit": 2048, "expired_at": "2027-01-01T00:00:00Z",
    }],
    {"live-1": {
        "online": True, "cpu": 12.5, "ram": 250, "ram_total": 1000,
        "net_in": 2048, "net_out": 1024, "net_total_up": 1000, "net_total_down": 2000,
        "ping": {"1": {"latest": 42, "loss": 0}},
    }},
)
assert mapped[0]["cpu"] == 12.5
assert mapped[0]["memory"] == 25.0
assert mapped[0]["upload"] == 1.0 and mapped[0]["download"] == 2.0
assert mapped[0]["latency"]["移动"] == 42 and mapped[0]["loss"]["联通"] is None
assert mapped[0]["traffic_label"] == "累计"
assert mapped[0]["code"] == "CN"
assert KomariClient._number(True) is None
bounded = KomariClient._build_samples(
    [{"uuid": "u" * 500, "name": "n" * 500, "group": "g" * 500, "region": "r" * 500}],
    {},
)[0]
assert len(bounded["id"]) == 128
assert len(bounded["name"]) == 160
assert len(bounded["region"]) == 128

app = QApplication([])
temporary = tempfile.TemporaryDirectory(prefix="komari-behavior-")
settings_path = str(Path(temporary.name) / "settings.ini")
monitor.QSettings = lambda *_: QSettings(settings_path, QSettings.Format.IniFormat)
window = ProbeWindow(live_enabled=False)
window.show()
window.resize(392, 520)
for _ in range(8):
    app.processEvents()
compact, rects, total = window._layout()
assert total == 6 and rects, (total, rects)
for card in window._cards:
    for block in card.metric_blocks:
        if block.unit == " KiB/s" and block.unit_label.isVisible():
            assert block.value_label.geometry().right() < block.unit_label.geometry().left(), (
                "速率数值和单位发生挤压", block.value_label.geometry(), block.unit_label.geometry()
            )
        assert card.main_layout.sizeHint().height() <= card.height()

def assert_no_card_overlap():
    rects = sorted((rect for rect, _ in window._layout_rects), key=lambda rect: (rect.y(), rect.x()))
    for previous, current in zip(rects, rects[1:]):
        if previous.intersects(current):
            raise AssertionError(f"卡片发生重叠: {previous.getRect()} -> {current.getRect()}")

assert_no_card_overlap()

# 宽窗口自动多列，卡片等宽且互不挤压。
window.resize(1100, 800)
for _ in range(8):
    app.processEvents()
card_widths = [card.width() for card in window._cards]
assert max(card_widths) - min(card_widths) <= 1, card_widths
for card in window._cards:
    for block in card.metric_blocks:
        if block.unit == " KiB/s" and block.unit_label.isVisible():
            assert block.value_label.geometry().right() < block.unit_label.geometry().left(), (
                "宽布局速率数值和单位发生挤压", block.value_label.geometry(), block.unit_label.geometry()
            )
assert_no_card_overlap()
window.samples[0]["name"] = "超长节点名称-" + "X" * 120
window._refresh_cards(force=True)
for _ in range(8):
    app.processEvents()
assert_no_card_overlap()
old_page = window.page_index
window.next_page()
assert window.page_index != old_page or window.page_count == 1
window.clear_page_pin()
window.resize(452, 538)
for _ in range(8):
    app.processEvents()
window.jump_to_page(2)
expected_fixed_ids = tuple(card.item["id"] for card in window._cards)
window.jump_to_page(2, pin=True)
assert window.page_pinned and tuple(window.pinned_node_ids) == expected_fixed_ids
assert "固定" in window.view_label.text()
window.clear_page_pin()
assert not window.page_pinned
window.toggle_editing()
window.refresh_spin.setValue(30)
window.carousel_spin.setValue(20)
assert window.refresh_interval_ms == 30_000
assert window.carousel_interval_ms == 20_000
assert int(window.settings.value("refreshSeconds")) == 30
assert int(window.settings.value("carouselSeconds")) == 20
old_carousel = window.carousel_enabled
window.carousel_button.click()
assert window.carousel_enabled is not old_carousel
window.toggle_editing()
window.sort_mode = "cpu"
window.group_mode = False
cpu_values = [item["cpu"] for item in window._items() if isinstance(item["cpu"], (int, float))]
assert cpu_values == sorted(cpu_values, reverse=True)
assert window._items()[0]["name"] != ""
first = window._items()[0]
before = len(window.selected_ids)
window._toggle_selected(first)
assert len(window.selected_ids) == before - 1
window._toggle_selected(first)
assert len(window.selected_ids) == before
window.toggle_editing()
app.processEvents()
assert window.editing and window.action_row.isVisible()
old_theme = window.theme
window.cycle_theme()
assert old_theme == "skin1" and window.theme == "skin2"
window.theme_button.click()
assert window.theme == "skin3"
for expected_theme in ("skin4", "skin5", "skin6", "skin1"):
    window.cycle_theme()
    for _ in range(4):
        app.processEvents()
    assert window.theme == expected_theme
    assert_no_card_overlap()
    card = window._cards[0]
    assert card.latency_widget.isVisible() == (expected_theme in {"skin1", "skin2"})
    assert card.latency_rows_widget.isVisible() == (expected_theme in {"skin3", "skin4"})
    assert card.latency_blocks_widget.isVisible() == (expected_theme == "skin5")
    assert card.trend_panel.isVisible() == (expected_theme == "skin6")
    assert card.details_widget.isVisible()
old_opacity = window.opacity_percent
window.opacity_up_button.click()
assert window.opacity_percent == min(100, old_opacity + 5)
old_page = window.page_index
window.next_button.click()
assert window.page_index != old_page or window.page_count == 1
window.toggle_editing()
assert window.locked and not window.action_row.isVisible()
window.theme = "skin1"
assert window._colors()["accent"].name().lower() == "#2d2e32"
window.close()
app.quit()
temporary.cleanup()
print({"layout": True, "page_count": window.page_count, "selection": True, "theme": True})

