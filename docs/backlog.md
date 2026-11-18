# takulife 백로그

기준일: 2026-11-18 · 기준 브랜치: `main`(`93be2ca1`, PR #421 반영). 백엔드 회귀
기준선은 아래 "현재 상태"의 기준선 표 첫 행 하나에만 적는다. 2026-08-25 기준으로
적힌 항목의 브랜치(`fix/media-overwrite-lowrisk-sweep`, main `e3d3448` 분기)는 머지됐다.

## 이 문서에 대하여

- **폐기**: 시안 기반 백로그 `B1~B29`, 이관 항목 `E1~E8`, 디자인 리뷰 큐
  (`.docs/design-review-queue.md`). 시안을 다시 만들기로 하면서 함께 폐기됐고
  (2026-07-29 사용자 결정), 큐 파일 자체도 존재하지 않는다. **복구하지 마라.**
- **배치**: 이 문서는 `docs/`에 있다. `.docs/`는 git-ignored라 소실된다 —
  디자인 리뷰 큐가 실제로 그렇게 사라졌다. 살아 있는 백로그는 여기 둔다.
- **표기**: `[실측]`은 오케스트레이터가 뮤테이션/프로브 왕복으로 직접 잰 항목,
  `[코드]`는 소스 읽기로만 확인한 항목이다. 확신은 증거가 아니므로 구분한다.
- **정본 소유**: 시간순 이력은 `docs/pr-log.md`, 교훈 정본은 메모리,
  가드레일 상세는 `docs/BE/`가 소유한다 — 이 문서는 현재 상태 인덱스로만 쓴다.

## 현재 상태 (신선 실행 기준)

행 하나는 한 줄이다(2026-11-18 사용자 승인). 상세·이연·검증 수치는 오른쪽 칸의
정본 문서와 `docs/plan-archive/`가 갖고, PR별 이력은 `docs/pr-log.md`가 갖는다.
이 표에 문단을 다시 쌓지 않는다.

### 기준선

| 항목 | 값 |
|---|---|
| 백엔드 회귀 | **4,662 passed** / 83.32초, `uv run pytest -q -n auto` `[실측 2026-11-18, main 93be2ca1]`. 앱 코드 커버리지 98%(8,266문 중 175문 미실행) `[실측 2026-11-18, --cov 앱 패키지 9개]` |
| e2e 여정 | 10 passed / 10.67초, `uv run pytest -q -m e2e tests/e2e` `[실측 2026-11-18, main 8fa6a43f]`. 기본 실행은 `addopts`의 `-m "not e2e"`로 제외. CI `e2e` 잡은 `continue-on-error: true`(관측 기간) `[코드 .github/workflows/ci.yml]` |
| Django check · 린트 | `manage.py check` 0 issues, `ruff check` 통과 `[실측 2026-11-18]` |
| 마이그레이션 드리프트 | 없음 `[실측 2026-11-18, makemigrations --check --dry-run]` |
| 배포 차단 | 0건(체크리스트는 `docs/deploy-runbook.md` §3) |
| 실행 순서 | 1단계(배포) 완료(2026-08-31, takulife.kr) / 2·3·4단계 완료 / **5단계는 실코호트 대기**(C1) / 6단계 미착수 |
| 행사 카탈로그 | 게시 169건 중 146건 종료(86%), 진행·예정 23건 `[실측 2026-08-24]` — 스냅샷이며 현재값 아님(재측정은 운영 DB) |
| OAuth | 활성화 완료(2026-08-26, 실 OAuth 왕복은 사용자 검증) |
| 열린 계획 | **없음**(2026-11-18). `prompt_plan.md`에 있던 절은 모두 `docs/plan-archive/`로 옮겼다. 폐기한 계획은 "착수하지 않는 것" 절 |

### 머지된 트랙

| 트랙 | 상태 | 정본 · 계획 |
|---|---|---|
| 요청 중 피드백(전역) | PR #366 머지(2026-09-15) | `docs/FE/loading-feedback.md` |
| 카테고리 어휘 스태프 CRUD | PR #365 머지(2026-09-15). 공개 화면 잔여는 트랙 59에서 닫힘 | `docs/BE/category-vocabulary.md` |
| 스태프 이벤트 목록 필터(트랙 26) | PR #364 머지(2026-09-15) | `docs/plan-archive/track-26.md` |
| 회원 닉네임(트랙 29) | PR #358 머지(2026-09-10) | `docs/BE/account-identity.md` · `docs/plan-archive/track-29.md` |
| 키워드 탐색(트랙 30) | PR #361 머지(2026-09-12). 이연은 G6 | `docs/BE/draft-source-agent-discovery.md` · `docs/plan-archive/track-30.md` |
| DB 락·트랜잭션 검수(트랙 32) | PR #367 머지(2026-09-15) | `docs/plan-archive/track-32.md` |
| 국내·미종료 필터(트랙 33) | PR #370 머지(2026-09-16) | `docs/BE/draft-source-agent-discovery.md` "트랙 33" 절 · `docs/plan-archive/track-33.md` |
| 홈 이벤트 달력(트랙 34) | PR #373 머지(2026-09-17) | `docs/FE/home-event-calendar.md` · `docs/plan-archive/track-34.md` |
| 드래프트 실행 결과 기록(트랙 35) | PR #376 머지(2026-09-18) | `docs/BE/draft-source-agent-discovery.md` "트랙 35" 절 · `docs/plan-archive/track-35.md` |
| 오류 묶음 기록(트랙 36) | PR #377 머지(2026-09-18) | `docs/BE/error-groups.md` · `docs/operations-runbook.md` §9 · `docs/plan-archive/track-36.md` |
| 운영 데이터 보존 정리(트랙 37) | PR #378 머지(2026-09-18) | `docs/BE/data-retention.md` · `docs/operations-runbook.md` §7.2 · `docs/plan-archive/track-37.md` |
| 어댑터 얇게(트랙 38) | PR 0 #380·PR 1 #382 머지(2026-09-19). 슬라이스 A·B·C는 **폐기** | `docs/plan-archive/track-38.md` |
| 보안 검토 반영(트랙 40) | PR #388 머지(2026-10-04). 상세는 J절 | `docs/BE/security-review-2026-09-27.md` §8 · `docs/plan-archive/track-40.md` |
| 거버넌스 구조 동기화(트랙 41) | PR #389 머지(2026-10-06) | `AGENTS.md` · `docs/plan-archive/track-41.md` |
| UI 다국어(트랙 43-1·43-2·43-3) | PR #395(2026-10-21)·#396(2026-10-22)·#397(2026-10-23) 머지. 번역 검수는 AI만 했고 원어민 검수는 없다. 이연은 K절 | `docs/BE/i18n.md` · `docs/plan-archive/track-43.md`·`track-43-2.md`·`track-43-3.md` |
| 행사 콘텐츠 번역(트랙 44-1) | PR #399 머지(2026-10-27). 번역문은 저장만 되고 공개 화면은 바뀌지 않는다. 44-2·44-3·44-4는 **폐기** | `docs/BE/i18n.md` "행사 콘텐츠 번역(트랙 44-1)" 절 · `docs/plan-archive/track-44.md` |
| 디자인 방향 문서(트랙 50) | PR #408·#409 머지(2026-11-03). 예약 트랙 B~E(51~54)는 **폐기** | `docs/FE/design-principles.md` · `docs/plan-archive/track-50.md` |
| 상태 문서 검토 잔여(트랙 55) | PR #411 머지(2026-11-12). 남은 공백: `git-commit-style-guard`는 `commit` 앞 `-C`·`-c`는 건너뛰지만 그 밖의 전역 `git` 옵션(예: `--git-dir`)은 인식하지 못함 `[코드 .claude/hooks/git-commit-style-guard.sh:65-68]`, F5b 일부 성공 일괄 처리의 공지 | `docs/plan-archive/track-55.md` |
| DB 연결 재사용·공개 캐시(트랙 17) | PR #415 머지(2026-11-13). gthread 워커 전환은 사용자 보류 | `docs/operations-runbook.md` §11 · `docs/deploy-runbook.md` §3-20·§3-21 · `docs/plan-archive/track-17.md` |
| 다크 모드 삭제·모바일 하단 탭 바(트랙 56) | PR #418 머지(2026-11-16) | `docs/FE/design-principles.md` · `docs/FE/mobile-tab-bar.md` · `docs/plan-archive/track-56.md` |
| 간격 역할 토큰(트랙 57) | PR #419 머지(2026-11-16). 가드 `tests/core/test_role_token_contract.py`. 후속으로 적혀 있던 트랙 B는 폐기 | `docs/FE/design-principles.md` · `docs/plan-archive/track-57.md` |
| DOS 형태를 공개 화면 전체에 적용(트랙 58) | PR #420 머지(2026-11-17). 스태프 화면 제외. 잔여는 해결된 항목 표 M행 | `docs/FE/design-principles.md` · `docs/plan-archive/track-58.md` |
| 트랙 58 잔여(트랙 59) | PR #421 머지(2026-11-18). 처리 내역은 해결된 항목 표 M행 | `docs/FE/loading-feedback.md` · `docs/BE/category-vocabulary.md` · `docs/plan-archive/track-59.md` |

production 반영: deploy PR #417 머지(2026-11-18, production `0c0ceed8`)까지 `[실측 gh]`.

### 사용자 확인 대기

코드로 닫을 수 없고 사용자만 확인할 수 있는 항목이다. 확인하면 이 목록에서 지운다.

- 트랙 59: 운영 DB의 카테고리·슬롯 확인(`docs/deploy-runbook.md` §3-22).
- 트랙 17: Supabase 연결 수 그래프, 헬스 체크 간격, 배포 뒤 7일 아웃바운드 기록(`docs/deploy-runbook.md` §3-20·§3-21 가운데 밖에서 잴 수 없는 것).
- 트랙 44-1: 맥 러너 재시작(저장소 main·`uv sync`), `docs/deploy-runbook.md` §3 항목 19(`0009` DB 기본값). 2026-10-27 배포 시점 기준 미수행.
- 트랙 40: `docs/deploy-runbook.md` §3 항목 8·16·17, 맥 러너 재시작(F5 복제본).
- 트랙 37: `prune_operational_data` 스케줄러 실제 등록(`docs/operations-runbook.md` §7.2).
- 트랙 33: 운영 DB에 남은 해외 소스 수동 확인(로컬 2건은 비활성화 완료).
- 트랙 50: `docs/FE/design-principles.md` ⑬-14 성격 단어 확인.
- 트랙 45: `core/client_error_views.py` IP 보조 스로틀 착수는 사용자 결정(미결).
- 트랙 45: `EmailAddress` 중복 감사의 운영 DB 실행은 사용자 몫(미완,
  `docs/operations-runbook.md` §10).
- 트랙 59: 실제 스크린리더 낭독은 사람이 확인해야 한다(사용자 확인 필요).

핵심 루프(발견 → 상태 → 방문 기록 → 굿즈 → 의도)는 URL·뷰·서비스 계층에서
끊긴 곳 없이 연결되어 있다. 교환(trade) 도메인은 존재하지 않으며, 이는 게이트
승인 전 착수 금지 원칙이 지켜지고 있다는 뜻이다.

---

## C. 제품 다음 단계

### C1 북극성 지표 — **배포 이후로 연기 (2026-07-31 사용자 결정). 설계 결정은 확정됨**

**연기 사유**(2026-07-31 당시 기록): 실행 순서 5단계는 *"with **real
cohorts**"*를 요구하는데 서비스가 아직 배포되지 않았고(1단계 인프라 대기),
SMTP 미설정이라 **신규 가입 자체가 동작하지 않는다.** 실사용자 0명이고 만들
수단도 지금은 없다. 로컬 DB의 **56행 / 고유 user_key 10개**는 목데이터다.

2026-10-27 갱신: 배포는 2026-08-31 완료(takulife.kr, 트랙 16). 재개 트리거 중
'배포 완료'는 충족됐고, 남은 조건은 실코호트(실사용 가입자) 확보와 SMTP
미설정에 따른 이메일 가입 제약이다.

착수 재개 트리거: **배포 완료 + 실사용자 가입 가능**. (배포 완료는 충족)

⚠️ 이 항목이 끝나도 실코호트가 생기기 전까지 **"5단계 완료"라고 쓰지 마라.**

#### 확정된 설계 결정 (재논의 불필요)

| # | 결정 | 근거 |
|---|---|---|
| 1 | **"의미 있는 수정" = 실제 값 변경만** | 기존 `ActivityLogEntry.Kind.COLLECTION_ITEM_ORGANIZED`를 쓴다 — `quantity`·`is_wanted`·`tradeable_quantity`·`acquired_on` 중 **값이 실제로 바뀔 때만** 기록된다(`archive/services.py:527-540` `[실측 rg 2026-10-27]`). ⚠️ 이건 이벤트가 아니라 **도메인 테이블**이라 `core/analytics.py`가 아니라 `archive` 쪽에서 읽어야 한다 |
| 2 | **구함·교환은 보조 축으로 분리** | 북극성 헤드카운트에 넣지 않는다. 교환 게이트 승인 전이라 핵심 지표를 교환 쪽으로 기울이지 않는다 |
| 3 | **노출은 스태프 대시보드 기존 행 교체** | `staff/views/__init__.py:284` `[실측 rg 2026-11-12]`의 `weekly_active_user_count`(13종 이벤트를 전부 합친 값)를 컬렉션 기여 기준으로 바꾼다. 새 대시보드 섹션은 만들지 않는다 |
| 4 | **월 = KST 달력월** | `AGENTS.md`가 "monthly"와 "four-week"를 별개 지표로 나열한다 — 후자가 롤링이므로 전자는 달력월로 읽는 것이 문서 내적으로 일관된다. ⚠️ `created_at`은 UTC aware로 저장되므로 경계 계산은 KST 기준이어야 한다. 이 저장소는 이미 타임존 오표시 결함을 겪었다(PR #255) |

#### 미해결 결정 (착수 시 사용자에게 물어라)

- `collection_item_linked_to_visit` — 생성 시점 링크와 사후 재링크를 구분해 셀지.
  같은 이벤트명을 공유한다(`archive/services.py:424`·`:562` `COLLECTION_ITEM_LINKED_TO_VISIT` 호출 `[실측 rg 2026-11-12]`; `:569`는 `MARKED_WANTED`라 바로잡음)
- `visit_photo_added` — 같은 달 `visit_record_created`와 별개 기여로 셀지,
  완성도 축에만 반영할지

#### 실측한 사실 (착수 전 재확인은 여전히 필요)

- `core/analytics.py` 공개 함수는 **4개뿐**이고 전부 슬라이딩 윈도우다. 월간
  코호트 개념 없음
- `AnalyticsEvent.EventName`은 **13종 선언**돼 있다. 착수 전 서술의 "8종"은
  선언 수가 아니라 **로컬 개발 DB에 나타난 종류 수**였다
- `pseudonymous_user_key`는 `HMAC(SECRET_KEY, user.pk)`로 **시간에 대해 안정적** —
  월간 코호트·4주 재방문 계산 가능. 단 `SECRET_KEY` 교체 시 연속성 단절
- 프로덕션 `record_event` 호출처 **15곳**(`archive/services.py` 13, `events/views.py` 2)
- `AnalyticsEvent` 퍼지·보존 커맨드 **0건**

#### 소유 위치 (도메인 경계 검토자 판정)

- 이벤트만으로 계산되는 지표(월간 기여·활성화·재등록·4주 재방문) → `core/analytics.py`
- **완성도** → `archive/queries.py`. `AnalyticsEvent.context`가 `name`·`memo`를
  하드 거부해(`core/analytics.py:33-35` `FORBIDDEN_CONTEXT_KEYS` `[실측 rg 2026-10-27]`) 필드 채움 여부는 이벤트에 애초에 실리지 않는다
- 조합 → `staff/queries.py`
- ⚠️ **`core/analytics.py`는 도메인 앱을 임포트하면 즉시 Red다**(A1 후속 core 가드).
  도메인 행을 읽어야 하는 지표를 그 파일에 두려는 시도는 구조적으로 막힌다

#### 영구히 계산 불가능한 것

`AnalyticsEvent`에 user FK가 없어(*"intentionally cannot be joined back to
accounts.User"*) `accounts.User` 속성과의 조인이 불가능하다 — **가입월 코호트별
리텐션** 같은 전통적 코호트 표는 설계상 만들 수 없다. 또 탈퇴로 계정이 삭제돼도
이벤트 행은 남아 과거 행동이 계속 집계된다. 둘 다 의도된 트레이드오프다.

---

## F. 운영·위생

| # | 항목 | 근거 | 비고 |
|---|---|---|---|
| F7 | 실사용 데이터 이후 스키마 변경 가이드 부재 | `archive/migrations/0011~0013,0019` 비-concurrent | 두 번째 배포부터 유효 |
| F10 | `staff_event_edit`의 lost-update 여지(해결 부분은 "해결된 항목" 표 F10) | — | lost-update 완전 해법(폼 버전 스탬프)은 이연 — 트리거: 스태프 동시 편집 실관측 |
| F12 | `/api/schema/` 스로틀·캐시 없음 + CI 스모크가 `/api/docs/`를 안 본다 | `docs/BE/openapi-schema.md` "미적용(의도)" | 실트래픽 개시 전 유보. 트리거 시 ①캐시/스로틀 적용 ②CI 도커 스모크(F3)에 `/api/docs/` curl 200 추가 |
| F14 | 폰트 폴백 메트릭 튜닝(size-adjust 계열) | 트랙 13에서 데스크탑 콜드 CLS 0.02(Good) 수용, 0.01 이하로 낮추려면 폴백 서체 메트릭 오버라이드+시각 회귀 필요(2026-08-29) | 이연 |
| F15 | og:image 브랜드 카드(1200×630 PNG) 제작·발행 | 트랙 16(2026-08-30)이 og:image를 의도적으로 미발행(래스터 자산 부재, favicon.svg 유용 금지, `test_페이지_응답은_og_image_태그를_포함하지_않는다` 핀) | 이연. 자산 제작 시 M4 핀 교체와 함께 발행 |
| F17 | CI `e2e` 잡의 `continue-on-error: true` 해제 시점 | `[문서]` 트랙 27 DOR 제안 기준 — main 연속 10회 `[문서 DOR 제안]` 비결함 그린 뒤 필수 게이트로 전환 | 미해결 사용자 결정. 롤백은 잡에 `if: false` 한 줄 |
| F18 | 스태프 셸이 CSRF 쿠키를 새로 발급하지 않는다 | `[실측 2026-09-10 e2e E7]` `templates/staff/base_staff.html`은 `{% csrf_token %}` 0건이라 일반 셸(`templates/core/partials/_topbar.html:37` 로그아웃 폼)과 달리 `csrftoken` 쿠키를 심지 않는다. 로그인 폼을 거친 사용자는 쿠키가 있지만, 쿠키가 지워진 상태로 `/staff/events/`에 바로 들어오면 일괄 비공개·인라인 액션 fetch가 403("세션이 만료되었거나 보안 토큰…") | 후보 수정 = 스태프 목록 뷰에 `ensure_csrf_cookie` 또는 셸에 `{% csrf_token %}`. 트랙 27은 운영 코드 무변경 범위라 테스트 픽스처 `login_as`가 쿠키를 심는 것으로 대응했다 |
| F19 | 홈 스냅샷이 방문 기록 수를 활성 조건에 넣지 않는다 | `[코드 web/views/events.py:237, e2e E4에서 발견]` 방문 기록만 1건인 사용자에게도 홈 `snapshot_active`가 "아직 기록이 없어요"를 보여준다 | 제품 판단 필요(방문 기록 수를 활성 조건에 넣을지). 트랙 27은 E4의 Then을 방문 기록 목록으로 옮겨 대응했다 |

**로컬 에이전트 수집처 탐색 — 구현됨(2026-08-20~24, PR #299·#301).** 서버
경계(모델 3종·러너 API·8단계 결정론 검증·승격) + `local_runner/` 어댑터 완비.
정본: `docs/BE/draft-source-agent-discovery.md`. 잔여 관측성·하드닝 항목은
아래 G절.

---

## G. 전수 검토 잔여 (2026-08-24)

### G2 [코드] gunicorn 워커 타임아웃 미설정 — **해결(트랙 46, 2026-10-28)**

**해결**: `docker/entrypoint.sh`가 `--timeout "${GUNICORN_TIMEOUT:-120}"`로 워커 타임아웃을 정한다(기본 120초 `[코드]`, env로 조정, 0 금지, 롤백은 `GUNICORN_TIMEOUT=30`). 계약 테스트 `tests/core/test_entrypoint_contract.py`가 플래그 유지와 기본값 120초를 고정한다.

아래는 측정 전 기록이다.

`docker/entrypoint.sh`에 `--timeout`이 없다. 러너 후보 제출이 요청 안에서
동기 네트워크 최대 6회(각 5초) → 최악 ~30초로 기본 타임아웃과 충돌 가능.
**트리거 발동: 2026-09-20 프로덕션 `DRAFT_DISCOVERY_ENABLED=true` 전환
[사용자 보고] — 트랙 39(러너 진행 표시) 종료 직후 별도 트랙으로 착수
예정(사용자 결정 2026-09-20).**

동일 근본 원인 `[계산 2026-09-05]`: 대시보드 「지금 수집」도 동기 실행(`staff/views/__init__.py:201-250`)이라 활성 소스 3개가 모두 느린 최악 시 `3×(5+5)+2×1 = 32초`(요청 타임아웃 5초 `drafts/fetching.py:9`, 소스 간 대기 1초 `drafts/management/commands/discover_drafts.py:58`)로 기본 30초를 넘길 수 있고, 워커 SIGKILL 시 `finally`의 감사 로그(`staff/views/__init__.py:247-250`)가 남지 않는다. `docker/entrypoint.sh`에 `--timeout` 0건 `[실측 2026-09-05]`. 프로덕션 활성 소스 수는 미실측. 사용자 보류·트리거는 그대로다.

**정정 (2026-09-28, 트랙 40 PR #388)**: 위 문단은 측정 전 기록이다. (1) 「지금 수집」 중복 실행은 트랙 40의 캐시 뮤텍스로 막혔다(보안 검토 F4, `staff/views/__init__.py` `DISCOVERY_RUN_LOCK_KEY`). 워커 타임아웃 자체(30초 초과 실행이 끊기는 것)는 여전히 이 G2 범위다. (2) "SIGKILL 시 `finally` 미실행"은 부분 오류: 타임아웃 시 아비터는 먼저 SIGABRT를 보내고(`gunicorn/arbiter.py:590-593` `[코드]`) 워커는 `sys.exit(1)`(`gunicorn/workers/base.py:195-198` `[코드]`)이라 `finally`(감사 로그·잠금 해제)가 실행된다. SIGKILL은 다음 아비터 점검 때까지 살아 있을 때만 간다(`arbiter.py:594-595`). (3) 위 줄 번호 `:200-245`·`:242-245`는 현재 `staff_draft_discovery_run` 기준 `:307-364`이다(`def` 307행, 잠금 해제 364행 `[실측 rg 2026-11-12]`).

**정정 (2026-10-28, 트랙 46)**: 후보 제출의 네트워크 호출은 robots·목록·표본에 승격 초기 드래프트 최대 20회(`DRAFT_DISCOVERY_MAX_FETCHES_PER_SOURCE` `[코드 config/settings.py]`)가 더해진다. `fetch_html` 1회 상한은 40초(리다이렉트 4홉 × (connect 5초 + read 5초) `[계산 2026-10-28]`). 「지금 수집」 정상 응답 시 소스 3개 약 128초, 소스 1개 약 42초 `[계산 2026-10-28: 소스 1개 = 1단계 2초 + 후보 시도 20회 × (fetch 1초 + 대기 1초) = 42초; 소스 3개 = 3 × 42초 + 소스 간 대기 2초 = 128초]`. 3소스 풀 예산 경로(128초)는 기본 120초를 넘어 `WORKER TIMEOUT`으로 끊길 수 있다. 이 경우 SIGABRT 뒤 `finally`가 뮤텍스를 해제하므로(같은 절 위 정정 참고) 다음 실행이 막히지 않는다. 기본값을 올리면 느린 외부 호스트의 워커 점유 노출(SRR 2026-10-28 Medium)이 같이 늘어 120초를 유지했고, 소스 수가 늘면 운영자가 env로 올린다. 병적 경로(동일 호스트 24회 × 40초 = 960초 `[계산 2026-10-28]`)는 120초로도 닫히지 않는다. 총 소요 데드라인·Crawl-delay 상한은 이연한다(트리거: 프로덕션 `WORKER TIMEOUT` 로그 관측).

**이연 (SRR 2026-10-28 Medium)**: fetch 전체 데드라인(`drafts/fetching.py`, 홉·청크마다 `time.monotonic()` 검사)과 `Crawl-delay` 상한(`discover_drafts.py` 206행 부근 `min(crawl_delay, 상한)` `[코드 drafts/management/commands/discover_drafts.py:208]`). 수용 기준 = 1바이트/4.9초 흘림 호스트 스텁과 `Crawl-delay: 99999` 스텁으로 fetch는 데드라인 안에 `FetchError`, 대기는 상한 이하. 트리거: 프로덕션 `WORKER TIMEOUT (pid:` 로그 관측 또는 러너 토큰 유출 의심.

### G3 [코드] LLM 아웃바운드 네트워크 수준 계약 테스트 부재

현재 보증은 코드 경로 부재 + 단위 모킹 2겹뿐. `pytest-socket` 등 신규 dev
패키지가 필요해 **uv 정책상 사용자 명시 승인 대기.**

### G6 트랙 30(키워드 탐색) 이연 항목(2026-09-12)

트랙 30(키워드 탐색 → 판별 → 드래프트·소스 등록) 승인 범위 밖으로 이연한
항목. 트랙 30 본체는 PR #361로 머지 완료됐다(2026-09-12, main `cfd69d3a`)
`[실측 gh]`. 가드레일 정본은 `docs/BE/draft-source-agent-discovery.md`
"트랙 30" 절.

- `[코드]` `local_runner/page_fetch.py:214`(`_fetch_general_web`) 일반
  웹 응답 크기 상한을 응답을 다 내려받은 뒤 `len(html.encode(...))`로
  검사한다(크기 검사 `:229` `[실측 rg 2026-11-12]`). 상한 자체가 메모리 사용을 막지 못한다(스트리밍 검사가 아님).
  개인 맥 단일 실행이라 위험이 낮아 이번 범위에서 뺐다.
- `[코드]` `local_runner/exploration_flow.py:398`(`known_urls` 호출 `[실측 rg 2026-10-27]`)
  탐색이 이벤트를 0건 낸 실행에서도 `client.known_urls(urls=[])`로 서버에
  빈 목록 조회를 보낸다. 결과를 바꾸지 않는 왕복이다.
- 검색 결과 페이지 자체를 발견 경로로 코드화하는 것(현재는 탐색 프롬프트가
  검색 결과 목록만으로 판단하게 지시할 뿐, 검색 결과 페이지 URL 패턴을
  코드가 알지 못한다). 트리거: 표본 주소가 검색으로 연속 두 번 안 잡히는
  사례 관측.
- 경로 정준화(같은 게시물의 다른 URL 형태를 하나로 묶기). 현재
  `_strip_tracking_params`(`drafts/agent_drafts.py:198` `[실측 rg 2026-10-27]`)는 추적
  쿼리스트링만 제거하고 경로 형식 차이는 다루지 않는다. 트리거: 경로
  형식만 다른 같은 행사가 별개 드래프트로 실제 등록되는 사례 관측.
- `[미검증]` 그 브라우저 제어 MCP 도구가 사용자의 상시 로그인 브라우저
  프로파일에 붙는지 격리된 새 프로파일을 쓰는지 확인하지 못했다(위 문서
  "격리 권고" 정정 절의 잔여 항목과 동일).

---

## H. 스태프 백오피스 현업 적합성 검토 (2026-09-05)

검토 경로: 코드·문서 판독 뒤 PSO·WED·SRR·DOR 4역할 병렬 검토, 인용된 file:line은
오케스트레이터가 전부 재확인. 현재 있는 것 `[코드]`: `staff/urls.py` 라우트 19개,
대시보드 지표 카드 5장, 드래프트 큐(상태 탭·검색·인스펙터·일괄 승인/반려 상한
20건 `MAX_BULK_APPROVE_DRAFT_IDS`), 이벤트 목록·생성·수정·게시 토글·검증·삭제,
수집 소스 읽기 전용 표, 홈 카테고리, 감사 로그(행동 11종). 스태프 테스트 함수
295개 `[실측 2026-09-05]` `rg -c 'def test_' tests/staff/*.py` 합계.

P0는 "shell 없이는 운영자가 일을 못 하는 것"으로 한정했다(PSO). PSO(P0=H1)와
WED(P0=H2)의 우선순위 충돌은 AGENTS.md 배타 책임에 따라 PSO 판정으로 조정했다.
H6도 같은 규칙으로 PSO P2를 따른다(2026-09-06 정정). 2026-09-06 외부 검토를
반영했고 정정 위치는 각 행에 날짜로 표기했다.

(H1·H2 근거의 `staff/views/events.py` 줄 번호는 작성 시점 값이며 현재 이동됨 — 토글 `staff_event_toggle_publish` `:599`, 삭제 확인 `:695` `[실측 rg 2026-11-12]`)

| # | 우선순위 | 항목 | 근거 | 분류·판정 |
|---|---|---|---|---|
| H1 | **P0** | 계정 운영 화면(잔여, 해결 내역은 "해결된 항목" 표 H1) | — | 사용자 결정(2026-09-07): ★3 액션 빈도 제한·step-up은 미구현 유지 수용(이연). ★2 확정(2026-09-07): superuser는 shell로만 생성·변경, 콘솔 제외 유지 |
| H2 | P1 | 이벤트 일괄 선택·일괄 게시 등(잔여, 해결 내역은 "해결된 항목" 표 H2) | — | 미해결 제품 결정(H2 종결과 무관하게 유지): 재검증("검증 완료")의 운영 절차가 `docs/event-operations-criteria.md`에 없음 — 사용자 결정 필요 |
| H4 | P1 | 검수 SLA 지표(잔여, 해결 내역은 "해결된 항목" 표 H4) | — | 사유 분포는 H10 뒤로 이연, 증감 없음(★2) |
| H6 | P2 | 수집 소스 생성·수정·활성 토글 콘솔 편입 | admin 이탈 안내 `staff/views/__init__.py:332` `[실측 rg 2026-11-12]`(트랙 19 import 추가로 225→237, 2026-09-07 재확인), `drafts/admin.py` 빈 ModelAdmin | 제품 권고. PSO P2(admin으로 가능) / WED P1(콘솔 밖 3번째 화면 강제). 2026-09-06 정정: 이전 표기 P1은 WED 의견으로 상향한 것이라 "우선순위는 PSO 판정" 규칙과 충돌해 PSO P2로 되돌림. WED 이견은 기록만. **사용자 결정(2026-09-07): P2 유지** — 운영자가 소스를 주 1회 이상 만진다는 사실이 확인되면 올리고, 착수 시 `superuser_console_required` 재사용(admin은 superuser 전용인데 콘솔 소스 화면은 is_staff 전체가 보므로) |
| H7 | P1 | 감사 범위 확대(잔여, 해결 내역은 "해결된 항목" 표 H7) | — | 전후 스냅샷은 H12(b) 보존 정책 결정까지 보류 |
| H8 | P1 | 알림(대기 누적·소스 전부 오류·러너 오프라인) | `send_mail`·`EmailMessage`·`mail_admins` 0건 `[실측 rg staff/ drafts/]` | 오프라인 즉시 표시는 트랙 39(offline 엔드포인트·대시보드 폴링)로 해소. 알림 메일은 이연 유지. DOR: 비용 정책 안 대안 없음(무료 웹훅은 외부 계정 액션 = 인프라 최후순위) |
| H9 | P2 | 소스별 수집 이력·실패율, 실패 후보 재시도/무시 액션 | `DraftSource` 상태 필드 2개뿐 `drafts/models.py:102-103` `[실측 rg 2026-10-27]`(정정 전 표기 56-66은 필드 줄을 빗나감, 2026-09-06 재측정) | 제품 권고 |
| H10 | P2 | 중복 경고(같은 행사 다른 URL), 반려 사유 큐 노출·템플릿 | 중복 판정은 URL 완전일치만 | 제품 권고 |
| H11 | P2 | 이벤트 검색에 공식 URL·ID, 변경 이력, 수정 화면 소비자 링크·반응 지표, 검증 만료 예고 | 검색 3열 `events/queries.py:244-246` `[실측 rg 2026-10-27]`, `Event.updated_at` 0건 `[실측 rg events/models.py]` | 제품 권고 |
| H12 | P2 | 수집 진행 표시, 감사 로그 보존 정책 | `staff/management/` 없음 `[실측 ls]`. 진행 표시는 현재도 제출 가드가 버튼 비활성+`.is-loading`을 적용(`templates/staff/dashboard.html:115` `data-submit-guard`, `static/js/shared/submit_guard.js`(옛 이름 `staff_submit_guard.js`) `[실측 rg 2026-10-27]`) | 권고. 2026-09-06 분리: (a) 진행 표시 — **트랙 39로 해소**(heartbeat phase·detail + 대시보드 5초/20초 폴링 + 러너 터미널 INFO 로그, 정본 `docs/BE/draft-source-agent-discovery.md` "트랙 39" 절). G2 타임아웃 조정은 원인을 공유할 뿐 진행 표시와는 별개다. (b) 감사 보존 정책 — 독립 과제, 유지. G2 해결(트랙 46) |
| H13 | P2 | 대시보드 소스 패널 「전체 보기」 링크, 이벤트 읽기 전용 미리보기 | `templates/staff/dashboard.html:91-103`(감사 패널은 `:276`에 링크 있음 `[실측 rg 2026-10-27]`) | 제품 권고 |

**보류·이연(기록된 사용자 결정, 재제안 아님)**: RBAC(2026-07-03 보류, 트리거는
첫 비-superuser 스태프), 취소·연기 상태(prompt_plan.md Deferred), 일괄
가져오기·내보내기(아래 「착수하지 않는 것」), 북극성·이벤트별 분해(C1), 신고·차단·
중재(교환 게이트), 모바일 차단(D10), 정기 수집 스케줄러(인프라 최후순위),
대시보드 증감 미표시 2장(M5).

**트랙 26(H2 세 번째 조각) 이연 항목**: `start_date`·`end_date`·`category`
전용 DB 인덱스 **0건**(`[실측]` `events/models.py`·`events/migrations/`
grep — 정렬·기간·카테고리 필터가 이 필드를 인덱스 없이 훑는다, 현재
카탈로그 규모에서 체감 영향은 미실측). 필터 이동 후 포커스 복원(이번
트랙은 필터 링크 이동이 매번 새 문서 로드라 포커스 복원 대상이 아님 —
장차 필터를 fetch 기반으로 바꾸면 필요). `staff/views/events.py`
필터 헬퍼(`_selected_event_filters`·`_event_filter_query_pairs`·
`_active_filter_summary`) 분리 모듈화 — 파일이 809줄 `[실측 wc -l 2026-10-27]`(작성 당시 793줄)로
800줄 상한 초과였고 **2026-10-27 트랙 45에서 분리 완료**(`StaffEventBulkUnpublishView`·`MAX_BULK_EVENT_IDS` → `staff/views/events_actions.py`, events.py 731줄 `[실측 wc -l]`). `{% querystring %}` 무효 값 잔존(BIR 사후 판정
Deviates, Low·비차단 — `docs/BE/staff-event-publish-actions.md` (r) 참고).

**기각(과설계)**: 담당자 배정·검수 락(`select_for_update`로 이미 안전), 전역
검색(검색 화면 3개), User 전체 admin 등록(SRR — 근거는 업무에 불필요한 계정 편집
기능의 추가 노출 최소화. allauth 65.18.0 admin은 이미 `EmailAddress`·`SocialAccount`를
편집 노출하므로 "피해 반경 1개→전체 확대"는 근거가 아니다 `[실측 2026-09-06]`).

**미실측(착수 전 재측정)**: 프로덕션 활성 소스 수, `StaffActionLog` 행 수, 종료
게시 이벤트 수.

**설계 시 확정(2026-09-06 외부 검토 반영)**: H4·H5 — 재오픈 후 대기 시간의 기산점과
반려율 계산 기준(기산점·반려율 기준 모두 2026-09-08 확정, `docs/BE/draft-review-lifecycle.md` (c)·(i)). H10 — 반려
사유 입력 경로는 단건 반려의 textarea뿐
(`templates/core/drafts/detail.html:150-151`), 일괄 반려는 사유 없이 id만 보낸다
(`static/js/staff/draft_bulk.js:7`). H13 — 비공개·미저장 이벤트 미리보기 범위.

**프론트 필요 기능(2026-09-06, WED·BIR 사전 검토 통합 — 인용 file:line은
오케스트레이터가 전수 재확인)**: 전제 = 스태프 콘솔은 소비자 CSS·JS를 로드하지
않는 독립 셸(`docs/FE/staff-console-redesign.md` S6)이고 1024px 미만은 데스크톱
게이트(S7)라 항목별 추가 반응형 요구는 없다. 프론트 작업 없음: H7·H12(b)는
백엔드, H8 이연, H14는 H1, H4는 `templates/staff/dashboard.html:29-36`
dash-metric 카드 재사용(집계만 백엔드). 구현됨(트랙 22, 왼쪽 열 `dash-panel`
+ `.dash-metrics--3` 변형 CSS, 링크 카드 포커스 링 인셋 규칙 추가). 두 역할 원문과 검증 기록은
`.docs/FE/2026-09-06-staff-backoffice-frontend-review.md`(git-ignored).

- H1 — 사이드바 "계정" 그룹을 기록 그룹 뒤(`templates/staff/_console_shell.html:50-59`)에
  superuser에게만 렌더(링크 숨김은 UX일 뿐 경계가 아님, `docs/BE/staff-account-operations.md` (a)). 목록 = 검색
  (`staff/search.py:15` `SEARCHABLE_URL_NAMES` 추가)·표(`templates/staff/events/list.html:32-73`)·
  페이저(`templates/core/partials/_pager.html`)·빈 상태 2분기(`templates/staff/audit_log/list.html:60-64`).
  상세 = rail-card 토글 폼 2개(`templates/staff/events/edit.html:125-146`); 자기 계정·
  마지막 관리자는 버튼 disabled + 사유 문단(`edit.html:172-175` 패턴), 판정 불리언은
  뷰가 계산. 탈퇴 유예 배지는 읽기 전용 — 재로그인만 취소(`accounts/models.py:15-18`),
  유예 10일(`accounts/services.py:23`), 종료 시각은 뷰가 계산. 확인 단계는 삭제와
  같은 서버 렌더 2단계(`confirmed=yes`, `staff/views/events.py:480-483`·`501-510`,
  `templates/staff/events/delete_confirm.html:54`)를 우선 권고 — 기존 PRG+messages
  (`templates/staff/base_staff.html:58-64`)와 맞고 JSON 엔드포인트가 필요 없다.
  JS 모달을 택하면 `static/js/components/confirm-modal.js`(Escape 101·Tab 107·기본
  포커스 아니오 144·포커스 복귀 174-177) 재사용, 서버 거부 문구는
  `error_response(detail)`(`core/errors.py:4-5`)로 내려야 `static/js/shared/api.js:94` `[실측 rg 2026-10-27]`
  formatError가 "알 수 없는 오류"로 뭉개지 않는다. 프론트 파일 `[코드 추정]` 5개
  (templates 2·css 1·js 1·`_console_shell.html` 수정). 구현됨(트랙 19).
- H2 — 체크박스 열 + bulkbar(`templates/core/drafts/list.html:50-61`) + 행별 실패
  사유(`:118-123` `data-bulk-fail-reason`) + 카테고리 칩(`events/list.html:18-24` 패턴)
  + 기간 `<form method="get">`(숨은 파라미터 `_console_shell.html:100-102` 패턴).
  선택 범위: 두 목록 모두 서버 페이지네이션(`events/list.html:77-78`, 페이지 15건
  `events/queries.py:186` `[코드]`)이라 선택은 현재 페이지·필터에서만 유효, 전환 시
  초기화(드래프트 큐와 같은 제약). 응답 반영은 `static/js/staff/draft_bulk.js:396-430`
  applyBulkResult(succeeded/failed 배열) 이식, 재시도는 목표 상태 지정 API에만 허용.
  인라인 토글: 현재 토글 뷰는 redirect 반환(`staff/views/events.py:443`)이라 fetch가
  JSON을 못 받는다 → JSON 분기 또는 별도 엔드포인트가 백엔드 계약. 정렬·기간
  파라미터는 `_event_filter_query_pairs`(`events.py:108-115`, warning·publish_status만)
  확장 필수 — 빠지면 수정 후 목록 복귀 시 새 필터가 소실되고 `list.html`·`edit.html`·
  `delete_confirm.html` 3곳이 `list_query`를 공유한다. 이벤트 목록엔 JS가 없어
  (`[실측]` `grep -c "<script\|shell_js\|page_js" templates/staff/events/list.html` = 0)
  단축키를 넣으려면 `static/js/staff/queue_shortcuts.js:23-53` 가드를 이식.
  체크박스 열·bulkbar·행별 실패 사유·목표 상태 지정 API는 **구현 완료
  (2026-09-09, 트랙 24, PR #350)**. 인라인 단건 목표 상태·검증 JSON
  엔드포인트, 행 배지·인라인 버튼도 **구현 완료(트랙 25, PR #353,
  오케스트레이터 기입)** — 정본 `docs/BE/staff-event-publish-actions.md`.
  정렬·기간·카테고리 필터, 카테고리 건수 배지, 검색어 유지 결함 2건 수정도
  **구현 완료(2026-09-12, 트랙 26)** — H2 세 트랙 모두 완료.
- H3 — 큐 제목 셀 안 인라인 배지(`core/drafts/list.html:97-106`; colgroup 6열
  `:66-73` 고정폭이라 열 추가 금지), 고지는 `templates/core/archive/personal_detail.html:115`
  promote-note에 1줄(신규 안내 카드 금지). JS 없음. 구현됨(트랙 23).
- H5 — `templates/core/drafts/detail.html:154-159` judge-actions에 재오픈 버튼,
  `static/js/staff/draft.js:178` bindApproveButton 구조(askConfirm→setLoading→post→
  `successEl.focus()` 223) 재사용. 서버 pending 전용 가드로 멱등. 구현됨(트랙 21).
- H6 — `templates/staff/sources/list.html`(`<form` 0건 `[실측 grep -c]`)에 생성 폼·
  행별 수정·토글, 폼은 `events/edit.html:31-99` 패턴. 토글은 양방향이라 확인
  불필요(`events.py:397-398` 선례). 완료 시 admin 이탈 문구(`staff/views/__init__.py:332`) 제거.
- H9 — 이력 표는 백엔드 저장 구조 선행(`DraftSource` 상태 필드는 `drafts/models.py:102-103`
  2개). 재시도는 확인 불필요, "무시"가 영구 폐기면 확인 필요(설계 시 결정).
- H10 — 사유 템플릿은 단건 textarea(`core/drafts/detail.html:150-151`)에만 붙는다.
  일괄 반려는 `draft_bulk.js:468`이 `draft_ids`만 보내므로 사유 추가는 백엔드 변경 동반.
- H11 — 이력 패널은 `Event.updated_at` 부재로 백엔드 선행. 소비자 링크·만료 배지는
  `events/edit.html:101-183` rail-card.
- H12(a) — 「지금 수집」은 순수 폼 POST라 `api.js` 오류 분기가 관여하지 않고 프록시
  타임아웃 시 브라우저 오류 화면만 보인다(`staff_draft_discovery_run` `staff/views/__init__.py:307`·`call_command` `:344`·락 해제 `:364` `[실측 rg 2026-11-12]`).
  대기 문구면 기존 가드로 충분, 실행 상태 조회면 백그라운드 잡 + 폴링(신규 아키텍처).
- H13 — 링크는 `dashboard.html:276` 패턴. 미리보기는 confirm-modal(예/아니오 전용)
  확장 금지, 콘텐츠 모달을 따로 설계.
- 공통 가드레일 — 신규 CSS는 `static/css/staff/tokens.css`의 `--c-*`만,
  `<main class="page" id="staff-main">` 래퍼 유지(S6). 위험 액션 폼에 `data-submit-guard`
  누락 금지(`[실측]` `rg -l data-submit-guard templates/` = 2026-09-06 기준 8파일, 2026-10-27 기준 27파일 `[실측 rg -l data-submit-guard templates/]`).
- 검토 정정 기록 — BIR가 `events/edit.html:176-179` 삭제 폼을 "확인 없음"
  Medium-High 결함으로 보고했으나, 삭제 뷰는 서버 렌더 2단계 확인(`staff/views/events.py:480-483`,
  `confirmed=yes` 없으면 확인 화면만 렌더)이라 결함이 아니다. 첫 폼의 더블클릭은
  확인 화면을 두 번 열 뿐이다.

---

## I. 닉네임 후속(이연)

트랙 29(회원 닉네임 도입) 승인 범위 밖으로 이연한 항목. 가드레일 정본은
`docs/BE/account-identity.md`.

- 소셜 가입 시 provider가 주는 표시 이름을 닉네임 초기값으로 제안(현재는
  provider 값과 무관하게 빈 입력을 요구).
- 닉네임 변경 이력 보관(현재는 이전 값을 남기지 않는다).
- superuser 계정 화면(`/staff/accounts/`)에 닉네임 열·검색 추가.
- 욕설·부분 문자열·유사 사칭(예: `adm1n`) 탐지 — 현재 예약어는 완전일치만.
- 사용 가능 여부 실시간(AJAX) 확인 — 추가 시 빈도 제한이 반드시 함께 필요.

---

## J. 보안 검토 2026-09-27 (트랙 40에서 반영, 2026-09-28)

정본: `docs/BE/security-review-2026-09-27.md`(발견 11건의 현재/변경 후 흐름, 변경
요소 표, Test List, §8 트랙 40 반영 결과 표). 기준 main `2c0e3552`. 트랙 40이
브랜치 `fix/security-review-2026-09-27`에서 반영, **PR #388 머지 완료(2026-10-04 11:19Z,
merge commit `e02463e5` `[실측 gh 2026-10-20]`)**, deploy #391(2026-10-06)로 production 반영.
전체 회귀 3,211 passed / 10 deselected `[실측 2026-09-28]`, PR CI 5개(테스트·의존성
감사·Docker 빌드·GitGuardian·e2e 관측) 통과 `[실측 gh pr checks]`. `check --deploy`
W021만, pip-audit 알려진 취약점 0건(잠금 내보내기 209행, dev 포함) `[실측 2026-09-27]`.
**배포 후 사후 확인(2026-10-20 기준 수행 여부 미확인, 사용자)**: 운영 DB의 비-http(s)·호스트
없는 `official_url` 행 수 확인(`docs/deploy-runbook.md` §3 항목 16 — 검증기는 이미 게시된
행을 소급 정리하지 않는다), 항목 8(`TRUSTED_PROXY_COUNT`)·17(memo 최대 길이), 맥 러너 재시작.

| # | 심각도 | 요지 | 근거 | 상태 |
|---|---|---|---|---|
| J1 | High | 스태프 이벤트 폼 `official_url` 스킴 미검증 → 공개 상세 `href`에 `javascript:` 저장형 XSS. 검증기가 `javascript:` 값을 그대로 반환 `[실측 shell dry-run]` | `events/services.py:41-74`, `templates/core/events/detail.html:86,186` | 수정(트랙 40, 커밋 `892feec3`) — 스킴 허용목록 + 호스트 필수 검사 |
| J2 | High | allauth `ip` 레이트리밋이 프로젝트 `TRUSTED_PROXY_COUNT`를 읽지 않아 프록시 뒤에서 전 사용자 공유 버킷(잘못된 로그인 10회/분이면 전체 429, 가입 30건/시간). 저장소 `ALLAUTH_` 설정 0건 `[실측 rg]`, Render 실측 미수행 | `config/settings.py:485-490,513-514`, allauth 65.18 `core/internal/httpkit.py:197-220` | 수정(트랙 40, 커밋 `b49a5fec`) — 운영 확인은 남음: Render env `TRUSTED_PROXY_COUNT`, 스테이징 4경로 확인 |
| J3 | Medium | DRF JSON 본문이 `DATA_UPLOAD_MAX_MEMORY_SIZE`(2,621,440바이트 `[코드]`)를 거치지 않고 memo `max_length` 없음 `[실측 소스·rg]` | `archive/serializers.py:11-44,206-274`, `archive/models.py:163,300`, DRF 3.17.2 `request.py:297-314` | (a) memo 상한 수정(트랙 40, 커밋 `fa1aa6ef`) / (b) 본문 상한 부분은 실측으로 반박 — DRF가 이미 `HttpRequest.body` 경로로 상한을 강제한다, 정본 §2 F3 정정 참조. 코드 변경 없이 핀 테스트만 추가 |
| J4 | Medium | 「지금 수집」 동기 실행 뮤텍스 없음, 워커 3개(`docker/entrypoint.sh:15` 기본) 점유. G2와 같은 축 — G2 본문의 `staff/views/__init__.py:201-250`는 현재 `staff_draft_discovery_run` 함수 전체 `:306-366`(데코레이터 306행·`def` 307행·`return` 366행) `[실측 rg 2026-11-12]` | `staff/views/__init__.py:306-366`(`staff_draft_discovery_run`) | 수정(트랙 40, 커밋 `4eb3742b`) — 캐시 뮤텍스, 보장 범위는 정상·파이썬 예외·SIGABRT 종료. G2 해결(트랙 46) |
| J5 | Low ×7 | CGNAT 대역 미차단 `[실측]`, 러너 읽기 IP 핀닝 없음(트랙 35 이연 포함), 러너 known-urls 무검사, 오류 리포트 전역 버킷, `SECURE_COOKIES` env 읽기 불일치, MFA 부재, CSP 부재 | 정본 문서 §2 F5~F11 | CGNAT 수정(커밋 `2cde14d7`)·known-urls 수정(커밋 `8315ab4c`)·`SECURE_COOKIES` 수정(커밋 `4bbc3ecc`). 러너 IP 핀닝은 트랙 35 이연과 함께 처리 예정, 오류 리포트 버킷은 선택 항목으로 미착수, MFA는 기록된 사용자 보류(2026-07-01), CSP는 별도 트랙(승인 필요) |

기록된 보류(재권고 아님): 슈퍼유저 step-up(2026-09-07), F12, F18, HSTS preload,
F10 MFA(2026-07-01 `auth-hardening` 결정).
반박된 가설과 확인된 경계는 정본 문서 §3, 트랙 40 반영 결과는 §8.

---

## K. 다국어(트랙 43) 이연 (2026-10-21)

정본은 `docs/BE/i18n.md`와 `docs/plan-archive/track-43.md` §7이다. 트리거가 없는 항목은 착수하지 않는다.

- **원문 제목 "세션 유지"** — `templates/account/delete_account.html:36`. 바로 아래 본문이 "즉시 로그아웃"이라 의미가 충돌한다(AI 검수자 3명 일치). 한국어 제품 문구 결정이라 사용자 확인 후 수정한다.
- **`static/js/shared/status.js:40` 죽은 `interested` 라벨** — 쓰이는 템플릿이 없다 `[코드 BIR 확인]`. 정리는 트리거 없음.
- **AI 검수 후 보류한 용어 제안** — 낮은 확신이라 반영하지 않았다. 목록은 `docs/BE/i18n.md` "AI 검수 기록". 트리거: 원어민 검수 도입.
- **스태프가 새로 만든 카테고리의 번역과 행·상세·칩 표시** — 새 카테고리도 자동으로 en·ja·zh-hans가 등록돼야 한다는 사용자 결정(2026-10-22)에 따라 트랙 44-4가 맡기로 했으나 44-4는 폐기됐다(2026-11-18, `Category.label_translations` 초안은 `docs/plan-archive/track-44.md`). 슬러그가 그대로 나오던 행·상세·칩(`web/views/_helpers.py:67, :161` `[실측 rg 2026-10-27, 그 시점의 줄]`)은 트랙 59에서 DB 라벨 조회로 바뀌었다(`core.categories.category_display_labels` `[코드]`, 가드레일 `docs/BE/category-vocabulary.md`). 번역 등록은 하지 않으므로 새 카테고리는 한국어 라벨로 남는다.
- **개인 항목 검색의 다국어 일치** — `archive/queries.py:341` `icontains`는 한국어 저장값만 맞춘다(영어 `exhibition` 검색은 안 걸린다). 트리거: 다국어 검색 요구.
- **`lang="ko"`를 못 붙이는 곳** — 활동 달력 항목 라벨(출처 플래그 없음, `CalendarActivityItem` 변경 필요), `alt`, 제목+날짜 혼합 `<option>`·컬렉션 상세 연결 방문 값 문자열. 트리거: 스크린리더 사용자 피드백 또는 도메인 변경 시.
- **테스트가 실제 `media/`에 쓴다** — `MEDIA_ROOT`를 테스트가 재정의하지 않아 사진 행 15개 대비 파일 8004개가 쌓여 있다 `[실측 2026-10-23]`. 43-3과 무관한 기존 문제. 트리거: 디스크 사용량 확인 시.
- **브라우저 미확인 항목** — 라이트 테마, 중국어 하단 고정 CTA, `/jsi18n/` 차단의 브라우저 재현, 로그인 상태 해제 확인 모달·상태 패널의 영어·일본어·중국어 동작, 실제 터치·스크린리더, 폭 385~919px 전 구간, 일부 사진만 성공하는 부분 실패, ja·zh 링크 접근 가능한 이름(홈 '기록' 링크만 2026-11-18에 확인했다 — ko·en·ja·zh-hans × 3개 브라우저에서 계산된 이름이 `기록`의 번역 + 행 제목 `[실측 Playwright]`. 그 밖의 링크는 미확인). 미확인 상태로 두는 것을 사용자가 수용했다(2026-10-22, 43-3 범위는 최종 보고에서 재확인). 트리거: 다음 UI 트랙 브라우저 검증.
- **영어 `참여 상태` 번역** — `Your status`(현재) vs `Attendance status`. 원문이 모호. 트리거: 원어민 검수 도입.
- **트랙 44: 스태프 게시물(행사) 다국어 자동 등록** — 44-1(행사 콘텐츠 번역)은 PR #399 머지 완료(2026-10-27, main `e38a0db9`, 계획 `docs/plan-archive/track-44.md` §10). 번역 시작에 필요한 맥 러너 재시작과 런북 §3 항목 19 확인은 "사용자 확인 대기" 목록에 있다. 공개 화면 노출(44-2)·스태프 상태와 다시 번역(44-3)·새 카테고리 자동 번역(44-4)은 **폐기**했다(2026-11-18 사용자 결정). 번역문은 `Event.text_translations`에 저장만 되고 화면에는 나오지 않는다. 서버 LLM API는 비용 정책상 쓰지 않고 로컬 러너로 번역한다.
- **번역 큐 영구 실패 20건 초과** — 서버 큐는 가장 오래된 20건만 돌려주므로(`events/translation_queue.py::PENDING_LIMIT`), 시도 한도(`TRANSLATION_MAX_ATTEMPTS = 2`)에 도달한 이벤트가 20건을 넘으면 그보다 새 이벤트가 처리되지 않을 수 있다. 트리거: 실제 발생(44-3은 폐기).
- **단위 풀어쓰기 숫자 격리** — "5만원"→"KRW 50,000" 같은 단위 풀어쓰기는 지어낸 숫자로 격리된다(`number_invented`). 알려진 한계, 트리거 없음.
- **`manual` 플래그는 이벤트 단위 하나** — 언어별로 쪼갤지는 번역 관리 화면을 다시 계획할 때 사용자 재확인한다(44-3은 폐기).
- **번역 의미 품질 사람 검수·표본 평가 없음** — 사용자 결정(AI 검증만). 트리거: 원어민 검수 도입.
- **장식 유니코드가 판정은 통과하고 원형 그대로 저장될 수 있음** — 문자 판정·ASCII 우회·한글 잔존 검사는 NFKC로 접은 문자열에서 돌고 저장은 NFC라서, 수학 알파뉴메릭 기호(예: U+1D400 대역) 같은 장식 유니코드가 통과할 수 있다(XSS 아님, 표시 품질·눈속임 문제). 트리거: 번역문 화면 노출을 다시 계획할 때(44-2는 폐기).
- **러너 배치가 통신·기타 예외에서 매번 같은 자리에서 멈출 수 있음** — `translate_pending_batch`는 4xx(429 제외)·`AdapterOutputError`·`ValueError`만 이벤트별 시도 횟수에 반영한다(전수검사 2026-10-26로 HTTP 상태 오류 분류는 해소). 5xx·429·`OSError` 등 통신·기타 예외는 의도적으로 전파되어 배치가 중단되고 횟수가 오르지 않으므로, 개별 이벤트 탓인 `OSError`가 나면 같은 자리에서 반복 중단될 수 있다. 트리거: 실제 발생 시.
- **고유명사 라틴 예외 폭 축소** — 현재 최대 폭은 `min(400, max(40, 6 × 원문 길이))`자다. 더 좁히려면(예: 80자) 제품 결정 재확인이 필요하다. 트리거: 사용자 재확인.
- **번역 전수검사(2026-10-26) 이연 항목** — 전부 트리거 없이는 착수하지 않는다.
  - 러너 `subprocess` 호출의 `env`/`cwd` 미지정 — 러너 env 파일의 `ANTHROPIC*` 변수 존재 확인은 사용자 몫. 트리거: 사용자 확인 결과 또는 러너 호출 환경 변경.
  - `claude` 호출 `--model` 미고정 — 모델 기본값이 바뀌면 번역 품질·비용이 바뀐다. 트리거: 번역 품질 변동 관찰.
  - 큐 정체 대응 `exclude` 파라미터 — 시도 한도 도달 이벤트가 20건을 넘을 때 제외 목록을 받는 방식. 트리거: 위 "번역 큐 영구 실패 20건 초과" 발생.
  - 이메일 정규식의 2차 비용 — 토큰 보유자(러너) 제출 입력에 한정되는 위험. 트리거: 토큰 보유자 외 입력 경로 추가.
  - 구획 리터럴 변형의 대소문자 처리 — `_strip_untrusted_literals`·`_strip_delimiter_literals`의 대소문자 변형. 트리거: 실제 우회 사례.
  - 어댑터 비공개 이름 3회 반복 — 4번째 사용처가 생기면 공개 이름으로 승격. 트리거: 4번째 사용처.
  - `runner_auth`의 Discovery 이름 — 번역 러너가 공유하는데 이름이 탐색 전용으로 읽힌다. 트리거: 세 번째 러너 API 추가 또는 이 모듈을 손댈 때.
  - 큐 분류 로직 3곳 중복(DAR-2) — 트리거: 분류 규칙을 바꿀 때.
  - 테스트 스타일 — 다중 When·중복 테스트·마커 정리. 트리거: 해당 테스트 파일을 손댈 때.
- **URL 접두사·hreflang·언어별 sitemap** — 트리거: 외국어 유입 수요 실측 또는 SEO 목표 명시.
- **`Category.label` 다국어** — 트리거: 외국어 세션의 카테고리 필터 사용률 실측.
- **JS 카탈로그 응답 캐싱** — 트리거: `/jsi18n/` 응답 시간 실측. 캐시 키에 언어를 포함해야 한다.
- **`msgfmt --statistics` CI 게이트** — 기준치 합의 후.
- **닉네임 허용 문자 확장·법률 문서 번역·중국어 번체** — 각각 별도 결정.
- **파이썬 한국어 리터럴 가드** — AST로 "gettext로 감쌌는가"를 판별하기 어려워 템플릿·JS만 가드한다. 필요가 생기면 별도 설계.
- **푸터 언어 선택기 시각 다듬기** — 현재 브라우저 기본 select·버튼 모양이다. 사양이 "새 CSS 없음"이어서 그대로 두었다.
- **전체 페이지 캐시 도입 시** `Vary: Accept-Language`와 언어 쿠키를 캐시 키에 넣는다.

---

## 해결된 항목

완전히 닫힌 항목의 한 줄 기록이다. 지운 본문과 검증 결과는 `docs/pr-log.md`와
git 이력에 있다(트랙 60 직전 원문: `git show 2a8f783a:docs/backlog.md`). 표 안의
수는 그 원문 본문의 값이고, 출처 태그(`[실측]`·`[코드]`)도 원문 항목을 따른다
`[문서 git show 2a8f783a:docs/backlog.md]`.

| ID | 내용 | 해결 | 정본 |
|---|---|---|---|
| A1 | 도메인 경계 가드(사각지대 22건 스캔 전환, core 가드 기본 거부) | 브랜치 `test/boundary-guard-glob`·`test/core-guard-glob`, 2026-07-31 | `docs/BE/contract-guards.md` |
| A2 | 서명 규약 가드가 `core.analytics` 사각지대를 놓치던 것 | 2026-08-01 | `docs/BE/contract-guards.md` |
| A3 | 보유/구함/교환 3축 술어 중복 | PR #277, 2026-08-01 | — |
| A4 | 마크업 리터럴 단언 공허화(실제 위험은 1곳뿐) | 2026-07-30 | — |
| A5 | 500 페이지 테스트 무하중(몽키패치가 실행 경로를 벗어남) | 커밋 `2db756e`, 2026-07-30(잔여 위험 PR #278) | — |
| B1 | 직접 등록 수정 기능 부재(PATCH 신설) | 브랜치 `feat/personal-place-detail-edit`, 2026-07-30 | `docs/FE/personal-place-detail-edit.md` |
| B2 | 소셜 가입 경로에 약관 동의 필드가 없던 것 | 트랙 11, 활성화 완료 2026-08-26 | — |
| C3 | 사이트 로그 4단계(보존 정리) | 트랙 37, PR #378 | `docs/BE/data-retention.md` |
| D1 | 기록 결과 화면 CTA 3분기 누락 | 완료(백엔드 변경 0줄) | — |
| D2 | 필터 칩 접근 가능한 이름 누락 | 완료 2026-08-01(스태프 2개는 PR #275) | — |
| D3 | 위험도 높은 스태프 POST 폼의 제출 중복 방지 부재 | 완료(리디자인 PR #275) | — |
| D4 | 서비스 전체 공식 포스터 제거·행사 에디토리얼 전환 | PR #282, 2026-08-15 | `docs/FE/event-typography-editorial.md` |
| E1 | `core/views.py` 분할 | PR #251 | — |
| E2 | `archive/queries.py` 분할 | PR #274, 2026-07-31 | — |
| E3 | 아카이브 쿼리 테스트 파일 분할 | PR #274, 2026-07-31 | — |
| E4 | 주석 언어·길이 규칙(전면 한국어화) | PR #269~#271, 2026-07-31 | — |
| E5 | 조건을 대신 설명하는 주석 6곳 | PR #272, 2026-07-31 | — |
| E6 | `core/views/` → `web/views/` 프레젠테이션 계층 분리(core 팬아웃 21→0, 앱 간 순환 임포트 3쌍→0, 2158 passed, 뷰 7파일 R100 바이트 동일, 라우트 175건 순회 순서 무변경, 뮤테이션 M1~M11 전부 Red). 이관 중 발견한 이연 항목 4건(템플릿 `core→web` 리네임, `web/views/` 내부 방향 가드 부재 등)은 착수하지 않았고 정본에 등재돼 있다. | PR #281, 2026-08-06 | `docs/BE/web-views-package.md`, `docs/BE/contract-guards.md` |
| G1 | 미디어 스토리지 저장소 계층 프라이버시 미보증(덮어쓰기) | 브랜치 `fix/media-overwrite-lowrisk-sweep`, 2026-08-25 | `docs/deploy-runbook.md` §3 체크리스트 ⑦-2 |
| G4 | 스태프 탐색 요청 뷰 스로틀 부재 | 브랜치 `fix/media-overwrite-lowrisk-sweep`, 2026-08-25 | `docs/BE/draft-source-agent-discovery.md` |
| G5 | `visit_edit.html` 필수 범례 누락 | 브랜치 `fix/media-overwrite-lowrisk-sweep`, 2026-08-25 | — |
| F1 | worktree 2개 삭제 | 해소 확인 2026-08-01(`git worktree list` → 작업 트리 1개 `[실측]`) | — |
| F2 | 런북 줄번호 드리프트 | 해소됨(날짜 불명) | — |
| F3 | CI 컨테이너 기동 스모크 부재 | 2026-08-01 | — |
| F4 | `project-status.md` 드리프트·사실 오류 | 2026-08-01 | `docs/pr-log.md` |
| F5 | 스로틀 미적용 생성 엔드포인트 4개 | 2026-08-01(+2026-09-14 트랙 32 추가) | — |
| F6 | SSRF DNS 리바인딩 TOCTOU | 2026-08-20 | — |
| F8 | 드래프트 상태 라벨 하드코딩 | PR #278, 2026-08-01 | — |
| F9 | `staff_event_toggle_publish`에 `select_for_update` 없음 | 2026-08-01 | — |
| F10 | `staff_event_edit`의 lost-update 여지 — POST 저장 경로가 `atomic()` 안에서 `get_object_or_404(Event.objects.select_for_update(), pk=pk)`로 재조회(F9와 같은 패턴), `CaptureQueriesContext`로 `FOR UPDATE` 계약 테스트 | 브랜치 `fix/media-overwrite-lowrisk-sweep`, 2026-08-25 | — |
| F11 | OpenAPI 스키마·문서 엔드포인트 부재 | 2026-08-16 | `docs/BE/openapi-schema.md` |
| F13 | 대시보드 표 저강조 색 위계 미실현 | 브랜치 `fix/media-overwrite-lowrisk-sweep`, 2026-08-25 | — |
| F16 | `.dockerignore`가 `.claude/`를 제외하지 않던 것 | 트랙 41 커밋 `92a7cdda`, PR #389, 2026-10-06 | — |
| H1 | 계정 운영 화면(`is_staff` 부여/해제·`is_active` 전환·탈퇴 유예 확인), H14(계정 정지) 흡수 — superuser 전용 `/staff/accounts/` | 트랙 19, PR #340, 2026-09-07 | `docs/BE/staff-account-operations.md` |
| H2 | 이벤트 일괄 선택·일괄 게시 내리기, 목록 인라인 토글/검증, 정렬·기간·카테고리 필터 — 트랙 24(PR #350)·트랙 25(PR #353)·트랙 26(PR #364) | 2026-09-12 | `docs/BE/staff-event-publish-actions.md` |
| H3 | 사용자 제보 드래프트 구분 표시 + 제보 폼 인라인 고지 | 트랙 23, PR #348, 2026-09-09 | `docs/BE/draft-review-lifecycle.md` (l) |
| H4 | 검수 SLA 지표(최장 대기·평균 처리·반려율) | 트랙 22, PR #346, 2026-09-08 | `docs/BE/draft-review-lifecycle.md` (i)~(k) |
| H5 | 반려 드래프트 재오픈 | 트랙 21, PR #345, 2026-09-08 | `docs/BE/draft-review-lifecycle.md` |
| H7 | 감사 범위 확대(드래프트 생성·필드 수정, 액션 2종 사실 기록) | 트랙 20, PR #343, 2026-09-07 | `docs/BE/staff-audit-log.md` |
| H14 | 계정 정지 UI | H1에 흡수, 2026-09-06 | — |
| K1 | 테스트 병렬 실행(pytest-xdist) 도입 — 직렬 134.77초 → `-n auto` 41.72~44.14초(연속 3회), CI "Run test suite" 82초 → 55초, `test` 잡 전체 116초 → 102초 | 트랙 49, PR #407, 2026-10-30 | `docs/BE/test-suite-speed.md` §8 |
| K(43-3) | UI 다국어 — 컬렉션·활동·마이페이지 | PR #397, 2026-10-23 | `docs/BE/i18n.md` |
| K(record-action-link) | 홈 '기록 대기' 행 링크 접근 가능한 이름 — `aria-labelledby`로 행마다 이름이 다름 | 2026-11-18 | `docs/BE/i18n.md` |
| K(시각 의존 테스트) | `test_discovery_runs.py`·`test_agent_drafts.py`의 시각 의존 실패 — 파라미터를 초 단위 오프셋/호출 시점 함수로 교체 | 트랙 45, 2026-10-27 | `docs/BE/test-suite-speed.md` §6 |
| L | 문서 전수검사(2026-10-27) 발견 — 코드·운영 잔여(활동 달력 scroll-margin-top, `static/css/staff/base.css` 중복 제거, 홈 달력 주석 정정, `client_error_views.py` 주석 교체, `auth.css` 폴백 삭제, 폰트 preload 재측정, 트리거 충족 2건, `prompt_plan.md` 트랙 44 머리말 갱신, 어댑터 진행 파일 규약 삭제). 사용자 몫 2건은 "사용자 확인 대기"에 있다 | 트랙 45, 2026-10-27 | `docs/plan-archive/track-45.md` |
| M(잔여 6건) | 트랙 58 보류분 6건 — 로딩 글자 채움색 투명 방식, 폼 검증 접근성(`aria-invalid`), 사이드바 접힘 폭 56.25rem 통일, `.sr-only`·`gi-*` 공용 CSS, 키보드·보조기기 3건, 새 카테고리 색 점(`data-palette-slot`) | 트랙 59, PR #421, 2026-11-18 | `docs/FE/loading-feedback.md`, `docs/FE/design-principles.md`, `docs/BE/category-vocabulary.md` |
| M(완료 보고 10건) | 트랙 59 완료 보고 당시 남겼던 10건 — 새 카테고리 라벨 슬러그 노출, 비한국어 `lang="ko"`, 소비자 JS 한국어 리터럴 가드 포함, 로딩 중 버튼 색 통일, 오류 문장 재낭독, `hscroll.js` 폭 조건 정합, `#visit-global-error` 삭제, `aria-busy` 동기화, `data-feedback-pair`, 내 활동 하단 고정 막대 전환 폭 | 트랙 59, PR #421, 2026-11-18 | `docs/plan-archive/track-59.md`(`#visit-global-error`·`data-feedback-pair` 상세는 `git show 2a8f783a:docs/backlog.md` M절) |
| M(확장) | 확장 중 발견·처리 — 한글 조합 입력 중 실시간 검색·뒤로가기·중복 적재, 고대비 로딩 겹침, 반전 행 찜 버튼 대비, 스태프 로딩 스피너 중심, 결과 영역 밖 링크 검색어 미동기화, 활동 '전체' 칩 정렬 유실, 인코딩만 다른 주소 중복 적재 | 트랙 59, PR #421, 2026-11-17 | `docs/plan-archive/track-59.md` |
| M(확장 2) | 확장 2(홈 '내 컬렉션' 패널) — '기록 대기' 행 클릭 이동, 최근 굿즈 격자 전환, 비공개 전환 행사 링크 제거, 비공개 행사 방문 기록 허용, 방문 완료 판정 통일, 대상 거절 응답 번역, `Event.is_published` 속성 단일화 | 트랙 59, PR #421, 2026-11-18 | `docs/plan-archive/track-59.md`, `docs/BE/visit-completion-concurrency.md` |

## 착수하지 않는 것

- **인프라 계정 액션** — 도메인 등록, PaaS 계약, SMTP 설정(T1~T8). 사용자가
  최후순위로 확정했다. "다음 단계"로 제안하지 않는다. SMTP 미설정 상태에서는
  신규 가입 이메일 인증이 동작하지 않는다는 사실만 기록해 둔다.
- **교환(trade) 매칭** — 밀도·신원·프라이버시·신고·차단·중재·운영 게이트
  승인 전까지 설계도 착수 금지.
- **서버 행사 필드 LLM 추출 재활성화** — 비용 정책상 불허.
  `DRAFT_LLM_EXTRACTION_ENABLED`는 계속 off이며 PaaS에 LLM API 키를 두지 않는다.
- **폐기된 시안 기반 시각 작업** — 과거 시안에서 나온 항목은 계속 착수하지 않는다.
  새 행사 에디토리얼 방향은 D4와 `docs/FE/event-typography-editorial.md`만 따른다.
- **데이터 내보내기(CSV/JSON)** — 어떤 구속 결정에도 없다. 요구가 생기면 그때.

### 폐기한 계획 (2026-11-18 사용자 결정)

사용자 지시 "열린 트랙 폐기. 작업 혼동 가능성."에 따라 아래 계획은 폐기했다.
계획 원문은 `docs/plan-archive/`에 기록으로만 남고, 각 파일 첫 줄에 폐기 표시가
있다. **이 파일들을 실행 계획으로 읽지 않는다.** 다시 하려면 사용자 승인과 새
계획이 필요하고, 옛 계획의 `file:line` 근거는 모두 다시 재야 한다.

| 계획 | 폐기 범위 | 그대로 유효한 것 | 원문 |
|---|---|---|---|
| 트랙 12 비밀번호 생성 경로 보안 | 전체(미착수) | 없음 | `docs/plan-archive/track-12.md` |
| 트랙 31 인스타그램 계정 정기 수집 | 전체(미착수) | 선행 트랙 30(PR #361) | `docs/plan-archive/track-31.md` |
| 트랙 38 어댑터 얇게 | 슬라이스 A·B·C | PR 0 #380·PR 1 #382 | `docs/plan-archive/track-38.md` |
| 트랙 44 행사 다국어 자동 등록 | 44-2·44-3·44-4 | 44-1(PR #399) | `docs/plan-archive/track-44.md` |
| 트랙 50 디자인 시스템 | 예약 트랙 B~E(51~54) | A단계 `docs/FE/design-principles.md` | `docs/plan-archive/track-50.md` |
| C2 소개 페이지 | 전체(미착수, 트랙 50의 E단계) | 없음 | `git show f3e5b3d3:docs/backlog.md` C2 절 |

`docs/BE/i18n.md`, `docs/FE/design-principles.md`, 런북 등 가드레일 문서 본문에
남은 "44-2", "44-3", "44-4", "트랙 B", "트랙 31" 언급은 폐기된 계획을 가리킨다.
그 문장이 적은 조건(예: 화면 노출 전 정규화 통일)은 같은 일을 다시 계획할 때의
조건으로만 읽는다.

---

## 갱신 규칙

- 해결 근거는 "해결된 항목" 표에 PR 번호(또는 커밋)와 정본 문서 링크로 남긴다.
  지운 본문과 검증 결과는 `docs/pr-log.md`와 git 이력에 있다.
- **어떤 항목이 서술한 문제를 고쳤다면, 그 항목의 표기를 같은 커밋에서 바꾼다.**
  이걸 빠뜨려 A1과 A5가 **해결된 지 몇 시간 만에** 미착수로 읽혔고, 두 번 다
  이미 있는 코드를 다시 쓸 뻔했다. 고침과 표기가 갈라지는 순간이 곧 사고 지점이다.
- 새 항목은 `file:line` 근거 없이 추가하지 않는다.
- 낡은 서술을 그대로 사용자에게 전달하지 않는다. 판정 전에 코드로 재확인한다.
  이 저장소는 낡은 백로그가 존재하지 않는 작업을 지시한 사고를 이미 겪었고,
  A1은 **해결된 지 몇 시간 만에** 미착수로 읽혔다.
- **숫자에는 단위와 출처를 붙인다.** 세는 대상(파일인가 등장 횟수인가 테스트
  케이스인가)을 밝히지 않은 수는 증거가 아니며 작업 규모의 근거가 될 수 없다.
  `[실측]`은 명령을 돌려 얻은 수, `[코드]`는 읽어서 센 추정이다. 구속력 있는
  전체 규칙은 `AGENTS.md`의 "Numbers In Documents"에 있다 — 이 백로그가 낳은
  과대 서술 3건이 그 규칙의 근거다.
