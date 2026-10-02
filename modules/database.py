"""DB 연결, 쿼리와 초기 데이터."""


import os

import pymysql
from flask import g
from werkzeug.security import generate_password_hash

from modules.common import REFERENCE


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


def close_db(error=None):
    #flask 종료시 db 종료
    connection = g.pop("db", None)
    if connection:
        connection.close()


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
