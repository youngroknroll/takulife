# 트랙 57: 간격 규칙을 숫자 단계에서 역할 토큰으로 바꾸고 자동 점검을 둔다 (2026-11-15) [v1 — 사용자 승인 2026-11-15 "자동점검 기준을 추가하고 진행"] · **PR #419 머지 완료(2026-11-16T18:35:47Z, merge commit `11a8aad5`, 사용자 직접 머지 "자체 머지 하였음.") `[실측 gh]`** — 스택 base 브랜치 `refactor/remove-dark-mode`로 머지돼 main에 없었으므로 2026-11-17 merge commit `3750d791`로 main에 합쳤다 `[실측 git]`. 합친 main에서 `uv run pytest -q -n auto` 4484 passed / 57.29초 `[실측 2026-11-17]`

> **배경** `[문서 사용자 대화 2026-11-15]`: 사용자가 간격 규칙(4px 배수 6단)의 출처를 물었고, 출처가 시안 `a4.css`뿐이라 근거가 순환임을 확인했다. 사용자 "유지보수가 편한 방안은? 숫자 원칙은 자유도가 떨어지더라고" → 권고(역할 이름 토큰 소수 + 컴포넌트 안 숫자는 자유) → "자동점검 기준을 추가하고 진행".
>
> **기준선** `[실측 python 2026-11-15, static/css 아래 dist 제외 CSS 53개 파일]`: `--page-pad-x`를 정의하는 파일 1개(`static/css/tokens.css`), 이 토큰을 값으로 쓰는 (선택자, 속성) 쌍 18개, 같은 쌍을 토큰 없이 리터럴로 정하는 선언 0개.

## 결정

- D1 간격 숫자 단계 토큰(`--space-1`~`--space-6`)과 "6단 스케일에서만 고른다" 규칙을 폐기한다. 시안이 쓴 값은 기록으로만 남긴다 `[문서 design-principles.md ⑦·⑩(a)]`.
- D2 역할 토큰은 여러 화면이 함께 움직여야 하는 값에만 둔다. 지금 운영에 있는 것은 D11의 세 가지다. 후보(섹션 사이 간격, 목록 행 높이, 컨트롤 높이 `--hit-*`)는 트랙 B가 운영 값을 재서 정한다. 이 트랙은 새 토큰 값을 만들지 않는다.
- D3 컴포넌트 안 숫자는 그 컴포넌트의 상수다. 4의 배수일 필요가 없다 `[문서 사용자 대화 2026-11-15]`. `docs/FE/design-principles.md` ⑩(d)-3의 미결("토큰으로 만들지, 컴포넌트 안 상수로 둘지")은 "컴포넌트 상수"로 닫는다.
- D4 글자 크기 토큰 묶음(`--fs-*`)은 공유 글자 역할의 이름으로 유지하되 "리터럴 금지" 규칙은 두지 않는다. 출처는 "시안에서 옴, 외부 근거 없음"으로 바로 적는다.
- D5 ⑩(b) 대응표의 `--page-pad-x` → `--space-3`/`--space-4` 행은 "역할 토큰으로 유지"로 바꾼다 `[문서 design-principles.md ⑩(b)]`. 단계 수와 값(데스크톱 32px → 24px 등)은 값 결정이라 트랙 B에 남긴다.
- D6 하한(터치 44px, 대비 4.5:1·3:1, 가로 넘침 0)은 지금처럼 브라우저 측정으로 잡는다 `[문서 design-principles.md ⑥]`. 숫자 규칙으로 바꾸지 않는다.
- D7 자동 점검은 소스 계약 가드 `tests/core/test_role_token_contract.py`이고 **정의 위치만** 본다: 역할 토큰마다 레지스트리가 적은 정의 파일 하나에서만 선언된다. 역할 토큰 목록과 정의 파일은 테스트 파일의 레지스트리가 정본이고 문서가 그 파일을 가리킨다. 트랙 B가 역할 토큰을 만들 때 레지스트리에 추가한다.
- D10 "토큰을 쓰는 (선택자, 속성)을 다른 폭에서 숫자로 덮어쓰지 않는다"는 자동 점검으로 만들지 않는다 `[문서 사용자 결정 2026-11-15 "정의 위치 점검만"]`. 배경: TDD 코치가 `AGENTS.md:976-977`("순수 표현의 레이아웃·간격·크기에는 자동 테스트를 만들지 않는다", 브라우저 한정 없음)과의 충돌을 보고했고, 오케스트레이터가 조문을 읽어 확인한 뒤 사용자에게 세 가지 형태를 물었다. 이 규칙은 문서의 규칙으로만 남고 리뷰에서 본다. `AGENTS.md`는 바꾸지 않는다.
- D11 레지스트리는 운영에 이미 있는 역할 토큰 세 가지를 싣는다 `[실측 python 2026-11-15, CSS 53개 파일]`: `--page-pad-x`(정의 `static/css/tokens.css`, 값으로 쓰는 선언 20개·15개 파일), `--site-header-h`(정의 `static/css/components/site-chrome.css`, 선언 5개·5개 파일), `--site-tabbar-h`(정의 같은 파일, 선언 37개·13개 파일). WED 사전 검토가 뒤 두 개의 누락을 지적했다.
- D12 `docs/FE/design-principles.md`가 가리키는 `tokens.css` 줄 번호 가운데 트랙 56의 다크 블록 삭제로 어긋난 곳(WED 사전 검토 D절이 나열)은 같은 유형의 소규모 결함이라 이 트랙에서 `rg -n`으로 다시 대조해 고친다.
- D13 하한 문장은 `AGENTS.md:994-1005`와 맞춘다: 가로 넘침·키보드 도달 불가·읽을 수 없는 글자는 결함이고, 터치 44px와 대비비는 측정해 정보로 보고한다.
- D8 CSS·템플릿은 바꾸지 않는다.
- D9 브랜치 `docs/role-token-rule`을 `refactor/remove-dark-mode` 위에 쌓는다(같은 문서를 앞 트랙의 열린 PR이 고쳤다). PR의 base는 `refactor/remove-dark-mode`이고 앞 PR 머지 뒤 main으로 바꾼다.

## 범위

- `docs/FE/design-principles.md`: ⑦ 간격 항목, ⑩(a) 간격·글자 크기 행의 지위와 출처, ⑩(b) `--page-pad-x` 행, ⑩(c) "간격 6단" 행, ⑩(d)의 리터럴 미결 항목, ⑫ 결정 이력(사용자 원문 인용), 필요하면 ⑬.
- `tests/core/test_role_token_contract.py` 신설.
- `docs/backlog.md`에 이 트랙의 줄을 추가한다.

제외: 토큰 값 변경, CSS 리터럴 정리(트랙 B), 시안 파일.

## Test List

| Scenario ID | Business behavior | Given | When | Then | Verification boundary | Boundary rationale | Test name | Status | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| RT-1 | 역할 토큰은 정해진 한 파일에서만 정의돼서 그 파일만 고치면 모든 화면이 따라온다 | `static/css` 아래 dist를 뺀 CSS 전체(주석 제거 뒤), 레지스트리의 역할 토큰과 정의 파일 | 토큰마다 `--토큰:` 선언이 있는 파일을 모은다 | 토큰마다 그 파일 집합이 레지스트리가 적은 정의 파일 하나다 | contract | CSS 소스 문자열만 읽으면 되고 DB·HTTP가 필요 없다 | `test_역할_토큰은_레지스트리가_적은_파일에서만_정의된다` | Green | 아래 Evidence(트랙 57)의 RT-1 줄 |
| RT-2 | 역할 토큰으로 정한 값을 다른 화면 폭에서 숫자로 덮어써 어긋나지 않는다 | | | | contract | | (만들지 않음) | Deferred | 사용자 결정 2026-11-15 "정의 위치 점검만"(D10) |

RT-1은 현재 코드에서 처음부터 Green이다(기준선). 그래서 뮤테이션 증거가 필요하다(코치 사전 계약, 모두 임시이고 커밋하지 않는다):
- M1a 페이지 CSS의 실제 규칙 안에 `--page-pad-x` 선언을 넣는다 → Red, 메시지에 정의 파일이 둘로 나온다.
- M1b 같은 선언을 주석으로만 넣는다 → Green 유지(주석 제거가 작동한다는 증거).
- M1c `tokens.css`의 `--page-pad-x` 선언 이름을 임시로 바꾼다 → Red, 정의 파일 집합이 비어 있다(아무것도 못 보고 통과하는 상태를 막는다).
- M1d `static/css/dist/shell.css`가 로컬에 있으면 그 안에 선언을 넣어도 Green 유지(dist 제외가 작동한다는 증거).

코치 계약 요점: 모듈 `pytestmark = pytest.mark.contract`, `read_text(encoding="utf-8")`, 파일 목록은 정렬, 주석은 파싱 전에 제거, 정의 판정은 `--토큰\s*:`(`var()` 사용은 정의가 아니다), 실패 메시지는 토큰·기대 파일·실제 파일 목록(상대 경로 정렬), 파싱 헬퍼는 값만 돌려주고 단언은 테스트 본문에, 독스트링에 "잡지 못하는 것"(정의 파일 안의 `:root` 밖 재정의, 토큰을 쓰지 않는 새 선택자, 숫자로 덮어쓰기, 렌더 값)을 적는다.

## AC

- AC1 `docs/FE/design-principles.md`에서 "6단 스케일에서만 고른다" 규칙이 사라지고 역할 토큰 규칙("같은 역할이면 같은 토큰", 컴포넌트 상수 허용, 하한은 측정)이 ⑦과 ⑩에 적힌다. ⑫에 사용자 원문이 인용된다. 숫자는 단위와 출처 태그를 갖는다.
- AC2 RT-1이 Green이고 뮤테이션 M1a·M1c에서 기대한 이유로 Red, M1b·M1d에서 Green이 유지된다.
- AC3 `uv run pytest -q -n auto`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run python manage.py check` 통과.
- AC4 `git diff --stat`에 `static/`·`templates/` 변경이 없다.

## Activated Roles (트랙 57)

Backend TDD Coach(테스트 계약 사전 검토), Backend & Integration Engineer(테스트 작성), Web Experience Designer(디자인 정본 문서 사전·사후 검토), Frontend Implementation Engineer(지정된 프론트 문서 `docs/FE/design-principles.md` 편집), Quality Verification Lead(완료 판정). pytest 실행과 판정은 오케스트레이터만 한다.

## Evidence (트랙 57)

- 사전 출력 `[문서 2026-11-15]`: TDD 코치 — `AGENTS.md:976-977`과의 충돌 보고, RT-1 계약·뮤테이션 절차, RT-3·RT-4 제안(RT-2가 빠지며 해당 없음). WED — 편집 명세 A1~A10, 역할 토큰 누락 두 가지 지적, 줄 번호 어긋남 목록, 사후 판정 기준(작업 노트 `.docs/FE/2026-11-15-role-token-doc-spec.md`). 사용자 결정 "정의 위치 점검만"으로 D10 확정.
- RT-1 `[실측 2026-11-15, 커밋 382d9674]`: `uv run pytest -q tests/core/test_role_token_contract.py` 1 passed(기준선 Green). 뮤테이션(임시, 스크립트가 원본 복원, 커밋 없음): M1a 페이지 CSS 규칙 안에 `--page-pad-x` 선언 → Red, 메시지 "실제 ['static/css/pages/event_list.css', 'static/css/tokens.css']". M1b 주석 안 선언 → Green. M1c `tokens.css` 선언 이름 변경 → Red, 메시지 "실제 []". M1e `--my-page-pad-x`·`--page-pad-x2`·`var()` 사용 → Green. M1f 페이지 CSS에 `--site-tabbar-h` 재선언 → Red. M1d 로컬 `static/css/dist/shell.css`에 `--page-pad-x:` 줄이 4개 있는 상태에서 Green(dist 제외 작동). 복원 뒤 1 passed, `git status`에 `static/` 변경 없음.
- 문서 `[실측 2026-11-15, 커밋 a5c8a715]`: `rg -n '에서만 고른다|임의 .rem. 리터럴' docs/FE/design-principles.md` 0건. `6단`·`--space-` 매치 3줄은 폐기·시안 기록·결정 이력 문맥. 토큰 이름 100개 재측정 일치, `[계산]` 39·22·16 재계산 일치. `tokens.css` 줄 번호 정정 10곳(WED 목록 9곳 + ⑫의 한 곳)을 오케스트레이터가 `awk`로 현재 파일과 대조해 일치.
- 회귀 `[실측 2026-11-15, HEAD a5c8a715]`: `uv run pytest -q -n auto` 4484 passed / 46.72초, `uv run ruff check .` 통과, `uv run ruff format --check .` 466개 파일 변경 없음, `manage.py check` 이슈 0, makemigrations 변경 없음. `git diff --stat 465e8fdf..HEAD`는 파일 3개(`docs/FE/design-principles.md`, `docs/backlog.md`, `tests/core/test_role_token_contract.py`)이고 `static/`·`templates/` 변경 없음.
- Test List 상태: RT-1 Green(뮤테이션 증거 있음), RT-2 Deferred(D10).
- 사후 판정 `[문서 2026-11-15]`: QVL 조건부 완료 — 지적 두 가지(Test List 표의 RT-1 상태, `design-principles.md` ⑤ 규칙 2의 `AGENTS.md` 줄 인용). Frontend Dual Review Gate는 CSS·템플릿·JS 변경이 없어 적용되지 않는다고 판단(`AGENTS.md` Documentation-only 행). WED 1차 Deviates(차단 0, 수정 권장 3, 참고 5) — 머리말 문장 순서, `cards.css` 인용 줄 어긋남, 빈 인용 두 곳.
- 지적 반영 `[실측 2026-11-15, 커밋 796c90f0]`: 문서가 인용한 `static/`·`templates/`·`tests/`·`core/vocab.py` 줄 번호를 구현자가 전부 다시 대조했고 어긋난 곳은 `cards.css` 5곳이었다. 오케스트레이터가 `cards.css` 98·135·138·180·206·230·241·353행과 `site-chrome.css:30,37-38`, `button.css:16`, `AGENTS.md:976-977`을 직접 읽어 일치 확인. ⑤ 규칙 2는 절 이름 인용으로, ⑫에 글자 크기 결정 문장 추가, 머리말은 시간 순으로 재작성.
- WED 재판정 **Conforms**(차단·수정 권장 0, 새 모순 없음). 참고 5(계획서 D 번호 인용의 경로)는 머지 때 `docs/plan-archive/track-57.md`로 옮기며 갱신한다.
- 최종 재실행 `[실측 2026-11-15, HEAD 796c90f0]`: `uv run pytest -q -n auto` 4484 passed / 49.20초, ruff check 통과·format 466개 파일 변경 없음, `manage.py check` 이슈 0, makemigrations 변경 없음, `git diff --stat 465e8fdf..HEAD -- static templates` 0줄. QVL 조건(지적 반영, WED Conforms, 최종 HEAD 재실행) 충족 → 완료.
