# SSLC Lab

제공된 SSLC MHTML 화면 자료를 바탕으로 만든 Flask 교육용 미러입니다. 로그인, 공지사항, 과제, 학습게시판, PBL, 자료실, FAQ, 문의하기, 마이페이지와 관리자 대시보드를 사용할 수 있습니다. SQL Injection, Reflected XSS, IDOR, 파일 업로드와 디렉터리 인덱싱 등을 실습할 수 있도록 일부 기능에 취약점을 구현했습니다. 아직 구현하지 않은 원본 화면 메뉴를 누르면 `미구현입니다.` 알림을 표시합니다.

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
| 현재 구현된 기능 | `/`와 `/index`에서 구현된 화면 링크와 적용된 취약점 안내 |
| 로그인 | 학생·관리자 로그인, 로그아웃, 세션 |
| 공지사항 | 목록·상세·검색·페이지 이동, 관리자 글 작성 |
| 과제 | 목록·검색·상세, 학생별 결과 파일 제출 및 다운로드 |
| 학습게시판 | 목록·상세·검색·페이지 이동, 학생 글 작성, 첨부파일 1개 |
| PBL | 36개 카드, 분야별 필터, 문제 상세, 파일 제출, 내 제출 파일 다운로드 |
| 자료실 | 목록·검색·상세 |
| FAQ | 목록·검색·상세 |
| 문의하기 | 내 문의 목록·검색, 문의 작성·상세 조회, 첨부파일, 관리자 답변 |
| 마이페이지 | 사용자 ID가 포함된 화면에서 REST API로 프로필 조회, 이메일·전화번호 수정 |
| 업로드 디렉터리 | `/uploads/`의 파일·하위 디렉터리 목록, 파일 접근, 업로드 스크립트 실행 |
| 관리자 페이지 | `/admin`에서 사용자 정보, 문의·파일 수, 최근 문의·업로드 목록 조회 |

게시판 본문은 일반 텍스트입니다. 서식 도구와 댓글은 없습니다. 과제와 PBL은 파일 제출 상태만 표시하며 채점, 선수 문제 잠금, 진도 계산은 하지 않습니다. PBL 문제 1번의 상세 본문·이미지는 제공된 자료를 사용했습니다. 나머지 문제는 자료에 있는 카드 제목·설명과 간단한 제출 안내를 사용합니다.

첨부파일을 포함한 요청 전체의 최대 크기는 16MB입니다. 업로드 화면에는 파일 선택만 있으며, 파일명은 multipart 요청의 `filename` 값으로 전달합니다. 별도의 저장 경로 입력란은 없습니다.

## 취약점 매핑

아래 경로는 기본 주소 `http://127.0.0.1:8080`을 기준으로 합니다. 로그인 후 `/`의 기능 인덱스에서도 각 화면과 적용된 취약점을 확인할 수 있습니다. 별도의 취약 모드 설정 없이 아래 동작을 제공합니다.

| 항목 | 적용 화면·경로 | 요청·입력 | 현재 동작 |
| --- | --- | --- | --- |
| SQL Injection | 학습게시판 검색 `/my-class/board/qna` | `GET`, `content` | 검색어를 SQL 문자열에 직접 연결합니다. DB 오류 발생 시 오류 내용을 화면에 표시하고, 입력 조건에 따라 검색 결과가 달라질 수 있습니다. |
| Reflected XSS | 학습게시판 검색 `/my-class/board/qna` | `GET`, `content` | 검색어를 검색 입력란의 HTML 속성에 인코딩 없이 반영합니다. 해당 화면의 CSP는 인라인 스크립트를 허용합니다. |
| Reflected XSS | 로그인 실패 메시지 `/login` | `POST`, `userId` | 실패한 아이디를 HTML 인코딩 없이 메시지에 반영합니다. 로그인 화면의 CSP는 인라인 스크립트를 허용합니다. |
| IDOR | 마이페이지 `/mypage/my-information/<user_id>`, API `/api/profiles/<user_id>` | 화면 `GET`, API `GET`·`PATCH`, 경로의 `user_id` | 로그인 여부만 확인하고 요청자와 대상 사용자 ID를 비교하지 않습니다. 다른 사용자의 프로필 조회와 이메일·전화번호 수정이 가능합니다. |
| 비밀글 권한 검증 누락 | 문의 상세 `/customer/contact/<inquiry_id>` | `GET`, 경로의 `inquiry_id` | 내 문의 목록은 계정별로 구분하지만, 상세 조회에서 소유자를 확인하지 않아 로그인한 다른 사용자도 문의 내용을 조회할 수 있습니다. |
| 파일 확장자 검증 우회 | PBL·과제 제출, 게시판·문의 첨부파일 | `POST`, 파일의 `filename` | 마지막 확장자 대신 파일명에 허용 확장자 문자열이 포함되는지만 확인하므로 복수 확장자로 우회할 수 있습니다. |
| 업로드 Path Traversal | 같은 업로드 기능 | `POST`, 파일의 `filename` | 파일명의 경로 구분자와 상위 디렉터리 이동을 저장 경로에 반영합니다. 기본 사용자·기능 디렉터리를 벗어날 수 있으며, 이동 범위는 업로드 볼륨 내부로 제한합니다. |
| 디렉터리 인덱싱 | `/uploads/`와 하위 디렉터리 | `GET` | nginx의 `autoindex on`으로 로그인 없이 파일·폴더 목록, 수정 시각과 크기를 표시합니다. |
| 파일 접근 권한 누락 | `/uploads/<저장된 파일 경로>` | `GET` | 애플리케이션 다운로드 권한 검사를 거치지 않고 nginx에서 파일을 제공합니다. 다른 사용자의 업로드 파일도 직접 접근할 수 있습니다. |
| 업로드 코드 실행 | `/uploads/` 아래 실행 확장자의 파일 | `GET`, 최종 확장자 `.php`·`.py`·`.cgi` | nginx가 별도의 `runner` 컨테이너로 전달합니다. PHP·Python 인터프리터와 `/bin/sh`로 실행한 출력·오류를 반환합니다. |
| 관리자 페이지 인증 누락 | `/admin` | `GET` | 로그인·관리자 권한 검사 없이 사용자 정보, 최근 문의와 업로드 목록을 반환합니다. |

공지사항 검색 `/my-class/board/notice`의 `content`는 파라미터 바인딩과 HTML 인코딩을 적용한 비교 대상입니다. 공지사항 글 작성의 관리자 권한 검사, 문의 답변의 관리자 권한 검사와 기존 `POST` 요청의 CSRF 검사는 유지합니다. 자료실·FAQ와 마이페이지에는 Reflected XSS를 적용하지 않았습니다.

마이페이지의 기존 `/mypage/my-information` 주소는 로그인한 사용자의 ID가 붙은 화면으로 이동합니다. 화면의 JavaScript가 동일한 ID로 REST API를 호출합니다. API는 비로그인 요청에 `401`, 존재하지 않는 사용자에 `404`를 반환하지만, 로그인한 다른 사용자의 요청은 소유권 검사 없이 처리합니다.

업로드 엔드포인트는 다음과 같습니다. 모두 공통 `save_upload()` 함수를 사용합니다.

| 화면 | 업로드 경로 | 파일 필드 | 기본 저장 경로 |
| --- | --- | --- | --- |
| PBL 문제 상세 | `/my-class/pbl/<problem_id>` | `taskResult` | `<user_id>/pbl/` |
| 과제 상세 | `/my-class/board/task/<task_id>` | `taskResult` | `<user_id>/task/` |
| 학습게시판 글 작성 | `/my-class/board/write/qna` | `file` | `<user_id>/qna/` |
| 공지사항 글 작성 | `/my-class/board/write/notice` | `file` | `<user_id>/notice/` |
| 문의 작성 | `/customer/contact/write` | `file` | `<user_id>/contact/` |

저장 파일명에는 충돌 방지를 위한 임의 접두사가 붙습니다. 공지사항 첨부파일도 공통 업로드 함수를 사용하므로 파일 업로드 취약점이 적용되며, 글 작성은 관리자만 가능합니다. `/download/<file_id>`는 로그인이 필요하고 과제·PBL·문의 첨부파일의 소유자 또는 관리자 권한을 확인합니다. `/uploads/`의 직접 접근에는 이 검사가 없어 업로드·목록 노출·파일 접근을 연계해 볼 수 있습니다. 디렉터리 인덱싱 자체는 목록 노출이고, 코드 실행은 nginx의 실행 파일 경로와 `runner`가 담당합니다.

SSRF는 내부 대상인 `internal-service`만 실행 중이며 사용자 URL을 받는 기능은 아직 없습니다. 포트 스캐너도 아직 구현하지 않았습니다. 인증 누락은 `/admin`과 `/uploads/`에서, 인증된 사용자의 권한 검증 누락은 문의 상세와 마이페이지 API에서 실습합니다.

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
       ├─ /uploads/ (파일 제공·디렉터리 인덱싱)
       └─ runner :9100 (업로드된 PHP·Python·CGI 실행)
```

nginx만 호스트 포트를 게시합니다. nginx와 web은 내부 `proxy` 네트워크에서, web·db·internal-service는 내부 `lab` 네트워크에서 연결됩니다. nginx와 runner는 별도 내부 `execution` 네트워크를 사용합니다. 세 내부 네트워크는 `internal: true`와 bridge `isolated` 모드를 사용해 외부 라우트와 호스트 bridge 주소를 만들지 않습니다. web과 runner에는 일반 외부 네트워크를 연결하지 않습니다.

컨테이너는 일반 사용자, 읽기 전용 루트 파일시스템, capability 제거, `no-new-privileges`, 메모리·프로세스 제한으로 실행합니다. Docker socket·호스트 네트워크·AWS 자격증명·민감한 호스트 디렉토리는 연결하지 않습니다. DB 앱 계정은 SELECT·INSERT·UPDATE만 허용합니다. 업로드 named volume은 web에서 쓰고 nginx·runner에서는 읽기 전용으로 연결합니다. runner에는 앱 서명키와 DB 비밀번호를 전달하지 않으며, 실행 제한 시간은 5초입니다.

Docker는 호스트 커널을 공유하므로 이 구성만으로 호스트 탈출 불가능을 보장할 수는 없습니다. EC2에서는 인스턴스 메타데이터 접근, IAM 역할, 호스트 방화벽, 보안 그룹과 엔진 업데이트를 별도로 확인해야 합니다. 아직 EC2 배포와 AWS 격리 검증은 수행하지 않았습니다. 현재 `.env`의 로컬 주소 설정을 유지합니다.

## 검증

서비스를 실행한 뒤 Python 표준 라이브러리로 통합 검증을 실행합니다.

```powershell
python -m unittest discover -s tests -v
```

현재 기능 테스트 12개를 사용합니다. 로그인·로그아웃, CSRF, 게시글 작성·검색·첨부파일, 공지 작성 권한, 과제·PBL 제출과 애플리케이션 다운로드 권한, 문의 작성·목록 구분·다른 계정의 상세 조회, 프로필 API 수정, 관리자 페이지 접근, 업로드 형식과 PHP·Python·CGI 실행, 구현 화면 링크와 로컬 리소스를 확인합니다. 검증 과정에서 가상 게시글과 제출 파일이 추가됩니다. localhost에서만 실행하도록 제한되어 있습니다. 테스트 통과는 현재 기능 동작을 확인한 결과이며, 모든 취약점 유형이나 EC2 격리를 검증했다는 뜻은 아닙니다.

주요 파일은 `app.py`, `compose.yaml`, `nginx/nginx.conf`, `Dockerfile.runner`, `upload_runner.py`, `db/init.sql`, `db/02-support.sql`, `templates/`, `static/app.css`, `static/app.js`입니다. 웹 서비스의 Python 라이브러리는 Flask, PyMySQL, Gunicorn이며 runner는 Python 표준 라이브러리와 PHP CLI를 사용합니다.
