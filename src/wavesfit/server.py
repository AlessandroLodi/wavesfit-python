"""Loopback-only HTTP/JSON and SSE server using the Python standard library."""

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlparse

from .config import default_config, validate_config
from .models import DEFINITIONS, Model, suggest
from .streaming import StreamingSession


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, session):
        self.session = session
        self.closing = threading.Event()
        super().__init__(address, Handler)

    def server_close(self):
        self.closing.set()
        self.session.close()
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _json(self, value, status=200):
        data = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/v1/state":
            return self._json(self.server.session.state())
        if path == "/v1/models":
            return self._json(
                {
                    "schema_version": "1.0",
                    "models": DEFINITIONS,
                    "default_config": default_config(),
                }
            )
        if path == "/v1/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while not self.server.closing.is_set():
                    data = json.dumps(
                        self.server.session.state(),
                        allow_nan=False,
                        separators=(",", ":"),
                    )
                    self.wfile.write(f"event: state\ndata: {data}\n\n".encode())
                    self.wfile.flush()
                    self.server.closing.wait(0.5)
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        name = "index.html" if path == "/" else path.lstrip("/")
        if name not in ("index.html", "app.js", "style.css"):
            return self._json({"error": "Not found"}, 404)
        data = files("wavesfit").joinpath("static", name).read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type", mimetypes.guess_type(name)[0] or "application/octet-stream"
        )
        self.send_header("Content-Length", str(len(data)))
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'",
        )
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).netloc != self.headers.get("Host"):
            return self._json({"error": "Cross-origin mutation rejected"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1048576:
                raise ValueError("Expected JSON body up to 1 MiB")
            data = json.loads(self.rfile.read(length))
            path = urlparse(self.path).path
            if path == "/v1/config":
                self.server.session.configure(validate_config(data))
                return self._json({"revision": self.server.session.revision})
            if path == "/v1/control":
                if data.get("action") not in ("pause", "resume"):
                    raise ValueError("action must be pause or resume")
                self.server.session.paused = data["action"] == "pause"
                return self._json({"paused": self.server.session.paused})
            if path == "/v1/suggest":
                state = self.server.session.state()
                observed = state["data"]
                if not observed:
                    raise ValueError("No observations yet")
                model = suggest(
                    Model.from_dict(data.get("model", state["config"]["model"])),
                    observed["x"],
                    observed["y"],
                )
                return self._json(model.to_dict())
            return self._json({"error": "Not found"}, 404)
        except (ValueError, KeyError, TypeError, OSError) as e:
            return self._json({"error": str(e)}, 400)


def create_server(config=None, port=8765):
    session = StreamingSession(config or default_config())
    try:
        return Server(("127.0.0.1", port), session)
    except OSError:
        try:
            return Server(("127.0.0.1", 0), session)
        except Exception:
            session.close()
            raise
