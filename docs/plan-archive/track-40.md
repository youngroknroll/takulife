# 트랙 40: 보안 검토 2026-09-27 반영 (2026-09-28) [v1 — SRR·DOR·DAR·QVL·TDD 코치 사전 검토 통합, 오케스트레이터가 라이브러리 소스·실측으로 재확인. **구현 완료, PR #388 오픈(머지 승인 대기)** — 사후 기록은 절 끝]

> **출처**: 사용자 `/goal` 지시(2026-09-28) "docs/BE 폴더의 보안 검토 문서를 토대로 반영". 정본 `docs/BE/security-review-2026-09-27.md` §7 권장 트랙(PR 1개·결함별 커밋 ①~⑤)을 범위로 채택한다. `/goal`이 사용자 확인 없이 진행하라고 지시하므로 이 지시를 §7 범위의 승인으로 본다(가정 — 최종 보고에 명시).
> **기준선**: 브랜치 `fix/security-review-2026-09-27` = main `2c0e3552`. `uv run pytest -q` **3181 passed / 10 deselected / 91.75초** [실측 2026-09-28]. 로컬 DB: 스킴이 http(s)가 아닌 `official_url` 0행, memo 최대 길이 PersonalEntry 23자·CollectionItem 7자 [실측 `manage.py shell`, 이벤트 172행].

## 정정 (정본 문서 대비, 오케스트레이터가 코드로 확인)
1. **F3 미들웨어 → DRF 파서로 위치 변경.** 문서의 `JsonBodySizeLimitMiddleware`(JSON이면 경로 무관 413)는 `/api/client-errors/`의 "항상 204" 계약과 충돌한다 — `tests/core/test_client_error_report.py` EG-31(`DATA_UPLOAD_MAX_MEMORY_SIZE=100`에서 204 단언)이 413으로 깨진다 [코드 `core/client_error_views.py:54-60`, 테스트 :345-357]. 결함의 원인은 DRF `JSONParser`가 `HttpRequest.read()`를 직접 읽어 Django 상한을 건너뛰는 것이므로 **DRF 파서 확장점에서 막는다**: `core/parsers.py` 신설 `SizeLimitedJSONParser(JSONParser)` — `CONTENT_LENGTH`가 `settings.DATA_UPLOAD_MAX_MEMORY_SIZE`(None이면 무검사)를 넘으면 본문을 읽기 전에 413 `APIException`. `REST_FRAMEWORK["DEFAULT_PARSER_CLASSES"]`에 JSON 자리만 교체(Form·MultiPart 유지). `ClientErrorReportView`는 `parser_classes = []`라 영향 없음.
2. **F10(MFA)은 기록된 사용자 보류다.** `auth-hardening` 결정(2026-07-01): allauth.mfa TOTP 폐기·"지금은 두지 않음"(B1 rate limit + B3 Google 2FA 위임). 문서 §4 보류 목록에 빠져 있었다 → 재권고하지 않고 문서 §4에 추가 기록.
3. **F7·F9는 Test List 초안에 시나리오가 없었다** → SEC-13~15b로 추가. F1 재게시 경로의 HTTP 번역(SEC-03b)과 허용 스킴 통과 핀(SEC-04b)도 추가.
4. **F1 초안 경로의 drafts 매핑(선택)은 제외.** 초안 `source_url`은 생성 3경로가 이미 http(s)로 제한 [문서 §2 F1, 코드 `drafts/serializers.py:95-98`]. Django admin은 `URLField` 검증기(http·https·ftp·ftps)라 `javascript:`는 도달 불가. 기존 초안이 스킴 오류를 내면 `approve_draft`가 `DraftPublicationError` → 503으로 번역한다(500 아님, 오도 문구 — 운영 확인 항목으로만 기록).

### v1 사전 검토 반영 (2026-09-28)
5. **F3 범위 확장(SRR 블로커)** — DRF `FormParser.parse`도 `stream.read()`로 무제한 읽는다 [코드 `rest_framework/parsers.py:77-84`]. POST는 CSRF 검사가 `request.POST`를 먼저 읽어 Django 상한을 타지만 PATCH·PUT은 그러지 않는다 [코드 `django/middleware/csrf.py:366`] → archive 상세 뷰 4개(`archive/views.py:149,360,495,681`)의 urlencoded PATCH가 무제한. `core/parsers.py`에 크기 검사 믹스인 하나로 `SizeLimitedJSONParser`·`SizeLimitedFormParser`를 두고 `DEFAULT_PARSER_CLASSES`의 두 자리를 교체(MultiPart는 Django 파서가 이미 상한 강제). SEC-08b 추가.
6. **F1 호스트 필수(SRR 강한 권고)** — `https:javascript:alert(1)`·`http://`는 `urlsplit` 스킴이 허용값이지만 netloc이 비어 있다 [실측 `urlsplit`]. 규칙 = 스킴 ∈ {http, https} **그리고** netloc 존재. 같은 예외·같은 체크 항목 하나로 판정(항목 문구 "공식 URL은 http:// 또는 https://로 시작하는 주소여야 합니다"). 탭·CR·LF 삽입과 앞 제어문자는 `urlsplit`이 제거·스킴 불인식해 이미 거부된다 [실측]. SEC-01에 사례 추가.
7. **F7 전용 상수(DAR 수정)** — `MAX_EVENTS_PER_RUN`은 실행당 영속 드래프트 생성 상한이라 조회 요청 길이와 의미가 다르다 → `drafts/runner_views.py`에 `MAX_KNOWN_URLS_PER_REQUEST = 20`(러너 전송 최대 `EXPLORATION_MAX_EVENTS = 20` [코드 `local_runner/exploration_flow.py:17`]과 같은 값) 신설, `agent_drafts` 임포트 불필요.
8. **F4 잠금 해제 보장 범위(DOR·SRR, 오케스트레이터 정정)** — DOR 주장 "gunicorn 타임아웃 SIGKILL로 finally가 안 돈다"는 부분 오류: 기본 30초 [코드 `gunicorn/config.py`, `docker/entrypoint.sh`에 `--timeout` 없음] 초과 시 아비터는 먼저 SIGABRT를 보내고(`gunicorn/arbiter.py:590-593`) 워커는 `sys.exit(1)`(`gunicorn/workers/base.py:195-198`) → `SystemExit`가 `finally`를 통과하므로 잠금은 보통 풀린다. SIGKILL은 다음 아비터 점검까지 살아 있을 때만(`arbiter.py:594-595`). 보장 범위 = 정상·파이썬 예외·SIGABRT 종료, SIGKILL 뒤에는 TTL 600초까지 잔존 → 운영 런북에 수동 해제 명령. 만료 행이 남은 뒤의 `add`는 UPDATE 분기라 동시 획득 경쟁이 이론상 남는다(`django/core/cache/backends/db.py` `_base_set`, SRR) — F4 도입 전과 같은 결과라 신규 위험 아님, AC5에 명시. 구현: 잠금 해제는 감사 로그 기록 실패와 무관하게 실행되도록 바깥 `try/finally`에 둔다. F4 뮤텍스는 `drafts.discovery_runs`의 `SourceDiscoveryRun` 활성 실행 규칙과 다른 명령을 보호하므로 통합 대상이 아니다(DAR).
9. **F2 실패 양상 비대칭(DOR·SRR)** — 같은 `TRUSTED_PROXY_COUNT` 과대설정에서 axes·감사 로그(`core/ip.py:31-32`)는 조용히 REMOTE_ADDR 폴백, allauth(`httpkit.py:200-205`)는 XFF가 있고 홉이 모자라면 500. 권장값 1에서는 `split(",")`가 원소를 최소 1개 돌려줘 도달 불가 [코드], 2 이상에서만 발생 → 런북 문구로 기록(코드 변경 없음).
11. **F3 본문 크기 결함은 반박됨(구현 중 실측, 정정 1·5 폐기)** — DRF 3.17.2 `Request._parse`가 `JSONParser`·`FormParser`에는 `io.BytesIO(self.body)`를 넘긴다 [코드 `rest_framework/request.py:358-360`, SRR 사후 검증이 원래 인용 357-359의 1줄 오차를 지적해 정정] → `HttpRequest.body`의 `_check_data_too_big`이 `DATA_UPLOAD_MAX_MEMORY_SIZE`를 강제한다. 정본 문서·SRR은 `_load_stream`(:297-314)만 읽고 이 분기를 놓쳤다. 실측: 기본 상한에서 2,700,000바이트 JSON POST·폼 PATCH·JSON PATCH 모두 400·DB 불변 [실측 probe 2026-09-28], 상한을 1,024로 낮춘 SEC-08b·08c도 400 [실측]. → ④ `core/parsers.py`·`DEFAULT_PARSER_CLASSES` 변경 **취소**, SEC-08a·08e·09 삭제, SEC-08b·08c는 기대값을 413→400으로 바꿔 **기존 보호를 고정하는 핀**으로 유지(DRF 업그레이드로 이 분기가 사라지면 잡는다). memo 상한(F3a)은 유효 — 상한 이내 본문으로도 memo 2.5MB 저장이 가능했다.
10. **배포 전 운영 DB 확인(DOR)** — 비-http(s)·호스트 없는 `official_url` 행 수, memo 최대 길이를 `docs/deploy-runbook.md` §3 체크리스트에 추가. 로컬 값으로 대체 불가.

## 승인 범위 (PR 1개, 커밋은 결함별)
- **① F1** `events/services.py`: `ALLOWED_OFFICIAL_URL_SCHEMES = frozenset({"http", "https"})`, `PublishEventOfficialUrlSchemeError(PublishEventError)`. `_validate_publish_fields`에서 비어 있음 검사 직후 `urlsplit(...)`의 스킴 허용목록 + netloc 존재 검사(정정 6). `publish_field_checks`에 같은 위치(`official_url` 다음) `{"key": "official_url_scheme", "label": "공식 URL은 http:// 또는 https://로 시작하는 주소여야 합니다", ...}` — URL이 비어 있으면 판정 불가라 실패로 표시(기존 `official_url_unique` 선례와 같음, `tests/events/test_publish_field_checks.py` 누락 사례의 기대 실패 key에 추가). `staff/views/events.py` `_publish_event_field_errors`(→ `official_url` 필드 오류)·`REPUBLISH_ERROR_MESSAGES`(부모 `PublishEventError` 앞) 매핑. 템플릿 변경 없음(승인 전 체크는 기존 루프가 렌더).
- **② F2** `config/settings.py`: `build_allauth_trusted_proxy_count(trusted_proxy_count)`(→ `trusted_proxy_count or 0`, 기존 `build_axes_client_ip_callable` 관용구) + `ALLAUTH_TRUSTED_PROXY_COUNT = build_allauth_trusted_proxy_count(TRUSTED_PROXY_COUNT)`. 문서: `.env.example` TRUSTED_PROXY_COUNT 설명, `docs/deploy-runbook.md` §1 표·§3 체크리스트(스테이징 확인: IP A 실패 10회 뒤 IP B 첫 로그인이 429가 아님), `docs/operations-runbook.md` §2·§4(allauth도 이 env를 따름, 홉 과대설정 시 allauth는 500 `ImproperlyConfigured` — allauth `httpkit.py:201-205`).
- **③ F3a** `archive/models.py` `MEMO_MAX_LENGTH = 2000`, `archive/serializers.py` `PersonalEntrySerializer`·`CollectionItemSerializer`에 `memo = serializers.CharField(required=False, allow_blank=True, max_length=MEMO_MAX_LENGTH)`(Update 시리얼라이저는 상속).
- **④ F3b** `core/parsers.py`(신설: 크기 검사 믹스인 + `SizeLimitedJSONParser`·`SizeLimitedFormParser` + 413 `APIException` 하위 예외) + `config/settings.py` `DEFAULT_PARSER_CLASSES`(JSON·Form 교체, MultiPart 유지 — 정정 1·5).
- **⑤ F4** `staff/views/__init__.py`: `DISCOVERY_RUN_LOCK_KEY`·`DISCOVERY_RUN_LOCK_TIMEOUT_SECONDS = 600`, 활성화·소스 검사 뒤 `cache.add`가 False면 `messages.info("이미 수집이 실행 중입니다. 끝나면 다시 시도하세요.")` + 리다이렉트(감사 로그 없음). 잠금 해제는 감사 로그 `finally`를 감싸는 바깥 `try/finally`(정정 8). 운영 런북에 수동 해제 명령.
- **⑥ F5** `drafts/url_safety.py`·`local_runner/url_safety.py` `_is_unsafe_ip`에 `or not value.is_global`(두 파일 동시, 문자 일치 가드 `tests/local_runner/test_url_safety_parity.py`).
- **⑦ F7** `drafts/runner_views.py` `RunnerKnownDraftUrlsView`: `len(urls) > MAX_KNOWN_URLS_PER_REQUEST`(같은 파일 신설 상수, 값 20 [코드 러너 `EXPLORATION_MAX_EVENTS`와 같음], 정정 7) 또는 원소가 `str`이 아니면 400(기존 문구 `invalid known urls payload`).
- **⑧ F9** `config/settings.py` `load_secure_cookies()`(`_get_env` 사용, `load_secure_ssl` 관용구) → `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE`. `docs/operations-runbook.md:166`의 `os.environ.get` 인용 정정.
- **런북(DOR 초안 채택 — 여러 결함이 같은 런북 파일을 건드려 병렬 편집 충돌을 피하려고 ⑨ 문서 커밋 하나로 모은다)** ② `.env.example`·`docs/deploy-runbook.md` §1 표·§3 항목 8(스테이징: allauth 4경로 signup·login_failed·reset_password·manage_email이 위조 XFF에도 500·잘못된 429가 없음 [문서 DOR])·`docs/operations-runbook.md` §2·§4(정정 9 비대칭) / ⑤ `docs/operations-runbook.md` 수집 잠금 수동 해제 명령(`cache.delete("staff-draft-discovery-run-lock")`)과 보장 범위(정정 8) / ①·③ `docs/deploy-runbook.md` §3에 배포 전 운영 DB 확인(정정 10) / ⑥ 배포 순서 한 줄(서버 먼저, 러너 복제본은 러너 재시작 뒤 반영 — 서버 직접 fetch 경로는 즉시 보호).
- **⑨ 문서** `docs/BE/security-review-2026-09-27.md`(발견별 상태·정정 1·2·5~10 기록, 현재 미추적 파일) + `docs/backlog.md` J절 상태. 두 파일의 기존 미커밋 변경은 전부 이 보안 검토의 산출물이라 함께 커밋한다. `prompt_plan.md`는 커밋하지 않는다.

## 제외 (사유)
F6 러너 IP 핀닝·스트리밍 상한 — 문서 §7이 트랙 35 이연 항목과 함께 처리하도록 분리(기존 러너 테스트 다수가 `httpx.get`을 스텁해 읽기 경계 재설계가 필요). F8 지문별 상한 — 문서 §7 "선택", 공격자는 메시지를 바꿔 지문을 회피할 수 있어 효과가 비악의적 반복 루프에 한정. F10 MFA — 기록된 사용자 보류(정정 2). F11 CSP — 새 의존성·인라인 스크립트 nonce 전환이 필요해 별도 트랙(승인 필요). 템플릿 선택 항목(`rel="noopener noreferrer"`, textarea `maxlength`) — 프론트 이중 검토 대상이라 이 백엔드 트랙에서 제외. G2 gunicorn `--timeout` — 별도 예약 트랙. 사용자별 저장 총량·쿼터 — 문서 §4 하드닝.

## 수용 기준
AC1 `javascript:`·`data:`·`vbscript:`·스킴 없는 값·호스트 없는 값(`https:javascript:…`, `http://`)의 공식 URL은 생성·수정·재게시에서 거부되고 DB에 남지 않는다, 호스트가 있는 `http://`·`https://`는 통과, 승인 전 체크에 스킴 항목이 검증기와 같은 순서로 표시된다. AC2 `TRUSTED_PROXY_COUNT=1`이면 allauth 신뢰 홉도 1, 같은 `REMOTE_ADDR`·다른 `X-Forwarded-For` 두 클라이언트의 `login_failed` ip 버킷이 분리되고, 미설정이면 REMOTE_ADDR 기준이 유지된다. AC3 [정정 11 반영, QVL 최종 판정 지적] 상한 초과 JSON 본문과 urlencoded PATCH 본문은 기존 Django 본문 상한으로 **400**이고 행이 생기거나 바뀌지 않는다(대상 archive 상세 뷰는 PUT을 허용하지 않아 PUT은 해당 없음 — `archive/views.py:150,361,496,682` `http_method_names`) — 측정 전 원문: "…PATCH·PUT 본문은 413이고 행이 생기거나 바뀌지 않으며," multipart 사진 업로드는 그대로 201, `/api/client-errors/` 204 계약 유지. AC4 memo 상한+1자는 400, 상한과 같은 길이는 성공(상한 2,000자 [문서 §2 F3]). AC5 수집 실행 중 두 번째 POST는 명령을 돌리지 않고 감사 로그를 늘리지 않으며, 정상·예외 종료 뒤 잠금이 풀린다(보장 범위는 정상·파이썬 예외·SIGABRT 종료. SIGKILL 뒤 잠금 TTL 만료 직후의 근접 재요청 경쟁은 범위 밖이며 결과는 도입 전과 같다 — 정정 8). AC6 100.64.0.0/10은 서버·러너 모두 안전하지 않은 URL. AC7 known-urls가 요청당 상한(`MAX_KNOWN_URLS_PER_REQUEST`)을 넘거나 비문자열 원소가 있으면 400. AC8 `.env`의 `SECURE_COOKIES`가 반영된다. AC9 전체 회귀 Green, `check`·`makemigrations --check` 무변화, `check --deploy`(프로덕션형 env) W021만.

## 역할
Activated: **SRR**(설계 검토·사후 검증, 전 결함이 보안 경계) / **Backend TDD Coach**(Test List·Red/Green 판정) / **BIE**(구현·문서) / **QVL**(위험 매트릭스·최종 증거) / **DOR**(F2 env·런북, F3 파서 등록, F4 DatabaseCache 잠금·gunicorn 타임아웃 상호작용·배포 영향) / **DAR**(정정 1의 위치 변경 — core 공용 파서·설정 결합, F2 설정 함수). Not activated: PSO(제품 범위 변경 없음 — memo 상한은 남용 가드이며 로컬 실측 최대 길이 대비 여유가 크다, 운영 DB 확인은 DOR 체크리스트) / WED·BIR·FIE(템플릿·CSS·JS 변경 없음) / AIA(LLM 무관).

## 도메인 경계·결합·Pythonic
- 스킴 규칙은 `events` 검증기 한 곳(단일 출처), 뷰는 예외→문구 번역만. memo 상한 숫자는 `archive` 모델 모듈이 소유하고 시리얼라이저가 경계 검증. 본문 크기 가드는 `core`(공용 웹 기반) — 도메인 모듈 임포트 없음. 뮤텍스는 staff 뷰(오케스트레이션 경계, 기존 `staff/views/discovery.py` 캐시 제한 선례). 러너 복제본은 서버 모듈 임포트 금지 계약 유지.
- 결합: 새 의존 방향 없음(F7은 전용 상수로 `agent_drafts` 임포트 불필요, `core/parsers.py`는 `rest_framework`만 임포트 — 경계 계약 R1 `tests/core/test_architecture_boundaries.py`). 응집: 각 규칙이 소유 모듈에 모인다.
- 설정은 기존 `load_*`/`build_*` 순수 함수 + 모듈 속성 일치 계약 테스트 관용구를 따른다.

## Test List (초안 — 코치 확정 전, ID는 정본 문서 SEC 번호 승계 + 추가)
| ID | 행동 | 경계 | 테스트 위치 | 상태 |
|---|---|---|---|---|
v1 코치 확정 반영: SEC-13·14 위치 정정(`tests/drafts/test_runner_draft_api.py:200-215`가 known-urls 동작 테스트, `test_discovery_runner_api.py`는 인증 계약만 [코드]) / `tests/core/test_settings_env.py`는 파일 전체 `pytestmark = contract`(:7) → SEC-05a·15a 경계 contract / SEC-04b는 대문자 스킴만(소문자 http(s)는 기존 happy path 수십 건이 이미 덮음) / SEC-01·02는 웹 번역 대표 1건, 스킴 열거는 가장 싼 경계 SEC-04a / SEC-03(domain 재게시)은 SEC-04a와 같은 검증기 규칙이라 중복 → 재게시 경로는 SEC-03b(web)로 흡수 / SEC-08은 파서 unit(08a·08e)과 배선 web(08b·08c)으로 분리 / SEC-12는 기존 `TestLiteralIp` parametrize에 1행.
| ID | 행동 | Given → When → Then | 경계 | 위치 | 상태 |
|---|---|---|---|---|---|
| SEC-04 | 승인 전 체크 항목 집합·순서에 `official_url_scheme`이 `official_url` 다음에 온다 | 기존 핀 3건 갱신: `test_시작일이_종료일보다_늦으면_기간_체크만_실패한다`(dict·순서) / `test_제목이_공식_url과_같으면_…`(dict) / 짝 parametrize `official_url_missing` 기대 key에 `official_url_scheme` 추가 | contract | tests/events/test_publish_field_checks.py | Green |
| SEC-04a | 허용되지 않는 공식 URL은 검증기가 스킴 예외를 내고 미리보기는 스킴 항목만 실패 | 기존 짝 parametrize는 예외 클래스를 값으로 받아 아직 없는 예외를 넣을 수 없으므로 **별도 함수** `test_허용되지_않는_공식_URL은_검증기가_스킴_예외를_내고_미리보기는_스킴_항목만_실패한다`로 구현(코치 사후 판정: 동등 커버리지, ids: javascript_스킴·data_스킴·vbscript_스킴·스킴_없음·호스트_없는_https_콜론·호스트_없는_http) → `PublishEventOfficialUrlSchemeError` + 실패 key `{"official_url_scheme"}`. **F1 주행 테스트 = javascript_스킴** | contract | 같은 파일 | Green |
| SEC-04b | 대문자 스킴 공식 URL은 검증을 통과 | `HTTPS://Example.com/event` → `_validate_publish_fields` 정상 반환. 이미 Green → 뮤테이션: 스킴 비교를 대소문자 구분 `startswith`로 임시 교체 | domain | tests/events/test_events_services.py | Green |
| SEC-01 | 스태프가 `javascript:` 공식 URL로 이벤트를 만들면 공식 URL 필드 오류로 거부되고 저장되지 않는다 | 스태프 로그인 → 생성 POST → 400·`field_errors["official_url"]` 스킴 문구·Event 0행 | web | tests/staff/test_staff_event_create_view.py | Green |
| SEC-02 | 스태프가 공식 URL을 `data:`로 수정하면 필드 오류, 기존값 유지 | 게시 이벤트 → 수정 POST → 400·필드 오류·`refresh_from_db` 값 불변 | web | tests/staff/test_staff_event_edit_views.py | Green |
| SEC-03b | 형식이 잘못된 공식 URL의 초안 이벤트를 인라인 재게시하면 400과 전용 문구 | 기존 `_U8_CASES`(:271-285)에 `공식_URL_형식_무효`(`official_url="www.example.com"`) 1행 → `{"detail": 전용 문구}`, 상태 DRAFT 유지, 감사 로그 0 | web | tests/staff/test_staff_event_inline_actions.py | Green |
| SEC-05a | 신뢰 프록시 홉 수를 allauth 설정값으로 옮긴다 | `build_allauth_trusted_proxy_count(None/0/1)` → 0/0/1(parametrize). **F2 주행** | contract | tests/core/test_settings_env.py | Green |
| SEC-05b | 설정 모듈 `ALLAUTH_TRUSTED_PROXY_COUNT`가 함수 결과와 일치 | 기존 :488-495 AXES 일치 테스트 관용구 | contract | 같은 파일 | Green |
| SEC-06 | 신뢰 프록시 뒤에서 한 클라이언트의 로그인 실패가 다른 클라이언트를 막지 않는다 | `override_settings(ALLAUTH_TRUSTED_PROXY_COUNT=1, ACCOUNT_RATE_LIMITS={"login_failed": 소량/m/ip})`, 같은 REMOTE_ADDR·XFF A로 실패 소진 → XFF B의 올바른 비밀번호 로그인 성공. 이미 Green → 뮤테이션: 테스트의 override 값을 0으로 임시 변경 | web(slow) | tests/auth/test_auth_rate_limit.py | Green |
| SEC-07 | 프록시 미설정이면 XFF를 바꿔도 같은 REMOTE_ADDR 한도를 공유한다(위조 헤더로 우회 불가) | override 값 0, XFF A로 소진 → XFF B도 차단. 이미 Green → 뮤테이션: override 값 1 | web(slow) | 같은 파일 | Green |
| SEC-10 | memo가 상한을 넘으면 기록이 만들어지지 않는다 | `MEMO_MAX_LENGTH + 1`자 memo 생성 POST → 400 `memo` 오류·0행(parametrize: 비공식_기록·컬렉션_항목). **F3a 주행** | web | tests/archive/test_personal_entries_api.py, test_collection_items_api.py | Green |
| SEC-10b | memo가 상한과 같으면 저장된다 | `MEMO_MAX_LENGTH`자 → 201. 이미 Green → 뮤테이션: `max_length=MEMO_MAX_LENGTH - 1` | web | tests/archive/test_collection_items_api.py | Green |
| SEC-08a | (삭제) 파서 단위 테스트 | 정정 11 — 파서를 만들지 않아 보호할 운영 코드가 없음, 파일 삭제 | unit | — | 삭제 |
| SEC-08e | (삭제) 파서 정상 파싱 | 정정 11 | unit | — | 삭제 |
| SEC-08b | 상한 초과 JSON으로 컬렉션 항목을 만들면 거부되고 저장되지 않는다(기존 보호 고정 핀) | `settings.DATA_UPLOAD_MAX_MEMORY_SIZE` 축소 → POST → 400·0행. 첫 실행에서 413 대신 400이 나와 정정 11 발견. 뮤테이션: 상한 `None` → Red | web | tests/archive/test_collection_items_api.py | Green |
| SEC-08c | 상한 초과 urlencoded PATCH는 거부되고 기록 불변(기존 보호 고정 핀) | 비공식 기록 PATCH(form-urlencoded) → 400·값 불변. 뮤테이션: 상한 `None` → Red | web | tests/archive/test_personal_entries_api.py | Green |
| SEC-09 | (삭제) multipart 업로드 | 정정 11 — 보호할 파서 변경이 없어 삭제 | web | — | 삭제 |
| SEC-04c | 승인 전 체크 전부 통과 핀에 스킴 항목 포함(사전 검토가 놓친 연쇄 핀, 사이클 1 실행에서 발견) | `TestEventDraftPreapprovalChecks::test_모든_체크를_통과하면_전부_통과로_표시된다` 기대 dict에 `official_url_scheme: True` | web | tests/staff/test_staff_draft_views.py | Green |
| SEC-11 | 수집이 실행 중일 때 다시 요청하면 안내만 하고 명령·감사 로그가 늘지 않는다 | 잠금 키 선점 → POST → 대시보드 302·info 문구·`call_command` 미호출·`draft_discover` 로그 0. **F4 주행** | web | tests/staff/test_staff_draft_discovery_run_view.py | Green |
| SEC-11b | 수집이 끝나면(정상·부분 실패·예상외 예외) 잠금이 풀려 다음 요청이 다시 실행된다 | parametrize 3건 → 두 번째 POST도 실행·로그 2건. 이미 Green → 뮤테이션: 잠금 해제 줄 임시 삭제 | web | 같은 파일 | Green |
| SEC-12 | CGNAT 대역 리터럴 IP는 안전하지 않은 URL | `TestLiteralIp`에 `"http://100.64.0.1/"`(id `CGNAT_공유_주소`). **F5 주행** | unit | tests/drafts/test_url_safety.py | Green |
| SEC-12b | 서버·러너 판정 문자 일치 | 서버만 고친 상태에서 기존 가드 Red → 러너 복제본 반영 후 Green | contract | tests/local_runner/test_url_safety_parity.py(기존) | Green |
| SEC-13 | known-urls 요청이 상한을 넘으면 400 | 러너 헤더 + URL `MAX_KNOWN_URLS_PER_REQUEST + 1`개 → 400. **F7 주행** | web | tests/drafts/test_runner_draft_api.py | Green |
| SEC-14 | known-urls 원소가 문자열이 아니면 400 | `{"urls": [123]}` → 400 | web | 같은 파일 | Green |
| SEC-15a | OS env에 없으면 `.env`의 `SECURE_COOKIES`를 읽는다 | 기존 :10-19 `.env` 관용구, `load_secure_cookies()` → True. **F9 주행** | contract | tests/core/test_settings_env.py | Green |
| SEC-15b | 설정 모듈 쿠키 보안 플래그가 `load_secure_cookies()` 결과와 일치 | 모듈 속성 일치 관용구 | contract | 같은 파일 | Green |

TDD 체크포인트(코치 판정 — 문자 그대로의 "결함 단위 선작성"은 한 번에 하나 원칙과 불일치, 완화안 채택): (1) 결함마다 **주행 테스트 1개**를 정식 Red(기대 이유)→최소 Green, (2) 같은 결함의 나머지 신규 테스트는 그 Green **이전에** 작성·Red 확인해 두어 부수 Green인지 판정 가능하게 한다, (3) 구현은 주행 테스트의 최소 변경이며 나머지를 겨냥해 설계하지 않는다, (4) 부수로 풀리지 않은 나머지는 다음 사이클로 최소 변경. 이미 Green 핀은 임시 뮤테이션으로 Red→복원(미커밋, 증거는 로그). pytest 실행은 오케스트레이터 단독. 결함 순서 F1→F2→F3a→F3b→F4→F5→F7→F9.

첫 사이클 계약(코치): SEC-04a `javascript_스킴` — Given 정상 kwargs에 `official_url="javascript:alert(document.cookie)"`, When `_validate_publish_fields`·`publish_field_checks` 호출, Then `PublishEventOfficialUrlSchemeError` + 실패 key `{"official_url_scheme"}`. 기대 Red = `ImportError`(예외 클래스 없음) → 예외 정의 후 재Red = `DID NOT RAISE`. 최소 Green = 예외 + 검증기 스킴·호스트 검사 + 체크 항목. 명령 `uv run pytest -q tests/events/test_publish_field_checks.py`.

## 검증
결함마다 표적 테스트 → 슬라이스(`tests/events tests/staff tests/auth tests/archive tests/core tests/drafts tests/local_runner` 중 해당) → 마지막에 `uv run pytest -q` 전체, `uv run python manage.py check`, `makemigrations --check --dry-run`, 프로덕션형 env `check --deploy`.

## 이연 (Deferred Refactoring Note 요약)
F6(트리거: 트랙 35 이연 항목 착수 시, 위치 `local_runner/page_fetch.py`) / F8(트리거: 오류 리포트 예산 소진 실측) / F11 CSP(트리거: 사용자 승인, 새 의존성) / 템플릿 선택 항목(트리거: 프론트 트랙) / 사용자별 저장 쿼터.

## 사후 기록 (2026-09-28, 오케스트레이터)
- **결과**: 브랜치 `fix/security-review-2026-09-27` main `2c0e3552` 위 커밋 10개 [실측 git log] — 결함별 fix 7(F7 `8315ab4c`, F2 `b49a5fec`, F3a `fa1aa6ef`, F4 `4eb3742b`, F5 `2cde14d7`, F9 `4bbc3ecc`, F1 `892feec3`) + 테스트 2(F3 본문 상한 핀 `15b0ef6e`, 이름 정밀화 `277f771b`) + 문서 1(`1836f5fa`). 코드 커밋 뒤 전체 회귀 3211 passed / 10 deselected / 실패 0 / 99.72초 [실측], 기준선 대비 신규 30건 [계산]. `check` 이상 없음, `makemigrations --check` 변화 없음, `check --deploy` W021만 [실측].
- **역할 판정**: SRR 사후 전부 Conforms(F3 블로커 철회, 소스 독립 재확인) / 코치 After-Green 전부 Green(이름 정밀도 1건 → `277f771b`) / QVL 최종 판정 = 조건부 완료 → 조건 2건 충족: 최종 HEAD `1836f5fa` 전체 회귀 3211 passed·실패 0 [실측], AC3 문구 정정(413 → 기존 400 보호, PUT 해당 없음 — `archive/views.py` `http_method_names` [실측 rg]). PR #388 CI 5개 통과 [실측 gh pr checks].
- **트랙 중 정정 기록**: (1) F3 본문 크기 결함 반박(정정 11) — 정본 문서·SRR 사전 판단 모두 DRF `request.py:358-360` 분기를 놓침, 테스트 첫 실행이 413 대신 400을 내 발견. (2) 연쇄 핀 SEC-04c를 사전 QVL·코치가 놓침 → 사이클 1 실행에서 발견. (3) DOR "SIGKILL로 finally 미실행" 주장은 부분 오류(SIGABRT 먼저) — 정정 8. (4) 오케스트레이터 Numbers 위반 2건을 커밋 전 자체 정정: 문서 초안의 뮤테이션 수 22 → 18 [실측 명세 합계], DRF 인용 줄 357-359 → 358-360(SRR 지적). (5) 오케스트레이터가 `prompt_plan.md`를 Bash 스크립트로 한 번 편집해 숫자 태그 훅을 우회 → 같은 줄을 Edit 도구로 다시 적용해 훅 검사를 통과시킴.
- **남은 사용자 액션(저장소 밖)**: 운영 DB 비-http(s)·호스트 없는 `official_url` 행 수 확인 = **배포 전 차단**(`docs/deploy-runbook.md` §3 항목 16), memo 최대 길이 확인(항목 17), Render env `TRUSTED_PROXY_COUNT` 값 확인과 스테이징 allauth 공유 버킷 재현 소멸 확인(항목 8), 배포 후 러너 재시작(F5 복제본 반영), PR 머지 승인.

---

