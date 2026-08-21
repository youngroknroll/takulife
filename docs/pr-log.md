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
"재구성 불가"가 아니라 순수히 **줄 수 예산** 문제다. 아래 목록은 PR #298부터 #165까지다.
그보다 오래된 PR은 `gh pr list --state merged --limit 300 --json number,title` 으로
언제든 다시 조회할 수 있다.

---

## 최신 PR

### PR #299 — feat: 로컬 에이전트 수집처 탐색 (서버 경계 + 로컬 러너)

**무엇을 바꿨나**: `docs/BE/draft-source-agent-discovery.md` 승인 계약의 구현.
서버에 drafts 소유 모델 3종(SourceDiscoveryRun·SourceCandidate·
DiscoveryRunnerStatus), 실행 수명주기(`discovery_runs`: heartbeat 신선도
120초·임대 1800초·재임대 상한 2회·FOR UPDATE claim), 후보 결정론 검증
8단계(`candidate_validation`: 네트워크는 트랜잭션 밖, 저장은 재잠금+임대
재검증), X-Runner-Token 러너 API(빈 토큰 사전 거부, 스로틀 60/분, 공개
OpenAPI 제외), 스태프 탐색 요청 경로와 대시보드 패널 2개를 추가했다.
로컬에는 Django 무의존 `local_runner/`(폴링 루프 + Claude Code 어댑터,
`claude -p --output-format json --tools "WebSearch,WebFetch"`)를 추가했다.

머지 전 사용자 검토 5건 반영: 표본-목록 연관성 검사(sample_mismatch 단계
신설), 임대 900→1800초 + 유효 제출마다 갱신 + 에이전트 실행 중 heartbeat
스레드, 러너 5xx 지수 backoff·409 시 제출 중단과 complete 생략, 시그니처
게이트에 candidate_validation 등록, 문서 정정. 머지 직전 3역할(보안·운영·
QVL) 사후 재검토는 차단 0건이었고, 잔여 위험 4건(표본 URL 정규화 오탐,
제출 국면 heartbeat 미커버, backoff·ticker 테스트 부재, create_run 직렬화
자동검증 한계)은 `docs/BE` Known gap에 기록한 뒤 사용자 승인으로 머지했다.

**왜**: 새 수집처 발굴을 서버 LLM API 비용 없이 개인 맥의 로컬 에이전트로
수행하고, 서버는 에이전트 보고를 신뢰하지 않고 결정론 재검증만 믿는다.

**검증**: 전체 회귀 `uv run pytest -q` → **2253 passed**(26.03초) `[실측]`,
`manage.py check` 0 issues, 마이그레이션 드리프트 0건, 뮤테이션 왕복 6종
전부 Red, 러너 실기동 왕복(403/204 → claim → 실패 격리 → complete) 실측,
FE 이중 게이트 WED·BIR 모두 Conforms. CI 3잡 전부 pass.

**병합**: 2026-08-21, main `cbdf9c5`. PR #298 위 스택이라 #298을 먼저
머지한 뒤 base를 main으로 바꿔 순차 머지했다.

---

## 이전 PR (번호 — 실제 PR 제목)

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
- #176 — docs: Stage-0 T7/T8 — deploy runbook and event operations criteria
- #175 — feat: Stage-0 PR-0e — shared cache and analytics events
- #174 — feat: Stage-0 PR-0d — proxy-aware client IP resolution
- #173 — ci: Stage-0 PR-0c — GitHub Actions pipeline
- #172 — feat: Stage-0 PR-0b — runtime artifacts (Docker, gunicorn, media storage, health)
- #171 — feat(config): 0단계 배포 기반 PR-0a — settings 프로덕션 하드닝
- #170 — fix: 다크모드 4/4 — 대비 전수 감사(1152 조합) + 실결함 4건 보정
- #169 — feat: 다크모드 3/3 — 페이지별 스윕 + 게이트 수정
- #168 — feat: 다크모드 2/3 — 공용 컴포넌트 스윕 + 헤더 토글
- #167 — feat: 다크모드 1/3 — 토큰 다크 매핑 + 테마 인프라
- #166 — chore: FE 부채 스윕 + 허브 라벨 체계 정리 + 모바일 D-day 포스터 배지
- #165 — feat: 홈 슬라이더 모바일 [2,2] + 행사 둘러보기 포스터 그리드
