# takulife 백로그

기준일: 2026-08-25 · 기준 브랜치: `fix/media-overwrite-lowrisk-sweep`(main `e3d3448`에서 분기)

## 이 문서에 대하여

2026-07-30 전수 검수(11역할 중 7역할 활성) 결과를 근거로 백로그를 처음부터 다시
작성한 것이다. 이전 백로그는 전부 폐기됐다.

- **폐기**: 시안 기반 백로그 `B1~B29`, 이관 항목 `E1~E8`, 디자인 리뷰 큐
  (`.docs/design-review-queue.md`). 시안을 다시 만들기로 하면서 함께 폐기됐고
  (2026-07-29 사용자 결정), 큐 파일 자체도 존재하지 않는다. **복구하지 마라.**
- **배치**: 이 문서는 `docs/`에 있다. `.docs/`는 git-ignored라 소실된다 —
  디자인 리뷰 큐가 실제로 그렇게 사라졌다. 살아 있는 백로그는 여기 둔다.
- **표기**: `[실측]`은 오케스트레이터가 뮤테이션/프로브 왕복으로 직접 잰 항목,
  `[코드]`는 소스 읽기로만 확인한 항목이다. 확신은 증거가 아니므로 구분한다.
- **2026-08-24 재작성**: 전수 검토(2026-08-24) 및 후속 트랙 1~6 머지를 반영해
  해결 항목을 압축했다. 시간순 이력은 `docs/pr-log.md`, 교훈 정본은 메모리,
  가드레일 상세는 `docs/BE/`가 소유한다 — 이 문서는 현재 상태 인덱스로만 쓴다.

## 현재 상태 (신선 실행 기준)

| 항목 | 값 |
|---|---|
| 백엔드 회귀 | `[실측 2026-09-07]` `uv run pytest -q` → **2428 passed**(67.01초, PR #340 머지 후 main) |
| Django check | 0 issues |
| 마이그레이션 드리프트 | 없음 |
| 배포 차단 | **0건**(G1 해결 — 배포 시점 버킷 확인은 `docs/deploy-runbook.md` §3 체크리스트 ⑦-2로 이관) |
| 실행 순서 | 2·3·4단계 완료 / **5단계는 배포 이후로 연기**(C1, 실코호트 없음 — "미착수"가 아니라 사용자 결정이다) / 6단계 정상 미착수 / 1단계 인프라 대기 |
| 행사 카탈로그 | `[실측 2026-08-24]` 게시 169건 중 **146건 종료(86%)**, 진행·예정 23건, 검증 완료 0건 |
| OAuth 활성화 | **활성화 완료**(B2 코드 해소=트랙 11, GCP 클라이언트·env 설정 및 실 OAuth 왕복 검증=사용자, 2026-08-26) |

핵심 루프(발견 → 상태 → 방문 기록 → 굿즈 → 의도)는 URL·뷰·서비스 계층에서
끊긴 곳 없이 연결되어 있다. 교환(trade) 도메인은 존재하지 않으며, 이는 게이트
승인 전 착수 금지 원칙이 지켜지고 있다는 뜻이다.

---

## A. 안전망 복구

2026-07-30 전수 실측으로 확인한 거짓 초록 5건. 전부 해결됐다.

### A1 [실측] 도메인 경계 가드 — **해결됨(2026-07-31, 브랜치 `test/boundary-guard-glob`·`test/core-guard-glob`)**

손유지 파라미터 목록(사각지대 22건)을 파일시스템 유도 스캔으로 전환하고,
금지 앱 집합을 Django 앱 레지스트리 파생으로 바꿨다. `core` 가드는 기본 거부 +
허용 목록 2개로 사각지대 15개를 추가로 닫았다. 뮤테이션 26+10+4종 전부 Red.
검증: `uv run pytest -q` → 2024 passed. 정본: `docs/BE/contract-guards.md`.

### A2 [실측] 서명 규약 가드가 `core.analytics`를 보지 않는다 — **해결됨(2026-08-01)**

`SERVICE_MODULES`에 편입, 공개 함수 4개를 예외 없이 키워드 전용으로 변경.
검증: `uv run pytest -q` → 2145 passed, 뮤테이션 4종 전부 Red.

### A3 [실측] 보유/구함/교환 3축 술어 중복 — **해결됨(2026-08-01, PR #277)**

`archive/querysets.py`의 `CollectionItemQuerySet`(owned/not_owned/tradeable/
not_tradeable) + 모델 프로퍼티로 호출처 11곳 통합, 긍정·부정형 일치 가드 신설.
검증: `uv run pytest -q` → 2146 passed, 마이그레이션 드리프트 없음, 뮤테이션
7종 전부 Red.

### A4 [실측] 마크업 리터럴 단언 — **해결됨(2026-07-30)**

전수 실측 결과 실제 회귀 위험은 서술한 41곳이 아니라 컬렉션 빈 상태 1곳뿐이었다
(`aria-label` 앵커로 보강). 공허 단언 2건 삭제.

### A5 [실측] 500 페이지 테스트 무하중 — **해결됨(커밋 `2db756e` 2026-07-30, 잔여 위험 PR #278)**

몽키패치 대상을 실행 경로가 닿는 지점으로 정정하고, `_boom` 실제 호출 여부를
단언해 "패치가 실행 경로를 벗어나도 조용히 통과"하는 경로를 차단했다.

---

## B. 사용자 데이터 안전

### B1 [코드] 직접 등록 수정 기능 부재 — **해결됨(2026-07-30, 브랜치 `feat/personal-place-detail-edit`)**

`PersonalEntryDetailView`에 PATCH 추가(PUT은 부분 필드 비움 위험으로 제외) +
`client_token` 구조적 배제, 상세·수정 라우트 신설. 검증: `uv run pytest -q` →
2045 passed. 정본: `docs/FE/personal-place-detail-edit.md`.

### B2 [실측] 소셜 가입 경로에는 약관 동의 필드가 아예 없다 — **해결됨(트랙 11)**

- 해소: `accounts/forms.py`에 `TermsAgreementFormMixin`(필드·오류 메시지·
  `custom_signup`의 `terms_agreed_at` 기록 공용화)을 신설하고 `SignupForm`·
  `SocialSignupForm` 둘 다 이를 물려받는다. `config/settings.py`에
  `SOCIALACCOUNT_FORMS = {"signup": "accounts.forms.SocialSignupForm"}` +
  `SOCIALACCOUNT_AUTO_SIGNUP = False`를 등록해 신규 소셜 유저가 동의 폼을
  건너뛰지 못하게 막았다. `templates/socialaccount/signup.html`에 일반
  가입과 동일한 동의 체크박스 블록을 추가했다(더는 `{{ form.as_p }}` 단독
  렌더가 아니다). 계약·도메인 테스트 4개(`tests/auth/
  test_social_signup_terms_agreement.py` 2개, `tests/auth/
  test_social_login.py`의 `SOCIALACCOUNT_FORMS`/`AUTO_SIGNUP` 가드,
  `tests/auth/test_auth_rate_limit.py`의 소셜 가입 429 가드)가 회귀를 지킨다.
  검증: `[실측]` `uv run pytest -q` → **2308 passed**.
- 트랙 중 발견·즉시 수정: 소셜 가입 엔드포인트(`/accounts/3rdparty/signup/`)에
  allauth 기본 레이트리밋이 없었다(로컬 가입 뷰와 달리 `rate_limit`
  데코레이터 미적용). `accounts/views.py`에 `SocialSignupView`(같은 `signup`
  한도를 거는 서브클래스)를 신설하고 `config/urls.py`에서 allauth include
  이전에 선등록(`url name`은 `socialaccount_signup` 유지)했다. Red(302)→
  Green(429) 왕복으로 검증.
- 활성화 완료(2026-08-26): 사용자가 Google Cloud Console OAuth 클라이언트
  생성 + Render 환경변수(`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`) 설정을
  마쳤고, 실 OAuth 왕복 수동 검증도 정상 동작을 확인했다(사용자 보고).
  B2는 코드·운영 모두 종결.
- 발견 경위: 인증 화면 리스킨(PR #266) 보안 검토 중. 리스킨이 만든 것이
  아니라 선재 갭이었다.

---

## C. 제품 다음 단계

### C1 북극성 지표 — **배포 이후로 연기 (2026-07-31 사용자 결정). 설계 결정은 확정됨**

**연기 사유**: 실행 순서 5단계는 *"with **real cohorts**"*를 요구하는데 서비스가
아직 배포되지 않았고(1단계 인프라 대기), SMTP 미설정이라 **신규 가입 자체가
동작하지 않는다.** 실사용자 0명이고 만들 수단도 지금은 없다. 로컬 DB의
**56행 / 고유 user_key 10개**는 목데이터다.

착수 재개 트리거: **배포 완료 + 실사용자 가입 가능**.

⚠️ 이 항목이 끝나도 실코호트가 생기기 전까지 **"5단계 완료"라고 쓰지 마라.**

#### 확정된 설계 결정 (재논의 불필요)

| # | 결정 | 근거 |
|---|---|---|
| 1 | **"의미 있는 수정" = 실제 값 변경만** | 기존 `ActivityLogEntry.Kind.COLLECTION_ITEM_ORGANIZED`를 쓴다 — `quantity`·`is_wanted`·`tradeable_quantity`·`acquired_on` 중 **값이 실제로 바뀔 때만** 기록된다(`archive/services.py:528-541`). ⚠️ 이건 이벤트가 아니라 **도메인 테이블**이라 `core/analytics.py`가 아니라 `archive` 쪽에서 읽어야 한다 |
| 2 | **구함·교환은 보조 축으로 분리** | 북극성 헤드카운트에 넣지 않는다. 교환 게이트 승인 전이라 핵심 지표를 교환 쪽으로 기울이지 않는다 |
| 3 | **노출은 스태프 대시보드 기존 행 교체** | `staff/views/__init__.py:247`의 `weekly_active_user_count`(13종 이벤트를 전부 합친 값)를 컬렉션 기여 기준으로 바꾼다. 새 대시보드 섹션은 만들지 않는다 |
| 4 | **월 = KST 달력월** | `AGENTS.md`가 "monthly"와 "four-week"를 별개 지표로 나열한다 — 후자가 롤링이므로 전자는 달력월로 읽는 것이 문서 내적으로 일관된다. ⚠️ `created_at`은 UTC aware로 저장되므로 경계 계산은 KST 기준이어야 한다. 이 저장소는 이미 타임존 오표시 결함을 겪었다(PR #255) |

#### 미해결 결정 (착수 시 사용자에게 물어라)

- `collection_item_linked_to_visit` — 생성 시점 링크와 사후 재링크를 구분해 셀지.
  같은 이벤트명을 공유한다(`archive/services.py:406-412`, `:553-559`)
- `visit_photo_added` — 같은 달 `visit_record_created`와 별개 기여로 셀지,
  완성도 축에만 반영할지

#### 실측한 사실 (착수 전 재확인은 여전히 필요)

- `core/analytics.py` 공개 함수는 **4개뿐**이고 전부 슬라이딩 윈도우다. 월간
  코호트 개념 없음
- `AnalyticsEvent.EventName`은 **13종 선언**돼 있다. 착수 전 서술의 "8종"은
  선언 수가 아니라 **로컬 개발 DB에 나타난 종류 수**였다
- `pseudonymous_user_key`는 `HMAC(SECRET_KEY, user.pk)`로 **시간에 대해 안정적** —
  월간 코호트·4주 재방문 계산 가능. 단 `SECRET_KEY` 교체 시 연속성 단절
- 프로덕션 `record_event` 호출처 **15곳**(`archive/services.py` 13, `events/views.py` 2)
- `AnalyticsEvent` 퍼지·보존 커맨드 **0건**

#### 소유 위치 (도메인 경계 검토자 판정)

- 이벤트만으로 계산되는 지표(월간 기여·활성화·재등록·4주 재방문) → `core/analytics.py`
- **완성도** → `archive/queries.py`. `AnalyticsEvent.context`가 `name`·`memo`를
  하드 거부해(`core/analytics.py:35-37`) 필드 채움 여부는 이벤트에 애초에 실리지 않는다
- 조합 → `staff/queries.py`
- ⚠️ **`core/analytics.py`는 도메인 앱을 임포트하면 즉시 Red다**(A1 후속 core 가드).
  도메인 행을 읽어야 하는 지표를 그 파일에 두려는 시도는 구조적으로 막힌다

#### 영구히 계산 불가능한 것

`AnalyticsEvent`에 user FK가 없어(*"intentionally cannot be joined back to
accounts.User"*) `accounts.User` 속성과의 조인이 불가능하다 — **가입월 코호트별
리텐션** 같은 전통적 코호트 표는 설계상 만들 수 없다. 또 탈퇴로 계정이 삭제돼도
이벤트 행은 남아 과거 행동이 계속 집계된다. 둘 다 의도된 트레이드오프다.

---

## D. 사용자 흐름

### D1 — **완료**

형제 파셜(`_archive_results_record.html`)이 이미 갖고 있던 CTA 3분기를 그대로
이식(백엔드 변경 0줄). 브라우저 실측: `?subject=event:90`·`?subject=personal:187`
둘 다 HTTP 200.

### D2 — **완료(2026-08-01, 스태프 2개는 PR #275)**

필터 칩 8곳 전부 `aria-current="true"` + 가시 텍스트를 포함한 `aria-label`
(+"적용됨")을 갖는다. Chromium이 `aria-current` 자체는 접근성 트리에 노출하지
않는 것을 재확인해 `aria-label` 병행이 필수임을 확정했다.

### D3 — **완료**

스태프 콘솔 POST 폼 중 위험도 높은 6개(생성/토글/삭제확정)에 opt-in
`data-submit-guard` 신설. Slow 3G 900ms 연속 클릭 실측으로 판별력 확보(가드
있음 1건 vs 없음 3건). 리디자인(PR #275) 통과 후 회귀 가드로 보호됨.

### D4 [실측] 서비스 전체 공식 포스터 제거와 행사 에디토리얼 전환 — **해결됨(2026-08-15, PR #282)**

공식 포스터 운영 전면 종료: `Event.poster_image`·업로드 API·포스터 품질 경고
제거, 목이미지 2,869개(14M) `[실측]` 영구 삭제(사용자 사진은 무손상). 행사
탐색을 작품명·행사명 중심 에디토리얼 인덱스로 전환. 검증: 2144 passed, FE
이중 게이트(WED·BIR) `Conforms`. 정본: `docs/FE/event-typography-editorial.md`.

---

## E. 구조

### E1 [코드] `core/views.py` 분할 — **해결됨(PR #251)**

`core/views/` 패키지(7모듈: `_helpers`·`events`·`archive`·`activity`·
`collection`·`account`·`system`)로 전환. 169라우트 완전 일치 + 옮긴 함수 50개
AST 문자 단위 대조 + 매 단계 2026 passed 3중 증명. `config/urls.py` 무변경.

### E2 [실측] `archive/queries.py` 분할 — **해결됨(2026-07-31, PR #274)**

1012 → 653줄. 활동 달력 읽기 모델(366줄)을 `archive/activity_calendar_queries.py`로
분리(재수출 없음), 소비자 3곳 임포트 경로 갱신.

### E3 [코드] 아카이브 쿼리 테스트 분할 — **해결됨(2026-07-31, PR #274)**

1566줄 79개 테스트를 검증 대상 프로덕션 함수 기준 7개 파일로 재편. AST 대조
79 → 79, 본문 바이트 단위 동일.

### E4 [실측] 주석 언어·길이 규칙 — **해결됨(2026-07-31, PR #269~#271)**

314파일 전면 한국어화(주석 순 −3,757줄, 영어 산문 0). 재발 방지 가드
`tests/core/test_comment_language_guard.py` 신설(프로덕션 위반 우선 보고).

### E5 [실측] 조건을 대신 설명하는 주석 6곳 — **해결됨(2026-07-31, PR #272)**

6곳 전부 술어에 이름 부여(중복 pk 검사는 `core/query_params.py`의
`is_safe_pk_string`으로 통합), "왜 이 검사가 있는가" 근거성 주석은 유지.
뮤테이션 6종 전부 하중 확인.

### E6 [실측] `core/views/` → `web/views/` 프레젠테이션 계층 분리 — **해결됨(2026-08-06, PR #281)**

새 앱 `web` 신설, `core` 팬아웃 21→0·앱 간 순환 임포트 3쌍→0(완전 DAG). 검증:
2158 passed, 뷰 7파일 R100 바이트 동일, 라우트 175건 순회 순서 무변경, 뮤테이션
M1~M11 전부 Red. 이관 중 발견한 이연 항목 4건(템플릿 `core→web` 리네임,
`web/views/` 내부 방향 가드 부재 등)은 착수하지 않았고 정본에 등재돼 있다.
정본: `docs/BE/web-views-package.md`, `docs/BE/contract-guards.md`.

---

## F. 운영·위생

| # | 항목 | 근거 | 비고 |
|---|---|---|---|
| F1 | ~~worktree 2개 삭제~~ (해소됨) | `[실측 2026-08-01]` `git worktree list` → 작업 트리 1개뿐. 언젠가 정리됐다 | 해소 |
| F2 | ~~런북 줄번호 드리프트~~ (해소됨) | 참조를 `core/urls.py`, `core/views/system.py`의 `health()`로 줄번호 없이 재작성 | 해소 |
| F3 | ~~CI 컨테이너 기동 스모크 부재~~ (**해결됨 2026-08-01**) | `docker` 잡이 postgres 서비스를 붙이고 이미지를 실제로 띄워 `/health/` 200 폴링, `migrate` 미스킵 | 실검증은 CI 전용(로컬 Docker 없음) |
| F4 | ~~`project-status.md` 2334줄 / 사실과 다른 7곳~~ (**해결됨 2026-08-01**) | `docs/pr-log.md`(추적됨)로 이관, `.docs/project-status.md` 삭제, `AGENTS.md`·`CLAUDE.md`에 갱신 의무 명문화 | 해결 |
| F5 | ~~스로틀 미적용 엔드포인트 4개~~ (**해결됨 2026-08-01**) | 생성 엔드포인트 4개 `ScopedRateThrottle`(목록형 60/min, 폼형 30/min), GET은 무제한 | 해결 |
| F6 | ~~SSRF DNS 리바인딩 TOCTOU~~ (**해결됨 2026-08-20**) | `validate_fetch_url`이 검증 IP를 반환하고 `fetch_html`이 그 IP로 직접 연결(IP 핀닝). 실수집 TLS 200 실측 | 해결 |
| F7 | 실사용 데이터 이후 스키마 변경 가이드 부재 | `archive/migrations/0011~0013,0019` 비-concurrent | 두 번째 배포부터 유효 |
| F8 | ~~드래프트 상태 라벨 하드코딩~~ (**해결됨 2026-08-01, PR #278**) | 정본 `drafts/labels.py`의 `REVIEW_STATUS_LABELS`, 템플릿/JS 모두 서버값 참조(표시 6곳) | 해결 |
| F9 | ~~`staff_event_toggle_publish`에 `select_for_update` 없음~~ (**해결됨 2026-08-01**) | `atomic()` 안에서 잠그고 재조회, `CaptureQueriesContext`로 `FOR UPDATE` 단언 | 해결 |
| F10 | ~~`staff_event_edit`의 lost-update 여지~~ (**해결됨 2026-08-25, 브랜치 `fix/media-overwrite-lowrisk-sweep`**) | POST 저장 경로가 `atomic()` 안에서 `get_object_or_404(Event.objects.select_for_update(), pk=pk)`로 재조회(F9와 동일 패턴), `CaptureQueriesContext`로 `FOR UPDATE` 계약 테스트 + `select_for_update` 제거 뮤테이션 Red 확인 | 해결. lost-update 완전 해법(폼 버전 스탬프)은 이연 — 트리거: 스태프 동시 편집 실관측 |
| F11 | ~~OpenAPI 스키마·문서 엔드포인트 부재~~ (**해결됨 2026-08-16**) | `/api/schema/`·`/api/docs/`(drf-spectacular + Swagger UI sidecar), 계약 테스트 6건. `extend_schema_view` 키 오기입 28곳 회귀 가드 포함 | 정본 `docs/BE/openapi-schema.md` |
| F12 | `/api/schema/` 스로틀·캐시 없음 + CI 스모크가 `/api/docs/`를 안 본다 | `docs/BE/openapi-schema.md` "미적용(의도)" | 실트래픽 개시 전 유보. 트리거 시 ①캐시/스로틀 적용 ②CI 도커 스모크(F3)에 `/api/docs/` curl 200 추가 |
| F13 | ~~대시보드 표 저강조 색 위계 미실현~~ (**해결됨 2026-08-25, 브랜치 `fix/media-overwrite-lowrisk-sweep`**) | `.dash-table`로 색 상속 전환(`static/css/staff/pages/dashboard.css`), 라이트·다크 모두 computed 실측으로 `.dash-cell-dim`·`-faint`·`-wrap` 전부 토큰 일치 확인, WED·BIR `Conforms`×2. BIR 전수 확인이 찾은 동일 패턴 2건(`sources.css` `.src-cell-error` 위험색 소실 포함, `audit_log.css` dim/faint)도 같은 트랙에서 같은 방식으로 즉시 해소 — 라이트·다크 computed 실측 일치. `static/css/staff/` 내 이 패턴은 전수 재확인 결과 소멸(무해 판정: drafts·events·home_categories는 td color 미지정) | 해결 |
| F14 | 폰트 폴백 메트릭 튜닝(size-adjust 계열) | 트랙 13에서 데스크탑 콜드 CLS 0.02(Good) 수용, 0.01 이하로 낮추려면 폴백 서체 메트릭 오버라이드+시각 회귀 필요(2026-08-29) | 이연 |
| F15 | og:image 브랜드 카드(1200×630 PNG) 제작·발행 | 트랙 16(2026-08-30)이 og:image를 의도적으로 미발행(래스터 자산 부재, favicon.svg 유용 금지, `test_페이지_응답은_og_image_태그를_포함하지_않는다` 핀) | 이연. 자산 제작 시 M4 핀 교체와 함께 발행 |
| F16 | `.dockerignore`가 `.claude/`를 제외하지 않아 런타임 이미지에 하네스 파일(훅·에이전트 정의·settings)이 들어간다 | `[코드]` `Dockerfile:22` `COPY . .`, `.dockerignore` 제외 목록에 `.claude` 0건(트랙 18 DOR 발견, 2026-09-03) | 무해(실행 경로 없음)하나 위생 항목. 다음 배포 트랙에서 `.claude/` 1줄 추가 |

**로컬 에이전트 수집처 탐색 — 구현됨(2026-08-20~24, PR #299·#301).** 서버
경계(모델 3종·러너 API·8단계 결정론 검증·승격) + `local_runner/` 어댑터 완비.
정본: `docs/BE/draft-source-agent-discovery.md`. 잔여 관측성·하드닝 항목은
아래 G절.

---

## G. 전수 검토 잔여 (2026-08-24)

### G1 [코드] 미디어 스토리지 저장소 계층 프라이버시 미보증 — **해결됨(2026-08-25, 브랜치 `fix/media-overwrite-lowrisk-sweep`)**

외부 발견 재검증으로 **덮어쓰기 축이 본선이었음을 정정**한다: `file_overwrite`
기본값 `True` + `upload_to`가 원본 파일명을 보존 = 사용자 간 사진 무단 대체
`[실측: S3Storage 인스턴스화]`. 조치: `archive/models.py`의 `upload_to`를
UUID 콜러블 3필드(`personal_entry_image_upload_to`·
`visit_record_photo_image_upload_to`·`collection_item_image_upload_to`)로
교체(+ 마이그레이션 0025, DB no-op) + `load_media_storage_config`의
`OPTIONS`에 `file_overwrite: False`·`default_acl: None`(R2 ACL 미지원 —
`None`=헤더 미전송)·`querystring_auth: True`를 명시 + 런북 버킷 확인 절차
추가(`docs/deploy-runbook.md` §3 체크리스트 ⑦-2). 함께 발견된 **캐시 컬링
결함**(`DatabaseCache` 기본 `MAX_ENTRIES=300`에 allauth 레이트리밋 4종 + DRF
스로틀 8스코프 + 계정 삭제 잠금 카운터가 공유 `[실측]`)은 `MAX_ENTRIES=10000`
명시로 해소(`config/settings.py` `CACHES`). 검증: `uv run pytest -q` →
2294 passed, 뮤테이션 4종(`file_overwrite`·`MAX_ENTRIES`·`select_for_update`·
스로틀 가드 제거) 전부 표적 Red. 배포 시점 버킷 퍼블릭 액세스 확인은
`docs/deploy-runbook.md` §3 체크리스트 ⑦-2로 이관됐다.

### G2 [코드] gunicorn 워커 타임아웃 미설정

`docker/entrypoint.sh`에 `--timeout`이 없다. 러너 후보 제출이 요청 안에서
동기 네트워크 최대 6회(각 5초) → 최악 ~30초로 기본 타임아웃과 충돌 가능.
**트리거: 서버에서 `DRAFT_DISCOVERY_ENABLED=true` 전환 전.**

동일 근본 원인 `[계산 2026-09-05]`: 대시보드 「지금 수집」도 동기 실행(`staff/views/__init__.py:200-245`)이라 활성 소스 3개가 모두 느린 최악 시 `3×(5+5)+2×1 = 32초`(요청 타임아웃 5초 `drafts/fetching.py:10`, 소스 간 대기 1초 `drafts/management/commands/discover_drafts.py:59`)로 기본 30초를 넘길 수 있고, 워커 SIGKILL 시 `finally`의 감사 로그(`staff/views/__init__.py:242-245`)가 남지 않는다. `docker/entrypoint.sh`에 `--timeout` 0건 `[실측 2026-09-05]`. 프로덕션 활성 소스 수는 미실측. 사용자 보류·트리거는 그대로다.

### G3 [코드] LLM 아웃바운드 네트워크 수준 계약 테스트 부재

현재 보증은 코드 경로 부재 + 단위 모킹 2겹뿐. `pytest-socket` 등 신규 dev
패키지가 필요해 **uv 정책상 사용자 명시 승인 대기.**

### G4 [코드] 스태프 탐색 요청 뷰 스로틀 부재 — **해결됨(2026-08-25, 브랜치 `fix/media-overwrite-lowrisk-sweep`)**

`staff/views/discovery.py`에 사용자당 60초 고정 창 10회 캐시 스로틀을
추가했다(`_discovery_request_throttled`). `cache.incr()`는 쓰지 않는다 —
`DatabaseCache`가 `incr()`를 오버라이드하지 않아 창이 계속 연장되는 결함을
피하려 `accounts/services.py`의 마감 시각-in-레코드 패턴을 그대로 따랐다.
검증: web 테스트(`test_사용자당_분당_10회를_초과한_탐색_요청은_거부되고_새_실행이_생성되지_않는다`)
+ 스로틀 가드 제거 뮤테이션 Red 확인.

### G5 [실측 2026-08-24] `templates/core/archive/visit_edit.html` 필수 범례 누락 — **해결됨(2026-08-25, 브랜치 `fix/media-overwrite-lowrisk-sweep`)**

`visit_create` 패턴을 그대로 미러링한 범례를 추가했다. 320px·1120px 실측으로
겹침 없음을 확인했고, WED·BIR 모두 `Conforms`.

---

## H. 스태프 백오피스 현업 적합성 검토 (2026-09-05)

검토 경로: 코드·문서 판독 뒤 PSO·WED·SRR·DOR 4역할 병렬 검토, 인용된 file:line은
오케스트레이터가 전부 재확인. 현재 있는 것 `[코드]`: `staff/urls.py` 라우트 19개,
대시보드 지표 카드 5장, 드래프트 큐(상태 탭·검색·인스펙터·일괄 승인/반려 상한
20건 `MAX_BULK_APPROVE_DRAFT_IDS`), 이벤트 목록·생성·수정·게시 토글·검증·삭제,
수집 소스 읽기 전용 표, 홈 카테고리, 감사 로그(행동 11종). 스태프 테스트 함수
295개 `[실측 2026-09-05]` `rg -c 'def test_' tests/staff/*.py` 합계.

P0는 "shell 없이는 운영자가 일을 못 하는 것"으로 한정했다(PSO). PSO(P0=H1)와
WED(P0=H2)의 우선순위 충돌은 AGENTS.md 배타 책임에 따라 PSO 판정으로 조정했다.
H6도 같은 규칙으로 PSO P2를 따른다(2026-09-06 정정). 2026-09-06 외부 검토를
반영했고 정정 위치는 각 행에 날짜로 표기했다.

| # | 우선순위 | 항목 | 근거 | 분류·판정 |
|---|---|---|---|---|
| H1 | **P0** | 계정 운영 화면(`is_staff` 부여/해제·`is_active` 전환·탈퇴 유예 확인). H14(계정 정지)를 흡수 | `[실측 2026-09-05]` `accounts.User` admin 미등록(`admin.site._registry` 11종, `accounts/admin.py` 없음), `staff/` 내 User 참조 0건(rg). 유일 경로 `manage.py shell`. 런북 §5 정정 완료 | 결함. 권고 = 두 플래그만 다루는 좁은 화면 + 감사 기록. **착수 전 계약 3건 확정 필요(2026-09-06 외부 검토 반영)**: ① 조작 주체 — `staff_console_required`는 `is_staff`만 검사(`staff/permissions.py:21`)라 그대로 재사용하면 검수 권한 스태프도 타 계정의 권한을 바꾸고 정지시킬 수 있다(`templates/staff/_console_shell.html:67`의 "전체 권한/검수 권한"은 표시일 뿐). superuser 한정 또는 별도 관문, 자기 계정·마지막 관리자 보호를 정한다. ② 감사 대상 — `StaffActionLog`는 `target_draft`·`target_event`만 가진다(`staff/models.py:32-41`). 액션 이름만 추가하면 변경된 계정을 추적 못 하므로 계정 대상 필드와 변경·기록의 원자성이 필요. ③ 이 화면으로 첫 비-superuser 스태프가 생기면 RBAC 보류(아래)의 재검토 트리거가 켜진다. User 전체 admin 등록은 계속 기각하되 근거 정정: `[실측 2026-09-06]` allauth 65.18.0 admin은 이미 `EmailAddress`(user·email·verified·primary)·`SocialAccount`(user·provider·uid·extra_data)를 편집 노출하므로 "피해 반경 1개→전체 확대"는 성립하지 않는다. 근거 = 업무에 불필요한 계정 편집 기능의 추가 노출 최소화. 인접: prompt_plan.md 트랙 12(비밀번호 set 경로, 계획 승인·미착수). **구현 완료(2026-09-07, 트랙 19, PR #340 머지)** — superuser 전용 `/staff/accounts/`. 정본 `docs/BE/staff-account-operations.md`. 사용자 결정(2026-09-07): ★3 액션 빈도 제한·step-up은 미구현 유지 수용(이연). ★2 확정(2026-09-07): superuser는 shell로만 생성·변경, 콘솔 제외 유지 |
| H2 | P1 | 이벤트 일괄 선택·일괄 게시 내리기, 목록 인라인 토글/검증, 정렬·기간·카테고리 필터 | 만료 1건 내리기 = 목록→수정→토글 3화면 `[코드]` `staff/views/events.py:404-443`·`templates/staff/events/edit.html:137-144`; 목록 checkbox 0건 `[실측 rg templates/staff/events/list.html]`; 운영 기준 주 1회 정리 `docs/event-operations-criteria.md:50-51`; 선례 `templates/core/drafts/list.html:50-60` bulkbar | 제품 권고. 계약(2026-09-06 반영): 일괄 내리기는 "비공개로 설정"이지 토글이 아니다 — 현재 토글은 읽은 상태를 반전하므로(`staff/views/events.py:413-418`) 내리기 성공 뒤 응답만 유실되면 재시도가 다시 게시한다. 부분 실패·재시도 대상·선택 범위(페이지네이션 `templates/staff/events/list.html:77-78`, 필터 `staff/views/events.py:110` 변경 시 선택 유지 여부)를 설계에서 명시. 종료 게시 건수는 착수 전 재측정(위 현재 상태 표 146/169건은 2026-08-24 값) |
| H3 | P1 | 사용자 제보 드래프트 구분 표시 + 제보 폼 인라인 고지 | `web/promotion.py:74-82` `source_name` 미전달, `EventDraft`에 origin 필드 없음(`drafts/models.py`). 제보 폼 `templates/core/archive/personal_detail.html:115`에 메모 공개 전환 안내 없음 | 제품 권고. 구분 표시에 `source_name`을 쓰지 않는다(2026-09-06 반영): 승인 시 이벤트로 복사되고(`drafts/services.py:273`) 소비자 상세에 "N 제공"으로 노출된다(`templates/core/events/detail.html:33-34`). 스태프 수집분은 `DraftSource.name`이 들어가고(`drafts/candidate_intake.py:62`) 제보분은 빈 값이라, 운영용 유입 경로 필드를 따로 둔다. 고지 문안은 메모가 `summary`로 매핑돼(`web/promotion.py:81`) 검수 후 공개 요약에 쓰인다는 내용. 고지 자체는 개인정보처리방침 §3(`templates/core/legal/privacy.html:53-56`)·약관(`templates/core/legal/terms.html:76`)에 있어 SRR Medium을 Low(문구 권고)로 정정 |
| H4 | P1 | 검수 SLA 지표(최장 대기·평균 처리·반려율·사유 분포) | 대시보드는 pending 건수만 `staff/views/__init__.py:152-186` | 제품 권고 |
| H5 | P1 | 반려 드래프트 재오픈 | 승인·반려 모두 pending 전용 `drafts/services.py:198-207`, `source_url` unique `drafts/models.py:15` → 반려는 영구 폐기, 복구는 shell | 결함(빈도 낮음) |
| H6 | P2 | 수집 소스 생성·수정·활성 토글 콘솔 편입 | admin 이탈 안내 `staff/views/__init__.py:237`(트랙 19 import 추가로 225→237, 2026-09-07 재확인), `drafts/admin.py` 빈 ModelAdmin | 제품 권고. PSO P2(admin으로 가능) / WED P1(콘솔 밖 3번째 화면 강제). 2026-09-06 정정: 이전 표기 P1은 WED 의견으로 상향한 것이라 "우선순위는 PSO 판정" 규칙과 충돌해 PSO P2로 되돌림. WED 이견은 기록만, 사용자가 P1을 원하면 조정 |
| H7 | P1 | 감사 범위 확대(드래프트 생성·필드 수정) | `/api/event-drafts/` `drafts/views.py:147-161`은 `StaffActionLog` 밖. v1 의도된 경계 | **결정 필요**: SRR Medium(승인 직전 필드 조작 추적 불가) / PSO 이연 |
| H8 | P1 | 알림(대기 누적·소스 전부 오류·러너 오프라인) | `send_mail`·`EmailMessage`·`mail_admins` 0건 `[실측 rg staff/ drafts/]` | 이연. DOR: 비용 정책 안 대안 없음(무료 웹훅은 외부 계정 액션 = 인프라 최후순위) |
| H9 | P2 | 소스별 수집 이력·실패율, 실패 후보 재시도/무시 액션 | `DraftSource` 상태 필드 2개뿐 `drafts/models.py:67-68`(정정 전 표기 56-66은 필드 줄을 빗나감, 2026-09-06 재측정) | 제품 권고 |
| H10 | P2 | 중복 경고(같은 행사 다른 URL), 반려 사유 큐 노출·템플릿 | 중복 판정은 URL 완전일치만 | 제품 권고 |
| H11 | P2 | 이벤트 검색에 공식 URL·ID, 변경 이력, 수정 화면 소비자 링크·반응 지표, 검증 만료 예고 | 검색 3열 `events/queries.py:213-217`, `Event.updated_at` 0건 `[실측 rg events/models.py]` | 제품 권고 |
| H12 | P2 | 수집 진행 표시, 감사 로그 보존 정책 | `staff/management/` 없음 `[실측 ls]`. 진행 표시는 현재도 제출 가드가 버튼 비활성+`.is-loading`을 적용(`templates/staff/dashboard.html:95` `data-submit-guard`, `static/js/shared/staff_submit_guard.js:29-30`) | 권고. 2026-09-06 분리: (a) 진행 표시 — 요구가 대기 문구인지 실제 실행 상태 조회인지 설계 시 확정. G2 타임아웃 조정은 원인을 공유할 뿐 진행 표시를 해결하지 않는다. (b) 감사 보존 정책 — 독립 과제. 운영 설정 보류(G2)는 유지 |
| H13 | P2 | 대시보드 소스 패널 「전체 보기」 링크, 이벤트 읽기 전용 미리보기 | `templates/staff/dashboard.html:91-103`(감사 패널은 251행에 링크 있음) | 제품 권고 |
| H14 | — | 계정 정지 UI → **H1에 흡수**(2026-09-06, `is_active` 전환과 같은 범위) | 승격 스로틀 `20/day` `config/settings.py:579`는 분산 계정 남용은 못 막는다 | H1 설계에서 다룬다. 별도 항목 아님. H1과 함께 완료 |

**보류·이연(기록된 사용자 결정, 재제안 아님)**: RBAC(2026-07-03 보류, 트리거는
첫 비-superuser 스태프), 취소·연기 상태(prompt_plan.md Deferred), 일괄
가져오기·내보내기(아래 「착수하지 않는 것」), 북극성·이벤트별 분해(C1), 신고·차단·
중재(교환 게이트), 모바일 차단(D10), 정기 수집 스케줄러(인프라 최후순위),
대시보드 증감 미표시 2장(M5).

**기각(과설계)**: 담당자 배정·검수 락(`select_for_update`로 이미 안전), 전역
검색(검색 화면 3개), User 전체 admin 등록(SRR).

**미실측(착수 전 재측정)**: 프로덕션 활성 소스 수, `StaffActionLog` 행 수, 종료
게시 이벤트 수.

**설계 시 확정(2026-09-06 외부 검토 반영)**: H4·H5 — 재오픈 후 대기 시간의 기산점과
반려율 계산 기준. H10 — 반려 사유 입력 경로는 단건 반려의 textarea뿐
(`templates/core/drafts/detail.html:150-151`), 일괄 반려는 사유 없이 id만 보낸다
(`static/js/staff/draft_bulk.js:7`). H13 — 비공개·미저장 이벤트 미리보기 범위.

**프론트 필요 기능(2026-09-06, WED·BIR 사전 검토 통합 — 인용 file:line은
오케스트레이터가 전수 재확인)**: 전제 = 스태프 콘솔은 소비자 CSS·JS를 로드하지
않는 독립 셸(`docs/FE/staff-console-redesign.md` S6)이고 1024px 미만은 데스크톱
게이트(S7)라 항목별 추가 반응형 요구는 없다. 프론트 작업 없음: H7·H12(b)는
백엔드, H8 이연, H14는 H1, H4는 `templates/staff/dashboard.html:29-36`
dash-metric 카드 재사용(집계만 백엔드). 두 역할 원문과 검증 기록은
`.docs/FE/2026-09-06-staff-backoffice-frontend-review.md`(git-ignored).

- H1 — 사이드바 "계정" 그룹을 기록 그룹 뒤(`templates/staff/_console_shell.html:50-59`)에
  superuser에게만 렌더(링크 숨김은 UX일 뿐 경계가 아님, 계약①). 목록 = 검색
  (`staff/search.py:15` `SEARCHABLE_URL_NAMES` 추가)·표(`templates/staff/events/list.html:32-73`)·
  페이저(`templates/core/partials/_pager.html`)·빈 상태 2분기(`templates/staff/audit_log/list.html:60-64`).
  상세 = rail-card 토글 폼 2개(`templates/staff/events/edit.html:125-146`); 자기 계정·
  마지막 관리자는 버튼 disabled + 사유 문단(`edit.html:172-175` 패턴), 판정 불리언은
  뷰가 계산. 탈퇴 유예 배지는 읽기 전용 — 재로그인만 취소(`accounts/models.py:15-18`),
  유예 10일(`accounts/services.py:22`), 종료 시각은 뷰가 계산. 확인 단계는 삭제와
  같은 서버 렌더 2단계(`confirmed=yes`, `staff/views/events.py:480-483`·`501-510`,
  `templates/staff/events/delete_confirm.html:54`)를 우선 권고 — 기존 PRG+messages
  (`templates/staff/base_staff.html:58-64`)와 맞고 JSON 엔드포인트가 필요 없다.
  JS 모달을 택하면 `static/js/components/confirm-modal.js`(Escape 101·Tab 107·기본
  포커스 아니오 144·포커스 복귀 174-177) 재사용, 서버 거부 문구는
  `error_response(detail)`(`core/errors.py:4-5`)로 내려야 `static/js/shared/api.js:106-144`
  formatError가 "알 수 없는 오류"로 뭉개지 않는다. 프론트 파일 `[코드 추정]` 5개
  (templates 2·css 1·js 1·`_console_shell.html` 수정). 구현됨(트랙 19).
- H2 — 체크박스 열 + bulkbar(`templates/core/drafts/list.html:50-61`) + 행별 실패
  사유(`:118-123` `data-bulk-fail-reason`) + 카테고리 칩(`events/list.html:18-24` 패턴)
  + 기간 `<form method="get">`(숨은 파라미터 `_console_shell.html:100-102` 패턴).
  선택 범위: 두 목록 모두 서버 페이지네이션(`events/list.html:77-78`, 페이지 15건
  `events/queries.py:184` `[코드]`)이라 선택은 현재 페이지·필터에서만 유효, 전환 시
  초기화(드래프트 큐와 같은 제약). 응답 반영은 `static/js/staff/draft_bulk.js:396-430`
  applyBulkResult(succeeded/failed 배열) 이식, 재시도는 목표 상태 지정 API에만 허용.
  인라인 토글: 현재 토글 뷰는 redirect 반환(`staff/views/events.py:443`)이라 fetch가
  JSON을 못 받는다 → JSON 분기 또는 별도 엔드포인트가 백엔드 계약. 정렬·기간
  파라미터는 `_event_filter_query_pairs`(`events.py:110-117`, warning·publish_status만)
  확장 필수 — 빠지면 수정 후 목록 복귀 시 새 필터가 소실되고 `list.html`·`edit.html`·
  `delete_confirm.html` 3곳이 `list_query`를 공유한다. 이벤트 목록엔 JS가 없어
  (`[실측]` `grep -c "<script\|shell_js\|page_js" templates/staff/events/list.html` = 0)
  단축키를 넣으려면 `static/js/staff/queue_shortcuts.js:23-53` 가드를 이식.
- H3 — 큐 제목 셀 안 인라인 배지(`core/drafts/list.html:97-106`; colgroup 6열
  `:66-73` 고정폭이라 열 추가 금지), 고지는 `templates/core/archive/personal_detail.html:115`
  promote-note에 1줄(신규 안내 카드 금지). JS 없음.
- H5 — `templates/core/drafts/detail.html:154-159` judge-actions에 재오픈 버튼,
  `static/js/staff/draft.js:178` bindApproveButton 구조(askConfirm→setLoading→post→
  `successEl.focus()` 223) 재사용. 서버 pending 전용 가드로 멱등.
- H6 — `templates/staff/sources/list.html`(`<form` 0건 `[실측 grep -c]`)에 생성 폼·
  행별 수정·토글, 폼은 `events/edit.html:31-99` 패턴. 토글은 양방향이라 확인
  불필요(`events.py:397-398` 선례). 완료 시 admin 이탈 문구(`staff/views/__init__.py:237`) 제거.
- H9 — 이력 표는 백엔드 저장 구조 선행(`DraftSource` 상태 필드는 `drafts/models.py:67-68`
  2개). 재시도는 확인 불필요, "무시"가 영구 폐기면 확인 필요(설계 시 결정).
- H10 — 사유 템플릿은 단건 textarea(`core/drafts/detail.html:150-151`)에만 붙는다.
  일괄 반려는 `draft_bulk.js:468`이 `draft_ids`만 보내므로 사유 추가는 백엔드 변경 동반.
- H11 — 이력 패널은 `Event.updated_at` 부재로 백엔드 선행. 소비자 링크·만료 배지는
  `events/edit.html:101-183` rail-card.
- H12(a) — 「지금 수집」은 순수 폼 POST라 `api.js` 오류 분기가 관여하지 않고 프록시
  타임아웃 시 브라우저 오류 화면만 보인다(`staff/views/__init__.py:210`·`232`·`242`).
  대기 문구면 기존 가드로 충분, 실행 상태 조회면 백그라운드 잡 + 폴링(신규 아키텍처).
- H13 — 링크는 `dashboard.html:251` 패턴. 미리보기는 confirm-modal(예/아니오 전용)
  확장 금지, 콘텐츠 모달을 따로 설계.
- 공통 가드레일 — 신규 CSS는 `static/css/staff/tokens.css`의 `--c-*`만,
  `<main class="page" id="staff-main">` 래퍼 유지(S6). 위험 액션 폼에 `data-submit-guard`
  누락 금지(`[실측]` `rg -l data-submit-guard templates/` = 8파일).
- 검토 정정 기록 — BIR가 `events/edit.html:176-179` 삭제 폼을 "확인 없음"
  Medium-High 결함으로 보고했으나, 삭제 뷰는 서버 렌더 2단계 확인(`staff/views/events.py:480-483`,
  `confirmed=yes` 없으면 확인 화면만 렌더)이라 결함이 아니다. 첫 폼의 더블클릭은
  확인 화면을 두 번 열 뿐이다.

---

## 착수하지 않는 것

- **인프라 계정 액션** — 도메인 등록, PaaS 계약, SMTP 설정(T1~T8). 사용자가
  최후순위로 확정했다. "다음 단계"로 제안하지 않는다. SMTP 미설정 상태에서는
  신규 가입 이메일 인증이 동작하지 않는다는 사실만 기록해 둔다.
- **교환(trade) 매칭** — 밀도·신원·프라이버시·신고·차단·중재·운영 게이트
  승인 전까지 설계도 착수 금지.
- **서버 행사 필드 LLM 추출 재활성화** — 비용 정책상 불허.
  `DRAFT_LLM_EXTRACTION_ENABLED`는 계속 off이며 PaaS에 LLM API 키를 두지 않는다.
- **폐기된 시안 기반 시각 작업** — 과거 시안에서 나온 항목은 계속 착수하지 않는다.
  새 행사 에디토리얼 방향은 D4와 `docs/FE/event-typography-editorial.md`만 따른다.
- **데이터 내보내기(CSV/JSON)** — 어떤 구속 결정에도 없다. 요구가 생기면 그때.

---

## 갱신 규칙

- 항목을 지울 때는 해결 근거(PR 번호 + 검증 명령 결과)를 함께 남긴다.
- **어떤 항목이 서술한 문제를 고쳤다면, 그 항목의 표기를 같은 커밋에서 바꾼다.**
  이걸 빠뜨려 A1과 A5가 **해결된 지 몇 시간 만에** 미착수로 읽혔고, 두 번 다
  이미 있는 코드를 다시 쓸 뻔했다. 고침과 표기가 갈라지는 순간이 곧 사고 지점이다.
- 새 항목은 `file:line` 근거 없이 추가하지 않는다.
- 낡은 서술을 그대로 사용자에게 전달하지 않는다. 판정 전에 코드로 재확인한다.
  이 저장소는 낡은 백로그가 존재하지 않는 작업을 지시한 사고를 이미 겪었고,
  A1은 **해결된 지 몇 시간 만에** 미착수로 읽혔다.
- **숫자에는 단위와 출처를 붙인다.** 세는 대상(파일인가 등장 횟수인가 테스트
  케이스인가)을 밝히지 않은 수는 증거가 아니며 작업 규모의 근거가 될 수 없다.
  `[실측]`은 명령을 돌려 얻은 수, `[코드]`는 읽어서 센 추정이다. 구속력 있는
  전체 규칙은 `AGENTS.md`의 "Numbers In Documents"에 있다 — 이 백로그가 낳은
  과대 서술 3건이 그 규칙의 근거다.
