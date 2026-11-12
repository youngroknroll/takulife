# 트랙 43: UI 다국어(ko/en/ja/zh-hans) 지원 (2026-10-21) [v1 — **사용자 범위 승인 완료(2026-10-21)**: 중국어 간체만 / 번역문은 이 세션이 작성하되 일본어·중국어는 검수 후 정식 노출 / 법률 문서 제외 / 쿠키 기반 확정 / 트랙 분할 승인. PSO·DAR·WED·DOR·BIR·SRR 사전 검토 통합(§11~§13). 코치 Test List(§14)는 코치 출력 도착 후 추가, QVL 매트릭스는 구현 후]

> **출처**: 사용자 요청(2026-10-21) "웹서비스를 한국어/영어/일본어/중국어를 지원하게 하고 싶어."
> **기준선**: main `07b7186e`, 회귀 3212 passed / 10 deselected [실측 2026-10-21, 트랙 42 후속 절]. 워킹트리에 `prompt_plan.md` 수정분과 `.DS_Store`만 있음 [실측 git status].
> **오케스트레이터 재확인**: 아래 4역할 인용 수치·file:line은 전부 오케스트레이터가 소스로 재확인했다(rg·sed·AST 스크립트). 틀렸던 1차 판단 2건은 §9에 기록.

## 1. 제품 결정 (PSO, 오케스트레이터 재확인)

- **가치 정의**: "한국어를 읽지 못하는 서브컬처 팬이 앱을 조작해 개인 굿즈 컬렉션을 기록·관리할 수 있게 한다." 콘텐츠(행사 제목·요약·장소, 사용자 입력)는 원문 그대로이고 UI 문구(버튼·라벨·안내·오류)만 번역한다. 행사 콘텐츠는 트랙 33 규칙("제목·본문에 한글 없으면 제외", `prompt_plan.md` 트랙 33 절)으로 한국 국내 행사만이며 기계번역은 비용 정책(LLM API·유료 API 불허, 메모리 `cost-constraint`)으로 불가.
- **북극성 연결**: 월간 컬렉션 기여 사용자의 활성화·축적 단계를 비한국어 사용자에게 연다. 발견(3순위) 가치는 늘지 않는다.
- **지원 언어**: ko(원문)·en·ja·zh. 중국어 변종은 §8 결정 1.

## 2. 현재 상태와 규모 [실측 2026-10-21]

- i18n 기반 없음: `config/settings.py:400-403` `LANGUAGE_CODE="ko-kr"`·`USE_I18N=True`뿐, `LANGUAGES`·`LOCALE_PATHS` 없음, `MIDDLEWARE`(325-341행)에 `LocaleMiddleware` 없음, `TEMPLATES` context_processors(351-365행)에 `i18n` 없음, `templates/` 90개 html 파일 중 `{% load i18n %}` 0파일, `locale/` 디렉터리 없음, 운영 파이썬에 `gettext` 호출 0건 [실측 rg]. `templates/base.html:2`·`templates/staff/base_staff.html:2` `<html lang="ko">` 고정 [코드].
- Django 5.2.17 [실측 `uv run python -c`]. allauth 번들 로케일에 ko·en·ja·zh_Hans·zh_Hant `.po`+`.mo` 있음 [실측 ls] — allauth 자체 문구는 추가 작업 없이 번역된다.
- 한글 UI 문자열 규모(상한 추정, 로그·내부 사유 포함) [실측 2026-10-21, 스크립트 `scratchpad/count_ko_by_pkg.py`·`count_js_ko.py`, rg 합산]:
  - 템플릿 한글 포함 줄: 소비자(비스태프·비법률) 1,557줄 / 스태프 426줄 / 법률 106줄(파일 2개 257줄). allauth 오버라이드 23파일(html 19 + 이메일 txt 4).
  - 파이썬 한글 문자열 리터럴(독스트링·테스트·마이그레이션·local_runner 제외): 551개 / 48파일 — staff 150 / archive 104 / drafts 65 / web 64 / core 60 / events 관리명령 34 / accounts 27 / drafts 관리명령 17 / events 12 / core 관리명령 8 / config 6 / accounts 관리명령 4.
  - JS 한글 문자열 리터럴(주석 제외): 소비자 144개 / 16파일, 스태프 75개 / 5파일. 변수 결합 문구 있음(`static/js/pages/visit_edit.js:173`).
  - 테스트: 한글 포함 247파일, 리터럴 URL 호출 532건·`reverse()` 70건 [실측 rg] — URL 접두사 방식을 기각하는 근거 중 하나.
- 폰트: Pretendard dynamic-subset `unicode-range` 선언 93개 중 가나·CJK 통합 한자 전체 범위를 담은 항목 0개, 개별 코드포인트만 희소하게 포함 [실측 rg, WED 재확인]. 일본어·중국어는 글리프 단위로 시스템 폰트 폴백.

## 3. 승인 범위 / 명시적 제외

**포함(1차)**: 공개 셸(헤더·푸터·내비·404/429/500), 홈, 이벤트 목록·달력·상세의 UI 문구, 계정(allauth 오버라이드 19 html + 이메일 4 txt [실측 find] — 발송 언어 전달 경로 포함), 컬렉션 CRUD·필터·등록, 활동(방문·관심·달력), 마이페이지, 위 표면의 파이썬 사용자 노출 메시지(archive·web·events·accounts·core)와 소비자 JS 16파일 [실측], `core/vocab.py` 상수 라벨(REGION·ARCHIVE_STATUS·COLLECTION_ITEM_TYPE 등), `<title>`·description·og 메타, `<html lang>` 동적화.

**제외**: 스태프 콘솔 전체(항상 한국어, §4-5), Django admin(자체 번역), 법률 문서 2파일 [실측 ls](법적 판본 우선 문제 — §8 결정 3), 콘텐츠 기계번역, DB 카테고리 라벨 `core.models.Category.label`(데이터 취급, 한국어 노출 — DAR 이연 §7), 닉네임 허용 문자(`accounts/validators.py:9`, 별도 트랙), 관리명령 출력·`drafts/` 운영 메시지·`local_runner/`, 알림 메일 신설(백로그 H8).

## 4. 구조 결정 (DAR, 오케스트레이터 재확인)

1. **Django 표준 gettext**: `LANGUAGES`(4개 [코드 결정]), `LOCALE_PATHS=[BASE_DIR/"locale"]`, `LANGUAGE_CODE`는 `"ko"`로 정리(`ko-kr`→`ko`, `<html lang="ko">` 현행 유지), `LocaleMiddleware`를 `SessionMiddleware`(332행) 뒤·`CommonMiddleware`(333행) 앞에 [코드], `django.template.context_processors.i18n` 추가. 새 앱·래퍼 모듈·모델 번역 프레임워크 없음.
2. **언어 결정 = 쿠키 기반, URL 접두사 없음**: `path("i18n/", include("django.conf.urls.i18n"))`로 `set_language`(`/i18n/setlang/`). 쿠키 → `Accept-Language` → `ko`. `i18n_patterns`를 `prefix_default_language=False`로 쓰면 접두사 없는 `/api/` 요청이 LANGUAGE_CODE로 강제돼(`django/middleware/locale.py:28-33` [코드]) 외국어 페이지의 fetch 오류가 한국어로 오고, `True`로 쓰면 한국어 URL 전체가 바뀐다 — 두 경우 모두 기각. 쿠키 방식에서는 이 강제 분기가 발동하지 않는다(DAR 정정: v1의 잔존 위험이 아니라 대안 기각 근거). 외국어 SEO·hreflang은 §7 이연.
3. **번역 호출 자리**: 메시지 리터럴이 지금 적힌 자리에서 그대로 감싼다 — `core/vocab.py` 상수는 값 자리에만 `gettext_lazy`(slug 키 불변, "매직 없음" 원칙 유지), 서비스 `ValidationError` 리터럴(`archive/services.py:105,333-337,374-375` [코드])은 `gettext_lazy`, 뷰 조립 리터럴(`archive/views.py:318,324` [코드])은 `gettext`. 메시지를 한 층으로 끌어모으는 재배치 금지. 경계 가드 R1과 무관(프레임워크 임포트).
4. **JS = `JavaScriptCatalog`**(`/jsi18n/`): `templates/base.html`에 `<script defer src="{% url 'javascript-catalog' %}">` 1줄을 페이지 스크립트보다 앞에, JS는 `gettext()`/`interpolate()`, `makemessages -d djangojs`로 자동 추출. 소비자 144개/16파일 [실측] 규모와 변수 결합 문구 때문에 페이지별 `json_script` 주입은 기각(DAR 1차 판단을 실측으로 뒤집음). 카탈로그 응답 캐싱은 §7 이연.
5. **스태프 항상 한국어**: `staff/permissions.py:9 staff_console_required`의 `_wrapped` 안에서 `with translation.override("ko"): return view_func(...)`. 스태프 뷰는 `return render(` 23건·`TemplateResponse` 0건이라 렌더가 override 안에서 끝난다 [실측 rg]. `superuser_console_required`는 이를 합성하므로 삽입 지점 1곳.
6. **DB 카테고리 라벨**: 데이터로 취급해 번역하지 않는다. `{% translate category.label %}` 런타임 조회는 가변 DB 값의 번역 책임을 배포 산출물(.po)로 역전시켜 기각.

## 5. 경험 사양 (WED, High 깊이 — 전 페이지 셸 변경)

- 전환기 위치: `templates/core/partials/_site_footer.html` `.site-footer-base-inner`(54행 [코드]) 안, `.footer-legal` 앞. 로그인·비로그인 동일, 계정 메뉴·설정 페이지에 중복 전환기 없음. `.footer-cols` 4열 고정(사용자 확정, `static/css/components/site-chrome.css:274-277`·`358-360` [코드])은 손대지 않는다.
- 마크업: `<form method="post" action="{% url 'set_language' %}" aria-label="…">` + csrf + hidden `next`(`request.get_full_path`) + `<select name="language">`(자기 표기 한국어/English/日本語/中文, 현재 언어 `selected`, 명시 `<label>`) + 제출 버튼. 새 CSS 클래스 없이 전역 폼 스타일 상속, 47.5rem 이하 기존 세로 쌓임 분기 재사용 [코드 site-chrome.css:361-378].
- 전환 후: 같은 페이지 복귀, 토스트 없음(전체 리로드가 피드백).
- 혼합 언어: 행사 제목·요약·장소·카테고리·지역 라벨 블록에 `lang="ko"`(적용 지점: `templates/core/events/detail.html:32,59,64,69,134,151,170`, `templates/core/home.html:45,75,127` [코드, 구현 시 재확인]). "원문 한국어" 안내 문구는 넣지 않는다.
- 날짜·시간: KST 표기 없음. 숫자 명시 서식(`Y/m/d`, `n.d` 등)은 언어와 무관하게 유지한다. **정정(2026-10-21, §13)**: 한국어 리터럴이 서식 문자열로 박힌 곳(홈 달력의 `Y년 n월 j일 l`·`n월 j일`·월 라벨 `{{ month }}월`)은 외국어 화면에 한국어가 섞이므로 Django 로케일 서식(`DATE_FORMAT`·`MONTH_DAY_FORMAT`·`F`)으로 바꾼다.
- 폰트: `static/css/base.css:34` [코드] 스택 끝에 OS CJK 폰트 추가(`"Hiragino Sans", "Yu Gothic", "Noto Sans JP", "PingFang SC", "Microsoft YaHei", "Noto Sans SC"`). CJK 웹폰트 자체 호스팅 보류.
- 메타: `<title>`·description·og 문구 번역, `<html lang="{{ LANGUAGE_CODE }}">`. 링크 미리보기 봇은 쿠키가 없어 항상 한국어 미리보기(인지 사항).
- 트랙 순서: 셸(전환기 포함)이 예외 없이 완결돼야 복구 경로가 생긴다. 중간 상태(일부 표면만 번역)는 허용.

## 6. 빌드·배포·CI (DOR, 오케스트레이터 재확인)

- `.mo`는 **Dockerfile builder 단계**에서 생성: `COPY . .` 뒤 `apt-get install gettext` + `uv run django-admin compilemessages`(settings 미로드 — `compilemessages.py:85-89`는 `DJANGO_SETTINGS_MODULE` 없으면 `./locale`만 본다 [코드]). `COPY --from=builder /app /app`(40행 [코드])로 자동 전달, 런타임 이미지 크기 증가 0바이트 [계산]. `.mo`는 미커밋(`.gitignore`에 `locale/**/*.mo`), `.po`만 커밋.
- CI `test` 잡(ubuntu-latest, Docker 미사용)에 `apt-get install -y gettext` + `compilemessages` 스텝 — 없으면 번역 단언 테스트가 거짓 통과/실패. `docker` 잡의 컴파일과는 목적이 달라 중복 유지.
- 설정 공백: `LANGUAGE_COOKIE_SECURE = _secure_cookies`(기본 False, `global_settings.py:168` [코드])를 `config/settings.py:541-542` [코드] 옆에, `LANGUAGE_COOKIE_SAMESITE="Lax"`.
- `Vary: Accept-Language`가 동적 응답 전부에 붙는다(`locale.py` process_response). 저장소에 `cache_page`·`CACHE_MIDDLEWARE` 0건 [실측 rg], whitenoise 정적 응답은 LocaleMiddleware를 안 거침 — 실질 영향 없음.
- 롤백: settings의 i18n diff(미들웨어·LANGUAGES·LOCALE_PATHS·context processor·LANGUAGE_CODE)를 **한 커밋**으로 revert. 부분 revert는 `<html lang="ko-kr">` 회귀. 마이그레이션 없음, `.po` 잔존 무해.
- 런북: `docs/deploy-runbook.md` §3 머릿글 "14개 항목"은 실측 17개와 이미 불일치 [실측 rg 번호 항목] — i18n 항목 추가 시 같은 수정에서 "18"로 정정. 신규 항목: `curl -H "Accept-Language: en"` → `<html lang="en">`, `Vary` 확인, `/i18n/setlang/` 쿠키 `Secure` 확인. §5에 롤백 한 줄. README §10 로컬 실행에 gettext 사전 조건(macOS `brew install gettext`, Linux `apt-get install gettext`).

## 7. 트랙 분할·파일·이연

- **43-1 기반+셸+홈+계정**(PR 1개): settings/urls/Dockerfile/ci.yml/.gitignore, `templates/base.html`·partials(헤더·푸터·토프바)·404/429/500·`templates/core/home.html`+홈 partials·`templates/account/`·`templates/socialaccount/`, `accounts/`·`web/views/account.py`·`web/views/home*` 메시지, `static/js/shared/`·`home_hero_rotator.js`, `staff/permissions.py` ko 고정, `core/vocab.py`, `static/css/base.css` 폰트 스택, 런북·README. 계약 테스트: LANGUAGES 4개 [코드 결정]·미들웨어 위치·LOCALE_PATHS·쿠키 플래그, `set_language` 왕복(`<html lang>` 변경), 미지원 코드 무시, 지원 언어 각각 홈 200 + 번역 문구 1개씩, `/jsi18n/` 200, 스태프 화면 ko 고정, 미번역 msgid 0건 가드(.po 파싱, 승인 범위 템플릿·파이썬·JS 자리 전부 스캔).
- **43-2 이벤트**(PR 1개): `templates/core/events/`·관련 partials, `web/views/events.py`·`events/` 메시지, `event_list.js`, 콘텐츠 블록 `lang="ko"`.
- **43-3 컬렉션·활동·마이페이지**(PR 1개): `templates/core/archive/`·`collection/`·`mypage`, `archive/views.py`(104 리터럴 포함 [실측 AST])·`archive/services.py`·`archive/serializers.py`·`web/views/{collection,archive,activity}.py`, `static/js/pages/` 나머지.
- **[2026-10-22 사용자 결정] 43-3에 포함 — 개인 항목 카테고리 제안 칩 번역**: `PERSONAL_ENTRY_CATEGORY_SUGGESTIONS`(`core/vocab.py`, 칩이 입력창을 채우는 값 [코드 templates/core/archive/personal_create.html:70])도 요청 언어로 보인다. 저장값이 언어마다 갈라지면 아카이브 필터 토큰(가드레일 20)이 깨지므로 설계 기본값은 **서버 경계 정규화**다 — 저장 시 입력이 어느 지원 언어의 제안 칩 번역과 같으면(대소문자 무시) 한국어 원문으로 바꿔 저장하고, 표시 때 요청 언어로 번역한다. 정규화 규칙과 기존 저장값(한국어) 호환은 43-3 사전 검토(DAR·BIR)에서 확정한다.
- 트랙마다 착수 시 `makemessages`로 msgid 수를 실측해 번역량을 다시 잰다(위 §2 수치는 상한).
- 같은 유형 소규모 결함(보고 후 같은 트랙에서 수정, 메모리 `no-backlog-deferral-feedback`): `archive/views.py:318` 영어 리터럴 `"User event status already exists for this event."`(같은 함수의 324행은 한글 [코드]) — 43-3에서 한국어 원문으로 통일 후 번역.
- **이연(트리거 명시)**: URL 접두사+hreflang+언어별 sitemap(트리거: 외국어 유입 수요 실측 또는 SEO 목표 명시) / [2026-10-22 사용자 결정으로 이연 해제 — 트랙 44-4가 맡는다] `Category.label` 다국어 / JS 카탈로그 응답 캐싱(트리거: `/jsi18n/` 응답 시간 실측 후) / `msgfmt --statistics` CI 게이트(기준치 합의 후) / 닉네임 허용 문자 확장 / 법률 문서 번역 / zh-hant(결정 1에 따라) / 전체 페이지 캐시 도입 시 `Vary: Accept-Language` 재검토.

## 8. 사용자 결정 (2026-10-21 승인 완료)

1. 중국어: **간체(`zh-hans`)만**. 번체는 이연(트리거: 번체 수요 확인).
2. 번역문 생산: **이 세션이 `.po` 작성**. 영어는 그대로 신뢰, 일본어·중국어는 PSO 품질 게이트 — 검수 시트(msgid↔ja↔zh 대조표)를 사용자에게 드리고 **사용자 확인 전에는 43-1의 production 반영(deploy PR 머지)을 하지 않는다**. 코드에 언어별 노출 스위치는 두지 않는다(과잉 설계, 릴리스 게이트로 충분).
3. 법률 문서: **1차 완전 제외**.
4. 언어 결정 방식: **쿠키 기반 확정**(URL 접두사 없음).
5. 트랙 분할 §7 승인: 43-1 → 43-2 → 43-3, PR 각 1개.

## 9. 1차 판단 정정 기록

- 1차 판단 §4-2(a)는 "`/api/` 강제 ko"를 쿠키 방식의 선택 이유로 썼으나 이는 `i18n_patterns` 사용 시에만 발동한다 — 대안 기각 근거로만 쓴다(DAR 정정, `locale.py:28-33` [코드] 재확인).
- 1차 판단 §4-1 JS 접근은 DAR 1차 답변에서 `json_script`로 바뀌었다가, 오케스트레이터 실측(소비자 JS 리터럴 144개/16파일 [실측])으로 `JavaScriptCatalog`로 재확정(DAR 2차 답변). 측정이 판단보다 먼저다.
- 1차 판단 §1 폰트 설명 "청크 범위 밖이면 폴백"은 부정확 — 가나·한자 전체 범위 선언이 0개라 "커버 집합 자체가 없다"가 정확(WED 재확인, 오케스트레이터 rg 재확인).

## 10. 역할

- Activated(사전 검토 완료): Product Scope Owner(범위·AC) / Domain Architecture Reviewer(gettext 배치·쿠키 방식·JS·스태프 ko) / Web Experience Designer(전환기·혼합 언어·폰트) / Deployment & Operations Reviewer(빌드·CI·롤백·런북).
- Activated(승인 후 v1에서): Backend TDD Coach(계약 테스트 Test List, 코치 계약부터) / Browser Interaction Reviewer(전환 폼 포커스·키보드·`defer` 로드 순서) / Security & Resilience Reviewer(`set_language` `next` 검증·쿠키 플래그·CSRF) / Quality Verification Lead(AC→증거 매트릭스) / Backend & Integration Engineer / Frontend Implementation Engineer.
- Not Activated: AI Automation Architect(LLM 범위 없음, 기계번역 불허).

## 11. Frontend Review Evidence (43-1)

- **깊이**: High — 전 페이지 공유 셸·교차 페이지 패턴(AGENTS.md Frontend Dual Review Gate).
- **WED 사전 사양**: §5 (2026-10-21 산출, 오케스트레이터가 푸터 마크업·4열 규칙·폰트 스택을 소스로 재확인 [실측 sed]).
- **BIR 사전 기준** (2026-10-21 산출, 오케스트레이터가 api.js·confirm-modal.js·hero rotator·base.html 줄을 소스로 재확인 [실측 sed·rg]):
  1. 스크립트 순서: `static/js/shared/i18n_fallback.js`(신규, `gettext`·`ngettext`·`interpolate`가 없을 때만 항등 폴백 정의)를 `error_report.js`보다 앞에, 그 바로 뒤에 `javascript-catalog` 스크립트를 둔다(전부 `defer`, 문서 순서 실행, 카탈로그가 폴백을 덮어쓴다). 이유: `status.js`가 모듈 최상위에서 한국어 문구 객체를 만든다 [코드 status.js:39-52].
  2. 인증 403 분류(`static/js/shared/api.js:14-17,88-96`): 문구 매칭 `AUTH_DETAIL_MARKERS`를 제거하고 `data.code === "not_authenticated"`로 판별한다. 서버 코드 필드는 §14 시나리오 M. 같은 유형의 문구 매칭은 저장소에서 api.js 한 파일뿐이다 [실측 rg `\.detail` — BIR].
  3. `static/js/components/confirm-modal.js`(66·71행 "아니오"/"예", `base.html:125`에서 전 페이지 로드)를 43-1 파일에 편입한다.
  4. `static/js/pages/home_hero_rotator.js`의 접합 `aria-label`(109·112행)은 `interpolate(gettext("…%(n)s…"), {n: …}, true)`로 바꾼다.
  5. 전환 폼에 `data-submit-guard`(규칙 `docs/FE/loading-feedback.md:33`, 선례 `_topbar.html:39`).
  6. 전환 후 스크롤: 폼 `id="language-switcher"`, hidden `next` = `request.get_full_path` + `#language-switcher`. 푸터에서 제출하므로 리로드 후 맨 위로 튀지 않고 전환 결과가 보이는 푸터로 돌아온다. WED·BIR이 정하지 않은 공백을 오케스트레이터가 정했으며 사후 verdict에서 확인한다.
  7. 입력 중 폼 페이지에서 전환 시 입력값 유실은 기존 링크 클릭과 같은 위험이라 수용한다(정보).
  8. 사용자 노출 리터럴 전수 래핑, DOM에는 `textContent`만 쓴다(`innerHTML` 금지 — SRR이 43-1 범위에서 0건 확인).
  9. 브라우저 측정 체크리스트: 4개 언어 × (데스크톱, 45rem 이하) × (라이트, 다크), 콘솔 오류 0건, 전환 왕복, 세션 만료 시 로그인 안내 모달, 확인창 버튼 번역, 푸터 4열 유지(47.5rem 이하 포함), CJK 글리프 깨짐 없음.
- **사후 verdict (2026-10-21)** — 리뷰어가 소스와 캡처 5장을 직접 열어 재확인한 판정이다 [실측 리뷰 출력]:
  - Web Experience Designer: **`Deviates`**. 단일 사유는 홈 달력의 날짜 서식을 언어별 서식으로 바꾼 것이 사전 사양("언어별 날짜 서식 적용 안 함")과 어긋나는데 계획서에 기록이 없었다는 점이다. 코드 자체는 합리적(한국어 리터럴이 외국어 화면에 섞이는 결함 수정)이라고 평가했고, 처리는 사양 정정을 §5·§13에 기록하는 것으로 했다. 사용자가 원치 않으면 중립 숫자 서식으로 되돌릴 수 있다. 나머지 항목(전환기 위치·앵커·`lang="ko"`·폰트·메타)은 `Conforms`. 정보: 푸터 select·버튼이 브라우저 기본 모양(사전 사양이 가정한 "전역 폼 스타일"이 저장소에 없었음), 사양의 "명시 `<label>`"과 "새 CSS 없음"이 양립 불가였음, 일본어 푸터 줄바꿈, 홈 컬렉션 요약의 혼합 출처 제목에는 `lang="ko"` 미적용(사용자 입력이 섞여 의도적).
  - Browser Interaction Reviewer: **`Conforms`**. 사전 기준 9항 전부를 소스·테스트·캡처로 재확인했다. Low 2건: 폼·select의 aria-label 중복(WED 사양이 둘 다 요구해 유지), 카탈로그 로드 실패 경로는 코드상 안전하나 브라우저 재현 증거 없음(Unverified).
  - Quality Verification Lead 완료 결정은 §15에 기록한다.

## 12. 보안·운영 조건 (SRR·DOR 통합)

- `LANGUAGE_COOKIE_HTTPONLY = True`: JS가 `django_language`를 읽지 않는다 [실측 rg static/js 0건 — SRR]. `LANGUAGE_COOKIE_SECURE`는 `_secure_cookies`, `LANGUAGE_COOKIE_SAMESITE`는 `"Lax"`. 세션·CSRF 쿠키는 SAMESITE를 명시하지 않고 Django 기본값을 쓴다 [실측 rg `SAMESITE` config/settings.py 0건].
- 404·429·500은 모두 `base.html`을 상속한다 [실측 rg extends]. 500은 컨텍스트 프로세서가 돌지 않으므로 `<html lang>`은 `{{ LANGUAGE_CODE }}` 변수가 아니라 `{% get_current_language as LANGUAGE_CODE %}` 태그로 얻는다. 세 템플릿에는 변수 보간 `blocktranslate`를 쓰지 않는다(번역이 500을 다시 500으로 만드는 경로 차단).
- 플레이스홀더 가드: `msgfmt --check-format`은 python-format 불일치는 잡지만(종료 코드 1) javascript-format 불일치는 놓친다(종료 코드 0) [실측 scratchpad/msgfmt-probe]. 그래서 msgid와 msgstr의 `%(name)s`·`%s` 토큰 집합 일치를 django·djangojs 두 도메인 모두에서 검사하는 결정적 테스트를 둔다(§14).
- 추가 계약 핀(SRR): `set_language`의 악성 `next`(외부 도메인·`javascript:`)가 항상 같은 호스트 또는 `/`로 가는 것, 스태프 뷰 예외 직후 다음 요청의 언어가 정상인 것, 쿠키가 ko 외 언어여도 오류 페이지가 렌더되는 것, `django_language` 쿠키에 `HttpOnly` 포함.
- 로거 AST 가드(`tests/core/test_error_logging_policy.py`)는 이미 로거 첫 인자의 `gettext`를 막는다 [코드 SRR 확인] — 43-1 변경 후 통과만 확인한다.
- 공유 부분 템플릿 `_pager.html`·`_calendar_grid.html` 등은 스태프 화면도 include한다 [실측 rg `_pager|_calendar_grid`: staff/accounts/list.html·staff/events/list.html 포함] — 스태프 한국어 고정(§4-5)이 이 때문에 필수다.
- 이연(SRR): 오류 묶음 `message_sample`이 요청자 언어로 번갈아 바뀌는 가독성 문제(트리거: 대시보드 혼재 보고), 스태프 대리 발송 기능이 생길 때 발신 언어 재검토, JS 카탈로그 캐싱 시 캐시 키에 언어 포함.

## 13. 정정 기록 (v0 → v1)

- §7의 `web/views/home*`는 존재하지 않는다 — 홈 뷰는 `web/views/events.py:168 home`이다 [실측 rg]. 43-1은 그 파일에서 홈 관련 문자열만 감싼다.
- WED의 `lang="ko"`(`region_label`, detail.html:64)와 §3의 `core/vocab.py` 번역이 충돌했다. REGION 8종 라벨은 지역 필터 어휘라 번역한다(서울→Seoul 등). `lang="ko"`는 행사 제목·요약·장소명·카테고리 라벨에만 붙이고 `region_label`에는 붙이지 않는다. 43-2 구현 때 detail.html:64에 적용하지 않는다.
- BIR이 제안한 403 판별 수단(본문 `code` 필드, `WWW-Authenticate` 헤더)은 이 프로젝트의 DRF 설정에서 성립하지 않는다 [코드 rest_framework/views.py:94-100, authentication.py:44-50]. 서버가 `code`를 싣는 시나리오 M을 추가했다.
- 43-1 파일 목록 보강: `static/js/shared/i18n_fallback.js`(신규), `static/js/components/confirm-modal.js`, `core/` 예외 핸들러 모듈(신규, 시나리오 M).
- BIR: `static/js/shared/`의 한글 217줄은 대부분 주석이다. 사용자 노출 리터럴은 `api.js`·`status.js` 중심이며, 작업량은 JS 문자열 리터럴 기준(소비자 144개 / 16파일 [실측])으로 본다.
- SRR 전제 정정: 스태프의 타인 대상 메일 발송 경로와 오류 지문의 언어 분기는 코드에 없다 [실측 rg — SRR].
- **스태프 셸도 공용 JS를 로드한다**: `templates/staff/base_staff.html:87-88`이 `api.js`·`confirm-modal.js`를 로드한다 [실측 rg `shared/api.js` templates/]. 이 두 파일이 `gettext`를 쓰게 되면 폴백·카탈로그가 없는 스태프 화면에서 ReferenceError가 난다. 스태프는 항상 한국어이므로 카탈로그는 넣지 않고 `i18n_fallback.js`(항등 폴백)만 `base_staff.html`에 로드한다. 공용 JS를 로드하는 템플릿은 `base.html`과 `base_staff.html` 둘뿐이다 [실측 rg -l]. 이 결함은 BIR·WED·DOR 사전 검토 어디에서도 나오지 않았고 JS 작업 결과를 `rg`로 소비처까지 추적하다 발견했다.
- 코치 정정: 설정 계약 테스트 `tests/core/test_settings_env.py`는 코치가 말한 309줄이 아니라 639줄이다 [실측 wc -l]. 설정 핀(I18N-1~6)은 새 파일 `tests/core/test_i18n_settings.py`에 둔다.
- DOR 전제 정정: `compilemessages`는 `./locale`만 처리하지 않고 현재 디렉터리 전체를 `os.walk`로 순회해 이름이 `locale`인 폴더를 전부 수집한다(`compilemessages.py:85-100` [코드]). 설정 모듈을 줘도 순회는 무조건 일어난다. 설정 없이 한 번 실행하자 `.venv`의 서드파티 `.po` 1280개를 다시 컴파일했다 [실측 로그 1282줄]. 그 검증 실행이 로컬 `.venv`의 서드파티 `.mo` 1280개를 다시 쓰는 부작용을 냈다 [실측 find -mmin]. 명령에 `--ignore .venv`를 붙였고(Dockerfile·CI·README), 붙이면 `.venv` 안 `.mo`가 하나도 바뀌지 않는다 [실측 타임스탬프 기준 파일 `find -newer` 0건].
- 코치 정정: I18N-11의 `xx` 설계는 프로젝트 코드로 뒤집을 수 없는 프레임워크 동작이었다. `set_language`는 `LANGUAGES` 허용 목록이 아니라 로케일 파일 존재(`check_for_language`)로 쿠키 설정을 정한다 [코드 django/views/i18n.py:60-62]. 프로브: `fr`은 쿠키가 설정되지만 이후 `<html lang>`은 `ko`, `xx`는 쿠키 없음 [실측 pytest 프로브]. 그래서 PSO 수용 기준 4("지원하지 않는 언어는 거부")의 실제 보장은 "쿠키 거부"가 아니라 "읽을 때 무시되어 화면 언어가 유지됨"이다. 테스트를 `fr`·`xx` 파라미터로 교체했고 `LANGUAGES`에 `fr`을 임시로 넣는 뮤테이션이 Red가 되는 것을 확인한 뒤 복원했다.
- 셸 작업자 발견: `{% get_available_languages %}`는 언어명에 `gettext`를 적용해 한국어 화면에서 English가 "영어"로 나왔다 [실측 작업자 렌더]. 언어 전환기는 자기 표기여야 하므로 `{% get_language_info_list %}`의 `name_local`로 교체했고 한국어·일본어 활성 상태 양쪽에서 표기가 바뀌지 않음을 확인했다.
- R4 소비처 점검 누락: 지역 라벨이 `build_event_json_ld`를 거쳐 JSON-LD payload에 들어가는 간접 경로를 엔지니어가 놓쳤다. 전체 회귀에서 `json.dumps`가 지연 번역 객체를 직렬화하지 못해 2건이 실패했다 [실측 uv run pytest -q: 3224 passed, 2 failed]. `DjangoJSONEncoder`로 고쳤고 비테스트 코드의 `json.dumps`는 그 한 곳뿐이다 [실측 rg].
- 사양 정정(날짜 서식, WED 사후 검토가 `Deviates`로 지적): §5의 "언어별 날짜 서식 적용 안 함"은 한국어 리터럴이 서식 문자열로 박힌 곳까지 막으려던 것이 아니었다. 번역가 3명 중 영어 번역가가 보고했고 오케스트레이터가 확인한 사실: 홈 달력에 `date:"Y년 n월 j일 l"`·`date:"n월 j일"`·`{{ month }}월`이 있어 영어 화면에도 "10월 21일"이 나왔다 [실측 rg 템플릿 태그 인자]. 이 결함은 AC1(승인 범위 미번역 0건)과 충돌한다. 한국어 출력이 글자 단위로 같고(`DATE_FORMAT`="Y년 n월 j일", `MONTH_DAY_FORMAT`="n월 j일", `F`="10월" [실측 django/conf/locale/ko/formats.py]) 다른 언어에서는 각 언어 서식이 나오는 Django 표준 서식으로 바꿨고, 숫자 명시 서식은 건드리지 않았다. 홈 달력 계약에 `month_start`(해당 월 1일 `date`)를 추가했다(I18N-17). 사용자가 원치 않으면 서식 문자열만 중립 숫자 서식으로 되돌릴 수 있다. 증거 문서의 "계획서 §13에 기록"은 이 항목을 쓰기 전의 오기였다.
- 코치 정정: `mail.outbox` 사용 테스트가 0건이라던 말은 리터럴 검색 결과였다. pytest-django `mailoutbox` 픽스처로는 11건의 선례가 있고 `tests/auth/test_signup_flow.py:10-32`가 가입 POST→메일 패턴이다 [코치 실측 rg `mailoutbox`].

## 14. Test List 현황 (43-1 백엔드)

코치 계약(Backend TDD Coach)과 오케스트레이터 보강. 상태는 2026-10-21 기준이고 모든 실행은 오케스트레이터가 fresh 실행한 결과다 [실측 uv run pytest -q].

| ID | 테스트(파일) | 경계 | 상태 | 증거 |
|---|---|---|---|---|
| I18N-1~6 | 설정 핀 6개(`tests/core/test_i18n_settings.py`) | contract | Green | R1 Red: `'ko-kr' == 'ko'`·LANGUAGES·LOCALE_PATHS·LANGUAGE_COOKIE_SECURE 속성 부재·LocaleMiddleware 부재·i18n 프로세서 부재 → R2a 설정 변경 후 6건 Green [실측] |
| I18N-7 | `test_jsi18n_경로는_200과_gettext_정의를_포함한다` | web | Green | Red 404 → R2a Green [실측] |
| I18N-8 | `test_스태프_콘솔_뷰는_활성_언어가_달라도_한국어로_실행되고_복원된다`(`tests/staff/test_staff_language_override.py`) | unit | Green | Red `'en' == 'ko'` → R2a Green [실측] |
| I18N-9 | `test_Accept_Language_헤더에_따라_홈_html_lang_속성이_결정된다` | web | Green | Red `'ko-kr' != 'ko-kr'` → R2a Green [실측] |
| I18N-10 | `test_setlang_POST로_언어를_바꾸면_이후_요청의_html_lang이_바뀐다` | web | Green | Red 404 → R2b Green [실측] |
| I18N-11 | `test_지원_목록에_없는_언어로_setlang_POST해도_이후_요청의_html_lang은_ko로_유지된다`(fr·xx) | web | Green | 작성 즉시 Green(코치 예고) → 뮤테이션: `LANGUAGES`에 `fr` 추가 시 fr 케이스 Red, 복원 후 Green [실측] |
| I18N-15 | `test_비로그인_403_응답은_언어와_무관하게_code가_not_authenticated다`(`tests/auth/test_auth_backend.py`) | web | Green | R1 Red: detail이 같음 → R2a 후 Red 사유가 `None == 'not_authenticated'`로 이동 → R2b Green [실측] |
| I18N-16 | `test_CSRF_실패_403에는_code_not_authenticated가_붙지_않는다` | web | Green | 작성 즉시 Green → 뮤테이션: 핸들러 조건을 `True`로 넓히면 이 테스트만 Red, 복원 후 Green [실측] |
| I18N-12 | `test_지원_언어별_홈_페이지에_번역된_문구가_보인다`(en·ja·zh-hans, `tests/core/test_ui_translations.py`) | web | Green | 번역 전 Red 3건(번역 문구 부재) → 번역 후 Green [실측] |
| I18N-12b | `test_지원_언어별_JS_카탈로그에_번역된_문구가_담긴다` | web | Green | 번역 전 Red 3건 → 번역 후 Green [실측] |
| I18N-13 | `test_가입_요청의_Accept_Language가_영어이면_인증_메일_제목이_영어다`(`tests/auth/test_signup_flow.py`) | web | Green | 번역 전 Red(제목이 한국어) → 번역 후 Green. 기대 문구를 지침에 없던 추측 "Please verify…"에서 번역가의 "Verify your email address"로 맞췄다 [실측] |
| I18N-14a | `test_po_파일에는_빈_msgstr나_fuzzy_항목이_없다`(`tests/core/test_i18n_catalog_completeness.py`) | contract | Green | 번역 전 Red(위반 목록) → Green. 뮤테이션(빈 msgstr)→Red→복원 Green [실측] |
| I18N-14b | `test_po_번역문의_자리표시자는_원문과_이름이_같다` | contract | Green | 번역 전 Red(`checked == 0`) → Green. 뮤테이션(자리표시자 이름 변경)→Red→복원 Green [실측] |
| I18N-14c | `test_po_번역문의_HTML_태그는_원문과_같다` | contract | Green | 번역 전 Red(`checked == 0`). **SRR 지적으로 강화**: 태그 이름만 비교하던 정규식이 속성 주입(`onmouseover`)을 통과시킴을 재현한 뒤 태그 전체 문자열 비교로 교체, 속성 주입 뮤테이션→Red→복원 Green [실측] |
| I18N-17 | `test_홈_달력_컨텍스트는_표시_월의_1일을_month_start로_담는다`(`tests/events/test_home_calendar.py`) | web | Green | Red `KeyError: 'month_start'` → Green [실측] |
| I18N-18 | `test_스태프_API_오류_문구는_요청_언어와_무관하게_한국어다`(`tests/staff/test_staff_api_language.py`) | web | Green | 첫 설계(404)는 Django 영어 문구라 세 언어가 같아 **틀린 이유로 통과**했다 [실측 프로브] → 405(DRF 번역 문구, ko·ja·en이 다름)로 교체해 Red(`ja ≠ ko`) → Green. 관문 제거 뮤테이션→Red→복원 Green [실측] |
| I18N-19 | `test_setlang_POST의_next가_외부_주소면_같은_사이트의_루트로_리다이렉트된다`(3 파라미터) | web | Green | 작성 즉시 Green(SRR 요구 핀). naive 리다이렉트 뷰 뮤테이션→3건 Red→복원 Green [실측] |
| I18N-20 | `test_스태프_콘솔_뷰가_예외를_던져도_활성_언어는_복원된다` | unit | Green | 작성 즉시 Green. 언어 미복원 뮤테이션→Red(I18N-8 포함 2건)→복원 Green [실측] |
| I18N-21 | `test_언어_쿠키가_일본어여도_404/500_페이지는_일본어_html_lang으로_렌더된다` | web | Green | 작성 즉시 Green. `<html lang>`을 컨텍스트 변수로 되돌리는 뮤테이션→500만 Red(404는 프로세서가 돌아 Green)→복원 Green [실측] |
| I18N-22 | `test_지원_언어별_홈에서_행사_제목은_한국어_원문_lang_ko로_표시된다`(3 파라미터) | web | Green | QVL이 지적한 AC6 회귀 가드 공백. 히어로 `lang="ko"` 제거 뮤테이션→3건 Red→복원 Green [실측] |
| I18N-23 | `test_승인_범위_템플릿에는_번역_태그_밖의_한국어_리터럴이_없다`(`tests/core/test_ui_korean_literal_guard.py`) | contract | Green | 계획 §7이 약속한 소스 가드(템플릿 부분). 대상 42파일 [실측 테스트가 개수 고정]. 날짜 서식을 `n월 j일`로 되돌리는 뮤테이션→Red→복원 Green [실측] |
| I18N-24 | `test_승인_범위_JS에는_gettext_밖의_한국어_리터럴이_없다` | contract | Green | JS 부분. 대상 14파일 [실측]. `gettext` 밖 리터럴 뮤테이션→Red→복원 Green [실측] |
| I18N-25 | `test_스태프_URL의_모든_DRF_뷰는_한국어_고정_관문으로_감싸져_있다` | contract | Green | SRR F4: `staff/urls.py`의 DRF 뷰 9개가 한국어 고정을 거치지 않았다. 12개(urls 9 + api_urls 3)를 세는 가드를 먼저 Red(위반 12건)로 두고 구현 [실측]. 관문 제거 뮤테이션→Red→복원 Green [실측] |

회귀 기준선: 전체 `3250 passed, 10 deselected` [실측 uv run pytest -q 2026-10-21, 기준선 3212건 + 새 테스트 38건]. e2e `10 passed` [실측 uv run pytest -q -m e2e tests/e2e].

## 15. 완료 평가와 잔여 (QVL·SRR·WED·BIR 사후 검토 반영, 2026-10-21)

- **판정**: 코드·테스트·브라우저 증거 기준 43-1은 완료다. 프론트엔드 게이트는 BIR `Conforms`, WED `Deviates`(날짜 서식 사양 정정을 §5·§13에 기록해 해소, 사용자 확인 대기)다. **production 반영(deploy PR 머지)은 일본어·중국어 검수 시트를 사용자가 확인하기 전까지 금지**다(§8-2, 런북 §3-18).
- 이 세션이 사후 검토를 받고 고친 것: SRR F1~F5(악성 `next` 핀, 예외 후 복원 핀, 비-ko 쿠키 오류 페이지 핀, 스태프 DRF 한국어 고정 12개, 번역문 HTML 속성 주입 가드), QVL이 지적한 소스 가드 공백(I18N-23·24)·AC6 회귀 가드(I18N-22)·§14 표 상태 불일치.
- 수치 정정: QVL이 `django.po`를 312건이라 했으나 `^msgid` 줄이 `msgid_plural` 4줄을 함께 세어 313줄이 된 것이다. 실제 메시지는 308건이다 [실측 grep '^msgid ' 309줄 − 헤더 1, msgfmt --statistics 308].
- 잔여 위험(정보): AC3 쿠키·`Accept-Language` 동시 우선순위는 Django 보장이며 이 저장소 테스트는 두 요인을 따로만 확인한다. AC4는 `fr`처럼 로케일 파일이 있는 미지원 코드가 쿠키로 저장되지만 읽을 때 무시된다(§13). 카탈로그 로드 실패 경로는 코드로만 검증했다. 일본어 푸터 "アクティビティカレンダー" 줄바꿈. 푸터 select·버튼의 브라우저 기본 모양. 파이썬 한국어 리터럴 가드 없음. 원문 한국어의 의미 충돌 "세션 유지" 제목(번역가 3명이 모두 보고, 번역으로 해결 불가).
- **PR**: #395(브랜치 `feat/i18n-foundation-43-1`, 커밋 7개 [실측 git log]). CI 5개 전부 통과 [실측 gh pr checks 395]: 테스트(gettext 설치 + `compilemessages --ignore .venv` 스텝이 처음 도는 잡), Docker 빌드(builder 단계 컴파일), e2e, 의존성 감사, GitGuardian. 머지는 사용자 승인 대기, production 반영은 일본어·중국어 검수 시트 확인 후. 검수 시트는 claude.ai 아티팩트(335건, 검수 우선 27건 [실측 build_sheet_data.py])로 만들었고 수정 목록을 채팅에 붙여 받는다.
- 이 세션이 만든 부작용: `compilemessages`를 설정 없이 한 번 실행해 로컬 `.venv`의 서드파티 `.mo` 1280개를 다시 썼다(내용상 동일, §13). 로컬에 Playwright Chromium을 설치했다(e2e 검증용).

---

