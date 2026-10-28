from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


assert main.normalize_komari_url("https://komari.example.invalid") == "https://komari.example.invalid"
assert main.normalize_komari_url("http://127.0.0.1:8765") == "http://127.0.0.1:8765"
assert main.normalize_komari_url("http://example.com") == main.KOMARI_BASE_URL
assert main.normalize_komari_url("https://user:password@example.com") == main.KOMARI_BASE_URL
assert main.normalize_komari_url("https://example.com/?token=secret") == main.KOMARI_BASE_URL
print("security_smoke: passed")
