# 트랙 23: 사용자 제보 드래프트 구분 표시 + 제보 폼 인라인 고지 — H3 (2026-09-09) [v2 — 7역할 검토 반영]

> **검토 반영 요약(v1 → v2)** [문서 각 역할 산출, 인용 file:line 오케스트레이터 재확인 2026-09-09]
> - PSO: ★1·★3·★4·★5·★6 승인. **★2 정정**: 상세 상단바 라벨은 소비자 화면 용어(`personal_detail.html:103`·`:113` "공식 제보")와
>   통일해 **"공식 제보"**, 큐·인스펙터 배지 "제보"는 승인. 제보자 표시는 배제 유지(운영 기준 문서에 제보 취급 0건 [실측 rg],
>   URL 중복 제보는 `PromotionDuplicateError`가 막음). AC5는 BIR의 `aria-describedby` 판정을 반영.
> - DAR: `origin` 이름·TextChoices·default·앱 상수 라벨·서비스 키워드 인자(호출자 web 지정)·`_build_draft_rows` 확장 승인.
>   권고: 문서 (l)에 "백필 불가"와 "이 마이그레이션 이전 행은 실제 경로와 무관하게 collected로 **오표시**된다"를 별개 문장으로.
>   정정: `create_draft_from_fields`는 `drafts/services.py:207`, `_build_draft_rows`는 `staff/views/drafts.py:101` [실측 grep].
> - SRR: 차단 없음. 고지 문장은 방침 §3·약관과 일치(정정 불필요), `origin`에 PII 없음, `/api/event-drafts/`는 `IsAdminUser`.
>   QVL 항목 추가: 구현 후 소비자 템플릿(`templates/core/events/*.html`)에 `origin` 참조 0건 확인.
> - DOR: 차단 없음. 0008 기대 SQL = `ADD COLUMN "origin" varchar(20) DEFAULT 'collected' NOT NULL` → `ALTER COLUMN "origin" DROP
>   DEFAULT`(선례 0003 `extraction_method`). **롤백은 코드 우선이 아니다** — NOT NULL·DB default 제거라 구코드 INSERT가 깨지므로
>   `migrate drafts 0007`(DROP COLUMN) 역방향을 코드 롤백과 함께 실행(문서 (g) 예외로 기록). 무중단 배포 시 구컨테이너 병행
>   구간의 INSERT 실패 위험은 0002·0003과 같은 기존 패턴 → 런북 일반 절로 이연.
> - WED: 배지 신규 클래스 `queue-origin-badge`(`--c-accent-soft` 배경·`--c-accent` 글자 [실측 tokens.css:28-29·65-66 라이트·
>   다크 정의], 약 12줄 [계산]), 인스펙터 헤드 재사용(추가 CSS 0줄 — `gap` 처리), 상세는 텍스트 접두(`source_name` 빈 값이라
>   출처 세그먼트는 기존 조건으로 자동 생략), 고지는 기존 `.promote-note` 문단 끝에 이어 붙임(소비자 CSS 무변경, 390px 자연
>   줄바꿈). 행 높이는 기존 3줄 패턴 범위 확장.
> - BIR: 배지는 순수 텍스트(`aria-label` 불필요), `queue-status-chip` 클래스·`data-draft-status-chip` 속성 미부여(`draft_bulk.js:348·
>   352·361` 셀렉터 비충돌), J/K 전환·일괄 처리 후 배지 유지. **신규 발견**: 같은 제보 폼이 개인 기록 목록 partial
>   `templates/core/partials/_archive_results_personal.html:114-119`에도 있다(문구 동일 [실측 grep]) → 고지 문장과
>   `aria-describedby`(`.promote-note`에 `id="promote-note-{{ id }}"`, 입력에 연결)를 **두 진입점 모두** 적용(오케스트레이터
>   결정: 같은 행동·같은 공개 함의, 사용자 표준 결정 2026-08-25). 배지 순서 이견(WED: 출처 뒤·상태 칩 앞 / BIR: 상태 칩 뒤)은
>   인스펙터(상태 → 유입 경로)와 읽기 순서를 맞추는 **상태 칩 뒤**로 확정.
> - TDD 코치: Test List 확정(아래). S3는 새 노드 없이 기존 URL 생성 테스트에 단언 1줄, S1·S2는 병합하지 않음(경계 다름).
>   `REVIEW_STATUS_LABELS` 계약 테스트는 저장소에 없다 [실측 rg] — v1의 "선례 동형" 전제 오류. `ORIGIN_LABELS` 계약은 스태프
>   액션 라벨 계약(`tests/staff/test_staff_action_labels.py`)과 같은 유형이라 채택(신규 파일 `tests/drafts/test_draft_labels.py`).

> 배경: `docs/backlog.md` H3(P1, 제품 권고). 사용자 지시(2026-09-09) "머지 진행 뒤 H3 진행" — #344·#345·#346 머지 완료
> (main a6b962c). 계약(2026-09-06 외부 검토 반영): 구분 표시에 `source_name`을 쓰지 않는다 — 승인 시 이벤트로 복사돼
> 소비자 상세에 "N 제공"으로 노출(`templates/core/events/detail.html:33-34` [실측 sed])되고 스태프 수집분은
> `DraftSource.name`(`drafts/candidate_intake.py:62`), 제보분은 빈 값이라 운영용 유입 경로 필드를 따로 둔다. 고지 문안은
> 메모가 `summary`로 매핑돼(`web/promotion.py:81` `summary=entry.memo` [실측 cat]) 검수 후 공개 요약에 쓰인다는 내용이며,
> 개인정보처리방침 §3(`templates/core/legal/privacy.html:52-56`)·약관(`terms.html:75-77`)에 이미 고지가 있어 SRR Low(문구
> 권고). 사실 [실측 2026-09-09]: `EventDraft`에 유입 경로 필드 없음(`drafts/models.py`), 생성 경로는 제보
> `web/promotion.py:74`(`create_draft_from_fields`), 스태프 admin API `staff/views/draft_api.py`(URL 생성), 자동 수집
> `drafts/management/commands/discover_drafts.py`, 러너 후보 검증 `drafts/candidate_validation.py`(둘 다 `create_draft_from_url`);
> 제보는 드래프트 id를 `PersonalEntry`에 남기지 않아(`PromotionResult.draft_id`만 반환) 기존 제보 드래프트 역추적 불가.
> 큐 표는 `colgroup` 고정폭(`templates/core/drafts/list.html:66-73`)이라 열 추가 금지, 제목 셀(`:97-106`) 안 인라인 배지
> (프론트 사전 검토 `.docs/FE/2026-09-06-staff-backoffice-frontend-review.md:41`·`:115`·`:158`). 인스펙터 헤드(`:143-146`)는
> `#id` + 상태 칩. 제보 폼 안내 문단 `templates/core/archive/personal_detail.html:115` `.promote-note`(생성 화면
> `personal_create.html:114-116`의 배너는 별개 문구 — 이번 범위 밖). 최신 마이그레이션 drafts 0007 [실측 ls]. 기준선
> [실측 2026-09-09 main a6b962c] `uv run pytest -q` 2474 passed / 73.21초.

## 승인 범위 (★ = 사용자 미확인 가정 — PSO 판정 병기)

1. **모델** `EventDraft.origin = CharField(max_length=20, choices=Origin.choices, default=Origin.COLLECTED)`,
   `class Origin(TextChoices): COLLECTED = "collected", "Collected"; USER_REPORT = "user_report", "User report"`. 마이그레이션
   drafts 0008(AddField default — 기존 행 전부 `collected`). ★1 값은 둘만: 스태프 수동 생성·자동 수집·러너 후보는 모두
   `collected`(운영자 관심은 "사용자가 낸 것인가"뿐, 세분화는 choices-only 마이그레이션으로 나중에 가능). ★4 기존 제보
   드래프트는 역추적 불가라 백필하지 않는다(문서화).
2. **서비스** `create_draft_from_fields(*, ..., origin=EventDraft.Origin.COLLECTED)` 키워드 추가(`drafts/services.py`),
   `web/promotion.py`가 `origin=EventDraft.Origin.USER_REPORT`를 넘긴다(web은 drafts를 이미 임포트). `create_draft_from_url`·
   `persist_prepared_draft`는 무변경(기본값). 한국어 라벨은 `drafts/labels.py`에 `ORIGIN_LABELS = {"collected": "수집",
   "user_report": "공식 제보"}`(모델 choices 라벨은 영어 유지 — `REVIEW_STATUS_LABELS` 선례; ★2 PSO 정정). 라벨 계약 테스트
   `tests/drafts/test_draft_labels.py` 신설(`set(ORIGIN_LABELS) == set(Origin.values)`).
3. **API** `EventDraftSerializer.fields`·`read_only_fields`에 `origin`, `EventDraftUpdateSerializer.read_only_fields`에도
   `origin`(트랙 21 DAR 결함 선례 — 빠지면 PATCH 본문의 origin이 `update_draft`로 내려가 500). ★6 노출은 읽기 전용.
4. **화면**(WED 사양 + BIR 기준 확정):
   (a) 큐 표 제목 셀(`list.html:97-106`) `<a class="queue-row-open">` 안, 상태 칩(`:103-105`, 전체 보기에서만 렌더) **뒤**에
   `{% if row.draft.origin == "user_report" %}<span class="queue-origin-badge">제보</span>{% endif %}` — 상태 칩이 없는 필터
   탭에서는 출처 span 뒤에 배지만 남는다. 순수 텍스트(`aria-label` 없음), `queue-status-chip` 클래스·`data-draft-status-chip`
   속성 금지. CSS(`static/css/staff/pages/drafts.css`, `.queue-row-open .queue-status-chip` 규칙 뒤): `.queue-origin-badge {
   display: inline-flex; font-size: 0.65625rem; font-weight: 700; padding: 0.125rem 0.4375rem; border-radius: 0.1875rem;
   background: var(--c-accent-soft); color: var(--c-accent); white-space: nowrap; }` + `.queue-row-open .queue-origin-badge {
   margin-top: 0.125rem; }` — 약 12줄 [계산], transition·animation 없음.
   (b) 인스펙터 헤드(`:143-146`) 상태 칩 뒤에 같은 `<span class="queue-origin-badge">제보</span>`(추가 CSS 0줄 [계산], `gap`).
   (c) 상세 상단바 메타(`detail.html:27-31`) `<span class="mono review-topbar-meta">` 맨 앞에 `user_report`면 "공식 제보 · "
   텍스트 접두(★2 PSO 정정 — 배지 아님). 뷰: `_build_draft_rows`(`staff/views/drafts.py:101`)에 `origin_label`(`ORIGIN_LABELS`)
   추가, 상세 뷰 컨텍스트 `origin_label`. 템플릿 분기는 `origin == "user_report"` 값 비교(라벨은 표시용).
   (d) 제보 폼 고지 — **두 진입점**: `templates/core/archive/personal_detail.html:115`와
   `templates/core/partials/_archive_results_personal.html:115`의 `.promote-note` 문단 끝에 ★3 문장을 이어 붙인다(별도 `<p>`
   금지, 소비자 CSS 무변경): "제보가 승인되면 이 항목의 메모가 공개 이벤트의 요약으로 함께 공개됩니다." 그리고 문단에
   `id="promote-note-{{ entry.id }}"`(partial은 `row.entry.id`), 입력 `#promote-url-…`에 `aria-describedby="promote-note-…"`
   (BIR — 토글 뒤 `input.focus()`라 문단이 자동으로 읽히지 않음). 신규 안내 카드 금지(no-guide-text-policy). ★5 유입 경로
   필터·탭은 없음(이연).
5. **문서**: `docs/BE/draft-review-lifecycle.md` (l) 유입 경로 필드 — 값·설정 경로·`source_name`과의 구분, "백필 불가"와
   "0008 이전 행은 실제 경로와 무관하게 collected로 오표시된다"(DAR, 별개 문장), (g)에 예외 1줄 — 0008은 NOT NULL·DB default
   제거라 롤백 시 `migrate drafts 0007` 역방향을 코드 롤백과 함께(DOR); `docs/BE/archive-personal-entry-api.md` "공식 제보와의
   관계" 절에 origin 1줄; `docs/FE/personal-place-detail-edit.md`에 고지 문장·`aria-describedby` 결정 1줄; 백로그 H3 완료;
   pr-log(머지 시).

## 배제 (범위 밖)
- 유입 경로 필터·통계(H9와 함께), 스태프 수동/자동/러너 세분화, 기존 드래프트 백필, 제보자 식별 저장(개인정보 —
  `PersonalEntry`와 드래프트 연결 없음 유지), 생성 화면 배너 문구 변경, 소비자 이벤트 상세 노출.

## 수용 기준
- AC1 제보(`promote_personal_entry`)로 만든 드래프트는 `origin == "user_report"`; `create_draft_from_fields` 기본값·
  `create_draft_from_url`·admin API URL 생성은 `collected`.
- AC2 `/api/event-drafts/` 응답에 `origin` 포함, PATCH 본문의 `origin`은 무시되고 500이 나지 않는다.
- AC3 큐 표: `user_report` 행에만 "제보" 배지, `collected` 행에는 없음(`colgroup` 불변). 인스펙터 헤드도 동일.
- AC4 상세 상단바: `user_report`면 "공식 제보 · " 접두 노출, `collected`면 없음.
- AC5 제보 폼 `.promote-note`에 고지 문장 렌더 — 개인 기록 상세(`personal_detail.html`)와 개인 기록 목록 partial
  (`_archive_results_personal.html`) 두 곳, 문단 `id`와 입력 `aria-describedby` 연결(폼이 안 보이는 분기는 기존 그대로).
- AC6 마이그레이션 0008 동기화, `sqlmigrate`로 `DEFAULT 'collected' NOT NULL` → `DROP DEFAULT` 확인, 회귀·check 통과, 소비자
  템플릿 `origin` 참조 0건 [rg](SRR).
- AC7 브라우저: 스태프 큐에서 제보 드래프트 배지(행 링크 접근 가능 이름에 "제보" 포함, collected 행은 없음)·J/K 전환 후
  인스펙터 배지 유지·상세 메타 확인, 소비자 개인 기록 상세와 목록에서 제보 폼 토글 → 고지 문장·입력의 접근 가능 설명
  (`aria-describedby`) 확인(1280px·390px), 콘솔 오류 없음. 임시 데이터·캡처 삭제.

## Activated Roles / Not Activated (확정 — 7역할 사전 검토 완료 2026-09-09)
- Activated: PSO(★1~★6), DAR(필드·라벨 소유, 서비스 시그니처, web→drafts 방향), Backend TDD Coach(Test List), SRR(고지 문구가
  방침 §3과 일치하는지 — 경량), DOR(0008 default AddField — 경량), WED·BIR(배지·칩·고지 사전·사후), BIE·FIE, QVL.
- Not Activated: AI Automation Architect(무관).

## Domain Boundary and Dependency Direction
- drafts 소유: 필드·choices·라벨·서비스 인자. web 소유: 제보 경로에서 값 지정(web → drafts 기존 방향). staff 소유: 표시(라벨
  맵 임포트, staff → drafts). archive 무변경(드래프트 연결 없음). 서명 규약: `create_draft_from_fields`는 `SERVICE_MODULES`
  대상(`drafts.services`) — 키워드 전용 유지.

## Test List (TDD 코치 확정) [문서 코치 산출]
- M1 `test_origin을_지정하지_않으면_기본값_collected로_저장된다`(`tests/drafts/test_draft_models.py`) — Red: AttributeError(필드
  없음) → 필드 추가 → 컬럼 부재 ProgrammingError → 0008 → Green.
- S3 기존 `test_관리자가_url로_이벤트_드래프트를_생성하면_추출된_필드와_함께_저장된다`(`tests/staff/test_staff_draft_api.py:36-58`)에
  `assert created.origin == EventDraft.Origin.COLLECTED` 1줄 추가(새 노드 없음, M1과 함께 Green — 새 코드 없이 Green임을 기록).
- S2 `test_create_draft_from_fields는_origin_인자를_받아_그대로_저장하고_생략하면_collected다`(parametrize "인자_생략"/"user_report_전달",
  `tests/drafts/test_drafts_services.py`) — Red: 전달 케이스 TypeError(키워드 없음).
- S1 `test_비공식_항목을_공식_URL과_함께_승격하면_생성된_드래프트의_origin이_user_report다`(`tests/archive/test_promotion_service.py`)
  — Red: AssertionError(collected) → `web/promotion.py`가 `origin=USER_REPORT` 전달.
- L1 `test_ORIGIN_LABELS의_키는_Origin_choices값과_일치한다`(신규 `tests/drafts/test_draft_labels.py`) — Red: ImportError.
- A1 `test_이벤트_드래프트_상세_응답은_origin을_포함한다`(`tests/staff/test_staff_draft_api.py`) — Red: KeyError.
- A2 `test_수정_요청_본문의_origin은_무시되고_500이_나지_않는다`(같은 파일, `reopened_at` 선례 `:180-193` 복제) — Red: 500.
- V1 `test_사용자_제보_드래프트만_목록_행에_배지가_붙는다`(`tests/staff/test_staff_draft_views.py`) — user_report 행 슬라이스
  (`data-draft-id="N"` ~ `</tr>`)에 `<span class="queue-origin-badge">제보</span>` 있음 + collected 행 슬라이스에 없음(양성·음성 짝).
- V2 `test_사용자_제보_드래프트만_인스펙터_헤드에_배지가_붙는다`(같은 파일, 패널 슬라이스).
- V3 `test_상세_상단바는_공식_제보_드래프트에만_공식_제보_접두를_보여준다`(parametrize user_report/collected).
- P1 `test_미제출_비공식_장소_상세를_열면_제보_고지_문장과_입력_설명_연결이_보인다`(`tests/archive/test_archive_personal_entry_detail_view.py`,
  `user_client`·`make_entry(kind=PLACE)`) — 문장 + `id="promote-note-<id>"` + `aria-describedby="promote-note-<id>"`.
- P2 `test_개인_기록_목록의_제보_폼에도_고지_문장과_입력_설명_연결이_보인다`(개인 기록 목록 페이지 렌더 테스트 파일 — BIE가
  `rg -ln "personal_entries\|/archive/personal/" tests/archive`로 배치, partial `_archive_results_personal.html` 경로).

## 구현 순서 (슬라이스별 커밋, pytest 실행·판정은 오케스트레이터 단독)
운영 방식은 트랙 21·22와 같다(테스트 먼저 → Red 기록 → 최소 구현 → Green → 조기 Green 뮤테이션 → 커밋).
1. M1·S3·S2·S1·L1 → 모델 필드(0008은 M1 컬럼 부재 Red 뒤) → 라벨 → 서비스 인자 → 제보 경로 → 커밋
   `feat(drafts): 드래프트 유입 경로 origin과 제보 경로 지정`
2. A1·A2 → serializer(`EventDraftSerializer`·`EventDraftUpdateSerializer`) → 커밋 `feat(staff): 드래프트 API origin 읽기 전용 노출`
3. V1~V3·P1·P2 → 뷰 라벨·템플릿·CSS·제보 폼(상세·목록 partial) + 브라우저(AC7) → 커밋 `feat: 제보 드래프트 배지와 제보 폼 공개 고지`
4. 문서 → 커밋 `docs: 드래프트 유입 경로 가드레일과 H3 종결`

## 검증 명령과 기대 증거
- `uv run pytest -q tests/drafts tests/archive/test_promotion_service.py tests/archive/test_promotion_api.py tests/staff/test_staff_draft_views.py tests/staff/test_staff_draft_api.py`
- `uv run pytest -q` 전체(기준선 2474), `manage.py check`, `makemigrations --check`, `sqlmigrate drafts 0008`(기대: `ALTER TABLE
  "drafts_eventdraft" ADD COLUMN "origin" varchar(20) DEFAULT 'collected' NOT NULL;` 다음 `ALTER TABLE "drafts_eventdraft" ALTER
  COLUMN "origin" DROP DEFAULT;`), `rg -n "origin" templates/core/events/` 0건.
- 브라우저 AC7.

## Frontend Review Evidence [문서 WED·BIR 사전 산출 2026-09-09]
- 검토 깊이: **Standard**(WED·BIR 동의) — 배지 2곳·메타 접두·고지 문장 2곳, 상호작용 없음, 링크 접근 이름·JS 셀렉터 분리·
  `aria-describedby` 기준 확인 필요.
- WED 사전 사양: 승인 범위 4에 통합(배지 클래스·토큰·CSS 규칙, 인스펙터 재사용, 상세 텍스트 접두, 고지 문단 이어 붙임, 390px
  자연 줄바꿈, colgroup 무변경). 수용 기준: AC-a colgroup 무변경·user_report 행에만 배지 / AC-b 인스펙터 재사용·CSS 0줄 /
  AC-c 상세 접두·`source_name` 빈 값 시 출처 세그먼트 자동 생략 / AC-d `.promote-note` 이어 붙임·소비자 CSS diff 없음.
- BIR 사전 기준: (1) 배지 순수 텍스트·`aria-label` 없음, 상태 칩 뒤 순서 (2) `queue-status-chip` 클래스·`data-draft-status-chip`
  속성 미부여 (3) `.promote-note` `id` + 입력 `aria-describedby`, 두 진입점 모두 (4) 신규 CSS transition·animation 없음.
- 계획된 브라우저 증거(BIR 목록): 스태프 큐 1440px — collected/user_report 행 링크 접근 가능 이름, J/K로 user_report 패널 이동
  후 헤드 배지 유지, 콘솔; 상세 상단바 user_report/collected 각 1건; 소비자 개인 기록 상세·목록 1280px·390px — 토글 전 폼
  hidden → 토글 후 입력 포커스·`aria-describedby` 설명 값·고지 문장; 콘솔 0건.
- **수집된 브라우저 증거** [실측 2026-09-09, Chrome DevTools MCP, 로컬 runserver, 임시 스태프·일반 계정 → 검증 후 삭제]:
  (1) 스태프 큐 1440px 전체 보기: user_report 드래프트(임시 #56) 행 링크 접근 가능 이름 "H3 검증용 제보 드래프트 … 검토 대기
  제보"(상태 칩 뒤 배지), 배지 클래스 `queue-origin-badge`만·`data-draft-status-chip` 없음, 같은 페이지의 collected 행에는
  배지 없음(배지 행 = #56만), 인스펙터 헤드 "#56 검토 대기 제보 …". J → 패널 #50(배지 없음) → K → #56 배지 유지. 배지 계산
  스타일 `inline-flex`·배경 rgb(229, 239, 255)·글자 rgb(31, 111, 235)(`--c-accent-soft`/`--c-accent`) — 첫 로드는 브라우저
  캐시의 옛 drafts.css라 미적용으로 보였고 캐시 무시 재로드 뒤 적용 확인(개발 환경 캐시, 결함 아님). 콘솔 0건. 캡처 `track23-01`.
  (2) 상세 #56 상단바 "공식 제보 · 휴리스틱 추출"(출처 세그먼트 자동 생략), collected #19 "출처 예시 소스 · LLM 추출 · 신뢰도
  50%"(접두 없음). 캡처 `track23-02`.
  (3) 소비자 개인 기록 상세 `/archive/personal/197/` 1280px: 토글 전 폼 hidden·`aria-expanded=false` → 토글 후 폼 표시·입력
  포커스, 문단 `id="promote-note-197"`, 입력 `aria-describedby="promote-note-197"` 일치, 고지 문장 렌더, 문단 418px×77px. 콘솔은
  기존 폰트 preload 경고 2건 [실측](트랙 14 셸 공통, 무관). 캡처 `track23-03`. 390px 에뮬레이션(창 최소 폭 500px라 `emulate`
  사용): 문단 358px×102px(4줄), 가로 스크롤 없음, 입력 포커스. 캡처 `track23-04`.
  (4) 개인 기록 목록 `/archive/personal/` 390px(partial): 항목 197 토글 → 폼 표시·입력 포커스·id/`aria-describedby` 일치·고지
  문장·가로 스크롤 없음. 콘솔 0건. 캡처 `track23-05`.
- **뮤테이션 기록**: A2(Update read_only에서 origin 제거 → 500 Red), V1·V2(배지 무조건 렌더 → 음성 단언 Red), V3(접두 무조건 →
  collected 케이스 Red). S3는 M1과 함께 새 코드 없이 Green(모델 기본값), A2는 serializer에 origin 추가 전 이미-Green(DRF가
  미지 필드를 무시) → 추가 후 뮤테이션으로 핀 확인. 정정 기록: 브리프 줄 번호 `create_draft_from_fields` 204 → 207,
  `_build_draft_rows` 100 → 101 [실측 grep]; v1의 "REVIEW_STATUS_LABELS 계약 테스트 선례" 전제는 오류(없음, TDD 코치).
- **WED 사후 판정: Conforms** [문서 WED 산출 2026-09-09] — AC-a(colgroup 무변경·user_report 행만 배지, `list.html:66-73`·`:106`),
  AC-b(인스펙터 재사용·전용 CSS 없음, `:146`), AC-c(상세 텍스트 접두·출처 세그먼트 자동 생략, `detail.html:30-31`), AC-d(두 진입점
  `.promote-note` 이어 붙임·새 요소 없음) 전부 코드·캡처 일치. 배지 순서(상태 칩 뒤) 확정에 재이의 없음. CSS 규칙 13줄
  [실측 sed](사양 약 12줄과 근접). 요청한 소비자 CSS diff 재확인: `git diff main...HEAD --stat -- static/css/pages/` = 0줄 [실측].
  #19 대비 캡처는 없고 DOM 실측(접두 없음)으로 대체.
- **BIR 사후 판정: Conforms** [문서 BIR 산출 2026-09-09] — (1) 순수 텍스트·칩 뒤 순서 (2) `draft_bulk.js:348·352·361` 셀렉터
  비충돌, `data-draft-status-chip`·`queue-status-chip` 참조 JS는 `draft_bulk.js` 1파일 [실측 rg] (3) 두 진입점 id·`aria-describedby`,
  `input.focus()` 로직 무변경 (4) transition·animation 없음. J/K는 `setCurrentRow`(`draft_bulk.js:194-216`)가 hidden·class만 토글해
  배지 소실 구조 없음. 잔여 Low: 일괄 승인/반려 뒤 배지 유지 브라우저 미실측(코드 검토 대체), 스크린리더 실기 청취 미수행.
- **QVL 1차 판정: 조건부 완료**(2026-09-09) — AC1~AC7·게이트 충족, 잔여 2건: (a) AC3 "필터 탭에서 상태 칩 없이 배지만 남는
  경우"가 테스트·캡처 모두 전체 보기만 다룸 (b) 뷰가 만든 `origin_label`이 큐 행에서 미사용(죽은 출력). **같은 트랙에서 해소**
  (커밋 5de83e7): V1을 `""`/`?status=pending` parametrize로 확장(대기 필터에서 user_report 행 배지·collected 행 없음), 큐 행
  dict의 `origin_label` 제거, 상세 접두는 `{{ origin_label }} · `(ORIGIN_LABELS, 렌더 결과 동일). 재실행: 뷰·API 89 passed,
  전체 2488 passed / 87.77초 [실측]. 그 외 QVL 잔여(Low, 이연): `create_draft_from_fields(origin=)` 인자 choices 검증 없음(호출자
  1곳 상수), 0008 롤백 리허설 없음(문서화), 일괄 처리 후 배지 유지 브라우저 미실측(코드 검토).
- **QVL 재판정: 완료**(2026-09-09) — 잔여 2건 해소를 코드로 직접 확인(V1 parametrize `:93-104`, `_build_draft_rows` 키 제거,
  `detail.html:30` `{{ origin_label }}` 렌더, `rg origin_label` 2건 [실측]). 잔여 Low는 위 이연 기록대로. 캡처 5장 [실측 ls]은
  재판정 뒤 삭제.

## 이연
- `create_draft_from_fields(origin=)` 값 검증(호출자가 늘면 choices 검사 추가), 0008 롤백 리허설.
- 유입 경로 필터·통계(H9), 세분화 값, 백필, 생성 화면 배너 문구, 런북 일반 절 "NOT NULL AddField + 무중단 배포 병행 구간"(DOR,
  0002·0003에도 소급되는 일반 위험), Render 컨테이너 교체 방식 확인.

## 문서 대상·핸드오프 조건
- `docs/BE/draft-review-lifecycle.md` (l), `docs/BE/archive-personal-entry-api.md` 1줄, `docs/backlog.md` H3 항목 완료, pr-log(머지 시).

---

