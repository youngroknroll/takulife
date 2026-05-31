# OshiLog EventSubmission API PO Scope

Date: 2026-06-01
Role: PO / General Manager
Project root: `/Users/yeongroksong/Desktop/study/project/taku`

## 목적

다음 백엔드 API 작업 대상으로 `EventSubmission`을 확정하고,
제품 관점의 승인 범위와 수용 기준을 명시한다.

이 문서는 PO 범위 정의 문서이며, 구현 지시 문서가 아니다.
구현 전 Tech Lead 설계와 통합 구현 계획 문서가 후속으로 필요하다.

## 기준 문서

1. `AGENTS.md`
2. `docs/plans/2026-05-20-oshilog-mvp-planning.md`
3. `docs/plans/2026-05-26-oshilog-rest-api-design-plan.md`
4. `docs/project-status.md`

## 제품 판단

- 현재 공개 이벤트 조회/관리자 드래프트 워크플로우는 구현되어 있다.
- 다음 단계는 사용자 제보 URL 수집 경로를 여는 것이다.
- 다만 스팸/악성 입력 리스크를 낮추기 위해 1차 릴리스는 인증 사용자만 제보를 허용한다.
- 제보 데이터는 공개 이벤트로 즉시 노출하지 않고, 관리자 검토 대기 큐로만 진입한다.

## 승인 범위

이번 작업에서 허용하는 범위:

- 사용자 제보 생성 API 추가
  - `POST /api/event-submissions/`
  - 인증 사용자만 접근 가능
- 관리자 제보 목록 조회 API 추가
  - `GET /api/admin/event-submissions/`
  - 관리자 전용
- 제보 생성 시 최소 필수 입력 검증
  - `source_url` 필수
  - URL 스킴 제한(`http`, `https`)
- 동일 URL 중복 제보 방지 정책 반영
  - 기본 정책: 대기/처리중 제보에 대해 중복 거절
- 응답 포맷/에러 포맷은 현재 API 규칙을 따른다.
- 테스트, 계획/상태/작업 로그 문서 업데이트

## 제외 범위

이번 작업에서 제외:

- 비로그인(공개) 제보 허용
- 제보 승인/반려 상세 워크플로우 확장
- AI 추출 연계
- 비동기 큐/레이트리밋/고급 안티스팸
- 사용자 마이페이지(내 제보 목록) API

## 수용 기준

1. 인증 사용자가 유효한 `source_url`로 제보를 생성하면 `201`을 반환한다.
2. 비인증 요청은 `401` 또는 `403`을 반환한다.
3. 관리자가 제보 목록을 조회하면 `200`과 목록 응답을 받는다.
4. 일반 사용자의 관리자 목록 접근은 `403`을 반환한다.
5. 잘못된 URL 스킴 또는 빈 URL은 `400`을 반환한다.
6. 중복 URL 제보는 `400`으로 거절되고, 의미 있는 에러 메시지를 반환한다.
7. 신규 동작을 검증하는 API 테스트가 추가되고 전체 회귀가 통과한다.

## 우선순위

- P0: `POST /api/event-submissions/` 인증/검증/중복거절
- P0: `GET /api/admin/event-submissions/` 관리자 접근제어
- P1: 응답 필드 정돈, 에러 메시지 정합성 개선

## 오픈 이슈

- 중복 판단 범위를 “모든 상태”로 볼지 “pending 상태”로 제한할지
- 제보 생성 시 즉시 fetch/extract를 수행할지, 단순 큐 적재만 할지

PO 기본 결정:

- 중복 판단: 우선 `pending` 제보 기준으로 제한
- 생성 처리: 우선 동기 fetch/extract 없이 제보 레코드 생성까지

## 다음 단계 요청

구현 착수 전 아래 문서를 순서대로 작성:

1. Tech Lead 설계 문서
   - 도메인 경계/의존 방향
   - 결합도/응집도 검토
   - Pythonic 코드 설계
2. 통합 구현 계획 문서
   - TDD 체크포인트
   - 검증 명령
   - Deferred Refactoring Note
