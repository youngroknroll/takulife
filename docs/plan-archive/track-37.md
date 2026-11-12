# 트랙 37: 운영 데이터 보존 정리 + 대시보드 저장소 패널 (2026-09-18, 사이트 로그 4단계) [v1 — DAR·DOR(보안 겸)·TDD 코치(QVL 관점 겸)·WED·BIR 사전 검토 통합]

> **출처**: 사용자 /goal(2026-09-18) "2->1->4 진행 …". 4단계 = 2026-09-17 제안의 네 번째 항목 [문서] "보존 정리 명령" + 대시보드 저장소 크기. 멈춰 묻지 말라는 지시라 역할 결정으로 확정.
> **브랜치·PR**: `feat/retention-cleanup`, feat/error-groups(PR #377) 위 스택 — PR base = feat/error-groups, #377 머지 후 main으로 재지정.

## 역할 충돌·정정 정리
1. 테이블명 표시: WED "말줄임+title" vs BIR "줄바꿈" → **줄바꿈(BIR)**: title은 키보드·터치로 못 보고, 같은 CSS 파일이 운영 식별자는 자르지 않는 관례 [코드 `static/css/staff/pages/dashboard.css` .dash-cell-wrap 주석].
2. 마크업: WED "ul(.dash-warning-list 재사용)" vs BIR "dl" → **dl(BIR)**: 순수 이름·값 쌍, 저장소 관례 [코드 `templates/core/events/detail.html:44-71`], ul 두 span은 붙어 읽힌다.
3. 대량 삭제 배치: DOR "배치 권고" vs DAR "근거 없음, 트리거까지 이연" → **이연(DAR)**: 대상별 단일 DELETE 문, 락 지연이 실측되면 배치(트리거 명시).
4. 초안 정정: `AccessFailureLog`는 `AXES_ENABLE_ACCESS_FAILURE_LOG` 미설정(기본 False)이라 이 프로젝트에서 항상 비어 있다 [코드 axes/conf.py:93-95, handlers/database.py:267] — 대상에는 두되(무해) 문서에 "설계상 0건" 명시. `AccessAttempt`는 axes가 AXES_COOLOFF_TIME(1시간) 창으로 자체 삭제 [코드 handlers/database.py:395-430] → 대상 아님.
5. 초안 정정: SourceDiscoveryRun 제외 사유는 FK 위험이 아니다(EventDraft.discovery_run SET_NULL, SourceCandidate CASCADE [코드 drafts/models.py:66-72,169-171]) — **범위 축소 결정**으로 이연.

## 승인 범위
- S1 `core/retention.py prune_operational_data(*, days=90, dry_run=False) -> dict`(대상별 {count, deleted, error}) + 얇은 명령 `core/management/commands/prune_operational_data.py`(`--days`, `--dry-run`, 대상별 건수 출력, 실패 있으면 CommandError 비0 종료 — purge_deleted_accounts 관례 [코드 accounts/management/commands/purge_deleted_accounts.py:16-23]).
  - 세션: 만료분만(`Session.expire_date < now`, --days 무관) — 건수는 직접 count, 삭제는 `call_command("clearsessions")` 위임(clearsessions는 건수를 반환하지 않음 [코드]).
  - axes: `AxesProxyHandler.reset_logs(age_days=)`·`reset_failure_logs(age_days=)` 재사용(모델 직접 delete 금지 — AXES_HANDLER 교체 대비). dry-run은 모델 count만.
  - ErrorGroup: `core/error_groups.py prune_stale_error_groups(*, days, dry_run)`(last_seen 기준, 소유 모듈에).
  - 대상별 try/except 격리(DB 트랜잭션이 아니라 오케스트레이션 격리 — 각 대상은 단일 문).
  - 제외(근거): AnalyticsEvent(월간 지표가 원본 스캔), 반려 드래프트 원문(재오픈 재검수), StaffActionLog(추가 전용 감사), SourceDiscoveryRun/Candidate(범위 축소).
- S2 `core/db_stats.py database_size_summary()`: postgresql이면 {"total_bytes", "total_label", "tables": 상위 5개 [{name, bytes, label}]}(pg_database_size(current_database()) + public 스키마 pg_total_relation_size, 쿼리 ≤2회), 그 외 엔진·쿼리 예외면 None(대시보드 500 금지 — DOR). 표기 라벨 함수: 1,048,576바이트 미만 KB, 1,073,741,824바이트 미만 MB, 그 이상 GB, 소수 1자리, 단위 앞 공백 없음 [결정, 저장소 "5MB" 관례].
- S3 대시보드 "저장소" 패널(WED 위치 + BIR 마크업): 오른쪽 레일 "최근 14일 처리량" 다음·콜아웃 앞, 헤더 메타 "전체 {total_label}", 본문 `dl`(dt 테이블명 — overflow-wrap:anywhere, dd 크기 — mono·고정 min-width), 값 없음이면 헤더 유지 + `.dash-empty` "Postgres 외 엔진에서는 저장소 크기를 측정할 수 없습니다.", 헤더 액션 없음(정적), 색은 --c-dim 이상, `.dash-table` 재사용 금지.
- S4 문서: 운영 런북 §7에 prune_operational_data 절(권장 일 1회, 첫 실행은 --dry-run, ENTRYPOINT override·uv 부재 경고, `python manage.py prune_operational_data`), 배포 런북 §6 미확정 표의 "T2 플랫폼 미선정" 낡은 문구 정정(§7이 Render 확정) + 두 정기 명령 등록을 사용자 액션으로(Render 스케줄러 비용 확인 포함), `docs/BE/data-retention.md`(보존 기간 표·제외 대상과 이유·AccessFailureLog 0건 설계·GitHub Actions 스케줄 비권고 이유 — 운영 DB 자격증명 외부 노출), 백로그 행.

## 제외
스케줄러 실제 등록(사용자 액션), 대량 삭제 배치(트리거: 단일 DELETE 락 지연 실측), SourceDiscoveryRun 정리(트리거: 저장소 패널에서 상위 용량), AnalyticsEvent 집계 테이블, 실패 시도 장기 감사 로그(AccessFailureLog 활성화 — 보안 별도 트랙).

## Test List (TDD 코치 초안 + DOR·WED 반영, 총 16건 [계산])
| ID | 경계 | 요지 |
|---|---|---|
| RT-01 | domain | 만료 세션만 삭제, 미만료 보존 (첫 테스트) |
| RT-02 | domain | AccessLog 91일 전 삭제·89일 전 보존(attempt_time은 auto_now_add라 생성 후 update로 설정 [코드 axes/models.py:16]) |
| RT-03 | domain | AccessFailureLog 같은 경계 |
| RT-04 | domain | AccessAttempt는 오래돼도 무영향 |
| RT-05 | domain | ErrorGroup last_seen 91일 전 삭제·89일 전 보존 |
| RT-06 | domain | AnalyticsEvent·StaffActionLog·EventDraft·SourceDiscoveryRun은 90일 넘어도 무영향(parametrize) |
| RT-07 | domain | --dry-run은 아무것도 지우지 않고 건수는 보고 |
| RT-08 | contract | 한 대상 실패가 다른 대상을 막지 않고 CommandError |
| RT-09 | domain | 대상별 건수 출력(숫자 존재로 검증) |
| RT-10 | contract | Postgres에서 total_bytes>0, tables ≤5·name/bytes/label (skipif vendor != postgresql) |
| RT-11 | unit | vendor가 postgresql 아니면 None, 쿼리 0회 |
| RT-12 | domain | 크기 쿼리 예외 → None(대시보드 보호) |
| RT-13 | contract | database_size_summary 단독 쿼리 ≤2회 |
| RT-14 | unit | 크기 라벨: 1023바이트·1,048,575·1,048,576·1,073,741,824 경계 |
| RT-15 | web | 대시보드 context `storage` + 패널 dl 렌더 |
| RT-16 | web | storage가 None이면 헤더 유지 + 측정 불가 문구 |
**착수 중 추가(TDD 코치 사후 검토 반영)**: RT-17 `--days` 1 미만은 거부(CommandError·함수 ValueError), 아무것도 지우지 않음 / RT-18 명령 `--dry-run`·`--days` 인자가 실제로 전달됨 / RT-19 storage는 있으나 tables 빈 목록이면 "표 크기를 가져오지 못했습니다." / RT-20 실패 대상은 stdout에 `error=` 표시. RT-07에 access_failure_logs 건수, RT-14에 0바이트 추가. RT-12는 공개 경계(connection.cursor)로 예외 주입.

## 사후 판정 기록 (2026-09-18, 오케스트레이터가 각 역할 산출 원문에서 옮김)
- WED: **Conforms with notes** — 위치·헤더 메타·Django 테이블명 그대로·값 없음 시 헤더 유지+dash-empty·새 클래스 4개·기존 토큰 [코드 templates/staff/dashboard.html 저장소 섹션, dashboard.css .dash-storage-*]. notes: WED 원안(말줄임+title, ul)은 역할 충돌 정리 1·2로 기각된 항목이라 이탈 아님. 수정 요구 없음.
- BIR: **Conforms** — dl>div>dt/dd, 이름 overflow-wrap:anywhere, .dash-table 미재사용, 크기 mono+min-width 4.5rem, 헤더 액션 없음, 값 없음 dash-empty, 포커스 가능 요소 0, 연결 JS 0 [코드]. 확인 필요(결함 아님): 헤더 메타 faint는 대시보드 전 패널 공통 기존 패턴 [실측 rg 10곳].
- TDD 코치: 결함 H1(--days 0·음수 전량 삭제)·M1(빈 tables 분기 미기록)·M2(private monkeypatch)·M3(CLI 배선 미검증)·L1·L2·L4 → 커밋 e33ad31d, 뮤테이션 4종 검출 [실측]. L3·L5 정보.
- QVL: **Complete with residual risk** — RT-01~20 전수 대응, S1~S4 일치. 잔여: 배포 런북 §6 "미확정/확정" 자기모순 문구 → "미등록"으로 정정(이 트랙), DELETE 후 공간은 VACUUM 전까지 미회수(문서화됨).
- 브라우저·실DB 실측: 레일 순서, 1280·1024 × 라이트·다크 넘침 0, 긴 이름 줄바꿈(행 53px), 콘솔 0, dry-run 세션 266 → 실제 294→28(활성 유지) [실측 track37 증거].
- 전체 회귀 3019 passed / 10 deselected / 0 skipped / 0 failed, check 0, makemigrations 변화 없음 [실측 e33ad31d].

## 검증
- 사이클 `uv run pytest -q <파일>`, 뮤테이션(PYTHONDONTWRITEBYTECODE=1), 기존 대시보드 테스트 파일 둘(test_staff_dashboard_system_errors.py·test_staff_dashboard_analytics.py [코드]) 회귀, 전체 회귀·check·makemigrations(마이그레이션 없어야 함). skip 건수 보고(RT-10·15 Postgres 전제).
- 로컬 실측: `--dry-run` 실제 DB 건수 출력, 실제 삭제 1회, 저장소 패널 브라우저 1280·1024 × 라이트·다크(BIR 사전 시나리오 목록 [문서]).

---

