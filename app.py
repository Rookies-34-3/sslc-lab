#임포트 
import hmac
import json
import math
import os
import secrets
import sys
from datetime import timedelta
from functools import wraps
from pathlib import Path
from uuid import uuid4

import pymysql
from flask import Flask, abort, flash, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


ROOT = Path(__file__).resolve().parent                                                  #root폴더 지정
ASSETS = json.loads((ROOT / "reference_assets.json").read_text(encoding="utf-8"))       #asset로드
REFERENCE = json.loads((ROOT / "reference_data.json").read_text(encoding="utf-8"))      #
PROBLEMS = {item["id"]: item for item in REFERENCE["problems"]}                         #
UPLOADS = Path(os.environ.get("UPLOAD_DIR", ROOT / "instance" / "uploads"))             #업로드 저장 파일 위치 
EXTENSIONS = {"pdf", "txt", "zip", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "hwp", "hwpx", "rtf", "png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config.update(
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
    #execute query
    with db().cursor() as cursor:
        cursor.execute(sql, values)
        return cursor.fetchone() if one else cursor.fetchall()


@app.teardown_appcontext
def close_db(error=None):
    #flask 종료시 db 종료
    connection = g.pop("db", None)
    if connection:
        connection.close()


@app.before_request
def load_user_and_check_csrf():
    #csrf 토큰 
    g.user = None
    if request.endpoint == "static":
        return
    if session.get("user_id"):
        g.user = query("SELECT id, username, display_name, role FROM users WHERE id=%s", (session["user_id"],), one=True)
    if request.method == "POST":
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
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store"
    return response


@app.context_processor
def template_context():
    token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return {"current_user": g.get("user"), "csrf_token": token, "assets": ASSETS, "ref": lambda path: ASSETS["resources"].get(path, "data:,")}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def render_page(template, asset_page, active, **context):
    return render_template(template, asset_page=asset_page, active=active, **context)


@app.get("/")
@app.get("/my-class")
def index():
# 루트 인덱스 
    return redirect(url_for("board", kind="notice") if g.user else url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
#로그인
    if request.method == "POST":
        user = query("SELECT * FROM users WHERE username=%s", (request.form.get("userId", "")[:80],), one=True)
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            return redirect(url_for("board", kind="notice"))
        flash("아이디 또는 비밀번호를 확인해주세요.", "error")
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


def check_kind(kind):
    if kind not in {"notice", "qna"}:
        abort(404)


@app.get("/my-class/board/<kind>")
@login_required
def board(kind):
    check_kind(kind)
    search = request.args.get("content", "").strip()[:200]
    page = max(1, request.args.get("page", 1, type=int))
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
    return render_page("board.html", kind, kind, kind=kind, heading="공지사항" if kind == "notice" else "강의 질문", posts=posts, total=total, search=search, page=page, pages=pages)


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


def save_upload(upload, *, post_id=None, problem_id=None):
    if not upload or not upload.filename:
        return None
    name = upload.filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not name or len(name) > 180 or any(ord(char) < 32 for char in name):
        abort(400, description="파일 이름을 확인해주세요.")
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if suffix not in EXTENSIONS:
        abort(400, description="지원하는 문서·이미지·압축 파일을 선택해주세요.")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    stored_name = uuid4().hex + "." + suffix
    target = UPLOADS / stored_name
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
            save_upload(request.files.get("file"), post_id=post_id)
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
        if not save_upload(request.files.get("taskResult"), problem_id=problem_id):
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


# flask main 함수
if __name__ == "__main__":
    if "--init-db" in sys.argv:
        with app.app_context():
            seed_data()
        print("Initialized demo accounts and notices.")
    else:
        app.run(host="127.0.0.1", port=8000, debug=False)
