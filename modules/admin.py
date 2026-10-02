"""관리자 화면."""


from modules.common import render_page
from modules.database import query


def admin_dashboard():
    stats = {
        "users": query("SELECT COUNT(*) AS n FROM users", one=True)["n"],
        "posts": query("SELECT COUNT(*) AS n FROM posts", one=True)["n"],
        "inquiries": query("SELECT COUNT(*) AS n FROM inquiries", one=True)["n"],
        "files": query("SELECT COUNT(*) AS n FROM files", one=True)["n"],
    }
    users = query(
        "SELECT u.id, u.username, u.display_name, u.role, COALESCE(p.email, '') AS email, COALESCE(p.phone, '') AS phone "
        "FROM users u LEFT JOIN user_profiles p ON p.user_id=u.id ORDER BY u.id"
    )
    inquiries = query(
        "SELECT i.id, i.title, i.category, i.created_at, u.username, i.answer IS NOT NULL AS answered "
        "FROM inquiries i JOIN users u ON u.id=i.owner_id ORDER BY i.id DESC LIMIT 10"
    )
    files = query(
        "SELECT f.id, f.original_name, f.stored_name, f.size_bytes, f.created_at, u.username "
        "FROM files f JOIN users u ON u.id=f.owner_id ORDER BY f.id DESC LIMIT 20"
    )
    return render_page("admin.html", "notice", "admin", page_title="관리자 페이지", stats=stats, users=users, inquiries=inquiries, files=files)


def register_routes(app):
    app.add_url_rule("/admin", view_func=admin_dashboard, methods=["GET"])
