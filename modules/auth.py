"""로그인, 로그아웃과 공통 인증 처리."""


import hmac
import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash

from modules.common import render_page
from modules.database import query


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


def login_required(view):
    # 기존 라우트 함수의 이름과 메타데이터 유지 인증 데코레이터
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            # 로그인되지 않은 사용자는 로그인 페이지로 이동
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


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
            #return redirect(url_for("board", kind="notice")) 인덱스 페이지로 리다이랙트 수정 
            return redirect(url_for("feature_index"))
        flash(username + " 계정의 아이디 또는 비밀번호를 확인해주세요.", "error")
    elif g.user:
        return redirect(url_for("board", kind="notice"))
    return render_page("login.html", "login", "login")


def logout():
    session.clear()
    return redirect(url_for("login"))


def register_routes(app):
    app.add_url_rule("/login", view_func=login, methods=["GET", "POST"])
    app.add_url_rule("/logout", view_func=logout, methods=["POST"])
