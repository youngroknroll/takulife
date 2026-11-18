# 트랙 59: 트랙 58이 넘긴 공개 화면 프런트 잔여 6건 (2026-11-17) [v1 — PSO·WED·BIR·QVL 사전 검토 반영(2026-11-17). 사용자 지시 2026-11-17 "머지 승인 후 백로그 진행" `[문서 사용자 지시]` — 오케스트레이터 해석: `docs/backlog.md` M절 6건을 이 트랙으로 진행한다. 사용자 결정 3건(D-가·D-나·D-다)은 답을 받는 대로 기입한다]

> **배경** `[문서]`: 트랙 58(PR #420, main `86d4ef33`)에서 발견했지만 main부터 있던 동작이라 넘긴 6건이다. 사전 검토 원문은 `.docs/FE/2026-11-17-track59-{brief,pso-pre,wed-pre,bir-pre,qvl-pre}.md`(git 무시 작업 메모).
>
> **기준선** `[실측 2026-11-17, main e586a661]`: 공개 화면 버튼 368개(로그인 24쪽 + 비로그인 3쪽 × 1280px·390px, Playwright로 `.is-loading`을 붙여 측정) 중 340개가 기준에서 벗어난다 — 글자가 접히며 폭이 줄어드는 묶음(예: 기록 삭제 42.2px → 18px, 상태 버튼 70.3px → 18px)과 글자가 남아 스피너와 겹치는 묶음(쪽 규칙이 `font-size`를 유지). `rg -n "aria-invalid" static/js` 0건. `.sr-only` 복제 8벌(쪽 CSS 8개 파일), `gi-0`~`gi-12` 13행 × 3개 파일. 공개 CSS·템플릿의 `--cat-slot-*` 소비처 0곳(`rg cat-slot`), 로컬 DB 카테고리 7종(처음부터 있던 것뿐, `manage.py shell`). 운영 DB는 확인하지 않았다.
>
> **브리프·백로그 정정** `[코드 사전 검토가 직접 읽음]`: ① 행사 상세 60rem(`static/css/pages/event_detail.css:369`)은 2열 접힘이 아니라 하단 고정 CTA 막대 조건이다. ② 접힘 폭 기준 2개(45rem·56.25rem)는 `docs/FE/design-principles.md` ⑩(d)-4에 이미 적혀 있고, 트랙 B(토큰 재정립)는 트랙 58이 흡수했다. ③ 로딩 관련 쪽 규칙 9곳은 색만 다루고 폭 문제의 원인이 아니다 — 원인은 공용 `font-size: 0`(`static/css/objects/interaction.css:56-59`)이다. ④ 목록|달력 전환에는 `aria-current`가 이미 있고, 없는 곳은 하위 탭 앵커 4개(`templates/core/partials/_archive_nav.html:22-25`)다. ⑤ 홈 달력은 월 이동 뒤 이미 `#home-calendar-agenda`로 돌아온다.

## 결정

- D1 한 트랙·한 PR, 커밋은 항목별로 가른다 `[문서 PSO]`. 순서: 4(복제 CSS) → 1(로딩) → 5(키보드·보조기기) → 2(폼 검증) → 3(접힘 폭) → 6(카테고리 색).
- D2 **1 로딩 표시**: `static/css/objects/interaction.css:56-59`의 `font-size: 0`을 글자 채움색 투명(`-webkit-text-fill-color: transparent`)과 자식 요소 `visibility: hidden`으로 바꾼다. 라벨이 자리를 그대로 차지하므로 폭·높이가 변하지 않고, `color`를 건드리지 않아 스피너의 `currentColor`가 유지된다. 스피너 `::after` 규칙, `static/js/shared/api.js`, `submit_guard.js`, 스태프 `static/css/staff/base.css`는 고치지 않는다 `[문서 WED·BIR 일치]`. 로딩 중 색(쪽마다 `--ink-2`/`--off`)은 구현 뒤 측정해 WED 사후 판정이 어긋남으로 보면 같은 트랙에서 맞춘다.
- D3 **2 폼 검증**: 소비자 전용 새 파일 `static/js/components/form_feedback.js`(`window.TakuFormFeedback`)에 공용 규칙을 두고 폼 6쪽 + 같은 패턴 2곳(`personal_detail.js` 제보 폼, `personal_entries.js`)이 쓴다 `[문서 BIR 기준 1~8]`. 규칙: 제출 시도마다 `aria-invalid` 전부 제거 → 위반 입력에만 `aria-invalid="true"` + `aria-describedby`에 오류 상자 id 추가(기존 값 보존) → DOM 순서 첫 위반 입력으로 `focus()`(닫힌 `<details>`는 먼저 연다) → 입력 값이 바뀌면 그 입력의 표시 해제. 입력에 속하지 않는 오류(403·429·5xx·네트워크·삭제 실패)는 오류 상자에 `tabindex="-1"`을 주고 포커스한다(선례 `static/js/shared/status.js:60-75`). 서버 400의 필드 키가 입력 `name`과 맞으면 같은 표시를 단다. 새 문구 0개, `formatError` 출력 유지, 부드러운 스크롤 추가 없음. 파일 입력의 시각 표시는 드롭존 2px `--ink` 테두리. 새 JS 파일은 `tests/core/test_ui_korean_literal_guard.py`의 고정 목록과 기대 개수에 더한다(가드가 새 파일도 보게 — 기존 가드의 대상 추가이고 새 가드 종류가 아니다).
- D4 **4 복제 CSS**: `.sr-only` 한 벌을 `static/css/components/text.css`(셸 묶음, `.archive-search-status` 아래)에, `gi-0`~`gi-12` 13행 한 벌을 `static/css/components/cards.css`(셸 묶음)에 둔다 — `tokens.css`는 `:root` 선언만 있는 파일이라 클래스 규칙을 넣지 않는다 `[코드 grep]`. 쪽 CSS 9개 파일의 복제본을 지운다. 새 CSS 파일은 만들지 않는다(셸 묶음 16개 목록 테스트 불변). 스태프 `static/css/staff/shell.css:286`은 그대로.
- D5 **5 키보드·보조기기** `[문서 WED·BIR]`: (a) 활동 달력·행사 달력의 월 이동 링크(이전·이번 달·다음)에 `#calendar-month`를 붙이고 월 제목 `<h2>`에 `id="calendar-month" tabindex="-1"`을 단다(기존 `#selected-date` 패턴과 같음). 홈 달력은 그대로. (b) 기록 목록 5쪽의 결과 창 제목은 서버가 번역·단복수 처리를 마친 안쪽 마크업을 결과 조각에 함께 실어 보내고 `archive_search.js`가 제목에 넣는다 — 숫자만 바꾸면 영어 단수·복수가 틀린다(`{% blocktranslate count %}` `[코드 templates/core/archive/index.html:71]`). 제목 문구는 쪽과 조각이 같은 include를 쓴다. 검색어가 비어도 갱신하고, 요청 실패 때는 바꾸지 않는다. 낭독은 기존 `#archive-search-status`가 맡고 제목은 live region으로 만들지 않는다. 뷰·직렬화 변경 없음(조각 템플릿만). (c) 하위 탭 앵커 4개에 현재 탭일 때 `aria-current="page"`를 단다 — 속성은 `href` 앞에 둬 `tests/archive/test_archive_nav.py`가 고정한 `href="/archive/personal/" class="active">` 인접을 지킨다.
- D6 문서: `docs/FE/loading-feedback.md`(로딩 방식 개정), `docs/FE/design-principles.md`(해당 절), `docs/backlog.md` M절·현재 상태 표, 폼 검증 가드레일은 기존 FE 문서에 절을 더한다(새 문서는 맞는 기존 문서가 없을 때만).
- **D-가 3 접힘 폭 = B** `[문서 사용자 결정 2026-11-17 "활동 쪽만 900px로"]`: 활동 목록 5쪽·활동 달력의 사이드바 접힘을 53.75rem → 56.25rem으로 올려 행사 목록·컬렉션과 맞추고(`max-width: 56.24rem` / `min-width: 56.25rem` 짝), 어긋난 짝 값(`auth.css`의 45.0625rem, `errors.css`의 `min-width: 45rem`, 컬렉션 `max-width: 56.25rem`)을 정리한다. 하위 탭 라벨·hero 재배치·하단 고정 CTA 막대의 53.75rem과 행사 상세 60rem은 그대로 둔다(선택지 C는 고르지 않았다).
- **D-나 2의 오류 문장 위치 = 지금 위치 유지** `[문서 사용자 결정 2026-11-17 "지금 위치 유지"]`: 오류 상자는 폼 맨 아래(저장 버튼 위)에 그대로 둔다. 위반 입력의 표시·포커스·연결만 더한다. 모바일에서 표시된 입력과 오류 문장이 한 화면에 같이 안 들어올 수 있다는 점은 사용자가 알고 고른 것이다.
- **D-다 6 스태프 카테고리 색 = 새 카테고리에도 색 점** `[문서 사용자 결정 2026-11-17 "새 카테고리에도 색 점"]`: 고정 슬러그 7종의 점 색 규칙은 그대로 두고, 그 밖의 카테고리는 배정된 팔레트 슬롯의 `--cat-slot-N-ink`를 공개 화면의 점에 쓴다. 슬롯 미배정이면 지금처럼 `--ink-2`. 색은 점에만 쓰고 `-soft`는 쓰지 않는다. 슬롯 7~11 색의 대비비: `--surface #F4F4F4` 위 5.39~6.48:1, `--canvas #C6C6C6` 위 3.47~4.17:1 `[계산 python WCAG 상대 휘도 2026-11-17]`. 슬롯 7(`#b91c1c`)이 오류 색 `#A80000`과 비슷하다는 점(둘 사이 1.22:1 `[계산]`)은 선택지에 적어 알렸다. 백엔드(공개 화면에 슬롯을 내리는 경로)는 DAR 설계 + Backend TDD Coach 계약 뒤에 구현한다.

## 범위 밖

- 스태프 화면과 스태프가 함께 쓰는 파일(`templates/core/partials/_pager.html`, `static/js/shared/*`, `static/js/components/confirm-modal.js`) 변경.
- 새 화면 문구·장식 화살표·새 움직임. `formatError`의 서버 필드 키 표기 변경(문구 변경).
- 폭 조건의 변수화·범위 문법 통일, 폭 리터럴 가드 신설, 역할 토큰 값 변경.
- 로딩 중 `aria-busy` 추가, 검색어를 비웠을 때 건수 낭독 추가, 홈 달력 월 이동 대상 변경(제품 권고로만 기록).
- 표현만 다루는 자동 테스트 추가(Frontend Work Policy).

## AC

- AC1 로딩: 기준선과 같은 측정(27쪽 × 1280px·390px `[계산 24 + 3]`)에서 `.is-loading` 전후 폭·높이 차 0px인 버튼이 전부이고, 라벨·글리프가 보이지 않으며 스피너가 보인다. 스태프 변경 0.
- AC2 폼: 폼 6쪽에서 위반 입력에 `aria-invalid="true"`·`aria-describedby` 연결·포커스, 값 수정 시 해제, 입력에 속하지 않는 오류와 삭제 실패는 오류 상자가 화면 안에 들어오고 포커스를 받는다. 새 번역 항목 0개.
- AC3 복제 CSS: 공개 CSS에 `.sr-only` 규칙 1벌·`gi-N` 13행 1벌 `[코드 기준선의 복제 수에서 계산]`. `.sr-only` 요소의 계산 크기와 시리즈 점 색이 변경 전후 같다(개별 링크 경로와 묶음 경로 둘 다).
- AC4 키보드: 두 달력에서 월 이동 뒤 `document.activeElement`가 월 제목이고 헤더에 가리지 않는다. 기록 목록 5쪽에서 실시간 검색 뒤 제목 건수가 응답의 건수와 같다(영어 단수·복수 포함). 하위 탭에서 현재 탭에만 `aria-current="page"`.
- AC5 접힘 폭: 활동 목록 5쪽·활동 달력이 899px에서 1열, 900px에서 2열로 바뀌고(행사 목록과 같은 폭) 859~901px 경계에서 가로 넘침 0 `[계산 56.25rem × 16px = 900px]`. 하위 탭 라벨·하단 고정 CTA 막대의 전환 폭은 변경 전과 같다.
- AC6 카테고리 색: 고정 7종이 아닌 카테고리의 점이 공개 화면 점 5종(홈 카테고리 타일, 홈 달력, 필터, 달력 칸, 행사 상세)에서 배정 슬롯 색으로 보이고, 미배정이면 `--ink-2`다 `[문서 WED 6절의 점 목록]`. 고정 7종의 점 색과 기존 쪽의 쿼리 수는 변하지 않는다. 스태프 화면의 색 견본은 그대로다.
- AC7 회귀: `uv run pytest -q -n auto` 실패 0(테스트 수 변화는 D3의 가드 목록 갱신과 D-다 선택에 따른 것만), e2e 여정 전부 통과, ruff·`manage.py check`·`makemigrations --check` 통과, 스태프 경로·공유 파일 diff 0.

## Activated Roles

- PSO(범위·제품 결정 정리), WED(경험 명세·사후 판정), BIR(상호작용 기준·사후 판정), QVL(위험·증거 대응·완료 판정), FIE(템플릿·CSS·JS 구현), Backend & Integration Engineer(가드 목록 갱신과 문서; D-다가 테스트·백엔드에 닿으면 그 부분).
- D-다 결정으로 추가 활성화: Domain Architecture Reviewer(슬롯을 공개 화면에 내리는 경로의 소유·의존 방향·캐시), Backend TDD Coach(그 경로의 Test List와 Red-Green 계약).
- **Not Activated**: DOR(배포·마이그레이션 없음; 셸 묶음 경로는 QVL 증거로 확인), SRR(신뢰 경계 불변), AAA(LLM 무관).

## 검증 절차

- 구현 전 기준선 묶음과 구현 뒤 재실행: `uv run pytest -q tests/core/test_shell_css_bundle.py tests/core/test_static_reference_guard.py tests/core/test_category_token_contract.py tests/core/test_role_token_contract.py tests/core/test_ui_korean_literal_guard.py tests/core/test_i18n_catalog_completeness.py tests/core/test_comment_language_guard.py tests/archive/test_archive_nav.py tests/archive/test_archive_view_toggle.py`.
- 전체: `uv run pytest -q -n auto`, `uv run pytest -q -m e2e tests/e2e`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run python manage.py check`, `uv run python manage.py makemigrations --check --dry-run`.
- 브라우저(Playwright, 커밋하지 않음) `[문서 BIR·QVL 증거 목록]`: 로딩 전후 크기(27쪽 × 2폭), 폼 6쪽 × 390px·1280px × 시나리오(필수 비움·교차 필드·이미지·서버 400/403/500 모의·삭제 실패·값 수정 뒤 해제), `.sr-only`·시리즈 점 전후 비교, 월 이동 포커스(2쪽 × 2폭 + 경계 달), 검색 건수(5쪽, 한국어·영어), 하위 탭 `aria-current`, 접힘 폭 경계 ±1px(D-가 선택 시), `DEBUG=false` 묶음 경로 재측정.
- 스태프 변경 0: `git diff --name-only main...HEAD`와 스태프 경로·공유 파일 목록의 교집합 0.

## Frontend Review Evidence (트랙 59)

- **깊이**: High — 여러 쪽에 걸친 패턴(로딩, 공용 CSS), 비동기 상태(실시간 검색), 포커스 이동, 반응형 접힘이 함께 들어 있다 `[문서 WED·BIR·QVL 일치]`.
- **WED 사전 명세**: `.docs/FE/2026-11-17-track59-wed-pre.md` — 로딩은 글자 투명 방식, 폼은 위반 입력 표시 + 오류 상자 위치 제안, 접힘 폭 선택지 A/B/C(권고 B), 복제 CSS 위치, 월 제목 포커스, 서버 렌더 제목 교체, 카테고리 색 비교.
- **BIR 사전 기준**: `.docs/FE/2026-11-17-track59-bir-pre.md` — 로딩 측정 기준 표, 폼 검증 기준 1~8과 증거 시나리오 (a)~(k), 월 이동 후보 A 권고, 건수 갱신 기준, 하위 탭 `aria-current`, 스태프 영향 표.
- **PSO**: `.docs/FE/2026-11-17-track59-pso-pre.md`. **QVL 사전**: `.docs/FE/2026-11-17-track59-qvl-pre.md`(깨질 수 있는 기존 테스트 4곳 `[문서 QVL]`, 묶음 경로 주의).
- **사전 검토 사이 충돌 정리**: 건수 갱신 방식은 BIR(숫자만 교체)과 WED(서버 렌더 제목 교체)가 달랐고, 제목이 `{% blocktranslate count %}`라 WED 안을 택했다. 공용 헬퍼 위치는 BIR(`static/js/pages/`)·WED(`static/js/components/`) 중 여러 쪽이 함께 쓰는 파일이라 `components/`로 정했다. `gi-N` 위치는 WED 1안(`tokens.css`) 대신 대안(`cards.css`)을 택했다(D4 이유).
- **계획한 브라우저 증거**: 위 "검증 절차".
- **사후 판정** `[문서 .docs/FE/2026-11-17-track59-{wed,bir}-post.md, -{wed,bir}-re.md]`: WED 사후 Deviates(차단 0건) → 조건 반영(`f3e3c9dd`·`5517da1a`·`56822d15`) → **재판정 Conforms, 남은 조건 없음**. BIR 사후 Deviates(차단 0건, 삭제 실패 2경로 M1·M2) → 반영(`f3e3c9dd`) → **재판정 Conforms, 차단 0건**. BIR 재판정이 권한 Low 결함 R2(잘못된 이미지 선택 시 표시 어긋남)는 `5fb5fbf5`에서 고치고 오케스트레이터가 폼 3개 × 1280px·390px 6경우를 쟀다 `[실측 Playwright]`. R2 수정 뒤 두 리뷰어를 다시 부르지는 않았다(QVL 권장 조건 5 "요구하지 않는다").
- **백엔드 판정** `[문서 .docs/FE/2026-11-17-track59-dar-post.md, .docs/BE/2026-11-17-track59-coach-post.md]`: DAR 조건부(차단 0건), Backend TDD Coach 조건부 → 조건 3건 반영(`74b2efe7`, 뮤테이션 A·B·C 실행·복원).
- **QVL 완료 판정** `[문서 .docs/FE/2026-11-17-track59-qvl-post.md]`: 조건부 완료 — AC1~AC7 미충족 0건. 차단 조건 2건(이 계획서 갱신, PR 직전 diff 재확인)은 처리했다. 남는 것은 미검증 목록의 사용자 수용이다.
- **아래 "미검증" 줄과 위 QVL 줄은 확장 전(PR 첫 판) 기록이다** `[문서]`: 확장에서 측정·구현으로 해소한 항목과 최종 판정은 "## 확장 (2026-11-17)" 절이 정본이다. AC1·AC7의 "스태프 변경 0·스태프 경로와 공유 파일 diff 0"도 확장에서 대체됐다(확장 절 "스태프 범위").
- **미검증(PR 본문에 그대로 실음)**: 실제 스크린리더 낭독(이중 낭독·재낭독), 실기기 iOS Safari·Android Chrome, 실제 bfcache 복원, forced-colors, 한글 IME 조합 입력 중 검색 제목, `.mobile-cta` 표시 상태의 전환 폭, 홈 카테고리 타일의 실제 새 카테고리 색, 파일 선택창을 거친 뒤의 포커스, `.sr-only`·`gi-N` 변경 전후 전수 비교, 로딩 기준선(버튼 368개)과 변경 뒤(392개)의 표본 차이.

## D-다 백엔드 설계와 Test List (DAR 설계 + Backend TDD Coach 계약)

- **설계** `[문서 .docs/FE/2026-11-17-track59-dar-pre.md]`: 슬롯 조회는 `core/categories.py`의 `palette_slot_by_slug() -> dict[str, int]`(슬롯 배정된 전체, 비활성 포함), 요청당 한 번 읽기는 `core/context_processors.py`의 `category_palette_slots(request)`(`SimpleLazyObject`), 점 요소 속성은 새 `core/templatetags/category_dots.py`의 `{% palette_slot_attr slug %}` → `data-palette-slot="N"`. 고정 7종·빈 슬러그는 조회 없이 빈 값. 뷰·직렬화·공개 캐시(`web/public_cache.py`, `events/queries.py`)는 바꾸지 않는다. 프로세스 전역 캐시 금지. 읽기 경로에서 슬롯 재계산 금지. CSS는 `[data-palette-slot="N"] { --dot-slot: var(--cat-slot-N-ink) }` 12줄 한 벌을 셸 CSS(`tokens.css` 아님)에 두고 점 5종이 `var(--dot-slot, var(--ink-2))`를 읽는다.
- **같은 트랙에서 고치는 인접 결함** `[코드 web/views/_helpers.py:68,246, web/views/events.py:147-149,263,636 — 변경 전 위치. 구현 뒤 라벨 조회 위치는 _helpers.py:32-36,51, events.py:155,269,644 [실측 grep HEAD ce4041b6]]`: 새 카테고리의 목록 행·적용 필터 칩·상세 라벨이 슬러그로 나오는 것, 홈 달력 범례에 새 카테고리가 빠지는 것. 고정 7종은 번역되는 `CATEGORY_LABELS` 그대로, 그 밖은 DB 라벨을 `category_labels_for(slugs)` 한 번 조회로 푼다.
- **Test List** `[문서 .docs/BE/2026-11-17-track59-coach-contract.md — 시나리오별 Given/When/Then·예상 Red 이유·최소 Green 범위는 그 파일]`. 상태는 사이클마다 갱신한다.
  - CS-1 (domain) 슬롯 맵 조회: 비활성 포함 배정된 것만, 쿼리 한 번 — `tests/core/test_category_queries.py` — Green
  - CS-2 (domain) 슬롯 없음·행 없음이면 속성 없음 — 새 `tests/core/test_category_palette_slot_display.py` — Green
  - CS-3 (domain) 슬롯 배정된 새 카테고리는 슬롯 번호 속성 — Green
  - CS-4 (domain) 고정 카테고리·빈 슬러그는 조회 없이 속성 없음(파라미터 케이스 8개 `[계산 빈 값 1 + 고정 7]`) — Green
  - CS-5 (domain) 프로세서 값으로 include를 거쳐 여러 점을 그려도 조회 한 번 — Green
  - CS-6 (domain, 이미-Green 핀 + 뮤테이션) 슬롯 재배정 뒤 다음 조회가 바뀐 값 — Green
  - CS-7 (domain, 이미-Green 핀 + 뮤테이션) 비활성·게시 0건 카테고리를 그려도 슬롯이 반납되지 않음 — Green
  - CS-8 (web) 홈·행사 목록·행사 달력·행사 상세에서 새 카테고리 점에만 슬롯 속성 — 새 `tests/events/test_category_palette_slot_pages.py` — Green
  - CS-9 (contract, 이미-Green 핀 + 뮤테이션) `tokens.css`의 `--dot-*` 이름 집합 = 고정 슬러그 집합 — `tests/core/test_category_token_contract.py`(기존 가드의 대상 추가) — Green
  - CS-10 (web) 새 카테고리로 목록을 거르면 행과 적용 필터 칩이 라벨 — `tests/events/test_event_list_view.py` — Green
  - CS-11 (web) 새 카테고리 행사가 여러 개여도 목록 쿼리 수가 행 수에 비례하지 않음 — Green
  - CS-12 (web) 새 카테고리 행사 상세가 라벨 — `tests/events/test_event_detail_view.py` — Green
  - CS-13 (web) 홈 범례가 표시 달의 새 카테고리를 고정 카테고리 뒤에 담음 — `tests/events/test_home_calendar.py` — Green
- **운영 방식**: 테스트 실행은 오케스트레이터만 한다. 한 번의 구현자 호출은 "직전 시나리오의 최소 구현 + 다음 시나리오의 테스트 1개"까지만 하고, 오케스트레이터가 직전 시나리오 Green과 다음 시나리오 Red(예상 이유)를 함께 확인한 뒤 다음으로 넘어간다 — 어떤 시나리오도 Red 확인 전에 구현하지 않는다.
- **기존 쿼리 수 단언 유지**: `tests/events/test_event_list_view.py:458`(최대 4건), `tests/events/test_home_view.py:549`(최대 21건)·`:576`(최대 11건) `[코드 코치가 직접 읽음]`은 고치지 않고 재실행으로 확인한다.
- **이 트랙 밖으로 분리(코치 권고, 사용자 보고)**: 활동·컬렉션 행의 `_subject_view`(호출처 8곳 `[실측 rg 코치]`)와 스태프 화면 4곳의 같은 라벨 결함, 비한국어 화면에서 새 카테고리 한글 라벨의 `lang="ko"` 표시.

## 위험

- `visibility: hidden`으로 숨긴 자식 글자는 로딩 중 접근성 이름에서 빠질 수 있다(로딩 중에는 `disabled`). forced-colors·Chromium 밖 브라우저는 미확인으로 남는다.
- 오류 상자와 포커스 이동이 겹쳐 스크린리더가 두 번 읽을 수 있다 — 실제 낭독은 확인 수단이 없어 미검증으로 보고한다.
- 셸 CSS를 고치면 로컬 `static/css/dist/shell.css`가 낡는다 — 묶음 경로 측정 전에 `bundle_shell_css`를 다시 돌린다.

## Evidence (트랙 59 — 진행 기록)

- 2026-11-17 사전 검토(PSO·WED·BIR·QVL) 수령, 기준선 측정(위), 계획서 v1 작성 `[문서]`.
- 2026-11-17 사용자 결정 3건 수령(D-가 B, D-나 위치 유지, D-다 색 점) `[문서 사용자 답변]`.
- 2026-11-17 Test List 13개 전부 Green `[실측 pytest — 시나리오별 Red 출력과 Green 건수는 .docs/FE/2026-11-17-track59-evidence.md "백엔드 TDD 기록"]`. 핀 3개(CS-6·CS-7·CS-9)는 일시 뮤테이션으로 Red 확인 뒤 복원. CS-2의 `슬롯_미배정` 케이스는 Given 오류(생성 시 슬롯 자동 배정)가 CS-3 구현 뒤 드러나 `update(palette_slot=None)`으로 수리했다.
- 2026-11-17 커밋 `5db4a277`(접힘 폭 — 6쪽 × 859·860·861·899·900·901px에서 899px 1열·900px 2열, 넘침 0 `[실측 오케스트레이터 Playwright]`) · `a1caf6c9`(폼 검증 — 구현자 측정 130건 실패 0 `[실측 구현자 Playwright, 65건 × 390px·1280px]`, 가드 JS 목록 24 → 25개) · `23f4e57c`(새 카테고리 색 점) · `6c3279e4`(새 카테고리 라벨·홈 범례).
- 2026-11-17 사후 판정 뒤 커밋 6개 `[실측 git log]`: `f3e3c9dd`(삭제 실패 포커스 M1·M2·M3, 낡은 표시 해제) · `5517da1a`(스피너 `box-sizing`, 폭 짝 값) · `74b2efe7`(코치 조건 테스트 보강) · `56822d15`(가드레일 문서·백로그 M절) · `5fb5fbf5`(R2 이미지 오류 표시) · `ce4041b6`(묶음 크기·잔여 2건 기록).
- 2026-11-17 PR 직전 최종 확인 `[실측 HEAD 5fb5fbf5, 그 뒤 ce4041b6은 문서 2개뿐]`: `uv run pytest -q -n auto` 4,508 passed / 50.50초, `uv run pytest -q -m e2e tests/e2e` 10 passed / 10.23초, `ruff check`·`ruff format --check`(469개 파일)·`manage.py check`·`makemigrations --check --dry-run` 실패 0. `git diff --shortstat main...HEAD` 87개 파일 +1,205/−300줄, main 위 커밋 15개, 스태프·공유 경로 교집합 0개 `[실측 git, HEAD ce4041b6]`.
- 2026-11-17 QVL 권장 보강 측정 `[실측 오케스트레이터 Playwright, HEAD 5fb5fbf5]`: `/archive/statuses/`·`/archive/personal/` 899px 1열·900px 2열·넘침 0px. 720px·721px에서 홈·로그인·가입·404 쪽 넘침 0px, CSS 조건(45.01rem)과 `hscroll.js` 조건(45.0625rem)이 두 폭 모두 같은 값. 달력 2쪽에서 월 이동 뒤 뒤로가기 → 주소에 `#calendar-month`가 없는 원래 쪽으로 돌아가고 포커스는 문서(`BODY`), 월 제목은 원래 달. 22px 사진 삭제 단추 스피너 중심 차 0px. 셸 묶음 원본 77,987B·gzip 19,346B·brotli 16,529B(트랙 58 대비 +2,408B·+552B·+450B `[계산]`), `docs/FE/css-delivery.md`에 기록.
- 2026-11-17 구현 중간 확인 `[실측 HEAD 6c3279e4]`: `uv run pytest -q -n auto` 4,508 passed / 61.44초(기준선 4,484 + 새 케이스 24 `[계산]`), `uv run pytest -q -m e2e tests/e2e` 10 passed / 9.81초, `ruff check`·`ruff format --check`(469 files)·`manage.py check`·`makemigrations --check --dry-run` 실패 0. 로딩 재측정 버튼 392개 어긋남 0, 22쪽 × 1440·900·375·320px 88건 넘침 0·콘솔 오류 0, 묶음 경로(`DEBUG=false`)에서 `.sr-only` 9개 1×1px·`gi-N` 31개 색 유지·로딩 42개 어긋남 0·새 카테고리 점 슬롯 색·899/900px 접힘 확인 `[실측 오케스트레이터 Playwright]`. 스태프 경로·공유 파일과 `git diff --name-only main...HEAD`의 교집합 0개, `web/public_cache.py`·`events/queries.py`·`core/models.py`·마이그레이션 변경 0 `[실측 git]`.
- 2026-11-17 커밋 `f2c32f56`(복제 CSS) · `47f3d6de`(로딩 — 버튼 368개 중 어긋남 340 → 0 `[실측 Playwright, 27쪽 × 1280px·390px]`) · `4409522f`(달력 월 이동 포커스) · `9e140e15`(하위 탭 `aria-current`) · `834c472c`(검색 뒤 제목 건수 + 가드 목록 71 → 75개 `[실측 pytest 996 passed, tests/core 가드 2개 + tests/archive]`). 구현자 측정: 월 이동 뒤 `activeElement.id`가 `calendar-month`(2쪽 × 1280px·390px), 제목 top 58~62px / 헤더 하단 50~54px, 검색 건수 5쪽 일치(영어 단수·복수 포함), 500 모의 시 제목 불변, 하위 탭 `aria-current` 개수 기대값과 일치 `[실측 구현자 Playwright 2026-11-17]`.

## 확장 (2026-11-17) — PR #421에 남겼던 잔여 전부를 같은 PR에서 처리

> **사용자 지시** `[문서 사용자 지시 2026-11-17, 원문]`: "백로그 남기지 말고 모두 처리하라고". PR #421을 열며 "이 PR에 넣지 않은 것" 10건 `[문서 PR 본문]`을 백로그 M절에 남긴 것에 대한 지적이다.
>
> **오케스트레이터 해석** `[문서]`: ① 남긴 10건 전부, ② "미검증"으로 적었던 것 중 자동화로 잴 수 있는 것 전부, ③ 그 과정에서 찾은 결함 전부를 PR #421에서 처리한다. 검토자가 "차단 아님·Low·기록만"으로 분류한 것도 같은 PR에서 고친다. 사람만 확인할 수 있는 것(실제 스크린리더·실기기·실제 입력기·파일 선택창)만 "사용자 확인 필요"로 남긴다.
>
> **스태프 범위** `[문서]`: 트랙 58의 "스태프 제외"는 DOS 모양 적용에 대한 것이었다. 확장은 스태프에서 새 카테고리 라벨 버그 4곳 `[코드]`, 공용 JS의 `aria-busy`(`shared/api.js` +2줄, `shared/submit_guard.js` +1줄 `[실측 git diff]`), 스피너 중심 1줄(`staff/base.css` `[실측 git diff]`)만 건드린다.

### 확장 결정

- 라벨: `core.categories.category_display_labels(slugs)` 한 곳이 고정 7종 `[코드]` 번역 라벨과 DB 라벨을 합친다. 목록 뷰는 `_subject_view(obj, category_labels=…)`에 지도를 한 번 넘긴다(쪽당 조회 1건 `[계산 호출 횟수, docs/BE/category-vocabulary.md 상한 표]`).
- 언어: `category_label_lang(label)` — 활성 언어가 한국어가 아니고 라벨에 한글 음절이 있을 때만 `"ko"`. 템플릿 태그 `category_lang_attr`. 한국어 화면·개인 항목·스태프 콘솔에는 붙지 않는다 `[코드]`.
- 로딩: 로딩 중 버튼은 비활성 모양을 입지 않는다(WED 판정). `.is-loading`과 `aria-busy="true"`는 항상 같이 붙고 같이 풀린다 `[코드 shared/api.js, shared/submit_guard.js]`.
- 실시간 검색 뒤 링크 동기화는 표식(`data-search-links`, `data-sort-menu`)이 붙은 묶음만. 활동 쪽 보기 전환·구역 탭은 서버가 검색어를 빼므로 대상 아님 `[코드, 테스트 tests/archive/test_archive_view_toggle.py]`.
- 화면 문구·번역 문자열·토큰 신설 0개 `[코드]`.

### 확장 Test List (XS, 백엔드 — 한 건씩 Red → Green, 오케스트레이터 실행)

- XS-1~XS-15 `[실측 pytest]`: 라벨 규칙(코어 2건), 스태프 4곳(6건), 내 활동·방문 칩·필터·N+1(7건) — 전부 Green. XS-2는 처음부터 Green인 핀(뮤테이션 확인). XS-15·XS-19는 처음 실행이 Green이어서 Given·단언을 고친 뒤 Red를 확인했다.
- XS-16~XS-26 `[실측 pytest]`: 언어 판정 단위 3건, 화면 8건 — 전부 Green. XS-26은 핀(뮤테이션 확인).
- XS-27 `[실측 pytest]`: "전체" 칩이 검색어와 정렬을 유지(3케이스 Red → Green). 코치 계약 없이 오케스트레이터가 정의했고 코치 재판정이 사후 판정했다.
- XS-28 `[실측 pytest]`: 검색어 없이 정렬만 있을 때의 "전체" 칩 핀(3케이스, 뮤테이션 3건).
- 사후 보강(코치 §6) `[실측]`: 달력 테스트의 고정 달 의존 제거, XS-21·XS-22 위치별 케이스 분리, 개인 항목 3케이스, 활성 언어 없음 1케이스, XS-12 제목 단언. 뮤테이션 13건 — 위치마다 해당 케이스만 실패, 원복 13/13.
- 실행 기록 원문: `.docs/BE/2026-11-17-track59-ext-tdd-log.md`(git 무시 작업 메모).

### 확장 Frontend Review Evidence

- 사전 `[문서 .docs/FE/2026-11-17-track59-ext-{wed-pre,bir-pre,wed-add}.md]`: WED·BIR 사전 명세, WED 추가 판정(로딩 색, forced-colors, 실제 잠금 상태).
- 사후 1차 `[문서 …-ext-{wed-post,bir-post,dar-post}.md, .docs/BE/…-ext-coach-post.md]`: WED Deviates(문서), BIR Deviates, DAR 조건부(5건), 코치 조건부(8건) → 전부 반영.
- 재판정 1 `[문서 …-ext-{wed-re,bir-re}.md]`: WED Deviates(문서 4건 + 측정), BIR Deviates(N1·N2·N3·S6-3) → 전부 반영.
- 재판정 2 `[문서 하위 에이전트 보고]`: WED Deviates(문서 2건), BIR Deviates(D1·D2·D3), DAR 조건부(출처 5건), 코치 조건부(4건) → 전부 반영(커밋 `f6752b30`·`4266fb98`·`0c081610`).
- 재판정 3 `[문서 하위 에이전트 보고 2026-11-17]`: WED Conforms(고칠 것 없음), BIR Conforms(고칠 것 없음), DAR 재판정 2 통과(고칠 것 없음), 코치 재판정 2 조건부(핀 F1·F2·F3) → 반영(`9958e12b`) → 코치 재판정 3 통과(고칠 것 없음). BIR 재판정 3이 "닿지 않는다"고 추측한 `?page=1` 주소의 Enter는 오케스트레이터가 3 브라우저에서 재현해 고쳤고(`39d3202d`), BIR 확인 판정 Conforms.
- QVL 완료 판정 `[문서 하위 에이전트 보고 2026-11-17]`: 조건부 완료 — 범위 ①②③ 닫힘, 백로그에 남은 트랙 59 열린 항목 0건, 코드 결함 0건. 기록·측정 7건 요구 → 전부 처리(아래 "확장 Evidence"의 마지막 두 줄).

### 확장에서 새로 찾아 같은 PR에서 고친 것

- 한글 조합 확정 뒤 검색이 걸리지 않던 것(Chromium, main부터) `[실측 CDP 입력기 모의]`.
- 뒤로가기 직후 대기 검색이 결과를 덮어쓰던 것, 같은 검색어의 반복 요청·방문 기록, 조합 중 지우기 링크 `[실측]`.
- 실시간 검색 뒤 결과 밖 링크가 처음 검색어에 머물던 것(N1), Enter 중복 방문 기록(N2·D1), 뒤로가기 `?page=N`에서 1쪽이 뜨던 것(D2) `[실측 3 브라우저]`.
- "전체" 칩만 정렬을 잃던 것(XS-27) `[실측]`.
- 고대비에서 로딩 글자 겹침, 작은 찜 버튼 hover 색, 방문 칩 슬러그·0건 필터, 스태프 스피너 2px 어긋남 `[실측]`.

### 확장 Evidence

- 2026-11-17 커밋 `[실측 git log]`: `6a174885`·`389616c1`·`07c09f6e`·`4df83eb3`·`8c13a1cd`·`01d25707`·`6bfdf86c`·`80652d0a`·`17c90ac0`·`f77a7d7c`(1차), `404a434a`·`5f8c65eb`·`17fd448d`·`b6a39d7b`·`0603c9d0`(재판정 1 반영), `f6752b30`·`4266fb98`·`0c081610`(재판정 2 반영).
- 2026-11-17 재판정 3 반영 커밋 `[실측 git log]`: `39d3202d`(주소 비교에서 `page=1`을 1쪽으로), `9958e12b`(핀 F1·F2·F3), `92f9e0c1`(백로그 한 줄). 핀 뮤테이션 12건 — 위치마다 해당 케이스만 실패, 원복 12/12 `[실측]`. F2 테스트는 쿼리 계층 상수 임포트로 아키텍처 가드에 걸려, 가드 허용 목록을 늘리지 않고 쪽 크기를 응답에서 읽게 고쳤다 `[실측 전체 회귀 1 failed → 0 failed]`.
- 2026-11-17 자동 검증 `[실측 HEAD 92f9e0c1]`: `uv run pytest -q -n auto` 4,585 passed / 54.72초(PR 첫 판 4,508 + 확장 77케이스 `[계산]`), `uv run pytest -q -m e2e tests/e2e` 10 passed / 9.78초, `ruff check`·`ruff format --check`(474개 파일)·`manage.py check`·`makemigrations --check --dry-run` 실패 0. 최종 HEAD(문서 커밋 뒤)의 재실행 값은 PR 본문에 SHA와 함께 적는다.
- 2026-11-17 브라우저 측정 `[실측 오케스트레이터 Playwright Chromium·WebKit·Firefox, 일부 실제 Chrome — 상세는 .docs/FE/2026-11-17-track59-evidence.md의 "확장 — …" 절들]`: 로딩 같은 표본 버튼 392개 중 변경 전 364개 어긋남 → 변경 뒤 0개; `.sr-only` 32개 요소·시리즈 색 118개 요소 전후 차이 0곳; 고대비 버튼 137개 × 2배색 시스템 색; 실제 bfcache 복원 뒤 로딩 표시 해제; 하단 고정 막대 859px·860px 표시·861px 숨김; 언어 표시 범위(공개 8쪽 × 4개 언어, 내 활동 × 3개 언어 × 2폭, 배치 차이 0건); 검색 뒤 결과 밖 링크 254개(13쪽 × 3 브라우저)가 새로 연 쪽과 동일; D1·D2 수정 전 재현·수정 후 해소; 스태프 실제 제출 경로의 `.is-loading`·`aria-busy` 불일치 0·크기 변화 0px.
- 2026-11-17 QVL 요구 측정 `[실측 오케스트레이터]`: 새 카테고리 행사 2건과 6건(3종)에서 홈 쿼리 수 — 로그인 18 → 23·23건, 비로그인 8 → 12·12건(행사 수에 비례하지 않음, 임시 pytest로 재고 파일 삭제). 고대비 에뮬레이션 Firefox·WebKit 버튼 37개씩 시스템 색·글자 채움색 투명·폭 변화 0, 로딩 그림이 라벨을 지운 그림과 픽셀 동일(Chromium·Firefox·WebKit × 2쪽). 홈 설정 원복 확인(`featured_categories = ['exhibition']`, DB 읽기).
- 2026-11-17 QVL 요구 문서 `[코드]`: `docs/backlog.md` 트랙 59 행·`[계산]` 태그, `docs/BE/i18n.md` 가드레일 16의 판정 서술, `docs/BE/category-vocabulary.md` 홈 쿼리 수 `[실측]`, `docs/deploy-runbook.md` §3-22(운영 DB 카테고리·슬롯 7 색 확인).
- 결함 아님으로 판단한 것 `[문서]`: 달력 월 이동 뒤 주소에 `#calendar-month`가 남는 것(홈 달력 `#home-calendar-agenda`와 같은 방식이고, 뒤로가기는 해시 없는 원래 쪽으로 돌아간다 `[실측 PR 첫 판 측정]`). 손으로 고친 주소의 `page=01` 같은 값(페이저는 정수만 만든다 `[코드 templates/core/partials/_pager.html]`).
- 사용자 확인 필요(자동화 불가) `[문서]`: 실제 스크린리더 낭독, 실기기 터치·가상 키보드, macOS 실제 한글 입력기의 조합 중 Enter, 파일 선택창 뒤 포커스, 브라우저 확대 분수 폭, 실제 Windows 고대비, Safari·Firefox의 실제 bfcache, 운영 DB의 카테고리와 슬롯 7 점 색(런북 §3-22), 고정 카테고리가 슬롯을 반납했다가 다른 슬롯으로 재활성화되면 스태프 견본과 공개 화면 색이 달라지는 것의 수용(고정 7종 규칙을 유지한 결과, `docs/BE/category-vocabulary.md` "알려진 어긋남").
- 로컬 흔적 `[실측 DB 읽기]`: 확인용 카테고리 `night_market`(슬롯 7)·`book_fair`(슬롯 8)와 행사 601~604는 남겨 둔다(사용자가 말하기 전에는 지우지 않는다). 측정용 사용자 세션(pk 30·20·80)은 머지 뒤 정리한다. 계정 122는 측정에서 확정 단계를 보내지 않아 그대로다.

## 확장 2 (2026-11-18) — 홈 '내 컬렉션' 패널 요청과 그 과정에서 찾은 것을 같은 PR에서 처리

### 확장 2 요청과 결정

- 사용자 요청 `[문서 2026-11-17 대화 원문]`: "홈 화면의 내컬렉션 보유현황 리스트의 행을 클릭하면 해당 컬렉션의 상세페이지로 넘어가야해. 최근 등록한 굿즈의 사진을 클릭해도 마찬가지. 최근 등록한 굿즈의 사각 섹션 에서 창 너비에 맞게 카드 사이즈를 맞추고 카드와 카드사이에는 라인이 있어야해. 표에서 아웃라인이 있듯이. 각 칸의 카드의 위치는 상하좌우 중앙정렬이 되어야해"
- 사용자 결정 `[문서 2026-11-17~18 선택지 답]`: ① 눌리는 행은 "'기록 대기' 목록의 행". ② "휴대폰에서는 3개로, 섹션 너비 퍼센테이지의 1/3인거지"(PC는 한 줄에 다섯 칸). ③ 다른 행 목록은 바꾸지 않는다 — "'기록 대기' 행만". ④ "비공개 행사도 기록 허용".
- 오케스트레이터 결정 `[문서]`: 같은 브랜치·같은 PR(#421)에서 처리. 화면 문구·번역 문자열·토큰은 새로 만들지 않는다. 직접 등록 항목 행은 그 항목 상세로 간다. 비공개 행사의 홈 행은 제목 링크와 반전 없이 '기록' 링크만 둔다. 비공개 행사의 예정에서 방문 완료로 바꾸는 요청은 그대로 허용한다. 방문 완료 표시를 지운 비공개 행사에는 기록할 수 없다. 스태프 화면의 게시 판정도 같은 속성으로 맞춘다(출력 HTML 동일).

### 확장 2 AC

- AC-H1 `[문서]`: 홈 '기록 대기' 행의 어디를 눌러도 그 대상의 상세로 간다(게시된 행사는 행사 상세, 직접 등록 항목은 항목 상세). '기록' 링크는 따로 눌린다.
- AC-H2 `[문서]`: 최근 굿즈의 사진과 이름이 그 굿즈의 컬렉션 상세로 간다.
- AC-H3 `[문서]`: 최근 굿즈는 창 폭에 맞는 격자다 — 넓은 화면 다섯 칸, 45rem 이하 세 칸, 칸 사이와 바깥에 선, 카드는 칸의 가로·세로 가운데, 가로 넘침 없음.
- AC-H4 `[문서]`: 방문 완료로 표시한 행사는 비공개가 돼도 방문 기록을 남길 수 있다. 다른 사용자의 표시나 예정·관심만으로는 남길 수 없고, 거절 응답은 없는 행사와 구별되지 않는다.
- AC-H5 `[문서]`: 비공개 행사를 가리키는 공개 상세 링크가 사용자 화면(홈·활동 목록·활동 달력·방문 기록 상세)에 없다.

### 확장 2 Activated Roles

- Activated `[문서]`: WED·BIR(사전 명세와 사후 판정), FIE(템플릿·CSS·JS), BIE(백엔드·테스트·문서), Backend TDD Coach(계약과 사후 판정), DAR·SRR(비공개 행사 기록 규칙의 사전·사후), QVL(완료 판정).
- Not Activated `[문서]`: PSO(사용자가 선택지로 직접 결정), DOR(배포·설정·마이그레이션 변경 없음), AAA(LLM 범위 아님).

### 확장 2 Test List (백엔드 — 한 건씩, 오케스트레이터 실행)

- HSL-1~13 `[문서 .docs/FE/2026-11-18-track59-ext2-reports.md의 코치 보고 1·2]`: 홈 기록 대기 행 링크, 굿즈 링크, 비공개 행사 무링크, 제목·장소의 언어 표시, '기록' 링크 이름. 계약 원문은 하위 에이전트 보고로만 있었고 파일로 남기지 않았다가 2026-11-18에 대화 기록에서 꺼내 위 파일에 보존했다.
- VT-1~24 `[문서 .docs/BE/2026-11-18-track59-vt-contract.md]`: 방문 기록 대상 규칙(쿼리·직렬화기·폼 사전 선택·서비스 방어·뷰 응답), 활동 달력 링크, `Event.is_published`, 기록장·상태 목록의 방문 완료 행 링크.
- 그 밖의 고정 `[실측 pytest]`: 스태프 수정 화면·목록의 게시 표시 2건, 굿즈 격자 칸 수 1건(다섯 케이스), 비공개 행사 방문 기록의 상세·수정·삭제 1건.
- 실행 기록과 뮤테이션 원문 `[문서]`: `.docs/BE/2026-11-17-track59-ext-tdd-log.md`의 "확장 2"·"확장 3" 절. 절차에서 어긋난 점(테스트를 두 개씩 맡긴 것, 한 번의 Green에 구조 변경이 섞인 것, 테스트 결함으로 실패한 첫 실행 두 번, 요약 줄을 남기지 않은 Red 두 번)도 그 절에 적혀 있다.

### 확장 2 Frontend Review Evidence

- 사전 `[문서 .docs/FE/2026-11-18-track59-ext2-reports.md "WED 사전 보고 1"·"BIR 사전 보고 1"]`: WED 표 격자 사전 검토, BIR 행 링크 사전 검토. 구현 전에 하위 에이전트 보고로 받았고 파일로는 2026-11-18에 대화 기록에서 꺼내 보존했다.
- 사후 `[문서 같은 파일 "WED 사후 보고 1~4"·"BIR 사후 보고 1~4"]`: WED Deviates(F1~F6) → Deviates(H1~H4) → Deviates(J1) → Conforms. BIR Deviates(F1~F3) → Deviates(F4) → Conforms → 스태프 템플릿 확인 판정 Conforms. 지적은 전부 같은 PR에서 반영했다. WED의 H3(달력 행 최소 높이)·H4(폴백 분기 삭제)는 측정과 DAR 판정을 본 뒤 WED가 철회했다.
- 백엔드 `[문서 같은 파일]`: DAR 사전 → 사후 통과 아님(F1~F4) → 통과 아님(스태프 다섯 곳) → 통과. SRR 사전 → 통과 → 확인 판정 통과. Backend TDD Coach 계약 → 사후 판정을 다섯 차례 거쳐 통과(재판정 4).
- 검토 깊이 `[문서]`: High. 이유 — 홈 행 전체 링크가 겹친 링크 구조를 만들고, 굿즈 격자의 반응형이 바뀌고, 링크 규칙이 여러 쪽(홈·활동 목록·활동 달력·기록 폼)에 걸쳐 한 번에 바뀌었다.
- 계획한 브라우저 증거 `[문서]`: Chromium·WebKit·Firefox 세 브라우저에서 굿즈 격자의 칸·사진 치수와 가로 넘침(폭 아홉 개), 굿즈 수별 칸 구성, 기록 대기 행의 누름 지점·상태별 색·Tab 순서·실제 클릭 이동, 영어 화면 이름, 고대비, 비공개 행사 기록 흐름(폭 두 개), 대상 고정 폼의 거절, 기록장·상태 목록 링크, 활동 달력의 링크 없는 행, 네 언어의 '기록' 링크 이름, 스태프 화면 HTML 대조.
- 측정 원문 `[문서 .docs/FE/2026-11-18-track59-home-snapshot-evidence.md 1~18절]`.
- QVL 완료 결정 `[문서 하위 에이전트 보고 2026-11-18]`: 조건부 완료(C1~C4: 낡은 주석 한 건, 고정 테스트 두 건, 일본어·중국어 링크 이름 측정, 계획·백로그·PR 본문 기록) → 반영 뒤 확인 판정도 조건부 완료(R1: 이 절의 빠진 세 항목, R2: 최종 HEAD 값과 로컬 흔적 문장) → 이 편집으로 반영 → 최종 확인 판정 완료(고칠 것 없음, HEAD `4d746344`). 코드와 테스트에서 찾은 결함은 주석 한 건뿐이었다.

### 확장 2에서 새로 찾아 같은 PR에서 고친 것

- 비공개가 된 행사를 가리키던 404 링크: 홈·활동 목록 세 곳, 활동 달력 세 경로 `[실측 pytest·Playwright]`.
- 홈 기록 대기 제목·장소의 `lang="ko"` 누락, '기록' 링크 이름이 행마다 같던 것, 제목 링크 포커스 링이 잘리던 것, 행 사이 선이 눌리지 않던 것, 굿즈 이름이 낱말 중간에서 끊기던 것 `[실측 Playwright 세 브라우저]`.
- 기록장·상태 목록에서 메모 없이 저장한 방문 기록이 있는 행에 '＋ 기록'이 다시 나오고 '수정'이 없던 것(main부터 있던 동작) `[실측 pytest Red 다섯 케이스]`.
- 대상이 고정된 기록 폼에서 서버가 대상을 거절하면 서버 원문이 그대로 보이던 것 — 기존 번역 문장으로 바꿨다 `[실측 Playwright 아홉 조합]`.
- 게시 판정 비교가 여러 곳에 흩어져 있던 것 — `Event.is_published` 하나로 모았다(뷰·서비스 여덟 곳, 스태프 템플릿 일곱 곳) `[코드]`.
- 이 브랜치가 줄을 밀어 낡게 만든 문서의 파일:줄 인용 — 문서 아홉 개에서 다시 쟀다 `[실측 스크립트 대조]`.

### 확장 2 Evidence

- 2026-11-18 커밋 `[실측 git log 20790403..HEAD]`: `31c95ebc`·`f6c60efc`·`f179c08a`·`1bad4583`·`adf966ce`(홈 패널), `d901c3b4`·`9da3e6bd`·`f0503fcf`(비공개 행사 기록 허용), `fb020e4f`·`6975e058`·`2b60a01e`·`17856d8d`·`f56f3eb2`(사후 판정 반영), `fbe2ee0f`·`66ead434`·`e57c99b4`·`452b1993`·`e8fc7d29`(재판정 반영과 문서 인용). 그 뒤 QVL 조건 반영 커밋과 최종 HEAD의 검증 값은 PR 본문에 SHA와 함께 적는다.
- 2026-11-18 자동 검증 `[실측 HEAD 452b1993]`: `uv run pytest -q -n auto` 4,656 passed / 48.91초, `uv run pytest -q -m e2e tests/e2e` 10 passed / 9.82초, `ruff check`·`ruff format --check`(476개 파일)·`manage.py check`·`makemigrations --check --dry-run` 실패 0건.
- 사용자 확인 필요(자동화 불가) `[문서]`: 실제 스크린리더 낭독(행 링크와 '기록' 링크의 이름, 오류 칸), 실기기 터치의 눌림 표시, WebKit 고대비, 브라우저 확대로 생기는 분수 폭, 가운데 클릭·Ctrl 클릭의 새 탭, 하단 탭 바가 마지막 칸을 가리는 실제 상황. 수용 여부를 물을 것: 링크가 걸린 행에서 글자 드래그 선택이 안 되는 것, 거절 문구 "항목을 찾을 수 없습니다."의 정확성, 거절 뒤 나가는 곳이 방문 기록 목록인 것, 활동 달력의 링크 없는 행. 검토자의 제품 제안 두 가지(기록장·상태 목록 링크에 행 제목을 이름으로 넣기, 같은 행사의 재방문 기록 진입점)는 결함이 아니어서 사용자 보고에 싣는다.
- 2026-11-18 최종 검증 `[실측 HEAD caeedf5e, 오케스트레이터]`: `uv run pytest -q -n auto` 4,662 passed / 53.05초, `uv run pytest -q -m e2e tests/e2e` 10 passed / 10.14초, `ruff check`·`ruff format --check`(476개 파일)·`manage.py check`·`makemigrations --check --dry-run` 실패 0건, CI 체크 6개 pass, `git rev-list --count 20790403..HEAD` 20개. 그 뒤 커밋은 문서 한 개(백로그의 검증 값)뿐이다.
- 로컬 흔적 `[실측 DB 읽기 2026-11-18]`: 이 확장의 측정용 임시 데이터(초안 행사 606·607, 직접 등록 항목 212, 상태 202~205, 찜 83·84)는 삭제했고 남은 행은 0건이다. `[M59]` 확인 행사 601~604는 4건 그대로다.
