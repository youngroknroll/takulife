# 테스트 스위트 실행시간 개선 사례

백엔드 테스트 스위트가 313.81초 걸려 Red-Green 루프를 막던 문제를 같은 날
같은 스위트에서 약 30초로 줄인 과정과, 그 과정에서 드러난 실제 결함을
기록한다. 측정 조건이 다른 수치를 같은 조건의 개선처럼 비교하지 않도록
각 수치에 시점·스위트 규모를 함께 적었다.

## 1. 측정 기록

| 시점 | 스위트 규모 | 실행시간 | 출처 |
|---|---|---|---|
| 2026-07-17 (개선 전) | 테스트 함수 1,481개(정적 카운트, parametrize 전개 전) `[실측 git grep 2026-10-28, 커밋 37260451^]` | 313.81초(non-e2e) | 커밋 `37260451` 본문 `[코드]` |
| 2026-07-18 (개선 후, 같은 스위트) | 테스트 함수 1,485개 `[실측 git grep 2026-10-28]` | 약 30초(non-e2e), e2e 129.17초 → 약 76초 | 커밋 `37260451` 본문 `[코드]` |
| 2026-10-27 (현재) | 4,284 passed / 10 deselected | 152.46초(main `e38a0db9`), 145.07초(트랙 45 작업 트리) | `docs/backlog.md` "현재 상태" `[실측 2026-10-27]` |
| 2026-10-28 (직렬, main `8901c96d`) | 4,284 passed / 10 deselected | 149.07초 | `uv run pytest -q --durations=40` `[실측 2026-10-28]` |

개선 전후 비교는 2026-07-17과 2026-07-18의 같은 스위트만 유효하다. 현재
152초는 테스트가 약 2.9배로 늘어난 뒤의 값이며 개선 효과의 역산 근거로
쓰지 않는다.

## 2. 원인 분석

실행 시간을 나눠 본 결과 세 가지가 겹쳐 있었다.

1. **비밀번호 해싱.** 사용자 픽스처가 테스트마다 운영 강도의 PBKDF2 해시를
   수행했다. 1회당 약 0.38초 `[실측, config/settings_test.py docstring]`이며,
   임시 사용자를 많이 만드는 테스트에서 시간의 대부분을 차지했다.
2. **전역 autouse 캐시 초기화.** `tests/conftest.py`의 `clear_cache`가 autouse라
   DB를 쓰지 않는 테스트까지 매번 캐시 테이블을 비웠다.
3. **계층 미분리.** 순수 함수 테스트와 느린 통합 테스트가 한 덩어리라 일부만
   골라 돌릴 수단이 없었다.

## 3. 선택한 해결

| 조치 | 내용 | 근거 |
|---|---|---|
| 테스트 전용 설정 | `config/settings_test.py`가 운영 설정을 그대로 불러온 뒤 `PASSWORD_HASHERS`만 MD5로 덮어쓴다. `CACHES`는 일부러 덮어쓰지 않아 `DatabaseCache` 계약을 운영과 동일하게 유지한다 | `config/settings_test.py` `[코드]` |
| 설정 경계 가드 | `manage.py`·`config/wsgi.py`·CI·Docker가 테스트 설정을 참조하지 못하게 계약 테스트로 고정하고, `.dockerignore`로 이미지에서 제외한다 | `tests/core/test_test_settings_boundary.py` `[코드]` |
| 픽스처 축소 | `clear_cache`의 autouse 해제, `make_user` 기본 비밀번호를 unusable로 바꿔 인증과 무관한 테스트가 해시 비용을 내지 않게 함 | 커밋 `37260451` 본문 `[코드]` |
| 계층 marker | `unit`·`domain`·`web`·`contract`·`slow`·`e2e` 여섯 marker를 등록하고 `--strict-markers`로 오탈자를 막는다. 기본 실행은 `-m "not e2e"` | `pytest.ini` `[코드]` |

대안으로 pytest-xdist 병렬 실행을 검토했지만, 원인이 불필요한 작업량이라
먼저 작업량을 줄이는 쪽을 택했다. 병렬화는 DB 격리 비용이 따로 들고 숨은
결함을 더 가릴 수 있다.

## 4. 개선 과정에서 발견한 결함

전역 캐시 초기화를 없애자 e2e 연속 로그인 시나리오가 429로 실패했다.
원인은 django-allauth 기본 로그인 rate limit(IP당 30회/분)이 **성공한
로그인까지 카운트**한다는 점이었고, 전역 autouse 픽스처가 매 테스트 캐시를
비워 이 동작을 계속 가리고 있었다. 운영 설정은 바꾸지 않고
`tests/e2e/conftest.py`에 캐시 격리 픽스처를 두어 해소했으며, 이 계약을 더
낮은 계층에서 고정하는 회귀 테스트를 추가했다.

- `tests/auth/test_auth_rate_limit.py::test_성공한_로그인도_login_한도에_포함되어_초과하면_429로_차단된다`
  `[코드]` — 한도를 2회/분으로 좁힌 설정에서 3번째 성공 로그인이 429인지 확인
  (커밋 `9058f3bf`, 2026-07-18).

## 5. 검증 방식

- 테스트를 작성한 뒤 코드를 일부러 깨서(뮤테이션) 실제로 Red가 되는지
  확인하는 절차를 상시 적용한다. 반복 실패 유형과 판정 규칙은
  `docs/BE/contract-guards.md` "이 저장소에서 반복되는 실패 유형"에 있다.
- CI `test` 잡은 PostgreSQL 서비스 컨테이너에서 `uv run pytest -q`를 실행한다.
  e2e 여정 10건은 별도 `e2e` 잡에서 `-m e2e`로만 실행하며 관측 모드
  (`continue-on-error`)다(`.github/workflows/ci.yml` `[코드]`).

## 6. 한계

- 2026-10-27 기준 152초는 다시 120초를 넘었다. 시각 의존 테스트 2곳은 트랙
  45에서 고쳤지만(`docs/backlog.md` K절), 실행시간 자체의 2차 개선은
  2026-10-28에 측정만 했다(§7). 단일 병목은 없고 병렬화만 남았으며 도입은
  사용자 결정 대기다.
- marker 분류는 선언 기준이며 자동 검증이 없다. 잘못 분류된 테스트가 있어도
  기계가 잡지 못한다.

## 7. 2차 측정(2026-10-28) — 단일 병목 없음, 병렬화만 남음

측정 환경: main `8901c96d`, 로컬 Mac 8코어, 로컬 PostgreSQL 14.19
`[실측 2026-10-28]`.

- 직렬 `uv run pytest -q --durations=40`: 4,284 passed / 10 deselected /
  149.07초 `[실측 2026-10-28]`. 가장 느린 단일 항목은 2.07초(setup,
  `tests/archive/test_activity_calendar_queries.py::test_활동_월_조회_결과에는_본인_활동만_포함된다`),
  다음이 0.94초·0.92초(`test_comment_language_guard`·`test_secret_literal_guard`
  전수 스캔)다. 상위 40건 합계는 약 15초 미만이다 `[계산 상위 40건 합산 추정]`.
- 모듈 단위 분해(`tests/archive/test_visit_records_api.py`, 37건, 4.30초):
  setup 1.72초 · call 2.87초 · teardown 0.05초 `[실측 2026-10-28]`.
- 픽스처 셋업 합계(스크래치 플러그인 `pytest_fixture_setup` 훅 타이밍,
  `tests/archive tests/auth` 1,129건 48.93초): `django_db_setup` 1.60초(1회),
  `_django_db_marker` 0.16초(1,129회), `_reseed_category_vocabulary` 0.03초,
  `_restore_korean_language` 0.01초 `[실측 2026-10-28]`.
- 결론: 시간은 테스트 본문의 요청 처리에 고르게 분산되어 있고, 픽스처·DB 셋업
  최적화 여지는 없다.
- 병렬 측정: `uv run --with pytest-xdist pytest -q -n 4`(의존성 변경 없이 측정)
  4,284 passed / 53.87초, 직렬 149.07초 대비 단축 `[실측 2026-10-28, 4워커·8코어]`.
  전 테스트가 병렬에서도 통과해 테스트 간 격리는 성립한다.
- 도입하려면 필요한 변경:
  - `uv add --group dev pytest-xdist`
  - `pytest.ini` `addopts`에 `-n auto`, 또는 CI 잡에만 `-n 4`
  - 워커별 테스트 DB(`test_taku_gw0`…)가 생기므로 로컬 Postgres의 DB 생성
    권한 확인
  - `tests/e2e`는 `live_server` 포트 충돌 가능성 때문에 직렬 유지 권고
- 미도입 사유: `AGENTS.md` "Package And Command Policy"가 새 test-convenience
  패키지에 승인된 계획과 사용자 명시 승인을 요구한다. **도입 여부는 사용자 결정
  대기**이며 이 트랙에서는 도입하지 않았다(`docs/backlog.md` K절 끝 항목).
