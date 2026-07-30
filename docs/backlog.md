# takulife 백로그

기준일: 2026-07-30 · 기준 커밋: main `755fe0c`

## 이 문서에 대하여

2026-07-30 전수 검수(11역할 중 7역할 활성) 결과를 근거로 백로그를 처음부터 다시
작성한 것이다. 이전 백로그는 전부 폐기됐다.

- **폐기**: 시안 기반 백로그 `B1~B29`, 이관 항목 `E1~E8`, 디자인 리뷰 큐
  (`.docs/design-review-queue.md`). 시안을 다시 만들기로 하면서 함께 폐기됐고
  (2026-07-29 사용자 결정), 큐 파일 자체도 존재하지 않는다. **복구하지 마라.**
- **배치**: 이 문서는 `docs/`에 있다. `.docs/`는 git-ignored라 소실된다 —
  디자인 리뷰 큐가 실제로 그렇게 사라졌다. 살아 있는 백로그는 여기 둔다.
- **표기**: `[실측]`은 오케스트레이터가 뮤테이션/프로브 왕복으로 직접 잰 항목,
  `[코드]`는 소스 읽기로만 확인한 항목이다. 확신은 증거가 아니므로 구분한다.

## 현재 상태 (신선 실행 기준)

| 항목 | 값 |
|---|---|
| 백엔드 회귀 | `uv run pytest -q` → **2045 passed** |
| Django check | 0 issues |
| 마이그레이션 드리프트 | 없음 |
| 배포 차단 | **0건** (보안·운영 검토 모두) |
| 실행 순서 | 2·3·4단계 완료 / **5단계 미착수** / 6단계 정상 미착수 / 1단계 인프라 대기 |
| 행사 카탈로그 | 게시 169건 중 **141건 종료(83%)**, 진행·예정 28건, 검증 완료 0건 |

핵심 루프(발견 → 상태 → 방문 기록 → 굿즈 → 의도)는 URL·뷰·서비스 계층에서
끊긴 곳 없이 연결되어 있다. 교환(trade) 도메인은 존재하지 않으며, 이는 게이트
승인 전 착수 금지 원칙이 지켜지고 있다는 뜻이다.

---

## A. 안전망 복구 — **착수 확정** (2026-07-30 사용자 결정)

전부 실측으로 확인한 거짓 초록이다. 통과하는 2013건이 이 영역에서는 아무것도
보장하지 못하므로, 이후 모든 작업의 회귀 감지가 여기에 의존한다.

### A1 [실측] 도메인 경계 가드가 5개 모듈과 동적 임포트를 보지 못한다

- 근거: `tests/core/test_architecture_boundaries.py:31-63`(파라미터 목록),
  `:13-22`(`_imported_modules`가 `ast.Import`/`ast.ImportFrom`만 순회)
- 실측 1: `events/queries.py`에 `from archive.models import CollectionItem`을
  넣고 전체 실행 → **2013 passed**. 목록에 없는 모듈이라 무검출.
- 실측 2: `drafts/views.py`에 `importlib.import_module("archive.models")`를
  넣고 전체 실행 → **2013 passed**. 동적 임포트는 어느 모듈에서든 무검출.
- 누락 모듈: `events/models.py`, `events/queries.py`, `drafts/models.py`,
  `drafts/serializers.py`, `drafts/queries.py`
- 범위: 파라미터 목록 5줄 추가 + `_imported_modules`가 `ast.Call`의
  `importlib.import_module(...)`/`__import__(...)` 문자열 인자도 수집하도록 확장

### A2 [실측] 서명 규약 가드가 `core.analytics`를 보지 않는다

**최초 서술 정정(2026-07-30).** 이 항목은 원래 "`accounts.services`의 위반
4건"으로 적혀 있었다. **그 전제가 틀렸다.** 이 가드가 보호하는 것은 *다른
앱이 가로질러 호출하는* 서비스 경계이고, `accounts.services`는 호출처가
전부 앱 내부다(`accounts/views.py:118`, `accounts/signals.py:18,34`,
`purge_deleted_accounts.py:18`). `rg`로 재확인 — `accounts` 밖에서
임포트하는 프로덕션 코드 **0건**. 따라서 그 모듈의 위치 인자는 위반이
아니며, 목록에 넣고 서명을 바꾸는 것은 규약 집행이 아니라 규약 발명이었다.
호출처 약 20곳을 바꾸는 헛일이 될 뻔했다.

- **처리 완료**: `tests/core/test_service_signature_conventions.py` 모듈
  독스트링에 제외 근거를 기록했다. 다음 사람이 같은 오판을 하지 않도록.
- **실제 누락은 `core.analytics`다.** 이쪽은 진짜 교차 도메인 서비스다 —
  `events/views.py:10`, `staff/views/__init__.py:19`, `archive/services.py:7`이
  임포트한다. 이미 목록에 있는 `core.promotion`과 같은 성격인데 빠져 있다.
  비준수 함수 4개: `pseudonymous_user_key(user)`, `record_event(event_name, *, ...)`,
  `distinct_user_key_count_since(days=7)`, `event_name_counts_since(days=7)`
  (`core/analytics.py:40,73,113,127`).
- **미착수 — 별도 승인 필요.** `record_event` 호출처만 프로덕션 15곳 이상
  (`archive/services.py`에 다수)이라 A2보다 범위가 훨씬 크다. 위치 인자가
  의도된 설계라는 근거는 코드·문서 어디에도 없어 드리프트로 판단하지만,
  원 설계 의사는 **미확인**이다.

### A3 [실측] 보유/구함/교환 3축 술어가 8곳에 흩어져 있고 뮤테이션에 걸리지 않는다

- 근거: `core/views.py:1544,1546,1560,1562,1812,1816`,
  `archive/queries.py:516,521,584,586`
- 실측: `core/views.py:1544`를 `owned = item.quantity >= 0`(항상 참)으로
  바꾸고 전체 실행 → **2013 passed**.
- 이 중복은 이미 한 번 결함을 만들었다. `core/views.py:1538`의 주석이
  *"that duplication is what hid the original owned/wanted axis bug"* 라고
  스스로 적고 있다(PR #245).

**전수 실측(2026-07-30).** 술어 10개 지점 각각에 `> 0` → `>= 0`
(`__gt` → `__gte`) 뮤테이션을 걸고 매번 전체 스위트를 돌렸다. 종료 코드로만
판정했다 — 처음엔 stdout에서 `failed`를 문자열로 찾다가 AXES 로그의
"failed login attempts"를 테스트 실패로 오독했다.

| 지점 | 결과 |
|---|---|
| `views:1544` 보유 배지 | **무방비** (2022 passed) |
| `views:1546` 교환 배지 | **무방비** (2022 passed) |
| `views:1560·1562` 라벨 | 잡힘 (각 1건) |
| `views:1812·1816` 상세 행 | 잡힘 (2건·3건) |
| `queries:516·521·584·586` | 잡힘 (3~5건) |

미보호는 **10곳 중 2곳뿐**이었다. 원인은 `tests/archive/test_archive_collection_view.py:532`가
이미 `quantity=0` 항목을 만들어 **라벨만 단언하고 배지는 보지 않았기** 때문이다.

- **처리 완료**: 배지 축 테스트 2건 추가. 각 뮤테이션이 실제로 Red가 되는 것을
  왕복 확인했다(`:1544` → 1건, `:1546` → 2건).
- **남은 것은 안전이 아니라 구조다.** 10곳 모두 테스트로 덮였으므로 술어를
  모델로 옮기는 일은 더 이상 안전망 작업이 아니다. **E군(구조)으로 이관** —
  `core/views.py`를 크게 여는 [E1] 분할과 같은 트랙에서 처리하는 편이
  충돌이 적다.

### A4 [실측] 마크업 리터럴 단언 — **실제 위험은 41곳이 아니라 1곳이었다**

**완료(2026-07-30).** 착수 전 서술("13개 파일에 41회")이 **부풀려져 있었다.**
전수 실측 결과:

| 형태 | 수 | 판정 |
|---|---|---|
| `in` (양성) | 33 | 안전 — 리네임하면 즉시 시끄럽게 실패 |
| `not in` | 8 | 아래로 세분 |
| └ 실제 회귀를 놓침 | **1** | 컬렉션 빈 상태 — 뮤테이션으로 실증 |
| └ 이미 공허 | 2 | `class="current"`·`visit-filter` — 저장소에 없는 문자열 |
| └ 안정 앵커가 이미 있음 | 5 | 양성 단언·`aria-label`·앵커 개수 가드가 짝을 이룸 |

- **유일한 실결함**: `has_items` 게이트를 부수고 클래스를 리네임하면, 빈 컬렉션에
  검색 폼이 렌더되는 회귀가 살아 있는데도 통과했다. 검색 입력의 접근 이름
  (`aria-label="컬렉션 검색"`)으로 앵커를 바꿔 닫았다.
- **공허 2건 삭제**: `class="current"`는 오래전 삭제된 인라인 페이저의 잔재,
  `visit-filter`는 *"쓰지 말라"* 고 경고하는 CSS 주석에만 존재. 둘 다 절대 실패 불가.
- **`test_archive_nav.py`는 커버리지가 아니라 가독성 때문에 바꿨다.** 뮤테이션
  4가지를 시도했지만 새 단언이 고유하게 잡는 경우를 만들지 못했다 — 앵커 개수
  가드와 탭별 양성 단언이 이미 전부 잡는다. 정직하게 기록한다.

★ **A3(8곳→2곳)에 이어 두 번째 과대 서술이다.** `file:line` 근거를 달아도
개수는 추정이 섞인다. 착수 전 실측으로 범위를 좁히는 것이 매번 이득이었다.

★ **내 검증 절차의 결함 1건**: 앵커로 `<form`을 지정했다가 테스트가 깨졌다.
`collection.html`에 `<form`이 한 번뿐인 것만 보고 **base·partial 합성을 빠뜨렸다**
(`_topbar.html`의 로그아웃 폼이 모든 인증 페이지에 있다). 게다가 뮤테이션이
Red가 되는 것만 확인하고 **깨끗한 상태가 Green인지 확인하지 않았다** — 왕복의
절반만 돈 것이다. 이후 양방향을 모두 재도록 고쳤다.

<!-- 아래는 착수 전 서술 (보존) -->
### A4 착수 전 기록

- 근거: `tests/archive/test_archive_collection_view.py:422-430` 외,
  `assert ... class="..."` 패턴이 13개 파일에 41회
- 문제: 클래스명을 리네임하면 "존재하지 않는 문자열의 부재"를 검사하게 되어
  실제 회귀가 나도 계속 통과한다. 이 저장소는 리네임이 가드를 조용히
  무력화한 사례를 이미 겪었다.
- 좋은 반례: `tests/archive/test_archive_collection_detail_view.py:247-258`은
  태그 자체의 부재까지 함께 단언해 이 위험을 피했다.
- 범위: 조건부 렌더 검증을 `resp.context[...]` 단언으로 낮추는 것부터.
  전면 교체가 아니라 A1~A3 진행 중 마주치는 파일부터 점진 적용.

### A5 [실측] 500 페이지 테스트가 자기가 말하는 이유로 통과하지 않는다

E1 진행 중 발견했다. `tests/core/test_error_pages.py:26-47`의
`test_핸들러가_예외를_던지면_요청_컨텍스트_없이도_커스텀_500_페이지가_렌더링된다`는
독스트링에서 *"Simulate an unhandled view exception on `/`"* 라고 밝히고
`monkeypatch.setattr(..., _boom)`으로 뷰를 터뜨린다고 적어 두었다.

**그 패치 줄을 통째로 지워도 통과한다.** 실측한 실제 원인은
`RuntimeError: Database access not allowed` — 이 테스트에 `db` 픽스처가 없어서
홈 뷰의 DB 접근이 막히며 500이 나는 것이다. `_boom`은 처음부터 무하중이었다.

- 검증하려는 **결과**(요청 컨텍스트 없이 `500.html`이 렌더된다)는 여전히
  맞으므로 무가치한 테스트는 아니다. 다만 **서술한 메커니즘과 실제 메커니즘이
  다르다.** 다음 사람이 이 패치를 근거로 뷰 예외 경로가 검증된다고 믿으면 틀린다.
- 선택지: ①패치를 지우고 독스트링을 실제 이유(DB 접근 차단)로 고친다
  ②`db` 픽스처를 붙여 패치가 실제로 하중을 받게 한다. ②가 원래 의도에 가깝다.
- **미착수.** E1 범위 밖의 기존 결함이라 건드리지 않았다.

---

## B. 사용자 데이터 안전

### B1 [코드] 직접 등록에 수정 기능이 없어 오타 수정이 파괴적 삭제를 강요한다

- 근거: `archive/personal_urls.py:11-15` →
  `PersonalEntryDetailView(RetrieveDestroyAPIView)` (`archive/views.py:89`).
  대조: `CollectionItemDetailView(RetrieveUpdateDestroyAPIView)`
  (`archive/views.py:373`)는 PATCH를 갖는다.
- 영향: `personal_entry` FK가 `EventInterest`(`archive/models.py:26`),
  `UserEventStatus`(`:76`), `VisitRecord`(`:189`) 3곳에서 `CASCADE`다.
  장소명 오타 하나를 고치려면 삭제·재등록뿐이고, 그 순간 그 장소에 딸린
  방문 기록과 사진이 함께 사라진다. 우선순위 1·2 자산이다.
- 참고: 삭제 경고 문구는 정확히 있다
  (`static/js/pages/personal_entries.js:57-58`). 즉 "몰래 사라지는" 결함이
  아니라 **수정 경로 자체가 없는** 결함이다.
**백엔드 완료(2026-07-30).** `PersonalEntryDetailView`가 PATCH를 받는다.
PUT은 `http_method_names`로 제외했다 — 부분 수정이 언급하지 않은 필드를
비우면 안 되기 때문이다.

**PATCH를 열자 멱등 키가 함께 열렸다.** `client_token`이 시리얼라이저에
명시 선언돼 있어 모델의 `editable=False`를 덮는다. 실측으로 확인했다 —
PATCH 페이로드의 토큰이 저장값을 덮어썼고, 그러면 PR #246이 막았던 중복
생성이 다시 열린다. `CollectionItemUpdateSerializer`와 같은 방식으로
구조적 배제해 닫았다. **두 변경을 한 커밋에 넣은 이유**는 앞의 것만으로는
회귀이기 때문이다.

**해결됨(2026-07-30).** 브랜치 `feat/personal-place-detail-edit`(커밋 8건,
main 대비 +2199/−2)가 상세 라우트 `/archive/personal/<int:entry_id>/`와
수정 라우트 `/archive/personal/<int:entry_id>/edit/`를 열어 남은 절반을
닫았다. 상세 근거는 `docs/FE/personal-place-detail-edit.md`(프론트 이중
게이트 사후 verdict 4건, 전부 `Conforms`). 검증: `uv run pytest -q` →
**2045 passed**, Django check 0 issues, 마이그레이션 드리프트 없음.

---

## C. 제품 다음 단계

### C1 [코드] 북극성 지표를 지금 측정할 수 없다 — 실행 순서 5단계가 통째로 비었다

- 근거: `core/analytics.py:113-137`은 "최근 N일" 슬라이딩 윈도우뿐이고 월간
  코호트 개념이 없다. 대시보드가 내놓는 값은
  `staff/views/__init__.py:245-248`의 주간 활성 사용자 수 — 8종 이벤트를 전부
  합친 "아무 행동이나 한 사용자"라 *컬렉션 기여*로 좁혀져 있지 않다.
- 없는 것: 월간 컬렉션 기여 사용자, 활성화(첫 아이템·첫 기록), 재등록률,
  4주 재방문, 의도(구함/교환) 사용률, 완성도.
- 원자재는 이미 쌓이는 중이다 — `core/models.py:63-86`의 `AnalyticsEvent`에
  `COLLECTION_ITEM_CREATED`/`VISIT_RECORD_CREATED` 등이 있다. 새 배포도
  유료 서비스도 필요 없다.
- 왜 지금인가: 2·3·4단계가 실제로 끝났고 5단계만 비어 있다. 이 지표 없이는
  다음 기능 우선순위가 계속 추측이 된다.

---

## D. 사용자 흐름

### D1 [코드] 나의 일정의 방문 완료 행에 "기록 남기기" 진입로가 없다

- 근거: `templates/core/partials/_archive_results_statuses.html:79-83`의
  `visited` 분기는 "예정으로" 되돌리기와 삭제만 렌더한다. 해당 CTA는
  `templates/core/events/detail.html:197-199`에만 존재한다.
- 영향: 활동 관리 화면에서 방문 완료·미기록을 정리하려면 이벤트 상세로
  되돌아가야 한다. 핵심 루프의 마찰 지점.

### D2 [코드] 필터 칩의 활성 상태가 보조기술에 노출되지 않는다

- 근거: 칩을 렌더하는 템플릿 8곳 중 `templates/core/events/list.html:29-35`,
  `events/calendar.html:36-41`, `core/drafts/list.html:65-68`,
  `staff/events/list.html:22-24`에 상태 속성이 없다. 반면
  `archive/visits.html`·`statuses.html`·`index.html`은 이미 갖고 있다.
- 범위: 이미 검증된 형제 템플릿의 패턴을 복제. 다중 선택 칩(지역·카테고리)에
  `aria-current`가 맞는지 `aria-pressed`가 맞는지는 Web Experience Designer
  판정 필요.

### D3 [코드] 스태프 콘솔 POST 폼 7개 중 1개만 연타 가드가 있다

- 근거: 가드 있음 — `static/js/pages/staff_event_edit.js`(검증 완료 폼).
  가드 없음 — `templates/staff/events/edit.html`(4개),
  `events/create.html`, `events/delete_confirm.html`, `dashboard.html`.
- 영향: "게시 내리기" 연타 시 상태 역전 가능, "삭제 확정" 연타 시 두 번째
  요청이 404 오류 화면. "지금 수집"은 스스로 "수십 초가 걸릴 수 있습니다"라고
  경고하면서 그동안 계속 클릭 가능하다(현재는 수집 플래그 off라 휴면).
- 범위: 기존 5줄 패턴을 공용화해 6개 폼에 바인딩.

---

## E. 구조

### E1 [코드] `core/views.py`가 2189줄 / 최상위 함수 50개다

- 전역 규약 상한(파일 800줄)의 2.7배이며, 이벤트 발견·활동·컬렉션·시스템
  네 영역의 프레젠테이션이 한 파일에 섞여 있다.
- 선례: 같은 저장소의 `staff/views/`가 이미 패키지 분할되어 있다
  (`__init__.py` 329 / `events.py` 584 / `drafts.py` 306 / `_helpers.py` 42).
**완료(2026-07-30). 커밋 7건.** `core/views/` 패키지로 전환했다.

| 모듈 | 줄 |
|---|---|
| `__init__.py` (순수 재노출 + `__all__`) | 48 |
| `_helpers.py` (여러 그룹이 공유하는 리프) | 179 |
| `events.py` / `archive.py` / `activity.py` / `collection.py` | 461 / 639 / 432 / 429 |
| `account.py` / `system.py` | 104 / 27 |

- **행위 불변을 세 겹으로 증명했다.** ①옮긴 함수 50개 전부를 이전 리비전에서
  AST로 떠서 **문자 단위 대조**(테스트는 복붙 중 주석·공백 손실을 못 잡는다)
  ②169개 라우트의 (패턴, 이름, 함수명) 완전 일치 ③매 단계 전체 회귀 2026 passed.
  `config/urls.py`는 **한 글자도 바뀌지 않았다** — 재노출 계약이 성립한다는 증거다.
- **순환은 `_helpers.py`로 끊었다.** 둘 이상이 쓰는 것만 리프로 올렸다.
  `archive.py` → `collection.py` 단방향 임포트 하나만 남았고(방문 상세가 굿즈
  카드 헬퍼를 쓴다) 역방향은 없다.
- **`__init__.py`에 `import *`를 쓰지 않았다.** star import는 서브모듈의
  module-level 이름까지 패키지 네임스페이스에 얹어, 몽키패치가 "성공"하고
  테스트가 "통과"하지만 실행 경로엔 닿지 않는 **조용한 무효화**를 만든다.
- 첫 단계에서 `core/views.py`를 그대로 `__init__.py`로 옮겨(100% rename,
  이력 보존) 패키지를 만든 뒤 하나씩 빼냈다. 파일과 패키지는 공존할 수 없고
  Python이 패키지를 우선하므로, 이 순서라야 매 단계가 초록으로 유지된다.

### E2 [코드] `archive/queries.py` 996줄 — 활동 달력 읽기 모델이 함께 들어 있다

- 근거: `archive/queries.py:646-996`이 달력 집계 전용 구간(약 350줄).
- 우선순위 낮음. 경계 위반이 아니라 가독성 비용이다.

### E3 [코드] `tests/archive/test_archive_queries.py` 1536줄에 5개 도메인이 섞여 있다

- 근거: 상태(38-90) · 방문기록(305-392) · 찜(443-707) · 직접등록(864-1007) ·
  컬렉션(1026-1528).
- 범위: 이 저장소가 이미 쓰는 "파일명=검증 계층" 관례를 쿼리 테스트에도 적용.

---

## F. 운영·위생

| # | 항목 | 근거 | 비고 |
|---|---|---|---|
| F1 | worktree 2개 삭제 | `git log main..<branch>` 각각 **0 커밋** | 611MB 즉시 회수, 안전 |
| F2 | ~~런북 줄번호 드리프트~~ (해소됨) | `docs/deploy-runbook.md:58`이 참조하던 `core/views.py:728-735`는 PR #251의 `core/views/` 패키지 분할로 파일 자체가 사라져 드리프트가 더 악화됐었음. 참조를 `core/urls.py`, `core/views/system.py`의 `health()`로 줄번호 없이 재작성해 파일 이동·리팩터에도 무효화되지 않게 함 | 해소 |
| F3 | CI 컨테이너 기동 스모크 부재 | `.github/workflows/ci.yml:94-101`이 `docker build`만 실행 | entrypoint 회귀를 첫 배포에야 발견 |
| F4 | `project-status.md` 2334줄 / 사실과 다른 7곳 | 머지된 PR #250을 "열림, 머지 승인 대기"로 기재 등 | 자기 규약("concise index") 위반 |
| F5 | 스로틀 미적용 엔드포인트 4개 | `archive/views.py:74,101,145,290` vs `config/settings.py:521-525` | 배포 후 개선 |
| F6 | SSRF DNS 리바인딩 TOCTOU | `drafts/fetching.py:61,70-71` | **수집 플래그를 켜기 전** 반드시 |
| F7 | 실사용 데이터 이후 스키마 변경 가이드 부재 | `archive/migrations/0011~0013,0019` 비-concurrent | 두 번째 배포부터 유효 |

---

## 착수하지 않는 것

- **인프라 계정 액션** — 도메인 등록, PaaS 계약, SMTP 설정(T1~T8). 사용자가
  최후순위로 확정했다. "다음 단계"로 제안하지 않는다. SMTP 미설정 상태에서는
  신규 가입 이메일 인증이 동작하지 않는다는 사실만 기록해 둔다.
- **교환(trade) 매칭** — 밀도·신원·프라이버시·신고·차단·중재·운영 게이트
  승인 전까지 설계도 착수 금지.
- **LLM 자동 수집 재활성화** — 비용 정책상 불허. 현재 플래그 off.
- **시안 기반 시각 작업** — 새 시안이 나온 뒤 판단한다. 대비율·44px 터치
  타깃·모션 pause는 폐기된 규칙이므로 결함으로 취급하지 않는다.
- **데이터 내보내기(CSV/JSON)** — 어떤 구속 결정에도 없다. 요구가 생기면 그때.

---

## 갱신 규칙

- 항목을 지울 때는 해결 근거(PR 번호 + 검증 명령 결과)를 함께 남긴다.
- 새 항목은 `file:line` 근거 없이 추가하지 않는다.
- 낡은 서술을 그대로 사용자에게 전달하지 않는다. 판정 전에 코드로 재확인한다.
  이 저장소는 낡은 백로그가 존재하지 않는 작업을 지시한 사고를 이미 겪었다.
