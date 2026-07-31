# 스태프 콘솔 (관리 도구) — 기술 기록

기준일: 2026-08-01 · 브랜치 `feat/staff-console-redesign`
대상: `templates/staff/`, `templates/core/drafts/`, `templates/core/staff/home_categories.html`,
`static/css/staff/`, `static/js/staff/`

이 문서는 **가드레일만** 담는다. 계획서는 `.docs/FE/staff-console-redesign.md`에 있고
git-ignored라 소실된다. 여기 적힌 것은 다음 작업자가 모르면 같은 실수를 반복할 것들이다.

## S1 ⚠️ `hidden` 속성은 컴포넌트의 `display` 선언에 진다

**현상**: 드래프트 큐의 문서 높이가 뷰포트 882px인데 **1893px**였다. 사이드바가 거기
맞춰 늘어나 푸터의 「사이트로 돌아가기」가 화면 밖으로 밀려 보이지 않았다.

**원인**: 인스펙터 패널 4장을 서버에서 미리 렌더링하고 JS가 `el.hidden`으로 토글하는데,
`.queue-inspector-panel { display: flex }`가 `hidden`의 UA 기본값 `display: none`을
덮었다. 같은 특이도에서 저자 스타일이 UA 스타일을 이긴다. 숨었어야 할 3장이 그대로
세로로 쌓였다. `[실측]` `getComputedStyle`이 `hidden` 요소 3개에 `"flex"`를 반환했다.

**가드레일**: `static/css/staff/base.css`에 `[hidden] { display: none !important; }`.
스태프 JS는 전부 `el.hidden` 프로퍼티로만 토글하고 `style.display`를 쓰지 않아
(`[실측]` `rg "style\.display" static/js/staff/` → 0건) `!important`가 안전하다.
새 JS를 넣을 때 `style.display`를 쓰면 이 가드와 충돌한다.

**자동 테스트로는 못 잡는다.** Django 테스트는 계산된 스타일을 보지 않는다. 이 결함이
살아 있는 동안 전체 2111건이 초록이었다.

## S2 ⚠️ 정적 파일을 옮기면 화면은 200이고 스크립트만 404가 난다

**현상**: `js/pages/draft.js`를 `js/staff/`로 옮기고 템플릿 참조를 고쳤는데, 서버가
옛 경로를 계속 내보냈다. `[실측]` 네트워크 패널에서 `draft.js` 404.

**원인 두 겹**:
1. 템플릿이 메모리에 캐시돼 있었다. `--noreload`로 띄운 서버는 **재시작해야** 템플릿
   변경이 반영된다. 첫 확인 때 200으로 보인 것은 브라우저 캐시였다.
2. Django 테스트는 정적 파일을 받아오지 않는다. 참조가 깨져도 전 항목 통과한다.

**가드레일**: `tests/core/test_static_reference_guard.py`가 템플릿의 `{% static %}`
리터럴을 모아 `finders.find()`로 존재를 확인한다. 뮤테이션 2건(경로 되돌리기, CSS 오타)
모두 Red 확인. 두 번째 테스트가 "참조를 하나도 못 모으면 무력하다"를 막는다.

**브라우저로 확인할 때는 서버를 재시작하고 캐시를 무시하고 새로고침하라.**

## S3 ⚠️ `confidence`는 0~1이다. 0~100으로 읽으면 조용히 틀린다

**현상**: 드래프트 큐의 신뢰도 배지가 전 행 「1%」였고 색 등급도 늘 최하(빨강)였다.

**원인**: `EventDraft.confidence`는 `FloatField`에 검증이 없다. 생산자
(`drafts/llm_extraction.py`의 `_min_confidence`)와 임계값
(`settings.LLM_ESCALATION_CONFIDENCE_THRESHOLD = 0.6`)이 **0~1 척도**인데, 화면이
`>= 80` / `>= 50`으로 비교하고 `|floatformat:0`으로 찍었다. 0.83이 「1%」가 되고
등급 분기는 어느 값에서도 참이 되지 않았다.

**가드레일**: 표시는 `{% widthratio value 1 100 %}`, 등급 비교는 `0.8` / `0.5`.
`tests/staff/test_staff_draft_views.py::TestDraftConfidenceDisplay`가 지킨다.
상세 화면의 같은 오류는 재설계 이전부터 있었다 — 필드에 척도 표기가 없으면 반복된다.

## S4 대시보드 품질 경고 합계는 `needs_reverification`을 뺀 값이다

`events/queries.py`의 `published_quality_warnings`는 표가 보여주는 5행의 합만 `total`로
낸다. 「표의 합 == total」을 유지하려고 일부러 뺐다. 시안 문구는 「미확인 N건 **포함**」
이었으나 사실과 반대라 쓰지 않았고, 「이 합계에 **없음**」으로 적었다.
`tests/staff/test_staff_console.py`가 문구를 단언한다.

## S5 「0건」을 본문 전체에서 찾는 단언은 아무것도 증명하지 않는다

대시보드에는 「검토 대기 0건」·「품질 경고 0건」·「지난주 0건」이 함께 있다. 특정 카드가
0을 보여주는지 보려면 `<p class="dash-metric-label">라벨</p>...</article>` 범위로 좁혀야
한다. `[실측]` 값을 `"-"`로 만드는 뮤테이션에서 옛 단언은 **3건 모두 통과**했다.

## S6 스태프 콘솔은 소비자 CSS·JS를 로드하지 않는다

`templates/staff/base_staff.html`은 `base.html`을 상속하지 않는 독립 문서다.

- 색은 `static/css/staff/tokens.css`의 `--c-*` **만** 쓴다. `--brand`·`--surface`·
  `--rose-*`·`--line`·`--fs-*`를 쓰면 그 페이지에 정의가 없어 **조용히 깨진다**
- 스태프 전용 JS는 `static/js/staff/`에 둔다
- 공유해도 되는 것은 `static/js/shared/`와 `js/components/confirm-modal.js`뿐이다
  (후자는 `templates/base.html`도 쓴다)
- `.page` 여백은 `static/css/staff/base.css` 한 곳에만 둔다. 화면별 CSS에 흩어 두었더니
  drafts 두 화면이 규칙을 빠뜨려 여백 0으로 렌더링되고 있었다

`django.contrib.messages`는 셸마다 클래스가 다르다 — 소비자는 `site-message-*`,
스태프는 `staff-message-*`. 한쪽만 검사하면 다른 쪽이 메시지를 잃어도 통과한다
(`tests/core/test_base_site_messages.py`가 둘 다 본다).

## S7 데스크톱 게이트를 숨기는 규칙의 위치 (D10)

시안이 최소 폭 1024px를 선언하고 모바일 보드를 그리지 않아, 1023px 이하에서는
`.staff-shell`을 감추고 정적 안내(`.staff-desktop-gate`)만 보인다.

**`.staff-shell`을 숨기는 미디어쿼리는 `shell.css`에 둔다.** `base.css`에 두면
캐스케이드 순서상 `shell.css`의 무조건부 `display: grid`가 나중에 실행돼 미디어쿼리를
덮는다(같은 특이도, 나중 규칙 승리). `[실측]` `base.css`에 뒀을 때 1023px에서도
`getComputedStyle`이 `"grid"`를 반환했다.

게이트의 `<h1>`이 DOM에서 화면 제목보다 앞선다. 두 폭 모두 **보이는 h1은 정확히 1개**다
(`[실측]` 1440px·1023px 양쪽 확인).

## 이월

- 드래프트 상태 라벨(「검토 대기/승인됨/반려됨」)이 `templates/core/drafts/list.html`
  3곳과 `static/js/staff/draft_bulk.js`의 `STATUS_STATE_LABEL`에 각각 하드코딩돼 있다.
  현재 값은 서로 어긋나지 않는다. 모델 `ReviewStatus`의 라벨은 영문이라 그대로는 못 쓰고,
  `choices=` 변경은 이 저장소가 AlterField 실측으로 이미 기각한 방식이다.

## 사후 검토 판정과 처분

네 역할이 독립으로 검토했다. 판정을 남기지 않으면 다음 게이트가 읽을 것이 없다.

| 역할 | 판정 | 처분 |
|---|---|---|
| Web Experience Designer | Conforms with concerns | 헤딩 위계 통일(h2), 1024~1199px 방어 규칙, 이탈 항목 구분선 — 전부 반영 |
| Browser Interaction Reviewer | **Deviates** | High 2건·Medium 3건 반영. 아래 참조 |
| Security & Resilience Reviewer | D9 **조건부 승인** | 조건(대시보드 회귀 테스트) 충족 |
| Quality Verification Lead | 조건부 가능 | 판정 기록(이 절) + 검색창 결정이 조건 |

### BIR이 잡은 것 중 자동 테스트로는 못 잡는 것

- **Enter 전역 가로채기**: `evt.preventDefault()`가 포커스된 요소를 보지 않아,
  「새로고침」 링크에 포커스를 두고 Enter를 눌러도 전체 검토 화면으로 갔다.
  `[실측]` 재현됨. 이제 큐 밖에서는 손대지 않고, Enter는 행에서만 가로챈다.
- **확인 대화상자 중 포커스 탈취**: 대화상자가 열린 채 J/K를 누르면 갇혀 있어야
  할 포커스가 밖으로 나가고 판정 대상이 바뀌었다. `.confirm-overlay:not([hidden])`
  로 열림을 감지해 무효화한다.
- **판정 후 포커스 유실**: 「전체」 탭에서 반려하면 `activeElement === body`가 됐다.
  ⚠️ 첫 수정은 **틀린 시점을 겨냥했다** — 버튼을 지우는 순간을 막았으나, 실측해
  보니 포커스는 그 전에 확인 대화상자가 닫히면서 이미 사라진다. 코드를 읽어
  세운 가설이 실행에서 뒤집힌 사례다.

### 검토자 둘이 같은 것을 짚었다

커맨드바 검색창(`_console_shell.html`)이 무동작이다. `q`를 읽는 뷰가 없고
(`rg` 0건) 바인딩하는 JS도 없다. 더 나쁜 것은 `action="{{ request.path }}"`라
제출하면 기존 질의문자열이 통째로 날아간다 — `/staff/drafts/?status=pending`
에서 검색하면 `status`가 사라진다. 7화면 공용 셸에 상시 노출된다.
