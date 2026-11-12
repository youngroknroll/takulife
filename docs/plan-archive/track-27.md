# 트랙 27: 여정 기반 e2e 스위트 재도입 — pytest-playwright + live_server (2026-09-09) [v2 — TDD 코치·QVL·DOR·BIR 검토 반영]

> **검토 반영 요약(v1 → v2)** [각 역할 산출, 인용 file:line은 오케스트레이터가 rg/sed로 재확인 2026-09-09]
> - TDD 코치(v1 Reject → 아래 4건 반영): ① **E3 분리** — 생성·수정·삭제는 서로 다른 fetch(`collection.js:233` post / `:390` patch /
>   `collection_detail.js:61` del [실측 rg])라 한 뮤테이션이 셋을 덮지 못함 → 한 파일 안에 테스트 3건(E3a·E3b·E3c), 각자 뮤테이션.
>   ② E3 삭제 뮤테이션 "뒤 `/` 제거"는 **약함** — 테스트 중 DEBUG=False(pytest-django `django_debug_mode` 기본 [코드 plugin.py:143])라
>   `APPEND_SLASH` 301이 나가고 fetch는 DELETE 메서드를 보존해 재요청 → 204 → Green 유지 가능. → 경로 세그먼트 변경(`/api/collection-
>   items/` → `/api/collection-item/`)으로 교체(진짜 404). ③ E5 뮤테이션 줄 인용 오류 — `archive_search.js:126`은 `fetchParams.set
>   ("partial","1")` [실측] → "126행 **다음에** `fetchParams.delete("q")` 삽입"으로 확정(partial 보존). ④ **`login_as`가 `user_logged_in`
>   시그널을 우회** — `accounts/signals.py:9` `cancel_pending_deletion_on_login`이 이 시그널에 걸려 있음 [실측] → 세션 키 수기 작성
>   대신 `RequestFactory` 더미 request + `django.contrib.auth.login()`으로 세션 생성(시그널 보존, 뷰는 여전히 안 거쳐 레이트리밋 무관).
>   E4 뮤테이션 줄 `visit_create.js:234` 명시. Test List에 `경계 근거`·`Evidence` 열 추가. E5 이름을 Then과 일치.
> - QVL: ① `DJANGO_ALLOW_ASYNC_UNSAFE`를 conftest 모듈 최상단에 두면 **기본 백엔드 실행에도 샘**(deselect는 수집 뒤라 conftest는
>   항상 임포트) → tests/e2e 전용 session autouse 픽스처로 이동. ② E2는 `location.reload()`(URL 불변)라 `to_have_url` 불가 →
>   `expect(locator)` 재시도로 흡수. ③ E7 결과 텍스트 단언을 `page.goto("/events/")` **이전**에 고정. ④ 임시 `-m` 실행이 addopts의
>   `not e2e`를 대체하는 함정 → AGENTS.md에 한 줄 경고. ⑤ CI 잡 그린은 로컬로 증명 불가 → PR Actions 실행 로그를 완료 증거로 명시.
>   ⑥ 승인: E3c에 모달 `아니오` 경로(삭제되지 않음) 한 단계 추가. ⑦ `clear_cache_e2e` E1·E8만 = 정확(allauth login 한도는 GET도 셈).
> - DOR: ① `e2e` 잡은 **`continue-on-error: true`로 시작**, main 연속 10회 [문서 DOR 제안 기준] 비결함 그린 뒤 필수 게이트 전환(사용자
>   결정). ② `actions/cache@v4`로 `~/.cache/ms-playwright`를 `hashFiles('uv.lock')` 키로 캐시. ③ `actions/upload-artifact@v4`
>   `if: failure()` `retention-days: 7`(트레이스에 테스트 세션 쿠키·테스트 비밀번호가 담김 — 운영 비밀 아님, 창만 최소화). ④ 잡은 자체
>   `services: postgres` 블록 복제(기존 관례). ⑤ e2e 잡에 `DEBUG` env를 **설정하지 않는다**(`STORAGES["staticfiles"]`는 import 시 env
>   DEBUG로 결정 — false면 매니페스트 부재 ValueError). ⑥ 롤백 한 줄 = 잡에 `if: false`. ⑦ `uv.lock`을 1단계 커밋에 반드시 포함.
>   R2 확정: pytest-django `live_server`는 staticfiles 설치 시 `StaticFilesHandler`(finders 기반, collectstatic 불필요) [실측
>   `.venv/.../pytest_django/live_server_helper.py:30-37`].
> - BIR(High 3건): ① E2 `/archive/statuses/`의 "방문 예정"은 요약 카드(`statuses.html:16`)와 행 span이 중복 → `#archive-results`
>   스코프 필수. ② E2 상세는 reload 뒤 `status-row`가 `hidden`으로 DOM에 남아(`detail.html:102`) "방문 예정" 2건 매치 → 결합 텍스트
>   `현재 상태: 방문 예정`(`detail.html:93`)으로 단언. ③ E4 홈 "기록"은 `기록 대기`(`:50`)·액션 링크 `기록`(`:77`)·빈 상태(`:132`)와
>   충돌 → `get_by_text("기록 1", exact=True)`(dt+dd 결합 텍스트). Must: `대상`은 `select_option(label=)`, 모달 `예`/`아니오`는
>   트리거 클릭 **뒤에** 질의(DOM 지연 생성 `confirm-modal.js:129-131`), 재방문은 `page.goto`(bfcache·`go_back` 금지), E6 링크는
>   정규식 `이벤트 #\d+ 보기`, 라벨 `이메일`·`비밀번호`·`현재 비밀번호로 확인`은 sr-only "(필수)"가 붙어 `exact=True` 금지.
> - 오케스트레이터 확정: R1 — 경계 가드는 `test_*_api.py`/`test_*_view(s).py` 글롭 또는 `client`·`admin_client`·`user_client`·
>   `staff_client` 인자 선언 파일만 대상 [실측 `tests/core/test_architecture_boundaries.py:619-621,697-707`] → `test_*_e2e.py`에
>   `page`·`live_server`·e2e 픽스처만 쓰면 대상 밖. pytest-playwright 0.9.0의 `base_url`·`browser_context_args`는 둘 다 session 스코프
>   [실측 ephemeral env `inspect.getsource`] → tests/e2e/conftest.py의 `base_url` 오버라이드가 e2e 컨텍스트에 적용됨(CLI `--base-url`은
>   e2e에서 무시됨을 문서화).

> 배경: 사용자 결정(2026-09-09) ① 2026-07-22 "자동 테스트=백엔드 로직만, e2e 전면 삭제" 정책을 **부분 철회** — 여정 기반·JS fetch·
> 다중 페이지 세션 흐름에 한정한 e2e만 허용, 기하·CSS·애니메이션·포커스 위치 단언은 계속 금지 ② 러너 = pytest-playwright + Django
> `live_server` ③ 초기 편입 = 아래 8건 전부. 삭제된 옛 스위트(커밋 2a6b22b, PR #209)는 29파일·2,502줄 [실측 `git show --stat 2a6b22b`]
> 중 여정 검증은 약 5파일, 나머지 약 24파일은 터치 타깃·오버플로·bfcache·reduced-motion 등 렌더 기하 측정 [파일명 기준 읽음]이라
> 리디자인마다 깨져 삭제됐다. 이번 스위트는 그 실패를 편입 기준으로 막는다. 기준선 [실측 2026-09-09 main 29c42ea]
> `uv run pytest -q` 2541 passed / 74.33초. `tests/e2e/`에는 `.py` 0건, git-ignored `__pycache__`만 남아 있다 [실측 `find`·`git
> check-ignore`]. `playwright` 1.61.0은 dev 그룹에 이미 있고 [실측 `uv pip show`], `pytest-playwright`는 없다 — `uv pip install
> --dry-run pytest-playwright` 결과 0.9.0 + pytest-base-url 2.1.0 + python-slugify + text-unidecode 4패키지 추가 [실측]. 로컬
> Chromium 캐시(chromium-1228) 존재 [실측 `ls ~/Library/Caches/ms-playwright`]. 로컬·CI 모두 Postgres(`DATABASE_URL`, CI 서비스 컨테이너).

## 편입 기준 (구속 — 옛 스위트 실패의 직접 대응)

1. **여정만.** 테스트 하나는 사용자가 여러 화면을 거쳐 무엇을 이루는지를 따라가고, 마지막 단언은 **DB 상태 또는 다음 페이지에 보이는
   내용**이다. 기하(크기·위치·오버플로)·CSS 클래스·애니메이션·reduced-motion·bfcache·포커스 위치·터치 타깃 단언 금지.
2. **Django 테스트 클라이언트가 못 잡는 것만.** 편입 조건은 둘 중 하나: (a) 브라우저 JS fetch가 개입(`status.js`·`collection.js`·
   `collection_detail.js`·`visit_create.js`·`archive_search.js`·`draft.js`·`event_bulk.js`·`confirm-modal.js`), (b) 세션이 여러
   페이지에 걸쳐 이어지는 흐름(로그인 게이트·로그아웃·탈퇴 후 세션 소거). 서버 렌더만으로 끝나는 페이지는 기존 `web` 계층이 담당.
3. **셀렉터는 역할·라벨·텍스트만.** `get_by_role`·`get_by_label`·`get_by_text`·`get_by_placeholder`만 허용, CSS 클래스·`data-*`
   속성 스크래핑 금지. 예외는 서버가 제공하는 안정 id 컨테이너(`#archive-results`, `#draft-approve-success`, `#event-bulk-result`)를
   **범위 한정**에만 쓰는 것(단언은 그 안의 텍스트·링크로).
4. **자동 대기 단언만.** `expect(locator)`·`expect(page).to_have_url` 계열만. `wait_for_timeout`·`sleep`·`wait_for_load_state
   ("networkidle")` 금지. 디바운스(250ms [코드 `archive_search.js:19`])도 자동 대기로 흡수.
5. **이미-Green 핀은 뮤테이션 증거 필수.** 기존 기능을 덮는 e2e는 첫 실행이 Green이므로, Test List의 지정 뮤테이션(운영 코드 1곳
   임시 변경)으로 Red를 실증하고 되돌린 기록이 Evidence에 있어야 한다.
6. **상한.** 초기 8건 [문서 사용자 결정], 이후 추가는 "JS fetch 또는 다중 페이지 세션" 조건을 통과하는 **실제 결함**이 발생했을 때만.

## 승인 범위

1. **의존성·마커·기본 실행 분리** — `uv add --group dev pytest-playwright`(플러그인 추가; `playwright` 라이브러리는 그대로).
   `pytest.ini`: `e2e` 마커 등록 + `addopts = -m "not e2e" --strict-markers`(옛 pytest.ini 원문 [실측 `git show 2a6b22b^:pytest.ini`]
   과 동일 형태) → 기본 `uv run pytest -q`는 백엔드만, e2e는 `uv run pytest -q -m e2e tests/e2e`(CLI `-m`이 addopts `-m`을 덮음).
   pytest.ini 주석의 "removed on 2026-07-22" 문단은 철회 사실로 교체.
2. **`tests/e2e/conftest.py`** (신규, 200줄 이하 목표 [계산]) — 소유 계약:
   - `DJANGO_ALLOW_ASYNC_UNSAFE=1`은 **모듈 최상단이 아니라** tests/e2e 전용 `scope="session", autouse=True` 픽스처에서 설정하고
     종료 시 복원(QVL: conftest 모듈은 deselect와 무관하게 항상 임포트되므로 최상단 설정은 백엔드 실행에 샘). 이유는 옛 conftest
     선례와 같다 — Playwright sync API의 이벤트 루프가 Django ORM 가드를 건드림.
   - `pytest_collection_modifyitems`로 `tests/e2e/` 아래 모든 항목에 `e2e` 마커 자동 부여(파일마다 `pytestmark` 반복 불필요).
   - `base_url` 픽스처를 `live_server.url`로 덮어씀(pytest-base-url·pytest-django 둘 다 session 스코프) → 테스트는 `page.goto("/events/")`.
   - `page` 파생: `page.set_default_timeout(10_000)`(ms) — 기본 30초 대기를 줄여 실패를 빨리 드러냄 [코드 기본값 Playwright].
   - `verified_user(email=None, *, password=None, is_staff=False)` 팩토리 — `create_user` + `EmailAddress(verified=True, primary=True)`
     (`ACCOUNT_EMAIL_VERIFICATION="mandatory"` [코드 `config/settings.py:424`]). `transactional_db` 기반(live_server 요구, 루트
     `make_user`(`db`)와 배타).
   - **`login_as(user)`** — 로그인 **뷰**를 거치지 않되 Django 인증 파이프라인은 그대로 태운다: `RequestFactory().get("/")`로 더미
     request를 만들고 `request.session = SessionStore()`를 붙인 뒤 `django.contrib.auth.login(request, user, backend=
     "django.contrib.auth.backends.ModelBackend")`(`AUTHENTICATION_BACKENDS` 2번째 [코드 `config/settings.py:407-413`]) →
     `request.session.save()` → `context.add_cookies([{name: settings.SESSION_COOKIE_NAME(기본 sessionid), value:
     request.session.session_key, url: live_server.url}])`. 이렇게 하면 `user_logged_in` 시그널이 발화해 `accounts/signals.py:9`
     `cancel_pending_deletion_on_login`·axes `handle_user_logged_in`·`update_last_login`이 실제 로그인과 같게 실행된다(TDD 코치
     Blocking ④ — 세션 키 수기 작성은 이 시그널을 숨긴다). docstring에 "로그인 뷰·레이트리밋·axes 잠금은 거치지 않는다"를 명시.
     `SESSION_ENGINE`·`SESSION_COOKIE_NAME` 미설정 = Django 기본 [실측 rg], `SESSION_COOKIE_SECURE`는 env `SECURE_COOKIES` 미설정
     시 False [코드 `:518`] → http live_server에서 쿠키 유효. 뷰를 피하는 이유: allauth 기본 login 레이트리밋 `30/m/ip`가 GET·성공
     POST를 모두 세어(QVL 확인 `allauth/account/views.py:99`) 폼 로그인을 반복하면 뒤쪽 테스트가 429로 조용히 실패한다.
   - `clear_cache_e2e(transactional_db)` — 폼 로그인을 실제로 거치는 E1·E8만 요청(루트 `clear_cache`는 `db` 기반이라 배타).
   - 팩토리: `make_published_event(title, **kw)`, `make_pending_draft(**kw)`(`extracted_category="popup_store"`,
     `extracted_region="seoul"` — `tests/drafts/test_draft_vocab_guard.py:38` 선례 [실측], `source_url` 유일).
3. **여정 테스트 8파일 / 테스트 10건** [계산 — E3만 3건] — `tests/e2e/test_<여정>_e2e.py`, 파일 1건 = 여정 1건(DAMP). E3 파일은
   생성·수정·삭제 테스트 3건을 담는다(TDD 코치 ①). 이름은 한국어 여정 문법. 세부는 Test List. 파일 안에서 `client`·`user_client`
   류 인자 이름을 절대 쓰지 않는다(경계 가드 R1).
4. **CI** — `.github/workflows/ci.yml`에 `e2e` 잡 신설(옛 잡 원문 [실측 `git show 2a6b22b^:.github/workflows/ci.yml:94-130`] 복원 +
   DOR 보강): 자체 `services: postgres` 블록 복제, **`continue-on-error: true`**(관측 기간; 전환 규칙은 backlog에 기록), `DEBUG` env
   미설정, `uv sync --frozen`, `actions/cache@v4`(`path: ~/.cache/ms-playwright`, `key: ${{ runner.os }}-playwright-${{ hashFiles(
   'uv.lock') }}`), `uv run playwright install --with-deps chromium`, `uv run pytest -q -m e2e tests/e2e --tracing retain-on-failure
   --output e2e-artifacts`, `actions/upload-artifact@v4` `if: failure()` `retention-days: 7` `path: e2e-artifacts/`. 재시도 플러그인은
   넣지 않는다(플레이키가 실제로 관측될 때 별도 결정). 롤백 = 잡에 `if: false` 한 줄. `test` 잡은 무변경(`uv run pytest -q`가
   addopts로 e2e 제외).
5. **정책 문서 갱신(같은 PR)** — `AGENTS.md` ① "Automated Tests Cover Backend Logic Only" 절 제목·본문을 "부분 철회(2026-09-09)"로
   고쳐 편입 기준 6항 요약 ② 계층표에 `e2e` 행 추가, "There is no browser layer" 문장 교체 ③ Frontend Work Policy의 "Do not write
   browser or end-to-end tests" 두 곳 수정(기하 측정은 여전히 실측·미커밋) ④ 경고 한 줄: 임시 `-m <expr>` 실행은 addopts의 `not e2e`를
   **대체**하므로 `-m "<expr> and not e2e"`로 쓸 것(QVL ④). `CLAUDE.md:90-93` 스택 문단 갱신. `docs/backlog.md` "현재 상태" 표에 e2e
   명령·건수 행 추가 + `continue-on-error` 전환 규칙(미해결 결정). 메모리 `backend-only-test-policy`는 오케스트레이터가 갱신(저장소 밖).
6. **잔재 정리** — `tests/e2e/__pycache__`(git-ignored) 삭제.

**명시 제외**: 템플릿·CSS·브라우저 JS·뷰·모델 변경 0건(뮤테이션은 임시이며 커밋 금지). 이메일 발송·소셜 로그인·비밀번호 재설정·
사진 업로드·Firefox/WebKit·xdist 병렬·재시도 플러그인·시각 회귀·Lighthouse. 기하 실측은 지금처럼 리뷰어의 임시 Playwright/MCP.

## Activated Roles / Not Activated

- Activated: Backend TDD Coach(Test List·뮤테이션 증거 계약), Quality Verification Lead(AC↔증거 매핑·플레이키 판단),
  Deployment & Operations Reviewer(CI 잡·아티팩트·의존성), Browser Interaction Reviewer(여정의 비동기 대기·셀렉터·복구 경로 기준),
  Backend & Integration Engineer(conftest·테스트·CI·문서 구현).
- Not Activated: Product Scope Owner(범위는 사용자가 직접 결정), Domain Architecture Reviewer(운영 코드 무변경; 테스트 경계 가드
  `tests/core/test_architecture_boundaries.py:619-621,697-751`은 `test_*_e2e.py`·Playwright 픽스처에 반응하지 않음 [실측 오케스트레이터
  sed — R1 확정]), Security & Resilience Reviewer(`login_as`는 테스트 전용, 운영 코드 무변경 — DOR가 트레이스 아티팩트 보존 7일로
  노출 창 최소화), Web Experience Designer·Frontend Implementation Engineer(프론트 산출물 0건), AI Automation Architect.

## Test List (경계 `e2e` 신설 — 실제 Chromium + live_server; Red = 지정 뮤테이션 실증)

| ID | 여정(한 문장) | Given | When | Then | 경계 근거(왜 e2e인가 / 하위 계층 재확인은 무엇인가) | 뮤테이션(Red 증거) | 테스트 이름 | 상태 / Evidence |
|---|---|---|---|---|---|---|---|---|
| E1 | 로그인하면 next로 착지하고 로그아웃하면 보호 페이지가 다시 로그인으로 보낸다 [코드 `login.html:51-57`, `_topbar.html:20,36-38`, `web/views/archive.py:182`] | 인증 완료 사용자(비밀번호 있음), `clear_cache_e2e` | `/accounts/login/?next=/archive/`에서 라벨 `이메일`·`비밀번호`(부분 일치, sr-only "(필수)" 포함) 입력 → 버튼 `로그인` → 버튼 `계정 메뉴` → 버튼 `로그아웃` → `page.goto("/archive/")` | 1차 URL `/archive/`, 로그아웃 후 URL이 `/accounts/login/?next=/archive/` | 다중 페이지 세션(2-b). next 착지는 `tests/auth/test_login_redirect_landing.py` [실측 ls]가 web 계층에서 보호 → 재확인. 신규 위험은 실제 브라우저 쿠키로 이어지는 로그아웃 게이트 하나 → 뮤테이션 1곳으로 충분 | `web/views/archive.py:182` `@login_required` 제거 | `test_로그인한_사용자가_로그아웃하면_보호_페이지가_다시_로그인을_요구한다` | **Red-검증됨** [실측 2026-09-09] Green 1 passed/5.43초 → 뮤테이션 Red: 마지막 `to_have_url` 실패(actual `/archive/`) → 복원 Green 1 passed/3.19초. 백엔드 `uv run pytest -q` 2541 passed, 1 deselected/73.41초 |
| E2 | 이벤트 상세에서 방문 예정을 누르면 아카이브 일정에 나타난다 [코드 `detail.html:93,102-110`, `status.js:213-224,257-269`, `statuses.html:16,80`, `_archive_results_statuses.html:62`] | `login_as(user)`, 게시 이벤트 1건 | `/events/<id>/` 버튼 `방문 예정` 클릭(POST 후 `location.reload`, URL 불변) → `page.goto("/archive/statuses/")` | 상세에 텍스트 `현재 상태: 방문 예정`(결합 텍스트, BIR ②) `to_be_visible`, 일정 페이지 `#archive-results` 스코프 안에 링크 `<제목>`과 텍스트 `방문 예정`(BIR ①), DB `UserEventStatus(status="planned")` 1행 | JS fetch(2-a). 상태 API 자체는 `tests/archive/test_user_event_status_api.py`가 web 계층에서 보호 → 재확인. 신규 위험 = 버튼→payload→reload 배선 | `status.js:214` payload 키 `status` → `state` | `test_이벤트_상세에서_방문_예정을_누르면_아카이브_일정에_나타난다` | **Red-검증됨** [실측 2026-09-10] 스위트 Green 10 passed/10.38초 → 뮤테이션 Red `현재 상태: 방문 예정` not visible (1 failed/7.82초) → 복원 Green(최종 스위트 10 passed/10.02초) |
| E3a | 컬렉션 항목을 만들면 목록에 나타나고 상세가 열린다 [코드 `collection_create.html:150`, `collection.js:233,236`, `_archive_results_collection.html:29`] | `login_as(user)` | `/collection/new/` 라벨 `이름` 입력 → 버튼 `항목 저장` → 목록 링크 `<이름>` 클릭 | 생성 후 URL `/collection/`, 클릭 후 URL `/collection/<id>/`에 헤딩 `<이름>`, DB `CollectionItem` 1행 | JS fetch(2-a) POST 경로. API는 `tests/archive/test_collection_items_api.py` 보호 → 재확인 | `collection.js:233` URL 세그먼트 `/api/collection-items/` → `/api/collection-item/` | `test_컬렉션_항목을_만들면_목록에_나타나고_상세가_열린다` | **Red-검증됨** [실측 2026-09-10] 뮤테이션 Red URL `/collection/new/` 잔류(파일 1 failed, 2 passed/9.73초) → 복원 Green |
| E3b | 컬렉션 항목 이름을 고치면 상세가 새 이름을 보여준다 [코드 `collection_detail.html:27`, `collection_edit.html:30-32,161`, `collection.js:390,393`] | `login_as(user)`, ORM으로 만든 항목 1건 | `/collection/<id>/` 링크 `수정` → 라벨 `이름` 값 교체 → 버튼 `저장` | URL `/collection/<id>/`, 헤딩이 새 이름, DB `name` 갱신 | JS fetch(2-a) PATCH 경로 — POST와 다른 호출이라 별도 뮤테이션 필요(TDD 코치 ①) | `collection.js:390` URL 세그먼트 `/api/collection-items/` → `/api/collection-item/` | `test_컬렉션_항목_이름을_고치면_상세가_새_이름을_보여준다` | **Red-검증됨** [실측 2026-09-10] 뮤테이션 Red URL `/collection/<id>/edit/` 잔류(파일 1 failed, 2 passed/10.32초) → 복원 Green |
| E3c | 컬렉션 항목 삭제를 확인하면 목록이 빈 상태가 되고, 취소하면 남는다 [코드 `collection_detail.html:28-32`, `collection_detail.js:61,63`, `confirm-modal.js:63-71,129-131`, `_archive_results_collection.html:114-120`] | `login_as(user)`, ORM으로 만든 항목 1건 | `/collection/<id>/` 버튼 `굿즈 삭제` → 모달 버튼 `아니오`(QVL ⑥) → 같은 페이지에서 다시 `굿즈 삭제` → 모달 버튼 `예` | `아니오` 뒤 URL 불변·DB 1행 유지, `예` 뒤 URL `/collection/`에 텍스트 `아직 등록한 컬렉션이 없어요`, DB 0행. 모달 버튼은 트리거 클릭 뒤 질의 | JS fetch(2-a) DELETE + 확인 모달 취소 경로(테스트 클라이언트가 못 잡는 브라우저 상호작용) | `collection_detail.js:61` URL 세그먼트 `/api/collection-items/` → `/api/collection-item/`(진짜 404; 뒤 `/` 제거는 APPEND_SLASH 301+DELETE 보존으로 Green 유지 가능 — 채택 금지) | `test_컬렉션_항목_삭제를_확인하면_목록이_빈_상태가_되고_취소하면_남는다` | **Red-검증됨** [실측 2026-09-10] 뮤테이션 Red URL 상세 잔류(파일 1 failed, 2 passed/9.57초) → 복원 Green |
| E4 | 방문 기록을 남기면 방문 기록 목록에 나타난다 [코드 `visit_create.html:46-71,96`, `visit_create.js:15,234,252,271`, `_archive_results_visits.html:46`] **(v3 정정 — 홈 스냅샷 Then 철회: `snapshot_active`(`web/views/events.py:126-131`)는 방문 기록 수를 보지 않아 기록 1건뿐이면 홈이 빈 상태를 보여줌 [실측 2026-09-10 첫 실행 실패] → 제품 판단은 백로그)** | `login_as(user)`, 게시 이벤트 1건 + 그 이벤트에 `planned` 상태(`selectable_events`는 planned만 [코드 `archive/queries.py:265`]) | `/archive/visits/new/` 라벨 `대상`에 `select_option(label=<제목>)`, 라벨 `방문 날짜`에 `YYYY-MM-DD` 입력 → 버튼 `기록 저장` | URL `/archive/visits/`, `#archive-results` 안 링크 `<제목>` 보임, DB `VisitRecord` 1행 | JS fetch(2-a). API는 `tests/archive/test_visit_records_api.py` 보호 → 재확인. 신규 위험 = select 값 파싱 `event:<id>` → payload 배선 | `visit_create.js:234` payload 키 `visited_on` → `visited` | `test_방문_기록을_남기면_방문_기록_목록에_나타난다` | **Red-검증됨** [실측 2026-09-10] 뮤테이션 Red URL `/archive/visits/new/` 잔류(1 failed/8.33초) → 복원 Green |
| E5 | 아카이브 검색어를 입력하면 새로고침 없이 결과가 좁혀지고 결과 링크로 이동한다 [코드 `_archive_search.html:26-32`, `archive_search.js:19,126,153,157`, `statuses.html:80`] | `login_as(user)`, 제목이 다른 게시 이벤트 2건에 planned 상태 [코드] | `/archive/statuses/` 입력(`get_by_label("아카이브 검색")` 또는 placeholder)에 첫 제목의 앞 단어 `fill`(제출 없음) → `#archive-results` 안 첫 제목 링크 클릭 | `#archive-results` 안에 첫 제목 링크 보임·둘째 제목 `to_have_count(0)`, URL에 `q=`(pushState), 클릭 후 URL `/events/<id>/` | JS fetch(2-a) 디바운스+조각 교체+pushState. 서버 `partial` 렌더는 `tests/archive/test_archive_partial.py` 보호 → 재확인 | `archive_search.js:126` **다음 줄에** `fetchParams.delete("q");` 삽입(partial 보존, 필터만 무력화) | `test_아카이브_검색어를_입력하면_새로고침_없이_결과가_좁혀지고_링크로_이동한다` | **Red-검증됨** [실측 2026-09-10] 뮤테이션 Red 둘째 제목 `to_have_count(0)` 기대, actual 1(1 failed/8.20초) → 복원 Green |
| E6 | 스태프가 드래프트를 승인하면 공개 이벤트가 된다 [코드 `drafts/detail.html:166,169`, `draft.js:191-224`, `staff/views/drafts.py:65-92`] | `login_as(staff)`, pending 드래프트 1건(제목·유일 source_url·`popup_store`·`seoul`) | `/staff/drafts/<id>/` 버튼 `승인하고 게시` → 모달 `예` → `#draft-approve-success` 안 링크 `re.compile(r"이벤트 #\d+ 보기")` 클릭 | `#draft-approve-success` `to_be_visible`·텍스트 `승인 완료`, 클릭 후 URL `/events/<n>/`에 제목, DB `Event.publish_status="published"`·`EventDraft.review_status="approved"` | JS fetch(2-a). 승인 서비스는 `tests/drafts/`·`tests/staff/` 보호 → 재확인 | `draft.js:201` approve URL `/approve/` → `/approved/` | `test_스태프가_드래프트를_승인하면_공개_이벤트_상세가_열린다` | **Red-검증됨** [실측 2026-09-10] 뮤테이션 Red `#draft-approve-success` hidden(1 failed/8.44초) → 복원 Green |
| E7 | 스태프가 이벤트를 골라 비공개로 설정하면 공개 목록에서 사라진다 [코드 `staff/events/list.html:34-42,75-76`, `event_bulk.js:75-76,196,266`, `events/querysets.py:11-12`] | `login_as(staff)`, 게시 이벤트 2건 | `/staff/events/` 체크박스 `<제목A> 선택` → 버튼 `선택 항목 비공개로 설정`(활성화 자동 대기) → 모달 `예` → **`#event-bulk-result` 텍스트 단언 뒤에** `page.goto("/events/")`(QVL ③) | `#event-bulk-result` 텍스트 `1건 모두 비공개 완료.`, 공개 목록에 제목B 링크 있고 제목A `to_have_count(0)`, DB A=`draft`·B=`published` | JS fetch(2-a). 뷰는 `tests/staff/test_staff_event_bulk_unpublish*.py` 보호 → 재확인 | `event_bulk.js:266` 본문 키 `event_ids` → `ids` | `test_스태프가_이벤트를_골라_비공개로_설정하면_공개_목록에서_사라진다` | **Red-검증됨** [실측 2026-09-10] 첫 실행 Red(403 CSRF — 픽스처 결함, 위 발견 ①) → `login_as` CSRF 쿠키 후 Green → 뮤테이션 Red 결과 텍스트 빈값(1 failed/8.32초) → 복원 Green |
| E8 | 탈퇴를 요청하면 완료 페이지로 가고 같은 브라우저의 세션이 끊긴다 [코드 `delete_account.html:57-70`, `web/views/account.py:196-208`, `accounts/views.py:42-58`, `delete_done.html:32`] | `login_as(user)`(비밀번호 있음, 비스태프), `clear_cache_e2e` | `/accounts/delete/` 라벨 `현재 비밀번호로 확인` 입력 → 버튼 `탈퇴` → `page.goto("/archive/")`(`go_back` 금지) | URL `/accounts/delete/done/`에 링크 `다시 로그인`, 재방문 URL `/accounts/login/?next=/archive/`, DB `deletion_requested_at` not null | 다중 페이지 세션(2-b). 세션 차단은 `tests/auth/test_account_deletion.py:366`, 완료 페이지는 `test_account_deletion_done.py` 보호 [실측 grep] → 재확인. 신규 위험 = 실제 브라우저 쿠키 교체 | `web/views/account.py:201` `logout(request)` 제거 | `test_탈퇴를_요청하면_완료_페이지로_가고_세션이_끊긴다` | **Red-검증됨** [실측 2026-09-10] 지정 뮤테이션(`logout` 제거)은 POST가 400 Bad Request로 응답해 **1차 Then(완료 페이지 URL)에서** Red(1 failed/8.45초, 400 원인은 미조사) → 세션 게이트 단언의 민감도를 따로 실증하려고 **대체 뮤테이션 `logout(request)` → `request.session.cycle_key()`** 실행: 재방문 URL이 `/archive/`로 남아 마지막 단언에서 Red(1 failed/8.15초) → 복원 Green |

**첫 실행 발견 2건 [실측 2026-09-10 `uv run pytest -q -m e2e tests/e2e` 8 passed, 2 failed/21.34초]:** ① E7 — 일괄 비공개 POST가
403("세션이 만료되었거나 보안 토큰이 유효하지 않습니다"). 원인: Django는 `get_token()`이 불린 응답에만 `csrftoken` 쿠키를 심는데
(`django/middleware/csrf.py:472`), 일반 셸은 `_topbar.html:37` 로그아웃 폼의 `{% csrf_token %}`으로 매 페이지 쿠키를 얻지만 스태프
셸(`base_staff.html`)에는 `csrf_token` 0건 [실측 grep] → `login_as`로 바로 들어온 브라우저에 쿠키가 없다. 실제 사용자는 로그인 폼에서
쿠키를 받으므로 **픽스처가 실사용 상태를 덜 흉내 낸 것**이 1차 원인 → `login_as`가 `get_token(request)`로 CSRF 쿠키도 심도록 수정.
잔여 제품 위험(쿠키가 지워진 스태프가 스태프 셸에 바로 진입하면 모든 fetch 403)은 다른 종류의 작업이라 백로그(후보:
`ensure_csrf_cookie`). ② E4 — 위 행 정정. 두 발견 모두 편입 기준 2-a가 노린 "브라우저에서만 보이는 배선 결함"이며, 테스트
클라이언트 스위트(2541건)는 둘 다 통과시킨다.

Evidence 기록 위치: 각 행의 `상태 / Evidence` 칸에 `Green(초) → Red(뮤테이션, 실패 단언) → Green` 세 줄 요약을 구현 후 오케스트레이터가
Edit로 기입한다. 상태 값은 `Pending`·`Green`·`Red-검증됨`·`Deferred`.

Red 증거 절차(각 ID 공통): ① 테스트 작성 → 실행 Green(첫 실행, "기존 기능"이므로 정상) ② 지정 뮤테이션 적용 → 같은 테스트만
실행 → **실패 사유가 Then의 단언**인지 출력으로 확인 ③ `git checkout -- <파일>`로 복원 → 재실행 Green. 세 실행의 요약 줄을 Evidence에
기록. 뮤테이션은 절대 스테이징하지 않는다(`git status`로 확인 후 커밋).

## 구현 순서 (TDD 체크포인트)

1. 의존성·마커: `uv add --group dev pytest-playwright` → `uv run pytest -q`가 2541 passed(기준선 [실측])로 **무변화**인지, `uv run
   pytest -q -m e2e tests/e2e`가 "no tests ran"으로 끝나는지 확인. 커밋 `build(test): Add pytest-playwright and the e2e marker`.
2. conftest + E1(세션 흐름의 최소 여정) → Green/뮤테이션 Red/Green. 커밋 `test(e2e): Add the journey conftest and login journey`.
3. E2 → E3a·E3b·E3c → E4 → E5 → E6 → E7 → E8 각각 한 건씩 Green→Red→Green, 각 커밋 `test(e2e): Add the <여정> journey`.
   구현자는 BIR Must 7항(스코프·결합 텍스트·`exact=True`·`select_option(label=)`·모달 지연 질의·`page.goto` 재방문·`to_have_url`/
   `expect(locator)` 대기)을 브리프에서 그대로 받는다.
4. CI 잡. 커밋 `ci: Run the e2e journey suite in its own job`.
5. 정책 문서(AGENTS.md·CLAUDE.md·pytest.ini 주석·backlog). 커밋 `docs: Record the journey e2e policy`.
6. 종합 검증(아래) → PR `test/e2e-journeys` → 머지 승인 대기.

## 검증 명령과 기대 증거

**최종 실측 [실측 2026-09-10, 브랜치 `test/e2e-journeys` 792a06c, PR #354 오픈]:** `uv run pytest -q -m e2e tests/e2e` 10 passed/9.16초 ·
`uv run pytest -q` 2541 passed, 10 deselected/71.68초 · `tests/core/test_secret_literal_guard.py` 10 passed(E2E_PASSWORD 리터럴이 걸려
`valid_password` 픽스처로 교체한 뒤) · `manage.py check` 이상 없음 · `makemigrations --check` 변경 없음 · 운영 코드 diff 0파일 ·
커밋 12건(main 29c42ea 기준, `git log --oneline main..HEAD` [실측]). CI `e2e` 잡 결과는 PR 체크에서 확인(관측 모드).

- `uv run pytest -q` → 2541 passed [실측 기준선] 유지(e2e 자동 제외).
- `uv run pytest -q -m e2e tests/e2e` → 10 passed [계산 — E3 3건], 소요 초를 기록(테스트당 `transactional_db` TRUNCATE 비용 포함).
- 설치 직후 `uv run pytest -q -m e2e tests/e2e --fixtures | grep -A3 base_url` → tests/e2e/conftest.py 정의가 이기는지 [실측]으로 확정.
- `git status --short` → 1단계 커밋에 `pyproject.toml`·`uv.lock` 둘 다 포함(DOR ⑦).
- PR 오픈 후 GitHub Actions `e2e` 잡 실행 로그(`gh run view`)가 CI 완료 증거(QVL ⑤) — 로컬 통과만으로 CI 완료를 주장하지 않는다.
- `uv run pytest -q -m e2e tests/e2e --tracing retain-on-failure --output <scratch>` → 실패 0건이면 아티팩트 0개 [계산].
- `uv run python manage.py check`, `uv run python manage.py makemigrations --check --dry-run` → 변경 없음.
- `git diff --stat main` → 운영 코드(`templates/`·`static/`·`web/`·`archive/`·`events/`·`drafts/`·`staff/`·`accounts/`) 0파일.
- pytest 실행은 오케스트레이터 단독(메모리 `pytest-single-runner-delegation`: live_server·Postgres·Chromium 공유 시 동시 실행이
  허위 실패를 만든다). 서브에이전트는 편집만.

## Domain Boundary / Coupling / Pythonic

- 운영 코드 무변경. `tests/e2e/`는 `tests/` 안의 새 계층이며 ORM 접근은 fixture 시딩과 Then 단언에만 쓴다. 테스트 파일은 서비스·쿼리
  계층을 임포트하지 않는다(모델과 픽스처만).
- conftest는 팩토리 함수 반환 관례(루트 `tests/conftest.py`)를 따른다. 공용 픽스처가 중요한 전제(스태프 여부·비밀번호 유무)를 기본값에
  숨기지 않도록 키워드 전용 인자로 강제.
- 셀렉터 상수화 금지(DAMP): 각 테스트 본문에 라벨·버튼 텍스트를 그대로 쓴다.

## Deferred

- 재시도 플러그인(`pytest-rerunfailures`) — 플레이키 관측 시. xdist 병렬 — e2e 8건 [문서]의 소요가 문제될 때. 사진 업로드 여정,
  소셜 로그인, 비밀번호 재설정(메일 필요). 트랙 26(정렬·기간·카테고리 필터)은 별개.

## 문서 대상 / 인계 조건

- `AGENTS.md` 테스트 정책(정본), `pytest.ini` 주석, `CLAUDE.md` 스택 문단, `docs/backlog.md` 현재 상태 표. 인계 필수 사실: 편입 기준
  6항, `login_as` 쿠키 주입 이유(레이트리밋), 뮤테이션 Red 절차, 기본 실행에서 e2e가 빠진다는 점.

## 오케스트레이터 재확인 항목 (v2에서 해소)

- R1 해소: 경계 가드 매칭 규칙 직접 확인 [실측 sed `tests/core/test_architecture_boundaries.py:619-621,697-751`] — 글롭 3종 또는
  client 계열 인자 4종만 대상. e2e 파일은 대상 밖.
- R2 해소: pytest-django `live_server`는 staticfiles 설치 시 `StaticFilesHandler`(`serve(insecure=True)` → finders) [실측
  `live_server_helper.py:30-37`]. 단 `STORAGES["staticfiles"]`는 import 시 env `DEBUG`로 결정되므로 CI e2e 잡에 `DEBUG=false`를 넣지
  않는다. 테스트 실행 중 `settings.DEBUG`는 pytest-django가 False로 둔다 [코드 `pytest_django/plugin.py:143`] — APPEND_SLASH 301·
  404/500 템플릿이 운영과 같게 동작.
- 미해소(사용자 결정 필요, 착수 차단 아님): `e2e` 잡의 `continue-on-error` 해제 시점 — DOR 제안 "main 연속 10회 비결함 그린" [문서].
  backlog에 기록하고 사용자 판단을 기다린다.

---

