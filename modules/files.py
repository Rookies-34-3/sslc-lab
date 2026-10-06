"""공통 파일 업로드와 다운로드."""


from uuid import uuid4

from flask import abort, g, send_from_directory

from modules.auth import login_required
from modules.common import UPLOADS
from modules.database import db, query

#허용 목록
EXTENSIONS = {"pdf", "txt", "zip", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "hwp", "hwpx", "rtf", "png", "jpg", "jpeg", "gif", "webp"}


def save_upload(upload, *, post_id=None, problem_id=None, area="files"):
    if not upload or not upload.filename:
        return None
    name = upload.filename.replace("\\", "/")
    if not name or len(name) > 180 or any(ord(char) < 32 for char in name):
        abort(400, description="파일 이름을 확인해주세요.")
    #취약한 설정
    if not any("." + extension in name.lower() for extension in EXTENSIONS):
        abort(400, description="지원하는 문서·이미지·압축 파일을 선택해주세요.")
    UPLOADS.mkdir(parents=True, exist_ok=True)
    upload_root = UPLOADS.resolve()
    candidate = upload_root / str(g.user["id"]) / area / name
    target = candidate.with_name(uuid4().hex[:8] + "-" + candidate.name).resolve()
    if upload_root not in target.parents:
        abort(400, description="파일 경로를 확인해주세요.")
    target.parent.mkdir(parents=True, exist_ok=True)
    stored_name = target.relative_to(upload_root).as_posix()
    if len(stored_name) > 80:
        abort(400, description="파일 이름을 줄여주세요.")
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

#get요청 가능
def register_routes(app):
    app.add_url_rule("/download/<int:file_id>", view_func=download, methods=["GET"])
