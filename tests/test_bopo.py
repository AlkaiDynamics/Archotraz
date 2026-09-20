from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from archotraz.bopo import BopoHttpControlPort


class RecordingHandler(BaseHTTPRequestHandler):
    requests: list[dict[str, object]] = []

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _record(self, body: object = None) -> None:
        self.__class__.requests.append(
            {
                "method": self.command,
                "path": self.path,
                "headers": {key.lower(): value for key, value in self.headers.items()},
                "body": body,
            }
        )

    def do_GET(self) -> None:  # noqa: N802
        self._record()
        payload = json.dumps({"ok": True, "db": {"ready": True}}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("x-request-id", "bopo-health-id")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        self._record(body)
        payload = json.dumps({"status": "pass", "testedAt": "now", "checks": []}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("x-request-id", "bopo-preflight-id")
        self.end_headers()
        self.wfile.write(payload)


class BopoHttpControlPortTests(unittest.TestCase):
    def setUp(self) -> None:
        RecordingHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_uses_unscoped_endpoint_and_correlates_request(self) -> None:
        port = BopoHttpControlPort(base_url=self.base_url)
        response = port.health()
        self.assertEqual(response.request_id, "bopo-health-id")
        recorded = RecordingHandler.requests[0]
        self.assertEqual(recorded["method"], "GET")
        self.assertEqual(recorded["path"], "/health")
        headers = recorded["headers"]
        self.assertIn("x-request-id", headers)
        self.assertNotIn("x-company-id", headers)

    def test_preflight_uses_company_scope_and_provider_type(self) -> None:
        port = BopoHttpControlPort(base_url=self.base_url, company_id="company-123")
        response = port.preflight("shell", {"runtimeCommand": "echo"})
        self.assertEqual(response.request_id, "bopo-preflight-id")
        recorded = RecordingHandler.requests[0]
        self.assertEqual(recorded["method"], "POST")
        self.assertEqual(recorded["path"], "/agents/runtime-preflight")
        headers = recorded["headers"]
        self.assertEqual(headers["x-company-id"], "company-123")
        self.assertIn("x-request-id", headers)
        self.assertEqual(
            recorded["body"],
            {"providerType": "shell", "runtimeConfig": {"runtimeCommand": "echo"}},
        )


if __name__ == "__main__":
    unittest.main()
