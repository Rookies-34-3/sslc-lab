"""로그인, 로그아웃과 요청 인증·CSRF 검사."""
import hmac
import secrets
from functools import wraps

from flask import Blueprint, abort, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash

from . import render_page
from .db import query

bp = Blueprint("auth", __name__)


@bp.before_app_request
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


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


@bp.route("/login", methods=["GET", "POST"])
def login():
    #로그인
    if request.method == "POST":
        user = query("SELECT * FROM users WHERE username=%s", (request.form.get("userId", "")[:80],), one=True)
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["id"]
            session["csrf_token"] = secrets.token_urlsafe(32)
            session.permanent = True
            return redirect(url_for("board.board", kind="notice"))
        flash("아이디 또는 비밀번호를 확인해주세요.", "error")
    elif g.user:
        return redirect(url_for("board.board", kind="notice"))
    return render_page("login.html", "login", "login")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
