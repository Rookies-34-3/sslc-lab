# SSLC Lab

제공된 SSLC MHTML 화면 자료를 바탕으로 만든 Flask 교육용 미러입니다. 로그인, 공지사항, 과제, 학습게시판, PBL, 자료실, FAQ, 문의하기, 마이페이지를 사용할 수 있습니다. 아직 구현하지 않은 원본 화면 메뉴를 누르면 `미구현입니다.` 알림을 표시합니다.

## 로컬 실행

Docker Desktop의 Linux 컨테이너 모드와 Docker Engine 28 이상을 사용합니다. 환경 파일 생성에는 Python 3만 필요합니다.

```powershell
cd C:\Users\yt010\Desktop\Rookies\sslc-lab
python tools/setup_env.py
docker compose build
docker compose up -d --wait
```

브라우저에서 http://127.0.0.1:8080 을 엽니다. 로그인 후 기본 `/` 화면에서 현재 구현된 기능으로 바로 이동할 수 있습니다. 기본 설정은 이 PC에서만 접속할 수 있습니다.

| 아이디 | 초기 비밀번호 | 권한 |
| --- | --- | --- |
| student1 | Lab1234! | 학생1 |
| student2 | Lab1234! | 학생2 |
| admin | Lab1234! | 관리자 |

모두 가상 실습 계정입니다. 최초 DB 생성 시 `.env`의 `LAB_PASSWORD`로 계정을 만듭니다. 이미 생성된 계정의 비밀번호는 `.env` 수정만으로 바뀌지 않습니다. `tools/setup_env.py`는 기존 `.env`를 덮어쓰지 않으며, 앱 서명키와 DB 비밀번호를 무작위로 생성합니다.

상태 확인은 `docker compose ps`, 로그 확인은 `docker compose logs --tail 50 web`입니다. 종료는 `docker compose stop`, 다시 시작은 `docker compose start`를 사용합니다. 코드 수정 후에는 build와 up을 다시 실행합니다.

DB와 업로드 파일은 Docker named volume에 저장되어 컨테이너 재생성 후에도 유지됩니다. `docker compose down -v`는 해당 데이터를 삭제하므로 일반 종료에는 사용하지 않습니다.

## 구현 범위

| 화면 | 동작 |
| --- | --- |
| 현재 구현된 기능 | `/`와 `/index`에서 구현된 화면 링크 제공 |
| 로그인 | 학생·관리자 로그인, 로그아웃, 세션 |
| 공지사항 | 목록·상세·검색·페이지 이동, 관리자 글 작성 |
| 과제 | 목록·검색·상세, 학생별 결과 파일 제출 및 다운로드 |
| 학습게시판 | 목록·상세·검색·페이지 이동, 학생 글 작성, 첨부파일 1개 |
| PBL | 36개 카드, 분야별 필터, 문제 상세, 파일 제출, 내 제출 파일 다운로드 |
| 자료실 | 목록·검색·상세 |
| FAQ | 목록·검색·상세 |
| 문의하기 | 학생별 문의 작성·조회, 첨부파일, 관리자 답변 |
| 마이페이지 | 사용자별 이메일·전화번호 조회 및 수정 |

게시판 본문은 일반 텍스트입니다. 서식 도구와 댓글은 없습니다. 과제와 PBL은 파일 제출 상태만 표시하며 채점, 선수 문제 잠금, 진도 계산은 하지 않습니다. PBL 문제 1번의 상세 본문·이미지는 제공된 자료를 사용했습니다. 나머지 문제는 자료에 있는 카드 제목·설명과 간단한 제출 안내를 사용합니다.

과제와 PBL 제출 파일은 제출한 학생과 관리자만 애플리케이션 다운로드 경로로 받을 수 있습니다. 문의는 작성자와 관리자만 조회할 수 있고, 학생은 자신의 프로필만 수정할 수 있습니다. 게시판 첨부파일은 로그인한 사용자에게 공개됩니다. 업로드는 문서·이미지·압축 파일로 제한하며 첨부파일을 포함한 요청 전체의 최대 크기는 16MB입니다.

현재는 취약점을 추가하기 전 정상 기능과 컨테이너 격리 기반을 구현한 상태입니다. 문의하기와 마이페이지에는 이후 인증·인가 비교 실습을 추가할 수 있도록 사용자별 데이터와 권한 검사를 구성했습니다. 내부 SSRF 실습용 `internal-service`는 실행되지만 사용자가 URL을 입력하는 SSRF 기능은 아직 없습니다. SQL Injection, Reflected XSS, 포트 스캐너와 관리자 페이지 노출 실습도 아직 추가하지 않았습니다. `/uploads/`에는 디렉터리 인덱싱 실습을 위한 nginx 목록 표시가 설정되어 있습니다.

## 화면 자료

`docs/`의 MHTML에서 CSS, 이미지, 공통 HTML 구조를 추출해 `static/reference/`와 `templates/reference/`에 저장했습니다. 원본 스크립트와 실제 계정 정보는 앱에 연결하지 않습니다. Noto Sans KR와 아이콘 폰트도 로컬에 저장해 실행 중 외부 사이트의 리소스를 요청하지 않습니다.

상단 메뉴·로고·클래스 정보·배너·게시판·PBL 카드의 원본 스타일을 재사용합니다. 구현하지 않은 링크에는 `data-unavailable` 표시를 남기고, 클릭하면 이동을 막은 뒤 `미구현입니다.` 알림을 표시합니다. 필요한 클릭 동작만 작은 JavaScript로 연결했습니다.

화면 자료를 갱신할 때만 아래 명령을 실행합니다. 일반 실행에는 필요하지 않습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe tools/import_reference.py
```

추출 과정은 공개 폰트 서버에서 폰트를 처음 다운로드할 수 있으며, 이미 저장된 폰트는 재사용합니다. 추출한 리소스·참조 템플릿·JSON을 다시 생성하며 원본 MHTML은 수정하지 않습니다. 로고와 원본 화면은 제공된 수업 자료에 기반한 교육용 미러에 사용합니다.

## 컨테이너 구성

```text
127.0.0.1:8080
  └─ nginx :8080
       ├─ web :8000 (Gunicorn + Flask)
       │    ├─ db :3306 (MySQL)
       │    └─ internal-service :9000 (고정 JSON 응답)
       └─ /uploads/ (교육용 디렉터리 인덱싱)
```

nginx만 호스트 포트를 게시합니다. nginx와 web은 내부 `proxy` 네트워크에서 연결되며, web·db·internal-service는 내부 `lab` 네트워크에 연결됩니다. 두 내부 네트워크는 `internal: true`와 bridge `isolated` 모드를 사용해 외부 라우트와 호스트 bridge 주소를 만들지 않습니다. web에는 일반 외부 네트워크를 연결하지 않습니다.

컨테이너는 일반 사용자, 읽기 전용 루트 파일시스템, capability 제거, `no-new-privileges`, 메모리·프로세스 제한으로 실행합니다. Docker socket·호스트 네트워크·AWS 자격증명·민감한 호스트 디렉토리는 연결하지 않습니다. DB 앱 계정은 SELECT·INSERT·UPDATE만 허용하고, 업로드는 별도 volume에 UUID 이름으로 저장합니다.

Docker는 호스트 커널을 공유하므로 이 구성만으로 호스트 탈출 불가능을 보장할 수는 없습니다. EC2에서는 인스턴스 메타데이터 접근, IAM 역할, 호스트 방화벽, 보안 그룹과 엔진 업데이트를 별도로 확인해야 합니다. 아직 EC2 배포와 AWS 격리 검증은 수행하지 않았습니다. 현재 `.env`의 로컬 주소 설정을 유지합니다.

## 검증

서비스를 실행한 뒤 Python 표준 라이브러리로 통합 검증을 실행합니다.

```powershell
python -m unittest discover -s tests -v
```

로그인·로그아웃, CSRF, 게시글 작성·검색·첨부파일, 공지 작성 권한, 과제·PBL 제출 파일의 사용자별 접근, 문의 소유권과 관리자 답변, 마이페이지 계정 분리, 업로드 형식, 구현 화면 인덱스 링크와 로컬 리소스를 확인합니다. 검증 과정에서 가상 게시글과 제출 파일이 추가됩니다. localhost에서만 실행하도록 제한되어 있습니다.

주요 파일은 `app.py`, `compose.yaml`, `db/init.sql`, `db/02-support.sql`, `templates/`, `static/app.css`, `static/app.js`입니다. 실행 중 필요한 Python 라이브러리는 Flask, PyMySQL, Gunicorn입니다.
