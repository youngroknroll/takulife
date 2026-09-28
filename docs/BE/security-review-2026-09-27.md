# 보안 검토 2026-09-27 — 발견 사항·변경 요소·흐름

**Current fact.** 2026-09-27, main `2c0e3552`(트랙 39 PR #385 머지 직후) 기준으로
저장소 전체를 CWE Top 25 관점에서 검토했다. 리뷰 전용 산출물이며 이 문서 작성
시점의 코드 변경은 0건이다. 검토 범위는 비테스트 Python 20,149줄
`[실측 git ls-files '*.py' | grep -v -E '^tests/|/migrations/' | xargs wc -l]`,
브라우저 JS 7,128줄 `[실측]`, 템플릿 90개 `[실측]`, `config/`·CI·Docker·
`local_runner/` 전부다. 방법은 ① CWE 패턴 `rg` 스캔, ② 신뢰 경계 12개의 소스
전수 판독, ③ Security & Resilience Reviewer 어댑터의 독립 검토와 대조(오케스트레이터가
모든 file:line을 재확인), ④ 실측 명령(§6). 라이브러리 인용 줄 번호는 설치본
기준이다: Django 5.2.17, DRF 3.17.2, django-allauth 65.18.0, django-axes 8.3.1
`[실측 uv run python -c]`.

**Decision.** 결함은 High 2·Medium 2·Low 7이며 Critical은 없다. High 2건과
Medium 2건은 수정 트랙 하나(PR 1개, 결함별 커밋)로 묶는 것을 권고하고, Low는 같은
유형이면 트랙 안에서 함께 처리하고 아니면 이연한다(§7). 수정 착수 시
`prompt_plan.md`에 계획서를 만들고 §2 끝의 Test List 초안을 가져간다. 이 문서는
리뷰 결과와 가드레일의 정본이고, 진행 상태는 `docs/backlog.md` J절이 든다.

**Update (2026-09-28, 트랙 40).** F1·F2·F3a·F4·F5·F7·F9는 반영 완료(브랜치
`fix/security-review-2026-09-27`, 결함별 커밋은 §8 표, 검증 증거는 §8 Evidence).
F1은 운영 DB에 이미 저장된 비-http(s) 값이 있으면 코드 배포만으로 닫히지 않으므로
`docs/deploy-runbook.md` §3 항목 16이 배포 전 차단 항목이다. F3b(DRF 본문 크기
미들웨어/파서 변경)는 구현 중 실측으로 **반박**돼 코드 변경을 취소하고
기존 보호를 고정하는 핀 테스트만 추가했다(§2 F3 정정 참조). F6·F8·F11·프론트
선택 항목은 이 트랙 범위 밖으로 이연, F10(MFA)은 기록된 사용자 보류다(§4).
상세 발견별 상태는 §8.

## 1. 요약

| # | 심각도 | CWE | STRIDE | 발견 | 위치 | 확신 |
|---|---|---|---|---|---|---|
| F1 | High | 79 | T·E | 스태프 이벤트 폼 `official_url` 스킴 미검증, 공개 상세 `href`에 `javascript:` 저장형 XSS | events/services.py:42-75 | 높음 `[실측]` |
| F2 | High | 799·400 | D | allauth `ip` 레이트리밋이 프로젝트 `TRUSTED_PROXY_COUNT`와 무관, 프록시 뒤에서 전 사용자 공유 버킷 | config/settings.py:491-496 | 코드 높음, 운영 미실측 |
| F3 | Medium | 770 | D | DRF JSON 본문이 Django 2.5MB 상한을 거치지 않고 memo에 길이 상한 없음 | archive/serializers.py:16-46, :212-280 | 높음 `[실측 소스]` — (b) 본문 상한 부분은 반박, (a) memo 상한만 유효. §2 F3 정정 참조 |
| F4 | Medium | 400 | D | 「지금 수집」 동기 실행에 뮤텍스 없음, gunicorn 워커 3개 점유 | staff/views/__init__.py:290-336 | 높음 |
| F5 | Low | 918 | I | SSRF 판정이 100.64.0.0/10(CGNAT) 통과 | drafts/url_safety.py:14-22, local_runner/url_safety.py:18-26 | 높음 `[실측]` |
| F6 | Low | 367·400 | I·D | 러너 일반 웹 읽기에 IP 핀닝 없음, 본문 전량 수신 뒤 크기 검사 | local_runner/page_fetch.py:213-231 | 높음 |
| F7 | Low | 20·770 | D | 러너 known-urls 목록 길이·타입 무검사 | drafts/runner_views.py:250-265 | 높음 |
| F8 | Low | 770 | D | 오류 리포트 전역 단일 버킷 소진 시 관측 공백 | core/client_error_views.py:89-96 | 높음 |
| F9 | Low | 16 | T | `SECURE_COOKIES`만 `os.environ` 직접 읽기 | config/settings.py:523 | 높음 |
| F10 | Low | 308 | S | 스태프·슈퍼유저 MFA 부재, `/admin/` 노출 | config/urls.py:181, config/settings.py:287-311 | 높음 |
| F11 | Low | 693 | T | CSP 헤더 없음 | config/settings.py 전체, templates/base.html:8-15, :20-36, :81-86 | 높음 |

STRIDE 약어: S 위장, T 변조, R 부인, I 정보 노출, D 서비스 거부, E 권한 상승.

## 2. 발견 상세와 변경 요소

### F1 [High] 스태프 `official_url` 스킴 미검증, 공개 상세 저장형 XSS

**현재 흐름**

```text
스태프 이벤트 생성/수정 폼 POST  (is_staff 계정이면 충분, staff/permissions.py:9-25)
  -> staff/views/events.py:383-387  _event_edit_form_values_from_post: POST 원문을 그대로 dict로
  -> staff/views/events.py:429 / :505  create_published_event / update_published_event(official_url=원문)
  -> events/services.py:42-75  _validate_publish_fields
        검사: 공백 제거, 비어 있음, 제목=URL, 중복, 기간, 카테고리, 지역   <- 스킴 검사 없음
  -> events/services.py:174 Event.objects.create(...)  /  :237 event.save(update_fields=...)
        URLField의 URLValidator는 full_clean()이 없으면 실행되지 않는다
  -> DB에 "javascript:alert(document.cookie)" 저장
  -> templates/core/events/detail.html:86, :186  <a href="{{ event.official_url }}" target="_blank" rel="noopener">
        autoescape는 <, >, ", & 만 바꾸며 URL 스킴은 그대로 둔다
  -> 공개 방문자가 "공식 페이지로" 클릭 -> takulife 오리진에서 스크립트 실행
```

같은 검증기를 `republish_event`(events/services.py:278-286), 스태프 인라인
재게시(staff/views/events_actions.py:56), 초안 승인 `approve_draft`
(drafts/services.py:363-372)도 쓴다. 초안의 `source_url`은 생성 경로 3곳이 이미
`http(s)`로 제한한다(drafts/serializers.py:95-98, drafts/agent_drafts.py:208-213,
web/promotion.py:69-72). 스태프 수동 생성·수정 경로만 제한이 없다.

**재현** `[실측 2026-09-27, DB 쓰기 없음]`

```text
uv run python manage.py shell -c "from events.services import _validate_publish_fields; from events.models import Event; print(_validate_publish_fields(title='테스트', official_url='javascript:alert(document.cookie)', start_date=None, end_date=None, category='', region='', existing_queryset=Event.objects.none()))"
# 출력: ('테스트', 'javascript:alert(document.cookie)')
```

**왜 문제인가(이유).** `official_url`은 사람이 읽는 텍스트가 아니라 브라우저가
실행 컨텍스트를 정하는 `href` 값이다. 문자 이스케이프는 태그 탈출만 막고,
`javascript:`·`data:` 스킴은 정상 문자열이라 통과한다. 검증기가 "값이 있는가"만
묻고 "어떤 종류의 값인가"를 묻지 않아 생긴 결함이다. 전제는 `is_staff` 계정
1개이고 슈퍼유저가 아니어도 된다. `CSRF_COOKIE_HTTPONLY = False`
(config/settings.py:527, JS가 읽어야 해서 의도된 값)라 스크립트가 `csrftoken`을
읽어 피해자 권한으로 `/api/*`·`/staff/*` 쓰기를 대행할 수 있고, 슈퍼유저가
클릭하면 계정 권한 부여(`/staff/accounts/<pk>/staff/`)까지 이어지는 권한 상승
경로다.

**변경 요소**

| 파일 | 변경 | 이유 |
|---|---|---|
| events/services.py | `ALLOWED_OFFICIAL_URL_SCHEMES = frozenset({"http", "https"})`, `PublishEventOfficialUrlSchemeError(PublishEventError)` 추가. `_validate_publish_fields`에서 비어 있음 검사 직후 `urlsplit(normalized_official_url).scheme`가 허용목록 밖이면 raise | 생성·수정·재게시·승인 4경로가 이 함수 하나를 지나므로 한 곳에 두면 전부 덮인다 |
| events/services.py `publish_field_checks` | 같은 순서 위치에 `{"key": "official_url_scheme", "label": "공식 URL은 http 또는 https여야 합니다", "passed": ...}` 항목 추가 | 승인 전 체크 dry-run은 검증기와 순서·규칙이 같아야 한다(트랙 38 PR #380 계약) |
| staff/views/events.py `_publish_event_field_errors`, `REPUBLISH_ERROR_MESSAGES` | 새 예외를 `official_url` 필드 오류 문구로 매핑(부모 `PublishEventError` 앞에 둔다) | 스태프가 400 화면에서 원인을 바로 본다 |
| staff/views/drafts.py (선택) | `approve_draft`의 `DraftPublicationError` 503 매핑 앞에 스킴 오류 매핑 | 초안 경로는 이미 스킴이 제한돼 도달하지 않는다. 일관성용 |
| templates/core/events/detail.html:86, :186 (선택) | `rel="noopener noreferrer"` | 외부 링크로 리퍼러가 새지 않게 하는 하드닝. 프론트 변경이라 이중 검토 대상 |

**정정 (2026-09-28, 구현 반영)**: 규칙을 스킴 허용목록만이 아니라 "스킴 ∈
{http, https} **그리고** netloc(호스트) 존재"로 강화했다. `https:javascript:alert(1)`·
`http://`는 `urlsplit`이 스킴은 허용값으로 인식하지만 netloc이 비어 있어
스킴만 검사하면 통과했을 값이다 `[실측 urlsplit]`.

주의: 스킴이 없는 값(`www.example.com`)도 거부된다. 현재는 이 값이 저장되어
상대 경로 `/events/www.example.com`로 깨진 링크가 된다. 착수 전에
`Event.objects.exclude(official_url__startswith="http")` 건수를 운영 DB에서 재고,
있으면 스태프 수정 화면에서 고친 뒤 배포한다(재게시 경로가 거부하기 때문).
**정정 (2026-09-28, SRR 사후 검증)**: 접두어 검사는 호스트 없는 `http://`를 놓친다.
`docs/deploy-runbook.md` §3 항목 16의 `urlsplit` 기준 명령(스킴 http(s) + 호스트)을 쓴다.
또 검증기는 생성·수정·재게시 시점에만 걸리고 이미 게시된 행을 소급 정리하지 않으므로,
운영 DB에 이런 행이 있으면 코드 배포만으로 F1이 닫히지 않는다 — **배포 전 차단 항목**이다.

**변경 후 흐름**

```text
POST official_url="javascript:..." -> _validate_publish_fields -> PublishEventOfficialUrlSchemeError
  -> staff 폼: 400 + field_errors["official_url"]   /  인라인 재게시 JSON: 400 detail
  -> DB 미저장 -> 공개 페이지 도달 불가
```

**목적·가드레일.** 공식 URL 스킴 허용목록의 단일 출처는 `_validate_publish_fields`다.
뷰·폼·템플릿에 중복 구현하지 않는다. `publish_field_checks`는 항상 같은 항목·같은
순서를 유지한다.

**수용 기준.** `javascript:`·`data:`·`vbscript:`·스킴 없는 값은 생성·수정·재게시
모두 거부되고 DB에 남지 않는다. `http://`·`https://`는 통과한다. 승인 전 체크
목록에 스킴 항목이 함께 표시된다.

### F2 [High] allauth `ip` 레이트리밋이 프록시 뒤에서 전 사용자 공유 버킷

**현재 흐름**

```text
프로덕션: 클라이언트 -> PaaS 리버스 프록시(X-Forwarded-For 추가) -> gunicorn -> Django
  REMOTE_ADDR = 프록시 IP  (모든 사용자 동일)

allauth 레이트리밋 (config/settings.py:491-496)
  signup "5/m/ip,30/h/ip" · login_failed "10/m/ip,5/300s/key" · reset_password "20/m/ip,5/m/key"
  -> allauth/core/internal/ratelimit.py:121-122  rate.per == "ip" -> get_ip(request)
  -> :113  get_adapter().get_client_ip(request)
  -> allauth/account/adapter.py:842-848  (accounts/adapters.py는 이 메서드를 override하지 않는다)
  -> allauth/core/internal/httpkit.py:212-220  get_client_ip
        TRUSTED_CLIENT_IP_HEADER(없음) -> get_client_ip_from_xff: ALLAUTH_TRUSTED_PROXY_COUNT 기본 0 -> None
        -> REMOTE_ADDR = 프록시 IP
  -> 버킷 키 ("ip", 프록시 IP): 사이트 전체가 버킷 하나

프로젝트 TRUSTED_PROXY_COUNT (config/settings.py:519-520, core/ip.py:18-47)
  -> axes(AXES_CLIENT_IP_CALLABLE)와 StaffActionLog.ip_address에만 배선
  -> allauth는 이 값을 읽지 않는다 (설정 접두어 ALLAUTH_, allauth/app_settings.py:59-66, :97)
```

저장소에 `ALLAUTH_TRUSTED_PROXY_COUNT`·`TRUSTED_CLIENT_IP_HEADER` 참조 0건
`[실측 rg -n 'ALLAUTH_TRUSTED_PROXY_COUNT|TRUSTED_CLIENT_IP_HEADER|ALLAUTH_' config/ .env.example docs/ tests/]`.
기존 잠금 테스트 tests/auth/test_auth_lockout.py:70-106은
`ACCOUNT_RATE_LIMITS={"login_failed": "1000/m/key"}`로 `ip` 범위를 꺼 둔 채 axes만
검증하므로, 이 공유 버킷은 테스트 스위트가 한 번도 보지 않았다.

**왜 문제인가(이유).** 런북(`docs/deploy-runbook.md` §1 env 표,
`docs/operations-runbook.md` §4)은 PaaS 배포에서 앱이 프록시 뒤에 있다고 전제하고
`TRUSTED_PROXY_COUNT`를 필수로 둔다. 같은 전제에서 allauth의 `ip` 범위는 프록시
IP로 묶여 다음이 된다.

- 익명 공격자가 분당 잘못된 로그인 10회를 유지하면 모든 사용자의 로그인 POST가
  429(`templates/429.html`)다. 비용은 분당 요청 10건이다.
- 가입은 사이트 전체 30건/시간, 비밀번호 재설정 메일 요청은 20건/분으로 묶인다.
  정상 사용자끼리 서로의 한도를 소진한다.
- `TRUSTED_PROXY_COUNT`가 Render env에 없다면 axes(config/settings.py:504-506,
  실패 5회·쿨다운 1시간)도 프록시 IP를 잠가 1시간 전체 로그인 차단이 된다. 이
  env 값은 저장소 밖이라 미검증이다(§5).

Render에서 `REMOTE_ADDR`이 프록시 IP인지는 실측하지 않았다. 확신은 코드 경로에
대해서만 높다.

**변경 요소**

| 파일 | 변경 | 이유 |
|---|---|---|
| config/settings.py | `TRUSTED_PROXY_COUNT = load_trusted_proxy_count()` 바로 아래에 `ALLAUTH_TRUSTED_PROXY_COUNT = TRUSTED_PROXY_COUNT or 0` 추가. 한국어 주석: allauth 레이트리밋 ip 버킷도 같은 env로 프록시를 신뢰한다 | env 하나로 axes·감사 로그·allauth가 같은 클라이언트 IP를 본다. allauth 자체 경로를 쓰므로 `RATE_LIMIT_IPV6_PREFIX` 처리도 그대로 살아 있다 |
| .env.example, docs/deploy-runbook.md §1 표, docs/operations-runbook.md §4 | `TRUSTED_PROXY_COUNT` 설명에 "allauth 레이트리밋 ip 범위도 이 값을 따른다"를 추가 | 운영자가 값 하나로 세 소비자를 통제한다는 사실을 알아야 한다 |
| docs/deploy-runbook.md §3 체크리스트 | 스테이징 확인 절차 추가: IP A에서 잘못된 로그인 10회 뒤 IP B의 첫 로그인이 429가 아니어야 한다 | 프로덕션 프록시 홉 수가 맞는지 실측으로 닫는다 |

대안으로 `accounts/adapters.py`에 `get_client_ip`를 override해 `core.ip.get_client_ip`로
위임할 수 있다. 채택하지 않는 이유는 allauth의 헤더 파싱·IPv6 접두 처리를 버리게
되고, 정책이 두 구현(`core/ip.py`, allauth)으로 갈라져 드리프트하기 때문이다.

**정정 (2026-09-28, 구현 반영)**: 같은 `TRUSTED_PROXY_COUNT` 과대설정에서
실패 양상이 비대칭이다 — axes·`StaffActionLog.ip_address`(`core/ip.py`)는
조용히 `REMOTE_ADDR`로 폴백하지만, allauth(`httpkit.py:200-205`)는
`X-Forwarded-For`가 있고 설정된 홉 수보다 짧으면 500(`ImproperlyConfigured`)을
던진다. 권장값 1에서는 `split(",")`가 최소 1개 원소를 돌려줘 이 500이
도달 불가능하고, 2 이상에서만 발생한다 `[코드]`.

**변경 후 흐름**

```text
TRUSTED_PROXY_COUNT=1 -> ALLAUTH_TRUSTED_PROXY_COUNT=1
  -> httpkit.get_client_ip_from_xff: X-Forwarded-For 오른쪽에서 1번째 = 실제 클라이언트 IP
  -> 버킷 키 ("ip", 클라이언트 IP): 사용자별 분리
미설정(로컬 개발) -> 0 -> REMOTE_ADDR  (현재 동작 그대로)
```

주의: allauth는 `X-Forwarded-For` 홉 수가 설정값보다 적으면 `ImproperlyConfigured`를
던진다(httpkit.py:201-205). 헤더가 아예 없으면 `REMOTE_ADDR`로 폴백한다. 값을
실제 홉 수보다 크게 잡으면 요청이 500이 되므로, 과대설정 금지 원칙
(operations-runbook §4)이 allauth에도 그대로 적용된다.

**목적·가드레일.** 클라이언트 IP 해석의 단일 env는 `TRUSTED_PROXY_COUNT`다. 소비자가
셋(axes, StaffActionLog, allauth)이며 새 소비자(IP 기반 스로틀 등)를 더할 때도 이
env를 따른다. 특정 소비자만 별도 설정을 두지 않는다.

**수용 기준.** `TRUSTED_PROXY_COUNT=1`에서 같은 `REMOTE_ADDR`·다른 `X-Forwarded-For`의
두 클라이언트는 `login_failed`·`signup` 버킷이 분리된다. 미설정에서는 기존
동작(REMOTE_ADDR)이 유지된다. 설정 계약 테스트가 두 값의 일치를 고정한다.

### F3 [Medium] DRF JSON 본문 크기 무제한, memo 길이 상한 없음

**현재 흐름**

```text
인증 사용자 POST/PATCH  /api/personal-entries/ , /api/collection-items/<id>/   (Content-Type: application/json)
  -> DRF Request._load_stream (rest_framework/request.py:297-314)
        content_length > 0 이고 아직 읽지 않았으면 self._stream = self._request   (HttpRequest 자체)
  -> JSONParser.parse -> stream.read() -> django/http/request.py:488-493 HttpRequest.read()
        DATA_UPLOAD_MAX_MEMORY_SIZE 검사 없음. 그 검사는 HttpRequest.body(:398-425)와 multipart 파서에만 있다
  -> 본문 전체가 워커 메모리에 올라가고 json.loads
  -> PersonalEntrySerializer.memo / CollectionItemSerializer.memo: TextField 자동 매핑, max_length 없음
        (archive/models.py:164, :303 · archive/serializers.py에 memo max_length 0건 [실측 rg])
  -> DB 저장
```

Django 기본 `DATA_UPLOAD_MAX_MEMORY_SIZE`는 2,621,440바이트
`[코드 django.conf.global_settings]`이며 이 프로젝트는 재정의하지 않는다.
`Transfer-Encoding: chunked`(Content-Length 없음)는 DRF가 `content_length == 0`으로
보아 본문을 아예 파싱하지 않으므로 이 경로에 해당하지 않는다. `/staff/` 아래
DRF 뷰(일괄 승인·반려·비공개, 목표 게시 상태)도 같은 파서를 쓰므로 스태프 한정으로
같은 노출이 있다.

**왜 문제인가(이유).** 이 저장소의 쓰기 API는 스로틀(분당 30회 등)로 횟수만
제한하고 요청 하나의 크기는 제한하지 않는다. 실제 상한은 PaaS 프록시의 본문
제한만 남는데 그 값은 확인되지 않았다(§5). 계정 1개로 워커 메모리(gunicorn sync
워커 3개, docker/entrypoint.sh:15 기본값) 또는 DB 용량을 소진할 수 있다.

- 2.5MB를 상한으로 가정해도 memo 쓰기 3경로 합 90회/분 × 2.5MB = 225MB/분 =
  13.2GB/시간 `[계산]`이다.
- 프록시 제한이 없으면 요청 1건으로 워커 하나의 메모리를 소진한다.
- 사진은 5MB × 30회/분 = 8.8GB/시간 `[계산]`으로 저장소 비용 축이다(사용자별 쿼터
  부재, 하드닝 항목).

전제는 인증 사용자 1명이다. 가입에는 이메일 인증이 필수다.

**변경 요소**

| 파일 | 변경 | 이유 |
|---|---|---|
| archive/models.py | `MEMO_MAX_LENGTH = 2000` 상수(도메인이 규칙을 소유) | 시리얼라이저·템플릿이 같은 수를 가져다 쓴다 |
| archive/serializers.py | `PersonalEntrySerializer`·`CollectionItemSerializer`에 `memo = serializers.CharField(required=False, allow_blank=True, max_length=MEMO_MAX_LENGTH)` 명시. Update 시리얼라이저는 상속으로 함께 적용 | TextField 자동 매핑은 상한이 없다. 경계 검증은 시리얼라이저 소유(AGENTS.md Domain Boundary) |
| core/middleware.py (신설) | `JsonBodySizeLimitMiddleware`: `CONTENT_TYPE`이 `application/json`으로 시작하고 `CONTENT_LENGTH` 정수가 `settings.DATA_UPLOAD_MAX_MEMORY_SIZE`를 넘으면 `HttpResponse(status=413)`. 경로 무관(JSON 본문 전체). multipart·urlencoded는 제외(Django 파서가 이미 비파일 필드를 제한하고 파일은 `validate_uploaded_image`가 5MB 상한) | 필드 상한만으로는 본문을 읽어 들이는 메모리 소모를 막지 못한다. Content-Length 검사는 읽기 전에 끝난다 |
| config/settings.py MIDDLEWARE | `CommonMiddleware` 뒤에 등록 | 인증·CSRF보다 앞에서 거절해 비용을 최소화 |
| templates/core/archive/personal_create.html:109, personal_edit.html:110, collection_create.html:55 근처 textarea (선택) | `maxlength` 속성 | 사용자 안내. 프론트 변경이라 이중 검토 대상, 트랙 분리 가능 |

**변경 후 흐름**

```text
Content-Length > 2,621,440 (JSON)          -> 413, 본문 읽지 않음
Content-Length 이내, memo 2,001자 이상      -> 400 {"memo": [...]}
Content-Length 이내, memo 2,000자 이하      -> 기존과 동일
multipart(사진)                            -> 미들웨어 통과, 기존 5MB 검증 그대로
```

**목적·가드레일.** JSON 본문 상한의 기준은 Django `DATA_UPLOAD_MAX_MEMORY_SIZE`
하나다. 별도 숫자를 두지 않는다. 사용자별 저장 총량·일일 쿼터는 이 트랙에 넣지
않고 하드닝 항목으로 남긴다(§4).

**수용 기준.** 2,621,441바이트 JSON POST는 413이고 행이 생기지 않는다. memo
2,001자는 400, 2,000자는 201. 사진 업로드(multipart 5MB 이하)는 계속 201.

**정정 (2026-09-28 실측, 트랙 40 구현 중).** 위 서술은 측정 전 기록이다.
(b) "DRF JSON 본문이 Django 상한을 거치지 않는다"는 **반박됐다**: DRF 3.17.2
`Request._parse`는 `JSONParser`·`FormParser`에 `io.BytesIO(self.body)`를
넘기고 `[코드 rest_framework/request.py:358-360]`, 이 `HttpRequest.body`
접근이 `_check_data_too_big`을 거쳐 `DATA_UPLOAD_MAX_MEMORY_SIZE`를 이미
강제한다. 위 서술은 `_load_stream`(:297-314)만 읽고 이 분기를 놓친 것이다.
실측: 기본 상한에서 2,700,000바이트 JSON POST·폼 PATCH·JSON PATCH 모두
400이고 DB 불변, 상한을 1,024바이트로 낮춘 경우도 400 `[실측 2026-09-28]`.
그래서 미들웨어·파서 도입은 **하지 않았고**, 이 기존 보호를 고정하는 핀
테스트만 추가했다(SEC-08b·08c, DRF 업그레이드로 이 분기가 사라지면 잡는다).
(a) memo 길이 상한 부분은 그대로 유효하고 수정 완료(`archive/models.py`
`MEMO_MAX_LENGTH = 2000`, 커밋 `fa1aa6ef`) — 상한 이내 본문으로도 memo에
2.5MB 문자열을 저장할 수 있었던 결함은 이 상한으로 막혔다.

### F4 [Medium] 「지금 수집」 동기 실행에 뮤텍스 없음

**현재 흐름**

```text
스태프 POST /staff/draft-discovery/run/  (staff/views/__init__.py:290-336)
  -> DRAFT_DISCOVERY_ENABLED · 활성 소스 확인
  -> :321 call_command("discover_drafts", stdout=out)   <- 요청 스레드에서 동기 실행, 락 없음
        소스마다 robots 확인·fetch·1초 대기(discover_drafts.py:59, :91-94) + 후보마다 Crawl-delay 대기(:206)
  -> 수십 초 ~ 분 단위로 gunicorn 워커 1개 점유  (기본 3개, docker/entrypoint.sh:15)
동시에 POST 3회 -> 워커 3개 전부 점유 -> 공개 방문자 요청 대기
```

**왜 문제인가(이유).** 전제는 `is_staff` 계정과 `DRAFT_DISCOVERY_ENABLED=true`
(프로덕션 개통 2026-09-20)다. 사고 시나리오는 두 가지다. 스태프 본인이 응답을
기다리다 다시 클릭하는 것과, 탈취된 스태프 세션이 반복 POST하는 것. 어느 쪽이든
결과는 사이트 전체 응답 지연이다. 같은 축의 워커 수준 방어(gunicorn `--timeout`)는
백로그 G2로 예약돼 있고, 이 항목은 애플리케이션 수준에서 중복 실행을 막는 것이다.

**변경 요소**

| 파일 | 변경 | 이유 |
|---|---|---|
| staff/views/__init__.py | 상수 `DISCOVERY_RUN_LOCK_KEY = "staff-draft-discovery-run-lock"`, `DISCOVERY_RUN_LOCK_TIMEOUT_SECONDS = 600`. `call_command` 앞에서 `cache.add(key, 1, timeout)`가 False면 `messages.info("이미 수집이 실행 중입니다. 끝나면 다시 시도하세요.")` 후 대시보드로 리다이렉트(감사 로그 없음, 기존 무동작 관행과 동일). 실행 경로는 `try/finally`에서 `cache.delete(key)` | `cache.add`는 키가 없을 때만 성공하는 원자적 연산이라 DatabaseCache(워커·재배포 공유)에서 뮤텍스로 쓸 수 있다. timeout은 프로세스가 죽었을 때 잠금이 영구히 남지 않게 하는 안전장치다 |
| staff/views/discovery.py:26-50 (참고, 변경 없음) | 같은 캐시 기반 제한 패턴의 선례 | 새 패턴을 만들지 않는다 |

**정정 (2026-09-28, 구현 반영)**: 잠금 해제 보장 범위는 정상 종료·파이썬
예외·gunicorn SIGABRT 종료다. 기본 30초 타임아웃 초과 시 아비터는 먼저
SIGABRT를 보내고(`gunicorn/arbiter.py:590-593`) 워커는 `sys.exit(1)`로
반응해(`gunicorn/workers/base.py:195-198`) `SystemExit`가 `finally`를
통과하므로 잠금이 보통 풀린다. SIGKILL(다음 아비터 점검까지 워커가 남을
때만, `arbiter.py:594-595`) 뒤에는 TTL 600초까지 잠금이 남는다. 만료 행이
남은 뒤의 `add`는 UPDATE 분기라 동시 획득 경쟁이 이론상 남지만, 이는
도입 전과 같은 결과라 신규 위험이 아니다.

**변경 후 흐름**

```text
POST #1            -> cache.add 성공 -> 명령 실행 -> finally: 감사 로그 + cache.delete
POST #2 (실행 중)  -> cache.add 실패 -> info 메시지 + 리다이렉트, 명령 미실행, 감사 로그 없음
```

**목적·가드레일.** 요청 스레드에서 돌리는 장시간 동기 작업은 캐시 뮤텍스로 단일
실행을 보장한다. G2(gunicorn `--timeout`)는 이 뮤텍스의 대체가 아니라 워커 수준
보강이다.

**수용 기준.** 잠금이 잡힌 상태의 두 번째 POST는 `StaffActionLog`에
`draft_discover` 행을 추가하지 않고 안내 메시지와 302를 돌려준다. 정상 실행 뒤에는
잠금이 풀려 다음 POST가 다시 실행된다.

### F5~F11 [Low] 변경 요소 요약

| # | 현재 | 변경 요소 | 이유·목적 |
|---|---|---|---|
| F5 CGNAT | `_is_unsafe_ip`가 `is_private`·`is_loopback`·`is_link_local`·`is_multicast`·`is_unspecified`·`is_reserved` 열거. `100.64.0.1`은 `is_private=False`·`is_global=False`인데 안전 판정 `[실측 Python 3.13.5]` | drafts/url_safety.py:14-22와 local_runner/url_safety.py:18-26 둘 다 `or not value.is_global` 추가. tests/drafts/test_url_safety.py와 러너 테스트에 `100.64.0.1` 거부 케이스 | 열거 대신 "전역 라우팅 가능한 주소만 허용"으로 기준을 뒤집어 누락 대역을 없앤다. `64:ff9b::7f00:1`은 이미 `is_reserved`로 차단됨 `[실측]` |
| F6 러너 읽기 | `_fetch_general_web`(local_runner/page_fetch.py:213-231)은 검증 뒤 `httpx.get(url)`로 DNS를 다시 풀고, `response.text` 전량 수신 뒤 크기 검사. 인스타 경로(:88-94)는 상한 없음 | 서버 `drafts/fetching.py:83-101`과 같은 IP 핀닝(연결 URL 호스트 치환 + Host 헤더 + sni_hostname), `httpx.stream`으로 1,000,000바이트 초과 시 중단. 인스타 경로에도 같은 상한 | 서버와 러너의 fetch 안전 규칙 비대칭 제거. 트랙 35 이연 항목(캡션 경로 응답 크기 상한·DNS 리바인딩)과 같은 축이라 그 이연을 닫는 작업으로 처리 |
| F7 러너 known-urls | drafts/runner_views.py:253-259가 `urls`의 list 여부만 검사 | 길이 상한(예 500)과 원소 `str` 검사, 위반 시 400 | 토큰 보유자 한정이지만 거대한 `IN` 절과 비문자열 500을 막는 방어 심도. **정정(2026-09-28 구현 반영)**: 상한 500 대신 전용 상수 `MAX_KNOWN_URLS_PER_REQUEST = 20`(러너 전송 상한 `EXPLORATION_MAX_EVENTS`와 같은 값)을 신설 — `MAX_EVENTS_PER_RUN`(실행당 영속 드래프트 상한)과 의미가 달라 재사용하지 않았다 |
| F8 오류 리포트 버킷 | `GlobalClientErrorThrottle`(core/client_error_views.py:89-96)가 `ident="global"` 단일 버킷 120건/시간 | 지문별 분당 상한을 추가(예 같은 fingerprint 10건/분). 전역 상한은 유지 | 위조 Origin 1곳이 예산을 독점해 1시간 관측 공백을 만드는 것을 줄인다. 기록된 F7(Origin 위조 가능)과 인접 |
| F9 SECURE_COOKIES | config/settings.py:523만 `os.environ.get` 직접 사용, 다른 플래그는 `_get_env`(:12-24) | `_get_env("SECURE_COOKIES", "")`로 통일 | `.env` 파일 값이 조용히 무시되는 운영 함정 제거. Render는 OS env를 쓰므로 현 배포 영향 없음 |
| F10 MFA | `allauth.mfa` 미설치(INSTALLED_APPS config/settings.py:287-311), `/admin/` 노출(config/urls.py:181). extras `django-allauth[mfa]`는 pyproject에 이미 있음 | 별도 트랙: `allauth.mfa` 앱·URL 등록, 스태프·슈퍼유저 필수화 여부는 제품 결정 | F1 같은 스태프 전제 결함의 전제(계정 탈취)를 어렵게 한다. 기록된 보류(슈퍼유저 step-up)와는 별개 |
| F11 CSP | CSP 설정 0건 `[실측 rg]`, base.html 인라인 스크립트 3개(:8-15, :20-36, :81-86) | 별도 트랙: nonce 기반 `Content-Security-Policy` 미들웨어(새 의존성 도입은 승인 필요) | XSS 피해 반경 축소. 인라인 스크립트가 있어 nonce 없이는 도입 불가 |

### Test List 초안 (수정 트랙 착수 시 prompt_plan.md로 이관)

| Scenario ID | 업무 행동 | 경계 | 테스트 이름(한국어) | 상태 |
|---|---|---|---|---|
| SEC-01 | 스태프가 `javascript:` 공식 URL로 이벤트를 만들면 거부된다 | web | `스태프가_javascript_스킴_공식URL로_이벤트를_생성하면_필드_오류가_되고_저장되지_않는다` | Pending |
| SEC-02 | 스태프가 기존 이벤트 공식 URL을 `data:`로 수정하면 거부된다 | web | `스태프가_공식URL을_data_스킴으로_수정하면_필드_오류가_되고_기존값이_유지된다` | Pending |
| SEC-03 | 스킴 없는 공식 URL을 가진 비공개 이벤트는 재게시가 거부된다 | domain | `스킴_없는_공식URL_이벤트를_재게시하면_스킴_오류가_된다` | Pending |
| SEC-04 | 승인 전 체크 목록에 스킴 항목이 검증기와 같은 순서로 들어 있다 | contract | `승인전_체크는_검증기와_같은_순서로_공식URL_스킴_항목을_포함한다` | Pending |
| SEC-05 | `TRUSTED_PROXY_COUNT=1`이면 allauth 프록시 신뢰 홉도 1이다 | contract | `TRUSTED_PROXY_COUNT가_설정되면_allauth_신뢰_프록시_홉_수도_같은_값이_된다` | Pending |
| SEC-06 | 신뢰 프록시 뒤에서 다른 클라이언트 IP는 로그인 실패 한도를 공유하지 않는다 | web | `신뢰된_프록시_뒤에서_한_클라이언트의_로그인_실패가_다른_클라이언트_IP의_로그인을_막지_않는다` | Pending |
| SEC-07 | 프록시 설정이 없으면 기존처럼 REMOTE_ADDR 기준으로 제한한다 | web | `프록시_설정이_없으면_REMOTE_ADDR_기준으로_로그인_실패_한도가_적용된다` | Pending |
| SEC-08 | 상한을 넘는 JSON 본문은 읽기 전에 413으로 거절된다 | web | `상한을_넘는_JSON_본문으로_컬렉션_항목을_만들면_413이_되고_행이_생기지_않는다` | Pending |
| SEC-09 | multipart 사진 업로드는 본문 상한 미들웨어의 영향을 받지 않는다 | web | `상한_이내_사진_multipart_업로드는_기존처럼_저장된다` | Pending |
| SEC-10 | memo가 2,000자를 넘으면 400이다 | web | `memo가_최대_길이를_넘는_비공식_기록_생성은_400이_된다` | Pending |
| SEC-11 | 수집 실행 중 두 번째 요청은 명령을 돌리지 않는다 | web | `수집이_실행_중일_때_다시_요청하면_안내만_하고_감사_로그가_늘지_않는다` | Pending |
| SEC-12 | CGNAT 대역 IP로 풀리는 호스트는 안전하지 않은 URL로 거부된다 | unit | `CGNAT_대역으로_해석되는_호스트는_안전하지_않은_URL로_거부된다` | Pending |

## 3. 확인됨(완화 있음)

재검토 없이 신뢰할 수 있는 경계와 그 근거다. 새 경로를 추가할 때 이 목록의 규칙을
그대로 따른다.

- JSON-LD: web/views/events.py:530-537 `_json_ld_script`가 `<`·`>`·`&`를 `<`
  등으로 바꿔 `</script>` 탈출을 막는다. 홈·상세 `|safe` 2곳이 이 함수만 거친다.
- archive IDOR: 뷰 `get_queryset`이 `user=request.user`로 한정하고
  (archive/views.py:155, :198, :246, :297, :375, :435, :500, :693), FK 입력
  `personal_entry`·`visit_record`는 시리얼라이저 `__init__`에서 요청자 소유로
  스코프(archive/serializers.py:70-76, :165-173, :259-273), `event`는 게시된 것만
  (`Event.objects.published()`).
- 공식 제보: web/promotion.py:69-72가 `validate_fetch_url`로 `http(s)`·localhost·
  사설 IP 리터럴을 거른다.
- SSRF: drafts/fetching.py:74-117 최초 검증, 매 리다이렉트 홉 재검증, 검증 IP로
  직접 연결(IP 핀닝) + Host 헤더 + sni_hostname. 정본 `docs/BE/draft-fetching-ssrf.md`.
- 업로드: events/image_validation.py 5MB 상한, 확장자와 Pillow 실디코딩 포맷
  allowlist, 축당 10,000px, 총 40,000,000픽셀, EXIF 제거 재인코딩,
  archive/models.py:13-16 UUID 파일명. 저장소 `default_acl=None`·
  `querystring_auth=True`(config/settings.py:211-230).
- CSRF: `csrf_exempt` 운영 코드 0건 `[실측 rg]`, DRF는 `SessionAuthentication`만
  (config/settings.py:582-584), 폼은 전부 `csrf_token` 또는 JS `X-CSRFToken`
  (static/js/shared/api.js:34-46).
- 러너 API: 토큰 `constant_time_compare`, 빈 토큰 fail-closed, 스로틀 키 해시
  (drafts/runner_views.py:38-60). 임대 토큰도 상수 시간 비교
  (drafts/discovery_runs.py:268-276).
- 오류 리포트: 정제(제어문자·시크릿·이메일·URL 쿼리, core/error_groups.py:86-95),
  대시보드는 `message_sample`을 렌더하지 않고 나머지는 autoescape
  (templates/staff/dashboard.html:359-375).
- 설정 가드: `DEBUG=false`에서 `SECRET_KEY` 필수, `ALLOWED_HOSTS` 설정 시
  `DEBUG=true` 거부, `DATABASE_URL` 스킴 제한, 미디어 스토리지 5종 all-or-nothing,
  테스트 설정 경계 가드.
- 의존성: `pip-audit 2.9.0`으로 uv.lock 내보내기 209행(dev 그룹 포함) 검사, 알려진
  취약점 0건 `[실측 2026-09-27]`.
- 배포 점검: 프로덕션형 env로 `manage.py check --deploy` 실행 결과 W021(HSTS preload,
  의도된 결정) 1건만 `[실측 2026-09-27]`.
- 반박된 가설: JSON-LD XSS, archive FK IDOR, 제보 URL 스킴, 대시보드 텍스트 주입은
  소스로 반박됐다. 독립 검토 주장 중 "axes가 IP만 잠가 분산 크리덴셜 스터핑에
  무력"은 부분 오류다. `login_failed 5/300s/key`(config/settings.py:493)가 계정 단위
  제한을 이미 건다.

## 4. 기록된 보류·이연 (재권고 아님)

- 슈퍼유저 계정 조작 POST의 액션 빈도 제한·step-up 재인증 미구현: 사용자 결정
  (2026-09-07) 수용.
- `/api/schema/`·`/api/docs/` 스로틀·캐시 없음: 백로그 F12, 실트래픽 개시 전 유보.
- 스태프 셸이 `csrftoken` 쿠키를 새로 발급하지 않음: 백로그 F18.
- HSTS preload 꺼짐: CI 주석 W021, 되돌리기 어려운 별도 결정.
- 러너 캡션 경로 응답 크기 상한·DNS 리바인딩: 트랙 35 이연(F6이 이 항목을 포함한다).
- 사용자별 저장 총량·일일 쿼터: 이 검토에서 새로 식별한 하드닝 항목(F3), 트랙
  착수 시 결정.
- F10(MFA) 미도입: `auth-hardening` 결정(2026-07-01) — allauth.mfa TOTP는
  폐기, "지금은 두지 않음"(rate limit + Google 2FA 위임으로 대체). 이 문서
  §1·§2에는 재권고로 적혀 있었으나 이미 기록된 사용자 보류다(트랙 40에서
  누락을 확인해 이 항목에 추가).

## 5. 운영 확인 항목 (저장소 밖, 미검증)

| 항목 | 확인 방법 | 왜 |
|---|---|---|
| Render env `TRUSTED_PROXY_COUNT` 설정 여부와 값 | Render 대시보드 env 확인 | 없으면 axes가 프록시 IP를 잠가 5회 실패 뒤 1시간 전체 로그인 차단(F2) |
| 프록시 뒤 `REMOTE_ADDR`·`X-Forwarded-For` 실제 값 | 스테이징에서 위조 `X-Forwarded-For`를 보내고 `StaffActionLog.ip_address` 확인(operations-runbook §4 절차) | F2의 운영 전제 확정 |
| allauth 공유 버킷 재현 | 스테이징: IP A에서 잘못된 로그인 10회, 이어서 IP B 첫 로그인이 429이면 공유 버킷 | F2 수정 전후 비교 증거 |
| Render 프록시 요청 본문 상한 | Render 문서 또는 큰 본문 실측 | F3의 실제 노출 크기 |
| 스킴 없는 `official_url` 기존 행 수 | 운영 DB `Event.objects.exclude(official_url__startswith="http").count()` — 정정: 호스트 없는 값까지 잡도록 `docs/deploy-runbook.md` §3 항목 16의 `urlsplit` 기준 명령을 쓴다 | F1 배포 뒤 재게시 거부를 피하려면 먼저 고쳐야 한다. 검증기는 기존 게시 행을 소급 정리하지 않으므로 0이 아니면 **배포 전 차단**(SRR 사후 검증) |

## 6. 검증 증거 `[실측 2026-09-27]`

```text
# 배포 점검 (W021만, exit 0)
DEBUG=false ALLOWED_HOSTS=review.example CSRF_TRUSTED_ORIGINS=https://review.example SECURE_SSL=true SECURE_COOKIES=true SECRET_KEY=<더미> uv run python manage.py check --deploy

# 의존성 (No known vulnerabilities found, 내보내기 209행)
uv export --format requirements.txt --frozen --no-emit-project --no-hashes -o /tmp/req.txt
uvx --python 3.13 pip-audit==2.9.0 -r /tmp/req.txt --no-deps --disable-pip --strict

# F1 재현 (DB 쓰기 없음): §2 F1의 shell 명령

# F5 대역 판정 (False False)
uv run python -c "import ipaddress; a=ipaddress.ip_address('100.64.0.1'); print(a.is_private, a.is_global)"

# 부정 주장 근거 (전부 0건)
rg -n 'ALLAUTH_TRUSTED_PROXY_COUNT|TRUSTED_CLIENT_IP_HEADER|ALLAUTH_' config/ .env.example docs/ tests/
rg -n 'csrf_exempt' --type py -g '!tests/**'
rg -n 'allauth\.mfa|MFA_|Content-Security-Policy|CSP_|NUM_PROXIES' config/ core/ templates/base.html
rg -n 'max_length' archive/serializers.py     # memo 항목 없음
```

함정 2건: 로컬 `uvx pip-audit`는 venv 생성(ensurepip)에서 SIGABRT로 죽어
`--no-deps --disable-pip`가 필요했다(CI는 정상). `rg`는 `.venv`를 gitignore로
건너뛰므로 라이브러리 소스 검색은 `--no-ignore`를 붙인다.

## 7. 권장 트랙 구성

- **PR 1개, 커밋은 결함별로 분리**: ① F1 스킴 허용목록(+SEC-01~04) → ② F2 allauth
  배선·문서(+SEC-05~07) → ③ F3 시리얼라이저 상한·미들웨어(+SEC-08~10) → ④ F4
  뮤텍스(+SEC-11) → ⑤ F5·F7·F9 소규모 동류(+SEC-12). F6은 트랙 35 이연 처리와
  함께, F8은 선택. F10·F11은 제품·의존성 결정이 필요해 별도 트랙.
  **정정(2026-09-28)**: ③의 "미들웨어" 부분은 구현 중 실측으로 반박돼
  취소됐다 — DRF 3.17.2가 JSON·Form 파서 모두에 이미 `HttpRequest.body`
  경로(Django `DATA_UPLOAD_MAX_MEMORY_SIZE` 상한 포함)를 태워 별도 파서도
  미들웨어도 불필요하다(§2 F3 정정, §8).
- **Activated Roles**: Security & Resilience Reviewer(계획 검토·사후 검증), Backend
  TDD Coach(Red-Green), Backend & Integration Engineer(구현), Quality Verification
  Lead(증거 매트릭스), Deployment & Operations Reviewer(F2 env·런북, F3 미들웨어
  등록). **Not Activated**: Product Scope Owner(제품 범위 변경 없음, F10은 별도
  트랙에서 활성), Domain Architecture Reviewer(경계 변경 없음, `core/middleware.py`
  신설은 core 소유 규칙에 부합 — **정정: 신설 자체가 취소됐다**, 위 항목 참조),
  Web Experience Designer·Browser Interaction
  Reviewer(템플릿 선택 항목을 넣을 때만 활성), AI Automation Architect(해당 없음).
- **순서 근거**: F1과 F2는 각각 함수 한 곳·설정 한 줄로 닫히는 High라 먼저
  처리한다. F3의 미들웨어는 F1·F2와 독립이다. F4는 G2(gunicorn `--timeout`) 트랙과
  같은 PR로 묶어도 된다.
- **완료 기준**: 위 Test List 전부 Green, `uv run pytest -q` 전체 회귀 Green,
  `check --deploy` W021만, 스테이징에서 §5의 allauth 공유 버킷 재현이 사라짐.

## 8. 반영 결과 (트랙 40, 2026-09-28)

| # | 상태 | 근거·커밋 | 관련 테스트 ID |
|---|---|---|---|
| F1 | 수정 | `events/services.py`(스킴 허용목록 + 호스트 필수), `staff/views/events.py`(필드 오류 매핑), 커밋 `892feec3` | SEC-01, SEC-02, SEC-03b, SEC-04, SEC-04a, SEC-04b, SEC-04c |
| F2 | 수정 | `config/settings.py` `build_allauth_trusted_proxy_count` + `ALLAUTH_TRUSTED_PROXY_COUNT` 배선, 커밋 `b49a5fec` | SEC-05a, SEC-05b, SEC-06, SEC-07 |
| F3a(memo 상한) | 수정 | `archive/models.py` `MEMO_MAX_LENGTH = 2000`, `archive/serializers.py`, 커밋 `fa1aa6ef` | SEC-10, SEC-10b |
| F3b(본문 크기) | 반박 — 코드 변경 취소, 핀 테스트만 추가 | §2 F3 정정 참조. DRF 3.17.2 `Request._parse`가 `HttpRequest.body`를 태워 이미 상한이 걸린다 `[코드 rest_framework/request.py:358-360]`, 핀 커밋 `15b0ef6e` | SEC-08b, SEC-08c(기대값 413→400으로 정정, 기존 보호 고정 핀) |
| F4 | 수정 | `staff/views/__init__.py` 캐시 뮤텍스, 커밋 `4eb3742b`. 보장 범위는 정상·파이썬 예외·SIGABRT 종료(§2 F4 정정) | SEC-11, SEC-11b |
| F5 | 수정 | `drafts/url_safety.py`·`local_runner/url_safety.py` `or not value.is_global`, 커밋 `2cde14d7` | SEC-12, SEC-12b |
| F6 | 제외(이연) | 트랙 35 이연 항목과 함께 처리 예정(§7) | — |
| F7 | 수정 | `drafts/runner_views.py` `MAX_KNOWN_URLS_PER_REQUEST = 20`, 커밋 `8315ab4c` | SEC-13, SEC-14 |
| F8 | 제외(선택 항목, 미착수) | §7 사유 그대로 | — |
| F9 | 수정 | `config/settings.py` `load_secure_cookies()`, 커밋 `4bbc3ecc` | SEC-15a, SEC-15b |
| F10 | 보류(기록된 사용자 결정) | `auth-hardening` 2026-07-01 결정, §4 추가 기록 | — |
| F11 | 제외(별도 트랙, 승인 필요) | 새 의존성·인라인 스크립트 nonce 전환 필요 | — |

Evidence `[실측 2026-09-28, 브랜치 fix/security-review-2026-09-27]`:

- 전체 회귀 `uv run pytest -q` 3,211 passed / 10 deselected / 실패 0 / 99.72초(기준선 3,181 passed, 신규 테스트 30건 `[계산]`). e2e(`-m e2e tests/e2e`)는 명시 요청 시에만 돌리는 규칙이라 실행하지 않았다.
- `manage.py check` 이상 없음, `makemigrations --check --dry-run` No changes detected, 프로덕션형 env `check --deploy` W021 1건(HSTS preload, 의도된 결정).
- 시나리오마다 구현 전 Red를 기대한 이유로 확인했고, 이미 Green이던 핀과 구현 되돌리기 뮤테이션 18건(스크립트 명세 4개 합계 `[실측]`)은 전부 Red를 낸 뒤 바이트 단위로 복원했다(임시 변경, 미커밋).
- 러너 복제본 반영 전 서버만 고친 상태에서 문자 일치 가드 `tests/local_runner/test_url_safety_parity.py`가 Red였다(SEC-12b).
- 남은 운영 확인(저장소 밖, 미검증): Render env `TRUSTED_PROXY_COUNT` 값과 실제 홉 수, 스테이징 allauth 공유 버킷 재현이 사라지는지, 운영 DB의 비-http(s)·호스트 없는 `official_url` 행 수와 memo 최대 길이(`docs/deploy-runbook.md` §3 항목 16·17).
