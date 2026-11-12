# 트랙 36: 오류 묶음 기록(백엔드·프론트) + 대시보드 시스템 오류 패널 (2026-09-18, 사이트 로그 1단계) [v1 — PSO·DAR·SRR·DOR·TDD 코치·QVL·WED·BIR 사전 검토 통합]

> **출처·승인**: 사용자 /goal(2026-09-18) "2->1->4 진행 …". 1단계 = 2026-09-17 제안 1번 "오류 묶음 테이블, 백엔드·프론트" + 대시보드 확인. 사용자 원 요구 "앱서비스 환경(프론트/백엔드)", "최대한 용량을 차지하지 않는 방법". 멈춰 묻지 말라는 지시라 역할 결정으로 확정.
> **브랜치·PR**: origin/main에서 `feat/error-groups`, PR 1개(1단계). 트랙 35 PR #376과 독립.

## 역할 충돌 정리
1. PSO "S4·S5(프론트)는 SRR 선행 조건부 2차 PR" → **같은 PR 포함**: SRR이 이미 선행 검토했고(F1~F9) 그 통제를 전부 수용 기준에 넣는다. 사용자 목표가 단계별 PR 하나다.
2. S6 러너 보고 → **제외**(PSO): 실행 단위 실패는 `SourceDiscoveryRun.error_summary`가 이미 대시보드에 노출 [코드 `templates/staff/dashboard.html:242`]. 백로그 아이디어로만.
3. 프론트 스크립트 위치: QVL "첫 defer" vs BIR "head 맨 위 인라인 부트스트랩" → **BIR안**: 인라인 금지 규정·CSP가 없고 [코드 rg 0건] head 인라인 스크립트가 이미 3개 [코드 `templates/base.html:9-25,70-75`, `templates/staff/base_staff.html:11-27`] — 초안의 "2곳"은 오기. 부트스트랩은 큐에 넣기만, 본체는 defer 목록 첫 번째.
4. csrf_exempt → **쓰지 않음**(DAR·코치): DRF `APIView` + `authentication_classes=[]`가 이미 CSRF 제외 [코드 `drafts/runner_views.py` csrf_exempt 0건].

## 승인 범위
- S1 `core.ErrorGroup`(core 소속, `AnalyticsEvent` 선례 [코드 `core/models.py:147-159`]): source(backend|frontend), fingerprint(64자 unique), error_type(≤100자), location(≤255자), message_sample(≤500자), first_seen, last_seen(index), count. 마이그레이션 core 0007 [코드 최신 0006].
- S2 `core/error_groups.py record_error(*, source, error_type, location, message)`: 진입 즉시 정제(개행·제어문자 제거 → 설정 시크릿 값(SECRET_KEY, ANTHROPIC_API_KEY, DRAFT_DISCOVERY_RUNNER_TOKEN, DB 비밀번호) 부분 일치면 message 전체 비움 → 이메일 마스킹 → URL 쿼리 제거 → 500자 절단)(SRR F2·F3). 지문 = sha256(source|error_type|location). 저장 = `filter(fingerprint).update(count=F+1, last_seen, message_sample)` → 0행이면 create → IntegrityError면 update(DAR·SRR F5). **출처별 상한** backend 250행·frontend 250행 [결정, 합 500], 새 묶음 생성 시 같은 출처가 상한이면 그 출처의 last_seen 최고령 1행 삭제 — 근사 상한(동시 생성 시 ±1~2행 허용, DAR). 전체를 세이브포인트 + `except Exception`으로 감싸 절대 예외 없음, 실패 시 `core.error_groups` 로거 WARNING 1줄(고정 접두어 `error-group record failed`, 정제된 값만)(DOR·SRR F9). HTTP를 모른다.
- S3 `core/logging.py ErrorGroupHandler`: `django.request` 로거에만 부착(root 금지), `emit()` 안 지연 임포트(부팅 시 AppRegistryNotReady 방지, DAR), exc_info 없는 레코드 무시, **원 예외가 `django.db.Error` 계열이면 DB 기록 시도 없이 건너뜀**(DB 장애 시 추가 지연 → gunicorn 기본 30초 [문서 `docs/operations-runbook.md:275`] 초과 방지, DOR·SRR F4). error_type=예외 클래스 qualname, location=`<METHOD> <resolver_match.route>`(없으면 "unresolved"). 본문·쿼리·쿠키·사용자 저장 안 함.
- S4 프론트: head 맨 위(테마 스크립트 앞) 인라인 부트스트랩(8줄 이내 [결정]) = `addEventListener("error"/"unhandledrejection")`로 `window.__takuErrorQueue`에 push만. `static/js/shared/error_report.js`(두 셸 defer 목록 첫 번째)가 큐 소비 + 이후 이벤트 처리. 규칙(BIR): 핸들러 전체 try/catch, 페이지당 5건 [결정] 카운터는 처리 시작 시 증가, 같은 지문 1회, "Script error."·확장 프로그램 URL·교차 출처 스크립트 무시, `sendBeacon(url, new Blob([json], {type:"application/json"}))`, `window.onerror =` 대입 금지, DOM·토스트 영향 0, bfcache 복귀 시 카운터 유지(같은 페이지뷰). 페이로드: message(≤300자), 스크립트 경로(같은 출처, 쿼리 제거), line, col. **착수 중 정정**: 페이지 경로(page)는 저장에 쓰이지 않아 받기만 하면 공격 표면만 넓히므로 계약에서 뺐다(필수 = message·script·line).
- S5 `POST /api/client-errors/`(core 뷰, DRF APIView, 인증 없음): 본문 4KB [결정] 초과·비JSON·비UTF-8·허용 외 키·다른 Origin/Referer → 기록 없이 204(정보 비노출). 전역 단일 버킷 스로틀 120회/시간 [결정, XFF 우회 방지 — 러너 선례 `drafts/runner_views.py:48-60`] 초과 → 204. **프론트 새 묶음 생성 별도 상한 20개/시간** [결정](SRR F1). 경로의 숫자·UUID 세그먼트는 `:id`로 치환(SRR F8). error_type = "js:" + 메시지 앞부분 대신 오류 이름(Error/TypeError…, 없으면 "js:unknown"), location = `스크립트경로:line` — 메시지는 message_sample로만.
- S7 대시보드 "시스템 오류" 패널(WED 명세): 오른쪽 레일 "품질 경고" 다음, `<section class="dash-panel">`. 요약 2줄 "24시간 N종 · 7일 N종"(last_seen이 창 안인 묶음 수 — 발생 횟수 아님), "백엔드 N · 프론트 N", 상위 5개 `<ul>`(출처 텍스트 라벨·count·last_seen·error_type·location, 자르지 않고 overflow-wrap:anywhere), 빈 상태 "최근 발생한 시스템 오류가 없습니다 ✓". 새 클래스 7개, 기존 토큰만. 조회 함수 `core/error_groups.py`에 1개(DAR), 쿼리 수 고정. 자동 이스케이프만, `|safe`·innerHTML 금지(SRR F6).
- S8 문서: `docs/BE/error-groups.md`(가드레일: 무예외·출처별 상한·정제·DB 오류 건너뜀·Origin 검사는 브라우저 경로만 막음(F7)·프론트 count는 페이지뷰 수 의미·롤백 시 테이블 유지), 운영 런북 확인 절차(패널이 비어도 DB 정상 신호 아님), backlog 행.

## 제외
S6 러너 보고, 4단계(보존 정리·DB 크기), connect_timeout 등 DB 연결 튜닝(기존 보류), IP 보조 스로틀, 폐기 요청 수 지표.

## 역할
PSO·DAR·SRR·DOR·코치·QVL·WED·BIR(사전 완료) / Backend Eng·Frontend Eng. AIA 미활성(모델 없음).

## Test List (코치 초안 + SRR·DOR·QVL 반영, 총 25건 [계산])
| ID | 경계 | 요지 |
|---|---|---|
| EG-01 | domain | source choices 밖이면 full_clean 실패 (첫 테스트) |
| EG-02 | contract | fingerprint unique 제약 |
| EG-03 | unit | 정제: 개행·제어문자 제거, 이메일 마스킹, 쿼리 제거, 500자 |
| EG-04 | unit | 정제: 설정 시크릿 값이 섞이면 message 비움 |
| EG-05 | domain | 새 지문 → 1행, count 1 |
| EG-06 | domain | 같은 지문 → count 2, last_seen·message 갱신 |
| EG-07 | domain | 저장 실패 주입 → 예외 없음·0행·WARNING 1줄(정제값, 재귀 없음) |
| EG-08 | domain | 깨진 트랜잭션 안에서 호출해도 예외 없음 |
| EG-09 | domain | create가 IntegrityError(동시 생성)면 update로 count 반영 |
| EG-10 | domain | 출처 상한: backend 250에서 새 backend → 최고령 backend만 삭제 |
| EG-11 | domain | frontend가 상한이어도 backend 행은 삭제 안 됨 |
| EG-12 | domain | 핸들러: exc_info 없는 레코드 무시 |
| EG-13 | domain | 핸들러: 예외 레코드 → error_type·location(METHOD route) |
| EG-14 | domain | 핸들러: 원 예외가 django.db.Error면 record_error 미호출 |
| EG-15 | contract | settings 배선: 실제 뷰 예외 500 → ErrorGroup 1행(기존 500 응답 불변) |
| EG-16 | web | 수집: 같은 출처 정상 페이로드 → 204, frontend 1행 |
| EG-17 | web | 수집: 다른 Origin → 204, 0행 |
| EG-18 | web | 수집: 4KB 초과·비JSON·비UTF-8·허용 외 키 → 204, 0행 |
| EG-19 | contract | 수집: 전역 스로틀 초과 → 204, 행 증가 없음 |
| EG-20 | domain | 수집: 프론트 새 묶음 시간당 20 초과 → 새 묶음 안 만듦(기존 묶음 count는 증가) |
| EG-21 | unit | 수집: 경로 숫자·UUID → :id |
| EG-22 | domain | 패널 조회: 24h·7d 묶음 수, 출처별, 상위 5 last_seen 순 |
| EG-23 | contract | 패널 조회 쿼리 수 0건·10건에서 동일 |
| EG-24 | web | 대시보드: error_type의 `<script>`가 이스케이프되어 렌더 |
| EG-25 | web | 대시보드 패널 빈 상태 문구 |
**착수 중 추가 시나리오(TDD 코치 사후 검토 H1 반영, 트랙 35 재발 방지)**: EG-26 빈 시크릿은 대조 안 함 / EG-27 error_type·location 제어문자 제거 / EG-28 저장 실패 로그도 정제값 / EG-29 내부 DB 오류가 호출자 트랜잭션을 깨지 않음(세이브포인트 핀) / EG-30 name 개행 API / EG-31 Django 업로드 상한 초과도 204 / EG-32 비스로틀 예외도 204 / EG-33 지문 구분자 모호성 없음 / EG-34 지문은 정제값 기준 / EG-35 location 255자 절단값 기준 한 묶음. 빈 script는 EG-18에 편입.
프론트 JS(S4)는 자동 테스트 없음 — 브라우저 증거(BIR 시나리오 9개: 동기 throw, rejection, head 인라인 오류, 10건 폭주→5건, 중복 1건, 교차 출처 무시, bfcache, 무영향, 패널 반영).

## 검증
- 사이클: `uv run pytest -q <파일>`. 핸들러 추가 직후 기존 500 회귀 7건/5파일 [실측 QVL rg] 우선: tests/core/test_error_pages.py, tests/staff/{test_staff_draft_actions,test_staff_home_categories_view,test_staff_account_views,test_staff_draft_api_audit}.py.
- `manage.py check`(부팅 시 핸들러 임포트), `makemigrations --check --dry-run`, `migrate --plan`(0007이 CREATE만), 전체 회귀.
- 실측: 로컬 500행 채운 뒤 `pg_total_relation_size('core_errorgroup')`(DOR, [계산] 추정치 0.5~1MB 대체). curl 150회 스로틀·비UTF-8. 브라우저 1280·1024 × 라이트·다크.

## 사후 판정 기록 (2026-09-18, 오케스트레이터가 각 역할 산출 원문에서 옮김)
- WED: **Conforms with notes** — 사전 명세 대비 이탈은 클래스 7→8(`.dash-error-location`)과 faint→dim 색 전환뿐, 수정 요구 없음.
- BIR: **Conforms with notes** — 인수 기준 8개 중 7개 충족, bfcache 1개 미실측이었음. 수정 요구 3건 → 커밋 6ac9cd98(부트스트랩 큐 50건 상한, 드레인 항목별 try/catch, URL base) + bfcache 실측(뒤로가기 persisted=true, 카운터 5 유지 [실측]).
- SRR: **조건부 통과** — F1~F9 통제 전부 코드·테스트로 확인, 신규 결함 1건(error_type·location 제어문자 미정제 → 로그 위조 경로) + 정보 1건(2.5MB 초과 400) → 커밋 bc43ea57, 뮤테이션 3종 검출 [실측].
- 브라우저 검증 발견(오케스트레이터): 무시 이벤트가 페이지당 상한 소진, 패널 faint 대비 3.09:1 [계산], 위치 줄 p 여백 → 커밋 14fa37c3.
- 전체 회귀 2982 passed / 10 deselected / 0 failed, check 0, makemigrations 변화 없음 [실측 bc43ea57].

## 이연
러너 보고(트리거: error_summary 단건 노출로 부족하다는 운영 신호), IP 보조 스로틀(신뢰 프록시 헤더 확보 시), 시크릿 스캐너 고도화, 폐기 요청 수 지표, 상한·스로틀 env화.

---

