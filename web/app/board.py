"""공지사항·학습게시판 목록, 검색, 상세와 글 작성."""
import math

from flask import Blueprint, abort, g, redirect, request, url_for

from . import render_page
from .auth import login_required
from .db import db, query
from .files import save_upload

bp = Blueprint("board", __name__)


def check_kind(kind):
    if kind not in {"notice", "qna"}:
        abort(404)


@bp.get("/my-class/board")
@login_required
def board_root():
    return redirect(url_for("board.board", kind="qna"))


@bp.get("/my-class/board/<kind>")
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


@bp.get("/my-class/board/<kind>/<int:post_id>")
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


@bp.route("/my-class/board/write/<kind>", methods=["GET", "POST"])
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
        return redirect(url_for("board.post_detail", kind=kind, post_id=post_id))
    return render_page("write.html", "write", kind, kind=kind, heading="공지사항 작성" if kind == "notice" else "강의 질문 작성")
