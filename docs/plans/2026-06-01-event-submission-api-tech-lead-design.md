# OshiLog EventSubmission API Tech Lead Design

Date: 2026-06-01
Role: Tech Lead / Architect
Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## 목적

PO 승인 범위를 기준으로 `EventSubmission` 백엔드 API의 기술 설계를 확정한다.
이 문서는 설계 문서이며, 생산 코드 변경 전 단계 산출물이다.

## 입력 문서

1. `AGENTS.md`
2. `docs/plans/2026-06-01-event-submission-api-po-scope.md`
3. `docs/plans/2026-05-26-oshilog-rest-api-design-plan.md`
4. `docs/project-status.md`

## 승인 범위 재확인

이번 설계가 다루는 범위:

- `POST /api/event-submissions/` (인증 사용자 제보 생성)
- `GET /api/admin/event-submissions/` (관리자 제보 목록)
- `source_url` 필수/스킴 검증
- `pending` 상태 중복 URL 거절
- 테스트 및 문서 업데이트

이번 설계에서 제외:

- 공개(비로그인) 제보
- 제보 승인/반려/드래프트 전환 API
- 비동기 큐, 레이트 리밋, 고급 스팸 방어
- 사용자용 “내 제보 목록” API

## 도메인 경계 및 의존 방향

### 도메인 소유권

- `drafts` 도메인:
  - `EventSubmission` 상태/중복 규칙 소유
  - 제보 생성 유스케이스 소유
  - 관리자 제보 목록 조회 유스케이스 소유
- `accounts` 도메인:
  - 제출자 식별(`submitted_by`)의 사용자 모델 소유
- `core`:
  - 공통 에러 응답 포맷만 제공

### 의존 방향

허용:

- `drafts.views -> drafts.serializers`
- `drafts.views -> drafts.services`
- `drafts.views -> drafts.models`(조회 queryset 제한 목적)
- `drafts.views -> core.errors`
- `drafts.services -> drafts.models`
- `drafts.models -> accounts.User(AUTH_USER_MODEL FK)`

금지:

- `events -> drafts` 신규 의존 추가
- `drafts`에서 `events.services` 호출하여 제보 생성 시점에 발행 워크플로우 결합
- `core`가 도메인 모델 import

비즈니스 로직 배치:

- 중복/상태 규칙은 `drafts.services`에 둔다.
- 뷰는 인증/권한, serializer 검증, 서비스 호출, 응답 매핑만 수행한다.

## 데이터 설계

`drafts.models`에 `EventSubmission` 모델을 추가한다.

필수 필드(초기 범위):

- `source_url`: `URLField`
- `submitted_by`: `ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE)`
- `status`: `pending`, `reviewed`, `rejected` 중 하나 (기본 `pending`)
- `created_at`, `updated_at`

권장 인덱스/제약:

- `status`, `created_at` 인덱스
- 중복 URL 정책은 1차로 서비스 레벨에서 보장
  - 기준: `status=pending`인 동일 `source_url` 존재 시 거절

설계 판단:

- 부분 유니크 제약(예: pending 상태 조건부 unique)은 DB별 동작/이식성 검토가
  필요하므로 현재 범위에서는 서비스 검증 우선 적용
- DB 제약 강화는 Deferred Refactoring으로 분리

## API 설계

### 1) 사용자 제보 생성

- Method/Path: `POST /api/event-submissions/`
- Auth: 로그인 필수
- Request body:
  - `source_url` (required)
- Success:
  - `201 Created`
  - 응답: `id`, `source_url`, `status`, `created_at`

검증/실패:

- 비로그인: `401` 또는 `403`
- 빈 URL/잘못된 포맷/비허용 스킴: `400`
- pending 중복 URL: `400` + 필드 에러(`source_url`)

### 2) 관리자 제보 목록

- Method/Path: `GET /api/admin/event-submissions/`
- Auth: 관리자 전용
- Success:
  - `200 OK`
  - 최신순(`-id`) 또는 `-created_at` 정렬
- 실패:
  - 비관리자: `403`

## 결합도/응집도 검토

- 결합도:
  - 제보 수집을 `drafts` 내부에 유지해 `events`와의 런타임 결합을 늘리지 않는다.
  - 제보 생성 시 발행/승인 프로세스를 호출하지 않아 교차 도메인 오케스트레이션을
    의도적으로 차단한다.
- 응집도:
  - URL 기반 입력 수집 책임을 `drafts` 도메인에 집중시켜 기존 draft ingestion
    흐름과 같은 경계에 둔다.
  - 상태 규칙(`pending` 중복 거절)도 동일 서비스 계층에 모아 응집도를 유지한다.

잔여 결합(허용):

- `drafts`가 `accounts.User` FK를 참조
  - 인증 리소스 소유자 표현에 필요한 정상 결합

## Pythonic 코드 설계

- Django/DRF 기본 확장점 우선:
  - 모델: 상태/필드 정의
  - serializer: 입력 형식/필드 검증
  - service 함수: 도메인 규칙 집행
  - view: HTTP 어댑터
- 명시적이고 작은 함수 사용:
  - 예: `create_event_submission(*, user, source_url)`
- 회피할 설계:
  - serializer `create()` 내부에서 복합 비즈니스 규칙 은닉
  - 거대한 뷰 메서드에 검증/규칙/저장 혼합
  - 제보 생성 시점의 암묵적 draft/event 생성

## 리스크 및 완화

1. 동시 요청에서 중복 URL 경합
   - 완화: `transaction.atomic()` + 생성 직전 pending 존재 재확인
2. 악성/무의미 URL 대량 입력
   - 완화: 현재는 인증 필수로 1차 제한, 레이트리밋은 후속 과제로 분리
3. 향후 상태 확장 시 규칙 분산
   - 완화: 상태 전이 로직을 서비스 계층 단일 진입점에 고정

## 테스트 설계 가이드(구현 전)

핵심 행위 테스트:

1. 로그인 사용자의 정상 제보 생성 `201`
2. 비로그인 제보 거절 `401/403`
3. 비관리자 관리자목록 접근 거절 `403`
4. 관리자 목록 조회 성공 `200`
5. `ftp://` 등 비허용 스킴 거절 `400`
6. pending 중복 URL 거절 `400`

아키텍처 테스트:

- `drafts.views`가 `events` 모듈을 import하지 않는지 유지 검증

## Deferred Refactoring Note

Deferred Refactoring Note

- Topic: pending 조건부 유니크 제약을 DB 레벨로 승격
- Why it is not part of the current scope: 현재 범위는 최소 API 제공과 규칙 검증이 우선
- Why it may be needed later: 고트래픽에서 서비스 레벨 중복검사만으로는 경쟁조건 완전
  차단이 어렵다
- Trigger condition: 제보 트래픽 증가 또는 중복 경합 재현
- Expected change location: `drafts/models.py`, 마이그레이션, `drafts/services.py`
- Related tests: 중복 생성 경쟁조건/무결성 테스트

## 구현 전 게이트

이 설계가 승인되면, 다음으로 통합 구현 계획 문서에서 아래를 확정한다.

- TDD RED-GREEN 체크포인트
- 파일 단위 수정 목록
- 검증 명령 세트
- 상태/리팩토링 문서 업데이트 절차
