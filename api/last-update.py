import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api._bootstrap import PROJECT_ROOT  # noqa: F401
from phase_0.source_registry import load_registry
from phase_1.config import REGISTRY_PATH, FUNDS_JSON


def _cors_headers(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        _cors_headers(self)
        self.end_headers()
        return

    def do_GET(self):
        ts = ""
        try:
            registry = load_registry(REGISTRY_PATH)
            ts = registry.last_data_update or ""
            if not ts and FUNDS_JSON.exists():
                data = json.loads(FUNDS_JSON.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("last_updated"):
                    ts = data["last_updated"]
        except Exception:
            pass
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        _cors_headers(self)
        self.end_headers()
        self.wfile.write(json.dumps({"last_data_update": ts}).encode("utf-8"))
        return
