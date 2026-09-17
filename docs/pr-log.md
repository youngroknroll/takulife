# PR 로그

## 이 문서에 대하여

머지된 PR을 시간순으로 기록하는 **롤링 이력 문서**다. 다음 세 문서와 역할이 다르다.

- `docs/backlog.md` = 지금 무엇이 남았는지, 다음에 뭘 해야 하는지 — 살아있는 현재 상태
- `docs/BE/`·`docs/FE/`(·`DB/`) = 특정 주제가 지키는 가드레일을 말하는 기술 기록
- 이 문서 = **과거에 무엇이 언제 머지됐는지**의 시간순 목록. 교훈·회고는 담지 않는다
  (그 정본은 에이전트 메모리이며, 여기 옮겨 적지 않는다)

**형식은 롤링이다.** 가장 최근 머지된 PR 한 건만 상세히 적고(무엇을·왜 바꿨는지, 검증
결과), 그 이전 PR은 번호와 실제 PR 제목만 남긴다. 새 PR이 머지되면 방금 "최신"이었던
항목을 한 줄로 줄이고, 새 PR을 상세 항목으로 올린다(`AGENTS.md` "Document post-work
state" 절 참고).

한 줄 요약은 손으로 다시 쓰지 않는다. `gh pr list --state merged --limit 300 --json
number,title -q '.[] | "\(.number) — \(.title)"'` 출력을 그대로 옮긴다 — 제목 앞의
`feat:`/`fix:`/`docs:` 같은 접두어도 변경 성격을 알려주는 정보이므로 유지한다.

이 문서는 200줄을 넘기지 않는다. 머지된 PR 289건(`gh pr list --state merged`, 2026-08-17
`[실측]`)이 전부 들어가지 않으므로 최신부터 채우고 줄 수 예산에서 끊는다 — 컷오프는
"재구성 불가"가 아니라 순수히 **줄 수 예산** 문제다. 아래 목록은 PR #373부터 #240까지다.
그보다 오래된 PR은 `gh pr list --state merged --limit 300 --json number,title` 으로
언제든 다시 조회할 수 있다.

---

## 최신 PR

### PR #373 — feat(home): 홈 히어로 아래 이벤트 달력 섹션 (트랙 34)

**무엇을 바꿨나**: 홈 히어로 바로 아래에 이벤트 달력 섹션을 추가했다. 왼쪽 월
격자는 날짜 칸에 그날 진행 중인 행사의 카테고리 점만 표시하고(중복·빈 값 제외,
칸당 최대 4종), 앞뒤 달 채움 칸에는 점을 그리지 않는다. 범례는 그 달에 실제로
등장한 카테고리만 어휘 순서로 보여준다. 오른쪽 선택일 아젠다는 기본이 오늘(다른
달이면 1일)이고 최대 3건과 전체 건수, "이 날짜의 이벤트 N개 모두 보기 ›" 링크를
담는다(상한은 사용자 지시로 5건에서 3건으로 줄였다 — 2열에서 달력 아래 빈 여백).
날짜 칸·‹ 오늘 › 이동은 `?month=`·`?date=` 서버 렌더이며 행사 달력과 같은 파서를
쓰고, 잘못된 값은 오류 표시 없이 이번 달·오늘로 조용히 복귀한다. 이동 후
아젠다 카드로 스크롤·포커스가 옮겨간다. 반응형은 56.25rem 이하 1열(달력 위,
아젠다 아래), 45rem 이하 칸형 모바일 격자. 다크 모드는 새 CSS 색 전부 디자인
토큰(리터럴은 오늘 배지 글자 `#fff` 1곳)이다. 로그인 홈은 히어로 → 내 컬렉션
현황 → 이벤트 달력 순서(컬렉션 현황을 먼저 보여달라는 사용자 지시), 비로그인은
히어로 바로 아래가 달력이다. 같은 PR에서 계획 밖 같은 유형 결함 2건도 고쳤다:
행사 달력 선택일 영역에 `tabindex="-1"`·`scroll-margin-top`·포커스 링 제거를
더해 날짜 이동 후 포커스가 선택일로 오게 했고, 빠져 있던 콘서트 카테고리
점·바 색 규칙을 토큰 색으로 채웠다. 커밋 12개 `[실측 gh]`, 머지 2026-09-17
06:03Z `716fe90d`. 가드레일 정본 `docs/FE/home-event-calendar.md`.

**왜**: 디자인 핸드오프(claude.ai/design "Takulife index page mockups" 안 1b)를
서버 렌더로 옮겨 홈에서 바로 이번 달 행사를 훑고 날짜별 아젠다를 볼 수 있게
한다. 행사 달력·콘서트 색 수정은 이 트랙의 날짜 이동·색 규칙과 같은 유형
결함이라 별도 이연 없이 같은 PR에서 처리했다(사용자 상시 결정).

**검증**: `uv run pytest -q` → **2927 passed, 10 deselected**(이전 기준선 2905
대비 +22 `[계산]`, 신규 테스트 22건), `check` 0 issues, `makemigrations --check`
무변경. Test List HC-01~HC-17을 사이클마다 기대 사유 Red → Green으로 밟았고,
첫 실행이 Green이던 3건은 임시 뮤테이션으로 Red를 확인한 뒤 원복했다. 브라우저
(Chrome DevTools MCP, 로컬 dev 서버) 확인: 1280·901px 2열, 900px 1열 전환,
390px 모바일까지 가로 오버플로 0, 라이트·다크 computed 색이 토큰과 일치, 날짜
클릭 후 포커스가 아젠다 카드로 이동, 콘솔 오류 0건. 홈 비로그인 GET 쿼리
7건 → 8건(+1) `[실측 CaptureQueriesContext]`. WED·BIR 사후 판정 모두 Conforms.
머지 후 main `716fe90d` 재측정 `[실측 2026-09-17]`: `uv run pytest -q` → **2927
passed / 10 deselected / 84.81초**(이전 기준선 2905 대비 +22 `[계산]`), `check`
0 issues, `makemigrations --check` 무변경; main CI run 35188306747 success.

## 이전 PR (번호 — 실제 PR 제목)
- #372 — docs: PR #370 머지를 로그에 롤링 반영 + 회귀 기준선 재측정
- #371 — deploy: main → production
- #370 — feat(drafts): 키워드 탐색·서버 수집에 국내·미종료 필터를 넣는다 (트랙 33)
- #369 — docs: PR #363~#367 스택 머지를 로그에 롤링 반영 + 회귀 기준선 재측정
- #368 — deploy: main → production
- #367 — fix: DB 락·트랜잭션 검수 결함 7건 수정 (트랙 32)
- #366 — fix(web): 서버 요청 버튼의 클릭 방지·스피너를 사이트 전역으로 통일한다
- #365 — feat(staff): 카테고리 어휘를 상수에서 DB로 옮기고 슈퍼유저 CRUD 화면을 붙인다
- #364 — feat(staff): 이벤트 목록 정렬·기간·카테고리 필터 — H2 3/3 (트랙 26)
- #363 — docs: PR #336·#355·#357~#361 머지를 로그에 롤링 반영 + 회귀 기준선 재측정
- #362 — deploy: main → production
- #361 — feat: 키워드 탐색 → 판별 → 승인 가능한 드래프트·소스 등록 (트랙 30)
- #360 — deploy: main → production
- #359 — deploy: main → production
- #358 — feat(accounts): 회원 닉네임 도입 — 가입 필수 입력·헤더/마이페이지 표시·백필·변경 화면 (트랙 29)
- #357 — docs: PR #352·#353·#354·#356 머지를 로그에 롤링 반영 + 회귀 기준선 재측정
- #356 — feat(seo): Make the Korean brand name searchable (트랙 28)
- #355 — deploy: main → production
- #354 — test: Reintroduce a journey-based e2e suite (pytest-playwright + live_server)
- #353 — feat(staff): 이벤트 목록 인라인 비공개·재게시·검증 — H2 분할 2/3 (트랙 25)
- #352 — docs: PR #349·#350·#351 머지를 로그에 롤링 반영 + 회귀 기준선 재측정
- #351 — docs(readme): 아키텍처 설계 문서 형식으로 재구성하고 코드와 대조해 정정
- #350 — feat(staff): 이벤트 일괄 비공개 설정 — H2 분할 1/3 (트랙 24)
- #349 — docs: PR #347·#348 머지를 로그에 롤링 반영 + 회귀 기준선 재측정
- #348 — feat: 사용자 제보 드래프트 구분 표시와 제보 폼 공개 고지 — H3 (트랙 23)
- #347 — docs: PR #344·#345·#346 머지를 로그에 롤링 반영 + 회귀 기준선 재측정
- #346 — feat(staff): 대시보드 검수 SLA 지표 — H4 (트랙 22)
- #345 — feat(staff): 반려 드래프트 재오픈 — H5 (트랙 21)
- #344 — docs: PR #341·#342·#343 머지를 로그에 롤링 반영 + 회귀 기준선 재측정
- #343 — feat(staff): 드래프트 admin API 생성·수정 감사 기록 — draft_create·draft_update (트랙 20 H7)
- #342 — test(core): superuser는 shell로만 만든다 — is_superuser 대입 경로 0건 계약 가드
- #341 — docs: PR #339·#340 머지를 로그에 롤링 반영 + 백로그 H1 종결·★3 수용 기록
- #340 — feat(staff): superuser 전용 계정 운영 화면 — is_staff·is_active 목표 상태 지정 + 2단계 확인 + 감사 target_user (트랙 19 H1)
- #339 — docs: PR #338 머지를 로그에 롤링 반영 + 회귀 기준선 재측정
- #338 — docs: 스태프 백오피스 갭 검토 결과 반영과 런북 §5 정정
- #337 — docs: PR #332~#335 머지를 로그에 롤링 반영
- #336 — deploy: main → production
- #335 — harness: 오케스트레이터 계약·어댑터 정비·숫자 태그 훅 (트랙 18)
- #334 — deploy: main → production
- #333 — deploy: main → production
- #332 — docs: 머지 로그·런북 실측 기록 + design(home): 히어로 문구·카테고리 섹션 이동
- #331 — deploy: main → production
- #330 — feat: SEO 최적화 — robots 해제·sitemap·페이지별 메타·JSON-LD·noindex (트랙 16)
- #329 — deploy: main → production
- #328 — refactor: Tidy First 백엔드 구조 정리 6건 + 빈 PATCH 400 거부 (트랙 15)
- #327 — perf: 렌더 차단 요청·네트워크 종속 트리 개선 — 셸 CSS 번들 + 폰트 preload (트랙 14)
- #326 — deploy: main → production
- #325 — perf: Lighthouse 성능 최적화 3건 — 폰트 다이어트·HTML gzip·brotli (트랙 13)
- #324 — docs: 레거시 문서 트리 정리 반영 + 가드레일 기록 승격
- #323 — deploy: main → production
- #322 — fix(staff): 검수 큐 행 클릭 무반응과 표 가로 잘림을 고친다
- #321 — docs: PR #319·#320 머지를 로그에 롤링 반영
- #320 — feat: 소셜 가입 약관 동의(B2) + 헤더 인증 버튼 폰트 정렬
- #319 — docs: 배포 runbook DB를 Supabase 무료 티어로 전환
- #318 — deploy: main → production
- #317 — docs: PR #315·#316 머지를 로그에 롤링 반영
- #316 — test: 테스트 시크릿 리터럴 제거 + 스캐너 가드 신설
- #315 — ci: CI 성공 후 main→production deploy PR 자동 생성
- #314 — docs: PR #313 머지를 로그에 롤링 반영
- #313 — fix: 미디어 덮어쓰기·캐시 컬링 해소 + 저위험 스윕 (G1·F10·F13·G4·G5)
- #312 — docs: PR #310·#311 머지를 로그에 롤링 반영
- #311 — docs: 백로그 재작성 — 2026-08-24 실측 기준 최적화
- #310 — docs: PR #307~#309 머지를 로그에 롤링 반영
- #309 — design: 프론트 잔여 정리 스윕 — 500 헤더 중립화·필수표시 통일·죽은 코드 제거
- #308 — fix: 백엔드 잔여 정리 스윕 — 삭제 잠금·부분승격 라벨·EMAIL_PORT·동시 저장 멱등
- #307 — docs: PR #303~#306 머지를 로그에 롤링 반영
- #306 — fix: 러너 하드닝 — 후보 슬롯 원자 예약 + 비루프백 HTTPS 강제
- #305 — fix(config): 운영 드리프트 정리 — DRAFT_FETCH_CONTACT 배선 + 운영 문서 정정
- #304 — fix(archive): 방문 완료 동시성 직렬화
- #303 — build: 의존성 보안 업그레이드 + CI 취약점 감사 게이트
- #302 — docs: PR #300·#301 머지를 로그에 롤링 반영
- #301 — fix: 에이전트 수집처 탐색 사용자 검토 2라운드 4건 반영
- #300 — docs: PR #296~#299 머지를 로그에 롤링 반영
- #299 — feat: 로컬 에이전트 수집처 탐색 (서버 경계 + 로컬 러너)
- #298 — feat: 드래프트 수집 자동화 활성화 (F6 SSRF 근본 수정 + 플래그 env 전환 + 소스 큐레이션)
- #297 — docs: README를 포트폴리오형으로 전면 재구성
- #296 — docs: PR #294·#295 머지를 로그에 롤링 반영
- #295 — feat(harness): 파괴적 git과 계획서 덮어쓰기를 PreToolUse에서 막는다
- #294 — docs: PR #291~#293 머지를 로그에 롤링 반영
- #293 — chore: .claude 역할 어댑터·훅·프로젝트 설정을 버전 관리에 편입
- #292 — fix(FE): 인증 12화면 셸을 헤더·푸터와 같은 1120px 컨테이너로 정렬
- #291 — docs: PR #289·#290 머지를 로그에 롤링 반영
- #290 — feat(api): OpenAPI 문서화 도입 (drf-spectacular + Swagger UI)
- #289 — docs: PR #287·#288 머지를 로그에 롤링 반영
- #288 — design(home): 홈 히어로를 티켓 스텁 카드로 전환
- #287 — docs: PR #285·#286 머지를 로그에 롤링 반영
- #286 — feat(web): 홈 히어로 타이포 자동 슬라이드 로테이터
- #285 — fix(web): 브라우저 검토 후속 — 어휘 잔재 1건과 keep-all 누락 2건
- #284 — docs: PR #283 머지를 로그에 올리고 낡은 백로그 제목 3건을 닫는다
- #283 — fix: 배포 전 검토가 찾은 실조치 4건을 닫는다
- #282 — feat: 공식 포스터를 걷어내고 행사 화면을 타이포그래피 에디토리얼로 바꾼다
- #281 — refactor: 프레젠테이션 계층을 web 앱으로 분리해 앱 순환을 없앤다
- #280 — chore: 운영·위생 백로그 4건을 닫는다 (F3·F4·F5·F9)
- #279 — docs: 백로그 현재 상태를 main b43957c 기준으로 갱신
- #278 — fix: 조용히 깨질 자리 두 곳을 닫는다 (백로그 A5 잔여 + F8)
- #277 — refactor: 보유·교환 축 술어를 CollectionItem으로 모은다 (백로그 A3 이관분)
- #276 — refactor: core.analytics를 서명 규약 가드에 넣는다 (백로그 A2)
- #275 — feat(staff): 스태프 콘솔을 소비자 셸에서 분리하고 재설계한다
- #274 — refactor: Split archive queries and their tests by domain (E2 + E3)
- #273 — docs: Close E4, E5, and E1 in the backlog
- #272 — refactor: Name the conditions that comments were explaining (E5)
- #271 — style: Close the comment-policy track — missed files and a guard
- #270 — style: Sweep every comment under the rewritten policy
- #269 — style: Bring auth-track comments under the comment policy, and register E4
- #268 — docs: Refresh the status table against the merged tree
- #267 — docs: Fix three claims the post-merge auth review measured wrong
- #266 — design(accounts): Rebuild 12 auth screens as an editorial two-panel layout
- #265 — docs: 탈퇴 계정 파기 정기 실행을 런북 요구사항으로 등록
- #264 — 계정 설정 영역 에디토리얼 리디자인 + 이메일 단일 변경 흐름
- #263 — fix: 활동 달력의 방문·굿즈 중복 표시와 삭제 잔존 제거
- #261 — feat: Close the D group's user-flow gaps (staff console deferred)
- #260 — docs: Defer C1 until there are real users, but settle its definitions
- #259 — test(core): Guard every core module by default, not the six we listed
- #258 — docs: Close A5, and stop entries from going stale the moment they are fixed
- #257 — docs: Make a number in a document say what it counts
- #256 — test(core): Make the domain boundary guards find their own targets
- #255 — feat(archive): Let an unofficial place be opened and corrected
- #254 — Promote the technical records to the tree that survives
- #253 — Replace markup assertions that could not fail
- #252 — Make the 500 test fail for the reason it names, and unbreak the runbook pointer
- #251 — Repair the governance docs, rebuild the backlog, and act on what it measured
- #250 — feat(staff): Add the verify button to the event edit page
- #249 — feat(events): Give readers a way back to ended events
- #248 — feat(events): Default the public listing to ongoing and upcoming
- #247 — feat(events): Flag published events that need re-verification
- #246 — fix(archive): Give photo uploads and place entries an idempotency key
- #245 — fix(collection): Make owned, wanted and tradeable independent axes
- #244 — refactor(css): CSS optimization and accessibility sweep
- #243 — design(errors): Reskin 404/429/500 as editorial
- #242 — feat(core): 마이페이지 에디토리얼 + 비밀번호 변경 시각 추적
- #241 — feat(archive): 찜 목록 에디토리얼 — 내 활동 5탭 이관 완결
- #240 — design(collection): 굿즈 수정 페이지 에디토리얼 + --rose-border 다크 값
