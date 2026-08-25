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
"재구성 불가"가 아니라 순수히 **줄 수 예산** 문제다. 아래 목록은 PR #319부터 #177까지다.
그보다 오래된 PR은 `gh pr list --state merged --limit 300 --json number,title` 으로
언제든 다시 조회할 수 있다.

---

## 최신 PR

### PR #320 — feat: 소셜 가입 약관 동의(B2) + 헤더 인증 버튼 폰트 정렬

**무엇을 바꿨나**: 소셜 가입 경로에 약관·개인정보처리방침 동의를 강제 —
`accounts/forms.py`에 `TermsAgreementFormMixin`을 신설해 일반·소셜 가입
폼이 동의 필드와 `terms_agreed_at` 증적 기록을 공유하고,
`SOCIALACCOUNT_FORMS` 등록 + `SOCIALACCOUNT_AUTO_SIGNUP=False`(allauth
기본값 true면 신규 소셜 유저가 가입 폼을 건너뜀)를 계약 테스트로 고정.
트랙 중 발견한 소셜 가입 엔드포인트 레이트리밋 부재(보안 F1)도 같은
트랙에서 해소 — `config/urls.py` 선등록 `SocialSignupView`(url name
`socialaccount_signup` 유지). 프론트는 소셜 가입 화면 `form.as_p`를
명시적 필드 렌더로 교체(전역 input 규칙이 체크박스를 깨뜨림), 두 가입
화면 동의 블록 동일화 + 에러 시 aria 연결 추가, 헤더 로그인/회원가입
버튼을 주 메뉴와 동일한 0.92rem·44px로 통일.

**왜**: 백로그 B2(OAuth 활성화 차단 항목) 해소. Google 로그인을 켜기 전
동의 없는 가입 경로와 무제한 제출 경로를 함께 닫아야 활성화가 안전하다.

**검증**: TDD 4 시나리오 전부 기대 사유 Red→Green(레이트리밋은 stash
왕복으로 실효성 재확인), 전체 회귀 2308 passed `[실측]`, 헤더
69px==토큰(721~1440px 1줄)·에러 aria·라벨 링크 비토글 브라우저 실측,
WXD·BIR 이중 리뷰 모두 Conforms. 실 Google OAuth 왕복 1회는 크리덴셜
설정 후 수동 검증으로 남음(backlog B2 잔여).

**병합**: 2026-08-26, main `25635af`.

---

## 이전 PR (번호 — 실제 PR 제목)

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
- #186 — feat: Promote collection routes to top level (Target IA-1)
- #185 — feat(archive): Record collection item analytics events
- #184 — feat(archive): Add collection page (list, create, edit, delete)
- #183 — feat(archive): Add collection SSR query layer
- #182 — feat(archive): Add CollectionItem CRUD API
- #181 — fix(archive): Guard status creation against visit record drift
- #180 — feat(archive): Retire the GOODS kind into CollectionItem (PR-C4)
- #179 — feat: Collection track C3 — visit completion orchestration
- #178 — feat: Collection track C2 — goods boundary enforcement
- #177 — feat: Collection track C1 — CollectionItem model and invariants
