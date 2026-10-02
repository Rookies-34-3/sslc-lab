"""자료실, FAQ와 문의하기."""


from flask import abort, flash, g, redirect, request, url_for

from modules.auth import login_required
from modules.common import INQUIRY_FILE_OFFSET, REFERENCE, render_page
from modules.database import db, query
from modules.files import save_upload


INQUIRY_CATEGORIES = ("출결문의", "온라인 교육", "오프라인 교육", "PBL/과제", "프로젝트", "기타")# 문의하기 카테고리들


def support_rows(key):
    search = request.args.get("content", "").strip()[:200]
    rows = [row for row in REFERENCE[key] if not search or search.lower() in row["title"].lower()]
    return rows, search


@login_required
def resources():
    rows, search = support_rows("resources")
    return render_page("support_list.html", "task", "support", page_title="자료실", customer_active="resources", rows=rows, search=search, section="resources")


@login_required
def faq():
    rows, search = support_rows("faqs")
    return render_page("support_list.html", "task", "support", page_title="FAQ", customer_active="faq", rows=rows, search=search, section="faq")


@login_required
def support_detail(section, item_id):
    key = {"resources": "resources", "faq": "faqs"}.get(section)
    if not key:
        abort(404)
    item = next((row for row in REFERENCE[key] if row["id"] == item_id), None)
    if not item:
        abort(404)
    return render_page("support_detail.html", "task", "support", page_title="자료실" if key == "resources" else "FAQ", customer_active="resources" if key == "resources" else "faq", item=item, section=section)


def get_inquiry(inquiry_id):
    inquiry = query(
        "SELECT i.*, u.display_name FROM inquiries i JOIN users u ON u.id=i.owner_id WHERE i.id=%s",
        (inquiry_id,), one=True,
    )
    if not inquiry:
        abort(404)
    return inquiry


@login_required
def inquiries():
    search = request.args.get("content", "").strip()[:200]
    category = request.args.get("category", "")
    if category not in ("", *INQUIRY_CATEGORIES):
        abort(400, description="문의 분류를 확인해주세요.")
    clauses = ["(i.title LIKE %s OR i.body LIKE %s)"]
    values = ["%" + search + "%", "%" + search + "%"]
    if category:
        clauses.append("i.category=%s")
        values.append(category)
    rows = query(
        "SELECT i.*, u.display_name, EXISTS(SELECT 1 FROM files f WHERE f.problem_id=i.id+%s) AS has_file "
        "FROM inquiries i JOIN users u ON u.id=i.owner_id WHERE " + " AND ".join(clauses) + " ORDER BY i.created_at DESC, i.id DESC",
        (INQUIRY_FILE_OFFSET, *values),
    )
    return render_page("inquiries.html", "task", "support", page_title="문의하기", customer_active="contact", rows=rows, search=search, category=category, categories=INQUIRY_CATEGORIES)


@login_required
def write_inquiry():
    if request.method == "POST":
        category = request.form.get("category", "")
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        is_secret = request.form.get("is_secret") == "1"
        if category not in INQUIRY_CATEGORIES or not title or len(title) > 200 or not body or len(body) > 10000:
            abort(400, description="분류, 제목과 내용을 확인해주세요.")
        db().begin()
        try:
            with db().cursor() as cursor:
                cursor.execute("INSERT INTO inquiries (owner_id, category, title, body, is_secret) VALUES (%s,%s,%s,%s,%s)", (g.user["id"], category, title, body, is_secret))
                inquiry_id = cursor.lastrowid
            save_upload(request.files.get("file"), problem_id=INQUIRY_FILE_OFFSET + inquiry_id, area="contact")
            db().commit()
        except BaseException:
            db().rollback()
            raise
        return redirect(url_for("inquiry_detail", inquiry_id=inquiry_id, secret=1) if is_secret else url_for("inquiry_detail", inquiry_id=inquiry_id))
    return render_page("inquiry_write.html", "task", "support", page_title="문의하기", customer_active="contact", categories=INQUIRY_CATEGORIES)


@login_required
def inquiry_detail(inquiry_id):
    inquiry = get_inquiry(inquiry_id)
    if inquiry["is_secret"] and "secret" in request.args and inquiry["owner_id"] != g.user["id"] and g.user["role"] != "admin":
        abort(403)
    if request.method == "POST":
        if g.user["role"] != "admin":
            abort(403)
        answer = request.form.get("answer", "").strip()
        if not answer or len(answer) > 10000:
            abort(400, description="답변 내용을 입력해주세요.")
        query("UPDATE inquiries SET answer=%s, answered_at=NOW() WHERE id=%s", (answer, inquiry_id))
        flash("문의 답변을 등록했어요.", "success")
        return redirect(url_for("inquiry_detail", inquiry_id=inquiry_id))
    attachments = query("SELECT id, original_name FROM files WHERE problem_id=%s ORDER BY id", (INQUIRY_FILE_OFFSET + inquiry_id,))
    return render_page("inquiry_detail.html", "task", "support", page_title="문의하기", customer_active="contact", inquiry=inquiry, attachments=attachments)


def register_routes(app):
    app.add_url_rule("/customer", view_func=resources, methods=["GET"])
    app.add_url_rule("/customer/faq", view_func=faq, methods=["GET"])
    app.add_url_rule("/customer/<section>/<int:item_id>", view_func=support_detail, methods=["GET"])
    app.add_url_rule("/customer/contact", view_func=inquiries, methods=["GET"])
    app.add_url_rule("/customer/contact/write", view_func=write_inquiry, methods=["GET", "POST"])
    app.add_url_rule("/customer/contact/<int:inquiry_id>", view_func=inquiry_detail, methods=["GET", "POST"])
