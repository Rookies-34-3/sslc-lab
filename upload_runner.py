import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


UPLOADS = Path("/uploads").resolve()
COMMANDS = {
    ".php": lambda path: ["php", str(path)],
    ".py": lambda path: ["python", str(path)],
    ".cgi": lambda path: ["/bin/sh", str(path)],
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            return self.respond(200, b"ok\n")
        if not path.startswith("/run/"):
            return self.respond(404, b"not found\n")
        target = (UPLOADS / unquote(path.removeprefix("/run/"))).resolve()
        if UPLOADS not in target.parents or not target.is_file():
            return self.respond(404, b"not found\n")
        command = COMMANDS.get(target.suffix.lower())
        if not command:
            return self.respond(400, b"unsupported executable type\n")
        try:
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
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, message, *args):
        print(message % args, flush=True)


ThreadingHTTPServer(("0.0.0.0", 9100), Handler).serve_forever()
