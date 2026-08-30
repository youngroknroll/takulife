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
"재구성 불가"가 아니라 순수히 **줄 수 예산** 문제다. 아래 목록은 PR #331부터 #187까지다.
그보다 오래된 PR은 `gh pr list --state merged --limit 300 --json number,title` 으로
언제든 다시 조회할 수 있다.

---

## 최신 PR

### PR #330 — feat: SEO 최적화 — robots 해제·sitemap·페이지별 메타·JSON-LD·noindex (트랙 16)

**무엇을 바꿨나**: robots.txt를 크롤링 허용으로 전환(비제품 4경로
`/admin/`·`/api/`·`/accounts/`·`/staff/`만 차단 + Sitemap 위치 안내),
`web/sitemaps.py` 신설로 정적 공개 페이지와 공개 행사 상세를
sitemap.xml에 노출 — contrib sitemap 뷰의 DB `Site` 의존은 래퍼가
`RequestSite`를 직접 주입해 우회하므로 도메인이 요청 Host를 따른다.
페이지별 메타 제목·설명·canonical 조립을 배선하고, 행사 상세에 Event
JSON-LD(presenters 순수 함수 + 필드 화이트리스트 + `\uXXXX` 이스케이프)를
실어 meta_description 단일 소스가 메타·og·JSON-LD 세 표면을 공급한다.
비공개 페이지는 noindex 기본값(fail-closed)으로 차단하고 공개 6페이지만
해제 — 기본 블록과 해제를 한 커밋으로 묶어 배포 가능한 중간 상태를 없앴다.

**왜**: 검색 유입 기반 조성. robots 해제는 SMTP 게이트와 분리한다는
2026-08-29 사용자 결정 반영(검색 유입 방문자의 가입 미완은 수용된 상태,
배포 후 확인 절차는 deploy-runbook §3-12).

**검증**: 커밋 7개, 전체 회귀 2364 passed `[실측]`(기준 2325 + 신규 39),
WED·BIR 사후 리뷰 Conforms ×2, QVL 완료 판정 7/7 Passed. 슬라이스 전부
Green인 상태에서 브라우저 라이브 소스 대조가 JSON-LD description 분기
결함을 찾아 트랙 내 즉시 수정(J1u3·J1c).

**병합**: 2026-08-30, main `ad37d68`. production 반영은 #331 deploy PR.

---

## 이전 PR (번호 — 실제 PR 제목)

- #331 — deploy: main → production
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
- #317 — docs: PR #315·#316 머지를 로그에 롤링 반영
- #316 — test: 테스트 시크릿 리터럴 제거 + 스캐너 가드 신설
- #315 — ci: CI 성공 후 main→production deploy PR 자동 생성
- #314 — docs: PR #313 머지를 로그에 롤링 반영
- #313 — fix: 미디어 덮어쓰기·캐시 컬링 해소 + 저위험 스윕 (G1·F10·F13·G4·G5)
- #312 — docs: PR #310·#311 머지를 로그에 롤링 반영
- #311 — docs: 백로그 재작성 — 2026-08-24 실측 기준 최적화
- #310 — docs: PR #307~#309 머지를 로그에 롤링 반영
- #309 — fix: 전수 검토 잔여 프론트 3건 반영 (500 헤더 착시·필수 표시 통일·죽은 캐러셀 제거)
- #308 — fix: 백엔드 잔여 정리 스윕 — 삭제 잠금·부분승격 라벨·EMAIL_PORT·동시 저장 멱등
- #307 — docs: PR #303~#306 머지를 로그에 롤링 반영
- #306 — fix: 전수 검토 확정 결함 2건 반영 (수집처 상한 재검사 + 러너 URL 검증)
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
- #239 — feat(collection): 컬렉션 상세 페이지 신설
- #238 — 행사 상세 페이지 에디토리얼 리스킨 + 관련 행사
- #237 — design(ui): 안내 문구 블록효과 제거 → 브랜드-레드 불릿 통일
- #236 — feat(archive): 방문 상세 페이지 신설 (/archive/visits/<id>/)
- #235 — design(archive): 다녀온 기록 수정 페이지 에디토리얼 리스킨
- #234 — design(archive): 다녀온 기록 작성 페이지 에디토리얼 리스킨
- #233 — feat(archive): 직접 등록 에디토리얼 — 목록 리스킨 + 전용 작성 페이지 신설
- #232 — feat(archive): 내 활동 shell v2 — visits sort, 목록/달력 toggle, mobile layout
- #231 — feat(collection): Rebuild 굿즈 직접 등록 form editorial
- #230 — feat(archive): Unify 다녀온 기록 onto the editorial shell
- #229 — feat(pager): 공용 페이저 블록 창 + 5칸 점프 화살표
- #228 — design(archive): 나의 일정 페이지 에디토리얼 셸 통일
- #227 — fix(archive): 활동 달력 백로그 2건 근본 해결 (has_any_items·검색 DB 하향)
- #226 — design(archive): 활동 달력 에디토리얼 리빌드 + 상단·필터 목록 통일
- #225 — design(queue): 검토 큐 사용자 판정 반영 — 덱 타이밍·메타줄 중복·검색 버튼·토글 정렬·카드 날짜
- #224 — design(archive): Rebuild the activity page for the editorial mock, and unify the pager
- #223 — fix(web): 컬렉션 작품별 색 충돌 제거 + 패싯 컨트롤
- #222 — design(web): 이벤트 달력 아젠다 액션 hover 추가
- #221 — feat(web): 공용 페이지네이션 재구축 — 창 축약 + 점프 화살표
- #220 — design(web): 컬렉션 페이지 에디토리얼 리디자인
- #219 — design(calendar): Align detail actions
- #218 — design(web): Rebuild the events calendar in the editorial v2 style
- #217 — design(home): Tune hero deck timing
- #216 — copy(web): Rename 행사 to 이벤트 across the product
- #215 — design(web): Rebuild the home collection section, center the hero, divide sections
- #214 — design(cards): Remove official badges
- #213 — copy(web): Reword the home hero headline
- #212 — feat: Guard event category/region against out-of-vocabulary values (B1)
- #211 — feat(web): Move sorting from the sidebar to a results-head toggle menu
- #210 — design(web): Rebuild the events list page in the editorial style
- #209 — chore: Scope automated tests to backend logic and delete the e2e suite
- #208 — 리디자인 ④내 활동 · ⑤행사 달력 (로드맵 완결)
- #207 — design(web): Home editorial redesign — stack deck, de-chromed sections, category dots
- #206 — feat(web): Shared shell — notice banner, mobile hamburger, four-column footer
- #205 — design(web): Fix light-mode brand contrast to AA (design-rules §1.4)
- #204 — feat(web): D8 live search result summary live region
- #203 — feat(web): ARIA restoration stage 6 — staff chart text alternative
- #202 — feat: 10-day grace period for account deletion
- #201 — feat: ARIA restoration stage 5 — structural cleanup
- #200 — feat: ARIA restoration stage 4 — carousel and input labels
- #199 — feat: ARIA restoration stage 3 — disclosure expanded/controls sync
- #198 — feat: ARIA restoration stage 2 — toggle state, focus-based feedback
- #197 — feat: ARIA restoration stage 1 — modals, toast, shell labeling
- #196 — feat: Calendar accessible names, search box, mobile filter fold
- #195 — Logging coverage: observability for irreversible and security-relevant actions
- #194 — feat: Dual calendar (events + activity) with activity history
- #193 — Error handling and logging policy: guards and retro fixes
- #192 — fix: Close bfcache duplicate-creation gap (client_token + commit markers)
- #191 — docs(agents): Add commit-per-feature, PR-per-stage cadence
- #190 — test: Stage 4·5 authoring guards + dedup + TS-INF-04
- #189 — test: Korean behavior-scenario test suite + execution speed infra (stages 1-3)
- #188 — feat: Collection-first home snapshot (H-1/H-2)
- #187 — feat: Restructure top navigation to target IA (Target IA-2)
