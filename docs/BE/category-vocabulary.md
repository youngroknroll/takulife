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
| `palette_slot_by_slug()` | 슬롯이 배정된 전체(비활성 포함) | 공개 화면 점 색 |
| `category_labels_for(slugs)` | 전체, 행이 없는 슬러그는 결과에 없음 | 공개 화면 목록 행·적용 필터 칩·상세·홈 범례의 새 카테고리 라벨 |
| `category_display_labels(slugs)` | 고정 7종은 번역되는 상수 라벨, 그 밖은 DB 라벨, 행이 없으면 슬러그. 빈 슬러그는 결과에 없음. 조회는 고정이 아닌 슬러그가 있을 때만 1건 | 공개 화면 목록 행·적용 필터 칩·상세·내 활동 행·방문 목록 칩, 스태프 행사·드래프트 목록과 드래프트 상세 |
| `category_label_lang(label)` | 비한국어 화면이고 라벨에 한글 음절이 있으면 `"ko"`, 아니면 빈 문자열 | 템플릿 태그 `category_lang_attr`, 적용 칩·방문 목록 칩·홈 타일의 `lang` 값 |

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

**가드레일(2026-09-14)** — `reconcile_palette_slot`의 재획득 두 줄(빈 슬롯을
골라 `palette_slot`에 배정·저장하는 부분)은 반드시 자체 `transaction.atomic()`
(세이브포인트) 안에서 `IntegrityError`를 삼켜야 한다. 감싸지 않으면
`Model.save()`가 바깥 트랜잭션에 needs_rollback을 남겨, 생성·재게시·승인
경로는 뒤이은 감사 로그 기록이 `TransactionManagementError`(500·전체 롤백)로
막히고, 삭제 경로(`staff/services.py`의 `delete_event`, reconcile이 내부
atomic의 마지막 문장)는 예외 없이 이벤트만 되돌아가고 EVENT_DELETE 로그만
커밋된다 `[실측 2026-09-14 재현]`. 회귀:
`tests/core/test_category_palette_lifecycle.py`의
`test_카테고리_슬롯_재획득이_충돌해도_뒤이은_감사로그_기록이_성공한다`·
`test_삭제_경로에서_슬롯_재획득이_충돌해도_이벤트_삭제와_감사로그가_함께_커밋된다`
(세이브포인트를 되돌리면 2 failed `[실측]`).

## 공개 화면의 카테고리 색과 라벨

사용자 결정(2026-11-17): 새 카테고리에도 색 점을 준다(트랙 59).

- **고정 7종**은 슬러그 색이다. 점의 `data-category="<slug>"`가 `--dot-<slug>`
  토큰(`static/css/tokens.css` 20~26줄 `[코드]`)을 고른다.
- **그 밖의 카테고리**는 점 요소의 `data-palette-slot="N"`이 `--cat-slot-N-ink`를
  고른다. 12줄 매핑은 `static/css/components/category.css` 21~32줄 `[코드]`에 있다.
- **슬롯이 없거나 행이 없는 슬러그**는 중립색 점이다.

조회 경로: `palette_slot_by_slug()` → 컨텍스트 프로세서 `category_palette_slots`
(`core/context_processors.py`)의 지연 객체 → 템플릿 태그 `palette_slot_attr`
(`core/templatetags/category_dots.py`). 고정 7종·빈 카테고리만 있는 화면은 추가
쿼리가 0건이고, 새 카테고리가 있으면 슬롯 조회가 요청당 1건이다
`[코드 core/templatetags/category_dots.py, core/context_processors.py]`.

읽기 전용 규칙: 이 경로에서 `reconcile_palette_slot`을 부르지 않고 프로세스 전역
캐시를 두지 않는다. 테스트가 각각 지키는 것은 다음과 같다.

- 프로세스 전역 캐시를 두지 않아 슬롯 재배정이 다음 요청에 바로 보인다:
  `tests/core/test_category_queries.py`의
  `test_슬롯이_재배정되면_다음_슬롯_맵_조회가_바뀐_슬롯을_돌려준다`.
- 읽기만 하고 슬롯을 반납하지 않는다:
  `tests/core/test_category_palette_slot_display.py`의
  `test_비활성이고_게시_행사가_없는_카테고리의_속성을_그려도_슬롯이_반납되지_않고_속성에_실린다`.
- 요청당 슬롯 조회는 1번이다: 같은 파일의
  `test_프로세서가_준_슬롯_맵으로_include를_거쳐_여러_점을_그려도_조회는_한_번이다`.
- 컨텍스트 프로세서 등록이 빠지면 행마다 조회가 나가 쿼리 수가 늘어난다:
  `tests/events/test_event_list_view.py`의
  `test_새_카테고리_행사가_여러_개여도_목록_조회_쿼리_수는_행_수에_비례하지_않는다`가
  실패한다(등록 한 줄을 지운 뮤테이션: 행 2건 6쿼리 / 행 6건 8쿼리
  `[실측 2026-11-17 뮤테이션]`).

새 카테고리가 있는 화면의 요청당 추가 쿼리 상한은 아래와 같고 행 수에 비례하지
않는다. 고정 7종·빈 카테고리만 있으면 모두 0건이다.

| 화면 | 추가 쿼리 상한 |
|---|---|
| 행사 목록·행사 달력·행사 상세 | 3건(슬롯 1 + 라벨 2) `[코드 DAR 사후 확인이 호출 횟수를 셈, 2026-11-17]` |
| 로그인 홈 | 5건(슬롯 1 + 라벨 4, 기록 대기 행 라벨 1건 포함) `[계산 코치 계약 §1-6]` |
| 내 활동 기록장·나의 일정·방문 목록·찜 목록 | 각 1건 `[계산 코치 계약 §1-6]` |
| 방문 상세·방문 수정 | 최대 1건 `[계산 코치 계약 §1-6]` |
| 스태프 행사 목록 | 행 1건 + 새 카테고리 필터를 걸고 결과가 없을 때 요약 1건 `[계산 코치 계약 §1-6]` |
| 스태프 드래프트 목록·상세 | 각 1건 `[계산 코치 계약 §1-6]` |

알려진 어긋남: 고정 카테고리가 슬롯을 반납했다가 다른 슬롯으로 재활성화되면,
스태프 견본은 새 슬롯 색이고 공개 화면은 슬러그 색이다. 고정 7종은 슬롯을
조회하지 않기 때문이다.

`-soft` 12개 선언(`--cat-slot-N-soft`)은 공개 화면에서 여전히 쓰지 않는다.
계약 테스트가 선언을 요구해서만 남아 있다.

### 라벨

공개 화면의 목록 행·적용 필터 칩·행사 상세·홈 달력 범례는 새 카테고리의 DB
라벨을 보여 준다(트랙 59 이전에는 슬러그가 나왔다). 홈 범례는 고정 카테고리
뒤에 새 카테고리를 `category_labels_for`가 돌려준 정렬 순서(`sort_order, id`)로
붙인다 `[코드 web/views/events.py]`.

내 활동·컬렉션 행(`web/views/_helpers.py`의 `_subject_view`)과 방문 목록 칩은
같은 규칙(`core.categories.category_display_labels`)으로 라벨을 푼다. 호출처는
행 묶음마다 라벨 맵을 한 번 만들어 `category_labels=`로 넘기고, 단건 화면은
맵 없이 부르면 그 한 건만 푼다. 방문 목록 칩의 토큰은 고정 7종이면 한국어 원문,
새 카테고리면 DB 라벨이다. 새 카테고리 칩을 누르면 그 카테고리 방문만 걸린다.
스태프 화면 4곳(`staff/views/events.py`, `staff/views/drafts.py`)도 같은 함수를
쓴다. 병합 규칙이 `core`에 있어 `staff`가 `web`을 임포트하지 않는다.

**`lang` 규칙**:

- `lang="ko"`는 비한국어 화면이고 표시 라벨에 한글이 있을 때만 붙는다. 판정은
  `category_label_lang` 하나가 가진다. 고정 7종 번역 라벨과 영문 DB 라벨에는
  한글이 없어 붙지 않는다.
- 한국어 화면에는 속성 자체를 내지 않는다.
- 개인 항목(직접 등록) 행의 카테고리는 사용자 입력이라 붙이지 않는다. 활동
  화면은 공식 행사일 때만 태그를 쓴다.
- 스태프 화면은 한국어 전용(`<html lang="ko">`, `translation.override("ko")`)이라
  붙이지 않는다.
- 라벨 요소가 템플릿에서 직접 보이는 곳은 `{% category_lang_attr 라벨 %}`을 쓴다.
  적용 필터 칩은 문자열이 섞여 있어 뷰가 `active_filter_ko_chips`로, 방문 목록
  칩은 칩 dict의 `lang` 키로 값을 준다.
- `lang`을 `.record-row-pills`·`.record-row-end`·`.status-row`나 그 조상에 붙이지
  않는다. `archive.css`의 `:not(:lang(ko))` 선택자가 이 요소를 고른다.

## 색 계약 가드

`tests/core/test_category_token_contract.py`가 네 가지를 강제한다.

1. `tokens.css`에 12슬롯 × soft/ink 토큰이 **존재**한다
2. 그 토큰 **값이 `PALETTE`와 일치**한다 — 이름만 검사하면 두 파일이 조용히
   어긋나고, 스태프 화면(Python hex)과 소비자 화면(CSS 토큰)의 색이 달라진다
3. 활성 카테고리는 모두 유효 슬롯에 배정돼 있다
4. `tokens.css`의 `--dot-*` 이름 집합이 `core.vocab.CATEGORY_SOURCE_LABELS`의 키
   집합과 같다
   (`test_tokens_css의_점_색_토큰_이름은_고정_카테고리_슬러그_집합과_같다`)

그래서 `--dot-slot` 같은 새 이름을 `tokens.css`에 넣으면 4번이 깨진다. 슬롯
점 변수는 `category.css`에 둔다.

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
