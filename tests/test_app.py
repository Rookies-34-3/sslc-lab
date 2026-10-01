"""Integration checks for the local Compose service. Run after docker compose up."""
import html
import json
import os
import re
import unittest
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("TEST_BASE_URL", "http://127.0.0.1:8080")
if urlparse(BASE).hostname not in {"127.0.0.1", "localhost"}:
    raise ValueError("These checks are limited to the local lab preview.")
SETTINGS = dict(line.split("=", 1) for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if "=" in line and not line.startswith("#"))
PASSWORD = SETTINGS["LAB_PASSWORD"]


class Browser:
    def __init__(self):
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))

    def request(self, path, data=None, headers=None):
        request = Request(urljoin(BASE, path), data=data, headers=headers or {})
        try:
            response = self.opener.open(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            return response.code, response.read(), response.headers, urlparse(response.url).path

    def get(self, path):
        return self.request(path)

    def token(self, path):
        status, body, _, _ = self.get(path)
        if status != 200:
            raise AssertionError(f"Could not open form: HTTP {status}")
        return re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', body)[1].decode()

    def form(self, path, fields):
        return self.request(path, urlencode(fields).encode(), {"Content-Type": "application/x-www-form-urlencoded"})

    def login(self, username):
        return self.form("/login", {"csrf_token": self.token("/login"), "userId": username, "password": PASSWORD})

    def upload(self, path, fields, field_name, filename, content):
        boundary = "sslc-" + uuid4().hex
        parts = []
        for key, value in fields.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode())
        parts.extend([content, f"\r\n--{boundary}--\r\n".encode()])
        return self.request(path, b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"})


class LabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        status, body, _, _ = Browser().get("/health")
        if status != 200 or json.loads(body).get("status") != "ok":
            raise AssertionError("Start the local lab with docker compose up -d --wait first.")

    def setUp(self):
        self.student = Browser()
        status, _, _, path = self.student.login("student1")
        self.assertEqual((status, path), (200, "/my-class/board/notice"))

    def test_login_and_session(self):
        anonymous = Browser()
        status, _, _, path = anonymous.get("/my-class/pbl")
        self.assertEqual((status, path), (200, "/login"))
        status, body, _, _ = anonymous.form("/login", {"csrf_token": anonymous.token("/login"), "userId": "student1", "password": "wrong-password"})
        self.assertEqual(status, 200)
        self.assertIn("아이디 또는 비밀번호".encode(), body)
        status, _, _, path = self.student.form("/logout", {"csrf_token": self.student.token("/my-class/pbl")})
        self.assertEqual((status, path), (200, "/login"))

    def test_csrf_required(self):
        for token in ["", "올바르지 않은 토큰"]:
            with self.subTest(token=token):
                status, _, _, _ = self.student.form("/my-class/board/write/qna", {"csrf_token": token, "title": "검증", "body": "검증"})
                self.assertEqual(status, 400)

    def test_board_create_search_and_attachment(self):
        title = "동작 확인 " + uuid4().hex[:8] + " O'Reilly"
        body = "첫 번째 줄\n<b>일반 텍스트</b>"
        content = "실습용 첨부파일 확인".encode()
        path = "/my-class/board/write/qna"
        status, detail, _, location = self.student.upload(path, {"csrf_token": self.student.token(path), "title": title, "body": body}, "file", "확인.txt", content)
        self.assertEqual(status, 200)
        self.assertRegex(location, r"/my-class/board/qna/\d+$")
        self.assertIn(html.escape(body).encode(), detail)
        self.assertIn(title, html.unescape(detail.decode()))
        download = re.findall(rb'href="(/download/\d+)"', detail)[0].decode()
        status, saved, headers, _ = self.student.get(download)
        self.assertEqual((status, saved), (200, content))
        self.assertIn("attachment", headers["Content-Disposition"])
        status, results, _, _ = self.student.get("/my-class/board/qna?" + urlencode({"content": title}))
        self.assertEqual(status, 200)
        self.assertIn(title, html.unescape(results.decode()))
        self.assertIn("총 <b>1</b>개".encode(), results)

    def test_notice_admin_only(self):
        path = "/my-class/board/write/notice"
        self.assertEqual(self.student.get(path)[0], 403)
        self.assertEqual(self.student.form(path, {"csrf_token": self.student.token("/my-class/pbl"), "title": "권한 검증", "body": "권한 검증"})[0], 403)
        admin = Browser()
        self.assertEqual(admin.login("admin")[0], 200)
        status, body, _, location = admin.form(path, {"csrf_token": admin.token(path), "title": "관리자 동작 확인 " + uuid4().hex[:8], "body": "로컬 기능 검증용 공지입니다."})
        self.assertEqual(status, 200)
        self.assertRegex(location, r"/my-class/board/notice/\d+$")
        self.assertIn("로컬 기능 검증용 공지".encode(), body)

    def test_pbl_upload_owner_permissions(self):
        path = "/my-class/pbl/1"
        content = b"PBL local integration check."
        filename = "pbl-check-" + uuid4().hex[:8] + ".txt"
        status, body, _, location = self.student.upload(path, {"csrf_token": self.student.token(path)}, "taskResult", filename, content)
        self.assertEqual((status, location), (200, path))
        self.assertIn(filename.encode(), body)
        download = re.findall(rb'href="(/download/\d+)"', body)[0].decode()
        self.assertEqual(self.student.get(download)[:2], (200, content))
        other = Browser()
        other.login("student2")
        self.assertEqual(other.get(download)[0], 403)
        admin = Browser()
        admin.login("admin")
        self.assertEqual(admin.get(download)[:2], (200, content))
        self.assertEqual(Browser().get(download)[3], "/login")

    def test_task_upload_owner_permissions(self):
        path = "/my-class/board/task/1"
        content = b"Assignment local integration check."
        filename = "task-check-" + uuid4().hex[:8] + ".txt"
        status, body, _, location = self.student.upload(path, {"csrf_token": self.student.token(path)}, "taskResult", filename, content)
        self.assertEqual((status, location), (200, path))
        self.assertIn(filename.encode(), body)
        download = re.findall(rb'href="(/download/\d+)"', body)[0].decode()
        self.assertEqual(self.student.get(download)[:2], (200, content))
        other = Browser()
        other.login("student2")
        self.assertEqual(other.get(download)[0], 403)
        admin = Browser()
        admin.login("admin")
        self.assertEqual(admin.get(download)[:2], (200, content))

    def test_support_inquiry_and_profile_permissions(self):
        for path, text in [("/customer", "국가 사이버보안 기본지침"), ("/customer/faq", "교육 과정 중 근로")]:
            status, body, _, _ = self.student.get(path)
            self.assertEqual(status, 200)
            self.assertIn(text.encode(), body)

        email = "student1-" + uuid4().hex[:8] + "@example.test"
        status, body, _, location = self.student.form("/mypage/my-information", {"csrf_token": self.student.token("/mypage/my-information"), "email": email, "phone": "010-1234-5678"})
        self.assertEqual((status, location), (200, "/mypage/my-information"))
        self.assertIn(email.encode(), body)

        title = "권한 분리 문의 " + uuid4().hex[:8]
        status, body, _, location = self.student.form("/customer/contact/write", {"csrf_token": self.student.token("/customer/contact/write"), "category": "기타", "title": title, "body": "작성자와 관리자만 확인하는 문의입니다."})
        self.assertEqual(status, 200)
        self.assertRegex(location, r"/customer/contact/\d+$")
        self.assertIn(title.encode(), body)
        other = Browser()
        other.login("student2")
        self.assertEqual(other.get(location)[0], 403)
        self.assertNotIn(title.encode(), other.get("/customer/contact")[1])
        self.assertNotIn(email.encode(), other.get("/mypage/my-information")[1])
        admin = Browser()
        admin.login("admin")
        self.assertEqual(admin.get(location)[0], 200)
        self.assertEqual(Browser().get(location)[3], "/login")

    def test_upload_validation(self):
        path = "/my-class/pbl/1"
        for name, content in [("empty.txt", b""), ("example.html", b"ordinary text")]:
            with self.subTest(name=name):
                self.assertEqual(self.student.upload(path, {"csrf_token": self.student.token(path)}, "taskResult", name, content)[0], 400)

    def test_unknown_pages(self):
        for path in ["/my-class/pbl/99999", "/my-class/board/task/99999", "/my-class/board/unknown", "/customer/resources/99999", "/customer/faq/99999", "/customer/contact/99999", "/download/99999"]:
            with self.subTest(path=path):
                self.assertEqual(self.student.get(path)[0], 404)

    def test_pages_and_categories(self):
        for path in ["/", "/index", "/my-class/pbl", "/my-class/pbl/1", "/my-class/board/notice", "/my-class/board/task", "/my-class/board/task/1", "/my-class/board/qna", "/my-class/board/write/qna", "/customer", "/customer/faq", "/customer/contact", "/customer/contact/write", "/mypage/my-information"]:
            with self.subTest(path=path):
                status, body, _, _ = self.student.get(path)
                self.assertEqual(status, 200)
                self.assertIn("학생1".encode(), body)
                self.assertNotIn(b"{{", body)
                self.assertNotRegex(body, rb'(?:src|href)=[\'"]https?://')
        _, index_body, _, _ = self.student.get("/")
        self.assertIn("현재 구현된 기능".encode(), index_body)
        for href in [b'/my-class/board/notice', b'/my-class/board/task', b'/my-class/board/qna', b'/my-class/pbl', b'/customer', b'/customer/faq', b'/customer/contact', b'/mypage/my-information']:
            self.assertIn(b'href="' + href + b'"', index_body)
        reference = json.loads((ROOT / "reference_data.json").read_text(encoding="utf-8"))["problems"]
        category = reference[0]["category"]
        _, body, _, _ = self.student.get("/my-class/pbl?" + urlencode({"category": category}))
        self.assertEqual(body.count(b"lab-pbl-card"), sum(item["category"] == category for item in reference))
        self.assertIn(b'role="tab"', body)

    def test_local_assets_and_headers(self):
        _, _, headers, _ = self.student.get("/my-class/pbl")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        assets = json.loads((ROOT / "reference_assets.json").read_text(encoding="utf-8"))
        for stylesheet in set(sum(assets["styles"].values(), [])):
            with self.subTest(stylesheet=stylesheet):
                status, content, _, _ = self.student.get(stylesheet)
                self.assertEqual(status, 200)
                self.assertNotRegex(content, rb'url\([^)]*https?://')
        for font in (ROOT / "static" / "reference").glob("*.woff2"):
            self.assertEqual(font.read_bytes()[:4], b"wOF2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
