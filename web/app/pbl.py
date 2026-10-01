"""PBL 목록·분야 필터, 문제 상세와 결과 파일 제출."""
from flask import Blueprint, abort, flash, g, redirect, request, url_for

from . import PROBLEMS, render_page
from .auth import login_required
from .db import query
from .files import save_upload

bp = Blueprint("pbl", __name__)


@bp.get("/my-class/pbl")
@login_required
def pbl():
    category = request.args.get("category", "")
    categories = list(dict.fromkeys(problem["category"] for problem in PROBLEMS.values()))
    problems = [problem for problem in PROBLEMS.values() if not category or problem["category"] == category]
    submissions = {row["problem_id"] for row in query("SELECT DISTINCT problem_id FROM files WHERE owner_id=%s AND problem_id IS NOT NULL", (g.user["id"],))}
    counts = {row["problem_id"]: row["n"] for row in query("SELECT problem_id, COUNT(DISTINCT owner_id) AS n FROM files WHERE problem_id IS NOT NULL GROUP BY problem_id")}
    return render_page("pbl.html", "pbl", "pbl", problems=problems, categories=categories, category=category, submissions=submissions, counts=counts)


@bp.route("/my-class/pbl/<int:problem_id>", methods=["GET", "POST"])
@login_required
def problem_detail(problem_id):
    problem = PROBLEMS.get(problem_id)
    if not problem:
        abort(404)
    if request.method == "POST":
        if not save_upload(request.files.get("taskResult"), problem_id=problem_id):
            abort(400, description="제출할 파일을 선택해주세요.")
        flash("파일 제출을 완료했어요.", "success")
        return redirect(url_for("pbl.problem_detail", problem_id=problem_id))
    submissions = query("SELECT id, original_name, created_at FROM files WHERE owner_id=%s AND problem_id=%s ORDER BY id DESC", (g.user["id"], problem_id))
    return render_page("problem.html", "problem", "pbl", problem=problem, submissions=submissions)


@bp.get("/my-class/pbl/<int:group_id>/detail/<int:reference_id>")
@login_required
def reference_problem(group_id, reference_id):
    if (group_id, reference_id) != (518, 559):
        abort(404)
    return redirect(url_for("pbl.problem_detail", problem_id=1))
