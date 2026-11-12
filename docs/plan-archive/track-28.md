# 트랙 28: 한글 브랜드명 SEO — '타쿠라이프' 검색 노출 (2026-09-10) [v2 — PSO·DAR·TDD 코치·WED·BIR·QVL 검토 반영]

> **검토 반영 요약(v1 → v2)** [6역할 병렬 산출 2026-09-10, 인용 file:line은 오케스트레이터가 sed/rg로 재확인]
> - PSO: ★1·★4·★6·★7 채택. **★3 어순 수정**(컬렉션을 이벤트보다 앞 — CLAUDE.md 우선순위) → WED 재확정 완료. **★2·★5는 사용자 확인
>   필요**(og:site_name은 공유 카드에 상시 노출되는 브랜드 표기 / 소개 페이지는 "별도 트랙" 판정, 착수 여부는 사용자). T1에 "타쿠라이프
>   토큰이 잘리지 않을 것" 추가(브랜드 선두 배치로 구조적 충족).
> - DAR: `core/presenters.py` 신설 채택(경계 가드 `tests/core/test_architecture_boundaries.py:143-152`는 core→도메인 임포트 금지 — 순수
>   함수는 도메인 미참조라 자동 통과). **브랜드 리터럴 재하드코딩 금지** — 상수 1곳을 두 파일이 공유. 주석 2줄 [코드 주석 정책]은
>   `build_website_json_ld` docstring에. description 3곳 [코드] 동일 갱신·상수 승격 보류 승인. 컨텍스트 프로세서 전역 공급안 기각.
> - TDD 코치: 조건부 Approve — **T4는 새 파일** `tests/core/test_presenters.py`(`pytestmark = pytest.mark.unit`, 선례
>   `tests/core/test_context_processors.py:18`) — `test_head_meta.py`는 모듈 마커 `web`(`:16`)이라 부적합. T6 뮤테이션 지점=
>   `templates/base.html:66`. T7 리터럴은 `:140-142`(두 줄 결합). **C1 게이트: `brand_name_ko`는 home.html이 실제로 소비할 때만
>   추가**(소비처 없는 프로덕션 변경 금지). 기존 테스트 파손 0건 [실측 코치 rg → 오케스트레이터 재확인: `content="takulife"` 단언은
>   `:85` 아카이브 페이지 1건뿐, og:site_name 단언 0건].
> - WED: 깊이 Light. 최종 문안 확정(아래 B·C·E). 태그라인 `<br>` 2행 구조 유지, `.footer-tagline`에 nowrap 없음(`site-chrome.css:267-272`)
>   → 320px 소프트 랩은 정보. 헤더 로고 유지, h1 무변경.
> - BIR: 깊이 Light 확정. CSS 변경 불필요(`dist/shell.css`는 빌드 산출물, 직접 편집 금지). `structured_data` 오버라이드 2곳째(선언
>   `base.html:66` + `detail.html:13`) [실측 rg]. **리스크 1건: 블록명 오탈자 시 조용한 무출력 → View Source 필수.** 사후 체크리스트 7항
>   + 320px 캡처 권장.
> - QVL: 회귀 위험 (a)~(d) 전부 없음 [실측 rg]. 누락 3건 반영: 경계 가드 테스트를 검증 명령에 명시 / 비공개 페이지(archive·mypage·staff)
>   가 새 기본 description을 상속함을 서술(noindex라 SEO 영향 없음, `block description` 오버라이드는 공개 5템플릿 [실측 rg -l 6파일 중
>   base 제외]) / 런북 §3-12 확인은 `curl` 한 줄로.

> 배경: 사용자 요청 "구글에서 영문뿐 아니라 한국어 '타쿠라이프'로 검색해도 찾을 수 있게 SEO 최적화" → 설명 후 "구현 시작"(2026-09-10).
> 현황 [실측 rg 2026-09-10]: 리포 전체(templates·py·md, `.docs/` 제외)에서 문자열 `타쿠라이프` **0건**(`rg -n '타쿠라이프'` → 출력
> 없음). 구글은 페이지에 실제로 적힌 텍스트·title·구조화 데이터로 검색어를 매칭하므로, 한글 브랜드명이 사이트 어디에도 없는
> 현재 상태에서는 한글 검색어에 잡힐 근거가 없다. 트랙 16(SEO 기반: robots·sitemap·canonical·noindex·Event JSON-LD)은 종결 상태이며
> 이 트랙은 그 위에 "브랜드명 텍스트 신호"만 얹는다.
> 현재 표면 [코드]: `templates/base.html:27` `<title>` 기본값 `takulife` / `:29,:33` description·og:description 기본 문구(브랜드명 없음) /
> `:30` `og:site_name="takulife"` / `templates/core/home.html:3` title=`{{ project_name }}` / `core/context_processors.py:27`
> `project_name="takulife"` / JSON-LD는 `templates/core/events/detail.html:13`의 Event 스키마 1곳뿐(홈에는 없음) /
> `templates/core/partials/_site_footer.html:13-14` 로고 `takulife` + 태그라인 "그대들의 오타쿠 라이프를 위하여." /
> `_site_header.html:16` 브랜드 링크 `takulife`.

## 승인 범위 (★ = 사용자 미확인 가정 — 검토 역할 판정 병기 예정)

**A. 브랜드명 단일 소스** (`core/context_processors.py`) [DAR 채택·코치 게이트]
- 모듈 상수 `PROJECT_NAME = "takulife"`, `BRAND_NAME_KO = "타쿠라이프"`를 두고, 기존 `project_name()` 프로세서가 돌려주는 dict를
  `{"project_name": PROJECT_NAME, "brand_name_ko": BRAND_NAME_KO}`로 확장한다(프로세서 신설 없음 — 브랜드 이름은 한 함수가 소유).
  D의 `core/presenters.py`는 이 상수 2개 [코드]를 import해 쓰고 리터럴을 다시 적지 않는다(DAR). 한글 표기는 `타쿠라이프` 하나로
  고정하며 `타쿠 라이프`·`타큐라이프` 등 변형을 어디에도 쓰지 않는다.
- **코치 게이트**: `brand_name_ko`는 `home.html`의 title·og_title 블록이 `{{ brand_name_ko }} {{ project_name }} — …`로 실제 소비할
  때만 추가한다. 소비처 없이 추가하면 실패 테스트 없는 프로덕션 변경이라 C1 Green을 승인하지 않는다.
- `project_name`은 `takulife` 그대로 둔다 — `{% block title %}`을 가진 템플릿 59개 [실측 `rg -l 'block title' templates/ | wc -l`],
  `— takulife` 리터럴 23건 [실측 rg -c 합산]이 이 값과 접미사 규약에 묶여 있고, 하위 페이지 접미사 변경은 이 트랙 목적(브랜드
  검색어 매칭)에 기여가 작다(★7).

**B. 홈 title·og:title** (`templates/core/home.html`) [WED 확정·PSO 어순 반영]
- ★3 확정 title = `타쿠라이프 takulife — 굿즈 컬렉션·서브컬처 이벤트 기록` — 35자 [계산 python len], 구글 실무 상한 약 50~60자
  [문서, 픽셀 폭 기준 참고값] 이내. 어순은 CLAUDE.md 우선순위(컬렉션 → 이벤트)와 일치(PSO). 브랜드 토큰이 1~5번째 글자 [계산]라
  검색 결과 뒤쪽 잘림에도 끊기지 않는다. 템플릿은 `{{ brand_name_ko }} {{ project_name }} — 굿즈 컬렉션·서브컬처 이벤트 기록`으로
  적어 A의 컨텍스트 값을 소비한다. `og_title` 블록도 같은 문자열로 오버라이드(트랙 16 규약 "og:title == title" 유지 — 현재 홈은
  og_title을 오버라이드하지 않아 기본값 `takulife`, `base.html:32` [코드]).

**C. 기본 description·og:site_name** (`templates/base.html`, `web/views/events.py`)
- ★4 확정(PSO 채택·WED 확정) 기본 description = `타쿠라이프(takulife)에서 팝업스토어 · 콜라보 카페 · 극장 특전 · 굿즈 예약 · 전시를
  검색하고, 방문 상태와 기록을 보관하세요.` — 78자 [계산 python len]. 같은 리터럴이 3곳 [실측 rg: `base.html:29`, `base.html:33`,
  `web/views/events.py:437-440` `_DEFAULT_EVENT_META_DESCRIPTION`(두 줄 결합 문자열)]에 있으므로 3곳을 같은 커밋에서 동일하게
  바꾼다(행사 상세 폴백과 base 기본값이 갈라지지 않게). 기존 테스트 `tests/core/test_head_meta.py:140-142`의 리터럴은 M0형(행위
  유효·형식만 변경) 교체 — Test List(T7)에 복원 후 같은 커밋. 영향 범위(QVL): `block description`을 오버라이드하지 않는 비공개
  페이지(archive·mypage·staff 등)도 새 기본값을 상속하지만 전부 noindex라 SEO 영향 없음. 오버라이드하는 공개 템플릿은 5개 [실측
  `rg -l 'block description' templates/` 6파일 중 base 제외].
- ★2 `og:site_name`을 `타쿠라이프 takulife`(14자 [계산])로 바꾼다(1곳 [실측 rg `og:site_name` templates/ 1건]). 구글 사이트명 판정
  신호(WebSite 구조화 데이터·og:site_name·title·헤딩 — [문서 구글 "사이트 이름" 가이드]) 중 하나. WED는 이 값 채택("타쿠라이프"
  단독은 영문 브랜드 신호 소실로 기각). PSO: 공유 카드 상시 노출 표기라 사용자 확인 필요 → **사용자 결정(2026-09-10): 값은
  `타쿠라이프|takulife`(파이프 구분, 공백 없음, 17자 [계산])** — C3를 같은 PR(#356)에 T3 Red→Green으로 추가.

**D. 홈 WebSite JSON-LD** (`core/presenters.py` 신설 — DAR 채택, `web/views/events.py` home 뷰, `templates/core/home.html`)
- ★1 페이로드 = `{"@context": "https://schema.org", "@type": "WebSite", "name": "takulife", "alternateName": "타쿠라이프", "url":
  <요청 Host 기반 홈 절대 URL>}`. `url`은 canonical과 같은 출처(`request.build_absolute_uri("/")`, 트랙 16 "도메인=요청 Host" 결정
  유지). 홈에만 렌더한다 — base.html에 넣지 않는다(모든 페이지에 WebSite를 반복 발행하면 구글이 대표 페이지를 고르기 어려워짐
  [문서 구글 가이드: 홈페이지에 넣기]).
- 조립은 순수 함수 `build_website_json_ld(site_url)` — **`core/presenters.py` 신설(DAR 판정 완료)**: `events/presenters.py`와 같은
  이름 규약, 사이트 수준 데이터는 core 소유, `web/views/_helpers.py`는 모델·쿼리셋 가공 헬퍼라 응집이 깨져 기각. 함수는
  `core.context_processors`의 `PROJECT_NAME`·`BRAND_NAME_KO`를 import해 `name`·`alternateName`을 채운다(리터럴 재기재 금지).
  docstring 2줄 [코드 주석 정책]에 가드레일(한글 표기 단일 소스·홈 전용 발행, 강제는 T6)을 적는다. `core/**/*.py`는 경계 가드
  `tests/core/test_architecture_boundaries.py:143-152`(core→도메인 앱 임포트 금지)에 자동 편입되며 이 함수는 도메인 미참조라 통과.
- 직렬화·이스케이프는 기존 `web/views/events.py:426 _json_ld_script`(`<`·`>`·`&` → `\uXXXX`) 재사용 — 홈 뷰가 같은 파일에 있으므로
  이동·추상화 없음. 렌더는 `home.html`에 `{% block structured_data %}` 오버라이드(detail.html:13과 같은 형태, `json_script` 필터 금지
  — 트랙 16 BIR 발견).
- 화이트리스트 필드만(name·alternateName·url). `potentialAction`(SearchAction 사이트링크 검색창)은 넣지 않는다 — 구글이 2024년
  지원 종료 [문서].

**E. 본문 텍스트에 한글명** (`templates/core/partials/_site_footer.html`)
- ★6 확정(PSO 채택·WED 확정) 푸터 태그라인 1행을 `타쿠라이프 — 그대들의 오타쿠 라이프를 위하여.`(26자 [계산])로 바꾸고 `<br>` 뒤
  2행 `이벤트·컬렉션·활동 기록을 한곳에.`는 그대로 둔다 — 모든 페이지 본문에 한글명이 1회 보이게 한다(숨김 텍스트 금지). 헤더 브랜드
  링크 텍스트 `takulife`(`_site_header.html:16`, `500.html:19`)는 로고 표기이므로 유지(WED·PSO). CSS 변경 없음(BIR: `.footer-tagline`
  `site-chrome.css:267-272`에 nowrap·overflow 규칙 없음, 760px 이하 1열 전환 `:361-364` [코드]) — 320px 소프트 랩은 정보. 프론트
  정책상 자동 테스트 없음(문안 변경) — 브라우저 실측으로 검증.

**F. 문서**
- `docs/deploy-runbook.md` §3-12(SEO 배포 후 확인)에 한 줄 추가(QVL 제안 형태): `curl -s https://<host>/ | grep -o '<title>[^<]*</title>'`
  에 `타쿠라이프` 포함, `curl -s https://<host>/ | grep -c '"@type": "WebSite"'`가 1 — 홈은 SSR이라 curl로 충분.
- 프론트 기술 기록 `.docs/FE/2026-09-10-brand-name-seo.md`(gitignore 트리 — 커밋 안 함). 새 `docs/FE/` 문서는 만들지 않는다 —
  **DAR·QVL 판정: 충분.** 가드레일 3개(한글 표기 단일·홈 전용 JSON-LD·brand_name_ko 단일 소스)는 코드 구조(상수 1곳·오버라이드
  1곳)와 T6 뮤테이션 테스트가 강제하고, docstring 2줄 [코드 주석 정책]은 "왜"만 설명한다.

## 배제 (범위 밖)

- ★5 소개(`/about/`) 페이지 신설 — 새 공개 URL·뷰·템플릿·sitemap 화이트리스트·noindex 해제·문안까지 이 트랙과 같은 규모의 별도
  트랙. PSO 판정: "별도 트랙"(불필요 기각 — 본문 텍스트는 원 요청 충족 수준에 영향). **사용자 결정(2026-09-10): 별도 트랙 착수
  승인** → `docs/backlog.md` 항목으로 기록(미착수, 계획서부터).
- `hreflang`(단일 언어 사이트), Organization 스키마(운영 주체 정보 부재), og:image(백로그 기존 항목), 헤더 로고 텍스트 변경, 하위
  페이지 title 접미사 일괄 변경(★7), 네이버 서치어드바이저·서치콘솔 등록·외부 링크 확보(사용자 계정 액션 — 제안 금지 규약).

## 수용 기준

1. 홈 응답 `<title>`과 `og:title`이 ★3 문자열과 정확히 일치하고, 문자열이 `타쿠라이프`로 시작한다(T1 — PSO 추가 조건 "토큰 잘림
   없음"의 관찰 가능 형태).
2. 홈 응답 `description`·`og:description`이 ★4 문구와 정확히 일치하고, 행사 상세 폴백도 같은 문구다(T2·T7).
3. 홈 응답 `og:site_name`이 ★2 값이다(T3).
4. `build_website_json_ld("http://testserver/")`가 ★1 dict를 돌려준다(T4). 홈 응답의 `application/ld+json` 블록을 `json.loads`하면
   `@type == "WebSite"`, `alternateName == "타쿠라이프"`, `url == "http://testserver/"`(T5). 이벤트 목록 응답에는 `ld+json`이 0건
   (T6 — 홈 전용 계약, 뮤테이션 검증).
5. 푸터 태그라인에 `타쿠라이프`가 보인다 — 브라우저 실측(390px·1280px [문서 fe-responsive §5 뷰포트 중 2개] + 320px BIR 권장) +
   View Source. 홈 `structured_data` 블록이 실제 출력됨을 View Source로 확인(BIR 리스크: 블록명 오탈자 시 조용한 무출력).
6. 전체 회귀 초록 — 기준 2541 passed·10 deselected·82.12초 [실측 2026-09-10 착수 전 `uv run pytest -q`, main fffb75a] + `check` +
   `makemigrations --check --dry-run` 무변경 + 경계 가드 `uv run pytest -q tests/core/test_architecture_boundaries.py` 통과(QVL 명시).
7. WED·BIR 사후 Conforms 2건 + QVL 완료 판정.

## Activated Roles / Not Activated (확정 — 6역할 사전 검토 완료 2026-09-10)

- Activated: PSO(★1·★2·★5 제품 판정 — 브랜드 표기 우선순위·소개 페이지), DAR(D의 소유 모듈·core→web 의존 방향), Backend TDD
  Coach(Test List·경계 판정), Backend & Integration Engineer(A·C·D 백엔드+테스트·F 런북), WED·BIR(B·C·E 문안·메타·JSON-LD 위치 —
  깊이 Light 제안), Frontend Implementation Engineer(B·E 템플릿), QVL(증거 매핑·완료 판정).
- Not Activated: SRR(정적 문자열만 — 이스케이프 헬퍼는 트랙 16 검증 완료 재사용, 사용자 입력 무관), DOR(설정·env·마이그레이션
  없음), AI AA(무관).

## Domain Boundary and Dependency Direction

- 브랜드 상수는 `core`(context processor)가 소유. WebSite 페이로드 조립 함수는 `core/presenters.py`(신설 — DAR 확정)에 두고
  `web/views`가 호출 — 기존 방향(core ← web)과 일치, `core/presenters.py`의 허용 의존은 `core.context_processors` 상수뿐(도메인 앱
  import 금지 가드 자동 적용). `events` 무접촉(C의 상수 리터럴 1곳은 `web/views/events.py` 소유). 템플릿은 컨텍스트 변수만 읽는다.

## Coupling and Cohesion Review

- `brand_name_ko`를 `project_name()` 안에 두어 "브랜드 이름" 응집 유지(프로세서 1개 추가 안 함). `_json_ld_script` 재사용으로
  이스케이프 규칙 단일 유지. 기본 description 3곳 [코드] 동일 리터럴은 기존 구조 그대로(상수 승격은 이 트랙 범위 밖 — Deferred).

## Pythonic Code Design

- `build_website_json_ld(site_url)`은 인자 하나·dict 반환·부작용 없음. 클래스·설정 플래그·레지스트리 없음.

## Test List (TDD 코치 확정 2026-09-10 — 조건부 Approve; 경계 = pytest 마커; Red = 기대 실패 사유) [문서 코치 산출]

| # | 경계 | Given / When / Then | Red 사유 | 뮤테이션 | 파일 |
|---|---|---|---|---|---|
| T1 | web | 홈 GET `/` → `<title>`·`og:title` == ★3 문자열(`타쿠라이프`로 시작) | 현재 `<title>takulife</title>`·`og:title=takulife` [코드 home.html:3, context_processors.py:27] | — | tests/core/test_head_meta.py(모듈 마커 web) |
| T2 | web | 홈 GET `/` → description·og:description == ★4 문구 | 현재 브랜드명 없는 문구 [코드 base.html:29,:33] | — | 같은 파일 |
| T3 | web | 홈 GET `/` → `og:site_name` == ★2 값 | 현재 `takulife` [코드 base.html:30] | — | 같은 파일 — **★2 사용자 확인 후 착수** |
| T4 | unit | `build_website_json_ld("http://testserver/")` → ★1 dict(키 5개 [코드]) 전체 계약 | ImportError(`core/presenters.py` 부재 [실측 ls]) | — | **새 파일 `tests/core/test_presenters.py`**, `pytestmark = pytest.mark.unit`(선례 `tests/core/test_context_processors.py:18`) |
| T5 | web | 홈 GET `/` → ld+json 파싱 `@type=="WebSite"`·`alternateName=="타쿠라이프"`·`url=="http://testserver/"`(배선·렌더 계약, T4와 필드 분리) | 홈에 ld+json 0건 | — | tests/core/test_head_meta.py(정규식 `tests/events/test_event_detail_view.py:103-104` 패턴) |
| T6 | web | 이벤트 목록 GET `/events/` → ld+json 0건(홈 전용) | 이미 Green | `templates/base.html:66` 기본 블록에 `<script type="application/ld+json">{}</script>` 임시 주입 → T6만 실패 확인 → 원복, diff 잔재 0 | 같은 파일 |
| T7 | web | 요약·카테고리·장소·기간 전부 없는 행사 상세 → description == ★4 폴백 | M0형: 프로덕션 리터럴 3곳 [코드] 교체 후 옛 기대값으로 Red → 테스트 리터럴 갱신 → Green(C2 안 미니 사이클) | — | tests/core/test_head_meta.py:140-142 |

## 구현 순서 (슬라이스별 커밋 — pytest 실행·판정은 오케스트레이터 단독) [코드 슬라이스 정의]

1. C1 `feat(seo)`: A + B — T1 Red→Green. 코치 게이트: Green 리뷰 시 `brand_name_ko` 소비처(home.html)를 코드로 제시.
2. C2 `feat(seo)`: C description 리터럴 전부(위 C절의 3곳 [코드]) + T2·T7 — 같은 커밋(트랙 16 M0a·M0b 선례).
3. C3 `feat(seo)`: og:site_name — T3. **★2 사용자 확인 전까지 보류**(확인 후 즉시 진행; 미확인이면 이 슬라이스만 제외하고 PR).
4. C4 `feat(seo)`: D presenter(상수 import) + 홈 뷰 컨텍스트 + home.html 블록 — T4→T5→T6(뮤테이션).
5. C5 `design(footer)`: E 태그라인 — 프론트 이중 리뷰 사후 평결 대상.
6. C6 `docs(deploy)`: F 런북 한 줄.
7. 브랜치 `feat/brand-name-seo`, PR 1건(트랙=PR 규약). `prompt_plan.md`는 스테이징 금지.

## 검증 명령과 기대 증거

- 착수 전 기준 재측정: `uv run pytest -q 2>&1 | tail -3`(passed 수·초 [실측]로 기준 6 갱신).
- 슬라이스별: `uv run pytest -q tests/core/test_head_meta.py`(Red 사유 확인 → Green).
- 회귀: `uv run pytest -q` 전체 + `uv run python manage.py check` + `uv run python manage.py makemigrations --check --dry-run` +
  `uv run pytest -q tests/core/test_architecture_boundaries.py`(새 모듈 편입 확인).
- 브라우저(Chrome DevTools MCP, `uv run python manage.py runserver`) — BIR 사후 체크리스트: ① 홈 View Source(서버 응답 원문)에서
  `<title>`·description·og:title·og:description·og:site_name이 확정 문안과 공백·구두점까지 일치, `structured_data` 블록이 실제
  출력됨, 헤드 순서(테마 스크립트 최선두 → viewport → title → CSS 체인 → ld+json → GA → `</head>`) ② `JSON.parse(document.
  querySelector('script[type="application/ld+json"]').textContent)` 결과가 키 5개 [코드]만 ③ `/events/`에서 같은 셀렉터 `null`
  ④ 콘솔 오류 0건(라이트·다크 각 1회) ⑤ 헤더 브랜드 `takulife`·h1 무변경 ⑥ 320px·390px·1280px 푸터 스크린샷(잘림·겹침 없음, 줄 수
  증가는 정보) ⑦ `git diff`에 `static/css/dist/` 변경 0건 → 검증 후 캡처 삭제.

## Frontend Review Evidence (트랙 28)

- 깊이: **Light 확정**(WED·BIR 동의) — 문안·메타·JSON-LD 블록 추가만이고 레이아웃·상호작용·비동기·breakpoint 변화 없음.
- WED 사전 사양 [문서 WED 산출 2026-09-10, 어순 재확정 포함]: title `타쿠라이프 takulife — 굿즈 컬렉션·서브컬처 이벤트 기록`(35자
  [계산]) / description ★4 문구(78자 [계산]) / og:site_name `타쿠라이프 takulife` / 태그라인 1행 `타쿠라이프 — 그대들의 오타쿠 라이프를
  위하여.` + 2행 유지 / 헤더 로고·h1 무변경 / `.footer-logo`(1.2rem·700)와 태그라인(0.8rem·muted)은 워드마크+캡션 위계라 중복 결함
  아님 [코드 site-chrome.css:260-272] / 사후 확인: 문안 정확 일치·h1·헤더 무변경·390px 소프트 랩 기록·1280px 1행 무줄바꿈.
- BIR 사전 기준 [문서 BIR 산출 2026-09-10]: `structured_data` 오버라이드는 부모 선언 위치(`base.html:66`)로 렌더 순서 고정 —
  home.html 내 `extra_css` 앞뒤 무관 / ld+json은 인라인·비실행 MIME이라 렌더 차단·bfcache·테마 초기화 영향 없음 / CSS 변경 불필요,
  `dist/shell.css` 직접 편집 금지 / 리스크: 블록명 오탈자 시 조용한 무출력 → View Source 필수 / 수용 기준 6항(블록 출력·헤드 순서·
  콘솔 0건·목록 페이지 ld+json 0건·푸터 무잘림·dist 무변경).
- 계획된 브라우저 증거: 위 "검증 명령" 브라우저 항목 ①~⑦.
- 사후 평결 [문서 2026-09-10 사후 검토 산출]: **WED Conforms**(B·C description·D·E 전 항목 사전 사양과 일치, 스크린샷 3장 육안 확인,
  og:site_name은 범위 밖) / **BIR Conforms**(수용 기준 6항 전부 충족, 결함 0건, 오버라이드 2곳·og:site_name 1곳·태그라인 1곳 rg 재확인)
  / **QVL 완료 판정: 완료(C3 제외 범위)** — 수용 기준 1·2·4·7 소스 대조 Passed, 5·6은 소스 정합 + 오케스트레이터 실측 의존, 3은
  보류 → **사용자 결정 후 C3 추가**: 2ca348e(`타쿠라이프|takulife`, T3 Red `content="takulife"` → Green) + 4dcdbc3(백로그 C2 소개
  페이지 별도 트랙). 회귀 재실행 **2547 passed·10 deselected·111.67초 [실측]**, check 0 issues. PR #356 커밋 7개 [실측 git log:
  ebfd39a·82dbd06·8a149d5·d6116cb·91e584f·2ca348e·4dcdbc3], 머지=사용자 승인(2026-09-10 "승인") → CI 5개 잡 pass [실측 gh pr
  checks] → **main b8e96c1 머지 완료(2026-09-10)**. WED·BIR C3 사후 Conforms(파이프 문자 이스케이프 문제 없음). 잔여: pr-log 롤링
  docs PR, 배포(deploy PR) 후 런북 §3-12 curl 실측.
  사고 기록: C3 커밋 시 일시적 `index.lock`으로 스테이징분이 백로그 커밋에 섞임 → 푸시 전 `reset --soft`로 분리(작업 트리 무손실).
- 정정 기록(Orchestrator Contract 규칙 4·6 위반 1건): QVL 완료 판정 브리프에 "네가 낸 완료 체크리스트 9항"이라고 적었으나 그 목록은
  QVL 사전 검토의 채팅 산출에만 있고 계획서에는 없었다 — QVL이 문서 부재를 잡아 계획서 수용 기준 7항 [문서] + AGENTS.md 완료
  체크리스트로 대체 매핑함. 브리프의 문서 참조는 존재 확인 후에만 쓸 것.
- 실측 증거 [실측 2026-09-10 runserver+DevTools MCP+curl]: 헤드 순서 테마 9-25행 → viewport 26 → title 27 → CSS 69~90 → ld+json 92 →
  `</head>` 94 / JSON.parse 키 5개·홈 1건·`/events/` null / 콘솔 error·warn 0건(홈 라이트·다크·목록) / 태그라인 1280px 404.97px·390px
  358px·320px 288px 전부 2행, 문서 scrollWidth==viewport(가로 스크롤 0) / `static/css/dist/` 변경 0건 / 캡처 3장 검증 후 삭제.

## Deferred

- 소개 페이지(★5 — 별도 트랙, 사용자 확인). 기본 description 리터럴(C절 3곳 [코드]) → 상수 승격(트리거: 리터럴이 한 곳 더 늘어날
  때; 템플릿 리터럴이라 새 컨텍스트 프로세서가 필요해 지금은 비용이 더 큼 — DAR). `project_name()` 함수명 재검토(트리거: 반환 키가
  셋 이상 — DAR). Organization 스키마(운영 주체 정보 확정 시). og:image(백로그 기존).

## 문서 대상 / 인계 조건

- `docs/deploy-runbook.md` §3-12 한 줄. `.docs/FE/2026-09-10-brand-name-seo.md`(로컬). `docs/backlog.md`는 현재 상태가 바뀌지
  않으면 무편집. 머지 시 `docs/pr-log.md` 롤링은 별도 docs PR(기존 관례).

---

