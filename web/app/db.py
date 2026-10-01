"""요청별 DB 연결, 쿼리와 가상 계정·공지 초기화."""
import os

import pymysql
from flask import current_app, g
from werkzeug.security import generate_password_hash


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
        for notice in current_app.config["REFERENCE"]["notices"]:
            body = "안녕하세요. 교육운영사무국입니다.\n\n" + notice["title"] + "\n\n이 게시글은 교육용 SSLC Lab의 가상 공지입니다.\nPBL 메뉴에서 문제를 확인하고 결과 파일을 제출해주세요.\n학습게시판에서는 강의 질문과 첨부파일을 등록할 수 있습니다.\n\n감사합니다."
            query("INSERT INTO posts (kind, author_id, title, body, created_at) VALUES ('notice',%s,%s,%s,%s)", (admin_id, notice["title"], body, notice["created_at"]))
