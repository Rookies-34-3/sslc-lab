"""지식컨텐츠 목록, 미리보기와 등록."""


import base64
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from flask import abort, flash, g, redirect, request, url_for

from modules.auth import login_required
from modules.common import UPLOADS, render_page
from modules.database import query


CONTENT_LIMIT = 256 * 1024
THUMBNAIL_LIMIT = 2 * 1024 * 1024
THUMBNAIL_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp", "image/svg+xml": "svg"}


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.og_title = ""
        self.og_image = ""
        self.title_parts = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "meta":
            name = (attributes.get("property") or attributes.get("name") or "").lower()
            if name == "og:title":
                self.og_title = attributes.get("content", "")
            elif name == "og:image":
                self.og_image = attributes.get("content", "")

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)


def fetch_http(url, limit):
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("http 또는 https URL을 입력해주세요.")

    started = time.perf_counter()
    try:
        response = urlopen(Request(url, headers={"User-Agent": "SSLC-Lab-Preview/1.0"}), timeout=3)
    except HTTPError as error:
        raise ValueError(f"대상 서버가 HTTP {error.code}을 반환했습니다.") from error

    with response:
        content = response.read(limit + 1)
        if len(content) > limit:
            raise ValueError("가져온 콘텐츠가 허용된 크기를 초과했습니다.")
        return {
            "status": response.getcode(),
            "final_url": response.geturl(),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
            "content_type": response.headers.get_content_type().lower(),
            "charset": response.headers.get_content_charset() or "utf-8",
            "body": content,
        }


def fetch_external_content(url):
    page = fetch_http(url, CONTENT_LIMIT)
    if page["content_type"] in THUMBNAIL_TYPES:
        title = ""
        thumbnail_url = page["final_url"]
        thumbnail = page
    else:
        try:
            text = page["body"].decode(page["charset"], errors="replace")
        except LookupError:
            text = page["body"].decode("utf-8", errors="replace")
        parser = MetadataParser()
        parser.feed(text)
        if not parser.og_image:
            raise ValueError("콘텐츠에서 og:image 썸네일을 찾지 못했습니다.")
        title = (parser.og_title or "".join(parser.title_parts)).strip()
        thumbnail_url = urljoin(page["final_url"], parser.og_image)
        thumbnail = fetch_http(thumbnail_url, THUMBNAIL_LIMIT)

    extension = THUMBNAIL_TYPES.get(thumbnail["content_type"])
    if not extension:
        raise ValueError("PNG, JPEG, GIF, WebP, SVG 썸네일만 가져올 수 있습니다.")
    return {
        "title": title[:200],
        "source_url": page["final_url"],
        "source_status": page["status"],
        "thumbnail_url": thumbnail_url,
        "thumbnail_status": thumbnail["status"],
        "elapsed_ms": page["elapsed_ms"] + thumbnail["elapsed_ms"],
        "mime_type": thumbnail["content_type"],
        "extension": extension,
        "image": thumbnail["body"],
        "data_url": "data:" + thumbnail["content_type"] + ";base64," + base64.b64encode(thumbnail["body"]).decode(),
    }


@login_required
def knowledge_content():
    contents = query("SELECT id, title, source_url, thumbnail_path, created_at FROM external_contents ORDER BY id DESC")
    return render_page("knowledge.html", "knowledge", "knowledge", contents=contents)


@login_required
def write_knowledge_content():
    title = request.form.get("title", "").strip()[:200]
    source_url = request.form.get("url", "").strip()[:2048]
    preview = None
    error = None
    if request.method == "POST":
        action = request.form.get("action")
        if action not in {"preview", "save"}:
            abort(400)
        try:
            preview = fetch_external_content(source_url)
            title = title or preview["title"]
            if not title:
                raise ValueError("콘텐츠 제목을 입력해주세요.")
            if action == "save":
                folder = UPLOADS / "knowledge"
                folder.mkdir(parents=True, exist_ok=True)
                stored_name = "knowledge/" + uuid4().hex + "." + preview["extension"]
                (UPLOADS / stored_name).write_bytes(preview["image"])
                query(
                    "INSERT INTO external_contents (owner_id, title, source_url, thumbnail_path) VALUES (%s,%s,%s,%s)",
                    (g.user["id"], title, source_url, stored_name),
                )
                flash("외부 콘텐츠를 추가했습니다.", "success")
                return redirect(url_for("knowledge_content"))
        except (URLError, TimeoutError, OSError, ValueError) as fetch_error:
            error = f"썸네일을 가져오지 못했습니다: {fetch_error}"
    return render_page(
        "knowledge_form.html",
        "knowledge",
        "knowledge",
        form_title=title,
        form_url=source_url,
        preview=preview,
        preview_error=error,
    )


def register_routes(app):
    app.add_url_rule("/pre-course/list", view_func=knowledge_content, methods=["GET"])
    app.add_url_rule("/pre-course/write", view_func=write_knowledge_content, methods=["GET", "POST"])
