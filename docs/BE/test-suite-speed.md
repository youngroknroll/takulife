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
| 2026-10-30 (직렬, main `73900041`) | 4,300 passed / 10 deselected | 134.77초 | `uv run pytest -q` `[실측 2026-10-30]` |
| 2026-10-30 (`-n auto` 8워커, PR #407) | 4,301 passed / 10 deselected | 41.72초·43.57초·44.14초(연속 3회) | `uv run pytest -q -n auto` `[실측 2026-10-30]` |

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
  → 2026-10-30 도입(§8).

## 8. 도입(2026-10-30, 트랙 49, PR #407)

① **승인**: 사용자 지시 "2번 진행"(백로그 K1 트리거 "사용자 승인" 충족)
`[문서]`.

② **측정**(8코어 Mac, 로컬 PostgreSQL 14.19, main `73900041`) `[실측
2026-10-30]`: 직렬 `uv run pytest -q` 134.77초(4,300 passed / 10
deselected). 의존성 추가 전 `uv run --with pytest-xdist pytest -q -n auto`
42.86초(8워커 — psutil 미설치라 `os.cpu_count()` 폴백 `[문서 xdist
configuration.md]`), `-n 4` 49.31초. 의존성 도입 뒤 `-n auto` 연속 3회
41.72초·43.57초·44.14초, 전부 4,301 passed / 10 deselected(래퍼 계약 테스트
1건이 늘어 기준선 4,300보다 1건 많다). 1회차 측정에서는 1 failed가 났는데
그 실패는 같은 트랙에서 아직 Red 상태였던 새 래퍼 계약 테스트였고(병렬
격리 결함이 아니다) 그 테스트를 Green으로 만든 뒤 3회 연속 전부 passed였다.

③ **`-n` 위치 결정**(`addopts`에 넣지 않고 CI test 잡과 `CLAUDE.md` 전체
회귀 명령에만 적용): 근거 실측 —
표적 파일 `tests/archive/test_visit_records_api.py`(37건)는 직렬 4.46초 →
`-n auto` 6.41초로 오히려 늘었고, 단일 테스트 파일은 직렬 0.01초(벽시계
0.53초) → `-n auto` 1.39초(벽시계 2.16초)로 늘었다. `-m e2e tests/e2e`는
그대로 직렬 10 passed / 11.09초(xdist 비활성)다. 즉 Red-Green 루프의 표적
실행에 `-n`을 강제하면 워커 기동·워커별 테스트 DB 생성 비용만 더해져
느려진다.

④ **CI 실측**: PR #407 CI(run 41070183412) 6잡 전부 pass `[실측 gh
2026-10-30]`. GitHub 호스트 러너의 "Run test suite" 단계는 main
`73900041`(run 41055310841, 직렬)의 82초 → `-n auto` 적용 뒤 55초, `test`
잡 전체는 116초 → 102초로 단축됐다 `[실측 gh run view 2026-10-30]`. `-q`가
xdist 머리줄("N workers")을 억제하므로 워커 수는 CI 로그에 직접 나오지
않고 실행시간 비교로 확인했다.

⑤ **DB 생성 권한**: 워커별 테스트 DB(`test_taku_gw0`…)는 pytest-django가
만들고, `DatabaseCache` 테이블은 테스트 DB 생성 시 자동 생성된다
(`core/migrations/0002` docstring `[코드]`). 로컬 역할 `taku`는
`rolcreatedb=t` `[실측 dbshell]`. CI 쪽 권한은 사전에 따로 점검할 수
없었고 ④의 CI 통과로 간접 검증했다.

⑥ **가드레일**: 새 테스트가 병렬에서만 깨지면 공유 상태(파일·캐시·시퀀스)
결함으로 보고 같은 PR에서 고친다. `-n` 플래그 자체는 속도 손잡이라 계약
테스트로 고정하지 않는다(Backend TDD Coach 판정 `[문서]`).

⑦ **SIGTERM 전달 재현**(§8.y 선행 조건 재검증, `docs/operations-runbook.md`
참조): `uv run python <스크립트>`에 `kill -TERM <uv pid>`를 보내면 자식
파이썬의 SIGTERM 핸들러가 신호 15를 받고 종료하며 uv 종료 코드는 0이다
`[실측 2026-10-30]`. 재현 명령:
```bash
uv run python -c 'import signal, sys, time; signal.signal(signal.SIGTERM, lambda *_: sys.exit(print("child got SIGTERM"))); print("ready", flush=True); [time.sleep(0.2) for _ in iter(int, 1)]' & sleep 3; kill -TERM $!; wait $!; echo "uv exit=$?"
```
기대 출력 `ready` / `child got SIGTERM` / `uv exit=0` 그대로 확인됐다
`[실측 2026-10-30]`.
