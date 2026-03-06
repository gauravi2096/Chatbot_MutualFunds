import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api._bootstrap import PROJECT_ROOT  # noqa: F401
from phase_2.orchestration import chat


def _cors_headers(handler: BaseHTTPRequestHandler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")


def _read_body(handler: BaseHTTPRequestHandler) -> bytes:
    content_length = int(handler.headers.get("Content-Length", 0))
    if content_length:
        return handler.rfile.read(content_length)
    return b""


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        _cors_headers(self)
        self.end_headers()
        return

    def do_POST(self):
        try:
            body = _read_body(self)
            payload = json.loads(body.decode("utf-8")) if body else {}
            message = (payload.get("message") or "").strip()
            if not message:
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                _cors_headers(self)
                self.end_headers()
                self.wfile.write(json.dumps({"detail": "message must be non-empty"}).encode("utf-8"))
                return
            fund_id = payload.get("fund_id")
            result = chat(query=message, fund_id=fund_id)
            data = {
                "message": result.get("message", ""),
                "source_url": result.get("source_url", ""),
                "last_data_update": result.get("last_data_update", ""),
            }
        except json.JSONDecodeError as e:
            self.send_response(400)
            self.send_header("Content-type", "application/json")
            _cors_headers(self)
            self.end_headers()
            self.wfile.write(json.dumps({"detail": str(e)}).encode("utf-8"))
            return
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
