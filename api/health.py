import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api._bootstrap import PROJECT_ROOT  # noqa: F401  # ensure path and env loaded


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
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        _cors_headers(self)
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
        return
