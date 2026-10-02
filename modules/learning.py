"""과제와 PBL 목록, 상세 및 파일 제출."""


from flask import abort, flash, g, redirect, request, url_for

from modules.auth import login_required
from modules.common import ASSIGNMENT_FILE_OFFSET, REFERENCE, render_page
from modules.database import query
from modules.files import save_upload


PROBLEMS = {item["id"]: item for item in REFERENCE["problems"]}                         # pbl 목록
TASKS = {item["id"]: item for item in REFERENCE["tasks"]}                               # 과제 목록


@login_required
def task_board():
    search = request.args.get("content", "").strip()[:200]
    tasks = [task for task in TASKS.values() if not search or search.lower() in task["title"].lower()]
    submitted = {
        row["problem_id"] - ASSIGNMENT_FILE_OFFSET
        for row in query(
            "SELECT DISTINCT problem_id FROM files WHERE owner_id=%s AND problem_id BETWEEN %s AND %s",
            (g.user["id"], ASSIGNMENT_FILE_OFFSET, ASSIGNMENT_FILE_OFFSET + 999_999),
        )
    }
    return render_page("task_board.html", "task", "task", tasks=tasks, submitted=submitted, search=search)


@login_required
def task_detail(task_id):
    task = TASKS.get(task_id)
    if not task:
        abort(404)
    submission_key = ASSIGNMENT_FILE_OFFSET + task_id
    if request.method == "POST":
        if not save_upload(request.files.get("taskResult"), problem_id=submission_key, area="task"):
            abort(400, description="제출할 파일을 선택해주세요.")
        flash("과제 파일 제출을 완료했어요.", "success")
        return redirect(url_for("task_detail", task_id=task_id))
    submissions = query(
        "SELECT id, original_name, created_at FROM files WHERE owner_id=%s AND problem_id=%s ORDER BY id DESC",
        (g.user["id"], submission_key),
    )
    return render_page("task.html", "task", "task", task=task, submissions=submissions)


@login_required
def pbl():
    category = request.args.get("category", "")
    categories = list(dict.fromkeys(problem["category"] for problem in PROBLEMS.values()))
    problems = [problem for problem in PROBLEMS.values() if not category or problem["category"] == category]
    submissions = {row["problem_id"] for row in query("SELECT DISTINCT problem_id FROM files WHERE owner_id=%s AND problem_id IS NOT NULL", (g.user["id"],))}
    counts = {row["problem_id"]: row["n"] for row in query("SELECT problem_id, COUNT(DISTINCT owner_id) AS n FROM files WHERE problem_id IS NOT NULL GROUP BY problem_id")}
    return render_page("pbl.html", "pbl", "pbl", problems=problems, categories=categories, category=category, submissions=submissions, counts=counts)


@login_required
def problem_detail(problem_id):
    problem = PROBLEMS.get(problem_id)
    if not problem:
        abort(404)
    if request.method == "POST":
        if not save_upload(request.files.get("taskResult"), problem_id=problem_id, area="pbl"):
            abort(400, description="제출할 파일을 선택해주세요.")
        flash("파일 제출을 완료했어요.", "success")
        return redirect(url_for("problem_detail", problem_id=problem_id))
    submissions = query("SELECT id, original_name, created_at FROM files WHERE owner_id=%s AND problem_id=%s ORDER BY id DESC", (g.user["id"], problem_id))
    return render_page("problem.html", "problem", "pbl", problem=problem, submissions=submissions)


@login_required
def reference_problem(group_id, reference_id):
    if (group_id, reference_id) != (518, 559):
        abort(404)
    return redirect(url_for("problem_detail", problem_id=1))


def register_routes(app):
    app.add_url_rule("/my-class/board/task", view_func=task_board, methods=["GET"])
    app.add_url_rule("/my-class/board/task/<int:task_id>", view_func=task_detail, methods=["GET", "POST"])
    app.add_url_rule("/my-class/pbl", view_func=pbl, methods=["GET"])
    app.add_url_rule("/my-class/pbl/<int:problem_id>", view_func=problem_detail, methods=["GET", "POST"])
    app.add_url_rule("/my-class/pbl/<int:group_id>/detail/<int:reference_id>", view_func=reference_problem, methods=["GET"])
