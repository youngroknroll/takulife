# 트랙 16: SEO 최적화 — robots 해제·sitemap·페이지별 메타·JSON-LD·noindex (2026-08-29)

> 배경: 사용자 요청 "SEO 최적화". 사용자 범위 결정(2026-08-29): robots.txt
> 전면 차단 **지금 바로 해제** + 기술 SEO 기반 + 페이지별 메타 + 구조화
> 데이터 + 비공개 noindex 전부. 검토 6역할 병렬(DAR·DOR·SRR·코치·WED·BIR)
> + 추가 판정 2건(도메인 출처, noindex 테스트 경계) 완료.
> 기록: 코치 1차 보고의 "sites 미설치"는 오류로 정정됨(settings.py:293
> `django.contrib.sites`, :399 `SITE_ID=1` [코드]) — 이 정정이 도메인 출처
> 재판정(RequestSite 채택)의 계기.

## 승인 범위

**R. robots.txt 허용 전환** (core/views.py:20-23)
- `Disallow: /` 제거 → `User-agent: *` + `Disallow: /admin/`, `/api/`,
  `/accounts/`, `/staff/`(SRR 정책) + `Sitemap: <요청 Host 기반 절대 URL>`.
- 기존 차단 단언 테스트(tests/core/test_robots_txt.py:13-20)는 R0으로
  Test List에 복원 후 R1 Green과 같은 커밋에서 교체(코치 절차).

**S. sitemap.xml 신설**
- `django.contrib.sitemaps`를 INSTALLED_APPS에 추가, Sitemap 클래스
  (발행 행사 + 정적 공개 5페이지)와 ~15줄 래퍼 뷰를 `web/sitemaps.py`에
  신설(DAR 결정). 래퍼가 `RequestSite(request)`를 넘겨 **도메인=요청
  Host** — DB Site.domain 미참조(기본 example.com 리스크 구조적 제거,
  canonical과 도메인 출처 단일화). 행사 위치는 `Sitemap.location()`
  오버라이드(`get_absolute_url` 추가 금지 — events→web 역결합).
- 소스는 `Event.objects.published()` 단일 호출(SRR B3).

**M. 페이지별 title·meta·og** (WED 사양)
- base.html의 description·og:description을 `og_title`과 같은 블록 패턴으로
  전환, `og:url`·`<link rel="canonical">` 신설 — 값은 뷰 컨텍스트에서
  `request.build_absolute_uri` + 쿼리스트링 제거 경로(DAR·WED).
- title 구분자 `{고유} — takulife`로 통일 — events 3템플릿의 기존
  `takulife | X` 순서 전환 포함(같은 종류 결함, 트랙 내 처리).
- 행사 상세: title=`[work_title · ]title — takulife`(truncatechars 20),
  description=summary 우선, 없으면 카테고리·장소·기간 조립+폴백
  (truncatechars 100). 목록·달력·legal은 정적 문구(WED 표), 홈은 공통
  문구 유지. GET 파라미터는 메타에 절대 미반영.
- **og:image는 발행하지 않는다**(래스터 자산 부재, favicon.svg 유용 금지).

**J. 행사 상세 JSON-LD** (schema.org Event)
- 조립은 `events/presenters.py` 순수 함수(DAR — 데이터 소유 도메인),
  렌더는 detail 템플릿의 `{% block structured_data %}`(CSS 체인 뒤,
  </head> 앞 — BIR 위치 규칙).
- **`json_script` 필터 금지** — type이 `application/json` 고정이라 JSON-LD
  로 인식 안 됨(BIR 발견). 수동 `<script type="application/ld+json">` +
  `<`·`>`·`&`의 `<`류 이스케이프(제목에 `</script>` 포함돼도 안전).
- fail-closed: `start_date` 또는 `location_name` 없으면 블록 전체 생략
  (WED — 구글 Event 필수 필드를 placeholder로 채우지 않는다).
- 화이트리스트 필드만: name·startDate·endDate·location(Place)·
  location.address(region 라벨)·url·description(메타와 동일 소스).
  `view_count`·`source_name`·`publish_status`·`created_at`·`verified_at`은
  어떤 속성으로도 매핑 금지, J2 테스트로 고정(SRR B2).

**N. noindex fail-closed** (DAR 설계 + 코치 경계 판정)
- base.html `{% block robots_meta %}` 기본값 **noindex** — 새 템플릿이
  블록을 빠뜨리면 비색인(안전) 쪽으로 실패. 공개 6페이지(홈·목록·달력·
  상세·legal 2)만 오버라이드로 해제. X-Robots-Tag 미들웨어 기각.
- 비공개 페이지는 이미 전부 `@login_required` 302(SRR 실측) — noindex는
  벨트-앤-서스펜더. staff 셸 기존 하드코딩(base_staff.html:30)과의 중복은
  구현 시 확인해 한 곳으로 정리(N1′ 스태프 케이스가 보호).

**D. 문서**
- docs/deploy-runbook.md §3-12 재작성: robots 해제를 SMTP 게이트와 분리
  (2026-08-29 결정), "검색 유입자는 가입 인증 메일 미동작으로 가입 완료
  불가"라는 알려진 상태 명기(DOR).
- docs/backlog.md: og:image 브랜드 카드(1200×630 PNG) 이연 항목 추가.

## 배제 (범위 밖·기각)

- Site.domain env 시드 마이그레이션(DOR 대안 b)·sitemap 손코딩(c) — DAR
  기각(도메인 출처는 RequestSite로 단일화, contrib 재사용).
- X-Robots-Tag 헤더/미들웨어, PageMeta 모델, SEO 전용 앱, 사이트맵
  레지스트리, `get_absolute_url` 추가 — DAR 기각.
- og:image 발행, eventStatus/eventAttendanceMode/organizer 매핑(근거 필드
  없음), 쿼리스트링별 title 변형 — WED 제외.
- `/accounts/` 하위 login/signup의 robots Allow 예외 — 미채택(단순 전체
  Disallow, 필요해지면 별도 제품 결정 — SRR).
- /api/docs/·/admin/ 접근 제어 축소, view_count 봇 분리 — SRR 이연.
- robots 해제/sitemap 분리 배포(DOR 권고) — RequestSite 채택으로 근거
  소멸(도메인 데이터 의존 없음), 단일 PR 진행.

## 수용 기준

1. R1·R2: robots.txt에서 `Disallow: /` 소멸, 4개 비제품 경로 Disallow,
   Sitemap 라인 존재. 기존 R0 테스트는 같은 커밋에서 교체.
2. S1~S3·S2b: sitemap이 발행 행사만·비공개 경로 0건·도메인=요청 Host
   (테스트에서 testserver — Site.domain(example.com) 회귀 방지).
3. M1: 행사 상세 메타 컨텍스트가 행사명 포함 title·기본 문구와 다른
   description을 조립. 공개 페이지 title 전부 상호 상이 + `— takulife`
   통일. og:image 태그 0건.
4. J1u·J1·J2: 조립 함수 필드 계약, 응답 본문 JSON 파싱 성공+필수 키,
   내부 필드 값 부재. start_date/location_name 결손 시 블록 미렌더.
5. N2′·N1′: 공개 6페이지 noindex 부재(web), 비공개 대표 5종 존재
   (contract). N2′는 N1′와 같은 커밋 이상으로 우선(코치 — fail-closed의
   조용한 실패 방향이 공개 쪽).
6. 전체 회귀 초록(기준 2325개 테스트 [실측 2026-08-29 트랙 15], 착수 시
   재측정) + `manage.py check` + `makemigrations --check --dry-run`.
7. 프론트 이중 리뷰 사후 Conforms 2건 + QVL 완료 판정. BIR 브라우저
   체크리스트: 헤드 순서(테마 스크립트 최선두·CSS 체인 34-50행 불변),
   JSON-LD `JSON.parse` 성공+type 확인, `</script>` 포함 제목 원문 소스
   확인, noindex 전수 View Source, 추가 바이트 [실측] 기록.

## Activated Roles

- 활동 완료(사전): DAR(소유 위치·도메인 출처·noindex 메커니즘),
  DOR(런북 정합·배포 경로), SRR(robots 정책·JSON-LD 화이트리스트·noindex
  판정표·스로틀 무충돌), Backend TDD Coach(Test List·경계 판정 2건),
  WED·BIR(사전 사양·기준 — 깊이 Standard, BIR 판정).
- 구현·사후: Backend & Integration Engineer, Frontend Implementation
  Engineer, WED·BIR 사후 평결, Quality Verification Lead(최종).
- Not Activated: PSO(사용자 직접 범위 결정), AI AA(무관).

## Frontend Review Evidence (트랙 16)

- 깊이: Standard — BIR 판정(44개 템플릿 base.html 상속 [실측 BIR grep]
  전반에 걸친 noindex 영향 + JSON-LD 이스케이프 리스크는 Light 부적합).
- WED 사전 사양·BIR 사전 기준: 2026-08-29 검토 산출이 세션 기록으로
  소실되어 2026-08-30 착수 시 재산출(WED: 페이지별 문구 표·조립 규칙·
  truncatechars 20 적용 대상 판정 / BIR: 헤드 삽입 4규칙을 트랙 14 이후
  줄번호로 재기준, 이스케이프 계층 판정, staff 독립 셸 실측으로 noindex
  중복 정리 대상 부재 확정).
- **WED 사후 판정: Conforms**(2026-08-30) — 사양 표 전항 파일 독립
  재검증 일치. 비차단 관찰 1건: 상세 title 접미사가 Python 리터럴
  " — takulife"(project_name 상수 고정이라 렌더 동일).
- **BIR 사후 판정: Conforms**(2026-08-30) — 헤드 규칙 4건·이스케이프
  사양(소문자 <는 RFC 8259 등가 판정)·체크리스트 7항 중 6항 코드
  정합, 추가 바이트 1항은 오케스트레이터 실측 인용(Unverified 병기,
  결함 아님). staff 셸 무변경 확인.
- 브라우저 실측(2026-08-30, 로컬 dev + Chrome DevTools MCP): 체크리스트
  7항 전부 통과 — JSON.parse 성공·금지 키 0건·</script> 라운드트립
  일치·noindex 전수(공개 6종 0건/비공개 4종+스태프 존재)·추가 바이트
  상세 +580B·홈 +115B [실측]. 콘솔 오류 0건. 이 검증에서 JSON-LD
  description 분기 결함을 발견해 J1u3·J1c로 트랙 내 즉시 수정.
- **QVL 완료 판정(2026-08-30): 완료 가능** — 수용 기준 7건 전부 Passed,
  Failed 0. 신규 테스트 수 +39는 QVL이 diff에서 독립 재집계해 2325→2364와
  대조 일치. Unverified 병기(비차단): ① 프로덕션 curl 확인(robots·
  sitemap — 런북 §3-12 배포 후 항목) ② BIR 추가 바이트 항목(실측 인용)
  ③ HTML 특수문자 포함 description의 두 표면 바이트 동일성(단일 소스라
  구조적 건전, 테스트 케이스는 평문만 — 기록용).

## Domain Boundary / Coupling

- web→events 기존 방향만 재사용(web/views/events.py:421 선례), 신규 의존
  방향 0. JSON-LD 조립=events/presenters(데이터 소유), 렌더·메타·sitemap·
  noindex=web/템플릿.
- 도메인 출처 단일화: canonical·og:url·sitemap·robots Sitemap 라인 전부
  요청 Host. Site.domain은 allauth용으로만 잔존, SEO 경로에서 미참조.

## 파일

- core/views.py, tests/core/test_robots_txt.py(R0→R1·R2)
- config/settings.py(INSTALLED_APPS), config/urls.py(sitemap 라우트)
- web/sitemaps.py(신규), tests/web/test_sitemaps.py(신규 — S1·S2·S2b·S3)
- events/presenters.py(build_event_json_ld), tests/events/(J1u·J2)
- web/views/events.py(메타·JSON-LD 컨텍스트), tests/web/(M1·J1·N1′·N2′)
- templates/base.html, templates/core/events/{list,calendar,detail}.html,
  templates/core/home.html, templates/core/legal/{privacy,terms}.html
- docs/deploy-runbook.md, docs/backlog.md

## Test List (코치 계약, 2026-08-29)

| ID | 시나리오 | 경계 |
|---|---|---|
| R0 | (기존 보존) 전면 차단 단언 — R1 Green 커밋에서 교체 | web |
| R1 | 로봇_배제_파일은_사이트맵_위치와_함께_전체_크롤링을_허용한다 | web |
| R2 | 로봇_배제_파일은_비제품_경로는_계속_차단한다(admin·api·accounts·staff) | web |
| S1 | 사이트맵_아이템은_발행된_행사만_포함한다 | domain |
| S2 | 사이트맵_엔드포인트는_발행된_행사_상세_경로를_응답한다(도메인 무단언) | web |
| S1c | 사이트맵_아이템은_pk_오름차순으로_정렬된다(신규 발견 2026-08-30 — S2 실행 중 UnorderedObjectListWarning [실측], 무순서 페이지네이션 누락·중복 리스크. 코치 판정: 정렬은 관찰 가능 행동이라 리팩터링 아님) | domain |
| S2b | 사이트맵_URL의_호스트는_요청_호스트를_따른다(Site.domain 회귀 방지) | contract |
| S3 | 사이트맵은_비공개_경로_URL을_포함하지_않는다 | web |
| S4 | 사이트맵은_정적_공개_페이지_5종을_포함한다(신규 발견 2026-08-30 — 승인 범위 S의 "정적 공개 5페이지"에 대응하는 시나리오 부재를 코치가 지적, Canon TDD 절차로 추가) | web |
| M0a | (기존 보존) test_head_meta.py::행사_상세_og_title 행사_제목_포함 — M1 Green 커밋에서 리터럴만 신질서 갱신(행위 유효, 삭제 아님 — 코치 판정 2026-08-30) | web |
| M0b | (기존 보존) test_head_meta.py::행사_상세_og_title 특수문자_이스케이프 — M0a와 동일 절차 | web |
| M1 | 행사_상세_페이지는_행사명이_들어간_메타_제목을_조립한다 | web |
| M1d | 행사_상세_페이지는_요약_우선순위로_description을_조립한다(신규 2026-08-30 — 코치 분해: 수용 기준 3의 description 축) | web |
| M2 | 공개_페이지_title은_서로_다르고_접미사가_통일돼_있다(신규 2026-08-30 — list·calendar 전환 포함) | web |
| M3 | 페이지는_쿼리스트링_없는_canonical과_og_url을_포함한다(신규 2026-08-30) | web |
| M4 | 페이지_응답은_og_image_태그를_포함하지_않는다(신규 2026-08-30 — 뮤테이션 검증 예상) | web |
| J1u | 행사_JSON_LD_페이로드는_행사_핵심_필드를_담는다(+결손 시 None) | unit |
| J1u2 | 지역_라벨이_없으면_주소_필드를_생략한다(신규 발견 2026-08-30 — J1u Green 검수에서 addressRegion null 가능성 발견, 코치 판정: address 키 생략) | unit |
| J1 | 행사_상세_페이지는_유효한_JSON_LD를_응답에_포함한다 | web |
| J1e | 행사_JSON_LD는_제목에_포함된_스크립트_종료_태그를_이스케이프한다(신규 발견 2026-08-30 — 주입 안전성은 렌더 여부와 독립 축, 코치 판정: 별도 시나리오. 이미-Green이면 뮤테이션 검증) | web |
| J1u3 | description을_명시하면_요약_대신_그_값을_쓴다(신규 발견 2026-08-30 — 브라우저 검증에서 JSON-LD description=""·메타=조립문 분기 실측, "메타와 동일 소스" 위반. 코치 판정 (a): meta_description 주입) | unit |
| J1c | 행사_상세_페이지의_JSON_LD_description은_메타_description과_같다(신규 2026-08-30 — 배선 계약, 같은 응답 내 두 표면 직접 대조) | web |
| J2 | JSON_LD는_내부_운영_필드를_노출하지_않는다(5필드 값 부재) | contract |
| N2′ | 공개_페이지_응답은_noindex_로봇_지시를_포함하지_않는다(6종) | web |
| N1′ | 비공개_페이지_응답은_noindex_로봇_지시를_포함한다(5종) | contract |

첫 Red=R1(코치 지정). 커밋 단위: R → S → J → M → N → D 순 6커밋 안팎,
브랜치 `feat/seo-track-16`(origin/main 분기 — 트랙 15 PR #328과 독립).

## 검증 커맨드

- 타깃: `uv run pytest -q tests/core/test_robots_txt.py` 등 시나리오별
  슬라이스(Red 사유 확인 후 Green)
- 최종: `uv run pytest -q` + `uv run python manage.py check` +
  `uv run python manage.py makemigrations --check --dry-run`
- 브라우저(BIR 체크리스트 7항): Chrome DevTools MCP로 홈·행사 상세·
  비공개 1종·스태프 1종 — 수용 기준 7 항목
- 문서: 런북 §3-12 diff 검토(DOR 정합)

## Deferred

- og:image 브랜드 카드 제작·발행(1200×630 PNG — 디자인 자산 트랙),
  eventStatus/AttendanceMode(모델에 취소·연기 상태 도입 시),
  view_count 봇 분리(크롤 볼륨 실측 후), /api/docs/·/api/schema/ 접근
  제어 재검토(별도 결정), 검색엔진 콘솔 등록·sitemap 제출(사용자 계정
  액션 — 기록만, 제안 아님).
- 알려진 사실: 크롤러 GET이 `view_count`를 그대로 증가시킨다
  (web/views/events.py:422, dedup 없음 [코드]) — 인기순 지표로 쓰기 전
  재검토 필요.

---

