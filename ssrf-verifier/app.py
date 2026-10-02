from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse
import json
import time
import threading


records = {}
lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):

    def send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # SSRF 요청을 받는 endpoint
        if path.startswith("/check/"):
            verification_id = path[len("/check/"):]

            if not verification_id:
                self.send_json(400, {
                    "error": "verification_id required"
                })
                return

            with lock:
                records[verification_id] = {
                    "received": True,
                    "time": time.time(),
                    "client": self.client_address[0],
                    "method": "GET",
                    "path": self.path
                }

            print(
                f"[SSRF VERIFY] request received: "
                f"id={verification_id}, "
                f"client={self.client_address[0]}, "
                f"path={self.path}",
                flush=True
            )

            self.send_json(200, {
                "received": True,
                "id": verification_id
            })
            return

        # Scanner가 요청 발생 여부를 확인하는 endpoint
        if path.startswith("/status/"):
            verification_id = path[len("/status/"):]

            with lock:
                record = records.get(verification_id)

            if record:
                self.send_json(200, record)
            else:
                self.send_json(200, {
                    "received": False,
                    "id": verification_id
                })

            return

        # health check
        if path == "/health":
            self.send_json(200, {
                "service": "ssrf-verifier",
                "status": "ok"
            })
            return

        self.send_json(404, {
            "error": "not found"
        })


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 9001), Handler)

    print(
        "[+] SSRF verifier listening on 0.0.0.0:9001",
        flush=True
    )

    server.serve_forever()