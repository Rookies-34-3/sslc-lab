"""마이페이지 화면과 프로필 API."""


import re

from flask import g, jsonify, redirect, request, url_for

from modules.auth import login_required
from modules.common import render_page
from modules.database import query


@login_required
def mypage_root():
    return redirect(url_for("mypage", user_id=g.user["id"]))


@login_required
def mypage(user_id):
    return render_page("mypage.html", "mypage", "mypage", page_title="내 정보 관리", profile_user_id=user_id)


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


def register_routes(app):
    app.add_url_rule("/mypage/my-information", view_func=mypage_root, methods=["GET"])
    app.add_url_rule("/mypage/my-information/<int:user_id>", view_func=mypage, methods=["GET"])
    app.add_url_rule("/api/profiles/<int:user_id>", view_func=profile_api, methods=["GET", "PATCH"])
