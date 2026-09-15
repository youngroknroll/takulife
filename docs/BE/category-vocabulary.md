# 카테고리 어휘 (DB 기반)

카테고리는 더 이상 `core/vocab.py`의 상수가 아니라 `core.models.Category`
행이다. 스태프(슈퍼유저)가 `/staff/categories/`에서 생성·수정·비활성화한다.

> ⚠️ 트랙 번호 주의: `prompt_plan.md`가 이 작업을 "트랙 27 후보"로 적었는데,
> `docs/pr-log.md`와 메모리에서 **트랙 27은 이미 여정 e2e 재도입(PR #354)**을
> 가리킨다. 번호가 겹치니 이 문서를 찾을 때는 번호가 아니라 이름으로 찾아라.

## 소유와 경계

- 소유 앱은 `core`다. `core`는 어떤 도메인 앱도 되참조하지 않는다(경계 R1).
- ORM을 쓰는 조회는 `core/categories.py`가 맡는다. `core/vocab.py`는 순수
  상수 모듈로 남는다 — 그 파일이 스스로 "매직 없음"을 선언하고 있고,
  `vocab → models → vocab` 순환을 피해야 한다.
- `Event.category`는 **CharField(슬러그) 그대로**다. FK로 바꾸지 않았다.
  `EventDraft.extracted_category`는 어휘 밖 값도 보존해야 하는 자유 문자열이라
  FK가 될 수 없는데, Event만 FK가 되면 초안→이벤트 승격 경로에 슬러그↔FK
  변환 계층이 새로 생긴다.

## 하드 삭제는 없다

비활성화만 있다. 그래서 **`category_exists()`는 비활성 카테고리도 True**를
돌려준다 — 비활성 카테고리로 이미 저장된 이벤트가 재게시될 때 어휘 검증에서
거부되면 안 되기 때문이다. 이 함수를 "활성만"으로 좁히면 기존 이벤트의
재게시가 조용히 막힌다.

쓰임새별로 함수가 갈린다. 고를 때 이 표를 보라.

| 함수 | 포함 범위 | 쓰는 곳 |
|---|---|---|
| `category_exists(slug)` | 전체(비활성 포함) | 어휘 검증 |
| `category_label(slug)` | 전체, 없으면 슬러그 반환 | 라벨 표시 |
| `category_slugs()` | 활성만 | LLM 추출 enum·러너 어휘 |
| `active_category_choices()` | 활성만 | 신규 등록 폼 |
| `category_choices_for_editing(keep_slugs=)` | 활성 + 현재 값 | 기존 값 편집 폼 |
| `all_category_choices()` | 전체 | 필터 칩 |

`category_label`의 `.get(slug, slug)` 폴백은 필수다(선례 `archive_status_label`).
카테고리 행이 사라져도 그 슬러그를 쓰던 이벤트 렌더가 깨지지 않아야 한다.

`category_choices_for_editing`의 `keep_slugs`를 빠뜨리면, 이미 저장된 비활성
값이 선택지에서 사라져 단일 값은 저장 시 다른 값으로 조용히 바뀌고 다중
값(홈 강조)은 해제할 방법이 없어진다.

## 팔레트 슬롯

색은 스태프가 고르지 않는다. `core/categories.py`의 `PALETTE` 12슬롯에서
자동 배정한다. 슬롯 번호가 `static/css/tokens.css`의 `--cat-slot-{n}-soft/-ink`
인덱스다.

**반납 규칙** — 활성 여부와 게시 건수를 **함께** 봐야 한다.

| 상태 | 슬롯 |
|---|---|
| 활성 + 게시 0건 | **유지** |
| 비활성 + 게시 0건 | 반납 |
| 비활성 + 게시 1건 이상 | 유지 |

"게시 0건이면 반납"만으로 구현하면 **새로 만든 카테고리가 생성 직후 자기
슬롯을 반납한다**(정의상 게시 0건이다). 사전 검토가 이것을 Critical로 잡았다.

⚠️ **재계산 시점은 게시상태 전이와 카테고리 활성 전이뿐이다. 조회(GET)
경로에서는 절대 호출하지 마라.** 호출부는 `events/services.py`(게시·게시중단·
재게시)와 `events/signals.py`(비활성 신호) 네 곳뿐이고, 스태프 뷰는 직접
호출하지 않는다.

`core`가 `events`를 임포트할 수 없어(R1) 게시 건수를 직접 셀 수 없다. 그래서
`core`는 `category_deactivated` 시그널로 "무엇이 바뀌었는지"만 알리고, 실제
반납 판단은 `events` 쪽 수신자가 한다.

**미배정(`palette_slot=None`)은 정상 상태다.** 반납 후 재게시 시 빈 슬롯이
없으면 미배정으로 남고, 게시 자체는 막지 않는다. 스태프 화면은
`palette_hex_for(None)`이 항상 4키 dict(중립색)를 돌려주므로 `None` 분기가
필요 없다.

## 아직 닫히지 않은 간극 — 소비자 화면의 색

**소비자 화면은 아직 슬러그 기반 토큰(`--cat-{slug}-*`)을 쓴다.** 슬롯
토큰(`--cat-slot-{n}-*`)은 48개가 정의돼 있지만 소비처가 0곳이다
`[실측 2026-09-13]`.

결과: 스태프가 새로 만든 카테고리는 스태프 화면에서는 제 색으로 보이지만
**소비자 화면에서는 중립 폴백으로 렌더된다.** 기능(필터·라벨·목록·홈 타일)은
정상이고 강조색만 폴백이다.

남은 이관 표면 `[실측 2026-09-13]`: 소비자 템플릿 9지점 / 7파일, 소비자 CSS
25지점 / 3파일(`home.css`·`event_list.css`·`event_calendar.css`, 슬러그 6종
하드코딩). 이 이관은 소비자 렌더를 바꾸므로 FE 리뷰 2역할의 사전 산출이
선행돼야 한다.

## 색 계약 가드

`tests/core/test_category_token_contract.py`가 세 가지를 강제한다.

1. `tokens.css`에 12슬롯 × soft/ink 토큰이 **존재**한다
2. 그 토큰 **값이 `PALETTE`와 일치**한다 — 이름만 검사하면 두 파일이 조용히
   어긋나고, 스태프 화면(Python hex)과 소비자 화면(CSS 토큰)의 색이 달라진다
3. 활성 카테고리는 모두 유효 슬롯에 배정돼 있다

## 마이그레이션

- `core/0005` 스키마, `core/0006` 시딩, `staff/0011` FK, `staff/0012` 액션 추가
- 시딩은 `core.vocab.CATEGORY`를 **라이브 import하지 않고 동결 스냅샷**을
  심는다(선례 `archive/0017`). 어휘가 나중에 바뀌어도 이미 적용된 0006은
  옛 값을 심는 것이 맞다.
- `reverse_code`는 noop이 아니라 **슬러그 정확 매칭 삭제**다.
- 롤백 순서는 Django가 그래프 의존 관계로 자동 해결한다. `migrate core 0005`
  실행 시 `Unapplying staff.0011` → `Unapplying core.0006` 순으로 FK 오류 없이
  성공한다 `[실측 2026-09-13, 로컬 Postgres 2회 재현]`. 사전 검토의 "운영자가
  순서를 직접 강제해야 한다"는 판단은 이 실측으로 반증됐다.
- 왕복 실측 `[2026-09-13]`: forward 7행 → `migrate core 0005` 0행·컬럼 제거 →
  forward 재적용 7행(슬롯 0~6 원래 색 순서). 이벤트 171건·감사 로그 19건 보존.

### ⚠️ 마이그레이션 테스트의 함정

`tests/core/test_category_seed_migration.py`는 `core`를 0006 이전으로 되감는데,
`staff.0011`이 `core.0006`에 의존하므로 **Django가 `staff.0011`도 함께
되감는다.** 테스트가 `core`만 복구하면 `staff` 스키마가 한 단계 뒤에 남아,
알파벳 순으로 뒤에 도는 다른 테스트가 없는 컬럼을 만나 죽는다. 증상과 원인이
다른 디렉터리에 있어 파일 단독 실행으로는 재현되지 않는다.

그래서 이 파일은 매 테스트 뒤 **전체 앱을 head로 재이주**시킨다. 앱을 손으로
나열하지 마라 — 나중에 `core`에 의존하는 앱이 하나 더 생기면 같은 방식으로
조용히 깨진다.

같은 구조의 `tests/auth/test_nickname_backfill_migration.py`는 현재
`accounts`에 의존하는 다른 앱의 마이그레이션이 0건이라 무증상이다
`[실측 2026-09-13]`. 그 앱을 참조하는 FK가 생기면 같은 증상이 나타난다.

### ⚠️ transactional 테스트가 어휘를 비운다

어휘가 상수가 아니라 DB 행이 되면서 새로 생긴 함정이다.
`transaction=True` 테스트는 끝나며 테이블을 비우는데, 마이그레이션이 심은
시딩은 **복구되지 않는다.** 그래서 **첫 transactional 테스트만 7건을 보고
두 번째부터 0건을 본다** `[실측 2026-09-13]`.

순서 의존이라 증상이 "왜 이 테스트만 실패하지"로 보인다. 실제로 e2e 드래프트
승인 여정이 이렇게 깨졌다 — 게시 시 카테고리 검증이 빈 어휘를 만나 실패했고,
2816개 테스트는 전부 통과하는 상태였다. 여정 e2e가 잡아낸 결함이다.

`tests/conftest.py`의 autouse 픽스처 `_reseed_category_vocabulary`가 복구한다.
transactional 여부를 먼저 판정하고 나서만 DB를 조회하므로 `-m unit`은 DB에
접근하지 않는다. 새로 `transaction=True` 테스트를 쓸 때 어휘가 비어 보이면
이 픽스처부터 확인하라.

## 감사 로그

`StaffActionLog.target_category` FK와 액션 4종(`category_create`/`update`/
`disable`/`enable`)이 있다. 계획서는 3종만 정의했으나, 비활성화만 남기고
재활성화를 남기지 않으면 "지금 활성인데 disable 로그만 있는" 상태를 설명할
수 없어 계정 화면 선례(`USER_DEACTIVATE`/`USER_REACTIVATE`)대로 쌍을 맞췄다.

감사 로그 **조회**(`staff/queries.py`)도 `target_category`를 select해야 한다.
FK만 저장하고 조회를 빠뜨리면 화면의 "대상" 열이 `-`로 비어 어떤 카테고리를
만들고 지웠는지 감사할 수 없다 — 실제로 그 상태로 한 번 구현됐고 브라우저
검증에서 잡았다.

## 권한

화면 4개 뷰와 활성/비활성 엔드포인트 **전부**에 `@superuser_console_required`를
개별로 단다. 사이드바의 `{% if request.user.is_superuser %}`는 경계가 아니다.

`tests/staff/test_staff_category_permissions.py`의 AST 가드가
`staff/views/categories.py`의 최상위 함수를 전수 검사한다 — 나중에 엔드포인트가
늘고 URL 파라미터 목록을 고치는 걸 잊어도 이 가드가 잡는다.

## 생성 경합

생성 POST는 `transaction.atomic()` 안에서 `select_for_update()`로 기존 행을
잠그고 슬롯 가용성을 재검사한다. 폼을 11/12에서 열어 둔 채 다른 슈퍼유저가
마지막 슬롯을 채우면 GET 시점 방어만으로는 13번째 배정이 생긴다.
