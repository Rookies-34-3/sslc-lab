'''
디렉터리 리스팅으로 노출된 업로드 파일 중
PHP / Python / CGI 파일을 실행하기 위한 runner 서버
'''

import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


#/uploads라는 파일 경로 객체로 선언
UPLOADS = Path("/uploads").resolve()                                           

#확장자와 실행 방법 매핑
COMMANDS = {
    ".php": lambda path: ["php", str(path)],
    ".py": lambda path: ["python", str(path)],
    ".cgi": lambda path: ["/bin/sh", str(path)],
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 클라이언트가 GET 요청 처리
        path = urlsplit(self.path).path
        if path == "/health":
            return self.respond(200, b"ok\n")

        # /run/으로 시작하는 요청만 실행 대상으로 처리
        if not path.startswith("/run/"):
            return self.respond(404, b"not found\n")

        # /run/ 이후의 경로를 실제 /uploads 경로와 결합
        target = (UPLOADS / unquote(path.removeprefix("/run/"))).resolve() 
        if UPLOADS not in target.parents or not target.is_file():
            return self.respond(404, b"not found\n")
        
        command = COMMANDS.get(target.suffix.lower())
        # 지원하지 않는 확장자는 실행하지 않음
        if not command:
            return self.respond(400, b"unsupported executable type\n")
        try:      
            # 코드 실행
            result = subprocess.run(                                              
                command(target),
                cwd="/tmp",
                env={"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8"},
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=5,
            )
            output = result.stdout + result.stderr
            return self.respond(200, output or f"exit={result.returncode}\n".encode())
        except subprocess.TimeoutExpired:
            return self.respond(504, b"execution timed out\n")

    def respond(self, status, body):
         # HTTP 응답 생성
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, message, *args):
        print(message % args, flush=True)


ThreadingHTTPServer(("0.0.0.0", 9100), Handler).serve_forever()
