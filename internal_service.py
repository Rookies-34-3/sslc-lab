""" SSRF 공격 대상 역할을 하는 Docker 내부 전용 HTTP 서버

/course
→ og:image 포함 HTML

/ssrf-proof.svg
→ SSRF 성공 증명 이미지

/admin
→ 내부 전용 데이터 접근 예시

/health
→ Docker 상태 확인


"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
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


COURSE_HTML = """<!doctype html>
<html lang="ko"><head>
<meta charset="utf-8">
<meta property="og:title" content="SSRF SUCCESS - internal-service reached">
<meta property="og:image" content="/ssrf-proof.svg">
<title>SSRF SUCCESS</title>
</head><body>internal-service:9000 reached</body></html>
""".encode()
PROOF_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" rx="36" fill="#121722"/>
<rect x="44" y="44" width="1112" height="542" rx="28" fill="#1d2636" stroke="#ff6b19" stroke-width="6"/>
<circle cx="120" cy="120" r="28" fill="#35c46a"/>
<text x="170" y="140" fill="#35c46a" font-family="Arial, sans-serif" font-size="42" font-weight="700">INTERNAL RESPONSE RECEIVED</text>
<text x="600" y="300" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-size="92" font-weight="800">SSRF SUCCESS</text>
<text x="600" y="390" text-anchor="middle" fill="#ff9a3d" font-family="Arial, sans-serif" font-size="44">internal-service:9000 reached</text>
<rect x="226" y="448" width="748" height="82" rx="16" fill="#0b0f17"/>
<text x="600" y="502" text-anchor="middle" fill="#ffffff" font-family="monospace" font-size="34">SSLC{internal_network_access}</text>
</svg>""".encode()


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
        if path == "/ssrf-proof.svg":
            self.send_body(PROOF_SVG, "image/svg+xml")
            return
        data = RESPONSES.get(path)
        if data is None:
            self.send_error(404)
            return
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_body(body, "application/json")


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
