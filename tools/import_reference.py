"""Import saved SSLC styles, images and layout; never execute archived scripts."""

import hashlib
import json
import re
import tarfile
from concurrent.futures import ThreadPoolExecutor
from email import policy
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "static" / "reference"
PARTIALS = ROOT / "templates" / "reference"
PAGES = {
    "login": "러닝클라우드 로그인 _ SSLC.mhtml",
    "notice": "공지사항.mhtml",
    "task": "과제.mhtml",
    "qna": "학습 게시판.mhtml",
    "write": "글작성.mhtml",
    "detail": "SSLC공지사항 내용.mhtml",
    "pbl": "pbl.mhtml",
    "problem": "pbl에서 문제.mhtml",
    "mypage": "마이페이지.mhtml",
    "knowledge": "지식 컨텐츠.mhtml",
}
CSS_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)")
ACTIVE_PATHS = {
    "/my-class/roadmap": "/",
    "/my-class": "/my-class/board/notice",
    "/my-class/board": "/my-class/board/qna",
    "/my-class/board/notice": "/my-class/board/notice",
    "/my-class/board/task": "/my-class/board/task",
    "/my-class/board/qna": "/my-class/board/qna",
    "/my-class/board/write/qna": "/my-class/board/write/qna",
    "/my-class/pbl": "/my-class/pbl",
    "/pre-course": "/pre-course/list",
    "/pre-course/list": "/pre-course/list",
    "/customer": "/customer",
    "/customer/faq": "/customer/faq",
    "/customer/contact": "/customer/contact",
    "/mypage/my-information": "/mypage/my-information",
}
SUPPORT_RESOURCES = [
    {"id": 1, "title": "[국가정보원] 국가 사이버보안 기본지침", "author": "관리자1", "created_at": "2026-07-10 12:12", "views": 314, "has_file": True},
    {"id": 2, "title": "[과기정통부·KISA] AI 보안 레드티밍 가이드", "author": "관리자1", "created_at": "2026-07-10 12:09", "views": 242, "has_file": True},
    {"id": 3, "title": "[과기정통부·KISA] AI 보안 위협 대응 매뉴얼", "author": "관리자1", "created_at": "2026-07-10 12:06", "views": 124, "has_file": True},
    {"id": 4, "title": "교육 평가 기준(생성형AI활용 사이버보안 전문인력 양성과정 33기 이후 기수부터 해당)", "author": "관리자", "created_at": "2026-06-05 16:03", "views": 1074, "has_file": False},
    {"id": 5, "title": "교육 평가 기준(클라우드기반 스마트융합보안과정 32기 이후 기수부터 해당)", "author": "관리자", "created_at": "2026-04-22 10:06", "views": 1362, "has_file": False},
    {"id": 6, "title": "SSLC 사용 가이드", "author": "관리자", "created_at": "2025-09-09 09:54", "views": 603, "has_file": True},
    {"id": 7, "title": "PBL 안내", "author": "관리자", "created_at": "2025-06-10 10:38", "views": 2092, "has_file": False},
]
SUPPORT_FAQS = [
    {"id": 1, "title": "교육 과정 중 근로를 해도 괜찮을까요?", "author": "관리자", "created_at": "2024-09-21 15:21", "views": 754},
    {"id": 2, "title": "공가 (또는 병가) 신청을 했는데, HRD-Net에는 지각/결석/조퇴로 뜹니다. 공가 신청이 안 된 건가요?", "author": "관리자", "created_at": "2024-09-21 15:20", "views": 497},
    {"id": 3, "title": "코로나19 확진 시, 출결 인정은 어떻게 되나요?", "author": "관리자", "created_at": "2024-09-21 14:54", "views": 180},
    {"id": 4, "title": "상담 신청은 어디서 하나요?", "author": "매니저2", "created_at": "2024-07-08 14:35", "views": 231},
    {"id": 5, "title": "평가 기준은 어떻게 되나요?", "author": "매니저2", "created_at": "2024-07-03 09:49", "views": 571},
    {"id": 6, "title": "노트북이 멈췄습니다. 재부팅이 안돼요.", "author": "매니저2", "created_at": "2024-07-02 10:06", "views": 316},
]


def read_archive(path):
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    parts = [part for part in message.walk() if not part.is_multipart()]
    main = next(part for part in parts if part.get_content_type() == "text/html")
    html = main.get_payload(decode=True).decode(main.get_content_charset() or "utf-8")
    return BeautifulSoup(html, "html.parser"), parts


def local_name(data, suffix):
    return hashlib.sha256(data).hexdigest()[:20] + suffix


def put(data, suffix):
    name = local_name(data, suffix)
    destination = ASSETS / name
    if not destination.exists():
        destination.write_bytes(data)
    return "/static/reference/" + name


def font_url(url):
    if urlsplit(url).hostname == "fonts.gstatic.com" and url.endswith(".woff2"):
        return url
    filename = urlsplit(url).path.rsplit("/", 1)[-1]
    match = re.match(r"(fa-(?:brands|regular|solid)-\d+).*\.woff2$", filename)
    if match:
        return "https://maxst.icons8.com/vue-static/landings/line-awesome/font-awesome-line-awesome/webfonts/" + match[1] + ".woff2"
    match = re.match(r"(la-(?:brands|regular|solid)-\d+).*\.woff2$", filename)
    if match:
        return "https://registry.npmjs.org/line-awesome/-/line-awesome-1.3.0.tgz#" + match[1] + ".woff2"
    return None


def cache_font(url):
    # Only these public font origins are eligible for a build-time fetch.
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"fonts.gstatic.com", "maxst.icons8.com", "registry.npmjs.org"}:
        raise ValueError("Unexpected font origin")
    name = hashlib.sha256(url.encode()).hexdigest()[:20] + ".woff2"
    destination = ASSETS / name
    if not destination.exists():
        with urlopen(Request(url, headers={"User-Agent": "SSLC-Lab-Asset-Import/1.0"}), timeout=30) as response:
            if urlsplit(response.url).hostname != parsed.hostname:
                raise ValueError("Unexpected font redirect")
            data = response.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise ValueError("Oversized font resource")
        if parsed.hostname == "registry.npmjs.org":
            with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as archive:
                member = archive.getmember("package/dist/line-awesome/fonts/" + parsed.fragment)
                data = archive.extractfile(member).read()
        if not data.startswith(b"wOF2"):
            raise ValueError("Invalid WOFF2 resource")
        destination.write_bytes(data)
    return url, "/static/reference/" + name


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    PARTIALS.mkdir(parents=True, exist_ok=True)
    archives = {key: read_archive(ROOT / "docs" / name) for key, name in PAGES.items()}
    resources, css_parts = {}, {}
    suffixes = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/svg+xml": ".svg"}
    for soup, parts in archives.values():
        for part in parts:
            location = part.get("Content-Location", "")
            kind = part.get_content_type()
            data = part.get_payload(decode=True)
            if kind in suffixes:
                if kind == "image/svg+xml" and re.search(rb"<script|\bon\w+\s*=|<foreignObject|(?:href|src)\s*=\s*[\"'](?:https?:|javascript:)", data, re.I):
                    raise ValueError("Active SVG in archive")
                resources[location] = put(data, suffixes[kind])
            elif kind == "text/css":
                css_parts[location] = data.decode(part.get_content_charset() or "utf-8")

    def resolve(url, origin="https://lms.sslc.kr/"):
        if url in resources:
            return resources[url]
        absolute = urljoin(origin if not origin.startswith("cid:") else "https://lms.sslc.kr/", url)
        return resources.get(absolute)

    fonts = {}
    for location, css in css_parts.items():
        for match in CSS_URL.finditer(css):
            original = urljoin(location if not location.startswith("cid:") else "https://lms.sslc.kr/", match[2])
            target = font_url(original)
            if target:
                fonts[original] = target
    with ThreadPoolExecutor(max_workers=8) as pool:
        downloaded = dict(pool.map(cache_font, sorted(set(fonts.values()))))
    resources.update({original: downloaded[target] for original, target in fonts.items()})
    print(f"Cached {len(downloaded)} font files.", flush=True)

    def rewrite_css(css, origin):
        def replace(match):
            source = match[2]
            if source.startswith("data:"):
                return match[0]
            return 'url("' + (resolve(source, origin) or "data:,") + '")'
        css = re.sub(r"@import\s+(?:url\([^;]+|['\"][^;]+);", "", css)
        return CSS_URL.sub(replace, css)

    for location, css in css_parts.items():
        resources[location] = put(rewrite_css(css, location).encode("utf-8"), ".css")

    def clean(node):
        for tag in list(node.find_all(["script", "iframe", "object", "embed", "base"])):
            tag.decompose()
        for tag in [node, *node.find_all(True)]:
            for attr in list(tag.attrs):
                if attr.lower().startswith("on"):
                    del tag[attr]
            if tag.get("src"):
                tag["src"] = resolve(tag["src"]) or "data:,"
            if tag.get("style"):
                tag["style"] = rewrite_css(tag["style"], "https://lms.sslc.kr/")
            if tag.name == "a":
                path = tag.get("data-path") or urlsplit(tag.get("href", "")).path
                if path in ACTIVE_PATHS:
                    tag["href"] = ACTIVE_PATHS[path]
                else:
                    tag["href"] = "#"
                    tag["data-unavailable"] = "true"
        # Archived text is data, never Jinja source.
        return str(node).replace("{{", "&#123;&#123;").replace("{%", "&#123;%").replace("{#", "&#123;#")

    def save(name, text):
        (PARTIALS / name).write_text(text + "\n", encoding="utf-8")

    notice = archives["notice"][0]
    header = notice.select_one(".flegSU")
    header["class"] = [c for c in header["class"] if c != "sticky"]
    user = header.select_one("#login")
    user["role"] = "button"
    user["tabindex"] = "0"
    user["aria-expanded"] = "false"
    user["aria-controls"] = "user-menu"
    user.find("span", recursive=False).string = "__USER_DISPLAY__"
    save("header.html", clean(header).replace("__USER_DISPLAY__", "{{ current_user.display_name }}"))
    save("course.html", clean(notice.select_one(".hRjIcE")))
    nav = notice.select_one(".gGhjif")
    for selected in nav.select(".selectedTab"):
        selected["class"] = []
    save("nav.html", clean(nav).replace("<span>로드맵</span>", "<span>인덱스</span>"))
    save("footer.html", clean(notice.select_one(".jgPiCh")))

    login = archives["login"][0].select_one("#root")
    form = login.find("form")
    form["method"] = "post"
    form["action"] = "/login"
    for field in form.select("input"):
        field["required"] = ""
    hidden = archives["login"][0].new_tag("input", attrs={"type": "hidden", "name": "csrf_token", "value": "__CSRF__"})
    form.insert(0, hidden)
    save("login_body.html", clean(login).replace("__CSRF__", "{{ csrf_token }}"))

    problem_body = archives["problem"][0].select_one(".jUVhzP")
    save("problem_body.html", clean(problem_body))

    knowledge = archives["knowledge"][0].select_one(".render.login")
    save("knowledge_heading.html", clean(knowledge.select_one(".krGcMb")))
    knowledge_body = knowledge.select_one(".kpLUAB")
    save("knowledge_intro.html", clean(knowledge_body.select_one(".cAczGt")))
    knowledge_cards = knowledge_body.select_one(".fSAiJd")
    for card in knowledge_cards.select(".gylEXM"):
        card["data-unavailable"] = "true"
    save("knowledge_cards.html", "".join(clean(card) for card in knowledge_cards.find_all(recursive=False)))

    data = {"notices": [], "problems": [], "tasks": [], "resources": SUPPORT_RESOURCES, "faqs": SUPPORT_FAQS}
    for row in notice.select("table tr"):
        cells = row.find_all("td")
        if len(cells) == 4:
            data["notices"].append({"title": cells[0].find("span").get_text(strip=True), "created_at": cells[2].get_text(" ", strip=True)})
    for index, row in enumerate(archives["task"][0].select("table tr"), 1):
        title = row.select_one("td.title > span")
        period = row.select_one("td.submitDate")
        author = row.select_one("td.author")
        created = row.select_one("td.date")
        if title and period and author and created:
            data["tasks"].append({
                "id": index,
                "title": title.get_text(strip=True),
                "submit_period": period.get_text(" ", strip=True),
                "author": author.get_text(strip=True),
                "created_at": created.get_text(" ", strip=True),
            })
    for index, card in enumerate(archives["pbl"][0].select(".sc-hyhWHZ"), 1):
        title = card.select("h2 p")
        if len(title) < 2:
            continue
        description = card.select_one(".subTitle")
        number = card.select_one(".number")
        category = title[0].get_text(strip=True).strip("[] ")
        if category.startswith(("기초역량", "심화역량")):
            category = "개인정보보호"
        data["problems"].append({
            "id": index,
            "category": category,
            "title": title[1].get_text(strip=True),
            "description": description.get_text(strip=True) if description else "결과 파일을 업로드해주세요.",
            "number": number.get_text(strip=True) if number else f"{(index - 1) % 6 + 1:02d}",
            "group": card.select_one(".sc-EElJA > div > span:last-child").get_text(strip=True),
            "level": card.select_one(".level").get_text(strip=True),
            "card_class": " ".join(card.get("class", [])),
            "top_class": " ".join(card.select_one(".sc-EElJA").get("class", [])),
            "body_class": " ".join(card.find("h2").parent.get("class", [])),
        })
    (ROOT / "reference_data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    styles = {}
    for key, (soup, _) in archives.items():
        styles[key] = list(dict.fromkeys(resources[link["href"]] for link in soup.select('head link[rel="stylesheet"]') if link.get("href") in resources))
    # Expose convenient paths without keeping real service URLs in browser markup.
    mapping = {urlsplit(url).path: local for url, local in resources.items() if url.startswith("https://lms.sslc.kr/")}
    manifest = {"styles": styles, "resources": mapping, "fonts": len(downloaded)}
    (ROOT / "reference_assets.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {len(data['problems'])} PBL cards, {len(data['notices'])} notices, {len(data['tasks'])} tasks, and {len(list(ASSETS.iterdir()))} assets.")


if __name__ == "__main__":
    main()
