# 트랙 43-2: 이벤트 화면(목록·달력·상세) UI 다국어 (2026-10-22) [v1 — 트랙 43 §7·§8 승인 범위 안, 사용자 "다음 단계 진행하자"(2026-10-22). WED·BIR·백엔드 TDD 코치 사전 검토 통합]

> **기준선**: main `20156602`(PR #395 머지 후 docs 커밋), 전체 회귀 3254 passed / 10 deselected / 105.66초 [실측 2026-10-21 main 8b7a9458]. 브랜치 `feat/i18n-events-43-2`.
> **오케스트레이터 재확인**: 검토 3건의 file:line은 소스로 대조했다 [실측 rg·sed 2026-10-22]. 틀린 브리프 3건은 §7에 기록했다.

## 1. 범위 (승인: 트랙 43 §7 "43-2 이벤트")

- **포함**: `templates/core/events/{list,calendar,detail}.html`(한글 포함 줄 48·44·33 [실측 grep -c]), `static/js/pages/event_list.js`(한글 문자열 2개, 8행 [코드]), `web/views/events.py`의 한국어 리터럴 3자리(261·500·551행, 상수 조각 4개 [실측 AST]).
- **제외**: 스태프 콘솔, `events/services.py` 스태프 게시 검증 메시지 8개 [실측 AST], `events/views.py` API 설명 4개 [실측 AST], 행사 콘텐츠, `Category.label`과 `core/vocab.py`의 `CATEGORY` 한국어 라벨(§3 승인 제외 — **2026-10-22 사용자 결정으로 번역 대상이 됨**: 시드 카테고리는 §2-14, 새 카테고리 자동 번역은 트랙 44-4), 법률 문서. `event_list.js`를 함께 로드하는 아카이브 템플릿 5개 [실측 rg]는 43-3 범위다.

## 2. 검토 통합과 결정 (충돌은 소스 실측과 승인 범위로 해소)

1. **필터 토글**(BIR A3 기본안 채택): 서버가 `{% translate "필터 열기 ▾" as … %}`로 렌더한 텍스트와 `data-label-open`·`data-label-close` 속성을 만들고 JS는 그 속성만 읽는다. JS에 한국어 문자열이 없어 두 카탈로그 불일치와 `/jsi18n/` 실패 시 언어 혼합이 생기지 않는다. `event_list.js`는 JS 가드 목록에 추가한다(14→15 [계산]).
2. **[2026-10-22 사용자 결정 "카테고리도 번역 대상임"으로 §2-14가 대체]** 초기안 — **카테고리 이름**(WED "칩 번역"과 BIR "번역 금지"가 충돌): 이벤트 화면에서는 모든 카테고리 이름을 한국어 + `lang="ko"`로 통일한다. 같은 slug가 한 화면에서 영어 칩과 한국어 필터로 갈라지고, 적용 칩(`CATEGORY_LABELS` 한국어)과 빠른 칩이 나란히 서로 다른 언어가 되기 때문이다. 하드코딩된 빠른 칩 2개는 뷰가 넘기는 `CATEGORY_LABELS`로 렌더해 한국어 리터럴 가드를 약화하지 않는다. 홈의 번역된 칩(43-1)은 그대로 둔다. **사용자 결정 대기**: 카테고리 이름 번역 여부(§8).
3. **[§2-14로 대체 — 카테고리가 번역되면 `lang`을 따로 붙일 칩이 없어 문자열 리스트로 되돌린다]** 초기안 — **적용 칩 구조**(WED·BIR·코치 일치): `_active_filter_chips`가 문자열·지연 번역 혼합 리스트라 카테고리 칩에만 `lang`을 붙일 수 없다. 항목을 `{"label", "lang"}` 딕셔너리로 바꾸고, 리스트 전체를 직접 단언하는 기존 테스트 4줄(`tests/events/test_event_list_view.py:162,174,175`, `tests/core/test_events_calendar_view.py:399-400` [실측 rg])을 라벨 비교로 고친다. 이 컨텍스트 키는 템플릿 3곳만 읽는다 [실측 rg].
4. **목록 h1·title·og_title**: `msgctxt "페이지 제목"` 새 msgid(en Events). 푸터의 `이벤트 목록`은 en All events인데 이 페이지는 기본 필터가 진행·예정만 보여 "All"이 오해를 준다. 달력 제목은 푸터 msgid 재사용.
5. **`source_name 제공`**: 초안은 `%(source)s 제공` 단일 msgid에 `lang`을 붙이지 않기로 했다(영문 출처명일 수 있음, BIR C7). **구현 중 뒤집음(2026-10-22)**: 출처가 있는 행사 50개의 값 5종이 전부 한글이라 [실측 shell] 영·일·중 화면에서 한국어가 `lang="ko"` 밖으로 샜다(브라우저 점검이 적발). msgid를 `<span lang="ko">%(source)s</span> 제공`으로 바꿨다. 행사 제목·작품명·장소·요약·카테고리 이름·출처 이름에 붙이고 `region_label`·`status_label`에는 붙이지 않는다(번역 어휘, 계획 §13). 출처가 영문인 행사가 생기면 그 값에도 `ko`가 붙는다(정보).
6. **기본 메타 설명**: 함수 안 `gettext`로 `base.html`과 같은 msgid를 재사용하고, 이 분기의 `truncatechars(…, 100)`을 뺀다. 번역문 길이는 ko 78·en 148·ja 60·zh 45자 [실측 python len]이라 en이 중간에서 잘린다. `summary`·파츠 분기의 100자 제한은 유지한다.
7. **`month_label`**(500행, 이벤트 템플릿·테스트가 읽지 않는 키 [실측 rg]): 키 이름은 docstring 계약이라 유지하고 값만 `date_format(date(year, month, 1), "YEAR_MONTH_FORMAT")`로 바꾼다. ko는 `Y년 n월`이라 1000년 이상에서 출력이 같다 [코드 django ko formats.py:8]. 활동 달력의 같은 키(`web/views/activity.py:349`)는 43-3이다.
8. **서식**: 목록 월 칸·달력 월 이름은 `date:"F"`, 달력 선택일 제목은 `date:"MONTH_DAY_FORMAT"`(ko `n월 j일`과 글자 동일 [코드 formats.py:9]). 숫자 서식(`Y/m/d` 등)과 `date:"l"`은 유지. zh-hans는 월·일이 0 패딩된다(홈과 같은 Django 표준 동작, 수용).
9. **개수**: `검색 결과 N개`·`이벤트 N건`은 `blocktranslate trimmed count`로 만들고 숫자 `<span class="results-count">`를 msgid 안에 둔다(속성까지 원문과 같아야 함, 가드레일 3). 한국어는 단수·복수 같은 글자.
10. **마감 표기 5종·일정/장소 미정·월 이동·지역/상태 칩**: 43-1 msgid를 그대로 재사용한다(`D-%(dday)s`의 자리표시자 이름은 `dday`). **찜** 3곳은 `context "동작"`(en Save, 컨텍스트 없는 `찜` msgid는 없음 [실측 grep]). 상태 버튼 `방문 예정`·`방문 완료`·`놓침`은 재사용(JS가 클릭 후 같은 번역으로 덮어씀). `현재 상태: <span>`은 `{% translate "현재 상태:" %}` + `<span>`으로 쪼갠다(e2e가 `현재 상태: 방문 예정` 텍스트를 찾음 [코드 tests/e2e/test_event_status_journey_e2e.py:17]).
11. **속성 안 번역**은 `{% translate … as v %}`·`{% blocktranslate trimmed asvar v %}`로 변수에 담아 쓴다. **정정(BIR 사후 판정, Django 소스로 확인)**: 두 경우 모두 결과가 안전 문자열이라 속성에서 이스케이프되지 않는다 [코드 django/templatetags/i18n.py 94-98행 `mark_safe`·201행 근처 `SafeString`]. 초안의 "변수 출력은 이스케이프됨"은 틀렸다. 번역문에 원문에 없는 `"`가 들어가면 속성이 깨지므로 카탈로그 가드(E-29, msgstr의 이스케이프되지 않은 `"` 개수가 원문 이하)가 속성 안전의 유일한 장치다.
12. **CSS**: 영어 월 이동 줄이 360px에서 넘칠 것으로 WED가 추정했다 [계산 추정]. 브라우저 측정으로 확인된 경우에만 `static/css/pages/event_calendar.css`의 ≤45rem 블록에 wrap 허용 변경 1건을 넣는다. 확인되지 않으면 CSS 변경 0건.
13. **테스트 수집기**: 기존 `_LangTrackingParser`는 void 태그(`input` 등)를 스택에 넣고 닫을 때 팝해 `lang="ko"` 판정이 형제로 샌다 [코드 tests/core/test_ui_translations.py:61-74]. 새 테스트는 void 태그를 푸시하지 않는 수집기를 쓴다.
14. **카테고리 이름 번역 (사용자 결정 2026-10-22 "카테고리도 번역 대상임", §2-2·§2-3 대체)**: 머지 전 같은 PR(#396)에서 처리한다. 설계 — ① `core/vocab.py`의 `CATEGORY` 7개 값을 `gettext_lazy`로 바꿔 행·상세·적용 칩·빠른 칩·홈 행·아카이브가 같은 번역을 쓴다(msgid는 한국어 그대로, 이미 번역된 `팝업스토어`·`콜라보 카페`·`굿즈 예약` 재사용, 새 msgid `극장 특전`·`전시`·`팬미팅`·`콘서트` 4개 [실측 grep]). ② DB 라벨(`Category.label`, 필터 체크박스·홈 타일)은 뷰에서 `gettext(label)`로 번역한다 — 어휘 msgid와 글자가 같으면(7개 모두 동일 [실측 shell]) 번역되고 스태프가 새로 만든 라벨은 한국어 그대로 남으며 그때만 `lang="ko"`를 붙인다(한국어 요청은 번역 없음). ③ 카테고리 이름 요소의 `lang="ko"`를 모두 제거한다(번역된 영어에 `ko`가 붙으면 오류). ④ 지연 번역 객체가 `str` 전용 API에 들어가는 곳(메타 설명의 `" · ".join`)은 `str()`로 감싼다. ⑤ 아카이브 방문 필터는 라벨 문자열이 필터 키라(`web/views/archive.py:239-270`) 번역 언어에서도 같은 요청 안에서 일관되게 동작해야 한다 — 영어 요청 테스트를 추가한다. ⑥ 한국어 출력은 그대로여야 한다(번역 카탈로그가 없는 `ko`는 msgid가 그대로 나옴).
15. **§2-14 사전 검토 통합(WED Standard 권고·BIR Light, 2026-10-22)**: ⑦ 제거 대상에 홈 달력 범례 `_home_event_calendar.html:79` `legend-label`을 추가한다(어휘 값 [코드 web/views/events.py:148-152]). 홈 컬렉션 스냅샷 `snapshot-record-cat`의 `lang="ko"`도 제거하고 비공식 항목의 사용자 입력 카테고리는 태그하지 않는다(사용자 입력 규칙, BIR C8-b). ⑧ 조건부 `lang="ko"`(DB 라벨 — 필터 체크박스·홈 타일)는 뷰가 판정한다: 활성 언어가 `ko`가 아니고 `gettext(label) == label`이며 라벨에 한글이 있을 때만 `"ko"`(스태프가 영문 라벨을 만들면 붙이지 않음). 체크박스는 `(slug, label, lang)` 3-튜플 컨텍스트 `CATEGORY`로 바꾸고(`events/queries.py`의 `consumer_category_choices`는 스태프도 쓰므로 건드리지 않음), 홈 타일 딕셔너리에 `lang` 키를 추가한다. ⑨ **아카이브 방문 필터 토큰은 언어 무관으로 고정한다(BIR 판정 Medium 결함, 설계 변경)**: 번역된 라벨을 `cat:<라벨>` 토큰으로 쓰면 영어에서 만든 URL이 한국어 전환 뒤 조용히 무시되고(푸터 `next`가 쿼리를 보존 [코드 templates/core/partials/_site_footer.html:63]) 개인 항목의 한국어 `팝업스토어`와 공식 칩이 영어에서 두 칩으로 갈라진다 [코드 web/views/archive.py:237-270, archive/queries.py:454-457 BIR 인용]. 토큰은 어휘의 한국어 원문 라벨(요청 언어와 무관한 `ko` 평가)로 고정하고 칩 표시 텍스트만 번역한다. 기존 북마크와 한국어 단언(`tests/archive/test_archive_visits_filter.py:122-147`)은 그대로 유지된다. ⑩ CSS는 기본 변경 0건이고 홈 카테고리 타일의 영어 "Exhibition"이 360px 경계라 브라우저 측정으로 넘침이 확인될 때만 `home.css` `@media (max-width: 64rem)`의 `.cat-name`에 `overflow-wrap: anywhere` 1줄을 추가한다(WED 추정, 측정 전).

## 3. Test List (코치 E-01~E-29 반영, 번호는 임시)

- **A 뷰**: E-01 검색 칩 3개 언어(`%` 포함 q 안전) / E-02 `month_label` ko·en / E-03 기본 메타 설명 3개 언어·말줄임 없음·JSON-LD 일치 / E-04 `web/views/events.py` AST 가드(번역 호출 밖 한국어 리터럴 0건).
- **B 목록·C 달력·D 상세**: h1/title / 월 칸·월 이름·선택일 제목 서식(ko 불변 + en) / 칩 aria-label / 개수 단수·복수 / `lang="ko"` 요소 단위 / 찜 aria-label / 오류 패널 / `source_name 제공` / 종료 행사 `title`. 요소 단위 등식 단언만 쓴다(부분 문자열 금지, 43-1 교훈).
- **E JS·서버**: 토글 버튼의 `data-label-open`·`data-label-close`가 번역된 텍스트와 같고 초기 텍스트와 일치.
- **가드**: 템플릿 가드에 파일 3개 추가(42→45 [계산]), JS 가드에 `pages/event_list.js` 추가(14→15 [계산]).
- **F 합격 테스트(도착 시 Green이므로 뮤테이션 필수)**: E-26 영어 장면의 `lang="ko"` 밖 한글 0건 / E-27 세 언어 msgid 집합 동일 / E-28 msgstr에 한글 0건 / E-29 msgstr의 추가 `"` 0건.

## 4. 슬라이스와 분업

1. 테스트 먼저(Backend & Integration Engineer, 테스트 파일만): 위 Test List를 새 파일 `tests/core/test_event_ui_translations.py`와 가드 파일에 쓴다. 오케스트레이터가 실행해 Red 이유가 "한국어 원문이 그대로 나옴"인지 확인한다.
2. 구현(병렬, 파일 분리): Backend & Integration Engineer = `web/views/events.py` + 기존 테스트 줄(§2-3 [실측 rg]). Frontend Implementation Engineer = `templates/core/events/*.html` + `event_list.js`(+ 측정 후 CSS). 컨텍스트 계약은 §2-2·3: 키 `category_labels`(slug→라벨 딕셔너리), `active_filter_chips` 항목 `{"label", "lang"}`.
3. 오케스트레이터가 `makemessages`를 한 번 실행하고 번역가(언어별 병렬)가 43-1 용어집으로 채운 뒤 `compilemessages --ignore .venv` → Green → 전체 회귀·e2e.
4. 브라우저 검증(오케스트레이터), WED·BIR 사후 판정, 독립 AI 검수(언어별), 검수 반영, 문서 갱신.

## 5. Frontend Review Evidence (사전)

- **깊이**: Standard. 문구·`lang`·서식 변경이며 새 비동기 상태·모달·sticky 구조는 없다. 필터 토글(서버·JS 공유 문구)과 카테고리 라벨 언어 일관성은 High 수준으로 본다(BIR).
- **WED 사양 요지**: 요소별 번역 방식 표, `lang="ko"` 대상 목록(제목·작품명·카테고리·장소·요약과 카테고리 `<label>`, 줄번호는 WED 보고서 인용 [코드 WED 보고, 오케스트레이터 대조]), 레이아웃 위험은 월 이동 줄만 높음이고 나머지는 낮음~중간.
- **BIR 기준 요지**: A 필터 토글(텍스트·`aria-expanded` 동기, 카탈로그 실패 시 혼합 없음), B 찜 이름은 상태와 무관하게 고정하고 `aria-pressed`만 상태 전달, C 혼합 언어 마크업, D 상태·칩·빈 상태·달력 서식, E 서버 문자열, F 상세 동작, G 가드 갱신.
- **브라우저 증거 계획**: 언어 en·ja·zh-hans × 페이지 3개 × 뷰포트 1280·500·360px에서 가로 넘침 0, 월 이동 줄·머리·결과 머리 박스 교차 0, `lang="ko"` 밖 한국어 텍스트 노드·속성 스캔 0건(허용: 브랜드, `<title>`·meta의 행사 제목), 콘솔 오류 0, 필터 토글 열기→닫기→열기, 언어 전환 후 쿼리·`month`·`date` 보존, 한국어 회귀는 main과 같은 픽스처의 가시 텍스트 비교.
- **사후 판정(2026-10-22)**: WED 전체 `Conforms`(사양 위반 0, Unverified 6건). BIR 전체 `Unverified`(Deviates 근거 0건, 소스로 확인한 A~F는 충족, G2 문서 갱신과 런타임 항목이 미확인). BIR 정정 1건을 채택했다 — 속성 안 번역이 이스케이프되지 않는다는 점(§2-11 정정).
- **오케스트레이터가 사후 판정 뒤에 닫은 증거** [실측]: 한국어 불변 — 익명 13개 URL과 임시 사용자 로그인 11개 URL(상태·찜 포함)에서 main과 보이는 텍스트·접근성 속성 DIFF 0(DB 행 번호 속성은 제외). 영·일·중 × 21종 × 360px 63프레임, × 9종 × 500·800·1280px 81프레임에서 `lang="ko"` 밖 한국어 0·가로 넘침 0·월 이동 줄 겹침 0. 필터 토글 Enter·Space 교대와 포커스 유지, 언어 전환 `next`가 필터·`month`·`date` 쿼리를 보존, 하단 고정 CTA가 영어·일본어 360px에서 한 줄 328×44px(바 높이 65px), 콘솔 0건.
- **끝내 확인하지 못한 항목(사용자 위험 수용 대상)**: 라이트 테마(이번 CSS 변경은 색이 아니라 레이아웃뿐 [코드 git diff]), 중국어 고정 CTA, `/jsi18n/` 차단 재현(`event_list.js`가 이제 `gettext`를 쓰지 않아 무관하나 코드로만 확인), 로그인 상태에서 해제 확인 모달·상태 패널의 영어·일본어·중국어 동작(JS 무변경 [코드], e2e는 한국어만), WebKit 정렬 메뉴(기존 한계).
- **QVL 결정**: §9에 기입.

## 6. 번역·검수

43-1 용어집·규칙(스크래치패드의 `i18n-glossary.md`, `i18n-translator-rules.md`)을 그대로 쓴다. 검수는 독립 AI 검수자가 언어별로 한다(사용자 지시 2026-10-21). 원어민 사람 검수는 없다.

**검수 결과(2026-10-22)** [실측 검수 JSON·패처 출력]: 새 msgid 56개를 번역가와 별개인 검수자 3명이 전부 읽었다. 영어 4건 중 3건, 일본어 2건 중 1건, 중국어 2건 중 2건을 구조 검증 패처로 반영했고 거부는 0건이다. 미반영은 영어 `참여 상태`(low 확신, 원문 모호)와 일본어 고정 번역 note이며, 후자는 오케스트레이터가 테스트와 카탈로그를 함께 `検索結果 N件`으로 직접 고쳤다.

## 7. 정정 기록 (오케스트레이터 브리프 오류, 검토자가 적발)

- 브리프의 "한국어 리터럴 4개"는 3자리·상수 조각 4개였다(551행은 이어 붙인 문자열 하나, 500행은 f-string 조각 둘) [실측 AST].
- 브리프의 "`event_list.js` 한글 문자열 1개"는 8행 한 줄에 2개였다 [코드].
- 브리프의 "`cta_visibility.js`는 상세의 로그인 CTA"는 틀렸다. 하단 고정 CTA 바를 보이고 숨기는 스크립트이고 한국어 문자열이 없다 [코드 static/js/shared/cta_visibility.js:1-12]. 상세의 상태 패널 토글은 `status.js:472-486`이 처리하고 상세는 `event_list.js`를 로드하지 않는다 [실측 rg].

## 8. 사용자 결정 (2026-10-22 완료: "카테고리도 번역 대상임" — §2-14로 구현)

초기 질문은 다음과 같았다 — 카테고리 이름(팝업스토어 등 `CATEGORY` 상수 값, `core/vocab.py:21-29` [코드])을 번역할지. 기본값은 §2-2의 한국어 + `lang="ko"`다. 번역하려면 `CATEGORY` 값을 지연 번역으로 바꾸는 코드 변경이 필요하고, 필터 패널의 체크박스 라벨은 DB `Category.label`이라 번역에서 빠져 같은 화면에 두 언어가 남는다.

## 9. 완료 평가 (QVL, 2026-10-22)

- **QVL 판정**: 조건부 완료. 조건 C1 WED 사후 `Conforms` 충족, C3 새 msgid 검수 반영·기록 충족, C4 상세 연관 행사 섹션 증거 충족(영어 누수 스캔 장면과 `lang="ko"` 요소 단위 테스트 추가, 브라우저 63프레임이 연관 행사가 있는 상세 3종을 포함), C5 로그인 상태 한국어 불변 충족(임시 사용자 11개 URL에서 main과 차이 0 [실측]). **C2 BIR 사후는 전체 `Unverified`**(Deviates 근거 0건)라 Frontend Dual Review Gate 4항에 따라 사용자가 잔여 위험을 명시적으로 수용해야 완료로 표시할 수 있다.
- **QVL 지적으로 추가한 것**: 연관 행사 장면(E-26 `detail_related`, 이 장면이 처음에 Red를 냈다 — 메타 설명이 `카테고리 라벨 · 장소 · 기간`을 잇는 것은 콘텐츠라 `<title>`·`<meta content>` 위치에 한해 허용), `query_failed` 오류 패널(ko·en), `source_name` HTML 이스케이프, 테스트 파일 분리(800줄 상한). 새 테스트 5개의 변이는 전부 Red였다 [실측 mutate_43_2.py].
- **최종 자동 검증** [실측 2026-10-22]: `uv run pytest -q` 3348 passed / 10 deselected / 99.97초(기준선 3254, +94 [계산]), e2e 10 passed, `manage.py check` 0건, `makemigrations --check --dry-run` 변경 없음.
- **사용자 위험 수용 대상(BIR Unverified)**: 라이트 테마, 중국어 하단 고정 CTA, `/jsi18n/` 차단 재현(토글은 서버 렌더라 무관 [코드]), 로그인 상태 해제 확인 모달·상태 패널의 영어·일본어·중국어 동작(JS 무변경 [코드], 43-1에서 일본어 확인 모달 확인), WebKit 정렬 메뉴(기존 한계).
- **사용자 결정 반영(2026-10-22 "카테고리도 번역 대상임", §2-14·§2-15)**: 같은 PR에서 구현했다. 사전 검토 WED(Standard)·BIR·코치 → 테스트 먼저(구현 전 Red 70개 [실측 pytest]) → 구현 → 번역 4개 msgid → 독립 AI 검수(ja·zh 제안 0건, en 1건 low 미반영) → 사후 판정 WED `Conforms`, BIR `Unverified`(Deviates 0건, 새 결함 1건=백업 파일 3개를 삭제함), QVL 조건부 완료. QVL 지적 G1·G3·G2는 홈 범례·스냅샷·아카이브 행 `lang` 테스트와 JSON-LD 단언 테스트, 변이 6개로 닫았다.
- **증분 최종 검증** [실측 2026-10-22]: `uv run pytest -q` 3418 passed / 10 deselected / 104.71초(기준선 3254, +164 [계산 3418−3254]), e2e 10 passed, `manage.py check` 0건, 마이그레이션 변경 없음. 한국어 불변 재측정(카테고리 번역 이후): 익명 15개 URL(홈 포함)과 로그인 16개 URL(아카이브 방문·방문 상태·찜·카테고리 필터 포함)에서 main과 보이는 텍스트·접근성 속성 차이 0. 변이는 누적 31개(16+9+6 [계산])가 전부 Red였다.
- **브라우저(카테고리)** [실측 Chrome DevTools]: 영·일·중에서 홈·목록·달력·상세의 카테고리 이름 번역, `lang="ko"` 요소 중 한글 없는 것 0건, 홈 타일(폭 75px·320px에서 65px)에 번역 라벨 21개와 한국어 7개를 넣어 넘침 0(CSS 변경 0건), 스태프 화면은 영어 요청에서도 `<html lang="ko">`와 한국어 카테고리, 아카이브 방문 필터 토큰이 4개 언어에서 `cat:팝업스토어`로 같음.
- **코치 Test List C-00~C-16 대응**: C-01 적용 칩 문자열 리스트, C-02~C-04·C-06·C-08~C-10 번역·`lang` 단언, C-05 한국어 파라미터(명시적 `lang` 속성 없음), C-07 `category_labels` 영어 렌더, C-11 메타 설명, C-12·C-13 아카이브 칩, C-14 스태프 한국어, C-15 누수 스캔 장면 2개, C-16 카탈로그 가드 E-27~29(새 msgid 4개 포함).
- **사용자 결정·위험 수용 대상**: ① 영어 `Collab cafe`(칩)와 `Collab café`(메타 설명·용어집) 표기 통일(low 확신, 43-1 칩·메타 설명·테스트를 함께 바꿔야 함) ② 아카이브 페이지는 43-3 전까지 한국어 UI에 번역된 카테고리 이름이 섞인다(deploy를 43-3 뒤로 미룰지 수용할지) ③ BIR `Unverified`(라이트 테마, 중국어 고정 CTA, `/jsi18n/` 차단 재현, 로그인 상태 비-ko 모달) ④ 개인 항목 제안 칩(`PERSONAL_ENTRY_CATEGORY_SUGGESTIONS`)은 저장값이라 번역하지 않는다(43-3 계획에 명시).

---

