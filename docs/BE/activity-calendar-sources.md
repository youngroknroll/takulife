# 활동 달력 출처 우선순위

`/archive/calendar/`가 방문·굿즈 활동을 셀 수 있는 출처는 항상 두 종류다 —
상태 테이블(`VisitRecord`/`CollectionItem`)과 행동 로그(`ActivityLogEntry`).
이 문서는 그중 무엇을 그릴지 정하는 규칙과, 이 규칙을 우회하면 재발하는
결함(2026-07-31 중복 표시·삭제 잔존 수정, PR 미기재)의 근거를 남긴다.

## Decision — 상태 테이블 우선 (사용자 결정, 2026-07-31, A안)

`core/views/activity.py`의 `_ACTIVITY_TYPE_GROUPS`에서 `"visit"`와 `"goods"`
그룹은 각각 `VISIT_KIND`, `GOODS_ACQUIRED_KIND`만 가리킨다. 대응하는 행동
로그 kind(`VISIT_RECORD_CREATED`, `COLLECTION_ITEM_CREATED`,
`COLLECTION_ITEM_ORGANIZED`)는 이 딕셔너리에 없다.

**Guardrail**: 이 3개 kind를 다시 `_ACTIVITY_TYPE_GROUPS`에 넣지 마라. 방문·굿즈
등록은 상태 테이블 행과 로그 행을 원자적으로 함께 쓰므로, 둘 다 그룹에 있으면
같은 활동이 두 번 보인다.

## Guardrail — 계층 경계

이 규칙은 웹 계층(`core/views/activity.py`)에 있다. `archive/queries.py`의
`list_user_activity_for_month`는 손대지 않았고, 계약대로 5개 출처 원자료를
그대로 반환한다("달력 표시 가능한 원자료 전체"). 어떤 kind를 실제로 그릴지는
웹 계층 책임이다.

이 규칙을 질의 계층으로 내리지 않는 이유: `archive/queries.py`의
`_interest_added_fallback_items`는 **행 단위 교차 대조**(이 event에 로그 행이
있는지)라서 질의 계층 밖에서는 만들 수 없다. 반면 이번 규칙은 **kind 단위
무조건 규칙**(대응 상태 행 존재 여부와 무관하게 항상 숨김)이라, 이미 웹 계층에
있는 `status` 그룹 은폐(`_visible_activity_group`)와 같은 자리다.

## Guardrail — 회귀 테스트는 반드시 HTTP API 경유로 데이터를 만들 것

`tests/archive/conftest.py`의 `make_visit`/`make_collection_item`은
`.objects.create()` 직접 호출이라 `ActivityLogEntry`가 생기지 않는다. 이
결함이 오래 안 잡힌 이유가 이것이다 — 중복 상황 자체가 테스트에서 만들어진
적이 없었다.

달력 중복 관련 회귀 테스트를 새로 쓸 때는 반드시 실제 HTTP API를 거쳐 상태
행과 로그 행이 함께 생기게 하라: `POST /api/visit-records/`,
`POST /api/collection-items/`, `PATCH`/`DELETE /api/collection-items/<pk>/`.
서비스 함수를 직접 호출하는 것도 안 된다 — 아래 아키텍처 계약 항목을 봐라.

## Guardrail — 뷰 계층 테스트는 `archive.services`를 임포트할 수 없다

`tests/core/test_activity_calendar_view.py`는 `tests/core/test_architecture_boundaries.py`
가드의 적용을 받는 뷰 계층 테스트라 `archive.services`를 임포트하지 못한다.
회귀 테스트가 HTTP 경유를 쓰는 이유가 이것이기도 하다. 허용 목록에 예외를
추가해 이 가드를 무력화하지 마라.

## Evidence — 질의 계층 가드가 무엇을 보증하는가

`tests/archive/test_activity_calendar_queries.py`의
`test_행동성_활동은_occurred_at의_로컬_날짜에_표시된다`는 `방문기록작성`/
`굿즈등록`/`굿즈정리` 파라미터 케이스를 포함한다. 이 3케이스가 이번 수정 후에도
통과하는 것은 "수정이 질의 계층까지 내려가지 않고 웹 계층에 머물렀다"는 증거다.
이 케이스가 깨지면 `archive/queries.py`가 잘못 바뀐 것이다.

## Known gap — 의도된 동작 변화 (버그로 오인 금지)

다음은 이번 수정의 부수 효과가 아니라 결정이다:

- 달력은 `visited_on`/`acquired_on`만 따르고 `occurred_at`은 따르지 않는다.
- **굿즈를 수정만 하면(수량 변경 등) 달력에 새 활동이 생기지 않는다.** 등록
  시점 1건만 유지된다.
- 하드 삭제된 항목은 달력의 모든 표면(셀·`selected_items`·`kind_counts`)에서
  사라진다. 감사 로그 행 자체는 `ActivityLogEntry`에 `SET_NULL` + 스냅샷으로
  DB에 남는다 — "상위 삭제가 히스토리를 조용히 지우면 안 된다"는 기존 설계는
  바뀌지 않았고, 표시만 감춘다.
- **검색 점프도 같은 규칙을 따른다.** 로그 전용 항목(예: 하드 삭제된 굿즈의
  등록 로그)으로는 더 이상 점프하지 않는다.

굿즈 수정 무반응과 검색 점프 변화는 특히 나중에 버그로 오인해 되돌릴 위험이
있다. 되돌리기 전에 이 문서와 사용자 결정(A안, 2026-07-31)을 먼저 확인하라.

## Deferred — 이번 범위 밖

- 굿즈 삭제 종결 로그(`collection_item_deleted` kind) 신설.
- 굿즈 "최근 수정" 신호를 대체 설계로 되살리는 것.
- `interest_removed` 표시 정책 재검토.

## Evidence — 검증 [실측]

전부 오케스트레이터가 직접 실행해 관찰했다.

- 전체 회귀 `uv run pytest -q`: 2028 passed, 0 failed
- `uv run python manage.py check`: 0 issues
- `uv run python manage.py makemigrations --check --dry-run`: No changes detected
- 뮤테이션 검증(수정을 되돌리고 신규 테스트 4건 재실행): 4건 전부 실패
  (`assert 2 == 1`, `assert 2 == 1`, `assert 1 == 0`, `assert 2 == 0`)
- 질의 계층 가드 `test_행동성_활동은_occurred_at의_로컬_날짜에_표시된다`: 5 passed
