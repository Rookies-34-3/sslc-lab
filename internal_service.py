"""A fixed internal HTTP endpoint with no filesystem or URL-fetching interface."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in {"/", "/health"}:
            self.send_error(404)
            return
        body = json.dumps({"service": "sslc-lab-internal", "status": "ok"}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
