# 방문 완료 처리 동시성 계약

`complete_visit_with_record`(archive/services.py)가 상태 행 부재 시 겪는
경쟁 삽입을 어떻게 잠그고 복구하는지, 왜 상위 자원이 아니라 자기 소유 테이블을
잠그기로 했는지의 근거를 남긴다. 정본 문서 부재로 2026-08-24 신설.

## Current fact

`complete_visit_with_record`는 `transaction.atomic()` 안에서 `UserEventStatus`
상태 행 조회를 `select_for_update()`로 잠근다. 행이 없어 새로 만들려는 두
요청이 동시에 들어오면, 진 쪽은 `create_user_event_status`가 던지는
`DuplicateUserEventStatusError`를 잡아 같은 조건으로 `select_for_update()`
재조회를 1회 수행하고, 이긴 쪽이 이미 커밋한 행을 이어받아 완료 처리를
계속한다. 재조회에도 행이 없으면(예측 밖 상태) 두 번째 생성 시도의 예외를
그대로 전파한다 — 재시도는 정확히 1회로 제한된다.

`VisitRecordListCreateView.create`와 그 personal-entry 대응 액션
(archive/views.py)은 이 `DuplicateUserEventStatusError`를 잡아 500이 아니라
`409`(`code: duplicate_user_event_status`)로 응답한다.

## Decision

상위 자원(Event/User) 잠금은 기각했다(2026-08-24 아키텍처 검토). 이유:

- **도메인 결합**: Event는 `events` 앱 소유 자원이다. `archive`가 그 행을
  잠그면 도메인 경계를 넘는 락 의존이 생긴다.
- **차단 범위**: 사용자 단위나 이벤트 단위로 잠그면 같은 사용자·같은 이벤트의
  무관한 다른 쓰기 경로까지 직렬화된다.

대신 `archive`가 소유하는 `UserEventStatus` 행 자체를 잠근다 — 경쟁이 실제
발생하는 자리이자 이 앱이 배타적으로 쓰는 테이블이다.

## Guardrail

- 복구 재시도 횟수를 1회 초과로 늘리지 마라. CP8 계약(상태 저장 실패 시
  방문 기록 생성까지 함께 롤백)이 무한 재시도와 함께 있으면 실패 조건이
  불명확해진다.
- `mark_visited`의 save → 활동 로그 → 분석 이벤트 순서, `create_visit_record`의
  `client_token` 멱등 검사(atomic 블록 밖에서 재조회)는 이번 동시성 수정과
  독립된 별개 계약이다. 이 함수를 리팩터링하며 두 로직의 실행 순서나 위치를
  옮기지 마라.
- 단일 DB 커넥션을 쓰는 테스트에서 경쟁 행을 세이브포인트(중첩 atomic) 안에서
  INSERT하면, 그 세이브포인트가 롤백될 때 경쟁 행도 함께 사라져 경쟁이
  재현되지 않는다. `tests/archive/test_visit_record_status_orchestration.py`의
  RACE-02가 별도 스레드 + 별도 DB 커넥션 + `transaction=True`를 쓰는 이유가
  이것이다. 동시성 회귀 테스트를 단일 커넥션 픽스처로 옮기지 마라.

## Known gap

SQLite는 `select_for_update()`를 무시한다. 이 잠금 계약은 PostgreSQL을
기준으로 성립한다. 로컬·CI 테스트는 `DATABASE_URL`이 가리키는 PostgreSQL로
실행되므로 RACE-02의 두-커넥션 재현은 유효하지만, 실제 병렬 부하(다중 프로세스,
네트워크 지연 포함) 재현은 아직 하지 않았다. 트리거: 스테이징 환경 확보 시.

## Evidence [실측, 2026-08-24]

`tests/archive/test_visit_record_status_orchestration.py`:
- RACE-01 `test_방문_완료_처리_시_상태_행_조회는_FOR_UPDATE_잠금_아래에서_실행된다`
  — FOR UPDATE 계약 확인. 잠금 호출을 되돌리는 뮤테이션 왕복으로 검출력 확인.
- RACE-02 `test_상태_행_생성이_동시_삽입과_충돌하면_기존_행을_재조회해_방문_완료_처리를_정상_완료한다`
  — 별도 스레드·커넥션으로 실제 경쟁 삽입 재현.

`tests/archive/test_visit_records_api.py`:
- RACE-03 `test_방문_완료_처리_중_중복_상태_오류가_발생하면_500이_아닌_409로_응답된다`
  — 뷰 레벨 409 번역 확인.

`archive` 스위트 788 passed.
