#임포트 
import base64
import hmac
import json
import math
import os
import re
import secrets
import sys
import time
from datetime import timedelta
from functools import wraps
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import pymysql
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parent                                                  # root폴더 지정
ASSETS = json.loads((ROOT / "reference_assets.json").read_text(encoding="utf-8"))       # asset로드 화면 리소스
REFERENCE = json.loads((ROOT / "reference_data.json").read_text(encoding="utf-8"))      # 화면에 표시할 데이터 로드

PROBLEMS = {item["id"]: item for item in REFERENCE["problems"]}                         # pbl 목록 
TASKS = {item["id"]: item for item in REFERENCE["tasks"]}                               # 과제 목록 

UPLOADS = Path(os.environ.get("UPLOAD_DIR", ROOT / "instance" / "uploads"))             # 업로드 저장 파일 위치 /app/instance/uploads
ASSIGNMENT_FILE_OFFSET = 1_000_000                                                      # 과제 파일 id 오프셋
INQUIRY_FILE_OFFSET = 2_000_000                                                         # 문의 글 파일 id 오프셋
INQUIRY_CATEGORIES = ("출결문의", "온라인 교육", "오프라인 교육", "PBL/과제", "프로젝트", "기타")# 문의하기 카테고리들 
CONTENT_LIMIT = 256 * 1024
THUMBNAIL_LIMIT = 2 * 1024 * 1024

# allow list 
THUMBNAIL_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "image/svg+xml": "svg"}
EXTENSIONS = {"pdf", "txt", "zip", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "hwp", "hwpx", "rtf", "png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)


app.config.update(                                                                      #flask 설정
    SECRET_KEY=os.environ["SECRET_KEY"],                                                #세션 서명에 사용 
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,                                                #업로드 크기 
    SESSION_COOKIE_NAME="sslc_lab_session",                                             #세션 정보 쿠키 이름
    SESSION_COOKIE_HTTPONLY=True,                                                       #http only설정
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",   #secure설정
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),                                      #세션 타임
)


def db():
    # db 연결
    if "db" not in g:
        g.db = pymysql.connect(
            host=os.environ.get("DB_HOST", "db"),                                       
            user=os.environ.get("DB_USER", "sslc_app"),
            password=os.environ["MYSQL_PASSWORD"],
            database=os.environ.get("DB_NAME", "sslc_lab"),
            charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5, read_timeout=10, write_timeout=10, autocommit=True,
        )
    return g.db


def query(sql, values=(), one=False):
    # 안전하게 db 실행
    with db().cursor() as cursor:
        cursor.execute(sql, values)
        return cursor.fetchone() if one else cursor.fetchall()


def unsafe_query(sql, one=False):
    # 취약하게 db 실행 
    with db().cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchone() if one else cursor.fetchall()


@app.teardown_appcontext
def close_db(error=None):
    #flask 종료시 db 종료
    connection = g.pop("db", None)
    if connection:
        connection.close()


@app.before_request
def load_user_and_check_csrf():
    #요청 처리 전에 csrf 토큰 
    g.user = None
    if request.endpoint == "static":
        return
    if session.get("user_id"):
        g.user = query("SELECT id, username, display_name, role FROM users WHERE id=%s", (session["user_id"],), one=True)
    
    if request.method == "POST":
    #post시에 검사 
        expected = session.get("csrf_token", "")
        provided = request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(expected.encode("utf-8"), provided.encode("utf-8")):
            abort(400, description="페이지를 새로고침한 뒤 다시 등록해주세요.")


@app.after_request
def security_headers(response):
    #응답 헤더에 추가 
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    vulnerable_xss = request.endpoint == "login" or (
        request.endpoint == "board" and request.view_args and request.view_args.get("kind") == "qna"
    )
    script_policy = "script-src 'self' 'unsafe-inline';" if vulnerable_xss else "script-src 'self';"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; " + script_policy + " connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.context_processor
def template_context():
    #Flask에서 템플릿을 렌더링시 실행
    # 세션에 csrf_token이 없으면 새로 만들고, 있으면 기존 값을 그대로 가져옴 및 데이터 공급
    token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return {"current_user": g.get("user"), "csrf_token": token, "assets": ASSETS, "ref": lambda path: ASSETS["resources"].get(path, "data:,")}


def login_required(view):
    # 기존 라우트 함수의 이름과 메타데이터 유지 인증 데코레이터
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            # 로그인되지 않은 사용자는 로그인 페이지로 이동
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def render_page(template, asset_page, active, **context):
    return render_template(template, asset_page=asset_page, active=active, **context)


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og_title = ""
        self.og_image = ""
        self.title_parts = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "meta":
            name = (attributes.get("property") or attributes.get("name") or "").lower()
            if name == "og:title":
                self.og_title = attributes.get("content", "")
            elif name == "og:image":
                self.og_image = attributes.get("content", "")

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)


def fetch_http(url, limit):
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("http 또는 https URL을 입력해주세요.")

    started = time.perf_counter()
    try:
        response = urlopen(Request(url, headers={"User-Agent": "SSLC-Lab-Preview/1.0"}), timeout=3)
    except HTTPError as error:
        raise ValueError(f"대상 서버가 HTTP {error.code}을 반환했습니다.") from error

    with response:
        content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError("가져온 콘텐츠가 허용된 크기를 초과했습니다.")
        return {
            "status": response.getcode(),
            "final_url": response.geturl(),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "content_type": response.headers.get_content_type().lower(),
            "charset": response.headers.get_content_charset() or "utf-8",
            "body": content,
        }


def fetch_external_content(url):
    page = fetch_http(url, CONTENT_LIMIT)
    if page["content_type"] in THUMBNAIL_TYPES:
        title = ""
        thumbnail_url = page["final_url"]
        thumbnail = page
    else:
        try:
            text = page["body"].decode(page["charset"], errors="replace")
        except LookupError:
            text = page["body"].decode("utf-8", errors="replace")
        parser = MetadataParser()
        parser.feed(text)
        if not parser.og_image:
            raise ValueError("콘텐츠에서 og:image 썸네일을 찾지 못했습니다.")
        title = (parser.og_title or "".join(parser.title_parts)).strip()
        thumbnail_url = urljoin(page["final_url"], parser.og_image)
        thumbnail = fetch_http(thumbnail_url, THUMBNAIL_LIMIT)

    extension = THUMBNAIL_TYPES.get(thumbnail["content_type"])
    if not extension:
        raise ValueError("PNG, JPEG, GIF, WebP, SVG 썸네일만 가져올 수 있습니다.")
    return {
        "title": title[:200],
        "source_url": page["final_url"],
        "source_status": page["status"],
        "thumbnail_url": thumbnail_url,
        "thumbnail_status": thumbnail["status"],
        "elapsed_ms": page["elapsed_ms"] + thumbnail["elapsed_ms"],
        "mime_type": thumbnail["content_type"],
        "extension": extension,
        "image": thumbnail["body"],
        "data_url": "data:" + thumbnail["content_type"] + ";base64," + base64.b64encode(thumbnail["body"]).decode(),
    }


@app.get("/my-class")
def my_class_root():
    return redirect(url_for("/index") if g.user else url_for("login"))


@app.get("/")
@app.get("/index")
@login_required
def feature_index():
    links = [
        ("공지사항", url_for("board", kind="notice"), "취약점 미적용 · SQL Injection 비교용 안전 검색"),
        ("과제", url_for("task_board"), "파일 확장자 우회 · 파일명 경로 이동 · 업로드 코드 실행"),
        ("학습게시판", url_for("board", kind="qna"), "SQL Injection · Reflected XSS · 파일 업로드 취약점"),
        ("PBL", url_for("pbl"), "파일 확장자 우회 · 파일명 경로 이동 · 업로드 코드 실행"),
        ("지식컨텐츠", url_for("knowledge_content"), "SSRF · 외부 콘텐츠 썸네일 가져오기"),
        ("자료실", url_for("resources"), "취약점 미적용"),
        ("FAQ", url_for("faq"), "취약점 미적용"),
        ("문의하기", url_for("inquiries"), "비밀글 쿼리 파라미터 제거 권한 우회 · 파일 업로드 취약점"),
        ("마이페이지", url_for("mypage", user_id=g.user["id"]), "IDOR · REST API 사용자 프로필 조회/수정"),
        ("로그인", url_for("login"), "Reflected XSS · 로그인 실패 메시지"),
        ("업로드 디렉터리", "/uploads/", "디렉터리 인덱싱 · 인증 없는 파일 접근 · PHP/Python/CGI 실행"),
        ("관리자 페이지", url_for("admin_dashboard"), "인증 없는 관리자 페이지 노출"),
    ]
    return render_page("index.html", "notice", "index", links=links)


@app.get("/pre-course/list")
@login_required
def knowledge_content():
    contents = query("SELECT id, title, source_url, thumbnail_path, created_at FROM external_contents ORDER BY id DESC")
    return render_page("knowledge.html", "knowledge", "knowledge", contents=contents)


@app.route("/pre-course/write", methods=["GET", "POST"])
@login_required
def write_knowledge_content():
    title = request.form.get("title", "").strip()[:200]
    source_url = request.form.get("url", "").strip()[:2048]
    preview = None
    error = None
    if request.method == "POST":
        action = request.form.get("action")
        if action not in {"preview", "save"}:
            abort(400)
        try:
            preview = fetch_external_content(source_url)
            title = title or preview["title"]
            if not title:
                raise ValueError("콘텐츠 제목을 입력해주세요.")
            if action == "save":
                folder = UPLOADS / "knowledge"
                folder.mkdir(parents=True, exist_ok=True)
                stored_name = "knowledge/" + uuid4().hex + "." + preview["extension"]
                (UPLOADS / stored_name).write_bytes(preview["image"])
                query(
                    "INSERT INTO external_contents (owner_id, title, source_url, thumbnail_path) VALUES (%s,%s,%s,%s)",
                    (g.user["id"], title, source_url, stored_name),
                )
                flash("외부 콘텐츠를 추가했습니다.", "success")
                return redirect(url_for("knowledge_content"))
        except (URLError, TimeoutError, OSError, ValueError) as fetch_error:
            error = f"썸네일을 가져오지 못했습니다: {fetch_error}"
    return render_page(
        "knowledge_form.html",
        "knowledge",
        "knowledge",
        form_title=title,
        form_url=source_url,
        preview=preview,
        preview_error=error,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
#로그인
    if request.method == "POST":
        username = request.form.get("userId", "")[:80]
        user = query("SELECT * FROM users WHERE username=%s", (username,), one=True)
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            return redirect(url_for("board", kind="notice"))
        flash(username + " 계정의 아이디 또는 비밀번호를 확인해주세요.", "error")
    elif g.user:
        return redirect(url_for("board", kind="notice"))
    return render_page("login.html", "login", "login")


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.get("/my-class/board")
@login_required
def board_root():
    return redirect(url_for("board", kind="qna"))


@app.get("/my-class/board/task")
@login_required
def task_board():
    search = request.args.get("content", "").strip()[:200]
    tasks = [task for task in TASKS.values() if not search or search.lower() in task["title"].lower()]
    submitted = {
        row["problem_id"] - ASSIGNMENT_FILE_OFFSET
        for row in query(
            "SELECT DISTINCT problem_id FROM files WHERE owner_id=%s AND problem_id BETWEEN %s AND %s",
            (g.user["id"], ASSIGNMENT_FILE_OFFSET, ASSIGNMENT_FILE_OFFSET + 999_999),
        )
    }
    return render_page("task_board.html", "task", "task", tasks=tasks, submitted=submitted, search=search)


@app.route("/my-class/board/task/<int:task_id>", methods=["GET", "POST"])
@login_required
def task_detail(task_id):
    task = TASKS.get(task_id)
    if not task:
        abort(404)
    submission_key = ASSIGNMENT_FILE_OFFSET + task_id
    if request.method == "POST":
        if not save_upload(request.files.get("taskResult"), problem_id=submission_key, area="task"):
            abort(400, description="제출할 파일을 선택해주세요.")
        flash("과제 파일 제출을 완료했어요.", "success")
        return redirect(url_for("task_detail", task_id=task_id))
    submissions = query(
        "SELECT id, original_name, created_at FROM files WHERE owner_id=%s AND problem_id=%s ORDER BY id DESC",
        (g.user["id"], submission_key),
    )
    return render_page("task.html", "task", "task", task=task, submissions=submissions)


def check_kind(kind):
    if kind not in {"notice", "qna"}:
        abort(404)


@app.get("/my-class/board/<kind>")
@login_required
def board(kind):
    check_kind(kind)
    search = request.args.get("content", "").strip()[:200]
    page = max(1, request.args.get("page", 1, type=int))
    try:
        if kind == "notice":
            values = (kind, "%" + search + "%", "%" + search + "%")
            where = "p.kind=%s AND (p.title LIKE %s OR p.body LIKE %s)"
            total = query("SELECT COUNT(*) AS n FROM posts p WHERE " + where, values, one=True)["n"]
            pages = max(1, math.ceil(total / 10))
            page = min(page, pages)
            posts = query(
                "SELECT p.*, u.display_name, EXISTS(SELECT 1 FROM files f WHERE f.post_id=p.id) AS has_file "
                "FROM posts p JOIN users u ON u.id=p.author_id WHERE " + where + " ORDER BY p.created_at DESC, p.id DESC LIMIT 10 OFFSET %s",
                (*values, (page - 1) * 10),
            )
        else:
            where = "p.kind='qna' AND (p.title LIKE '%" + search + "%' OR p.body LIKE '%" + search + "%')"
            total = unsafe_query("SELECT COUNT(*) AS n FROM posts p WHERE " + where, one=True)["n"]
            pages = max(1, math.ceil(total / 10))
            page = min(page, pages)
            posts = unsafe_query(
                "SELECT p.*, u.display_name, EXISTS(SELECT 1 FROM files f WHERE f.post_id=p.id) AS has_file "
                "FROM posts p JOIN users u ON u.id=p.author_id WHERE " + where + " ORDER BY p.created_at DESC, p.id DESC LIMIT 10 OFFSET " + str((page - 1) * 10)
            )
    except pymysql.MySQLError as error:
        return render_page("board.html", kind, kind, kind=kind, heading="강의 질문", posts=[], total=0, search=search, page=1, pages=1, sql_error=str(error)), 500
    return render_page("board.html", kind, kind, kind=kind, heading="공지사항" if kind == "notice" else "강의 질문", posts=posts, total=total, search=search, page=page, pages=pages, sql_error=None)


@app.get("/my-class/board/<kind>/<int:post_id>")
@login_required
def post_detail(kind, post_id):
    check_kind(kind)
    post = query("SELECT p.*, u.display_name FROM posts p JOIN users u ON u.id=p.author_id WHERE p.id=%s AND p.kind=%s", (post_id, kind), one=True)
    if not post:
        abort(404)
    query("UPDATE posts SET views=views+1 WHERE id=%s", (post_id,))
    post["views"] += 1
    attachments = query("SELECT id, original_name FROM files WHERE post_id=%s ORDER BY id", (post_id,))
    return render_page("post.html", "detail", kind, kind=kind, post=post, attachments=attachments)


def save_upload(upload, *, post_id=None, problem_id=None, area="files"):
    if not upload or not upload.filename:
        return None
    name = upload.filename.replace("\\", "/")
    if not name or len(name) > 180 or any(ord(char) < 32 for char in name):
        abort(400, description="파일 이름을 확인해주세요.")
    if not any("." + extension in name.lower() for extension in EXTENSIONS):
        abort(400, description="지원하는 문서·이미지·압축 파일을 선택해주세요.")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    upload_root = UPLOADS.resolve()
    candidate = upload_root / str(g.user["id"]) / area / name
    target = candidate.with_name(uuid4().hex[:8] + "-" + candidate.name).resolve()
    if upload_root not in target.parents:
        abort(400, description="파일 경로를 확인해주세요.")
    target.parent.mkdir(parents=True, exist_ok=True)
    stored_name = target.relative_to(upload_root).as_posix()
    if len(stored_name) > 80:
        abort(400, description="파일 이름을 줄여주세요.")
    try:
        with target.open("xb") as stream:
            upload.save(stream)
        size = target.stat().st_size
        if size == 0:
            abort(400, description="빈 파일은 제출할 수 없습니다.")
        with db().cursor() as cursor:
            cursor.execute("INSERT INTO files (owner_id, post_id, problem_id, original_name, stored_name, size_bytes) VALUES (%s,%s,%s,%s,%s,%s)", (g.user["id"], post_id, problem_id, name, stored_name, size))
            return cursor.lastrowid
    except BaseException:
        target.unlink(missing_ok=True)
        raise


@app.route("/my-class/board/write/<kind>", methods=["GET", "POST"])
@login_required
def write_post(kind):
    check_kind(kind)
    if kind == "notice" and g.user["role"] != "admin":
        abort(403)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        if not title or len(title) > 200 or not body or len(body) > 10000:
            abort(400, description="제목은 1~200자, 본문은 1~10,000자로 입력해주세요.")
        db().begin()
        try:
            with db().cursor() as cursor:
                cursor.execute("INSERT INTO posts (kind, author_id, title, body) VALUES (%s,%s,%s,%s)", (kind, g.user["id"], title, body))
                post_id = cursor.lastrowid
            save_upload(request.files.get("file"), post_id=post_id, area=kind)
            db().commit()
        except BaseException:
            db().rollback()
            raise
        return redirect(url_for("post_detail", kind=kind, post_id=post_id))
    return render_page("write.html", "write", kind, kind=kind, heading="공지사항 작성" if kind == "notice" else "강의 질문 작성")


@app.get("/my-class/pbl")
@login_required
def pbl():
    category = request.args.get("category", "")
    categories = list(dict.fromkeys(problem["category"] for problem in PROBLEMS.values()))
    problems = [problem for problem in PROBLEMS.values() if not category or problem["category"] == category]
    submissions = {row["problem_id"] for row in query("SELECT DISTINCT problem_id FROM files WHERE owner_id=%s AND problem_id IS NOT NULL", (g.user["id"],))}
    counts = {row["problem_id"]: row["n"] for row in query("SELECT problem_id, COUNT(DISTINCT owner_id) AS n FROM files WHERE problem_id IS NOT NULL GROUP BY problem_id")}
    return render_page("pbl.html", "pbl", "pbl", problems=problems, categories=categories, category=category, submissions=submissions, counts=counts)


@app.route("/my-class/pbl/<int:problem_id>", methods=["GET", "POST"])
@login_required
def problem_detail(problem_id):
    problem = PROBLEMS.get(problem_id)
    if not problem:
        abort(404)
    if request.method == "POST":
        if not save_upload(request.files.get("taskResult"), problem_id=problem_id, area="pbl"):
            abort(400, description="제출할 파일을 선택해주세요.")
        flash("파일 제출을 완료했어요.", "success")
        return redirect(url_for("problem_detail", problem_id=problem_id))
    submissions = query("SELECT id, original_name, created_at FROM files WHERE owner_id=%s AND problem_id=%s ORDER BY id DESC", (g.user["id"], problem_id))
    return render_page("problem.html", "problem", "pbl", problem=problem, submissions=submissions)


@app.get("/my-class/pbl/<int:group_id>/detail/<int:reference_id>")
@login_required
def reference_problem(group_id, reference_id):
    if (group_id, reference_id) != (518, 559):
        abort(404)
    return redirect(url_for("problem_detail", problem_id=1))


def support_rows(key):
    search = request.args.get("content", "").strip()[:200]
    rows = [row for row in REFERENCE[key] if not search or search.lower() in row["title"].lower()]
    return rows, search


@app.get("/customer")
@login_required
def resources():
    rows, search = support_rows("resources")
    return render_page("support_list.html", "task", "support", page_title="자료실", customer_active="resources", rows=rows, search=search, section="resources")


@app.get("/customer/faq")
@login_required
def faq():
    rows, search = support_rows("faqs")
    return render_page("support_list.html", "task", "support", page_title="FAQ", customer_active="faq", rows=rows, search=search, section="faq")


@app.get("/customer/<section>/<int:item_id>")
@login_required
def support_detail(section, item_id):
    key = {"resources": "resources", "faq": "faqs"}.get(section)
    if not key:
        abort(404)
    item = next((row for row in REFERENCE[key] if row["id"] == item_id), None)
    if not item:
        abort(404)
    return render_page("support_detail.html", "task", "support", page_title="자료실" if key == "resources" else "FAQ", customer_active="resources" if key == "resources" else "faq", item=item, section=section)


def get_inquiry(inquiry_id):
    inquiry = query(
        "SELECT i.*, u.display_name FROM inquiries i JOIN users u ON u.id=i.owner_id WHERE i.id=%s",
        (inquiry_id,), one=True,
    )
    if not inquiry:
        abort(404)
    return inquiry


@app.get("/customer/contact")
@login_required
def inquiries():
    search = request.args.get("content", "").strip()[:200]
    category = request.args.get("category", "")
    if category not in ("", *INQUIRY_CATEGORIES):
        abort(400, description="문의 분류를 확인해주세요.")
    clauses = ["(i.title LIKE %s OR i.body LIKE %s)"]
    values = ["%" + search + "%", "%" + search + "%"]
    if category:
        clauses.append("i.category=%s")
        values.append(category)
    rows = query(
        "SELECT i.*, u.display_name, EXISTS(SELECT 1 FROM files f WHERE f.problem_id=i.id+%s) AS has_file "
        "FROM inquiries i JOIN users u ON u.id=i.owner_id WHERE " + " AND ".join(clauses) + " ORDER BY i.created_at DESC, i.id DESC",
        (INQUIRY_FILE_OFFSET, *values),
    )
    return render_page("inquiries.html", "task", "support", page_title="문의하기", customer_active="contact", rows=rows, search=search, category=category, categories=INQUIRY_CATEGORIES)


@app.route("/customer/contact/write", methods=["GET", "POST"])
@login_required
def write_inquiry():
    if request.method == "POST":
        category = request.form.get("category", "")
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        is_secret = request.form.get("is_secret") == "1"
        if category not in INQUIRY_CATEGORIES or not title or len(title) > 200 or not body or len(body) > 10000:
            abort(400, description="분류, 제목과 내용을 확인해주세요.")
        db().begin()
        try:
            with db().cursor() as cursor:
                cursor.execute("INSERT INTO inquiries (owner_id, category, title, body, is_secret) VALUES (%s,%s,%s,%s,%s)", (g.user["id"], category, title, body, is_secret))
                inquiry_id = cursor.lastrowid
            save_upload(request.files.get("file"), problem_id=INQUIRY_FILE_OFFSET + inquiry_id, area="contact")
            db().commit()
        except BaseException:
            db().rollback()
            raise
        return redirect(url_for("inquiry_detail", inquiry_id=inquiry_id, secret=1) if is_secret else url_for("inquiry_detail", inquiry_id=inquiry_id))
    return render_page("inquiry_write.html", "task", "support", page_title="문의하기", customer_active="contact", categories=INQUIRY_CATEGORIES)


@app.route("/customer/contact/<int:inquiry_id>", methods=["GET", "POST"])
@login_required
def inquiry_detail(inquiry_id):
    inquiry = get_inquiry(inquiry_id)
    if inquiry["is_secret"] and "secret" in request.args and inquiry["owner_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)
    if request.method == "POST":
        if g.user["role"] != "admin":
            abort(403)
        answer = request.form.get("answer", "").strip()
        if not answer or len(answer) > 10000:
            abort(400, description="답변 내용을 입력해주세요.")
        query("UPDATE inquiries SET answer=%s, answered_at=NOW() WHERE id=%s", (answer, inquiry_id))
        flash("문의 답변을 등록했어요.", "success")
        return redirect(url_for("inquiry_detail", inquiry_id=inquiry_id))
    attachments = query("SELECT id, original_name FROM files WHERE problem_id=%s ORDER BY id", (INQUIRY_FILE_OFFSET + inquiry_id,))
    return render_page("inquiry_detail.html", "task", "support", page_title="문의하기", customer_active="contact", inquiry=inquiry, attachments=attachments)


@app.get("/mypage/my-information")
@login_required
def mypage_root():
    return redirect(url_for("mypage", user_id=g.user["id"]))


@app.get("/mypage/my-information/<int:user_id>")
@login_required
def mypage(user_id):
    return render_page("mypage.html", "mypage", "mypage", page_title="내 정보 관리", profile_user_id=user_id)


@app.route("/api/profiles/<int:user_id>", methods=["GET", "PATCH"])
def profile_api(user_id):
    if not g.user:
        return jsonify(error="로그인이 필요합니다."), 401
    profile = query(
        "SELECT u.id AS user_id, u.username, u.display_name, u.role, COALESCE(p.email, '') AS email, COALESCE(p.phone, '') AS phone "
        "FROM users u LEFT JOIN user_profiles p ON p.user_id=u.id WHERE u.id=%s",
        (user_id,), one=True,
    )
    if not profile:
        return jsonify(error="사용자를 찾을 수 없습니다."), 404
    if request.method == "PATCH":
        data = request.get_json(silent=True) or {}
        email = str(data.get("email", "")).strip()
        phone = str(data.get("phone", "")).strip()
        if email and (len(email) > 254 or email.count("@") != 1 or any(char.isspace() for char in email)):
            return jsonify(error="이메일 주소를 확인해주세요."), 400
        if not re.fullmatch(r"[0-9-]{0,20}", phone):
            return jsonify(error="전화번호는 숫자와 하이픈만 입력해주세요."), 400
        query(
            "INSERT INTO user_profiles (user_id, email, phone) VALUES (%s,%s,%s) "
            "ON DUPLICATE KEY UPDATE email=VALUES(email), phone=VALUES(phone)",
            (user_id, email, phone),
        )
        profile["email"] = email
        profile["phone"] = phone
    return jsonify(profile)


@app.get("/download/<int:file_id>")
@login_required
def download(file_id):
    attachment = query("SELECT * FROM files WHERE id=%s", (file_id,), one=True)
    if not attachment:
        abort(404)
    if attachment["problem_id"] is not None and attachment["owner_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)
    if attachment["post_id"] is not None and not query("SELECT id FROM posts WHERE id=%s", (attachment["post_id"],), one=True):
        abort(404)
    return send_from_directory(UPLOADS, attachment["stored_name"], as_attachment=True, download_name=attachment["original_name"], mimetype="application/octet-stream")


@app.get("/admin")
def admin_dashboard():
    stats = {
        "users": query("SELECT COUNT(*) AS n FROM users", one=True)["n"],
        "posts": query("SELECT COUNT(*) AS n FROM posts", one=True)["n"],
        "inquiries": query("SELECT COUNT(*) AS n FROM inquiries", one=True)["n"],
        "files": query("SELECT COUNT(*) AS n FROM files", one=True)["n"],
    }
    users = query(
        "SELECT u.id, u.username, u.display_name, u.role, COALESCE(p.email, '') AS email, COALESCE(p.phone, '') AS phone "
        "FROM users u LEFT JOIN user_profiles p ON p.user_id=u.id ORDER BY u.id"
    )
    inquiries = query(
        "SELECT i.id, i.title, i.category, i.created_at, u.username, i.answer IS NOT NULL AS answered "
        "FROM inquiries i JOIN users u ON u.id=i.owner_id ORDER BY i.id DESC LIMIT 10"
    )
    files = query(
        "SELECT f.id, f.original_name, f.stored_name, f.size_bytes, f.created_at, u.username "
        "FROM files f JOIN users u ON u.id=f.owner_id ORDER BY f.id DESC LIMIT 20"
    )
    return render_page("admin.html", "notice", "admin", page_title="관리자 페이지", stats=stats, users=users, inquiries=inquiries, files=files)


@app.get("/health")
def health():
    query("SELECT 1 AS ok", one=True)
    return jsonify(status="ok")


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(413)
def page_error(error):
    messages = {403: "이 항목에 접근할 권한이 없습니다.", 404: "페이지를 찾을 수 없습니다.", 413: "첨부파일을 포함한 요청은 16MB 이내로 제출해주세요."}
    message = messages.get(error.code, error.description)
    return render_page("error.html", "notice" if g.get("user") else "login", "error", message=message, code=error.code), error.code


def seed_data():
    password = os.environ["LAB_PASSWORD"]
    for username, name, role in [("admin", "관리자", "admin"), ("student1", "학생1", "student"), ("student2", "학생2", "student")]:
        if not query("SELECT id FROM users WHERE username=%s", (username,), one=True):
            query("INSERT INTO users (username, display_name, role, password_hash) VALUES (%s,%s,%s,%s)", (username, name, role, generate_password_hash(password)))
    admin_id = query("SELECT id FROM users WHERE username='admin'", one=True)["id"]
    if not query("SELECT id FROM posts WHERE kind='notice' LIMIT 1", one=True):
        for notice in REFERENCE["notices"]:
            body = "안녕하세요. 교육운영사무국입니다.\n\n" + notice["title"] + "\n\n이 게시글은 교육용 SSLC Lab의 가상 공지입니다.\nPBL 메뉴에서 문제를 확인하고 결과 파일을 제출해주세요.\n학습게시판에서는 강의 질문과 첨부파일을 등록할 수 있습니다.\n\n감사합니다."
            query("INSERT INTO posts (kind, author_id, title, body, created_at) VALUES ('notice',%s,%s,%s,%s)", (admin_id, notice["title"], body, notice["created_at"]))
    for username in ("student1", "student2", "admin"):
        user = query("SELECT id FROM users WHERE username=%s", (username,), one=True)
        if not query("SELECT user_id FROM user_profiles WHERE user_id=%s", (user["id"],), one=True):
            query("INSERT INTO user_profiles (user_id, email, phone) VALUES (%s,%s,%s)", (user["id"], username + "@example.test", "010-0000-0000"))
    if not query("SELECT id FROM inquiries LIMIT 1", one=True):
        student1 = query("SELECT id FROM users WHERE username='student1'", one=True)["id"]
        student2 = query("SELECT id FROM users WHERE username='student2'", one=True)["id"]
        query("INSERT INTO inquiries (owner_id, category, title, body, answer, answered_at) VALUES (%s,'PBL/과제','클라우드 보안 PBL 제출 문의','제출 파일 형식을 확인하고 싶습니다.','PDF 또는 ZIP 형식으로 제출해주세요.',NOW())", (student1,))
        query("INSERT INTO inquiries (owner_id, category, title, body) VALUES (%s,'기타','교육 평가 관련 문의','교육 평가 기준을 확인하고 싶습니다.')", (student1,))
        query("INSERT INTO inquiries (owner_id, category, title, body, answer, answered_at) VALUES (%s,'출결문의','출결확인서 발급 문의','출결확인서 발급 절차가 궁금합니다.','교육운영사무국으로 문의해주세요.',NOW())", (student2,))


# flask main 함수
if __name__ == "__main__":
    if "--init-db" in sys.argv:
        with app.app_context():
            seed_data()
        print("Initialized demo accounts and notices.")
    else:
        app.run(host="127.0.0.1", port=8000, debug=False)
