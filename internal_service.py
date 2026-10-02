"""Internal HTTP responses used by the SSRF lab."""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit


RESPONSES = {
    "/": {"service": "sslc-lab-internal", "status": "ok"},
    "/health": {"service": "sslc-lab-internal", "status": "ok"},
    "/public": {"title": "내부 학습 콘텐츠", "visibility": "public"},
    "/admin": {
        "service": "sslc-lab-internal",
        "visibility": "internal-only",
        "training_secret": "SSLC{internal_service_reached}",
    },
}
ROOT = Path(__file__).resolve().parent
COURSE_HTML = """<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta property="og:title" content="내부 전용 클라우드 보안 콘텐츠">
<meta property="og:image" content="/internal-thumbnail.png">
<title>내부 전용 콘텐츠</title>
</head><body>Docker 내부에서만 제공되는 실습용 콘텐츠입니다.</body></html>
""".encode()


class Handler(BaseHTTPRequestHandler):
    def send_body(self, body, content_type):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/course":
            self.send_body(COURSE_HTML, "text/html; charset=utf-8")
            return
        if path == "/internal-thumbnail.png":
            body = (ROOT / "static/reference/d91483bc8b5242850ae4.png").read_bytes()
            self.send_body(body, "image/png")
            return
        data = RESPONSES.get(path)
        if data is None:
            self.send_error(404)
            return
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_body(body, "application/json")


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
