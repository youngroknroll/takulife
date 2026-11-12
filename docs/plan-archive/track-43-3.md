# 트랙 43-3: 컬렉션·활동·마이페이지 UI 다국어 (2026-10-22) [v1 — 사용자 지시 "43-3 진행하자"(2026-10-22), 사전 검토 다섯 역할(DAR·TDD 코치·WED·BIR·QVL) 통합. 구현 완료, 브랜치 `feat/i18n-collection-43-3`, 완료 결정 = 조건부 완료(§6)]

> **기준선**: main `c0f61e1f`에서 `uv run pytest -q` → 3419 passed / 10 deselected / 47.86초 `[실측 2026-10-22]`, e2e 10 passed `[문서 pr-log #395·#396]`. 사실 파일 `scratchpad/facts_43_3.md`(측정 스크립트 `measure_43_3.py`·`measure_43_3_py.py`).
> **사용자 결정 반영**: ① 개인 항목 제안 칩 번역(저장은 서버가 한국어 원문으로 정규화) ② 아카이브 과도기·BIR Unverified 수용 ③ 새 카테고리 자동 번역은 트랙 44-4(범위 밖).

## 1. 범위 (오케스트레이터 실측, 검토 역할이 재확인)

- **템플릿 26개 파일 / 한국어 487줄** `[계산 578-48-43]`: `core/archive/` 16 + `core/partials/_archive_*`·`_collection_badges` 9 + `core/mypage.html` 1 `[계산]`. 제외: `core/drafts/*`·`core/staff/*`(`@staff_console_required` 스태프 화면 `[코드 staff/views/drafts.py:130,161,180]`), `core/legal/*`(1차 승인 제외), `_account_settings_panel_head.html`(한글이 주석뿐 `[코드]`).
- **JS 11개 파일 / 108줄** `[실측 measure_43_3.py]`. 변수가 낀 문장 조립 14곳 `[실측 BIR rg]`.
- **파이썬 사용자 노출 메시지**: `archive/services.py` 7·`serializers.py` 5·`views.py` 2(324·392행) `[실측]`, `web/views/{collection,account,activity,archive}.py` 라벨·단위, `core/vocab.py` 제안 칩 6개(158~163행 `[코드]`). `archive/views.py` 한글 상수 92개 중 90개는 OpenAPI 문서·로그·독스트링이라 번역 대상이 아니다 `[실측 AST 분류]`. `core/vocab.py` 27~33행은 `gettext_noop` 원문, 209~211행은 스태프 정렬이라 제외 `[코드 DAR]`.
- **날짜 서식 8곳**: 템플릿 `date:'n월'` 4·`Y년 n월 j일` 1·`Y년 n월 j일 l` 1·`n월 j일` 1·`calendar.html:117`의 `n월` 접미 1, 파이썬 `activity.py:91,349` `[실측 rg]`.

## 2. 사전 검토 통합 — 결정과 정정

1. **정규화는 서비스가 아니라 시리얼라이저에 둔다(DAR·TDD 코치 일치, 소스 확인)**: 개인 항목 쓰기 경로가 둘이다 — POST는 `create_personal_entry`, PATCH는 서비스 없이 DRF 기본 `update`다 `[코드 archive/views.py:112-116,149-160]`. `PersonalEntryUpdateSerializer`가 `PersonalEntrySerializer`를 상속하므로 `validate_category` 한 곳이 둘을 덮는다 `[코드 archive/serializers.py:17,51]`. 굿즈 유형 `item_type`도 쓰기 경로가 시리얼라이저 하나다 `[코드 archive/serializers.py:316]`.
2. **정규화 규칙(기본값)**: `core/vocab.py`에 순수 함수 둘 — `normalize_*(value)`(strip·casefold·악센트 무시 후 지원 언어 전부의 번역 또는 한국어 원문과 같으면 한국어 원문, 아니면 입력 그대로)과 `*_label(value)`(저장된 한국어 원문이 어휘일 때만 요청 언어로 번역). 번역 조회는 `translation.override(code)` + 즉시 `gettext`(지연 번역은 override 밖에서 평가되어 오답). 악센트 무시는 영문 키보드의 `cafe`가 `Café` 칩과 같게 하려는 선택이다(TDD 코치 P9, WED 허용 한계와 달리 포함 — 사용자가 반대하면 제거).
3. **칩 표시·값 방식**: 칩 라벨과 입력창 값이 같은 요청 언어 문자열이다 `[코드 personal_create.js:61-62]`(BIR의 값 분리 안은 영어 UI 입력창에 한국어가 뜨는 단점이 있어 채택하지 않음, JS 변경 없음). 수정 화면은 저장된 한국어 원문이 어휘일 때 입력창에 번역 라벨을 미리 채워 칩 활성 비교(`dataset.categoryLabel === value` `[코드 personal_edit.js:110-111]`)가 맞게 한다. 저장 시 서버가 다시 원문으로 정규화하므로 멱등이다.
4. **굿즈 유형 칩도 같은 결함이 main에 이미 있다(BIR D1, 소스 확인)**: `collection_create.html:86-87`이 번역 라벨을 `data-type-label`로 내보내고 `collection.js:131`이 `input.value`에 넣어 영어 사용자가 저장하면 `item_type`에 번역 문구가 들어간다. 필터는 정확히 일치(`archive/queries.py:500`)라 "Keychain"과 "키링"이 갈라진다 `[코드]`. 사용자 결정(2026-08-25 같은 유형 소규모 결함은 같은 트랙에서 수정)에 따라 43-3에서 같은 정규화를 적용한다. production에는 i18n이 아직 없어 오염 데이터는 없다(deploy PR #393 OPEN `[실측 gh]`) — **#393이 43-3보다 먼저 머지되면 영어 방문자가 번역 문구를 저장할 수 있다.**
5. **영어 `detail` 세 곳(`archive/views.py:213,318,457`)은 번역·통일하지 않는다**: `code`가 함께 내려가고 JS가 `code`를 먼저 처리해 화면에 `detail`이 나오지 않는다 `[코드 static/js/shared/api.js:107-112]`. 이전 기록("318행 하나, 한국어로 통일 후 번역")을 폐기한다. 단언 테스트 둘은 그대로 둔다 `[코드 tests/archive/test_event_interest_api.py:65, test_user_event_status_api.py:164]`.
6. **서비스·시리얼라이저·뷰 메시지는 즉시 `gettext`**(함수 안에서 발생, `docs/BE/i18n.md` 결정과 일치). 이전 계획(§4-3 "서비스는 `gettext_lazy`")을 정정한다. 영문 식별자(`quantity` 등)는 API 필드명이라 msgid에 그대로 둔다. 화면 도달: DRF 400 → `formatError`가 `필드명: 메시지`로 이어 붙인다 `[코드 api.js:121-127]` — UI 입력 검사로 정상 도달은 어렵고 직접 호출에서만 나온다(번역 가치는 낮지만 영어 화면에 한국어가 남지 않게 한다).
7. **날짜 서식**: `Y년 n월 j일`→`DATE_FORMAT`, `n월 j일`→`MONTH_DAY_FORMAT`, `Y년 n월`→`YEAR_MONTH_FORMAT`, 월만 쓰는 `n월`→`M`(좁은 칸 폭 44px·74px `[코드 archive.css:378,593]`이라 약어), 달력 제목은 `F`. 한국어 12개월 `n월` 대 `M` 불일치 0 `[실측 2026-10-22 django shell]`. 활동 달력 aria-label은 `DATE_FORMAT` + `l`을 자리표시자 `blocktranslate`로 합성(영어만 어순 변경). 요일 머리글 7개는 43-2의 `context "요일"` 재사용 `[코드 _archive_calendar_grid.html:21-27]`. `activity.py:349 month_label`은 템플릿이 읽지 않고 테스트 하나가 단언한다 `[코드 tests/core/test_activity_calendar_view.py:483]` — `date_format(.., "YEAR_MONTH_FORMAT")`로 바꾼다(0 채움 차이는 연도 1000 미만의 조작된 `?month=`에서만, 수용).
8. **마이페이지 배지 중복 제거**: `domain_label in title` 부분문자열 검사 `[코드 web/views/account.py:133-135]`는 번역하면 깨진다(영어 "My collection"이 "Collection"을 포함하지 않아 배지 중복 낭독). 검사를 지우고 행 1·2에 `"domain_label": ""`를 명시한다(한국어 출력 불변, `tests/core/test_mypage_view.py:257-262`가 고정). 단위(점·건·곳·장·개)는 `ngettext`/`npgettext`(영어 단수/복수, 한국어는 `msgid_plural` 동일, 가드레일 14).
9. **JS 문장 조립**: `interpolate(gettext("…%(n)s…"), {n: …}, true)` 한 가지 패턴(선례 `home_hero_rotator.js:111`). 복수형이 필요한 곳은 `archive_search.js:108`(`건 검색됨`)과 `visit_create.js:287`·`visit_edit.js:360`(업로드 개수)이며 **저장소의 JS `ngettext` 첫 사례**다 — 한국어 폴백이 한국어 원문과 같도록 두 인자는 같은 글자. `pgettext`는 JS에서 쓰지 않는다(폴백·가드 미지원 `[코드 i18n_fallback.js:11,17,23, test_ui_korean_literal_guard.py:117-121]`). 이미 있는 msgid(`네트워크 오류가 발생했습니다. 다시 시도해 주세요.` 등)는 글자 그대로 재사용.
10. **`lang="ko"` 적용표(WED S-1)**: 공식 행사의 제목·장소만 태그한다(`row.subject.is_official` 조건부, `detail_url`이 있는 `<a>`는 공식 `[코드 web/views/_helpers.py:151-178]`). 개인 항목·컬렉션 굿즈·후기·메모·닉네임·이메일은 사용자 입력이라 태그하지 않는다(BIR C8-b). 번역 어휘(카테고리·상태·지역)는 태그하지 않는다. `<option>` 행사 제목은 태그, 개인 항목 option은 안 함. 활동 달력 항목 라벨은 출처 플래그가 없어 태그하지 않는다(알려진 한계 — `CalendarActivityItem` 변경은 범위 밖). `alt`는 속성이라 `lang` 불가(한계). 줄 단위 적용표는 WED 보고서를 구현 브리프에 그대로 싣는다.
11. **마이페이지 연차 `년 활동 중`·방문 상세 `{요일} 방문`은 어순이 다르다**: 값과 라벨을 한 `blocktranslate` msgid에 넣어 번역가가 어순을 바꾼다 `[코드 mypage.html:19-20, visit_detail.html:43]`.
12. **활동 달력 월 이동 줄은 겹칠 위험이 구조상 낮다**: `.calendar-month-nav`가 `flex-direction: column`이다 `[코드 static/css/pages/archive_calendar.css:219-224]`. `docs/BE/i18n.md` 가드레일 18의 "같은 위험" 문장은 정정한다. 그래도 열두 달 × 영·일·중 × 360px로 실측하고 한국어 높이 변화 0을 확인한다(CSS는 겹침이 측정될 때만 수정).
13. **CSS 변경 후보(측정 후 판단)**: ① 찜 목록 행 `.record-row-pills`가 줄바꿈 없음 `[코드 archive.css:800-804]` — 320px에서 넘치면 `flex-wrap: wrap` ② 마이페이지 위험 행 "모든 기록과 컬렉션이 삭제됩니다"가 모바일 `nowrap`+말줄임 `[코드 mypage.css:226-231,331-333]` — 파괴 경고가 잘리면 `white-space: normal` ③ 히어로 요약 카드·컬렉션 탭은 측정 뒤. 모두 측정 전 추정이다.
14. **테스트 인프라**: `tests/conftest.py`의 autouse는 카테고리 시딩 하나뿐이고 언어 복원이 없다 `[코드 tests/conftest.py:34]`. 서비스 메시지를 `gettext`로 바꾸면 영어 요청 테스트 뒤에 `tests/archive/test_archive_services.py`의 한국어 단언 9곳이 순서 의존으로 깨진다 `[실측 rg]`. 구현 전에 `translation.activate("ko")` 후 `deactivate`하는 autouse fixture를 먼저 추가한다.
15. **한국어 리터럴 가드 확장**: 템플릿 고정 목록 45개→71개 `[계산 45+26]`, JS 15개→26개 `[계산 15+11]`. 고정 목록의 누락=미탐이므로 "모든 소비자 템플릿은 목록 또는 명시 제외 목록(스태프·드래프트·법률)에 속한다"는 분할 테스트를 더한다. 파이썬 AST 가드는 `web/views/{collection,activity,archive,account}.py`, `archive/{services,serializers}.py`로 넓히고(`archive/views.py`는 `extend_schema`·`OpenApiResponse` 호출 면제 후) `_GETTEXT_FUNCTION_NAMES`에 `gettext_noop`·`pgettext_lazy`·`ngettext_lazy`·`npgettext_lazy`를 추가한다 `[코드 test_ui_korean_literal_guard.py:179-181]`.

## 3. Activated Roles / Not Activated

- **Activated**: Backend TDD Coach(사전 완료), Backend & Integration Engineer(구현), Domain Architecture Reviewer(사전 완료), Web Experience Designer·Browser Interaction Reviewer(사전 완료·사후 판정 필요), Frontend Implementation Engineer(템플릿·JS), Quality Verification Lead(사전 완료·사후 판정 필요).
- **Not Activated**: Product Scope Owner(범위·제품 결정은 사용자가 확정), Security & Resilience Reviewer(정규화는 알려진 어휘로의 매핑일 뿐 신뢰 경계·권한을 바꾸지 않음 — 속성 안 번역 이스케이프는 카탈로그 가드 E-29가 막음), Deployment & Operations Reviewer(마이그레이션·설정 변경 없음), AI Automation Architect.

## 4. 슬라이스·커밋·병렬 (DAR·TDD 코치)

1. 테스트 인프라(언어 복원 fixture) + 한국어 특성화 핀(K0, 번역 전 현재 출력을 글자 단위로 고정; 전부 Green이라 변이로 Red 증거).
2. `core/vocab.py` 칩·함수 + `archive/serializers.py` 정규화(개인 항목·굿즈 유형) — 순차, 첫 계약: "영어 요청 `Pop-up store` 등록 → 저장 `팝업스토어`"(`tests/archive/test_personal_entry_category_i18n_api.py`).
3. 서비스·뷰 메시지(`archive/services.py`·`views.py`의 두 응답).
4. `web/views/*` 라벨·단위·날짜·마이페이지 + 해당 partial. 2 이후.
5. 템플릿 26개(아카이브·컬렉션·마이페이지) `[계산]` — 병렬 가능(파일 집합 분리).
6. JS 11개 `[계산]` — 병렬 가능.
7. `makemessages` → 번역 시트 → 영·일·중 번역 → 패치 → 컴파일 → 독립 AI 검수.
8. 가드 확장(템플릿·JS·파이썬·카탈로그) + 누수 스캔(아카이브·컬렉션·활동·마이페이지 장면) + 번역 단언.
9. 브라우저 검증·사후 판정·문서(`docs/BE/i18n.md`·`docs/backlog.md`)·PR.
- 새 테스트는 모두 새 파일에 둔다(기존 800줄 초과 파일 5개 `[실측 TDD 코치]`). 파일 분할안: `test_personal_category_normalization.py`(순수 함수), `tests/archive/test_personal_entry_category_i18n_api.py`, `..._chips_i18n_view.py`, `test_archive_error_messages_i18n.py`, `test_collection_ui_translations.py`, `test_activity_ui_translations.py`, `test_mypage_ui_translations.py`, `test_archive_ui_leak_scan.py`, `test_python_korean_literal_guard.py`.

## 5. 수용 기준과 증거 (QVL)

기준선은 전체 회귀 3419 passed / 10 deselected `[실측 2026-10-22]`이고 아래는 이 기준선에 대한 요구사항이다.

- **AC1 번역 완결성**: E-27~E-30 자동 적용 + JS 리터럴 추출→`djangojs.po` 존재 비교(E-27은 언어끼리만 비교해 소스와의 어긋남을 못 잡는다). `makemessages` 후 msgid 수·fuzzy 0을 `msgfmt --statistics`로 실측.
- **AC2 한국어 불변**: 저장소 K0 핀 + 일회성 main 대 브랜치 보이는 텍스트·접근성 속성 비교(43-2의 `ko_regress.py`·`ko_login_render.py` 방식, 로그인 임시 사용자). JS 오류 문구 여섯 종의 `textContent`.
- **AC3 언어 누수 0**: 아카이브·컬렉션·활동·마이페이지 장면(빈 상태·채운 상태·partial·필터·달력 월 경계·query_failed)에서 `lang="ko"` 밖 한글 0건. 사용자 입력·행사 제목은 ASCII 픽스처로 만들어 한글이 곧 누수가 되게 한다(43-2 방식). **스캔 사각지대**: `value=`·`data-*`·`textarea` 본문 — 알려진 한계로 기록하고 한글 메모 장면 하나로 `lang="ko"` 감쌈을 고정.
- **AC4 날짜**: ko 열두 달 `n월`=`M` 단언, 월 경계(12월→1월, 윤년 2/29), 영·일·중 한글 0.
- **AC5 정규화**: 네 언어 × 제안 칩 여섯 개 → 원문(단사성 포함), 자유 입력 불변, PATCH 경로, 활성 언어 누수 없음(호출 전후 `get_language()` 동일), 방문 필터 토큰 불변, 굿즈 유형 칩 동일 규칙.
- **AC6 JS**: 정적 가드 + `/jsi18n/` 영어 응답에 msgid 존재 + 자리표시자 이름 비교 + 브라우저 실측(사진 5MB 초과·형식·장수 초과·업로드 부분 실패·검색 결과 0/1/2건·확인 모달). `tests/e2e/`는 한국어만이라 증거가 아니다 `[코드 QVL 확인]`.
- **AC7 성능·구조**: `assertNumQueries` 계약 테스트 파일 불변, `check`·`makemigrations --check` 변화 없음, 전체 회귀는 기준선 + 신규, e2e 10 passed 유지 `[문서 pr-log]`.
- **변이 계획**: 정규화 제거·casefold 반전, 날짜 서식 `F` 복귀, 개수를 1 또는 2로 고정, 자리표시자 이름 변경, 가드 목록 파일 제거 — 각각 Red 확인 후 원복(`.mo` 재컴파일 필수).

## 6. Frontend Review Evidence

- **깊이**: Standard를 기본으로 하되 **High로 올리는 지점** — 칩 정규화(저장 데이터가 언어에 따라 갈라짐)·JS 문장 조립과 첫 `ngettext`·320px 실측(WED·BIR 권고).
- **WED 사전 사양(요지)**: 위 §2-10 `lang="ko"` 표, §2-7 날짜 표, 길이 위험 순위(§2-13), 용어 재사용 목록과 새 용어 후보(교환 Trade/交換/交换, 미보유 Not owned/未所持/未持有, 획득 경로 Source/入手経路/获取途径, 직접 등록 Self-added/自分で登録/自行登记, 공식 제보 Submit as official/公式として報告/提交为官方, 성지순례 Pilgrimage site/聖地巡礼/圣地巡礼, 굿즈숍 Goods shop/グッズショップ/周边商店, 카페 Café/カフェ/咖啡馆), 찜 버튼 `context "동작"`과 통계 `context "통계"`를 섞지 않는다. 인수 기준 S-1~S-15(`lang` 오적용·ko 한 글자 차이·월 이동 겹침·배지 중복·칩 정규화·320px 가로 스크롤·단수 오류가 Deviates) `[문서 WED 보고]`.
- **BIR 사전 기준(요지)**: High 권고. 텍스트로 로직을 분기하는 곳은 없음(rg 패턴 범위 한계) `[문서 BIR 보고]`. 라이브 리전은 빈 상태로 시작해 `textContent`로만 채우는 구조 유지. 서버 한국어 메시지가 `formatError`로 영어 화면에 노출되는 경로는 번역으로 막는다. `/jsi18n/` 차단 시 콘솔 ReferenceError 0건. 확인 모달은 `confirm-modal.js` 불변, 360×640에서 가장 긴 영어 문구가 잘리지 않는지 실측. 활동 달력 `#selected-date`는 이미 `tabindex="-1"` `[코드 calendar.html:146]`, 범례 활성 링크 aria-label이 가시 문구로 시작해야 한다(WCAG 2.5.3, 같은 `if` 체인이 `calendar.html:91,93,166`에 반복돼 변수 하나로 모은다). 활동 달력 `이번달`의 가시 문구와 aria-label `오늘로 이동`이 다른 기존 불일치는 사용자 결정 후보(R1, 이번 범위에서 건드리지 않음).
- **계획된 브라우저 증거**: 언어 네 개 × 아카이브 화면·달력·컬렉션·마이페이지·폼 × 320·360·500·800px, `lang="ko"` 밖 한글 스캔(사용자 입력 예외), 가로 넘침(`scrollWidth`)·겹침(`getBoundingClientRect`), 활동 달력 월 제목 열두 달 × 영·일·중, 한국어 불변 비교, 편집 화면 칩(제안 값 저장→언어 전환→입력창·칩 상태). 함정: 언어 쿠키 `HttpOnly`(푸터 폼 POST로 설정), iframe `srcdoc`의 `/jsi18n/` 오탐, bfcache로 남은 이전 언어 카탈로그, 임시 사용자·캡처 정리.
- **사후 판정(2026-10-23)**: **BIR = `Unverified`**(`Deviates` 0건, 기준 여덟 개 모두 코드 근거로 Conforms `[문서 BIR 사후 보고]`). 화면 재현이 없어서 `Unverified`였던 항목 중 사진 5MB 초과·형식·장수 초과 문구(en·ja·zh·ko)·부분 실패 문구(사진 1장 "photo was"·2장 "photos were"의 `ngettext` 분기)·부분 실패 후 이동 링크 포커스·활동 달력 실제 Tab 순서(ko·en 동일, DOM 순서)·포커스 링은 브라우저로, `/jsi18n/` 실패 폴백은 node 실행으로, `confirm-modal.js` 무수정은 diff 0바이트로 닫았다 `[실측 2026-10-23]`. 닫지 못한 것: 일부 사진만 성공하는 부분 실패(n>0), OS 파일 선택 창(`File`/`DataTransfer`+`change`로 대체), `/jsi18n/` 차단의 브라우저 재현, 라이트 테마, 실제 터치·스크린리더, 폭 385~919px 전 구간(대표 폭만), ja·zh 링크 접근 가능한 이름 스냅샷. **WED = `Deviates`(경미) 둘** `[문서 WED 사후 보고]`: ① 공식 행사 제목 `lang="ko"` 누락 5곳 중 3곳(잠긴 방문 대상·잠긴 방문 기록·연결된 방문 기록 제목)은 테스트 먼저(Red 3개)→구현→Green, 변이 6개 Red로 **수정했다**(나머지 2곳 — 제목+날짜 혼합 `<option>`과 컬렉션 상세 연결 방문 값 문자열 — 은 승인 사양이 태그하지 않기로 한 한계로 유지) ② 한국어 화면 변경 2건(활동 달력 검색 폼이 384px 이하에서 전폭, 찜 링크가 860px 이하에서 `♥ 찜`)은 한국어 320px에서 글자가 세로로 쌓이던 기존 결함을 푸는 수정이며 **사용자 인지 확인이 필요하다**.
- **QVL 완료 결정 = 조건부 완료** `[문서 QVL 최종 보고 2026-10-23]`. 조건: 사용자가 열린 결정 (a) 한국어 화면 변경 2건 유지 (b) 배포 PR #393을 43-3보다 먼저 머지하지 않기 (c) 악센트 무시 정규화 유지 (d) 원어민 검수 없음을 명시 수용하는 것과 미측정 범위(라이트 테마·실제 터치·스크린리더·385~919px)를 위험으로 받아들이는 것. AC 판정: AC1·AC3·AC5·AC7 충족, AC2는 의도된 변경 2건 때문에 부분, AC4는 한국어 열두 달 불변이 100장면 비교에 포함돼 충족(간접), AC6은 n>0 부분 실패·`/jsi18n/` 브라우저 재현·OS 파일 선택 창이 남아 부분. 전체 회귀 3985 passed / 10 deselected `[실측 2026-10-23]`.

## 7. 이연·알려진 한계 (트리거 명시)

- 개인 항목 검색(`archive/queries.py:326` `icontains`)은 한국어 저장값만 맞춘다 — 영어로 `exhibition`을 검색하면 안 걸린다 `[코드 DAR]`. 트리거: 다국어 검색 요구.
- 이미 영어로 직접 저장된 자유 입력 값의 일회성 정규화 마이그레이션 — 운영 DB 분포를 세어 건수가 0이 아닐 때. 현재 production에 i18n이 없다.
- 활동 달력 항목 라벨의 출처 플래그(`CalendarActivityItem`) — 행사 제목에도 `lang="ko"`를 붙이려면 도메인 변경 필요.
- `core/legal/*` 한국어(소비자 화면) — Known gap으로 기록(1차 승인 제외).
- 파일명 목록 구분자 `, `의 gettext 노출(R2) — ja·zh에서 어색할 수 있으나 결함 아님. 검색 개수 알림을 서버 렌더 문구로 옮기는 안(R3)은 구현자 선택, 기본은 `ngettext`.
- 알려진 한계: 번역은 AI 검수만(원어민 없음), 라이트 테마·중국어 고정 CTA·로그인 상태 비-ko 모달은 Unverified 수용.

---

