"""Small local HTTP servers that stand in for outside services in integration tests."""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def unused_port() -> int:
    """Returns a local port nothing listens on, for tests of an unreachable service."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def start_in_background(server: ThreadingHTTPServer, test_class) -> None:
    """Serves in a daemon thread until the test class's clean-up stops the server."""
    threading.Thread(target=server.serve_forever, daemon=True).start()
    test_class.addClassCleanup(server.server_close)
    test_class.addClassCleanup(server.shutdown)


class FakeMattermost(ThreadingHTTPServer):
    """Records the webhook messages and answers 200, like a Mattermost incoming webhook.

    Set `status` and `reply` to answer with an error instead.
    """

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _FakeMattermostHandler)
        self.messages = []
        self.headers = []
        self.status = 200
        self.reply = b"ok"

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_port}/hooks/test"


class _FakeMattermostHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.server.messages.append(json.loads(self.rfile.read(length)))
        self.server.headers.append(dict(self.headers))
        self.send_response(self.server.status)
        self.send_header("Content-Length", str(len(self.server.reply)))
        self.end_headers()
        self.wfile.write(self.server.reply)

    def log_message(self, format, *args):
        pass
