"""Flask 진입점, 기능 등록과 공통 응답 처리."""


import os
import sys
from datetime import timedelta

from flask import Flask, g, jsonify, redirect, request, url_for

from modules import admin, auth, board, files, knowledge, learning, mypage, support
from modules.auth import login_required
from modules.common import render_page, template_context
from modules.database import close_db, query, seed_data


app = Flask(__name__)


app.config.update(                                                                      #flask 설정
    SECRET_KEY=os.environ["SECRET_KEY"],                                                #세션 서명에 사용
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,                                                #업로드 크기
    SESSION_COOKIE_NAME="sslc_lab_session",                                             #세션 정보 쿠키 이름
    SESSION_COOKIE_HTTPONLY=True,                                                       #http only설정
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",   #secure설정
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),                                      #세션 타임
)


app.before_request(auth.load_user_and_check_csrf)
app.context_processor(template_context)
app.teardown_appcontext(close_db)

for feature_module in (auth, learning, board, knowledge, support, mypage, files, admin):
    feature_module.register_routes(app)


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


@app.get("/my-class")
def my_class_root():
    return redirect(url_for("feature_index") if g.user else url_for("login"))


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


# flask main 함수
if __name__ == "__main__":
    if "--init-db" in sys.argv:
        with app.app_context():
            seed_data()
        print("Initialized demo accounts and notices.")
    else:
        app.run(host="127.0.0.1", port=8000, debug=False)
