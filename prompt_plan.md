# 모바일 디자인 3단계 — 기록과 운영 : **3단계 구현·검증 완료** (2026-07-10, 브랜치 `feat/mobile-design-phase3`)

> **9커밋 전부 로컬 브랜치 반영, PR 대기**: `a4ae628`(vocab `INTEREST_LABEL` "찜" 통일) · `3d8d11e`(기록장→저장한 행사) · `9996d9e`(예정 목록→나의 일정) · `a978ade`(방문 기록→다녀온 기록, 페이지 라벨 한정) · `3189f58`(비공식→직접 등록 + 가드 테스트 재작성) · `583c968`(직접 등록 폼 3그룹 재배치) · `de71110`(이미지 첨부 노출) · `6532eda`(스태프 최근 처리 카드화, Gate D) · `9ce842e`(QA aria-label 오기 정정). 각 커밋 전 `uv run pytest -q` 전체 스위트 **1163 passed, 20 deselected** 무회귀 재확인, 최종 `uv run pytest -m e2e -o addopts='' tests/e2e/ -q` **20 passed**. 상세 변경·검증 기록은 `.docs/frontend-integration-changelog.md` 참조.
> 승인 근거: `.docs/plans/2026-07-10-mobile-first-commercial-design-improvement-plan.md` §15 3단계, §19-3(아카이브 명칭 승인, `INTEREST_LABEL`→"찜" 확정). frontend TDD-exempt — 단, `test_archive_mixed_rendering.py` 가드 테스트는 backend view 테스트라 TDD 대상(Red-Green 확인 완료), 템플릿/CSS/JS는 AGENTS.md Frontend Work Policy에 따라 자동 테스트 대신 수동 브라우저 검증.

## 범위 (§15 3단계)
1. vocab 통일: `core/vocab.py`의 `INTEREST_LABEL` "관심"→"찜"(§19-3), 안내 문구·로그인 모달 문구 동기화.
2. 아카이브 명칭 4건: 기록장→저장한 행사, 예정 목록→나의 일정, 방문 기록→다녀온 기록(페이지 라벨 한정, 엔티티 서술 유지), 비공식→직접 등록.
3. 직접 등록 폼 단계화: 기본(종류·이름)/상세(분류·작품명·장소·참고 링크, `<details>` 접기)/기록(메모) 3그룹 재배치, 이미지 첨부 노출(백엔드 기지원, `PersonalEntry.image` 무변경).
4. 스태프 최근 처리 내역 모바일 카드화(Gate D) — 45rem 이하 표↔카드 상호 전환.
5. (QA 후속) `index.html` summary-grid aria-label 오기 정정 + `_archive_nav.html` 사용 예시 주석 라벨 갱신.

## 수용 기준 (§10 Gate D 3단계 항목)
- **Gate D**: 스태프 콘솔 최근 처리 내역이 모바일(45rem 이하)에서 4열 표 대신 카드로 렌더(`6532eda`), 대상 제목은 줄바꿈만 허용(말줄임 금지), 담당 이메일만 말줄임 적용, 카드 텍스트 `--fs-sm`(0.8rem) 이상. 대시보드 다른 두 표·`home_categories` 표가 공유하는 `.data-table` 규칙은 무수정.
- 아카이브 전 페이지(저장한 행사/나의 일정/다녀온 기록/직접 등록/찜 목록) 라벨·타이틀·nav 탭·푸터·"빠른 이동" 링크가 새 명칭으로 일관 렌더, URL 경로·CSS 클래스명(`.unofficial` 등 내부 코드)·폼 필드 `name`은 전부 불변.
- 직접 등록 폼 제출 시 서버 필드 에러(`url`)가 있으면 접힌 상세 정보 `<details>`가 자동으로 펼쳐짐(§9 최소 구현).

## 판단 사항
- 1c(방문 기록→다녀온 기록)는 지시된 필드 목록이 title/h1/back-link/안내 li로 명시돼, `visits.html`의 summary-grid·aside aria-label과 `visit_create.html`의 부제 h2("새 방문 기록")는 엔티티 서술에 준해 라벨 변경 대상에서 제외 — 1a/1b는 aria-label이 명시적으로 포함돼 있었던 것과 달라, 실측 누락이 아닌 의도적 축소로 해석해 진행. 오케스트레이터 확인 결과 별도 후속 커밋 없이 그대로 승인.
- 1d 가드 테스트(`test_archive_mixed_rendering.py`)의 픽스처 title이 "비공식 아크릴"이라 "비공식"이 포함된 라벨 단언이 항상 참이 되는 가짜 통과 상태였음을 발견 — 픽스처를 "투명 아크릴"로 교체하고 단언을 "직접 등록" 포함 여부로 재작성, 라벨 변경 전 실행해 3 failed(RED) 확인 후 라벨 변경을 적용해 5 passed(GREEN) 확정.
- QA MEDIUM: `index.html`의 summary-grid aria-label이 "나의 일정 요약"으로 잘못 남아있던 것을 `9ce842e`로 "저장한 행사 요약"으로 정정. 같은 커밋에 LOW(구 라벨이 남은 사용 예시 주석)도 함께 해소.

## 검증
`uv run pytest -q` 전체 스위트 프레시 실행(1163 passed, 20 deselected 무회귀 확인, 각 커밋 시점마다 반복) + `uv run pytest -m e2e -o addopts='' tests/e2e/ -q`(20 passed) + 오케스트레이터 브라우저 실측(아카이브 전 페이지 라벨·구 라벨 잔존 0건, 직접 등록 폼 details 기본 닫힘+url 에러 자동 펼침, 이미지 실업로드 성공, 스태프 카드 375px/1440px 표-카드 전환) + `.docs/frontend-integration-changelog.md` 기록.

## 하지 말 것 / 범위 밖(별도 승인 대기)
Google OAuth 성공 경로(§19-4, 사용자 액션 선행 필요) · vocab 단일 출처화 확장(드래프트 상태 라벨 등, §17 Deferred) · 홈 포스터 찜 버튼(`.poster-interest`) 34px→44px 확대(WCAG 2.5.8 예외, 2단계에서 보류 유지 — 별도 사용자 승인 필요).

---
---

# 모바일 디자인 2단계 — 핵심 여정 : **2단계 구현·검증 완료** (2026-07-10, 브랜치 `feat/mobile-design-phase2`)

> **10커밋 전부 로컬 브랜치 반영, PR 대기**: `a9e2cb0`(홈 섹션 순서) · `ee390d2`(카드 region_label+44px) · `4509104`(상세 상태 축약형) · `5202514`(기록 남기기 1차 CTA 승격) · `3b4799e`(토스트 컴포넌트 신설) · `44cef98`(토스트 연동) · `6a003d0`(e2e 스모크) · `fee492c`(공식 링크 2차 강등, QA) · `8bb8010`(44px/40px 보완+포스터 예외 기록, QA) · `3a9c39f`(sessionStorage 방어, QA). 각 커밋 전후 `uv run pytest -q` 전체 스위트 **1162 passed, 20 deselected** 무회귀 재확인, 최종 `uv run pytest -m e2e -o addopts='' tests/e2e/ -q` **20 passed**. 상세 변경·검증 기록은 `.docs/frontend-integration-changelog.md` 참조.
> 승인 근거: `.docs/plans/2026-07-10-mobile-first-commercial-design-improvement-plan.md` §15 2단계, §19-1(1단계 구현 단위 승인 — 기능별 커밋 후 단계마다 별도 PR). frontend TDD-exempt(단, `region_label`은 백엔드 표시 데이터 추가라 TDD 대상 — RED→GREEN 완료) — AGENTS.md Frontend Work Policy에 따라 나머지는 자동 테스트 대신 수동 브라우저 검증.

## 범위 (§15 2단계)
1. 홈 섹션 순서: "카테고리로 둘러보기"를 "곧 종료돼요" 뒤·"새 이벤트" 앞으로 이동(§6.1).
2. 행사 카드 정보 위계: 목록 카드에 지역·장소 합성 표기("지역 · 장소명", §6.2), 찜 버튼·필터 토글 44px.
3. 상세 참여 상태 변경: `user_status` 있으면 "현재 상태+상태 변경" 축약형, 무상태는 직접 노출 유지(§6.3). 방문 완료 시 "기록 남기기" 1차 CTA 승격 + 공식 링크 2차 강등, 고정 CTA는 정확히 한 쌍만 렌더.
4. 행동 결과 피드백: 신규 토스트 컴포넌트(§6.4) — 찜·상태 변경 성공 시 opt-in 발화, `missed`는 제외, archive 템플릿 비침습.
5. (QA 후속) 상세 조작 영역 44px/40px 보완, 홈 포스터 찜 버튼 WCAG 예외 기록, sessionStorage 차단 환경 방어.

## 수용 기준 (§10 Gate B/C 2단계 항목)
- **Gate B**: 주요 조작 영역이 §5.4 합격 기준(44px 이상, 상태 버튼 40px 이상)을 충족 — 목록 찜/필터(`ee390d2`), 상세 찜/액션 링크/상태 버튼(`8bb8010`), 홈 포스터 찜 버튼(34px)만 WCAG 2.5.8 예외로 기록(`8bb8010`, **사용자 승인 대기**).
- **Gate C**: 홈에서 상세까지 두 번 이내 주요 선택으로 이동 가능(섹션 순서 조정으로 회귀 없음) · 찜과 방문 예정이 서로 다른 라벨·색·위치의 독립 요소로 렌더되고 각각 다른 성공 문구 표시(`44cef98`, 요소 존재 여부로 판정) · 방문 완료 후 기록 작성으로 바로 이동 가능(`5202514`) · 저장/상태 변경 후 결과와 다음 위치가 보임(토스트, `44cef98`).

## 판단 사항
- CTA 이중 primary: `5202514`에서 방문 완료+공식 URL 동시 보유 이벤트가 본문에 1차 스타일 버튼 2개(공식 링크+기록 남기기)를 동시 노출하는 것을 자체 발견해 보고, QA 판정(§4.1)에 따라 `fee492c`에서 공식 링크를 2차로 강등해 해소.
- 커밋 입도: 최초 5커밋으로 구현 후 사용자 방침(가능한 한 잘게, 혼자 테스트 통과+혼자 revert 가능한 단위)에 따라 `git reset --mixed`로 로컬 미푸시 히스토리를 10커밋으로 재구성. 재구성 전후 `git diff`로 최종 산출물이 바이트 단위로 동일함을 확인 후 진행.

## 검증
`uv run pytest -q` 전체 스위트 프레시 실행(1162 passed, 20 deselected 무회귀 확인, 각 커밋 시점마다 반복) + `uv run pytest -m e2e -o addopts='' tests/e2e/ -q`(20 passed) + 오케스트레이터 브라우저 실측(320~390px, 홈/목록/상세) + `.docs/frontend-integration-changelog.md` 기록.

## 하지 말 것 / 범위 밖(별도 승인 대기)
3단계(아카이브 명칭·`INTEREST_LABEL`→"찜"·직접 등록 폼 단계화·스태프 모바일 테이블) · 홈 포스터 찜 버튼(`.poster-interest`) 34px→44px 확대(WCAG 예외로 보류, 확대 여부 별도 승인 필요) · 개인화 홈 섹션(§17 Deferred).

---
---

# 모바일 우선 상용 디자인 1단계 — 출시 차단 문제 : **1단계 구현·검증 완료** (2026-07-10, 브랜치 `feat/mobile-design-phase1`)

> **8커밋 전부 로컬 브랜치 반영, PR 대기**: `4457452`(인증 셸 갭) · 검증만(브랜드 잔재 0건) · `0d11c12`(홈 팬 넘침 1차) · `5fe5c0d`(고정 CTA 조건부 노출) · `b010d0a`(스태프 모바일 탭) · `b14e444`(드래프트 라벨 1차) · `a497554`(팬 클램프 뷰포트 기준 정정) · `f7234ed`(pending 리터럴 정정) · `7ed70cd`(팬 클램프 회전 보정). 각 커밋 전 `uv run pytest -q` 전체 스위트 **1158 passed, 15 deselected** 무회귀 재확인, 브라우저 실측(Chrome DevTools, 320/360/375/390/1440px) 완료. 상세 변경·검증 기록은 `.docs/frontend-integration-changelog.md` 참조.
> 승인 근거: `.docs/plans/2026-07-10-mobile-first-commercial-design-improvement-plan.md` §15 1단계, §19 사용자 결정(v2.2 — 6건 중 5건 확정: 1단계 구현 단위 승인, 아카이브 명칭 승인, `INTEREST_LABEL`→"찜" 확정, Google OAuth 후순위 이동·1단계는 실패 경로만, 개인정보처리방침·이용약관·문의 채널 별도 트랙). frontend TDD-exempt — AGENTS.md Frontend Work Policy에 따라 자동 테스트 대신 수동 브라우저 검증.

## 범위 (§15 1단계)
1. 인증 셸: Google OAuth 미설정 시 버튼·구분선 숨김(`google_oauth_configured` context processor) + allauth 기본 `socialaccount/login.html`(무스타일 중간 확인 화면)을 기존 인증 셸(`auth.css`/`.auth-container`)로 오버라이드. 성공 경로(자격 등록·`.env`·redirect URI)는 §19-4로 후순위 이동, 이번 범위 제외.
2. 브랜드 표기 잔재(과거 프로젝트명·임시 도메인) 전수 확인 — 검증만, 0건.
3. 모바일 홈 히어로 카드 팬 가로 넘침 제거 — 고정 px 좌표(`carousel.js` REST_X/PART)에 뷰포트·카드 회전 폭 기준 scaleX(0~1 clamp) 적용.
4. 상세·기록장 고정 CTA가 본문 CTA와 무조건 동시 노출되던 문제 — IntersectionObserver로 원본 CTA가 화면 밖일 때만 표시.
5. 스태프 콘솔 모바일 탭 글자 깨짐 + "사이트로 돌아가기" 링크가 탭 스크롤 영역을 가리는 문제 — CSS 스코프 수정 + column 분리.
6. 드래프트 상태 라벨(칩·안내 문구) raw enum(pending/approved/rejected) 노출 — 기존 하드코딩 한글 라벨로 최소 수정(vocab 단일 출처화는 §17 보류).

## 수용 기준 (§10 Gate A/B/D 1단계 항목)
- **Gate A**: Google 로그인 취소/실패가 브랜드 셸 안에서 끝나고 미설정 시 버튼 숨김(`4457452`) · 헤더/푸터/인증/이메일/OAuth 동의 화면 서비스명 `takulife` 일치(검증) · 사용자 화면에 내부 코드(slug/enum) 미노출, 드래프트 상태 칩 포함(`b14e444`+`f7234ed`).
- **Gate B**: 320px 이상 페이지 수평 스크롤 없음, `document.body.scrollWidth <= window.innerWidth`로 판정(`0d11c12`+`a497554`+`7ed70cd`, 320/360/375/390px 실측) · 고정 CTA가 본문·폼·오류·토스트를 가리지 않음(`5fe5c0d`, 상세·기록장 양쪽) · 긴 텍스트가 레이아웃을 늘리지 않음(회귀 없음 확인).
- **Gate D**: 스태프 모바일 탭이 단어 단위로 읽힘(`b010d0a`) · "사이트로 돌아가기" 링크가 탭 스크롤 영역을 가리지 않음(`b010d0a`, §7.6) · 대기/승인/반려 상태 한글 표시, 일괄 승인 직후 칩 텍스트 포함(`b14e444`+`f7234ed`).
- Gate B의 44px 탭 타겟(2단계) · Gate C 전체(2단계) · Gate D 최근 처리 내역(3단계)는 이번 1단계 범위 밖.

## 판단 사항 — 팬 클램프 2회 추가 정정
최초 구현(`0d11c12`)은 계획서 §14 "구현 시 회귀 유의 지점"(고정 px 상수가 뷰포트를 모른다)을 해결했으나, 클램프 기준을 트랙 자체 폭으로 잡아 데스크톱에서도 항상 압축되는 새 회귀가 생겼다(`a497554`로 정정: 뷰포트 가장자리 기준으로 변경). 뷰포트 기준으로 바꾼 뒤에도 카드 회전(`center*REST_ANGLE`)으로 인한 실제 수평 extent를 반영하지 않아 375px에서 여전히 소폭 넘침이 남았다(`7ed70cd`로 정정: 회전 고려 half-extent 적용). 세 커밋 모두 브라우저 실측 기반 지시로 별도 커밋 처리, 히스토리 재작성 없음.

## 검증
frontend TDD-exempt — 각 커밋 전 `uv run pytest -q` 전체 스위트 프레시 실행(1158 passed, 15 deselected 무회귀 확인) + 브라우저 실측(오케스트레이터, Chrome DevTools 뷰포트 에뮬레이션) + `.docs/frontend-integration-changelog.md` 기록.

## 하지 말 것 / 범위 밖(별도 승인 대기)
2단계(홈 섹션 순서·카드 정보 위계·상세 상태 변경 피드백) · 3단계(아카이브 명칭·`INTEREST_LABEL`→"찜"·직접 등록 폼 단계화·스태프 모바일 테이블) · Google OAuth 성공 경로(§19-4, 사용자 액션 선행 필요) · vocab 단일 출처화(§17).

---
---

# 드래프트 운영 개선 — 콘솔 가시성·버그 + 검수 루프 UX + 소스 발굴 (plan of record)

> 작성일: 2026-07-08 · 절차: PO·UX·QA 3종 병렬 검토 → tech-lead 적대 검증(파일:행 실측) → 사용자 승인. 사용자 결정: 소스는 **"기준 있는 발굴 → 불합격 시 동결"**, 승인 후 흐름은 **권고안 (A)**.
> 전제: 1인 관리자 일상 운영. 범위 밖: celery/스레드/락/진행률 UI(확정 배제) · 소스 관리 UI(소스 0~1개 동안) · LLM 전 경로 · 반려 취소·연속 0건 카운터(소스 가동 후 백로그).
>
> **진행 상태**: PR-D1 **#101 머지**(e79d0d0) · PR-D2 **#102 머지**(249c943 — 검수 UX 5항목 + 후속 카드 통일 3건: 드래프트 카드 이벤트 카드와 폭 일치(707→1094px)·요약 카드 3열 "N건"·대시보드 요약 hero 내부·모바일 3열 1행) · **Phase 3 실측 완료 → 동결 결정(아래)**.

## Phase 3 실측 결과: **후보 전원 불합격 → 수집 동결 유지** (2026-07-08)

리서치(웹) + curl 실측(robots/목록/상세 각 1회, 저볼륨) 5곳 전원 탈락:

| 후보 | 목록 URL | 탈락 사유(실측) |
|---|---|---|
| 애니메이트 이벤트 보드 | animate-onlineshop.co.kr/board/list.php?bdId=event | robots `/board/` Allow·이벤트 전용·최고 밀도(진행 9건)였으나 **상세 링크가 `javascript:gd_btn_view()` — 정적 href 없음**. 파이프라인은 URL 합성 불가 → 구조적 탈락 |
| 대원미디어 news-event | daewonmedia.com/board/news-event | robots 전체 허용·정적·최신순이었으나 **표본 10건 중 이벤트 3~4건**(IR·사업뉴스 6~7건 — 기준 ④ 오탐 ≤1 대폭 미달) + **상세 og:title 사이트명 고정**("대원미디어" — 전 드래프트 제목 오염) |
| 유희왕 이벤트 보드 | yugioh.co.kr/board/board_list.php?b_category=event | 이벤트 전용·정적·최신순이었으나 **상세 og:title/title 사이트명 고정** + 본문이 내비/CSS 노이즈(콘텐츠 이미지 추정) + 저밀도·협소 |
| 미디어캐슬 cinema/notice | mediacastle.co.kr/cinema/notice | robots Allow·정적·제목 양호했으나 **2023-11 이후 게시 중단(죽은 보드)** + og:title 고정 |
| 아니플러스 storeCollaboCafe | aniplustv.com/storeCollaboCafe | **React SPA 셸(정적 앵커 0)** — CSR 확정, 기존 판정과 일관 |

**구조적 발견 2건**(모든 후보에 공통 — 향후 확장 판단 재료):
1. 한국 커머스/게시판 상세의 og:title이 **사이트명 고정**인 경우가 지배적 → 상세 기반 제목 추출이 구조적으로 약함. 해소하려면 "목록 앵커 텍스트를 제목 후보로 병행 추출" 확장 필요(현재는 상세만 추출).
2. 고도몰류 게시판은 상세 링크가 javascript 함수 → "URL 템플릿 합성" 확장 없이는 최고 품질 소스(애니메이트)도 사용 불가.

**결정: 수집 파이프라인 동결 유지**(`DRAFT_DISCOVERY_ENABLED=False`, 소스 0). 주 운영 경로 = 콘솔 "URL로 드래프트 생성"(수동) + PR-D2 검수 루프. **재개 트리거**: ① 합격 기준 4종을 충족하는 신규 정적 소스 발견 ② 배포 착수(§4-6 정기 실행 수단 결정과 동시 재평가) ③ 사용자가 파이프라인 확장(목록 앵커 제목 추출 + URL 템플릿 합성 — 애니메이트 unlock 조합)을 승인하는 경우 — 이 확장은 스코프 확대라 별도 계획·승인 필수.

## PR-D1 — 콘솔 운영 가시성 + 버그 수정 (브랜치 feat/staff-console-visibility)
1. **감사로그 라벨 9종 수정**(실배포 버그 — event_* 5종+draft_discover가 "홈 카테고리 변경"으로 오표기): staff/views.py에 한글 `ACTION_LABELS` dict(QUALITY_WARNING_LABELS와 동형) + 로우빌더로 action_label 부착. `get_action_display()` 금지(영문 라벨 + test_staff_console.py:169-182가 한글 단언). 대상 컬럼 target_event 표시 + **staff/queries.py select_related에 "target_event" 필수(N+1)**. event_delete는 SET_NULL이라 "-" 수용.
2. **405 데드엔드 해소**: staff_draft_discovery_run의 @require_POST 제거 → 뷰 본문 GET이면 dashboard redirect(flag-off 분기와 동일 패턴). test_run_get_not_allowed 405→302 갱신. 타 @require_POST 뷰는 스코프 밖.
3. **last_error·stale 노출**: 대시보드 소스 표에 오류 배지+사유, stale 경고. 파생 상태는 뷰 로우빌더, 임계는 settings 상수 `DRAFT_SOURCE_STALE_HOURS` 1개만.
4. **"마지막 실행" 요약**: 버튼 근처 표시. 데이터는 StaffActionLog 최신 DRAFT_DISCOVER의 created_at(소스별 last_checked_at max 아님 — 소스 0건이어도 정확).
5. **success 메시지 스타일 분리**: base.html 3분기(success 추가) + base.css `.site-message-success`(--mint-soft/--mint-ink). **공개+스태프+계정 전체 파급되는 공유 크롬 변경** — PR 설명에 명시.
6. **활성 소스 0건 프리체크**: drafts/queries.py에 `enabled_draft_sources_exist()` 헬퍼(staff→drafts는 허용 방향, 경계 테스트 확인됨) → 뷰가 실행 전 단락: flag-off와 동일하게 info 메시지+커맨드 미실행+감사로그 미기록. stdout 파싱 기각.

## PR-D2 — 검수 루프 UX
7. 대시보드 "검토 큐로 이동" → `/staff/drafts/?status=pending`.
8. **승인/반려 후 흐름 (A)**: draft.js 승인 성공 시 1.5초 setTimeout+reload 제거 → 성공 패널 지속(기존 "행사 #N 보기" 링크는 이미 구현돼 있으나 auto-reload가 지워버리는 상태) + 쿼리 보존 "목록으로" 링크. 반려는 즉시 목록 복귀(data-list-url, ?status 보존 — detail.html 상단 링크가 이미 보존).
9. raw_text 높이: `#raw-text-full`에만 max-height+overflow-y:auto(공용 .raw-box p 금지).
10. 생성폼 `<details><summary>` 기본 접힘(닫혀도 JS 바인딩 정상·e2e 무영향 실측). JS 토글 금지.
11. **반려 사유 입력(optional)**: detail.html textarea(pending만) + draft.js JSON body `rejection_reason` + 뷰 `request.data.get("rejection_reason","")` → 서비스 전달. **default "" 필수**(test_staff_draft_actions.py:158 계약). populated 케이스 신규 TDD.

## Phase 3 — 소스 발굴 (운영 절차, 코드 0 — PR-D1 후 권장: last_error 노출이 관찰 도구)
합격 기준 4종: ① robots 허용 ② 이벤트 전용 목록/피드(전체 사이트맵 배제) ③ 신규순 정렬 ④ 시험 표본 오탐 ≤1건. 후보 2~4곳 타임박스 실측(로컬 플래그 on + admin 등록 → "지금 수집" → 품질 판정 → 합격만 enabled). 전부 불합격 시 동결 명시 결정 + 재개 트리거(신규 소스 발견·배포 착수) 문서화.

## 테스트 영향(실측 완료)
갱신 1건: test_run_get_not_allowed(405→302). 유지 계약 3건: home_categories 한글 라벨 / null actor·target "-" / rejection_reason=="". e2e 중 승인/반려/생성폼/수집 흐름 타는 것 없음.

## 검증(각 PR)
백엔드 red-green TDD → 전체 pytest(베이스라인 1123)+e2e 무회귀 → 브라우저 클릭스루(데스크톱/모바일) → .docs/frontend-integration-changelog.md 기록.

---
---

# 콘솔 수집 실행 버튼 : **완료** (2026-07-08, PR #100 머지, main 1f5f033)

> 작성일: 2026-07-07 · 사용자 확정: **동기 실행 버튼**. discover_drafts를 터미널 수동 실행 대신 콘솔 대시보드에서 POST로 실행.
> 범위: `POST /staff/draft-discovery/run/`(POST only, @staff_console_required) → `call_command('discover_drafts')` 동기 호출(stdout 캡처) → 요약을 messages로 표시(성공/부분 실패 CommandError 구분). 대시보드 수집 소스 패널에 "지금 수집" 버튼 — `DRAFT_DISCOVERY_ENABLED=False`면 비활성+안내(플래그·소스 활성화는 별도 운영 판단). 감사로그 `draft_discover`(14자) 추가. celery/스레드/락 금지(동시 실행은 v2 문서화된 허용 리스크), 신규 JS 0.
> 한계 문서화: 동기 실행이라 소스·후보 수에 비례해 응답 지연(로컬 스모크 1소스 12초). 배포 시 웹서버 타임아웃과 §4-6 정기 실행 수단 결정에서 재평가.

---
---

# 게시 이벤트 CRUD + 품질 드릴다운 : **전체 완료** (2026-07-07)

> **3PR 전부 main 머지**: PR-E1 #97(목록+드릴다운) → PR-E2 #98(수정+감사 확장, 게이트에서 필터 유실 버그 발견·수정) → PR-E3 #99(생성+게시 토글+조건부 삭제, main 7c18526). 전체 1116 passed(시작 베이스라인 1038 → +78). 각 PR 브라우저 E2E(생성 필드 에러·수정 저장·토글·2단계 삭제·참조 차단 서버 거부 실측).
> 통합 가이드 `.docs/staff-events-guide.md` 신설(화면 지도·운영 흐름·설계 결정 — 삭제 가드는 staff/services.py 경유 필수).
> 잔여(소): StaffActionLogAdmin target_event 미노출 · 삭제 로그 제목 스냅샷 없음(의도) · malformed date blank 처리.
> 아래는 계획 원문(아카이브).

> 작성일: 2026-07-07 · 배경: 대시보드 품질 경고가 count 전용(드릴다운 없음), 승인 후 게시 이벤트는 수정 경로 자체가 없음(admin 미등록 — shell뿐). 사용자 결정: **기본 CRUD 필수** + **D = 게시 내리기 기본, 하드 삭제는 아카이브 참조 0건일 때만**(archive FK 3종이 CASCADE라 사용자 방문기록 연쇄 삭제 위험 — 참조 존재 시 건수 명시 차단).
> 기능 단위 커밋 · PR 단위 머지 · **각 PR 완료 시 .docs 문서화 필수**(사용자 지시).

## PR-E1 — R: 목록 + 드릴다운
- 백엔드(TDD): 품질 경고 5종 count 쿼리를 predicate 쿼리셋 공유 구조로 확장 → 경고별 대상 목록 조회(events/queries.py)
- `/staff/events/` 목록 뷰(@staff_console_required): 게시 이벤트 페이지네이션(기존 pager) + `?warning=` 화이트리스트 필터 + 게시 상태 필터
- 대시보드 품질 경고 행 → 드릴다운 링크, 콘솔 셸 4번째 탭 "이벤트 관리"

## PR-E2 — U: 수정
- 백엔드(TDD): `update_published_event` — 기존 불변식 재사용(제목 blank·official_url 필수), unique 충돌 필드 에러
- StaffActionLog 확장: `target_event` FK(SET_NULL) + event 액션 choices (마이그레이션 1)
- `/staff/events/<id>/edit/` SSR 폼(GET/POST-PRG), 포스터는 기존 set/clear_event_poster 재사용

## PR-E3 — C + D: 생성 · 삭제
- C: `/staff/events/new/` — 초크포인트 `create_published_event` 재사용(대체 구현 금지)
- D: unpublish↔재게시 토글 + 조건부 하드 삭제(아카이브 참조 3종 합 0건일 때만) — TakuConfirm 재사용, 전 액션 감사로그

## 하지 말 것
DRF 신규 API(SSR 폼 충분) · RBAC(백로그 유지) · 아카이브 CASCADE 변경 · 일괄 편집 · 이벤트용 별도 앱.

## 검증(각 PR)
백엔드 TDD red-green · 전체 pytest·e2e 무회귀 · 브라우저 클릭스루 · changelog + **.docs 문서화**.

---
---

# 스태프 독립 콘솔 셸 : **전체 완료** (2026-07-07)

> **2PR 전부 main 머지**: PR-C1 #95(셸 분리 — base.html 블록화·base_staff·_console_shell·staff-shell.css + 4템플릿 마이그레이션) → PR-C2 #96(밀도 보정·일괄 툴바 sticky·필터 쿼리 보존·고아 CSS 정리, main 22750fe). 각 PR 전체 1038 passed + 브라우저 실측(임시 스태프 계정·시드 데이터 생성→삭제, 데스크톱 1440/모바일 390, 크롬 상호 유출 0, sticky·쿼리 보존·XSS 폴스루 computed 단언).
> 잔여 없음. 사이드바(1안) 전환은 콘솔 항목 6개+ 시 — _console_shell.html 파셜 교체만으로 가능.
> 아래는 계획 원문(아카이브).

> 작성일: 2026-07-07 · 절차: 현 스태프 UI 인벤토리(Explore) + 콘솔 레이아웃 레퍼런스 리서치(web-ux-ui-designer) 병렬 → **사용자 확정: 2안(상단바 2단 탭)**. 기능 단위 커밋 · 큰 기능 단위 PR.
> 배경: 스태프 4화면(대시보드·드래프트 목록/상세·홈 카테고리)이 공개 사이트 셸(base.html → _site_header/_site_footer)을 그대로 상속 + sub-nav 4곳 복붙 = "페이지 안의 페이지" 이중 크롬. 접근제어(@staff_console_required)·JSON API는 레이아웃과 분리 — 템플릿·CSS 계층만 변경.

## 확정 레이아웃 (2안 — 상단바 2단 탭)
- 1단 topbar: "takulife 스태프 콘솔" + [사이트로 돌아가기 ↗]. 2단 탭: 대시보드/드래프트 관리/홈 카테고리(`aria-current` 유지). 모바일: 탭 줄 가로 스크롤.
- 티켓 스텁 토큰 그대로 재사용(신규 색 토큰 0), 장식 시그니처(형광펜·스탬프·티켓 칩) 콘솔 미도입. 콘솔 보정은 밀도만.
- 추후 항목 6개+ 시 사이드바(1안) 전환 — 셸 파셜만 교체 가능한 구조로.

## PR-C1 — 셸 분리 (커밋 단위)
1. base.html: `_site_header/_site_footer` include를 `{% block site_header %}`/`{% block site_footer %}`로 래핑(기본값 유지 — 공개 렌더 불변) + `templates/staff/base_staff.html` 신설(헤더 블록→콘솔 topbar+탭 파셜, 푸터→제거) + `components/staff-shell.css`(스킵 링크 포함, 신규 JS 0)
2. 스태프 4템플릿 extends 전환 + sub-nav 복붙 4곳 제거(detail "목록으로" top-action 유지)

## PR-C2 — 콘솔 마감 (커밋 단위)
1. 밀도 보정: staff_console.css·event_drafts.css 스코프에서 카드 패딩·폰트 한 단계 축소(--fs-md/--fs-sm 위주)
2. 일괄 승인 툴바 sticky 승격 + 상세→목록 복귀 필터 쿼리스트링(?status=) 보존

## 하지 말 것
사이드바/오프캔버스(v2) · 접힘 토글·localStorage · 아이콘 세트 · 탭 배지 context processor · 뷰/권한/API 변경 · staff 전용 신규 색 토큰.

## 검증 (각 PR)
frontend TDD-exempt — 전체 pytest(셸 단언 테스트 0건 확인됨)·e2e 15종 무회귀 + 브라우저 클릭스루(데스크톱/모바일) + `.docs/frontend-integration-changelog.md` 기록.

---
---

# UI 전면 리프레시 — "티켓 스텁" : **전체 완료** (2026-07-05)

> **3PR 전부 main 머지**: R1 #91(폰트+토큰 리스킨) → R2 #92(컴포넌트 시그니처) → R3 #93(페이지 마감+포스터 캡션 스트립, main a256d9b). 최종 검증: check 0 · 1038 passed · e2e 15 passed · 브라우저 클릭스루(데스크톱 1720/모바일 390) · 기본색 앵커 전수 스캔 0건.
> 접근성 확정: `--brand #d8432a` 유지(대형/UI 3:1 충족), 흰 배경 소형 텍스트는 `--brand-ink #c13a22`(5.39:1) 이원화 — PO 확정. `--end-ink #64686e`(4.75:1) 조정.
> 잔여 후속 정리 완료(#94, main 03d44ae, 2026-07-07): nav.css 블루 잔재 2건 토큰화(hover 섀도 → --brand RGB, group-label → --muted) + 미스냅 h1 3곳(archive/event_detail/auth) → `--fs-xl`(1.75, PO 확정) 통일 + 모바일 `--fs-xl-mobile` companion. 전체 1038 passed. **UI 리프레시 잔여 소진**(다크모드만 범위 밖).
> 아래는 계획 원문(아카이브).

> 작성일: 2026-07-05 · 절차: 현 UI 인벤토리(Explore) + 디자인 리서치(web-ux-ui-designer, 3방향) → 시안 3종 제작 → **사용자 확정: A(티켓 스텁) 베이스 + B 글린트 + C 폰트 예산·형광펜 하이라이트 + 카드 슬라이더 규칙 유지**. 확정 시안: https://claude.ai/code/artifact/2a02b322-7226-440b-8b56-b818f7c3dd3d
> 범위: **공개 페이지 전체**(홈·행사 목록/상세·아카이브·auth). 스태프 콘솔은 범위 밖(공용 토큰 변경의 자연 수혜만). 깊이: **비주얼 리프레시**(CSS 중심, 마크업 소변경은 포스터 캡션 1곳). 다크모드 범위 밖(토큰 구조만 도입 가능하게).

## 0. 디자인 시스템 확정값
- **팔레트**: paper `#F5F6F8` · surface `#FFFFFF` · ink `#1C222E` · muted `#5B6472` · line `#DDE1E8` · **accent(스탬프 레드) `#D8432A`**(hover `#C13A22`) · **하이라이트 라임 `#D8FF3D`**. 상태 4종: 진행중 `#DFF3E6/#1F7A44` · 예정 `#E4EAFB/#33488F` · 종료임박 `#FBEBD2/#9A5B12` · 종료 `#ECEDEF/#6B6F76`. 카테고리 6색 기존 유지.
- **색 역할 규칙(강제)**: 레드 = 브랜드 점·nav 활성 밑줄·NEW 배지·1차 CTA·찜 hover·스탬프 전용, **상태색으로 사용 금지**. 라임 = **텍스트 하이라이트 전용**(페이지당 1~2곳, 카드/버튼/배경 확장 금지 — 클리셰 가드).
- **타이포**: Pretendard 셀프호스팅(Variable woff2, OFL — 추가 유료/대형 폰트 없음) + 숫자·날짜·D-day는 시스템 모노(`ui-monospace` 스택, `tabular-nums`) `.mono-num` 유틸. 난립한 font-size(0.74~0.95 사이 10여 종)를 **6단 스케일로 재정렬**: 0.75 / 0.8 / 0.875 / 0.95 / 1.125 / 1.75(모바일 1.375)rem.
- **형태**: radius — 카드·패널 10px, 버튼·입력 8px, 칩 티켓 탭 `4px 999px 999px 4px`, pill 999px. 그림자 언어 단일화: 카드 플랫(1px line)+hover 보더 진하게, hero·히어로티켓만 큰 소프트 섀도.
- **시그니처**: ①절취선+펀치 노치(목록 카드 타일-본문 경계 세로, 포스터 카드 이미지-캡션 경계 가로 — CSS 원형 의사요소, mask 미사용) ②글린트 ✦(카드 hover/focus-within만, reduced-motion 시 비활성) ③스탬프 "공식 확인"(행사 상세 1곳 한정) ④형광펜(홈 히어로 "한눈에" 1곳으로 시작).
- **포스터 카드 캡션(필수 수리)**: 스크림 위 흰 글자 → **절취선 아래 불투명 캡션 스트립**(밝은 포스터 대비 리스크 구조적 해소). `_poster_card.html` 마크업 소변경. **캐러셀/hscroll 동작·구조·JS는 그대로**(카드 내부 스킨만 교체).

## 1. PR 분할 (수직 3 PR, 각각 독립 머지)
### PR-R1 — 폰트 + 토큰 기반(전역 리스킨의 토대)
- `static/fonts/PretendardVariable.woff2` 추가(+OFL 라이선스 고지 주석), base.css `@font-face`+`font-display:swap`+스택 갱신.
- tokens.css 신 팔레트·타입 스케일 변수·radius/shadow 토큰 정착. 컴포넌트 CSS에 산재한 하드코딩 리터럴(포커스 `#92b4ff`, 세컨더리 텍스트 `#334862` 계열, 상태버튼 테두리, 그라디언트) 토큰 참조로 스윕.
- 기대: 기존 마크업 그대로 새 팔레트로 렌더. 전체 pytest + e2e 무회귀.
### PR-R2 — 컴포넌트 시그니처
- 칩(티켓 탭 radius)·버튼·헤더(nav 액센트 밑줄)·pill 계열 형태 교체. 절취선/노치(.event-card 세로 · 카드류 가로). 글린트 유틸+적용. `.hl` 형광펜 유틸+홈 히어로 1곳. 스탬프(상세 헤더).
- reduced-motion 가드, focus-visible 유지.
### PR-R3 — 페이지 마감
- `_poster_card.html` 캡션 스트립 전환(마크업+home.css — 캐러셀 규칙 불변). event_list/event_detail/archive/auth 페이지 CSS를 신규 스케일·토큰으로 정리.
- 검증: 대비 AA 스팟체크(액센트 텍스트 사용처·캡션), 브라우저 클릭스루(홈 캐러셀 스와이프·필터·찜·아카이브), 스크린샷 기록.

## 2. 검증(각 PR 공통)
frontend TDD-exempt — 단 전체 pytest(뷰 렌더 테스트 포함)·Playwright e2e 15종 무회귀 + `node --check` + 브라우저 클릭스루(chrome-devtools) + `.docs/frontend-integration-changelog.md` 기록. JS 동작 변경 0(캐러셀·필터·찜·일괄승인 그대로).

## 3. 하지 말 것
새 JS 프레임워크/빌드 도입 · 마크업 구조 변경(포스터 캡션 제외) · 라임을 배경/버튼으로 확장 · 레드를 상태색으로 사용 · 스탬프 반복 노출 · Gmarket Sans 등 추가 웹폰트 · 다크모드(이번 범위 밖) · staff 콘솔 전용 스킨 작업.

---
---

# 드래프트 파이프라인 v2 — 자동 발견(무LLM) : **전체 완료** (2026-07-05)

> **6PR 전부 main 머지**: 선행 #84(테스트 .env 격리) → PR-1 #85(fetch+robots) → PR-2 #86(DraftSource+추출기) → PR-4 #87(게시 title 불변식) → PR-3 #88(discover_drafts 커맨드) → PR-5a #89(일괄 승인 백엔드) → PR-5b #90(검수 UX). 최종 1038 passed(시작 베이스라인 872, 신규 166).
> 실 소스 스모크 완료: 파이프라인 메커니즘 전부 실증(557 발견→10 생성+547 보류·robots·페이싱·격리). 소스 판정: aniplus items(CSR·lastmod 고정)·atzip(단축링크 오탐) disabled 유지, animate 실 URL 미확정 — **실효는 소스 큐레이션이 후속 운영 과제**.
> `DRAFT_DISCOVERY_ENABLED=False` 유지(정기 실행 수단은 배포 착수 시 결정 — §4-6). 잔여 수동 검증: web-checklist 시나리오 4·5·7·8.
> 아래는 계획 원문(아카이브).

---

# 구현 계획: 드래프트 파이프라인 v2 — 자동 발견(무LLM) (plan of record)

> 작성일: 2026-07-04 · 1R: 4종 병렬 오케스트레이션(PO·LLM자동화·아키텍처·보안) → PO 종합 → 사용자 4결정 반영
> 2R(설계 재검토, 같은 날): 4종 적대 검증(계획-코드 정합성·QA 시나리오·인프라 실현성·보안 반영도) → 결함 20여 건 반영. 주요 반영: 실행 환경 전제 명시(§2-0)·robots 구현 명세 강제(§2-2)·DNS 완화 우선순위 역전(§2-3)·XML 파싱 안전(§2-4)·PR-4 회귀 명시·PR-5 분할(백엔드 TDD 분리).
> 판정: **LLM API 비용 예외 불허(확정)** → v2 = 휴리스틱 기반 자동 발견 + 게시 불변식 + 검수 UX. LLM 관련 전부(프리필 ON·캘리브레이션·auto-approve) 비용 정책 변경 시까지 연기.

## 0. 한 줄 결론
운영자 시간의 1차 병목은 승인 클릭도 추출도 아닌 **소스 발견(완전 수동)**이므로, v2는 실측 완료된 무료 소스를 읽는 `DraftSource` + `discover_drafts` 커맨드로 신규 URL을 자동 인입(항상 PENDING, 사람 승인 유지)하고, 게시 초크포인트의 제목 구멍을 막는다. LLM은 비용 불허로 전 경로 보류 — 추출은 휴리스틱 그대로.

## 1. 사용자 결정 (2026-07-04 확정)
1. **LLM API 비용 예외 = 불허**: 프리필 ON·실 API 스모크·캘리브레이션·Sonnet 에스컬레이션 전부 보류. `DRAFT_LLM_EXTRACTION_ENABLED=False` 유지, 키 미설정 유지. 코드(core/llm, llm_extraction)는 머지된 상태로 동결 — 제거하지 않음.
2. **발견 산출물 = 바로 드래프트 생성**: 후보 큐 화면 없이 신규 URL을 기존 `create_draft_from_url`로 직접 투입(항상 PENDING). 실행당 상한으로 큐 범람 제어.
3. **게시 게이트 = 2계층 분리**: 공유 초크포인트(`create_published_event`)에는 불변식만(제목 blank/placeholder 차단), 완비성 게이트는 자동승인 전용으로 분리(v3).
4. **auto-reject v2 포함 → 결정론적 대체(한계 명시)**: 사용자가 선택한 LLM is_event 기반 auto-reject는 결정 1(LLM 불허)과 충돌(is_event가 LLM 산물)이라 **발견 단계 결정론 필터**(자기도메인·SNS·이미지·utm 제거 + `DraftCreationEmptyExtractionError` 스킵)로 대체. **한계(2R QA)**: 이 필터는 URL 패턴만 보므로 정상 제목·본문을 가진 비이벤트 페이지(카테고리 목록·일반 상품 상세 등)는 통과해 드래프트가 될 수 있다 — v2에서는 **허용된 잔여 리스크**로 두고 PR-3 스모크에서 오탐률을 관찰, 검수 부담으로 측정되면 §4-5(URL 경로 패턴 배제) 발동. LLM auto-reject 원안은 비용 정책 변경 시 복원.

## 2. 핵심 설계 결정 (1R 종합 + 2R 반영)

### 2-0. 실행 환경 전제 (2R 인프라 — BLOCKER 해소 조항)
- **배포 인프라는 현재 미구현**이다(Docker/Render는 2026-06-10 설계 문서만 존재. Dockerfile·render.yaml·GitHub Actions 전무, project-status.md "planned but unimplemented"). 따라서 **v2의 범위는 "코드 완성 + 로컬/수동 실행"까지**이며, "하루 1~2회 정기 실행"은 배포 작업이 완료되어야 이행 가능한 제품 약속임을 명시한다.
- **정기 실행 수단은 배포 착수 시 사용자 결정**(§4-6): (a) Render Cron Job — 웹 서비스와 별개 과금 리소스로 **비용 정책("배포서버·DB만") 해석에 사용자 승인 필요**, (b) GitHub Actions cron — 무료이나 프로덕션 DB 시크릿 이중화·외부 DB 접속 허용 여부·공유 러너 IP 평판(봇 차단) 리스크, (c) 수동 실행 — 추가 비용 없으나 "자동 발견"의 효용 일부 상쇄. non-zero exit를 사람에게 전달할 채널(cron MAILTO·Actions 실패 알림 등)도 이 결정과 함께 확정.
- 그전까지 `discover_drafts`는 운영자가 로컬(docker-compose Postgres)에서 수동 실행한다. 플래그 상수는 코드 상수이므로 배포 후 킬스위치가 "커밋+재배포"임을 인지(배포 게이팅 시 고려).

### 2-1. 모듈 배치·스키마
- 신규 앱 금지. `DraftSource` 모델은 `drafts/models.py`, 링크 추출기는 `drafts/discovery.py`(순수 함수, DB 무의존), 커맨드는 `drafts/management/commands/discover_drafts.py`. rss/sitemap/html 3유형은 **모듈 상수 dict 디스패치**(클래스/ABC/레지스트리 금지).
- `DraftSource` 스키마 최소: `name`·`url`·`source_type`(TextChoices: rss/sitemap/html)·`enabled`(기본 False)·`link_selector`(CharField blank, html용)·`last_checked_at`(null)·**`last_error`(TextField blank — 2R QA: CharField면 긴 예외 문자열이 Postgres DataError로 격리 자체를 깨뜨림. `rejection_reason` 관례 준수)**. JSONField 설정 스키마 금지. 실행당 상한은 settings 상수.
- **초크포인트 재사용(대체 금지)**: 발견된 URL은 반드시 기존 `create_draft_from_url` 경유 — SSRF 재검증·크기 제한·source_url UNIQUE 중복·휴리스틱 추출 전부 재사용. **provenance(2R): 커맨드는 `create_draft_from_url(url, source_name=source.name)`으로 호출** — source_name이 발견 출처의 유일한 기록(FK 추가 안 함). 목록 fetch도 `fetch_html` 코어를 `allowed_content_types` 파라미터화로 확장(별도 fetch 구현 금지). 리스팅 fetch 후 후보별 재fetch의 이중 fetch는 의도적 허용(캐싱 금지).
- **스킵 예외 명칭(2R 정합성)**: 커맨드 경계에서 잡는 빈 콘텐츠 예외는 `EmptyExtractionError`가 아니라 **`DraftCreationEmptyExtractionError`**(create_draft_from_url이 래핑함, services.py:103-107). 문자 그대로 전자를 잡으면 CSR/빈 페이지가 에러로 오집계되어 상시 false alarm.

### 2-2. robots.txt·크롤 에티켓 (구현 명세 강제 — 2R 보안·QA)
- **`RobotFileParser.read()`/`set_url()` 사용 금지.** robots.txt는 **가드된 fetch 코어로 바이트를 직접 수신**(5s 타임아웃·크기 캡·SSRF 검증 상속)한 뒤 `RobotFileParser.parse(lines)`로 주입한다. `read()`는 타임아웃 없는 urllib 페치라 프로세스 무한 행(hang) + SSRF 가드 우회 — 두 결함을 동시에 만든다.
- **실패 방향 확정: fail-closed.** robots.txt 404 = 전체 허용, 타임아웃/5xx = 해당 호스트 이번 실행 스킵. `last_error`에 "robots 페치 실패"와 "robots disallow"를 **구분 기록**(운영자가 일시 장애 vs 크롤 금지를 판별 가능해야 함).
- **후보 URL 호스트별 can_fetch 필수**: robots 체크는 목록 URL 1회로 끝나지 않는다. `create_draft_from_url` 호출 **전** 각 후보 URL에 대해 캐시된 `can_fetch(candidate_url)` 통과 필수 — can_fetch는 경로별이고(목록 Allow ≠ 상세 Allow), atzip류 후보는 아예 다른 호스트다.
- per-host 요청 간 상수 지연(sleep)·Crawl-delay 존중. User-Agent에 연락처 표기(`TakuLifeBot/1.0 (+운영 URL)` — 공개 연락 URL 확보는 운영 선결). 무인증 익명 요청만·차단 우회 금지·로그인 뒤 콘텐츠 금지(여기어때-야놀자·사람인-잡코리아 판례 수칙).

### 2-3. SSRF·DNS rebinding (우선순위 역전 — 2R 정합성·보안)
- httpx는 공개 DNS 훅이 없어 "검증 IP 핀닝(커스텀 transport)"은 TLS SNI/인증서 검증과 충돌하는 고난도 작업 — 1R의 "핀닝 1차" 판정은 과대평가였다. **역전: 1차 완화 = (a) `fetch_html` 내부 per-hop resolver 검증을 회귀 테스트로 고정(제거 금지 — 이것이 권위 SSRF 게이트, 선검증은 resolver 없이 DNS를 건너뜀) + (b) 배포 게이트에 링크로컬/메타데이터(169.254.0.0/16) egress 차단을 릴리스 차단 항목으로 등재**(앱 레벨 `is_link_local` 차단은 이미 존재 — TOCTOU 창의 백스톱). IP 핀닝은 §4-7 best-effort로 연기.
- 잔여 리스크 수용 근거: fetch 대상은 운영자가 등록한 DraftSource(사실상 allowlist), 항상 사람 승인, TOCTOU는 sub-second DNS 플립을 요구하는 좁은 창.

### 2-4. XML 파싱 안전 (2R 신규 발견 2건)
- **`xml.etree.ElementTree` 직접 파싱 금지 → `defusedxml`**(무료 경량 의존성) 사용. 신뢰불가 RSS/sitemap의 엔티티 확장 공격(billion laughs)은 1MB 크기 캡으로 못 막는다(수 KB 페이로드가 메모리에서 GB로 확장 — 배치 DoS).
- **str/인코딩 선언 함정**: `fetch_html`은 디코딩된 **str**을 반환하는데, `<?xml version... encoding="UTF-8"?>` 선언이 있는 str을 `fromstring`에 넣으면 `ValueError`. 파서는 fetch 출력(str)을 명시적으로 처리(re-encode 후 파싱)해야 하며, **바이트 픽스처 단위 테스트만으로는 이 결함이 안 잡힌다** — PR-3 스모크는 실 fetch→parse 경로를 반드시 통과시킬 것(주력 스모크 소스인 aniplustv sitemap이 정확히 이 경로에서 깨지는 케이스).
- 1MB 캡의 sitemap 충분성 미검증: 스모크에서 실 sitemap 바이트 크기 기록, 근접/초과 시 리스팅 전용 상수 분리(조용한 `ResponseTooLargeError` 영구 무산출 방지).

### 2-5. 신뢰성·관측 (1인 운영 — 2R 카운트 시맨틱 확정)
- 소스 단위 + URL 단위 이중 try/except 격리(`eval_extraction` 행 격리 패턴), `last_error` 기록, 부분 실패 시 non-zero exit(CommandError — 이 코드베이스 첫 선례임을 인지).
- **요약 카운트 정의**: "발견 N"은 **상한 적용 전 후보 총수**. 상한 도달 시 "상한 도달로 K건 보류" 별도 라인(조용한 유실 방지 — 백필 47건 중 10건만 처리되고 37건이 무기록 소실되는 시나리오 차단). 스킵 사유별(dup/robots 불허/robots 페치 실패/empty) 구분 출력.
- **같은 실행 내 소스 간 동일 URL 충돌 = 정상 스킵**(exit code 영향 없음): 사전 exists 체크(상태 무관 — REJECTED도 source_url 보존)를 빠져나가도 UNIQUE + `DraftCreationDuplicateError`로 안전. 이를 에러로 집계하면 상시 false alarm.
- **상한 이원화**: 드래프트 생성 상한(`DRAFT_DISCOVERY_MAX_PER_RUN=10`)과 별개로 **소스당 후보 fetch 시도 상한** — 후보 다수가 empty 스킵될 때 10건 채울 때까지 무제한 재fetch하는 증폭(에티켓 위반) 차단.
- enabled 소스 0개 → "활성 소스 없음" 명시 메시지 + exit 0. 동시 실행(수동+cron 겹침)은 데이터 안전(UNIQUE)하나 대상 사이트 중복 요청 유발 — **허용 리스크로 문서화**, 실행 락 도입 안 함(robots fail-closed+타임아웃으로 hang 원인 자체를 제거하는 것이 선결).
- 플래그: `DRAFT_DISCOVERY_ENABLED`(settings 부울, 기본 False — 기존 하드코딩 상수 컨벤션 일치 확인됨). celery/redis/헤드리스 브라우저 금지 유지.
- 경계 테스트 확장: `drafts/discovery.py`·`discover_drafts.py`를 staff/archive 금지 파라미터에 추가. discovery.py의 events import 금지는 **신규 어서션**(기존 drafts-wide 금지 테스트는 없음 — services.py가 events.services를 정당하게 import하므로 discovery.py에만 스코프).

## 3. v2 단계 (수직 6 PR — 2R에서 PR-5 분할)

### PR-1 — fetch 확장 + robots (파이프라인 미연결)
- `fetch_html`에 `allowed_content_types` 파라미터(기본 현행 유지, XML 계열 opt-in). 크기/리다이렉트/SSRF 코어 재사용 + **per-hop resolver 검증 존재를 회귀 테스트로 고정**.
- `drafts/robots.py`(가칭): §2-2 명세 그대로 — 가드된 fetch로 바이트 수신 → `parse(lines)` 주입, fail-closed, 사유 구분. TDD(허용/불허/404 허용/타임아웃·5xx 스킵).
- UA 연락처 갱신. DNS rebinding은 §2-3(코드 변경은 회귀 테스트 고정뿐, egress 차단은 배포 게이트 등재).

### PR-2 — DraftSource 모델 + 링크 추출기 (미연결)
- `DraftSource` 모델(§2-1 스키마, last_error=TextField) + 마이그레이션 + Django admin 등록.
- `drafts/discovery.py`: `extract_links_rss/sitemap/html` 3 함수 + dict 디스패치 + 잡링크 결정론 필터. **defusedxml 사용(§2-4)** + fetch_html str 출력 처리 명시. html은 `link_selector` 적용(BeautifulSoup 재사용). 고정 픽스처 TDD — 단 **str 입력(인코딩 선언 포함) 케이스 필수 포함**.
- 경계 테스트 확장(§2-5). **로컬 Postgres 검증 1회**(docker-compose db + DATABASE_URL에서 migrate + 스모크 — PG CI 잡이 없어 수동 게이트, 기록 남길 것).

### PR-3 — discover_drafts 커맨드 (플래그 게이트)
- enabled 소스 순회 → 목록 robots 체크 → 목록 fetch → 링크 추출·필터 → 사전 exists 중복 제거 → **후보별 robots can_fetch** → 신규만 `create_draft_from_url(url, source_name=source.name)`(생성 상한 + fetch 시도 상한, 이중 격리) → `last_checked_at`/`last_error` 갱신 + §2-5 시맨틱의 요약 출력.
- TDD: 신규만 생성·중복(사전 exists/실행 내 교차 소스 둘 다)·불안전·robots 불허/페치 실패 구분 스킵·한 소스 실패 비전파·양 상한 준수·`DraftCreationEmptyExtractionError` 스킵·enabled 0개 처리·카운트 시맨틱.
- **실 소스 수동 스모크**: aniplustv sitemap·animate board 대상, **실 fetch→parse 경로**(픽스처 아님)로. 기록 항목: sitemap 실 바이트 크기(1MB 캡 대비), 목록의 신규순 정렬 여부(§2-5 보류분 재발견 가정 검증), 오탐(비이벤트 드래프트) 건수. atzip은 결정론 필터 정밀도 관찰 후 enabled 판단 — **기준: 스모크 표본에서 타도메인·비이벤트 유입 0 확인 전 기본 False 유지**(서드파티 본문이 official_url을 유도 가능하므로 사람 승인 시 URL 육안 확인이 신뢰 경계).

### PR-4 — 게시 불변식 (2계층 중 초크포인트분)
- `create_published_event`: `title` blank 또는 `title == official_url`(정규화: 공백·트레일링 슬래시 무시 수준까지만 — 근접 변형 전반은 범위 밖 명시) 시 신규 `PublishEventError` 하위 예외로 거부. red-green.
- **기존 테스트 회귀 명시(2R)**: `test_staff_can_approve_pending_draft`(tests/test_staff_draft_actions.py:32 — 제목 정보 없는 드래프트 승인이 현재 200) 등 blank-title 승인 케이스가 깨진다 — "placeholder 드래프트는 승인 전 제목 입력 필요"로 테스트 갱신. `approve_draft`의 `or draft.source_url` 제목 폴백은 이 불변식 이후 도달 시 항상 실패하는 죽은 경로가 되므로 **제거**(또는 유지 시 사유 주석).
- **에러 매핑 3계층 배선**: 신규 예외를 `drafts.services`에서 포괄 `PublishEventError` 캐치보다 먼저 전용 캐치 → staff 뷰에서 400 + "제목을 입력해야 게시할 수 있습니다" 필드 에러로 표면화(기존 포괄 경로는 불투명한 503 — 데이터 문제를 서버 장애처럼 보이게 함). 위반 시 드래프트 PENDING 보존(PR #75 패턴).

### PR-5a — 일괄 승인 백엔드 (TDD — 2R에서 분리: 상태 전이+게시는 프론트 아님)
- 신규 일괄 승인 엔드포인트(staff): **건별 독립 트랜잭션, 부분 성공 허용**, 응답 `{succeeded: [...], failed: [{id, reason}]}` 집계. 사람이 선택한 id 목록만 처리(자동 선택 금지).
- TDD: 혼합 결과(중간 1건 중복 official_url/이미 승인됨/PR-4 불변식 위반) 시 나머지 정상 처리 + 실패 사유 반환, 감사로그 성공건별 기록.

### PR-5b — 검수 UX 프론트 (TDD-exempt)
- 드래프트 상세: `raw_text` 300자 절단 → 전체 보기 토글. **서버 렌더 오토이스케이프 유지 또는 JS textContent만 — `innerHTML`·`|safe` 금지**(2R 보안: 현재 XSS는 오토이스케이프로 방어 확인됨, 이 토글이 유일한 회귀 위험점). `extraction_method` 표기.
- 목록: 다중 선택 → PR-5a 엔드포인트 호출, 부분 실패 표기("3/5 성공" + 실패 사유), 실패 건 선택 유지. 필수필드 미비 건 시각 표시.
- staff 대시보드에 소스별 "마지막 수집 N시간 전" 신선도 표기(한계 인지: 커맨드가 돌지 않으면 갱신도 안 됨 — 실패 감지의 완결은 §2-0 실행 수단 확정에 종속).
- 수동 클릭스루 검증 + `.docs/frontend-integration-changelog.md` 기록.

## 4. DEFERRED (트리거 명시)
1. **LLM 전 경로 재개**(프리필 ON·실 API 스모크·원제안 스냅샷 계측·confidence 캘리브레이션·is_event auto-reject·atzip LLM 2차 추출): 트리거 = 사용자가 LLM API 비용 예외 승인(추정 월 $5~9, 최악 $30 미만). 코드 동결 보존. 재개 시 선결 = `update_draft` 원제안 덮어쓰기 계측 공백 해소(스냅샷 보존) + `is_event_confidence` 스키마 추가.
2. **자동 승인(v3)**: 트리거 = LLM 재개 AND 날짜·제목 precision ≥99%(스냅샷 기반 라벨 N≥약 150) AND 자동분 격리/롤백 staff UI. 설계 확정분: 완비성 게이트 `drafts/gating.py` 순수 함수, 오케스트레이터 `staff/services.py`(outer-atomic 감사로그), `approve_draft(actor=None)`(모델 변경 불요 — reviewed_by·actor 이미 null=True), `auto_approved`+`AUTO_APPROVE` 추가, `extraction_method=="llm" ∧ confidence≥τ` 필수, title/summary grounding 보강.
3. **popply**(DB권)·**X/인스타**(확정 배제)·**shop.aniplustv CSR**(empty 스킵 손실이 유의미할 때)·**URL 정규화 dedup**(utm 중복이 부담으로 측정될 때)·**sitemap index/gzip**(실측 소스가 요구할 때).
4. **크롤 콘텐츠 XSS 전수 재점검**: 트리거 = 자동 수집량 급증(현재는 오토이스케이프 방어 확인됨 — |safe/mark_safe/autoescape off 부재 grep 검증, 2026-07-04). `create_draft_from_fields`는 자체 스킴 검증 없이 호출자(promotion.py) 의존 — 두 번째 호출자 등장 시 가드 필요.
5. **URL 경로 패턴 기반 목록/카테고리 페이지 배제**(2R QA): 트리거 = PR-3 스모크·운영에서 비이벤트 드래프트 오탐이 검수 부담으로 측정될 때(§1-4 잔여 리스크의 해소 수단).
6. **정기 실행 수단 확정**(2R 인프라): 트리거 = Docker/Render 배포 착수. Render Cron Job(유료 — **비용 정책 해석 사용자 승인 필요**) vs GitHub Actions cron(시크릿 이중화·러너 IP 평판) vs 수동 운영. 실패 알림 채널 동시 확정. **소스별 "링크 0건 연속 N회" 경고**(link_selector 실효 상실 = 가장 현실적인 조용한 무력화)도 이때 함께.
7. **DNS rebinding IP 핀닝**(best-effort): 트리거 = 배포 후 egress 차단이 불가한 인프라로 판명될 때.

## 5. 검증·배포 게이트
- 백엔드 전부 TDD red-green. PR-5b만 TDD-exempt + 수동 검증. 구현은 PO 주도 오케스트레이션(senior-dev-codex 코딩, tdd-expert·qa·security 게이트) — 각 PR 착수 전 이 문서가 설계 근거.
- **배포 착수 시 필수 사전 점검(v2 범위 밖, 등재만)**: 클린 Postgres에 전체 마이그레이션 이력 처음부터 재생 + `migrate --check` 게이트(기존 백로그) + 링크로컬/메타데이터 egress 차단 확인(§2-3 릴리스 차단 항목) + §4-6 실행 수단 결정.

## 6. 하지 말 것 (오버엔지니어링 가드)
신규 Django 앱 · 소스 추상화 클래스/전략 레지스트리 · DraftSource JSONField 설정 · celery/redis/django-tasks · 헤드리스 브라우저 · URL 정규화 프레임워크 · 룰 엔진식 게이트 · `raw_llm_response` 선제 저장 · fetch 계층 범용 리팩터 · LLM 기반 중복 자동 병합 · 실행 락 매니저 자작(§2-5 허용 리스크 문서화로 대체).

---
---

# 이전 계획 (완료·아카이브)

## 드래프트 LLM 자동화 v1 (프리필) — 완료 (2026-07-03 계획, 3PR #72~#74 + 리뷰 후속 #75 전부 머지)
- v1 = LLM 프리필만(자동 게시 아님). Haiku 구조화 추출 + grounding(vocab enum 주입·evidence 스팬)·인젝션 방어(`<untrusted_page_content>` 구분자)·휴리스틱 폴백·동기 10s 타임아웃. `core/llm` 인프라 어댑터 + `drafts/llm_extraction.py` 함수 스왑. `extraction_method`/`confidence` 필드 + `eval_extraction` 커맨드.
- 플래그 `DRAFT_LLM_EXTRACTION_ENABLED=False` 유지. **실 API 스모크 미실행 → 2026-07-04 비용 불허 결정으로 보류 확정**(v2 §4-1).
- 당시 DEFERRED(자동 승인·게시 게이트 강화·소스 자동 수집)는 v2 계획에 흡수·재판정됨.

## Staff Console v1 (수직 3 PR) — 완료
- PR-1a 셸·PR-2 검수 귀속+감사로그(#69)·PR-3 home-categories 흡수(#70) 머지. 품질경고 5종 count·SessionAuth 고정·2-tier 게이트 반영. 후속 /staff/drafts/ 상태필터+페이지네이션(#71) 머지.
- 연기 백로그: 품질 드릴다운·공식제보 큐·게시이벤트 관리·4역할 RBAC(첫 비superuser 채용 시)·감사 스냅샷(인시던트 시)·axes 락아웃 복구는 내장 커맨드 런북.

## 인증 하드닝 — Phase A(allauth #66)·B1(rate limit+axes #67)·B3(Google 소셜 #83) 완료, B2(MFA) 보류. [[auth-hardening-backlog]]
## 아카이브 라이브 검색·개인 아카이브 — 다수 PR 머지. [[archive-search-filter]]·[[personal-archive-feature]]
