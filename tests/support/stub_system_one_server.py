"""A local HTTP server that stands in for a System One endpoint."""

import json
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass(frozen=True)
class ReceivedRequest:
    """One request the stub received: its method, path, headers and JSON body."""

    method: str
    path: str
    headers: dict[str, str]
    body: object


class StubSystemOneServer:
    """Answers every POST with the response set on it, and records each request.

    response_status and response_body are sent back as they are; a test sets
    them before the judge is asked. response_delay_seconds holds the response
    back, for a test of the judge's timeout.
    """

    def __init__(self) -> None:
        self.response_status = 200
        self.response_body: object = {"answers": {}}
        self.response_delay_seconds = 0.0
        self.received: list[ReceivedRequest] = []
        self._http_server = ThreadingHTTPServer(
            ("127.0.0.1", 0), self._build_handler_class()
        )
        # A held-back response is not waited for when the server stops.
        self._http_server.block_on_close = False
        self._thread = threading.Thread(
            target=self._http_server.serve_forever,
            # Checked this often for a stop, so that each test ends quickly.
            kwargs={"poll_interval": 0.01},
            daemon=True,
        )

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._http_server.server_address[:2]
        return str(host), int(port)

    @property
    def base_url(self) -> str:
        host, port = self.address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._http_server.shutdown()
        self._http_server.server_close()
        self._thread.join()

    def _build_handler_class(self) -> type[BaseHTTPRequestHandler]:
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                stub.received.append(
                    ReceivedRequest(
                        method=self.command,
                        path=self.path,
                        headers=dict(self.headers.items()),
                        body=json.loads(self.rfile.read(length) or b"null"),
                    )
                )
                time.sleep(stub.response_delay_seconds)
                body = json.dumps(stub.response_body).encode("utf-8")
                try:
                    self.send_response(stub.response_status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except OSError:
                    # The judge gave up waiting and closed the connection.
                    pass

            def log_message(self, format: str, *args: object) -> None:
                """Keep the test output free of request lines."""

        return Handler
