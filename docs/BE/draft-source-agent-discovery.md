# 로컬 에이전트 기반 수집처 탐색

상태: **서버 경계·로컬 러너 구현됨(2026-08-20), 트랙 30 키워드 탐색 본체
구현됨(2026-09-12)** — 정기 실행·자동 시작은 미구현
사용자 결정: 2026-08-20, 2026-09-11(트랙 30 재편)

## Current fact

- `DraftSource`는 RSS·Sitemap·HTML 수집처와 활성 여부, HTML 링크 선택자,
  마지막 실행 상태를 보관한다(`drafts/models.py`).
- `discover_drafts`는 활성 `DraftSource`를 읽고 목록과 후보 URL을 `robots.txt`
  및 URL 안전성 검증 뒤 가져온다. 후보 행사의 제목·날짜·장소 등은
  `create_draft_from_url`의 규칙 기반 추출로 채워 `EventDraft(PENDING)`으로
  저장한다(`drafts/management/commands/discover_drafts.py`,
  `drafts/services.py`).
- 스태프 대시보드의 「지금 수집」 버튼은 위 관리 명령을 동기로 실행한다.
- 서버의 행사 필드 LLM 추출은 `DRAFT_LLM_EXTRACTION_ENABLED=False`로 꺼져
  있다. 유료 API를 쓰지 않는다는 결정은 유지된다.
- 로컬 러너(`local_runner/`, Claude Code 어댑터), 에이전트 탐색 실행, 후보
  검증, 러너 heartbeat와 전용 인증 경계는 2026-08-20 구현됐다(상세는
  "구현 확정 사항" 절).

## Decision

행사 공급 자동화는 서로 다른 두 경로로 운영한다.

| 경로 | 입력 | 자동화 책임 | 결과 |
|---|---|---|---|
| 기본 소스 수집 | 이미 활성화된 `DraftSource` | 서버가 목록·후보 URL을 가져오고 행사 필드를 규칙으로 추출 | `EventDraft(PENDING)` |
| 로컬 에이전트 탐색 | 스태프의 별도 탐색 요청 | 개인 맥의 Codex 또는 Claude Code가 새 수집처와 표본 행사 URL을 제안 | 서버 검증을 통과한 `DraftSource`와 규칙 기반 `EventDraft(PENDING)` |

LLM은 행사 제목·날짜·장소·요약을 직접 채우지 않는다. LLM의 책임은 새
수집처와 표본 행사 URL을 찾고 구조화된 후보 명세를 반환하는 데서 끝난다.
저장, 소스 활성화, 행사 필드 추출과 공개 여부는 항상 서버가 결정한다.

모든 행사 드래프트는 생성 경로와 무관하게 관리자의 명시적 검수와 승인 전에는
게시 이벤트가 되지 않는다.

## Architecture

```text
staff console
  ├─ 기본 소스 수집 ─────────────────────────────┐
  │                                               │
  └─ 새 수집처 탐색 요청                          │
       -> source discovery run                    │
       -> local runner heartbeat / lease          │
       -> Codex or Claude Code web exploration    │
       -> structured source candidates            │
       -> server-owned deterministic validation   │
       -> promote accepted DraftSource            │
       └───────────────────────────────────────────┤
                                                   v
                                  rule-based discover_drafts
                                                   v
                                      EventDraft(PENDING)
                                                   v
                                           staff review
```

의존 방향은 다음과 같다.

```text
local runner -> authenticated source-discovery boundary -> drafts
drafts -> events publication service
```

- 로컬 러너는 후보 제안자이며 데이터 저장 결정권자가 아니다.
- `drafts`가 탐색 실행, 후보 검증 결과, `DraftSource` 승격, 규칙 기반
  `EventDraft` 생성을 소유한다.
- `events`는 승인된 공식 이벤트 게시만 계속 소유한다.
- `archive`, `events`, `core`는 에이전트 공급자나 로컬 러너에 의존하지 않는다.

## Components

### 1. 스태프 제어 화면

- 기존 「지금 수집」은 활성 소스의 규칙 기반 수집만 실행한다. 이 경로는 로컬
  러너나 LLM을 호출하지 않는다.
- 별도 「새 수집처 탐색」은 에이전트 탐색 실행을 만든다. 이름은 행사 필드 LLM
  추출로 오해되지 않게 수집처 탐색임을 드러낸다.
- 서버가 최근 heartbeat를 확인하지 못하면 탐색 버튼은 사용할 수 없는 상태와
  「로컬 러너 오프라인」 이유를 보여준다.
- 실행별 성공 후보와 실패 후보를 분리한다. 정상적으로 승격된 소스를 매번 다시
  검수하게 하지 않고, 실패·격리된 후보만 운영자의 확인 대상으로 모은다.

구체적인 배치, 문구, 비동기 갱신 방식과 접근성 기준은 프론트엔드 구현 계획에서
별도 확정한다.

### 2. 탐색 실행과 후보

`DraftSource.last_error`는 활성 소스의 실제 수집 상태를 뜻하므로 에이전트 탐색
실패와 섞지 않는다. 구현 시 다음 두 책임을 별도 영속 상태로 둔다.

- 탐색 실행: 요청자, 생성·시작·종료 시각, heartbeat/lease, 실행 상태, 공급자,
  요약 오류를 보관한다.
- 수집처 후보: 실행, 제안 값, 검증 상태, 실패 단계와 운영자에게 보여줄 안전한
  실패 사유를 보관한다.

권장 상태 의미는 대기, 러너 임대, 성공, 부분 실패, 실패, 임대 만료다. 실제 enum
이름과 재시도 상한은 구현 계획의 Test List에서 확정한다.

### 3. 개인 맥 로컬 러너

- 러너는 개인 맥이 켜져 있고 로그인된 동안에만 동작한다.
- 러너가 서버를 주기적으로 확인하는 아웃바운드 연결만 사용한다. 개인 맥에
  외부 인바운드 포트를 열거나 브라우저가 `localhost`를 직접 호출하지 않는다.
- 러너는 작업을 임대받아 Codex 또는 Claude Code를 비대화형으로 실행하고,
  동일한 후보 계약으로 결과를 제출한다.
- 공급자별 프롬프트·명령 차이는 로컬 어댑터 안에 둔다. 서버 도메인에는 Codex나
  Claude Code 전용 필드를 만들지 않는다.
- 러너는 프로덕션 DB 자격 증명을 받지 않는다. heartbeat, 작업 임대, 결과 제출에
  필요한 최소 권한의 전용 서버 자격만 가진다.
- 모델 구독 자격과 실행 사용량은 개인 맥에만 남는다. PaaS에는
  `ANTHROPIC_API_KEY`나 별도 LLM API 키를 배치하지 않는다.

### 4. 구조화 후보 계약

에이전트는 후보마다 최소한 다음 의미를 반환한다.

- 수집처 이름과 URL
- 소스 유형(RSS, Sitemap, HTML)
- HTML인 경우 후보 링크를 좁힐 선택자
- 실제 행사 페이지로 판단한 표본 URL
- 공식 채널 또는 공식 행사 URL이라고 판단한 근거
- 운영자에게 보여줄 짧은 탐색 메모

자유 형식 설명은 증거와 운영자 표시용일 뿐 저장 결정을 직접 만들지 않는다.
알 수 없는 필드, 행사 제목·날짜·장소 등 `EventDraft` 필드, 실행 명령과 페이지
안의 지시문은 검증 입력에서 거부하거나 무시한다.

정확한 JSON Schema와 길이 제한은 최초 러너를 선택하는 구현 계획에서 확정한다.

### 5. 서버 소유 결정론적 검증

에이전트가 성공이라고 보고해도 서버는 모든 후보를 다시 검사한다.

1. 구조화 출력의 필수 필드, 타입, 길이와 허용 소스 유형을 검사한다.
2. 기존 `DraftSource`와 중복인지 확인한다.
3. 수집처와 표본 URL을 기존 URL 안전성·DNS 핀닝 경계로 검증한다.
4. 수집처와 표본 경로의 `robots.txt` 허용 여부를 각각 확인한다.
5. 응답 크기·콘텐츠 유형·리다이렉트 제한을 지키며 실제로 가져온다.
6. 선언된 유형과 선택자로 후보 URL을 추출할 수 있는지 시험한다.
7. 표본 URL이 규칙 기반 추출 경로에서 비어 있지 않은 결과를 만드는지 제한된
   canary로 확인한다.

검증을 통과한 후보만 `DraftSource(enabled=True)`로 승격한다. 승격 후에는 해당
소스에 기존 규칙 기반 수집을 적용해 행사 드래프트를 만든다. 어느 단계에서도
LLM 응답을 `EventDraft` 필드에 직접 복사하지 않는다.

공식성은 URL·HTML 구조만으로 완전히 증명할 수 없다. 에이전트가 낸 공식성 근거는
추적용 증거이며 서버의 기술 검증을 대체하지 않는다. 잘못된 소스가 기술 게이트를
통과할 잔여 위험은 모든 결과를 `PENDING`으로 격리하고 관리자가 공식 URL을
확인한 뒤에만 게시하는 현재 승인 경계로 제한한다. 자동 게시를 도입한다면 이
설계의 안전 근거는 성립하지 않으며 별도 승인이 필요하다.

## Error handling and retry

- 러너 오프라인: 기본 소스 수집은 영향을 받지 않는다. 에이전트 탐색만 사용할 수
  없는 상태로 표시한다.
- heartbeat 직후 연결 단절: 생성된 작업은 임대 만료 후 다시 대기시키거나 실패로
  닫는다. 재시도 상한은 구현 계획에서 정한다.
- 잘못된 구조화 출력: 원문을 신뢰하지 않고 후보를 격리하며, 안전한 실패 단계만
  저장한다.
- 부분 실패: 후보별로 독립 처리한다. 통과한 후보는 승격하고 실패한 후보만 실패
  큐에 남긴다.
- 중복 제출과 재시도: 실행과 후보 제출에는 멱등성 키를 두고,
  `DraftSource.url`·`EventDraft.source_url` 유일성 계약을 유지한다.
- 승격 뒤 운영 실패: 소스를 비활성화해 이후 수집을 멈춘다. 이미 생성된
  `PENDING` 드래프트는 자동 삭제하지 않고 관리자가 검수·반려한다.
- 에이전트 실패: 서버 LLM 필드 추출로 폴백하지 않는다. 실패를 기록하고 기본
  규칙 기반 경로는 그대로 유지한다.

## Security and resilience guardrails

- 탐색 요청은 기존 스태프 인증과 CSRF 보호 뒤에 둔다.
- 러너 자격은 heartbeat·임대·결과 제출로 권한을 제한하고 회전·폐기할 수 있어야
  한다. 관리자 세션이나 프로덕션 DB 자격을 재사용하지 않는다.
- 에이전트가 방문한 웹 콘텐츠는 신뢰하지 않는 데이터다. 페이지 안의 지시문을
  따르지 않으며 구조화 후보 외의 명령·비밀 요청을 무시한다.
- 서버는 에이전트가 이미 확인했다는 주장과 무관하게 SSRF, DNS 리바인딩,
  리다이렉트, 응답 크기, 콘텐츠 유형과 `robots.txt`를 다시 검증한다.
- 로그에는 원문 페이지, 모델 프롬프트, 구독 자격, 러너 토큰을 남기지 않는다.
  실행 ID, 후보 URL, 실패 단계와 예외 종류처럼 운영에 필요한 최소 정보만 남긴다.
- 실행 생성과 러너 claim에는 스로틀과 단일 임대 계약을 둔다. 동일 작업이 동시에
  두 러너에 의해 저장 결정을 만들지 못해야 한다.

## Operations

- 개인 맥이 켜져 있지 않으면 에이전트 탐색을 사용할 수 없다는 제약을 정상 운영
  상태로 취급한다. 가용성 장애로 PaaS 앱을 실패시키지 않는다.
- 최초 공급자는 Claude Code로 확정됐다(`local_runner/claude_code_adapter.py`).
  러너 자동 시작 방식과 토큰 저장·회전 절차는 아직 미결이다.
- 기본 소스 수집은 서버 기능 플래그와 활성 `DraftSource`만으로 계속 동작한다.
- PaaS 배포에는 LLM API 키나 에이전트 런타임을 추가하지 않는다.
- 운영 화면은 러너 최근 heartbeat, 탐색 실행 상태, 후보별 실패 단계, 승격된 소스와
  후속 규칙 기반 드래프트 생성 결과를 구분해 보여줘야 한다.

관찰 지표는 에이전트 실행 수, 제안 후보 수, 검증 통과·실패 후보 수, 승격 소스 수,
승격 소스가 만든 드래프트 수, 해당 드래프트의 관리자 승인·반려 결과다. 값과 목표
임계치는 실제 운영 데이터가 생긴 뒤 정한다.

## Implementation acceptance criteria

- 기본 「지금 수집」은 로컬 러너나 모델을 호출하지 않는다.
- 러너 heartbeat가 없으면 「새 수집처 탐색」을 실행할 수 없고 이유가 보인다.
- 온라인 러너는 서버 작업을 임대받아 구조화 후보만 제출할 수 있다.
- 서버가 모든 후보를 독립 검증하며 실패 후보는 자동 활성화하지 않는다.
- 검증 통과 후보는 활성 `DraftSource`가 되고 기존 규칙 기반 파이프라인으로
  `EventDraft(PENDING)`을 만든다.
- LLM 응답이 행사 제목·날짜·장소·요약 필드에 직접 저장되지 않는다.
- 부분 실패와 재시도에도 소스·드래프트가 중복되지 않는다.
- 에이전트 탐색 실패가 기본 수집이나 게시 이벤트에 영향을 주지 않는다.
- 로컬 러너는 DB 자격 없이 최소 권한 서버 경계만 사용한다.
- 모든 게시 전환은 기존 스태프 승인 서비스를 계속 거친다.

## Verification design

구현 시 자동화 테스트는 백엔드 계약만 다룬다.

- unit: 후보 Schema와 값 검증, 상태 전이, 임대 만료 판단
- domain: 후보별 승격·격리, 부분 성공, 멱등 재제출, 규칙 기반 드래프트 생성
- web: 스태프 권한·CSRF, 오프라인 실행 거부, 러너 최소 권한 인증
- contract: 기본 수집에서 LLM 호출 차단, 에이전트 필드의 `EventDraft` 직접 저장
  차단, URL 안전성·로그 비밀정보 비노출
- manual browser: 러너 온라인·오프라인 표시, 실행 중·부분 실패·완료 상태,
  실패 큐 복구 흐름

브라우저·레이아웃 자동 테스트는 추가하지 않는다. 실제 Chromium 조작 결과를
구현 기술 기록에 증거로 남긴다.

## Explicit exclusions

- `DRAFT_LLM_EXTRACTION_ENABLED` 활성화와 행사 필드 LLM 프리필
- 자동 승인·자동 게시
- PaaS 또는 상시 클라우드 에이전트 러너
- 정기 실행 스케줄러
- 결제형 검색 API와 별도 LLM API 키
- 개인 맥으로 향하는 인바운드 포트와 브라우저의 localhost 직접 호출
- Codex·Claude Code를 동시에 지원하기 위한 선제적 공통 프레임워크

## 구현 확정 사항(2026-08-20)

- 상수(모듈 상수, `drafts/discovery_runs.py`·`drafts/candidate_validation.py`):
  HEARTBEAT_FRESH_SECONDS=120 / LEASE_SECONDS=1800(최초 900에서 상향, 아래
  참고) / MAX_LEASES=2 / MAX_CANDIDATES_PER_RUN=10 /
  INITIAL_DRAFTS_PER_PROMOTED_SOURCE=5
- 실행 상태 enum: pending/claimed/succeeded/partially_failed/failed/expired.
  후보 실패 단계 8종(기록 당시): schema/duplicate/url_safety/robots/fetch/
  listing_extraction/sample_canary/sample_mismatch — **정정(트랙 35,
  2026-09-18)**: 트랙 33이 `not_domestic`을, 트랙 35가 `robots_fetch_failed`를
  추가해 현재 10종이다 `[실측 python3 ast, drafts/models.py:160-170]`(원문 8종은
  기록 당시 값으로 남긴다)
- 러너 인증: env `DRAFT_DISCOVERY_RUNNER_TOKEN` + 헤더 `X-Runner-Token`,
  **빈 설정은 비교 전 명시 거부**(`constant_time_compare`가 빈 문자열 쌍을
  참으로 보는 함정 — 가드레일), 스로틀 `discovery_runner` 60/minute, 공개
  OpenAPI 문서에서 의도 제외
- 트랜잭션 가드레일: 네트워크 검증은 트랜잭션 밖, 저장은 run
  `select_for_update` 재잠금 + lease 재검증 뒤 짧은 atomic. **SQLite는
  `select_for_update`를 무시하므로 잠금 계약은 Postgres 기준**
- failure_reason·error_summary는 서버 정의 문구+예외 클래스명만(원문
  비보간), 초기 드래프트는 공유 candidate_intake 재사용으로 후보 URL별
  robots 재검증 유지, 전량 수집은 기존 「지금 수집」이 담당
- 러너 실기동 실측(2026-08-20): 왕복(403/204 → claim → duplicate·url_safety
  (gaierror) 격리 → complete FAILED) 및 `claude -p` 봉투 파싱 확인. CLI에
  --max-turns 없음(OS 타임아웃 600초)
- 표본-목록 연관성 검사(sample_mismatch 단계 신설) — 무관한 사이트의 정상
  행사 URL을 표본으로 붙여 목록 검증을 우회해 승격을 통과시키던 경로를
  차단한다(사용자 검토 발견, 2026-08-20)
- `create_run`은 heartbeat 단일 행(pk=1)을 `select_for_update`로 잠근 뒤
  활성 실행 검사와 생성을 같은 트랜잭션에서 수행한다 — 동시 탐색 요청
  2건이 모두 통과해 pending을 중복 생성하는 경쟁을 차단한다
- `LEASE_SECONDS` 900→1800 + 유효 제출마다 임대 갱신(`renew_lease`) +
  에이전트 실행 중 백그라운드 heartbeat 스레드 — 긴 검증 도중 임대가
  만료돼 제출이 거부되는 경로와, 에이전트 실행 중 대시보드가 러너를
  오프라인으로 오표시하는 문제를 함께 막는다
- 러너 폴링 경계(`_safe_poll`)는 HTTP 오류를 격리하고 지수 backoff로
  재시도한다. 후보 제출 중 409(임대 상실)를 받으면 그 실행의 제출을
  즉시 중단하고 `complete` 보고를 생략한다(다음 폴에서 서버가 재대기·만료
  처리)
- 러너는 에이전트 출력에 dict가 아닌 항목이 있었거나 유효 후보가 0개면
  `complete`를 `failed(invalid_output)`로 보고한다(빈 결과도 성공으로
  기록하지 않는다) — 사용자 검토 2라운드 발견(2026-08-21)
- heartbeat 티커 범위를 후보 제출·완료 보고까지 확장(`_run_once` 외곽
  try/finally) — 제출 국면 오프라인 오표시 재발 경로 폐쇄(2026-08-21)
- 러너 로깅은 모듈 logger로 전환(print 금지 게이트 `_SCAN_PACKAGES`에
  `local_runner` 편입), 티커는 `httpx.HTTPError`만 기록 후 지속·그 외
  예외는 전파, `main()`이 타임스탬프 포함 `logging.basicConfig` 설정
  (2026-08-21)
- 스태프 대시보드 실패 단계 라벨에 sample_mismatch("표본 불일치") 분기
  추가(WED·BIR 게이트 통과, 미지 단계 폴백은 overflow 안전장치 조건부로
  이연, 2026-08-21)

**격리 권고(미결).** `--permission-mode bypassPermissions`는 Anthropic
권한 문서([iam](https://docs.anthropic.com/ko/docs/claude-code/iam))가
격리된 환경에서만 쓰도록 권고한다. 현재는 `--tools`로 웹 탐색 2종
(WebSearch·WebFetch)만 허용해 파일·셸 도구가 없지만, 장기 상시 운영으로
전환하기 전에는 러너를 별도 실행 계정 또는 컨테이너 등 격리 환경에서
돌리는 구성을 권장한다.

**정정(2026-09-11, 측정 후 기록).** 위 문단의 "`--tools`로 웹 탐색 2종만
허용해 파일·셸 도구가 없다"는 전제가 무효화됐다 — 도구 목록 제한은 이 맥에
깔린 MCP 플러그인 도구까지는 막지 못했고, 여기에는 브라우저 제어(페이지
열기·클릭·폼 입력·자바스크립트 실행) 도구가 포함된다. 실제 `claude` CLI를
같은 인자로 호출해 열린 도구 목록을 직접 물어 확인했다: `--strict-mcp-config`
없이는 `WebSearch` + 크롬 개발자도구 MCP 도구 전부가 열리고, 붙이면
`WebSearch` 하나만 남는다 [실측 2026-09-11]. `WebFetch`는 두 경우 모두 열리지
않는다 — 이 맥의 전역 설정 거부 목록에 있어 하위 설정으로 뒤집을 수 없다
[실측]. 즉 인자에 남아 있는 `WebFetch`는 현재 죽은 값이다. 고친 내용:
`local_runner/claude_code_adapter.py`의 `_execute_claude`에
`--strict-mcp-config` 플래그를 추가하고, argv 계약 테스트 1건과 두 플래그
(`--permission-mode bypassPermissions`·`--strict-mcp-config`)가 항상 함께
있어야 한다는 쌍 불변식 회귀 테스트 1건을 신설했다(커밋 `b68e2881`). 남은
미검증 1건: 그 브라우저 제어 MCP 도구가 사용자의 상시 로그인 브라우저
프로파일에 붙는지, 격리된 새 프로파일을 쓰는지 확인하지 못했다 — 붙는다면
위 격리 권고의 우선순위가 올라간다.

### 검토 게이트 기록

- 보안 사후 판정(2026-08-20): Conforms — 사전 블로커 5건 닫힘 확인: 빈 토큰
  사전 거부(runner_views의 IsDiscoveryRunner), failure_reason 원문
  비보간(_save_failed_candidate + V12 뮤테이션), 후보 상한 서버
  강제(submit_candidate), create_draft_from_fields 미사용(경계 가드), 저장
  직전 재잠금·lease 재검증(locked_run_with_valid_lease + V11). 관찰(정보):
  단일 후보 제출 요청의 최악 지연이 fetch 예산에 따라 수십 초까지 가능 —
  배포 시 워커 타임아웃 튜닝으로 흡수.
- FE 이중 게이트(2026-08-20): WED·BIR 모두 Conforms(1차 BIR Medium — URL·
  사유 절단 접근 불가 — 수정 후 재판정).
- QVL(2026-08-20): 수용 기준 15항 전부 충족, 조건부 완료의 조건 2건(이
  소절과 SERVICE_MODULES 등록)은 같은 커밋에서 이행.
- 사후 수정분 재검토(2026-08-21, 보안·운영·QVL 3역할): 머지 차단 결함 0건.
  사용자 검토 5건은 전부 닫힘 확인(sample_mismatch 양경로·renew_lease 연장·
  409 시 complete 생략·시그니처 게이트는 테스트 증거 존재). 잔여 위험은
  아래 Known gap에 기록하고 사용자 승인 아래 머지.
- 사용자 검토 2라운드(2026-08-21) 4건 반영: R1~R6 Red-Green(이미-초록 3건은
  뮤테이션 왕복으로 실증), FE 게이트 BIR Conforms/WED는 폴백 이연을 관리된
  범위 축소로 판정, 실기동 왕복(유효 토큰 204/200·오탈 토큰 403 격리) 실측.
- 정정(2026-09-11, 측정 후 기록): 위 2026-08-20 보안 사후 판정의 "Conforms"는
  `--tools` 도구 목록 제한만으로 격리가 충분하다고 본 낡은 측정 위에 서
  있었다. 실제로는 MCP 플러그인 도구(브라우저 제어 포함)가
  `--strict-mcp-config` 없이 그대로 열려 있었다(위 격리 권고 정정 절 참고,
  [실측 2026-09-11]). 어댑터 수정과 argv 계약·쌍 불변식 테스트 신설로
  닫았다(커밋 `b68e2881`). 이 정정은 2026-08-20 판정 자체를 되돌리는 것이
  아니라, 그 판정이 딛고 섰던 전제가 오늘 실측으로 바뀌었음을 기록한다.

## Known gap

- 실행·후보 모델의 정확한 필드와 마이그레이션, lease·heartbeat·재시도 시간,
  스로틀 값은 구현 계획의 Test List 전에 승인해야 한다. → **해소**(위
  "구현 확정 사항" 절, 2026-08-20).
- 최초 러너 공급자와 구체적인 비대화형 실행 방식 → **해소**: Claude Code
  어댑터로 확정됐다(`claude -p --output-format json --tools
  "WebSearch,WebFetch" --permission-mode bypassPermissions`). 서버 후보
  계약은 계속 공급자 중립으로 유지한다.
- 공식성의 완전 자동 판정은 불가능하다. 현재 안전 근거는 게시 전 관리자 검수다.
- 로컬 러너 설치·업데이트·자동 시작(launchd)·토큰 회전 절차·정기 실행 스케줄러는
  아직 없다.
- `--permission-mode bypassPermissions` 격리 권고 미이행: 현재 `--tools`로
  웹 탐색 2종만 허용해 파일·셸 도구는 없지만, 장기 상시 운영 전에는 별도
  실행 계정 또는 격리 환경 구성이 필요하다(아래 격리 권고 참고).
- sample_mismatch 비교는 정규화 비대칭 오탐이 가능하다: 목록 추출 URL은
  `_strip_tracking_params`로 정규화(utm 제거·query 재인코딩)되지만
  `sample_url`은 원문 그대로 완전일치 비교라, 표기 차이(`%20` vs `+`,
  utm 포함)만으로 정당한 표본이 결정론적으로 거부될 수 있다. 거부
  방향(fail-safe)이라 보안 우회는 없다. 에이전트 프롬프트(`build_prompt`)에
  "표본은 목록에서 추출된 URL이어야 한다"는 지시도 아직 없다.
- heartbeat 스레드가 에이전트 탐색 국면만 덮던 문제 → **해소**(2026-08-21):
  티커 범위를 후보 제출·완료 보고까지 확장(`_run_once` 외곽 try/finally),
  제출 국면 120초 초과로 인한 러너 오프라인 오표시 재발 경로를 닫았다.
- `_HeartbeatTicker`는 테스트를 확보했다(2026-08-21, HTTPError 지속·비HTTP
  전파·정지 순서). **러너 5xx 지수 backoff 산식은 여전히 테스트 0건**이다.
- `create_run`의 동시 요청 직렬화는 FOR UPDATE SQL 발생 단언으로만 대리
  검증된다 — 실제 경쟁 재현은 자동 테스트로 불가하고(SQLite는
  select_for_update 무시), 실효성 검증은 Postgres 코드 리뷰뿐이다.
- 에이전트 1회 실행의 웹 호출량 상한이 없다: CLI가 --max-turns를 지원하지
  않아([실측] 2026-08-20) 600초 벽시계 타임아웃이 유일한 상한이다. 위험은
  프롬프트 주입이나 판단 오류가 있을 때 단일 실행이 구독 사용량을 과다
  소모할 수 있다는 것이다. 트리거: CLI가 --max-turns를 지원하게 되면
  반영한다.

## 트랙 30(v3.1): 키워드 탐색 본체 도입(2026-09-11~2026-09-12)

기존 절은 "이미 아는 계정을 주기적으로 도는 수집" 전제로 쓰였다. 트랙 30은
**스태프가 검색어를 입력하면 그 검색어로 새 행사·수집처를 찾는 경로**를
본체로 새로 얹었다. 계정 정기 수집(트랙 31)은 이 절 밖에서 별도로 다룬다.

### 3단 분리

한 실행 안에서 서로 다른 세 책임이 순서대로 실행되고, 각 단계는 앞 단계가
낸 것과 다른 것만 받아 다른 것만 낸다.

1. **탐색(exploration)** — 검색만 한다. 입력은 스태프가 낸 검색어
   하나(`run["query"]`)뿐이고, 출력은 URL과 얕은 판단(`is_event`,
   `why_excluded`, `platform`, 후보 수집처)뿐이다. 행사 본문을 읽지 않는다
   `[코드]` `local_runner/claude_code_adapter.py:83-130`
   (`build_exploration_prompt`) — 프롬프트 자체가 "이 환경에서는 페이지를
   여는 도구가 막혀 있다"고 명시하고 검색 결과 목록(제목·요약·URL)만으로
   판단하게 지시한다.
2. **읽기(read)** — 결정론이다. 모델을 부르지 않고 호스트만 보고 분기한다
   `[코드]` `local_runner/page_fetch.py:150-154`
   (`fetch_event_text(*, url)`): 인스타·X 캡션 경로(og:description 메타
   태그 파싱)와 일반 웹 경로(og:title/title·meta description) 중 하나로만
   간다.
3. **해석(interpret)** — 도구 없는 모델 호출이다. 읽기 단계가 낸 텍스트를
   데이터로만 받아 공식 여부와 행사 필드를 구조화 JSON으로 낸다 `[코드]`
   `local_runner/caption_interpreter.py:1-3, 15-77`
   (`build_interpretation_prompt`). 실행 시 `--tools TodoWrite,TodoWrite`로
   호출해 실질적으로 쓸 수 있는 도구가 없다 `[코드]`
   `local_runner/exploration_flow.py:120-127`(`_default_interpret`).

### 공식 여부 판단은 해석 단계에 있다

탐색 단계는 이 환경에서 페이지를 열 수 없어(위 프롬프트 명시) 본문 근거를
낼 수 없다. 그래서 탐색 프롬프트는 "공식 여부는 이 단계에서 판단하지
않는다. … 행사가 공식인지 비공식인지, 그 근거가 무엇인지는 본문을 직접
읽는 다음 해석 단계가 정한다"고 명시적으로 금지한다 `[코드]`
`local_runner/claude_code_adapter.py:107-110`. 판단(`judgment`:
official/unofficial/unclear)과 본문 인용 근거(`official_basis`, ≤200자)는
해석 단계 프롬프트에서만 요구한다 `[코드]`
`local_runner/caption_interpreter.py:50-55`. 서버는 이 판단값을 그대로
믿지 않고, `unofficial`·`unclear`일 때만 검토 메모 앞머리에 판단과 근거를
붙여 운영자가 보게 한다(그 외에는 접두를 붙이지 않는다) `[코드]`
`drafts/agent_drafts.py:55-60, 136-145`.

### 서버는 인스타·X를 절대 가져오지 않는다

계정형 후보 URL이 제출돼도 서버는 목록형 8단계 검증(가져오기 포함)을
타지 않고, `SNS_HOSTNAMES`에 속한 호스트는 존재 재확인 자체를 건너뛴다
`[코드]` `drafts/agent_drafts.py:200-205`(`submit_agent_draft`) — 일반 웹
호스트만 `validate_fetch_url`·`RobotsChecker`·`fetch_html`을 탄다. 이
계약은 호출 여부를 직접 단언하는 테스트로 고정돼 있다 `[코드]`
`tests/drafts/test_agent_drafts.py:423`
(`test_일반_웹_URL_제출은_서버가_존재를_재확인하고_인스타_URL_제출은_fetch를_호출하지_않으며_안전하지_않은_URL은_거부된다`).

### 계정형 소스는 비활성으로 등록된다

인스타·X 계정을 새 수집처로 제안하면 호스트 allowlist·핸들 경로 형식·
중복만 검사하고, 가져오기·robots.txt 확인 없이 `DraftSource(enabled=False)`
로 만든다 `[코드]` `drafts/candidate_validation.py:344-386`
(`register_account_source`). 스태프가 대시보드에서 직접 활성화해야 실제
수집이 시작된다. 목록형·계정형 분기는 러너가 아니라 서버가 결정한다
`[코드]` `drafts/runner_views.py:125-131`
(`RunnerCandidateSubmitView.post` — `source_type`이
`DraftSource.ACCOUNT_SOURCE_TYPES`면 `register_account_source`, 아니면
기존 `submit_candidate`).

### 공개 함수 시그니처(동결)

다음 트랙이 이 위에 얹는다. 시그니처를 바꾸면 이 문서와 아래 시그니처를
참조하는 테스트를 함께 갱신해야 한다.

- `drafts/agent_drafts.py`
  - `parse_agent_draft_payload(*, payload)` — 스키마 검사·정제, `(cleaned,
    stage)` 튜플 반환(`stage`가 `"schema"`가 아니면 통과)
  - `submit_agent_draft(*, run_id, lease_token, payload)` — 임대 확인 →
    서버 재확인(SNS 제외) → 임대 재확인·중복·상한 확인·`EventDraft` 생성,
    `(draft, created)` 튜플 반환
- `local_runner/page_fetch.py`
  - `fetch_event_text(*, url)` — 호스트로 캡션/일반 웹 분기, 텍스트 또는
    `None`(추출 실패) 반환
- `local_runner/caption_interpreter.py`
  - `build_interpretation_prompt(*, vocab, today, recent_drafts, text,
    platform)` — 해석 프롬프트 문자열 생성
  - `_local_precheck(*, interpreted, source_text, vocab)` — 어휘·기간·
    장소명 원문 대조 앞단 필터(서버 재검증을 대체하지 않음)
  - `should_submit(*, interpreted)` — `is_event`이고 제목이 비어있지 않을
    때만 `True`
  - `run_agent_interpretation(prompt, execute=None)` — 실행+JSON 파싱+
    보정 재시도 1회
- `drafts/candidate_validation.py`
  - `register_account_source(*, run_id, lease_token, payload)` — 계정형
    소스 전용 등록, 목록형 `submit_candidate`와 별도 함수

### 러너 실행 시 조각이 이어지는 흐름

`local_runner/runner.py`의 `_run_once`가 폴마다 heartbeat를 보내고 작업을
`claim`한 뒤, `build_exploration_prompt`로 탐색 프롬프트를 만들어
`_run_exploration_agent`로 실행한다(도구 `WebSearch,WebFetch` +
`--strict-mcp-config`). 결과를 `parse_exploration_output`으로 이벤트·소스
목록으로 정리한 뒤 `_process_run` → `run_exploration_flow`
(`local_runner/exploration_flow.py`)에 넘긴다. 이 함수가 이벤트마다
`fetch_event_text`(읽기) → `_default_interpret`(해석, 내부에서
`build_interpretation_prompt` + `run_agent_interpretation` + 로컬 사전검사
호출) → `should_submit` 순서로 걸러 통과한 것만 `client.submit_event`로
서버에 보낸다. 서버는 `drafts/runner_views.py`의 러너 API를 거쳐
`submit_agent_draft`(위 SNS 제외 규칙 적용)로 최종 검증·저장한다. 소스
후보는 별도로 `client.submit_candidate` → `RunnerCandidateSubmitView`가
목록형/계정형으로 분기해 처리한다. 제출 도중 서버가 409(임대 상실)를
내면 `LeaseLostError`로 그 실행 처리를 즉시 멈추고 완료 보고를 생략한다.

### 함정과 실측

- **도구 제한 인자의 함정** `[실측 2026-09-11]`: `claude` CLI의 `--tools`는
  쉼표로 구분된 유효한 이름이 둘 이상일 때만 실제로 제약이 걸린다. 빈
  문자열이나 단일 값은 조용히 무시돼 셸·파일 쓰기까지 기본 도구 전체가
  열린다. 그래서 해석 호출은 무해한 도구 이름을 일부러 두 번 적어
  `"TodoWrite,TodoWrite"`로 넘긴다 `[코드]`
  `local_runner/exploration_flow.py:122-127`. 이 중복은 실수가 아니다.
- **호스트마다 사용자 에이전트가 다르다** `[실측 2026-09-11]`: 인스타는
  브라우저 UA를 쓰면 `og:description` 메타 태그 자체가 안 나와 러너
  자체 식별 UA(`TakuLifeRunner/1.0`)를 쓰고, 일반 웹은 반대로 브라우저 UA를
  써야 응답이 온다 `[코드]` `local_runner/page_fetch.py:28-38`.
- **페이지 열기 도구가 전역 거부 목록에 있다** `[실측]`: `WebFetch`는
  `--tools`에 남겨 둬도 이 실행 환경의 전역 설정 거부 목록에 걸려 하위
  설정으로 못 뒤집는다 — 위쪽 "격리 권고" 정정 절 참고. 인자에 남은
  `WebFetch`는 현재 죽은 값이다.
- **URL 안전 판정이 서버와 러너에 복제돼 있다.** 러너가 Django·서버 도메인
  모듈을 임포트할 수 없어서다 `[코드]` `local_runner/url_safety.py:1-4`.
  두 파일의 실행 로직 줄이 문자 그대로 일치하는지 지키는 가드 테스트가
  있다 `[코드]` `tests/local_runner/test_url_safety_parity.py`
  (`test_서버와_러너의_URL_안전_판정_로직이_문자_그대로_일치한다`).
- **계정형 호스트 목록도 두 곳에 있다.** 같은 이유다 — 서버
  `drafts/candidate_validation.py:60-65`(`_ACCOUNT_SOURCE_ALLOWED_HOSTS`,
  instagram·x만)와 러너
  `local_runner/page_fetch.py:16-23`(`_CAPTION_HOSTNAMES`, twitter.com
  구형 도메인까지 포함) `[코드]`. url_safety와 달리 **이 두 목록은 문자
  일치를 강제하는 가드 테스트가 없다** `[실측: 저장소 전수 검색 결과
  0건]` — 한쪽만 고치면 조용히 갈라진다.
- **존재 검사와 생성 사이의 경합은 run 락이 막지 못한다** `[실측
  2026-09-14]`: `submit_agent_draft`가 `existing` 조회로 못 본 `source_url`을
  스태프가 수동으로 먼저 생성해 커밋하면, 뒤이은 `create_draft_from_fields`가
  unique 위반으로 `DraftCreationDuplicateError`를 던진다. 이를 잡아
  기존 행을 재조회해 `(existing, False)`로 정규화한다 — 러너는 500 대신
  duplicate 응답을 받는다. 회귀:
  `tests/drafts/test_agent_drafts.py::test_경쟁으로_기존_행을_놓친_제출은_예외_대신_기존_드래프트를_반환한다`.
- **탐색 요청 생성과 감사 로그는 한 트랜잭션이다** `[실측 2026-09-14]`:
  스태프 탐색 요청 뷰는 `create_run`과 `SOURCE_DISCOVER` 감사 로그 기록을
  하나의 `transaction.atomic()`으로 묶는다(`staff/views/_helpers.py`의
  "로그 실패 시 행동도 롤백" 계약). 회귀:
  `tests/staff/test_staff_source_discovery_request_view.py::test_탐색_요청_감사로그_삽입이_실패하면_실행_생성도_함께_실패한다`.

## 트랙 33: 국내·미종료 필터(2026-09-15~2026-09-16)

키워드 탐색이 만든 드래프트 중 해외 개최·이미 종료된 행사, 해외 수집처가
섞여 들어오는 문제를 막는다. 서버·러너 양쪽에 적용한다.

### 제외는 오류가 아니다

러너가 제출한 이벤트가 정책상 제외 대상이면 서버는 4xx가 아니라 **200**과
`{"status": "excluded", "reason": "ended"|"overseas"}`로 답한다 `[코드]`
`drafts/runner_views.py`(`AgentDraftExcludedError` 처리 분기). 4xx로 내리면
러너가 이를 실패로 세어, 정책대로 전부 걸러진 실행이 실패로 기록된다.

### 국내 판정은 서버가 재검증할 수 없는 러너 필드다

이벤트는 `venue_country`가 정확히 `"not_kr"`일 때만 제외하고, 없음·
`"unclear"`·enum 밖 값·대소문자나 공백이 다른 값은 모두 제출한다(불확실하면
행사를 놓치는 비용이 더 크다는 사용자 결정) `[코드]` `drafts/agent_drafts.py`
(`_exclusion_reason`). 소스 후보는 반대로 `source_country`가 정확히
`"kr"`일 때만 등록하고 그 외(없음 포함)는 모두 제외한다 — 소스는 한 번
잘못 승격되면 실행마다 해외 드래프트를 반복 생성하기 때문이다 `[코드]`
`drafts/candidate_validation.py`. 양쪽 모두 `.strip()`·`.lower()` 같은
정규화 없이 문자 그대로 비교한다 `[코드]` — 정규화를 넣으면 대소문자·공백만
다른 값을 오판하게 되므로 일부러 하지 않는다. 러너 해석 프롬프트는
`local_runner/caption_interpreter.py`에서 `venue_country`를 같은 세 값
(`kr`/`not_kr`/`unclear`)으로만 판정하게 지시한다.

### "오늘"은 서버·러너 모두 한국 시간 기준이다

서버는 `timezone.localdate()`(`TIME_ZONE = "Asia/Seoul"` `[코드]`
`config/settings.py`)를, 러너는
`datetime.now(ZoneInfo("Asia/Seoul")).date()`(`_KST` `[코드]`
`local_runner/exploration_flow.py`)를 각각 쓴다. 러너를 돌리는 개인 맥의
OS 시간대가 UTC 등 다른 값이어도 종료 판정이 서버와 갈리지 않게 하기
위해서다.

### 실행 상태는 후보 결과와 이벤트 결과의 결합이다

`complete_run`은 후보 결과(없음/전부 승격/전부 실패/혼합)와 이벤트 결과
(없음/실패 없음/실패 있음·생성 없음/실패 있음·생성 있음)를 각각 판정한 뒤
결합해 실행 상태를 정한다 `[코드]` `drafts/discovery_runs.py`. 실패가
없으면 생성이 0건이어도 SUCCEEDED다 — 제외는 실패가 아니기 때문이다.
실행 기록에는 `SourceDiscoveryRun.events_excluded`가 함께 저장된다.

### 읽을 수 없는 날짜는 거부가 아니라 정정이다

날짜 값이 비었거나 형식이 잘못됐으면 그 값을 비우고 원값을 메모에 남긴다
(`_normalize_unreadable_date` `[코드]` `drafts/agent_drafts.py`) — 그대로
두면 저장 시점에 예외가 났다. 종료 판정 자체도 날짜를 못 읽으면 제외하지
않고 제출한다(`_exclusion_reason`이 파싱 실패 시 `None` 반환).

### 서버 수집 경로는 수집 전용 생성 함수에서만 필터를 적용한다

`create_collected_draft_from_url`(`drafts/services.py`)만 "제목·본문에
한글이 없으면 제외"(`non_korean`)와 "본문에 나온 가장 늦은 날짜가 오늘
이전이면 제외"(`ended`)를 적용한다. 날짜 판정은 `drafts/extraction.py`의
`latest_mentioned_date(text)`가 본문 전체에서 가장 늦은 날짜 하나를
고르는 방식이다 — 규칙 추출기가 뽑는 시작·종료일에는 게시일이 섞여
믿을 수 없어 본문 전체를 다시 본다는 실측 근거가 있다(사용자 결정 기록
D9, `prompt_plan.md` 트랙 33 참고). 스태프가 URL을 직접 골라 추가하는
경로(`staff/views/draft_api.py`)에는 이 필터를 적용하지 않는다 — 사람이
이미 골라 확인한 URL이기 때문이다.

### 두 경로의 판정 축은 다르다 — 잔여 오탐·미탐

러너(키워드 탐색) 경로는 **개최지**(`venue_country`)와 **종료일(없으면 시작일)**로,
서버 수집 경로는 **한글 유무**와 **본문의 가장 늦은 날짜**로 판정한다. 서버
수집 경로에는 모델 판정이 없고 결정론 지역 추출은 해외를 판정할 수 없어서다
(`drafts/extraction.py` `_detect_region`은 서울·부산·인천 문자열만 본다
`[코드]`). 그래서 같은 문서가 경로에 따라 다르게 처리될 수 있다:

- 한국어로 쓴 **해외** 행사 페이지: 러너 경로는 제외, 서버 수집 경로는 한글이
  있어 **통과**한다 — 검수 큐에서 걸러야 하는 잔여 오탐이다.
- 영어로만 쓴 **국내** 행사 페이지: 러너 경로는 제출, 서버 수집 경로는
  `non_korean`으로 **제외**한다 — 잔여 미탐이다. 필요하면 스태프 URL 직접
  추가로 넣는다(그 경로는 필터를 적용하지 않는다).

이미 만들어진 드래프트와 등록된 소스는 이 필터로 소급 정리되지 않는다.
해외 소스는 `DraftSource.enabled=False`로 직접 비활성화해야 하며, 운영 DB에
해외 소스가 남아 있는지는 배포 후 수동으로 확인한다.

## 트랙 35: 드래프트 실행 결과 기록·대시보드 표시(2026-09-18)

행사별 결과를 실행 기록에 남기고 대시보드에 보여준다. 같은 트랙에서
2026-09-17 실기동 검토가 찾은 결함 5건(러너가 서버 판정을 무시, 탐색
프롬프트에 오늘·국내 조건 없음, X 게시물 읽기 미구현, 사유 로그 없음,
실패 소스 무조건 재검증)도 함께 고친다.

### `event_outcomes` 계약은 항목 단위로 버리고 200을 유지한다

outcome 5종(created/duplicate/excluded/failed/skipped)과 outcome별 허용
reason 집합은 서버 `EVENT_OUTCOME_REASONS`
`[코드]` `drafts/discovery_runs.py:29-43`가 소유한다. 러너 쪽 어휘(실제로
낼 수 있는 (outcome, reason) 짝)는 `local_runner/exploration_flow.py`가
`_record_outcome` 호출로 낸다 `[코드]`(예: 210·219·228행). 두 어휘가
갈라지지 않게 `tests/local_runner/test_outcome_vocabulary_parity.py`가
러너 소스를 AST로 읽어 서버 허용목록과 대조한다 `[코드]`.

완료 API는 리스트 타입이 아니면 기존처럼 400이지만, 리스트 안 개별
항목이 dict가 아니거나 url·outcome·reason 형식·허용목록을 벗어나면 그
항목만 조용히 버리고 200을 유지한다 `[코드]` `drafts/discovery_runs.py`
`_clean_event_outcomes`(57~96행). 완료를 400으로 내리면 러너
`RunnerClient.complete`가 예외를 내 `complete_run`이 실행되지 않아
실행이 CLAIMED로 남고, 임대 `LEASE_SECONDS=1800`초
`[코드 drafts/discovery_runs.py:19]` × `MAX_LEASES=2`
`[코드 drafts/discovery_runs.py:22]` 동안 새 탐색이 막히기 때문이다.
url은 `sanitize_text` 적용·http(s) 스킴·200자 이하만 통과하고
(`_clean_event_outcomes` 74~78행), `outcome=="created"`인 항목은 이
실행이 실제로 만든 드래프트 source_url과 대조해 없으면 버린다(87행,
러너 문자열을 그대로 믿지 않는다). 최대 20건까지만 남기고 초과분은
절단한다 — `_MAX_EVENT_OUTCOMES = 20`
`[코드]` `drafts/discovery_runs.py:46`.

### 건너뛴 항목은 attempted·excluded 둘 다에 들어간다

`events_excluded` 정의(`drafts/models.py:141`)와 일치시키고, 차단
호스트를 건너뛸 때 이미 attempted+failed로 세는 기존 패턴(`
local_runner/exploration_flow.py:205-211`)과 대칭을 맞춘다.

### 건너뛰기는 코드가 재확인할 수 있는 두 사유만 믿는다

탐색이 낸 `why_excluded`를 문자열 그대로 믿지 않고, `ended`는 같은
이벤트의 `end_date`(ISO)가 오늘(KST)보다 이전인지, `overseas`는 URL
호스트가 같은 출력의 `source_country=="not_kr"` 소스 호스트와 실제로
겹치는지 코드로 다시 본다 `[코드]` `local_runner/exploration_flow.py`
`_agent_marked_ended`(29~41행)·`_agent_marked_overseas`(44~49행). 되돌릴
때는 `SKIPPABLE_AGENT_REASONS = frozenset({"ended", "overseas"})`
(26행)에서 값을 빼면 된다. `today_kst()`는
`local_runner/clock.py`(단일 시각원, `_KST = ZoneInfo("Asia/Seoul")`)만
쓴다 `[코드]`.

### 탐색 프롬프트는 오늘·국내 조건을 명시로 받는다

`local_runner/claude_code_adapter.py` `build_exploration_prompt`(83행)가
`today` 인자를 받아 "대한민국에서 열리는 행사만 `is_event`를 참으로
하라"는 조건과 `why_excluded` 허용값(ended·overseas 포함), 이벤트마다
`end_date`(YYYY-MM-DD, 모르면 빈 문자열)를 요구한다 `[코드]`. `today`는
`local_runner/runner.py:156`에서 `today_kst().isoformat()`으로 채운다
`[코드]`.

### 읽기 단계의 예상된 예외는 그 행사만 죽이고 계속한다

기준선 실기동(2026-09-18, 실행 16)에서 행사 하나의 읽기 예외가 실행
전체를 `exploration_error`로 죽여 결과 4건만 남고 5번째 항목은 예외
클래스명 로그조차 없었다 `[문서 prompt_plan.md 트랙 35 S1c, 원 실측
2026-09-18]`. 지금은 읽기 단계에서 예상되는 예외
(`httpx.HTTPError`·`InvalidFetchUrlError`·`UnsafeFetchUrlError`·
`ResponseTooLargeError`·`EmptyExtractionError`·`OSError`)를
`_EXPECTED_FETCH_ERRORS`로 묶어 그 항목만 failed·`fetch_error`로 기록하고
다음 항목을 계속 처리한다 `[코드]`
`local_runner/exploration_flow.py:151-158,221-229`(본문 없이
예외 클래스명·호스트만 WARNING 1줄, 225~227행). 러너 `_process_run`의 두
실패 경로도 원인 예외 클래스명만 WARNING으로 남긴다(본문 금지)
`[코드]` `local_runner/runner.py:88,105`. 서버 완료 허용목록
`_ALLOWED_FAILURE_KINDS`에 러너가 실제 보내는 `exploration_error`가
있다 `[코드]` `drafts/discovery_runs.py:25`.

### X 게시물은 syndication 엔드포인트로만 읽는다

x.com·twitter.com의 `/<handle>/status/<숫자 id>` 경로만
`cdn.syndication.twimg.com/tweet-result`(고정 호스트)로 요청해 본문을
돌려주고, 그 외 경로(프로필·미디어 등)는 요청 자체를 보내지 않는다
`[코드]` `local_runner/page_fetch.py:59-61,127-184`(정규식
`_X_STATUS_PATH_RE`, 토큰 계산 `_x_syndication_token` 127~147행, 요청·응답
처리 `_fetch_x_post` 150~184행). 토큰 없이
호출하면 빈 본문(2바이트 `{}`)이 온다 `[문서 prompt_plan.md 트랙 35 S5,
원 실측 2026-09-18 curl]`; 실 게시물 URL 2건은 200으로 응답했다(같은
출처). 인스타 캡션 경로는 이 트랙에서 바꾸지 않았다.

### 소스 후보 robots 실패는 불허와 분리한다

robots.txt를 가져오지 못하면(네트워크·인증서 오류) 새
`FailureStage.ROBOTS_FETCH_FAILED`, robots.txt가 실제로 막으면 기존
`FailureStage.ROBOTS`를 쓴다 `[코드]` `drafts/robots.py:28-29,76-79`,
매핑은 `drafts/candidate_intake.py:14-16`. 마이그레이션
`drafts/migrations/0013_alter_sourcecandidate_failure_stage.py`가
`AlterField`로 반영한다.

### 최근 결정적 실패 재사용은 세 단계로만 좁힌다

같은 URL이 7일 안에 robots·sample_mismatch·listing_extraction으로
실패했으면 네트워크 없이 같은 단계로 새 실패 행을 만든다 `[코드]`
`drafts/candidate_validation.py:67-89`(`REUSABLE_FAILURE_STAGES`·
`REUSE_WINDOW = timedelta(days=7)`). **착수 중 정정**: 초안은
`url_safety`·`not_domestic`도 포함했으나, `url_safety`는 DNS 조회
실패(OSError)가 같은 단계에 섞여 일시 오류일 수 있고, `not_domestic`은
네트워크 없는 payload 필드 검사라 재사용 이득이 없이 다음 제출의
교정값을 덮으므로 둘 다 뺐다(같은 파일 62~66행 주석에 근거를 남겼다).
`robots_fetch_failed`·`fetch`·`sample_canary`도 일시 오류일 수 있어
재사용 대상이 아니다.

### 대시보드는 결과별 건수와 행사 단위 상세를 한 쿼리로 낸다

`drafts/queries.py` `recent_discovery_runs`(183~217행)가 후보
승격·실패 건수(조인 곱 방지를 위해 `distinct=True`)와 `run.events`
기준 행사 생성 수를 한 쿼리에서 annotate하고, `event_outcomes`가 비어
있던 옛 실행은 제외·실패 건수를 `None`으로 내 화면이 "-"로 표시한다.
행사별 상세 행은 `_outcome_rows`(158~180행)가 이미 로딩된
`event_outcomes` JSON만 써서(추가 쿼리 없이) 호스트+경로만 노출하는
`_display_url`(151~155행, `hostname` 사용 — 계정 정보가 섞인
`netloc`이 아니다)과 한국어 라벨(`EVENT_OUTCOME_LABELS`·
`EVENT_OUTCOME_REASON_LABELS`, 122·142행)로 만든다. 후보 실패 단계
라벨에 `not_domestic`·`robots_fetch_failed` 분기가 빠져 빈 칸으로
보이던 문제(착수 중 발견, 같은 종류)도 같은 트랙에서 채웠다 `[코드]`
`templates/staff/dashboard.html:310`.

### 실기동 대조

`[문서 prompt_plan.md 트랙 35 검증절, 원 실측 2026-09-18, 검색어
"치이카와 팝업스토어"]` — 기준선(수정 전, 실행 16): 결과
`exploration_error`로 실패, 소요 7분 39초, attempted 5건 / failed 1건 /
excluded 3건, 결과 4건 기록. 수정 후(실행 17): `partially_failed`(후보
실패만), 소요 1분 7초, attempted 6건 / failed 0건 / excluded 5건(그중
건너뜀 4건), 드래프트 1건 생성(아이파크몰 용산점), 건너뛴 4건 전수
확인 결과 오제외 0건. 이 수치는 이 문서 작성 세션에서 재실행해 얻은
것이 아니라 트랙 35 계획서에 이미 기록된 값을 그대로 옮긴 것이라
[문서] 태그를 쓴다 — 후속 세션이 이 표를 근거로 새 작업 규모를 정할
때는 재측정해야 한다.

### 이연

- `event_outcomes` 별도 모델 승격 — 트리거: 실행 간 URL 실패 조회 요구.
- 주관 사유(`same_name` 등) 건너뛰기 평가셋 — 트리거: 누적 실행 여러
  번 뒤 에이전트 사유와 서버 판정 일치율 확보(권고 3~5회).
- 캡션 경로 응답 크기 상한·DNS 리바인딩(TOCTOU) 하드닝.

## 트랙 39: 러너 진행 상태 실시간 표시·즉시 오프라인(2026-09-20)

대시보드 새로고침 없이 러너 진행 상태(검색 중·행사 확인 중·소스 후보
제출 중·완료 보고 정리 중)를 보여주고, 러너 종료 시 120초 신선도 대기
없이 즉시 오프라인으로 반영한다. 계획 정본은 `prompt_plan.md` 트랙
39(v1.1, 사용자 결정 1~6 확정)이며, 아래는 이 트랙이 코드에 새로 고정한
가드레일이다. **갱신(구현 완료, 2026-09-20)**: 착수 절 작성 시점에
"아직 없다"고 적었던 `runner_live_summary()`·`DISCOVERY_PHASE_LABELS`
(`drafts/queries.py`)와 `local_runner/progress.py`는 모두 구현·회귀
Green으로 확정됐다. `DiscoveryRunnerStatus` 5필드·
`record_heartbeat`/`record_offline`/`runner_is_online`·
`RunnerOfflineView`(204)는 착수 전부터 코드에 있었다 `[코드]`
`drafts/models.py`·`drafts/discovery_runs.py`·`drafts/runner_views.py`.
아래 각 절은 착수 시점의 계획서 계약이 아니라 구현된 실제 코드 위치를
가리키도록 갱신했다.

### phase 어휘 5종과 옛 러너 하위 호환

`DiscoveryRunnerStatus.Phase`는 idle·exploring·reading·submitting·
completing 5종만 허용한다 `[코드]` `drafts/models.py`
`DiscoveryRunnerStatus.Phase`. 어휘 밖 값은 저장하지 않고 `invalid
heartbeat phase` 경고 접두어로만 남긴다 `[코드]` `drafts/discovery_runs.py`
`normalize_heartbeat_phase`. phase가 없는 heartbeat(옛 러너)는 이전
phase 값을 덮지 않는다 — `record_heartbeat`가 `phase is not None`일
때만 `defaults["phase"]`를 채운다 `[코드]` `drafts/discovery_runs.py`
`record_heartbeat`. 서버 `drafts/queries.py`의 `DISCOVERY_PHASE_LABELS`와
러너 `local_runner/progress.py`의 `PHASE_LABELS`는 문자 그대로
일치해야 하며, 이 일치는 AST 대조 테스트
`tests/local_runner/test_phase_vocabulary_parity.py`(트랙 35
`test_outcome_vocabulary_parity.py`와 같은 방식)로 고정한다 `[코드]`.

### detail은 러너가 조립한 완성 문장, 서버는 정제만

`detail`은 서버가 어휘·인덱스로 재조립하지 않고 러너가 이미 완성한
한국어 문장을 그대로 받는다(오케스트레이터 결정 D1). 서버는
`clean_heartbeat_detail`로 제어문자 제거 + 200자 절단만 하고 문장
내용은 판단하지 않는다 `[코드]` `drafts/discovery_runs.py`
`clean_heartbeat_detail`(`sanitize_text` 위임). 화면 표시 경로는 두
갈래로 갈라진다: 서버 초기 렌더(Django 템플릿)는 자동 이스케이프를
쓰고, JS 갱신 경로(`static/js/staff/discovery_live.js`)는
`textContent`·`dataset` 대입만 쓰고 innerHTML이나 문자열 조립으로 DOM에
넣지 않는다 `[코드]` — `<script>`가 든 detail이 JSON에는 원문(제어문자만
제거) 그대로 실려도 화면에 태그로 실행되지 않게 하는 XSS 가드다. 브라우저
실측으로 detail `<script>alert(1)</script>` 제출 시 progress 텍스트가
원문 그대로 표시되고 요소 생성 0건임을 확인했다 `[실측 2026-09-20]`.

### `offline_at` 규칙과 `create_run` 단일 판정

online 판정은 "120초 이내 heartbeat" AND "`offline_at`이 없거나
`offline_at` < `last_heartbeat_at`" 두 조건을 모두 만족해야 한다
`[코드]` `drafts/discovery_runs.py` `runner_is_online`. `create_run`은
잠근 `DiscoveryRunnerStatus` 행으로 이 함수 하나만 호출해 온라인
여부를 판정한다 `[코드]` `drafts/discovery_runs.py` `create_run` —
신선도 검사를 별도로 인라인하면 오프라인 러너에도 검색어 실행이
생성될 수 있다는 것이 착수 전 재확인된 결함이었다(계획서 정정 3).

### `runner_shutdown`은 즉시 실패, 자동 재시도 없음

`_ALLOWED_FAILURE_KINDS`에 `runner_shutdown`이 등록돼 있다 `[코드]`
`drafts/discovery_runs.py`. 러너가 진행 중인 run을 안고 Ctrl+C로
종료하면(`local_runner/runner.py` `main()`의 `except KeyboardInterrupt`
분기가 `_report_shutdown`을 호출) 그 run은
`runner_shutdown` 사유로 즉시 실패 처리되며, 서버·러너 어느 쪽도 자동
재시도하지 않는다 — 재탐색은 스태프가 다시 요청한다(사용자 결정 2).
부분 집계는 마지막으로 처리한 항목 인덱스(`last_index`)로 근사하며
정확한 tally는 이 트랙의 Known gap이다(결정 D4). 실기동에서 탐색 중
SIGINT 시 이 경로가 실제로 타는 것을 확인했다 `[실측 2026-09-20]`
(아래 "종료 시퀀스" 절 실기동 로그 참고).

### live 계약은 순수 JSON, HTML 필드 없음

`GET /staff/api/discovery/live/`(url name `staff:discovery-live`,
`staff/urls.py`, view `staff/views/discovery_live.py`
`StaffDiscoveryLiveView` — 결정 D11)는 `IsAdminUser` +
`throttle_scope="staff_discovery_live"`로
보호되며, `{"runner": {...8키...}, "runs": [...], "server_time":
...}`만 반환한다(사용자 결정 6으로 초안의 `runs_html`·`runner_html`
필드는 폐기). `runner` 8키는 online·phase·phase_label·detail·
progress_visible·current_run_id·last_heartbeat_at·active(pending/claimed
실행 존재 여부, 결정 D8) `[코드]` `drafts/queries.py`
`runner_live_summary()`. `runs`는 트랙 35
`recent_discovery_runs()`가 만든 행을 `drafts/serializers.py`
`DiscoveryRunSummarySerializer`(id·status·status_label·tone·query·
created_at·promoted_count·failed_count·events_created·events_excluded·
events_failed·error_summary·outcomes 13필드, `outcomes`는 행사별 상세
`DiscoveryRunOutcomeSerializer`의 `display_url`·`outcome`·
`outcome_label`·`tone`·`reason_label` 5키 목록)로 옮긴다 `[코드]`.
`staff_discovery_live:
"40/minute"`은 `DEFAULT_THROTTLE_RATES`(`config/settings.py`)에 등록해야
하며 미등록이면 `ScopedRateThrottle`이 예외를 낸다. `created_at`·
`last_heartbeat_at`은 DRF `DateTimeField` 기본 ISO 8601로,
`server_time`은 `timezone.localtime()`(`staff/views/discovery_live.py`
`StaffDiscoveryLiveView.get`)으로 실려 셋 다 같은 +09:00 표기를 쓴다
`[코드]`. JS는 문자열 슬라이스로 `y.m.d H:i` 형태만
만든다(결정 D12) — 서버 파싱·재변환은 하지 않는다.

### 인증 만료는 대시보드 폴링을 멈춘다

`static/js/staff/discovery_live.js`는 폴링 응답이 401·403이거나
`window.TakuAPI.classify(result)`가 `"auth"`면 폴링을 멈춘다 `[코드]`.
이 뷰의 `IsAdminUser`는 스태프 권한이 없는 인증 세션에도 403을 낸다
(`PermissionDenied`) — DRF에서 인증 실패(401)와 권한 실패(403)를
`classify`가 둘 다 `"csrf"`로 분류하기 때문에, JS는 상태 코드
401/403과 `classify` 결과 중 하나만 맞아도 멈추도록 두 조건을 OR로
묶는다. 브라우저 실측: 403 인증 만료 주입 3.69초 안에 만료 안내 문구
표시, 이후 9초 동안 호출 0회.

### 러너 전송 간격: phase 전이는 즉시, detail만 바뀌면 5초

phase 값이 바뀌는 전이는 간격과 무관하게 heartbeat 1회를 즉시
보낸다(AC3 ≤5초 근거). 같은 phase 안에서 detail만 바뀌면 마지막 전송
후 5초 미만일 때 보류한다(결정 D2). 터미널 INFO 줄은 phase 또는
detail이 바뀔 때마다 1줄 남기며 보류하지 않는다 — 대시보드 폴링
간격(온라인 또는 pending/claimed 존재 시 5초, 그 외 20초, WED·BIR
채택)과는 별개다. 이 간격은 러너 스로틀 `discovery_runner`
60/minute(heartbeat·claim·candidates·drafts·complete 공유,
`config/settings.py`)를 넘지 않도록 즉시 전송 최대 12/분 + 티커
20초당 1회로 계산했다(정정 5).

### 종료 시퀀스: 완료 보고 → 오프라인 보고, 두 번째 Ctrl+C는 즉시

SIGINT·SIGTERM은 `KeyboardInterrupt`로 통일해 받는다 `[코드]`
`local_runner/runner.py` `_handle_sigterm`(SIGTERM 핸들러가
`raise KeyboardInterrupt()`, SIGINT는 파이썬 기본 처리로 이미
`KeyboardInterrupt`). 첫 Ctrl+C에서는 진행 중이던 run이 있으면
`_report_shutdown`이 `complete(failed, "runner_shutdown",
events_attempted=progress.last_index or 0)`를 보낸 뒤
`send_offline(timeout=_SHUTDOWN_TIMEOUT_SECONDS)`을 보낸다(각 호출
3초 타임아웃, `httpx.HTTPError`는 로그만 남기고 전파하지 않는다) `[코드]`
`local_runner/runner.py` `_report_shutdown`. 대기 중이면
`progress.run_id`가 `None`이라 `complete` 호출 없이 `send_offline()`만
보낸다. 두 번째 Ctrl+C는 오프라인 보고를 생략하고
즉시 종료한다(`main()`의 `except KeyboardInterrupt` 블록 실행 도중
다시 `KeyboardInterrupt`가 나면 그 블록 자체가 중단된다) — 이 경우
대시보드는 120초 신선도 만료로 오프라인을 알게 된다(제외 항목).

**착수 중 발견·수정 3건(같은 트랙, 2026-09-20)**: (1) `_run_once`가
`KeyboardInterrupt` 시 `progress.end_run()`을 호출해 `run_id`를
비웠던 결함(RP-R05c) — `finally` 절에 `interrupted` 플래그를 추가해
인터럽트일 때는 `end_run()`을 건너뛰도록 고쳤다(커밋 `7a96ef31`). (2)
`_report_shutdown`이 `progress.last_index`(읽기 단계 시작 전엔 `None`)를
그대로 보내 서버 정수 필드가 400을 내던 결함 — `or 0`으로
방어했다(커밋 `549af841`). (3) `run_exploration_flow`의
`_submit_sources`가 progress 콜백을 실제로 호출하지 않아 "소스 후보
제출 중" 문구가 실기동에서 절대 뜰 수 없었던 결함(가짜 흐름으로 전체를
대체한 테스트가 이를 가리고 있었다) — 실제 제출 루프에 progress 인자를
꿰었다(커밋 `c865d4c0`). 실기동으로 SIGINT(탐색 중) 왕복을 수정 전·후
모두 확인했다(아래 Evidence 절의 2026-09-20 실기동 로그 참고).

### 배포 순서: 서버 먼저, 러너는 그 뒤 재시작

서버를 먼저 배포한다 — 옛 러너(phase·detail 없는 heartbeat)는
`record_heartbeat`가 `phase=None`을 허용하므로 계속 동작한다. 러너는
그 뒤 재시작한다 — 옛 서버(이 트랙 배포 전)가 여분 키를 받으면 무시하고,
`/api/discovery/runner/offline/`가 아직 없던 시절의 서버에 새 러너가
호출하면 404가 나지만 러너는 로그만 남기고 계속 동작한다(DOR).

### Known gap

- `runner_shutdown`으로 종료된 run의 이벤트 집계는 정확한 tally가 아니라
  마지막 처리 인덱스 근사다(결정 D4) — 정확한 집계가 필요해지면 별도
  트랙.
- G2(gunicorn `--timeout` 미설정)는 이 트랙에서 다루지 않는다.
  `docs/backlog.md` G2는 2026-09-20 프로덕션 `DRAFT_DISCOVERY_ENABLED=true`
  전환으로 트리거가 발동한 상태이며, 이 트랙 종료 직후 별도 트랙으로
  진행하기로 사용자가 결정했다(2026-09-20).
- `docs/backlog.md` H8(알림 메일)은 이연 유지 — 이 트랙은 대시보드·러너
  터미널 표시만 다룬다.
- SSE/WebSocket, 정기 스케줄러/자동 시작은 이 트랙 범위 밖이다(계획서
  "제외" 절 — gunicorn sync 워커 3개 구성과 Redis 미보유 비용 정책이
  근거).
- 실기동에서 소스 후보가 실제로 생성된 실행은 없었다(실행 19·20·21 모두
  검색 결과 행사 0건). "소스 후보 제출 중" 문구의 화면 표시는
  `tests/local_runner/test_exploration_flow.py`의
  `test_탐색_흐름이_소스_후보를_제출할_때마다_progress_콜백에_순번과_전체_수를_넘긴다`(RP-R13
  수정 커밋 `c865d4c0`)와, "완료 보고 정리 중" 진행 행에 대한 Django
  shell heartbeat 스크린샷(2026-09-20 브라우저 실측)으로만 확인됐다 — 실제
  러너가 소스 후보를 제출하는 화면은 아직 촬영하지 못했다.
- 스태프 콘솔은 1024px 미만에서 "데스크톱에서 열어주세요" 게이트가
  먼저 뜨므로(기존 설계) 이 트랙의 모바일 뷰포트 검증은 적용 대상이
  아니다.
- 측정 함정: 비대화형 zsh의 `&` 백그라운드 자식 프로세스는 SIGINT
  무시를 물려받고, `uv run` 래퍼 PID에 신호를 보내면 실제 러너
  python 프로세스에 닿지 않는다 — SIGINT 왕복 실측 시
  `.venv/bin/python3 -c 'signal.signal(SIGINT, SIG_DFL);
  os.execv(...)'`로 러너를 재기동해 우회했다(2026-09-20 실기동).

## Evidence

- 사용자 승인(2026-08-20): 기본 수집은 규칙 기반 추출과 관리자 검수를 유지한다.
- 사용자 승인(2026-08-20): LLM은 개인 맥의 로컬 러너에서 새 수집처와 표본 행사
  URL을 찾고, 서버가 검증한 뒤 기존 규칙 기반 경로로 드래프트를 만든다.
- 코드 근거: `drafts/models.py`, `drafts/services.py`,
  `drafts/management/commands/discover_drafts.py`, `staff/views/__init__.py`,
  `config/settings.py`.
- 트랙 30 코드 근거: `drafts/agent_drafts.py`, `drafts/candidate_validation.py`,
  `drafts/runner_views.py`, `local_runner/claude_code_adapter.py`,
  `local_runner/exploration_flow.py`, `local_runner/page_fetch.py`,
  `local_runner/caption_interpreter.py`, `local_runner/url_safety.py`. 전체
  회귀 2680건 통과 `[실측]`(오케스트레이터 실행).
- 트랙 39 사용자 결정(2026-09-20): decisions.md D1~D12, 계획서 사용자 결정
  1~6.
  - 전체 회귀: `uv run pytest -q` 3181 passed / 10 deselected / 91.80초
    `[실측 2026-09-20, 오케스트레이터 실행]`. `manage.py check` 이상 없음,
    `makemigrations --check --dry-run` No changes detected. 여정 e2e
    `uv run pytest -q -m e2e tests/e2e` 10 passed / 12.37초 `[실측
    2026-09-20, 오케스트레이터 실행]`.
  - 브라우저 실측(Chrome DevTools MCP, 로컬 `runserver`, 개발 DB, 뷰포트
    1421x795) `[실측 2026-09-20]`: AC1(온라인→오프라인 반영) 0.66초
    (Django shell `record_offline` 호출 기준), 실제 러너 SIGTERM
    종료 기준 2.00초; AC3(phase 전이 반영, submitting) 1.18초;
    offline→online(20초 폴링 구간, 상한 20초) 17.31초; XSS(detail
    `<script>alert(1)</script>`) progress 텍스트 원문 그대로 표시·요소
    생성 0건; 가시성 숨김(document.hidden) 12초 동안 요청 0회·복귀 후
    53ms 안에 1회; 폴링 백오프 간격 [10, 20, 5, 5, 5]초(500 2회 주입);
    403(`NotAuthenticated`·`PermissionDenied` 둘 다) 주입 시 폴링 정지;
    같은 응답 반복 11초·폴 2회 동안 MutationObserver DOM 변경 0건.
  - 러너 실기동(로컬 `runserver --noreload` + 실제 `local_runner`, 개발
    DB) `[실측 2026-09-20]`: SIGTERM(대기 중) 신호→offline POST 31ms;
    SIGINT(대기 중, 기본 처리기 복원 후) 27ms; SIGINT(탐색 중, 수정
    전) offline POST만 발생·complete 없음·run이 `claimed`로 잔존(결함
    RP-R05c, 같은 트랙에서 수정); SIGINT(탐색 중, 수정 후) 신호→
    complete(runner_shutdown) POST 324ms→offline POST 363ms, run
    `failed`·`error_summary` "러너가 실행 실패를 보고했다
    (runner_shutdown)"·`events_attempted` 0·`runner_is_online` False.
