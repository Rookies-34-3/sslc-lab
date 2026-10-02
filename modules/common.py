"""공통 화면 자료와 템플릿 렌더링."""


import json
import os
import secrets
from pathlib import Path

from flask import g, render_template, session


ROOT = Path(__file__).resolve().parents[1]                                                  # root폴더 지정
ASSETS = json.loads((ROOT / "reference_assets.json").read_text(encoding="utf-8"))       # asset로드 화면 리소스
REFERENCE = json.loads((ROOT / "reference_data.json").read_text(encoding="utf-8"))      # 화면에 표시할 데이터 로드
UPLOADS = Path(os.environ.get("UPLOAD_DIR", ROOT / "instance" / "uploads"))             # 업로드 저장 파일 위치 /app/instance/uploads
ASSIGNMENT_FILE_OFFSET = 1_000_000                                                      # 과제 파일 id 오프셋
INQUIRY_FILE_OFFSET = 2_000_000                                                         # 문의 글 파일 id 오프셋


def template_context():
    #Flask에서 템플릿을 렌더링시 실행
    # 세션에 csrf_token이 없으면 새로 만들고, 있으면 기존 값을 그대로 가져옴 및 데이터 공급
    token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return {"current_user": g.get("user"), "csrf_token": token, "assets": ASSETS, "ref": lambda path: ASSETS["resources"].get(path, "data:,")}


def render_page(template, asset_page, active, **context):
    return render_template(template, asset_page=asset_page, active=active, **context)
