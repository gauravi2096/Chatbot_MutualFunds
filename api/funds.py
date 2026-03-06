import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api._bootstrap import PROJECT_ROOT  # noqa: F401
from phase_0.source_registry import load_registry
from phase_1.config import REGISTRY_PATH


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
        try:
            registry = load_registry(REGISTRY_PATH)
            data = [
                {"fund_id": s.fund_id, "fund_name": s.fund_name, "source_url": str(s.url)}
                for s in registry.sources
            ]
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            _cors_headers(self)
            self.end_headers()
            self.wfile.write(json.dumps({"detail": str(e)}).encode("utf-8"))
            return
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        _cors_headers(self)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))
        return
