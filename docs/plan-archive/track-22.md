# 트랙 22: 검수 SLA 지표 — H4 (2026-09-08) [v2 — PSO·DAR·TDD 코치·WED·BIR 검토 반영]

> **검토 반영 요약(v1 → v2)** [문서 각 역할 산출, 인용 file:line 오케스트레이터 재확인 2026-09-08]
> - PSO: ★1~★5 전부 수용. SLA 목표치는 운영 기준 문서에 없음(`docs/event-operations-criteria.md:51`은 만료 행사 주 1회
>   정리) → 목표 대비 표시 안 함 확정. 보강: V3에 노트 문구 단언, 혼재 상태(대기 있음 + 결정 없음) 케이스는 V3가 겸한다.
> - DAR: `drafts/queries.py` 소유·dict 반환·`now=None` 주입(선례 `accounts/services.py` `execute_pending_deletions`)·뷰 헬퍼
>   같은 파일 승인. R1 **레거시 결정 건**: `approved_at`/`rejected_at`이 None인 승인·반려 드래프트(0002 마이그레이션이 데이터
>   이관 없이 필드를 추가)는 `Case` 결정 시각이 NULL이라 창 필터에서 자동 제외 — 로컬 DB 승인 4건 전부·반려 4건 [실측 shell]
>   이 그렇다 → Q8 핀 + 문서 (i) 명문화. R2 `drafts.queries`는 서명 규약 가드 `SERVICE_MODULES` 미포함 — 키워드 전용은 모듈
>   내부 관례. R3 `staff/views/__init__.py`는 276줄 [실측 wc](브리프 274는 오기, 정정 기록). 이연: `decided_at` Case 필터는
>   인덱스를 못 탄다(건수 수만 규모 도달 시 부분 인덱스 검토).
> - TDD 코치: Q4·Q5(창 안/밖) 병합 → Q1~Q7 + DAR Q8. V4는 기존 「검토 대기」 카드가 같은 href를 써서 이미-Green 위험 →
>   라벨 "최장 대기"와 href를 같은 `<a>` 안에서 묶는 정규식. 시각 제어 = `now` 주입 + `created_at`은 `update()`(auto_now_add).
>   V2·V3는 S5 범위 정규식(라벨 `<p>`부터 카드 닫는 태그까지).
> - WED: 왼쪽 열 맨 위 확정(1024px에서 `.dash-layout`은 이미 1단 — `dashboard.css:423-427` `max-width: 74.9375rem` — 카드당
>   약 259px [계산]). **값 없음 표기는 하이픈 `-`**(콘솔 전역 `default:"-"` 관례, `—`는 placeholder·구두점 용도뿐 — v1 정정).
>   단위: 48시간 미만 "시간", 이상 "일"(정수 round, 최장 대기·평균 처리 공통), 반려율 "%". 메타 `dash-panel-head-meta--end`
>   (액션 없는 패널 규약). 최장 대기 카드는 대기 없음이어도 링크 유지. CSS 변형 6줄 [계산].
> - BIR: Medium 2건(사전 명세 공백) — (1) 값 없음 노트는 값과 **같은 컨테이너(`<a>`/`<article>`) 안 자식**이어야 스크린리더가
>   의미를 얻는다(형제 분리 금지) (2) 포커스 링(`base.css:82-88` outline 2px + offset 2px)이 `.dash-panel`·`.dash-metrics`의
>   `overflow: hidden`에 잘릴 위험 → Tab 포커스 캡처로 실측. `value`는 표시 직전 문자열만 컨텍스트로(정수 0 falsy 오판 방지).
>   신규 CSS에 transition·animation 금지. 권고(비필수): `.sr-only` "데이터 없음" 병기 — 채택하지 않음(WED polish 없음, 노트
>   문장이 같은 컨테이너 안에 있어 최소 조건 충족).

> 배경: `docs/backlog.md` H4(P1, 제품 권고) — 대시보드는 검토 대기 건수만 보여준다(`staff/views/__init__.py`
> `dashboard`, `draft_review_stats`). 설계 확정 항목 중 "재오픈 후 대기 시간의 기산점"은 트랙 21 ★2로 확정(`reopened_at`
> 있으면 그 값, 없으면 `created_at`, `docs/BE/draft-review-lifecycle.md` (c)), "반려율 계산 기준"은 이 트랙에서 정한다.
> 프론트 사전 검토 원문 `.docs/FE/2026-09-06-staff-backoffice-frontend-review.md:42`(WED: `dash-panel` 1개 또는 지표 카드
> 최대 4장 [문서], "0건"과 "데이터 없음"을 구분해 표시 — S5)·`:159`(BIR: 정적 렌더, 상호작용 없음, 기존 `dash-metric`
> 마크업). 사실 [실측 2026-09-08]: `.dash-metrics`는 `grid-template-columns: repeat(5, 1fr)` 5칸 고정
> (`static/css/staff/pages/dashboard.css:19-27`), 기존 증감 카드 3장은 7일 창·직전 7일 비교(`templates/staff/dashboard.html`
> 10-18행 주석: 과거 스냅샷이 없는 카드는 증감을 지어내지 않는다 — M5). ORM 프로토타입 `manage.py shell`: 기산점
> `Coalesce("reopened_at", "created_at")`, 결정 시각 `Case(When(approved → approved_at), When(rejected → rejected_at))`,
> `Avg(ExpressionWrapper(F("decided_at") - F("started_at"), output_field=DurationField()))`가 Postgres에서 실행됨(로컬 DB:
> 최근 7일 결정 0건 → `avg_handling=None`, 대기 중 최장 기산점 2026-07-31). 로컬 DB에 반려 사유가 있는 드래프트 0건 [실측 shell].
> 브랜치 `feat/review-sla-metrics` = `feat/draft-reopen`(PR #345, CI 4체크 pass [실측]) 위 스택 — `reopened_at` 필드를
> 소비하므로 트랙 21 머지 전에는 main에서 갈라설 수 없다. PR base는 `feat/draft-reopen`로 열고 #345 머지 후 main으로 재지정.
> 기준선 [실측 2026-09-08 feat/draft-reopen] `uv run pytest -q` 2461 passed / 70.98초.

## 승인 범위 (★ = 사용자 미확인 가정 — PSO 판정 병기)

1. **조회** `draft_review_sla(*, days=7, now=None)`(`drafts/queries.py`, `draft_review_stats` 옆, 키워드 전용) → dict:
   `longest_wait`(timedelta | None: 검토 대기 중 기산점 최솟값 기준 `now − 기산점`, 대기 없음이면 None) /
   `avg_handling`(timedelta | None: 창 `[now − days, now)`에 결정된 드래프트의 `결정 시각 − 기산점` 평균, 결정 없음이면
   None) / `rejection_rate`(float 0.0~1.0 | None: 같은 창의 결정 중 반려 비율) / `pending_count`·`decided_count`·
   `rejected_count`(int). 결정 시각 = 현재 상태가 approved면 `approved_at`, rejected면 `rejected_at`.
   ★1 **반려율·평균 처리의 집계 원천 = 드래프트 필드(현재 상태 + 결정 시각)**, 감사 로그가 아니다. 재오픈 → 재승인된
   드래프트는 승인 1건으로만 센다(과거 반려 기록 필드가 남아 있어도 `review_status`가 approved이므로). 근거:
   `draft_review_stats`와 같은 원천, 감사 보존 정책(H12(b) 미결)과 무관, 일괄 승인·반려도 드래프트마다 시각이 찍힘.
   ★2 창 = 7일(기존 증감 카드 3장 [코드]과 동일). 직전 7일 비교(증감)는 넣지 않는다 — 카드 폭·해석 부담 대비 가치가 낮고,
   결정 건수가 주당 한 자리일 때 비율 증감은 노이즈다(PSO 판단).
   ★3 **사유 분포는 이 트랙에서 제외** — `rejection_reason`은 자유 텍스트라 H10(사유 템플릿) 전에는 분포가 성립하지
   않고, 로컬 사유 보유 0건 [실측]. "사유 없음 비율"도 넣지 않는다.
2. **대시보드 뷰**(`staff/views/__init__.py` `dashboard`): `review_sla = draft_review_sla()`를 호출하고 표시용 변환
   헬퍼 `_build_review_sla_cards(sla)`(같은 파일, `_build_activity_columns` 옆)가 카드 3장 [계산]의 dict 목록을 만든다 —
   `label`·`value`(**문자열** 또는 None — 정수 0도 `"0"` 문자열로, BIR)·`unit`·`note`·`href`. ★4 단위(WED 확정): 최장
   대기·평균 처리는 `total_seconds()/3600`이 48 미만이면 `round` 정수 + "시간", 48 이상이면 `round(hours/24)` + "일";
   반려율은 `round(rate*100)` + "%". None이면 `value=None` → 템플릿이 하이픈 `-`를 보여주고(`{% if card.value is not None %}`
   분기) 단위 span을 렌더하지 않으며 노트에 "검토 대기 없음"/"최근 7일 결정 없음"을 쓴다(S5: 0과 데이터 없음 구분). 노트(값
   있을 때): 최장 대기 → "대기 {pending_count}건", 평균 처리 → "결정 {decided_count}건 기준", 반려율 → "반려 {rejected_count}건
   / 결정 {decided_count}건". 레거시(결정 시각 None) 승인·반려 건은 창 집계에서 자동 제외(DAR R1, Q8).
3. **화면** ★5(WED 사양 + BIR 기준 확정): `templates/staff/dashboard.html` 왼쪽 `dash-col`(`:90`) 첫 자식으로
   ```
   <section class="dash-panel">
     <div class="dash-panel-head">
       <h2 class="dash-panel-head-title">검수 SLA</h2>
       <span class="mono dash-panel-head-meta dash-panel-head-meta--end">최근 7일 결정 기준</span>
     </div>
     <div class="dash-metrics dash-metrics--3">
       {% for card in review_sla_cards %}
         {% if card.href %}<a class="dash-metric dash-metric-link" href="{{ card.href }}">{% else %}<article class="dash-metric">{% endif %}
           <p class="dash-metric-label">{{ card.label }}</p>
           <p class="dash-metric-value-row">
             <span class="mono dash-metric-value">{% if card.value is not None %}{{ card.value }}{% else %}-{% endif %}</span>
             {% if card.value is not None %}<span class="dash-metric-unit">{{ card.unit }}</span>{% endif %}
           </p>
           <p class="dash-metric-note">{{ card.note }}</p>
         {% if card.href %}</a>{% else %}</article>{% endif %}
       {% endfor %}
     </div>
   </section>
   ```
   최장 대기 카드만 `href="/staff/drafts/?status=pending"`(대기 없음이어도 링크 유지 — 기존 「검토 대기」 카드 규약), 노트는
   카드 컨테이너 **안** 자식(BIR). 신규 CSS(`static/css/staff/pages/dashboard.css`, `.dash-metric-note` 뒤):
   `.dash-metrics--3 { grid-template-columns: repeat(3, 1fr); border: none; border-radius: 0; }` — 6줄 [계산], gap 선
   `background: var(--c-line)`은 상속 유지, transition·animation 없음. 카드 전용 focus CSS 추가 금지(전역 `base.css:82-88` 상속).
   증감 표시 없음. 상단 `{% comment %}`에 "SLA 패널은 증감을 표시하지 않는다(★2)" 1줄.
4. **문서**: `docs/BE/draft-review-lifecycle.md`에 (i) 절 — 반려율·평균 처리 정의(현재 상태 + 결정 시각, 7일 창, 재오픈
   → 재승인은 승인만), `docs/backlog.md` H4 완료·"설계 시 확정" 반려율 기준 확정 표기, pr-log(머지 시).

## 배제 (범위 밖)
- 반려 사유 분포(H10 뒤), 직전 창 증감, 감사 로그 기반 집계, 드릴다운 표·기간 선택 UI, 알림(H8), 캐시·스냅샷 저장,
  대시보드 기존 카드 5장 [코드] 변경.

## 수용 기준
- AC1 검토 대기 없음 → `longest_wait` None → 카드 `-`·노트 "검토 대기 없음"; 대기 있음 → 가장 오래된 기산점 기준 시간/일,
  재오픈된 대기 드래프트는 `reopened_at` 기준(재오픈 전 `created_at`이 더 오래돼도 무시).
- AC2 창 안 결정 없음 → `avg_handling`·`rejection_rate` None → `-`·노트 "최근 7일 결정 없음"; 창 밖(7일 이전) 결정과
  결정 시각이 None인 레거시 건은 제외.
- AC3 반려율 = 창 안 rejected / decided(현재 상태 기준). 반려 → 재오픈 → 승인된 드래프트는 승인으로만 집계(★1 핀).
- AC4 평균 처리 = 창 안 결정의 `결정 시각 − 기산점` 평균. 재오픈 후 결정된 드래프트는 `reopened_at`부터 잰다.
- AC5 대시보드 컨텍스트 `review_sla_cards`(3장 [계산], label/value(str|None)/unit/note/href) + 렌더: 라벨 3개 [계산] 노출,
  값·단위 분리 마크업(S5 범위 단언), 데이터 없음이면 `-`와 단위 span 미렌더·노트가 같은 카드 컨테이너 안, 값 있으면 노트에
  건수(예: "대기 1건"), 최장 대기 링크 `?status=pending`(라벨과 같은 `<a>` 안).
- AC6 `uv run pytest -q` 회귀, `manage.py check`, `makemigrations --check`(변경 없음 — 모델 무변경).
- AC7 브라우저: 1440px·1024px에서 값 없음 상태와 값 있는 상태(로컬은 결정 시각 있는 결정 건이 없어 임시 드래프트로 준비)
  캡처, 1024px에서 `.dash-layout` 1단 전환 뒤 3칸 정렬 유지, Tab 포커스 링이 패널 `overflow: hidden`에 잘리지 않음(BIR),
  최장 대기 카드 접근 가능 이름에 라벨·값·노트 포함, 콘솔 오류 없음. 임시 데이터·캡처는 검증 후 삭제.

## Activated Roles / Not Activated (확정 — 5역할 사전 검토 완료 2026-09-08)
- Activated: PSO(★1~★5), DAR(집계 위치 `drafts/queries.py`·뷰 헬퍼 경계·ORM 표현), Backend TDD Coach(Test List),
  WED·BIR(패널 사양·데이터 없음 표시·사후 판정, depth Standard), BIE·FIE, QVL.
- Not Activated: SRR(신규 엔드포인트·입력·개인정보 없음, is_staff 대시보드 기존 경계 안의 집계 숫자), DOR(마이그레이션·
  설정 없음), AI Automation Architect(무관).

## Domain Boundary and Dependency Direction
- drafts 소유: 집계 함수(EventDraft 필드만 읽음, `select_related` 없음, 쿼리 2회 [계산]: 대기 aggregate 1 + 결정 aggregate 1).
  staff 소유: 뷰 호출·표시 변환·템플릿. 방향 staff → drafts. events·StaffActionLog 무관. 키워드 전용 인자는 모듈 내부 관례
  (`drafts.queries`는 `tests/core/test_service_signature_conventions.py` `SERVICE_MODULES` 미포함 [실측 grep]).

## Test List (TDD 코치 확정 + DAR Q8) [문서 코치 산출]
새 파일 없음. 조회 테스트는 `now`를 고정 datetime으로 주입, `created_at`은 `make_draft` 뒤 `EventDraft.objects.filter(pk=).update(created_at=...)`
(auto_now_add), `approved_at`·`rejected_at`·`reopened_at`·`rejection_reason`은 create kwargs로 직접 지정.
- 조회(`tests/drafts/test_drafts_queries.py` `TestDraftReviewSla`, 로컬 임포트):
  Q1 `test_드래프트가_전혀_없으면_최장_대기와_평균_처리와_반려율이_모두_None이고_카운트는_0이다` — Red: ImportError.
  Q2 `test_검토_대기_중인_드래프트가_여러_건이면_최장_대기는_가장_오래된_생성_시각_기준이다` — `now − 더 오래된 created_at`.
  Q3 `test_재오픈된_대기_드래프트의_최장_대기는_재오픈_시각_기준이다` — `created_at` 아주 과거, `reopened_at` 최근 → `now − reopened_at`.
  Q4 `test_평균_처리와_반려율은_창_안에서_결정된_드래프트만_반영하고_창_밖_결정은_제외한다` — 창 안 1·창 밖 1 → decided 1.
  Q5 `test_반려율은_창_안_결정_중_반려_비율로_계산된다` — 반려 1·승인 3 → 0.25, rejected 1, decided 4.
  Q6 `test_반려_후_재오픈되어_승인된_드래프트는_승인으로만_집계된다`(★1 핀) — approved + 과거 `rejected_at`·사유 → rejected 0.
  Q7 `test_재오픈_후_결정된_드래프트의_처리_시간은_재오픈_시각부터_계산한다` — `avg_handling == 결정 시각 − reopened_at`.
  Q8 `test_결정_시각이_없는_레거시_승인_반려_건은_창_집계에서_제외된다`(DAR R1) — approved·`approved_at=None`, rejected·
  `rejected_at=None` → decided 0·rejected 0, `avg_handling`·`rejection_rate` None.
  Q6·Q7·Q8은 Q1~Q5 구현 뒤 추가 코드 없이 Green일 수 있음(공통 Coalesce·Case·NULL 필터의 정상 부수효과) — 그 경우 오케스트레이터가
  "어느 구현이 이미 만족시키는지"를 기록하고 뮤테이션(예: Q6 = 반려 판정을 `rejection_reason != ""`로 바꿈, Q7 = 처리 시간
  기산점을 `created_at`으로 바꿈, Q8 = 창 필터에서 NULL을 `now`로 Coalesce)으로 Red를 확인한다.
- 뷰(`tests/staff/test_staff_console.py`):
  V1 `test_대시보드_컨텍스트에_검수_SLA_카드_3장이_문자열_값으로_담긴다` — 길이 3 [계산], 키 5개 [계산], 값 있는 카드의 `value`가
  숫자 문자열. Red: KeyError.
  V2 `test_검수_SLA_데이터가_없으면_카드는_하이픈과_안내_문구를_보여준다` — 드래프트 0건: S5 범위 정규식(`<p class="dash-metric-label">최장
  대기</p>` ~ `</a>`)로 값 `-`·노트 "검토 대기 없음"·`dash-metric-unit` 부재; 평균 처리·반려율 카드(`</article>`)는 "최근 7일 결정 없음".
  V3 `test_검수_SLA_데이터가_있으면_카드는_값과_단위와_건수를_함께_보여준다` — pending 1건 `created_at`을 3일 전으로 `update()`
  → 최장 대기 카드 값 `3`·단위 `일`·노트 "대기 1건"; 같은 응답에서 평균 처리 카드는 `-`(혼재 상태, PSO 보강).
  V4 `test_최장_대기_카드는_대기중_드래프트_목록으로_연결된다` — 정규식 `<a class="dash-metric dash-metric-link" href="/staff/drafts/?status=pending">\s*<p class="dash-metric-label">최장 대기</p>`
  (기존 「검토 대기」 카드가 같은 href라 라벨 결합 필수, 코치).
  단위 변환 단위 테스트(V5, 헬퍼 직접 호출): 47.6시간 → "48"·"시간", 48시간 → "2"·"일", 반려율 0.0 → "0"·"%"(정수 0이 문자열로 남는 BIR 핀).

## 구현 순서 (슬라이스별 커밋, pytest 실행·판정은 오케스트레이터 단독)
운영 방식은 트랙 21과 같다(테스트 먼저 → Red 기록 → 최소 구현 → Green → 조기 Green은 뮤테이션 → 커밋).
1. 조회(Q1~Q8) → 커밋 `feat(drafts): 검수 SLA 집계 조회 draft_review_sla`
2. 뷰 헬퍼(V1·V5) → 템플릿 패널 + CSS 변형(V2~V4) + 브라우저(AC7) → 커밋 `feat(staff): 대시보드 검수 SLA 패널`
3. 문서 → 커밋 `docs: 검수 SLA 지표 정의와 H4 종결`

## 검증 명령과 기대 증거
- `uv run pytest -q tests/drafts/test_drafts_queries.py tests/staff/test_staff_console.py`, `uv run pytest -q` 전체(기준선
  2461), `uv run python manage.py check`, `makemigrations --check --dry-run`(변경 없음). 브라우저 AC7.

## Frontend Review Evidence [문서 WED·BIR 사전 산출 2026-09-08]
- 검토 깊이: **Standard**(WED·BIR 동의, Light 기각 — 링크+노트 결합 신규 마크업·CSS 변형·반응형 2분기·포커스 링 클리핑 검증).
- WED 사전 사양: 승인 범위 3에 통합(위치·헤드 메타·카드 마크업·하이픈·단위 48시간 규칙·CSS 6줄 [계산]·링크 상시 유지).
  구현 수용 기준 7항: 왼쪽 열 첫 자식 / 제목·메타 / `dash-metrics dash-metrics--3` 자식 3개 [계산] / 최장 대기만 `<a>` /
  값 없음 `-`·단위 미렌더·노트 문구 / 48시간 단위 전환·% / 1024·1440px 3칸 한 행.
- BIR 사전 기준: (1) 카드 전용 focus CSS 금지, 전역 상속 (2) 값 없음 노트는 같은 컨테이너 안 자식 (3) `value`는 문자열만
  (4) 새 `<section class="dash-panel">`은 다른 패널과 같은 깊이, `<h2 class="dash-panel-head-title">` (5) transition·animation 금지.
- 계획된 브라우저 증거(BIR 목록): 1440px·1024px 캡처 각각 값 없음/값 있음(임시 결정 드래프트 준비), 1024px `.dash-layout` 1단
  확인, 스킵 링크 → Tab으로 최장 대기 카드 포커스 캡처(링 4변 클리핑 여부), 최장 대기 카드 접근 가능 이름(라벨·값·단위·노트
  포함)·노트가 `<a>` 자식인지 DOM 확인, 콘솔 오류 없음.
- **수집된 브라우저 증거** [실측 2026-09-08, Chrome DevTools MCP, 로컬 runserver, 임시 스태프 계정 → 검증 후 삭제]:
  (1) 1440px 혼재 상태(대기 있음·창 안 결정 없음 — 로컬 자연 상태): 패널이 `.dash-col` 첫 자식, 제목 "검수 SLA"·메타
  "최근 7일 결정 기준"(`--end`), 카드 태그 [A, ARTICLE, ARTICLE], 첫 카드 href `/staff/drafts/?status=pending`, 노트가 `<a>`
  안 자식, grid 열 262px×3 [실측] 한 행, border 0·radius 0, 텍스트 "최장 대기 39 일 대기 22건" / "평균 처리 - 최근 7일 결정
  없음" / "반려율 - 최근 7일 결정 없음". 캡처 `track22-01`. (2) 임시 결정 드래프트 3건 [계산] 추가 후 1440px: "평균 처리 2 일
  결정 3건 기준" / "반려율 33 % 반려 1건 / 결정 3건". 캡처 `track22-02`. (3) 1024px: 게이트 통과, `.dash-layout` 1단 767px,
  카드 254px×3 한 행, 노트 한 줄, 가로 스크롤 없음. 캡처 `track22-03`. (4) **포커스 링 클리핑 실측(BIR Medium 확인)**: 전역
  링(2px + offset 2px)이 SLA 카드 왼쪽·아래 2변, 기존 「검토 대기」 카드 3변에서 `overflow: hidden`에 잘림 → 같은 유형 기존
  결함이라 `.dash-metrics .dash-metric-link:focus { outline-offset: -2px }` 공통 규칙으로 수정(사용자 표준 결정 2026-08-25),
  수정 후 두 카드 모두 링이 카드 박스 안. 캡처 `track22-04`. (5) 콘솔 오류·경고 0건(로드 3회). 미캡처: 대기 0건 상태(로컬
  mock 대기 22건 [실측]) — V2 테스트가 렌더 문자열로 검증.
- **뮤테이션 기록**: Q6(반려 판정을 사유 유무로) → Q5·Q6 Red, Q7(기산점 created_at) → Q7 Red, Q8 1차(`Case(default=...)`)는
  When이 매치돼 효과 없음 → 8 passed(잘못된 뮤테이션, 증거 아님) → 2차(`Coalesce(Case, now−1초)`) → Q8만 Red. 정정 기록:
  브리프의 "S7 뒤 새 절 S8"은 S8·S9가 이미 있어 S10으로 기록(BIE 보고), `staff/views/__init__.py` 274 → 276줄 [실측 wc].
- **WED 사후 판정: Conforms** [문서 WED 산출 2026-09-08] — 수용 기준 7항 전부 코드(`dashboard.html:92-109`, `__init__.py:159-204`,
  `dashboard.css:86-96`)·캡처 4장 일치. 포커스 링 인셋 규칙은 사양 밖 추가지만 실측 근거의 기능적 접근성 결함 수정(AGENTS.md
  "포커스 도달 불가 등 기능 결함은 결함")이라 판정을 깎지 않음. polish 없음.
- **BIR 사후 판정: Conforms** [문서 BIR 산출 2026-09-08] — 기준 (1)~(5) 충족. (1)의 추가 규칙은 카드 전용이 아닌 `.dash-metrics`
  하위 링크 카드 공통, 색·굵기 재정의 없음, 저장소 선례 `static/css/pages/event_calendar.css:169-174`(그리드 `overflow: hidden`에
  같은 `outline-offset: -2px` 해법)와 동일 → 근거 있는 예외로 수용. `.dash-metric-link`는 대시보드 밖 사용처 없음 [실측 rg 파일
  5개]. 잔여: 상단 「검토 대기」 카드 포커스 캡처 미제공(선택자 구조상 동일 적용 — 오케스트레이터 실측: 수정 후 두 카드 모두
  `outline-offset -2px` 계산값 확인), 콘솔은 오케스트레이터 보고값. **정정 기각**: BIR가 전역 포커스 규칙 위치를
  `static/css/base.css:91-99`로 "정정"했으나 스태프 셸은 `static/css/staff/base.css`만 로드(`templates/staff/base_staff.html:39`,
  S6)하고 그 파일의 규칙은 `:82-89` [실측 sed] — 브리프의 `base.css:82-88`은 staff 쪽을 가리킨 것이라 유효(파일 경로 표기만 불충분).
- **QVL 1차 판정: Unverified**(2026-09-08) — AC1~AC6 Passed, AC7 기술 증거 대부분 Passed이나, QVL이 계획서를 읽은 시점에 위
  WED·BIR 사후 판정문이 아직 기록되지 않아(오케스트레이터가 QVL 실행 중 기록 — 경합, 트랙 19 교훈 재발) 게이트 미충족. QVL 요청
  보강 [실측 2026-09-08]: (a) 접근 가능 이름 — 최장 대기 카드 `<a>`의 textContent "최장 대기 39 일 대기 22건"(aria 속성 없음,
  라벨·값·단위·노트 포함) 실측 완료 (b) 반올림 tie — `round(47.5)`=48, `round(48.5)`=48(짝수 반올림), `0.335*100`=33.50000000000001
  → `round`=34 [실측 python3]: 정확한 .5 tie는 짝수로 가며 실사용 값이 tie에 정확히 걸릴 확률은 낮아 정보로만 기록 (c) 정리 —
  임시 스태프 계정·임시 결정 드래프트 3건 [계산] 삭제 완료 [실측 shell], 캡처 4장 [실측 ls]은 QVL 재판정 뒤 삭제 (d) "대기
  없음 + 결정 있음" 조합은 쿼리 레벨(Q4·Q5)만 커버, 뷰 렌더 조합 테스트 없음(잔여, Low) (e) PR base는 `feat/draft-reopen`로
  열고 #345 머지 후 main 재지정(계획 :36 그대로).
- **QVL 재판정: 완료**(2026-09-08) — 게이트 충족(WED·BIR Conforms 기록 + 코드 스팟체크 3건 일치: `event_calendar.css:171-174`
  선례, `staff/base.css:82-89` 전역 규칙, `dash-metric-link` 사용처 5파일 [실측 rg]). 잔여 Low: 뷰 레벨 "대기 없음 + 결정 있음"
  조합 미테스트, 반올림 값은 오케스트레이터 실측 인용, PR base main 재지정은 #345 머지 후. 캡처 4장은 재판정 뒤 삭제 [실측].

## 이연
- 사유 분포(H10), 증감 비교, 기간 선택, 드릴다운, `decided_at` Case 필터 부분 인덱스(건수 수만 규모 시).

## 문서 대상·핸드오프 조건
- `docs/BE/draft-review-lifecycle.md` (i), `docs/backlog.md` H4 항목 완료 + "설계 시 확정" 반려율 기준 확정, pr-log(머지 시).

---

