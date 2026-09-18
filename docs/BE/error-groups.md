# 오류 묶음(ErrorGroup) 기록 — 사이트 로그 1단계(트랙 36)

상태: **구현됨(2026-09-18)** — 백엔드 처리되지 않은 500 예외 + 프론트
전역 오류/거부 이벤트를 같은 테이블에 지문으로 묶어 저장하고, 스태프
대시보드에 요약 패널로 노출한다.

## Current fact

- `core.ErrorGroup`(`core/models.py:203-225`, 마이그레이션
  `core/migrations/0007_errorgroup.py`)는 다음 필드를 갖는다: `source`
  (choices `backend`/`frontend`, `max_length=10`), `fingerprint`
  (`max_length=64`, `unique=True`), `error_type`(`max_length=100`),
  `location`(`max_length=255`), `message_sample`(`max_length=500`,
  `blank=True`), `first_seen`·`last_seen`(`last_seen`만 `db_index=True`),
  `count`. 필드 상한을 모두 채운 500행 기준 실측 테이블 크기는
  **819,200바이트**(`pg_total_relation_size`)이고, 같은 조건에서 트랜잭션을
  롤백한 힙만의 크기는 **524,288바이트** `[실측 curl+psql, track36-evidence.md]`.
  출처별 상한(아래)이 있어 이 크기를 넘지 않는다.
- `core/error_groups.py`의 `record_error(*, source, error_type, location,
  message)`가 유일한 기록 진입점이다(`core/error_groups.py:76-109`). HTTP나
  Django 요청 객체를 모른다 — 호출자가 이미 문자열로 뽑아 넘긴다.
- 지문은 `sha256(f"{source}|{error_type}|{location}")`
  (`core/error_groups.py:58-61`, `compute_fingerprint`)이고, 같은 지문이면
  한 행에서 `count`만 늘린다.

## 무예외 보장

`record_error`는 절대 예외를 던지지 않는다(`core/error_groups.py:76-109`).

1. 저장은 자체 `transaction.atomic()`(중첩이면 세이브포인트)
   안에서 실행돼(`core/error_groups.py:94`), 호출자가 이미 깨진
   트랜잭션 안에 있어도 이 함수의 실패가 그 트랜잭션을 추가로
   오염시키지 않는다.
2. 갱신은 `update()`(존재하면 `count=F+1`) → 0행이면 `create()` → 동시
   생성으로 `IntegrityError`가 나면 다시 `update()`로 반영한다(DAR 결정,
   `core/error_groups.py:112-142`, `_upsert_error_group`). `create()`는
   자체 세이브포인트 안에서 실행돼 실패해도 바깥 갱신 시도를 오염시키지
   않는다.
3. 함수 전체를 `except Exception`으로 감싸고(`core/error_groups.py:104`),
   실패 시 `core.error_groups` 로거에 고정 접두어 `error-group record
   failed`로 WARNING 1줄만 남긴다 — **원 메시지는 포함하지 않고**
   `source`·정제된 `error_type`(최대 100자로 자른 값)만 남긴다
   (`core/error_groups.py:104-109`).

## 메시지 정제 순서

`sanitize_message`(`core/error_groups.py:64-73`)는 다음 순서로만 저장
가능한 문자열을 만든다.

1. 제어문자·개행·탭 제거 후 연속 공백 축소(`_CONTROL_CHARS_RE`,
   `_EXTRA_SPACES_RE`, `core/error_groups.py:19-20,66`).
2. `settings.SECRET_KEY`·`ANTHROPIC_API_KEY`·
   `DRAFT_DISCOVERY_RUNNER_TOKEN`·DB 비밀번호(비어 있으면 대조 제외) 중
   하나라도 부분 일치하면 **메시지 전체를 빈 문자열로 비운다**
   (`_contains_secret`, `core/error_groups.py:33-47,68-69`) — 이후
   단계로 넘어가지 않는다.
3. 이메일을 `[email]`로 마스킹(`_mask_emails`, `core/error_groups.py:50-51,71`).
4. URL 쿼리·프래그먼트 제거(`_strip_url_queries`,
   `core/error_groups.py:22,54-55,72`).
5. 500자(`MESSAGE_SAMPLE_MAX_LENGTH`, `core/error_groups.py:24,73`) 절단.

## 출처별 상한

`SOURCE_GROUP_LIMIT = 250`(`core/error_groups.py:27`) — `backend`·
`frontend` 각각 최대 250행, 합 최대 500행. **새 지문이 실제로 새 행을
만들 때만** 그 출처의 최고령(`last_seen` 오름차순) 1행을 지운다
(`_trim_source`, `core/error_groups.py:147-161`). `update()` 경로나
`IntegrityError` 재시도 경로(기존 행 갱신)에서는 부르지 않는다 — 근사
상한이라 동시 생성 시 ±1~2행 허용(DAR 결정).

## 핸들러(`core/logging.py`)

- `ErrorGroupHandler`(`core/logging.py:9-42`)는 `django.request` 로거에만
  붙는다(`config/settings.py:648-658`, `"django.request"` 항목의
  `handlers: ["console", "error_groups"]`, `level: "ERROR"`) — root에는
  붙이지 않는다. 다른 경로의 의도된 WARNING이 오류 묶음으로 새는 것을
  막기 위해서다.
- 모듈 최상단에 Django 모델·앱 임포트를 두지 않고 `emit()` 안에서만
  지연 임포트한다(`core/logging.py:20,33`) — `settings.LOGGING`은
  앱 레지스트리 준비 전에 평가되므로, 최상단에서 모델을 임포트하면
  부팅 시 `AppRegistryNotReady`가 난다.
- `exc_info`가 없는 레코드는 무시한다(`core/logging.py:15-16`).
- 원 예외가 `django.db.Error` 계열이면 `record_error`를 아예 호출하지
  않고 건너뛴다(`core/logging.py:20-25`) — DB 장애 중에 오류 묶음을
  남기려고 DB에 또 접근하면 지연이 늘어나 `docker/entrypoint.sh`의
  gunicorn 기본 타임아웃(설정 없음 → 기본 30초,
  `docs/operations-runbook.md:271`)을 넘길 수 있어서다.
- `location`은 `f"{method} {route}".strip()`이고 `route`가 없으면
  `"unresolved"`(`core/logging.py:27-31`). 요청 본문·쿼리스트링·쿠키·
  사용자 정보는 저장하지 않는다.

## 수집 API — `POST /api/client-errors/`

`core/client_error_views.py`, `ClientErrorReportView`(`:101-139`),
`core/urls.py:13`에 `client-errors/`로 등록. 이 저장소의 **첫 무인증 공개
쓰기 엔드포인트**라 어떤 입력이 와도 **항상 204**를 반환하고 상세를
노출하지 않는다.

- 같은 출처(Origin 없으면 Referer, 둘 다 없으면 거부)가 아니면 기록 없이
  204(`_is_same_origin`, `core/client_error_views.py:44-51,120-121`).
- 본문 4096바이트(`MAX_BODY_BYTES`, `:22`) 초과·비UTF-8·비JSON이면 204
  (`_parse_json_body`, `:54-60`).
- 허용 키는 `message`·`name`·`script`·`line`·`col`뿐이고 필수 키는
  `message`·`script`·`line`(`_ALLOWED_KEYS`·`_REQUIRED_KEYS`, `:24-25`).
  문자열 키(`message`·`name`·`script`)는 문자열 타입, 정수 키(`line`·
  `col`)는 정확히 `int`(`bool`은 `int`의 서브클래스라 배제,
  `_is_valid_int`, `:63-66`)만 허용한다(`_is_valid_payload`, `:69-78`).
- 전역 단일 버킷 스로틀 120회/시간
  (`GlobalClientErrorThrottle`, `:92-98`) — 이 API는 미인증이라 기본
  스로틀이 요청 IP를 식별자로 쓰는데, 저장소에 프록시 개수 설정이 없어
  `X-Forwarded-For`를 그대로 믿는 문제가 있어(러너 스로틀과 동일 문제)
  IP 대신 고정 문자열 `"global"`로 묶는다. 초과 시에도 204
  (`handle_exception`, `:113-117`).
- 위 상한과 별도로 **프론트 새 묶음 생성만** 시간당 20건
  (`NEW_GROUP_HOURLY_LIMIT`, `:23`, `_new_group_allowed`, `:81-89`) — 기존
  묶음 갱신(`count` 증가)은 이 상한과 무관하다. 이 상한이 없으면 익명
  프론트 보고가 새 묶음 생성만으로 시간당 상한을 소진해 다른 정상 오류의
  새 묶음 생성까지 막을 수 있다(SRR F1).
- 경로의 숫자·UUID 세그먼트는 `:id`로 접는다(`normalize_path`,
  `:33-41`) — 쿼리·프래그먼트는 항상 지운다.
- `error_type`은 `"js:" + (name 또는 "unknown")`(오류 이름, 메시지
  앞부분이 아니다), `location`은 `f"{정규화된 script}:{line}"`, 메시지
  원문은 `message_sample`로만 저장된다(`:127-130`).
- 이 뷰는 `extend_schema(exclude=True)`로 공개 OpenAPI 스키마에서
  제외된다(러너 API와 같은 패턴, `core/client_error_views.py:101`).

**Origin/Referer 검사는 브라우저를 통해 오는 요청 경로만 걸러낸다 — 실제
공격 방어가 아니다.** `curl` 등은 두 헤더 모두 얼마든지 위조할 수 있다
(`_is_same_origin` 주석, `core/client_error_views.py:44-47`, SRR F7). 이
엔드포인트의 실질 방어는 Origin 검사가 아니라 **본문 상한(4KB)·페이로드
스키마 검사·전역 스로틀(120/시간)·새 묶음 상한(20/시간)** 네 가지다.

## 프론트 캡처

- `templates/base.html:9-12`, `templates/staff/base_staff.html:11-13`의
  head 최상단(테마 스크립트보다 앞) 인라인 부트스트랩이
  `window.__takuErrorQueue = []`를 만들고 `error`·`unhandledrejection`
  리스너를 즉시 건다 — 이 시점에는 아직 다른 스크립트가 실행되지 않아
  이후 로드되는 어떤 스크립트의 동기 오류도 큐에 놓치지 않는다.
- `static/js/shared/error_report.js`(두 셸 모두 defer 목록 첫 번째,
  `templates/base.html:120`, `templates/staff/base_staff.html:80`)가 큐를
  드레인한 뒤(`drainBootstrapQueue`, `:75-86`) 큐의 `push`를 무시
  함수로 바꿔치고, 이후 오류는 자신의 리스너로 직접 처리한다
  (`bindListeners`, `:88-103`) — 같은 이벤트가 두 번 보고되지 않는다.
- 페이지당 최대 5건(`MAX_PER_PAGE`, `:11`)이고, **카운터는 필터를 통과해
  실제로 전송을 시도하는 항목만 늘린다**(`:64`, 2026-09-18 수정
  `14fa37c3`) — 이전 버전은 무시 대상(확장·교차 출처·중복)도 카운터를
  소모해, 폭주 앞부분이 전부 확장/교차 출처 오류면 뒤따르는 진짜 오류가
  상한 소진으로 전송되지 않는 결함이 있었다.
- 무시 대상: `"Script error."`(교차 출처 스크립트의 상세 가림,
  `:36-38`), `chrome-extension`/`moz-extension`/`safari-extension` 스킴과
  교차 출처 스크립트(`:48-52`), 같은 지문(`name|script|line|message
  앞 100자`)의 중복(`:57-60`).
- 전송은 `navigator.sendBeacon(ENDPOINT, new Blob([JSON.stringify(payload)],
  {type: "application/json"}))`(`:68-73`)이고 `window.onerror` 대입 없이
  `addEventListener`만 쓴다. DOM·토스트에 영향을 주지 않고, 실패는
  조용히 삼킨다(`:90-102,107-112`).
- bfcache로 페이지가 되살아나도 이 스크립트는 재실행되지 않아
  `reportedCount`·`seenFingerprints`는 같은 페이지뷰 동안 유지된다(주석,
  `:105-106`).
- 이 설계 때문에 **프론트 `count`는 실제 발생 횟수가 아니라 "몇 개의
  서로 다른 페이지뷰가 이 오류를 처음 5건 안에서 보고했는가"에 더
  가깝다.** 한 페이지뷰에서 같은 오류가 여러 번 나도 지문당 1회만
  전송되고, 페이지당 5건 상한도 있다.

## 대시보드 패널

- `core.error_groups.system_error_summary`(`:164-203`)가 **쿼리 2회
  고정**(`aggregate` 1회 + 상위 목록 `values()` 슬라이스 1회)으로
  전체 건수, 24시간·7일 창 안 `last_seen` 묶음 수, 출처별 건수, 상위
  5개(`last_seen` 내림차순)를 계산한다. "종" 표기(`templates/staff/
  dashboard.html:381`)는 **묶음 수**이지 발생 횟수 합이 아니다.
- `staff/views/__init__.py:282`가 이 결과를 `system_errors` 컨텍스트로
  대시보드에 넘긴다. 템플릿(`templates/staff/dashboard.html:372-398`)은
  Django 기본 자동 이스케이프만 쓴다 — `|safe`·`innerHTML` 없음(SRR F6),
  `error_type`에 `<script>`가 들어와도 텍스트로 렌더된다.
- 빈 상태 문구: `"최근 발생한 시스템 오류가 없습니다 ✓"`
  (`templates/staff/dashboard.html:378`).

## 롤백 시 유의

이 마이그레이션(`core/migrations/0007_errorgroup.py`)은 `CreateModel`만
있다 — 역적용(`migrate core 0006`)하면 테이블이 통째로 삭제된다. 배포
롤백 시 **기본은 테이블을 그대로 둔다**(역마이그레이션 실행 금지) — 이미
쌓인 오류 묶음을 되돌리기 롤백 한 번으로 잃을 이유가 없다.

## 이연

- 로컬 러너 실행 결과 보고(트리거: 대시보드 `error_summary` 단건 노출로
  부족하다는 운영 신호).
- IP 보조 스로틀(트리거: 신뢰 프록시 헤더(`X-Forwarded-For` 개수)
  확보).
- 시크릿 스캐너 고도화(부분 일치 대조 이상의 패턴 탐지).
- 폐기(무시)된 요청 수 지표 — 현재는 204만 보고 왜 버려졌는지 알 수 없다.
- 출처별 상한·스로틀 수치의 env화(현재는 상수 하드코딩).
- 사이트 로그 4단계(보존 정리 — 오래된 `ErrorGroup` 행 삭제 정책) —
  범위 밖(미착수).

## Evidence

`[실측 track36-evidence.md, 2026-09-18]` 뮤테이션 검출: 정제 7종(제어
문자·시크릿·빈 시크릿·이메일·URL·절단·DB 비밀번호), 세이브포인트 제거·
`IntegrityError` 재시도 제거·출처 필터 제거, 핸들러 DB 오류 건너뜀
제거·settings 배선 제거·`unresolved`/`exc_info` 분기, 수집 API 허용
키·dict·크기·타입·bool 배제·스로틀 204·새 묶음 상한, 요약 조회 24h·7d
창·정렬. 기존 500 회귀 5파일 **112 passed**. 브라우저(Chrome DevTools
MCP) 검증: 부트스트랩 선행 로드, 같은 오류 반복 시 beacon 1회, 서로
다른 10건 폭주 시 5건에서 멈춤, 무시 대상 미전송, 대시보드 패널
1280·1024 × 라이트·다크 가로 넘침 0·콘솔 오류 0. `curl` 검증: 다른
Origin 204·미기록, 비UTF-8 204, 130회 연속 전부 204, 새 프론트 묶음은
시간당 20에서 멈춤. 500행 채움 시 `pg_total_relation_size` 819,200바이트
(위 "Current fact" 참고).
