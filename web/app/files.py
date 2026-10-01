"""공통 업로드 검증·저장과 파일 다운로드 권한 검사."""
from uuid import uuid4

from flask import Blueprint, abort, current_app, g, send_from_directory

from .auth import login_required
from .db import db, query

bp = Blueprint("files", __name__)

EXTENSIONS = {"pdf", "txt", "zip", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "hwp", "hwpx", "rtf", "png", "jpg", "jpeg", "gif", "webp"}


def save_upload(upload, *, post_id=None, problem_id=None):
    if not upload or not upload.filename:
        return None
    name = upload.filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not name or len(name) > 180 or any(ord(char) < 32 for char in name):
        abort(400, description="파일 이름을 확인해주세요.")
    suffix = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if suffix not in EXTENSIONS:
        abort(400, description="지원하는 문서·이미지·압축 파일을 선택해주세요.")
    uploads = current_app.config["UPLOAD_DIR"]
    uploads.mkdir(parents=True, exist_ok=True)
    stored_name = uuid4().hex + "." + suffix
    target = uploads / stored_name
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


@bp.get("/download/<int:file_id>")
@login_required
def download(file_id):
    attachment = query("SELECT * FROM files WHERE id=%s", (file_id,), one=True)
    if not attachment:
        abort(404)
    if attachment["problem_id"] is not None and attachment["owner_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)
    if attachment["post_id"] is not None and not query("SELECT id FROM posts WHERE id=%s", (attachment["post_id"],), one=True):
        abort(404)
    return send_from_directory(current_app.config["UPLOAD_DIR"], attachment["stored_name"], as_attachment=True, download_name=attachment["original_name"], mimetype="application/octet-stream")
