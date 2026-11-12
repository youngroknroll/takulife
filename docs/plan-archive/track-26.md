# 트랙 26: 스태프 이벤트 목록 정렬·기간·카테고리 필터 (2026-09-12) [v1 — PSO·DAR·WED·BIR·TDD 코치 병렬 검토 반영, 인용은 오케스트레이터가 전수 재확인, **착수 승인 대기**]

> **위치**: 백로그 H2의 마지막 조각. 트랙 24 일괄 비공개(PR #350)·트랙 25 인라인 단건(PR #353) 완료 후 남은 것. 순서는 PSO 판정 [문서 `docs/backlog.md` H2 행].
> **기준선** [실측 2026-09-12, main `cfd69d3a`]: `uv run pytest -q` → **2684 passed / 10 deselected / 76.90초**, `check` 0 issues, `makemigrations --check --dry-run` 무변경.
> **데이터 실태** [실측 2026-09-12, 로컬 개발 DB]: 전체 171건 = 게시 171건 / 비공개 0건. 게시 중 종료 **149건(87.1%)** [계산]. 카테고리 분포 극장특전 37·팝업 30·전시 27·팬미팅 26·콜라보카페 26·굿즈예약 22·**빈 값 3**·**콘서트 0** [실측]. 페이지 크기 15건 [코드 `events/queries.py:184`].

## 오케스트레이터 정정 기록 (착수 전)

검토 과정에서 나온 사실 오류 [계산 3건]를 여기 남긴다 — 계획 본문은 정정된 값을 쓴다.

1. **`_event_filter_query_pairs` 호출부는 정의를 뺀 5곳이다** [실측 `rg -n '_event_filter_query_pairs' staff/views/events.py` → 120(정의)·145·320·436·479·514]. DAR가 6곳이라 보고했고 오케스트레이터가 그대로 되풀이했다. TDD 코치가 정정했다.
2. **`pager_query`는 이미 `q`를 포함한다** [코드 `staff/views/events.py:146-147` `if search: query_pairs.append(("q", search))`]. 따라서 페이저는 검색어를 잃지 않는다. `q` 소실 결함의 실제 위치는 ① 템플릿 탭·칩 링크(`templates/staff/events/list.html`, `q=` **0건** [실측 `grep -c`]) ② `list_query`를 쓰는 CRUD 뷰 [코드 4곳: 320·436·479·514]뿐이다. 오케스트레이터 초기 서술이 페이저까지 포함하는 것처럼 읽혔다.
3. **`AGENTS.md` Over-Engineering 절에 "반복 3회 이상이면 추상화" 문구는 없다** [실측 `sed -n '1043,1050p' AGENTS.md` — 수치 임계값 0건]. 그 규칙은 사용자 전역 `golden-principles.md` 소속이다. 오케스트레이터 브리프가 출처를 잘못 붙였고 DAR가 정정했다.

DAR의 역정정 [계산 2건]은 오케스트레이터가 재측정해 **기각**했다: `web/views/archive.py:106-110`의 `sort`·`page` 제외 주석 인용은 정확했고(DAR는 `sort not in` 검증 위치라는 다른 대상을 쟀다), `staff/views/events.py`는 **633행**이다 [실측 `wc -l` 633 + 파일 끝 개행 확인].

## Activated Roles / Not Activated

| 역할 | 활성 | 사유 |
|---|---|---|
| Product Scope Owner | ✅ | 필터 축·옵션 집합·기본값이 제품 결정 |
| Domain Architecture Reviewer | ✅ | 필터 검증·ORM 번역의 소유 계층이 바뀜 |
| Backend TDD Coach | ✅ | 목록 조회 동작 변경 |
| Backend & Integration Engineer | ✅ | 뷰·쿼리·어휘 구현 |
| Web Experience Designer | ✅ | 툴바 상호작용 요소가 [계산] 10개에서 26개로 늘어 배치 재설계 필요 |
| Browser Interaction Reviewer | ✅ | 기존 일괄·행 액션 JS와의 상호작용, 포커스·키보드 |
| Frontend Implementation Engineer | ✅ | 템플릿·CSS 구현 |
| Quality Verification Lead | ✅ | 최종 증거 대조 |
| Security & Resilience Reviewer | ❌ | 신뢰 경계 변경 없음 — 스태프 전용 GET 필터이고 값은 허용 목록 대조 후 ORM 파라미터로만 쓰인다. 새 외부 fetch·업로드·권한 경로 0건 |
| Deployment & Operations Reviewer | ❌ | 마이그레이션·환경 변수·CI·프로세스 기동 변경 0건 |
| AI Automation Architect | ❌ | LLM·프롬프트·모델 평가 범위 0건 |

## 승인 범위

목록 상단에 **단일 선택 링크** 필터 3축을 추가한다 [계산]. 폼 입력(`<input type="date">`, `<select>`)은 범위 밖이다.

| 파라미터 | 허용 값 | 없거나 허용 밖 |
|---|---|---|
| `?sort=` | `closing_soon`(종료 임박순) / `start_asc`(시작일 빠른순) | 현행 `-created_at` 유지 |
| `?period=` | `upcoming` / `ongoing` / `closing_soon` / `ended` | 전체 기간 |
| `?category=` | `CATEGORY` 7종 슬러그 [코드 `core/vocab.py:21-29`] | 전체 카테고리 |

기존 축(`warning`·`publish_status`·`q`)과 **AND 결합**한다. 기간 경계는 소비자 구현과 같은 규칙을 쓴다 [실측 `events/querysets.py:48-65`, `CLOSING_SOON_DAYS = 4` at `:7`].

### 함께 고치는 기존 결함

기록된 사용자 결정(2026-08-25, `CLAUDE.md` "Engineering Guardrails")에 따라 같은 유형·소규모 결함은 보고 후 같은 트랙·같은 PR에서 고친다.

- **F-A `q` 소실** — 검색 중 탭·칩을 누르면 검색어가 조용히 풀린다. 검색창 값은 남아 사용자가 여전히 검색 중이라고 오인한다. 가드레일 S9(`docs/FE/staff-console-redesign.md:147-159`)가 이미 같은 원칙("페이저도 같은 이유로 `q`를 유지한다")을 규정하는데 이 경로만 어긴다. PSO가 범위 포함 판정.
- **F-B 0건 복구 링크 부재** — `templates/staff/accounts/list.html:61`·`templates/staff/audit_log/list.html:67`은 0건일 때 "검색 지우기" 링크를 주는데 `templates/staff/events/list.html`에는 "검색" 문자열이 **0건**이다 [실측 `grep -c`]. 이 화면만 저장소 관례의 예외다. 축이 늘면 0건 도달 확률이 올라간다. BIR 발견.

## 명시적 제외

- 카테고리 **다중 선택** — 기존 필터가 전부 단일 선택이고 운영 문서가 다중을 요구하지 않는다
- 기간 **직접 날짜 입력**(from/to) — `docs/event-operations-criteria.md`에 임의 기간 조회 요구 0건
- `sort=newest` 미노출 — 소비자의 `newest`는 `-id` 기준 [코드 `events/querysets.py:154-155`]이라 스태프 기본값 `-created_at`과 의미가 겹치면서 기준만 다르다
- **필터 전환 후 포커스 복원 스크립트** — BIR 권고이나 결함이 아닌 기존 갭의 연장. 필터에 JS가 없는 화면에 JS를 들이는 변경이라 이연
- **카테고리 어휘 자체의 스태프 CRUD(생성·수정·삭제)** — 사용자가 2026-09-12에 요청했으나 **스키마 변경 트랙이라 트랙 26에 넣지 않는다**. 아래 "트랙 27 후보" 절 참고. 트랙 26은 현행 `core/vocab.py` 상수 어휘를 그대로 읽는다
- 저장된 필터 프리셋·정렬 상태 서버 저장, CSV 내보내기(백로그 「착수하지 않는 것」)
- **재검증("검증 완료") 운영 절차 정의** — H2의 미해결 제품 결정 [문서 `docs/backlog.md`], 이 트랙이 푸는 문제가 아니다. 기존 검증 버튼 문구·동작 무변경
- 보류·이연 기록 항목(RBAC, 정기 수집 스케줄러 등) 재제안 안 함

## Domain Boundary and Dependency Direction

DAR 판정. 방향 위반 **없음**.

- **어휘**는 `core/vocab.py`가 소유한다. `staff → core` 방향이며 `core/vocab.py`는 어떤 도메인 모듈도 import하지 않는 순수 상수 모듈이다
- **필터 값 검증**(허용 목록 대조)은 뷰(`staff/views/events.py`)가 소유한다. 선례 = `web/views/archive.py`의 `if sort not in ...` [실측 4곳: 113·227·459·596]
- **정렬 슬러그 → ORM 번역**은 `events/queries.py`가 소유한다. 뷰가 `-start_date` 같은 ORM 표현을 만들어 넘기지 않는다. 관용구 = `archive/queries.py:38-41,48-50,56-59,65-68`의 `ARCHIVE_*_SORT_ORDERING` 모듈 레벨 dict
- `events/` → `staff/` 역참조는 현재도 이후도 0건 [실측 `events/queries.py:1-9` import 목록]
- `staff/search.py`에 이벤트 목록 전용 필터 지식을 섞지 않는다 — 그 모듈의 소유 범위는 "3화면 공유 검색 폼 파라미터 위임"이다 [코드 `staff/search.py:1-15`]

### 어휘 결정 (DAR 규칙 + WED 발견의 합)

WED가 라벨 불일치를 지적했다: PSO가 기본 정렬 라벨을 "등록 최신순"이라 했으나 `EVENT_SORT_LABELS[""]`는 **"기본순"**이다 [실측 `core/vocab.py:180`]. 소비자 `""`는 `_ordered_by_default_state`(진행중/예정/종료 우선순위)이고 스태프 `""`는 `-created_at`이라 **동작 자체가 다르다**.

DAR 규칙("옵션 집합이 다르면 `core/vocab.py`에 별도 튜플")을 적용해 해소한다:

```python
STAFF_EVENT_SORT: tuple[tuple[str, str], ...] = (
    ("", "등록 최신순"),
    ("closing_soon", "종료 임박순"),
    ("start_asc", "시작일 빠른순"),
)
STAFF_EVENT_SORT_LABELS: dict[str, str] = dict(STAFF_EVENT_SORT)
```

슬러그는 `EVENT_SORT`와 공유하고 라벨만 스태프 실동작에 맞춘다. 템플릿 하드코딩 없음.

⚠️ **기간 어휘 함정(TDD 코치 발견)**: 멤버십 검사에 `EVENT_STATUS_LABELS`를 쓰면 안 된다 — 그 dict에는 소비자 표시용 `"all"` 키가 사후 추가돼 있어 [실측 `core/vocab.py:173`] `?period=all`이 유효 값으로 통과한다. **`EVENT_STATUS` 튜플**에서 만든 집합으로 검사한다.

## Coupling and Cohesion Review

`_event_filter_query_pairs`(`staff/views/events.py:120-127`)는 **필터 키 단일 출처** 역할을 한다. 확장하지 않고 새 축을 빠뜨리면 목록 페이저뿐 아니라 **수정·게시토글·검증·삭제 흐름의 목록 복귀**가 새 필터를 조용히 잃는다 [실측 호출부 5곳: 145·320·436·479·514]. 호출부마다 키를 개별 추가하는 방식은 금지한다.

`events/queries.py`는 220행 [실측], `staff/views/events.py`는 633행 [실측]. 후자는 CLAUDE.md 기준(200-400행 보통, 800 최대)의 상단이라 DAR가 필터 헬퍼 모듈 분리를 **권고**했으나, 이 트랙의 승인 범위가 아니므로 **이연**한다(아래 Deferred).

## Pythonic Code Design

- `list_staff_events`는 키워드 전용 인자를 그대로 늘린다 — `sort`·`period`·`category` [계산 3개] 추가. 번들 dataclass/TypedDict는 재사용처도 검증할 조합 규칙도 없어 `AGENTS.md` Over-Engineering("가상의 필요를 위한 추상화 금지")에 걸린다
- 정렬 매핑은 모듈 레벨 dict 상수 + `.get(sort, 기본)` — `archive/queries.py` 관용구
- 기간 필터는 `EventQuerySet.with_public_status`(`events/querysets.py:48-65`)를 **재사용**한다. 경계 규칙을 두 번 쓰지 않는다
- `start_asc` 정렬은 DB 암묵 기본값에 기대지 말고 `F("start_date").asc(nulls_last=True)`로 **명시**한다 — 같은 파일 `:114`가 이미 그 관용구를 쓴다

## TDD Checkpoints (Backend TDD Coach 계약)

한 번에 하나씩. Red → 최소 Green → 다음. 리팩터링은 코치가 허용할 때만.

### 도메인 계층 — `tests/events/test_events_queries_display.py` (`class TestListStaffEvents`)

| ID | 테스트 | 상태 |
|---|---|---|
| D01 | `test_카테고리_필터를_지정하면_해당_카테고리_행사만_반환한다` | Red |
| D02 | `test_기간_필터_예정을_지정하면_시작일이_오늘_이후인_행사만_반환한다` | Red |
| D03 | `test_기간_필터_진행중을_지정하면_오늘이_기간_안인_행사만_반환한다` | Red |
| D04 | `test_기간_필터_종료_임박_경계는_나흘_이내만_포함한다` (parametrize: 나흘 포함 / 닷새 제외) | Red |
| D05 | `test_기간_필터_종료를_지정하면_종료일이_지난_행사만_반환한다` | Red |
| D06 | `test_기간_필터와_카테고리_필터를_함께_지정하면_AND로_결합된다` | Red |
| D07 | `test_정렬_파라미터_시작일_빠른순을_지정하면_시작일_오름차순으로_정렬한다` | Red |
| D08 | `test_시작일이_없는_행사는_시작일_빠른순_정렬에서_뒤로_밀린다` | Red |
| D09 | `test_정렬_파라미터_종료_임박순을_지정하면_아직_안_끝난_행사가_임박순으로_먼저_온다` | Red |
| D10 | `test_정렬_종료임박순과_기간_필터_종료임박은_서로_다른_축으로_동작한다` | Red |

### 웹 계층 — `tests/staff/test_staff_events_views.py` (현행 테스트 함수 18개 [실측 `grep -c 'def test_'`])

| ID | 테스트 | 상태 |
|---|---|---|
| W01 | `test_카테고리_필터를_적용하면_context에_선택된_카테고리가_담기고_목록이_좁혀진다` | Red |
| W02 | `test_허용되지_않은_카테고리_값을_지정하면_필터_없이_전체_행사가_노출된다` | Red |
| W03 | `test_기간_필터를_적용하면_context에_선택된_기간이_담기고_목록이_좁혀진다` | Red |
| W04 | `test_허용되지_않은_기간_값을_지정하면_필터_없이_전체_기간이_노출된다` (parametrize: 없는 값 / **`all`**) | Red |
| W05 | `test_정렬_파라미터를_적용하면_context에_선택된_정렬이_담기고_목록_순서가_바뀐다` | Red |
| W06 | `test_허용되지_않은_정렬_값을_지정하면_필터_없이_현재_정렬이_유지된다` | Red |
| W07 | `test_검색_중_수정_화면으로_이동해도_검색어가_목록_복귀_링크에_남는다` (F-A) | Red |
| W08 | `test_목록에서_검색어와_페이지_이동을_함께_하면_검색어가_한_번만_담긴다` | **이미 Green (핀)** |
| W09 | `test_정렬_기간_카테고리를_지정한_채_수정_화면으로_이동해도_모두_list_query에_남는다` | Red |
| W10 | `test_정렬_기간_카테고리를_지정하지_않으면_기존_생성일_내림차순_전체_노출이_유지된다` | **이미 Green (핀)** |

### 템플릿 링크 계약 — 같은 파일 (오케스트레이터 추가)

TDD 코치의 브리프는 백엔드 범위만 받아 이 항목을 후속 트랙으로 분류했으나, **이 트랙에 템플릿 변경이 포함되므로 여기서 함께 못 박는다.**

| ID | 테스트 | 상태 |
|---|---|---|
| W11 | `test_검색_중_게시상태_탭_링크는_검색어를_유지한다` (F-A) | Red |
| W12 | `test_검색_중_경고_칩_링크는_검색어를_유지한다` (F-A) | Red |
| W13 | `test_기간_칩_링크는_현재_걸린_다른_축을_모두_이어받는다` | Red |
| W14 | `test_카테고리가_선택되면_카테고리_접기가_펼쳐진_채_렌더된다` (`<details open>`) | Red |
| W15 | `test_필터가_걸린_채_0건이면_필터_초기화_링크가_노출된다` (F-B) | Red |

### 이미 Green인 핀 — 뮤테이션 증거 필수

이 저장소의 구속 규칙이다. 처음부터 통과하는 테스트는 아무것도 증명하지 않을 수 있다. 대상은 W08·W10 [계산 2건].

- **W08 (반중복 핀)** — 구현 후 `staff_events` 뷰에 옛 `query_pairs.append(("q", search))` 줄을 되살려 `pager_query`의 `q=` 개수가 둘이 되는지 확인 → Red → 되돌려 Green. `_event_filter_query_pairs`에 `q`를 추가하면서 옛 줄을 안 지우면 실제로 일어나는 실수다
- **W10 (무필터 회귀 핀)** — `_selected_event_filters`의 `period` 기본값을 `""` 대신 `"ended"`로 바꿔 목록·컨텍스트가 달라지는지 확인 → Red → 되돌려 Green

### 테스트 함정 (착수 전 필독)

- ⚠️ **S9 검색어 단언 함정** — 본문 전체에서 `q=검색어`를 찾는 단언은 **결함이 있어도 통과한다**. 검색창 `value="{{ q }}"`와 새로고침 링크(`request.get_full_path`)에 검색어가 항상 들어 있기 때문이다. 과거 트랙에서 실제로 두 번 그랬다 [문서 `docs/FE/staff-console-redesign.md:157-159`]. W07·W09는 `resp.context["list_query"]`만, W08은 `resp.context["pager_query"]`만 단언한다. W11~W13은 **href 전체 문자열**을 단언한다
- ⚠️ **Django href 자동 이스케이프** — 템플릿이 href의 `&`를 `&amp;`로 이스케이프하므로 `html.unescape(resp.content.decode())`를 먼저 걸지 않으면 단언이 `&`를 못 찾는다. 선례와 그 이유 주석: `tests/archive/test_archive_search.py:150-154`
- **오늘 날짜 고정 방식** — 기존 테스트는 시간을 얼리지 않고 `date.today()` 상대 오프셋을 쓴다 [코드 `tests/staff/test_staff_events_views.py:117-134`]. 새 `period` 테스트도 같은 관례를 따른다
- **NULL 정렬은 DB 계약** — 로컬·CI 모두 PostgreSQL 16이다 [실측 `connection.vendor` → postgresql, `.github/workflows/ci.yml:20,27-28`]. 단 `DATABASE_URL`이 비면 sqlite로 폴백하고 [코드 `config/settings.py:62-64`] sqlite는 ASC에서 NULL을 **앞**에 놓는다. D08이 이 계약을 고정하고, 구현은 `nulls_last=True`를 명시해 DB 기본값 의존을 없앤다

## 프론트 설계 명세 (WED 사전 산출, Standard)

### 배치 — 행 분리 + 카테고리만 `<details>` 접기

- **첫째 줄 `.events-toolbar`**(기존 클래스 유지): 게시상태 탭그룹(불변) + **정렬 탭그룹**(`.events-tabgroup`/`.events-tab` 재사용, 신규 CSS 0줄) + CTA(우측 고정). 상호작용 요소 [계산 7개]
- **둘째 줄 `.events-filterbar`**(신규): 경고 칩그룹(불변, 최우선 자리 유지) + **기간 칩그룹**(`.events-chipgroup`/`.events-chip` 재사용) + **카테고리 `<details>` 토글**(접힘 기본, 선택 시 서버가 `open` 렌더). 상호작용 요소 [계산 12개]
- `.events-toolbar, .events-filterbar`로 flex 규칙을 공유해 중복 선언 방지(OOCSS)

**기각된 대안** [계산 3가지]: 전부 한 줄 wrap(경고 칩이 새 축 사이에 묻혀 시각 우선순위 소멸), 필터 전체를 하나로 접기(주간 최우선 작업인 경고 칩에 클릭이 늘어남), `<select>` 드롭다운(값 변경 시 이동에 JS 필요 — 단일 선택 링크 제약 위반).

**정렬은 탭그룹, 표 헤더 클릭은 기각**: 기본값 "등록 최신순"에 대응하는 등록일 컬럼이 표에 없고, 종료임박순·시작일빠른순이 같은 "기간" 컬럼을 가리켜 한 헤더가 세 상태를 토글해야 한다. 또 `.events-table td`가 전부 `overflow:hidden;text-overflow:ellipsis;white-space:nowrap` [코드 `static/css/staff/pages/events.css:113-120`]이라 14rem 고정폭 안에 정렬 아이콘 여유가 없다.

### 신규 CSS (최소)

```css
.events-filter-disclosure { align-self: flex-start; }
.events-filter-disclosure-summary { cursor: pointer; list-style: none; }
.events-filter-disclosure-summary::-webkit-details-marker { display: none; }
```
`is-active` 상태는 기존 `.events-chip.is-active`를 그대로 쓴다. 빈 상태 목록용 `.events-empty-filters` [계산 1개] 규칙을 더한다.

⚠️ **`.rule-list` 재사용 불가** — `static/css/objects/layout.css:27`에만 정의돼 있고 스태프 셸은 그 파일을 로드하지 않는다 [실측 `templates/staff/base_staff.html:37-41` — `tokens`·`base`·`shell`·`confirm-modal`만 로드]. 반드시 `--c-*` 토큰으로 새로 정의한다(S6).

### 빈 상태 (F-B 해소 포함)

```html
<div class="events-empty">
  <p class="events-empty-title">조건에 맞는 이벤트가 없습니다.</p>
  {% if active_filter_summary %}
  <ul class="events-empty-filters">
    {% for item in active_filter_summary %}<li>{{ item.label }}: {{ item.value }}</li>{% endfor %}
  </ul>
  <a href="{% url 'staff:event-list' %}">필터 초기화</a>
  {% endif %}
</div>
```
⚠️ **S9: 빈 상태 문구에 조사(을/를·과/와)를 쓰지 마라** — 사용자 입력 끝 글자가 자음이냐 모음이냐에 따라 달라져 템플릿에서 고를 수 없다. "라벨: 값" 포맷이 이 문제를 원천 회피한다. 필터가 전부 기본값이면 기존 한 줄만 렌더한다.

### 접근성 (정적)

기존 관례 그대로 확장 [코드 `templates/staff/events/list.html:12-15`]: 각 그룹에 `role="group"` + `aria-label`, 활성 링크에 `aria-current="true"` + `aria-label="{라벨}, 적용됨"`. `<details>`/`<summary>`는 네이티브 펼침 의미를 가지므로 `aria-expanded`·커스텀 JS 불필요.

**활성 상태 요약 바는 추가하지 않는다** — 소비자의 `_active_filter_chips`는 다중 선택과 접힌 필터 패널을 위한 것이다. 스태프는 축이 전부 단일 선택이고 카테고리 외에는 항상 펼쳐져 있어 `.is-active`가 각 축 자리에서 바로 보인다. 추가하면 상시 노출 요소가 [계산] 하나 더 늘 뿐이다.

## 상호작용 명세 (BIR 사전 산출, High)

### 새 `data-*` 속성 불필요 — 서비스 계층으로 증명됨

세 액션 모두 날짜·카테고리를 저장하지 않는다 [실측]:
- `events/services.py:193` `unpublish_event` → `save(update_fields=["publish_status"])`
- `events/services.py:213` `republish_event` → `save(update_fields=["publish_status"])`
- `events/services.py:220` `mark_event_verified` → `save(update_fields=["verified_at"])`

따라서 `period`(start_date/end_date 기반)·`category` 소속은 이 액션들로 이동하지 않고, `event_bulk.js:121-128`·`event_row_actions.js:184-199·223-234·262-273`의 기존 `publish_status`/`warning` 전용 행 제거 판정은 그대로 옳다. **`templates/staff/events/list.html:47`의 `data-selected-*` 속성을 늘리지 않는다** [코드 현재 2개].

⚠️ **가정 노출**: 이 증명은 위 `update_fields`가 현 형태를 유지한다는 전제에 의존한다. 세 액션 중 하나가 편집 가능 필드로 확장되면 재검증이 필요하다.

### BIR 수용 기준

1. 신규·기존 링크 **전부**가 현재 걸린 모든 축을 예외 없이 서로 이어받는다. 단일 공유 소스(`_event_filter_query_pairs` 확장)를 쓰고 손조립 템플릿 조건문 반복은 **허용하지 않는다**. 미달 시 사후 검토에서 Deviates
2. 각 새 링크는 활성 시 `aria-current="true"` + 선택 상태 `aria-label`
3. `period`/`category`가 걸린 상태에서 verify/unpublish/republish/bulk-unpublish를 실행해도 행 유지·제거 판정이 기존 `data-*` [코드 2개]만으로 충분함을 유지
4. 0건 도달 시 필터를 초기화할 링크를 빈 상태에 명시 (F-B)

### 기록된 정보 (결함 아님)

- 포커스: 전체 페이지 리로드라 포커스가 `<body>`로 복귀. skip-link(`templates/staff/base_staff.html:45`)로 사이드바를 우회해도 표까지 Tab 횟수가 [계산] 10회에서 26회로 는다. 기존 갭의 정도 악화(Medium)
- live region `#event-live`는 JS 액션 전용이라 필터 전환과 무관
- 터치 타깃 26px/28px [코드 `static/css/staff/pages/events.css:35,69`] — 44px 게이트는 2026-07-22 사용자 결정으로 폐지 [실측 `AGENTS.md:910-919`]. 정보로만 기록

## 구현 단계 (커밋 경계)

| # | 내용 | 파일 |
|---|---|---|
| 1 | `STAFF_EVENT_SORT`/`_LABELS` 추가 + **D01** | `core/vocab.py`, `events/queries.py`, 도메인 테스트 |
| 2 | **D02→D03→D04→D05** 기간 필터 (`with_public_status` 재사용) | `events/queries.py` |
| 3 | **D06** AND 결합 | 〃 |
| 4 | **D07→D08** 시작일 빠른순 + NULL 핀 (`nulls_last=True` 명시) | 〃 |
| 5 | **D09→D10** 종료임박순 + 축 혼동 방지 핀 | 〃 |
| 6 | `_selected_event_filters` 확장 + **W01~W06** | `staff/views/events.py` |
| 7 | `_event_filter_query_pairs`에 `sort`·`period`·`category`·`q` 추가 + 뷰의 옛 `q` 줄 제거 + **W07→W08(뮤테이션 필수)→W09** | 〃 |
| 8 | 템플릿·CSS(WED 명세) + **W11~W15** | `templates/staff/events/list.html`, `static/css/staff/pages/events.css` |
| 9 | **W10** + 기존 도메인 핀 재확인 + 전체 회귀 | — |

## 검증 명령과 기대 증거

```bash
uv run pytest -q tests/events/test_events_queries_display.py   # 단계별 표적
uv run pytest -q tests/staff/test_staff_events_views.py        # 단계별 표적
uv run pytest -q                                               # 최종 회귀
uv run python manage.py check                                  # 0 issues
uv run python manage.py makemigrations --check --dry-run       # No changes detected
```

- 최종 회귀 기대치: 기준선 2684 passed [실측] + 신규 테스트. 신규는 D01~D10 [계산 10건] + W01~W15 [계산 15건] = [계산 25건] 이상이며, parametrize 때문에 실제 수집 수는 더 많다. **실제 수는 실행 후 기입한다**
- 마이그레이션 [계산 0건] — 모델 변경이 없다
- 뮤테이션 증거 [계산 2건] W08·W10 — 각각 Red 확인 후 되돌려 Green 재확인
- 브라우저 실측(BIR 사후 판정용): 1024×768·1280·1440px에서 툴바 총높이·표 첫 행 y좌표, 링크 [계산 26개]의 실제 줄바꿈, 검색어 입력 → 탭 클릭 → 주소창 `q=` 유지, 0건 빈 상태 도달
- WED·BIR **사후 판정**(Conforms/Deviates) 필수 — 역할 나열은 증거가 아니다

## Deferred Refactoring Note

```text
- Topic: staff/views/events.py(633행 [실측])의 필터 검증·querystring 헬퍼 모듈 분리
- Why not now: 승인 범위는 필터 축 추가. 순수 정리이고 동작 변경이 없다
- Trigger: 파일이 800행 [문서 CLAUDE.md]에 근접하거나 필터 축이 더 늘 때
- Expected location: staff/views/_event_filters.py

- Topic: "필터 보존 querystring 생성" 변종 [실측 6개]의 공용 유틸화
- Why not now: 변종마다 배제 규칙이 다르고(달력은 sort 제외, 스태프는 q 제외) 그 차이가 주석으로 명시된 의도된 계약이다. 이번 범위는 스태프 목록 한 화면
- Trigger: 변종이 [계산] 여덟 번째로 늘거나 기존 변종에서 배제 규칙 버그가 실제로 발견될 때
- Expected location: core/ 공용 함수(include_keys/exclude_keys 인자)

- Topic: 카테고리 "미분류" 축 (빈 값 [실측 3건])
- Trigger: 사용자 승인. 백로그 후보로만 기록

- Topic: 필터 전환 후 활성 링크 포커스 복원 스크립트 (BIR 권고)
- Why not now: 결함이 아닌 기존 갭의 연장. 필터에 JS가 없는 화면에 JS를 들인다
- Trigger: 키보드 사용 운영자의 실제 불만 관측

- Topic: start_date·end_date·category 인덱스 (현재 [실측 0건] rg events/models.py)
- Why not now: 게시 171건 [실측] 규모에서 순차 스캔 비용이 문제가 아니다. 소비자 목록도 같은 열을 인덱스 없이 필터·정렬한다
- Trigger: 목록 응답 지연 실측 또는 카탈로그 수천 건 도달
```

## 문서 대상 / 핸드오프

- **`docs/BE/staff-event-publish-actions.md`** — H2 계열 정본. 필터 축 계약과 `_event_filter_query_pairs` 단일 출처 규칙을 추가한다
- **`.docs/FE/`** 기술 기록 — 프론트 구현에 필수 [실측 `AGENTS.md:921-923`]. WED·BIR 원문과 브라우저 실측을 담는다. `.docs/`는 git-ignored
- **`docs/backlog.md`** — H2 행을 트랙 26 완료로 갱신하고 H2 자체를 종결한다. 이연 항목(미분류 축·포커스 복원·인덱스)을 추가한다
- **`docs/FE/staff-console-redesign.md`** — 새 가드레일이 생기면(예: `.rule-list` 미로드로 인한 빈 상태 CSS 규칙) S 항목으로 추가
- PR 머지 후 **`docs/pr-log.md`** 롤링

## 사용자 결정 기록 (2026-09-12)

아래 [계산 3가지]는 사용자가 확정했다.

1. **기간 프리셋 `closing_soon` 유지** — 프리셋은 넷을 그대로 간다(예정/진행 중/종료 임박/종료). `EVENT_STATUS` 어휘를 부분집합 없이 통째로 쓴다
2. **결함 F-A·F-B [계산 2건] 이 트랙에 포함** — 기록된 2026-08-25 결정과 같은 결
3. **카테고리 칩 건수 배지 포함** — PSO의 "제외" 권고가 뒤집혔다. 아래 절이 그 범위다

## 카테고리 칩 건수 배지 (사용자 결정으로 추가된 범위)

칩 라벨 옆에 해당 카테고리의 건수를 표시한다(예: "콘서트 (0)"). 운영 문서 §1의 "특정 카테고리가 2주 이상 공백이면 그 카테고리 소스를 우선 조사"를 **클릭 전에** 보이게 하는 것이 목적이다 [문서 `docs/event-operations-criteria.md:19-22`].

- **집계 위치**: `events/queries.py` — `list_staff_events`와 같은 모듈이 소유한다. 뷰는 슬러그→건수 매핑만 받고 ORM 세부를 모른다(DAR의 정렬 매핑 판정과 같은 경계)
- **쿼리 비용**: `GROUP BY category` 집계가 요청당 [계산 1회] 추가된다. 행마다 재조회하는 N+1이 아니다

### 배지 의미 (PSO 판정 + 사용자 확정)

- **무엇을 세는가 — A안 채택**: `category`만 뺀 나머지 활성 필터(`period`·`warning`·`publish_status`·`q`)를 **전부 반영**한 카테고리별 건수. 즉 "이 칩을 누르면 나올 건수"다. B안(전역 총계)은 배지 값과 클릭 후 실제 건수가 어긋나는 정적 패싯 카운트 결함을 낳고, 이 트랙이 세우려는 "필터 조합 = AND, 그대로 반영" 계약과 정면으로 모순된다. 필터 무선택 화면에서는 A와 B가 같은 값이라 운영 문서 §1의 공백 점검 용도는 A로도 충족된다
- **"전체" 칩에도 배지를 붙인다**. 값은 표 하단 `page_obj.paginator.count`(`templates/staff/events/list.html:104`)와 **같은 쿼리셋**에서 나와야 한다 — 한 화면에 서로 다른 "전체" 숫자가 둘 뜨는 사고를 막는다
- **8번째 칩 "미분류" 신설** (사용자 확정 2026-09-12). `category=""`가 대상이다. `core/vocab.py:210-216` `is_valid_category`가 이미 `""`를 **"미분류"라는 이름으로 일부러 유효하게** 취급하므로 발명이 아니라 기존 1급 상태의 노출이다 [실측 독스트링 원문]. 어휘 밖 자유 텍스트 오염은 **0건**이고 빈 값은 정확히 빈 문자열 3건이다 [실측 2026-09-12, 로컬 개발 DB] — 버킷 정의가 `category=""` 하나로 깔끔하다
- **0건 칩을 숨기지 않는다**. "콘서트 (0)"처럼 그대로 표시한다. 숨기면 운영 문서 §1이 원하는 공백 신호 자체가 사라진다. 배지 옆에 "우선 조사 필요" 같은 안내 문구는 붙이지 않는다(안내 문구 최소화 방침)

### 배지 수용 기준 (PSO 추가분)

9. `?category=exhibition` 요청의 칩 배지 값은, 같은 요청에서 `category`만 제거하고 나머지 필터를 유지한 쿼리로 카테고리별로 센 건수와 같다. 배지 값과 그 칩을 눌렀을 때의 실제 표시 건수가 항상 일치한다
10. "전체" 칩 배지 값은 같은 필터 조합의 `page_obj.paginator.count`와 같다
11. **칩 배지 값의 합 == "전체" 칩 배지 값**이 어떤 필터 조합에서도 성립한다. 미분류 칩이 이 등식을 보장한다
12. 매치 0건인 칩도 다른 칩과 같은 마크업으로 "(0)"을 표시하며 `hidden`·`display:none` 처리되지 않는다

### 배지 관련 추가 테스트

| ID | 테스트 | 상태 |
|---|---|---|
| D11 | `test_카테고리_건수는_다른_활성_필터를_반영하고_카테고리만_제외한다` | Red |
| D12 | `test_카테고리가_빈_행사는_미분류_건수에_집계된다` | Red |
| W16 | `test_카테고리_칩_건수의_합은_전체_칩_건수와_같다` | Red |
| W17 | `test_매치가_0건인_카테고리_칩도_숨기지_않고_0을_표시한다` | Red |
| W18 | `test_미분류_칩을_선택하면_카테고리가_빈_행사만_노출된다` | Red |

⚠️ **무필터 기본 화면 주의(기록)**: 게시 중 종료가 **149건(87.1%)** [실측 2026-09-12, 로컬 개발 DB]이라 무필터 배지는 대부분 이미 끝난 행사를 센다. PSO 판정 = 새로운 왜곡이 아니다 — 표 하단 `paginator.count`가 트랙 26 이전부터 같은 종류의 합계를 보여주고 있었고, 배지는 그것을 카테고리별로 분해할 뿐이다. `period=ongoing`으로 바꾸면 진행 중만 반영한 수가 나온다. 이 사용법을 알리는 안내 문구는 넣지 않는다

---

