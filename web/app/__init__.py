"""Flask 앱 생성, 공통 화면 컨텍스트와 오류·응답 처리."""
import json
import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import Flask, g, jsonify, redirect, render_template, request, session, url_for

from .db import close_db, query

ROOT = Path(__file__).resolve().parent
ASSETS = json.loads((ROOT / "reference_assets.json").read_text(encoding="utf-8"))
REFERENCE = json.loads((ROOT / "reference_data.json").read_text(encoding="utf-8"))
PROBLEMS = {item["id"]: item for item in REFERENCE["problems"]}


def render_page(template, asset_page, active, **context):
    return render_template(template, asset_page=asset_page, active=active, **context)


def security_headers(response):
    #응답 헤더에 추가
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; font-src 'self' data:; script-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    if request.endpoint != "static":
        response.headers["Cache-Control"] = "no-store"
    return response


def template_context():
    token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return {"current_user": g.get("user"), "csrf_token": token, "assets": ASSETS, "ref": lambda path: ASSETS["resources"].get(path, "data:,")}


def index():
    # 루트 인덱스
    return redirect(url_for("board.board", kind="notice") if g.user else url_for("auth.login"))


def health():
    query("SELECT 1 AS ok", one=True)
    return jsonify(status="ok")


def page_error(error):
    messages = {403: "이 항목에 접근할 권한이 없습니다.", 404: "페이지를 찾을 수 없습니다.", 413: "첨부파일을 포함한 요청은 16MB 이내로 제출해주세요."}
    message = messages.get(error.code, error.description)
    return render_page("error.html", "notice" if g.get("user") else "login", "error", message=message, code=error.code), error.code


def create_app():
    from . import auth, board, files, pbl

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ["SECRET_KEY"],  #세션 서명에 사용
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  #업로드 크기
        SESSION_COOKIE_NAME="sslc_lab_session",  #세션 정보 쿠키 이름
        SESSION_COOKIE_HTTPONLY=True,  #http only설정
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",  #secure설정
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),  #세션 타임
    )
    app.config["UPLOAD_DIR"] = Path(os.environ.get("UPLOAD_DIR", ROOT.parents[1] / "instance" / "uploads"))
    app.config["REFERENCE"] = REFERENCE

    app.teardown_appcontext(close_db)
    app.after_request(security_headers)
    app.context_processor(template_context)
    for blueprint in (auth.bp, board.bp, pbl.bp, files.bp):
        app.register_blueprint(blueprint)
    app.add_url_rule("/my-class", view_func=index)
    app.add_url_rule("/", view_func=index)
    app.add_url_rule("/health", view_func=health)
    for code in (400, 403, 404, 413):
        app.register_error_handler(code, page_error)
    return app
