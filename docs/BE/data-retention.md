# 운영 데이터 보존 정리 — 사이트 로그 4단계(트랙 37)

상태: **구현됨(2026-09-18)** — 만료·보존 기간이 지난 운영 로그성 데이터를
지우는 관리 명령 `prune_operational_data`와, 스태프 대시보드에 DB 용량을
보여주는 저장소 패널을 더했다.

## 보존 대상

| 대상 | 삭제 기준 | 구현 |
|---|---|---|
| 세션(`django.contrib.sessions.Session`) | `expire_date < now`(만료분만, `--days` 무관) | `core/retention.py:21-28` `_count_sessions`·`_delete_sessions`, 삭제는 `call_command("clearsessions")`에 위임(건수는 직접 count — clearsessions는 건수를 반환하지 않는다 `[코드]`) |
| axes `AccessLog` | `attempt_time <= now - days일`(기본 90일) | `core/retention.py:31-37`, 삭제는 `AxesProxyHandler.reset_logs(age_days=)` 재사용(모델 직접 delete 금지 — `AXES_HANDLER` 교체 대비) |
| axes `AccessFailureLog` | `AccessLog`와 같은 기준(90일) | `core/retention.py:40-46`, `AxesProxyHandler.reset_failure_logs(age_days=)`. **이 프로젝트에서는 대상에 두되 설계상 항상 0건** — `AXES_ENABLE_ACCESS_FAILURE_LOG`가 설정되지 않아 기본값 `False`이고(`axes/conf.py:93-95`), 이 값이 `False`면 실패 시도를 애초에 `AccessFailureLog`에 적재하지 않는다(`axes/handlers/database.py:267`의 `if settings.AXES_ENABLE_ACCESS_FAILURE_LOG:` 분기). 대상에서 뺀 것이 아니라 지울 행이 원천적으로 생기지 않는다는 뜻이다 |
| `core.ErrorGroup`(트랙 36) | `last_seen`이 `days`일보다 오래된 행(기본 90일), 소유 함수는 출처별 250행 상한(`core/error_groups.py:27` `SOURCE_GROUP_LIMIT`)과 별개로 시간 기준 정리를 더한다 | `core/error_groups.py:190-204` `prune_stale_error_groups(*, days, dry_run=False)`, `core/retention.py:49-54`에서 호출 |

`AccessAttempt`(axes)는 이 정리 대상이 아니다 — axes가 `AXES_COOLOFF_TIME`
(1시간) 창을 넘긴 시도를 로그인 시도 처리 경로 안에서 스스로 삭제한다
(`axes/handlers/database.py:395-430` `clean_expired_user_attempts`). 별도
관리 명령이 개입할 필요가 없다.

## 제외 대상과 이유

| 대상 | 제외 이유 |
|---|---|
| `AnalyticsEvent`(집계 원본) | 월간 지표가 이 원본 테이블을 다시 스캔해 계산한다 — 오래된 행을 지우면 과거 월 지표를 다시 낼 수 없다 |
| 반려된 드래프트 원문(`EventDraft`, `status=rejected` 등) | 재오픈 후 재검수 흐름이 원문 텍스트를 다시 읽는다 — 보존 기간으로 지우면 그 흐름이 끊긴다 |
| `StaffActionLog` | 추가 전용(append-only) 감사 로그 — 보존 정리 대상이 아니라 감사 목적 자체가 "지우지 않는다"는 전제다 |
| `SourceDiscoveryRun`/`SourceCandidate` | 이번 트랙에서는 범위를 축소해 이연한다. FK 위험 때문이 아니다 — `EventDraft.discovery_run`은 `on_delete=models.SET_NULL`(`drafts/models.py:66-72`), `SourceCandidate.run`은 `on_delete=models.CASCADE`(`drafts/models.py:169-171`)라 실행 레코드를 지워도 참조 무결성이 깨지지 않는다. 착수 트리거는 저장소 패널에서 이 두 테이블이 상위 용량을 차지하는 것이 실측될 때다 |

## 구조

- 대상마다 `(건수 조회 함수, 삭제 함수)` 쌍을 `_TARGETS` 표(`core/retention.py:58-63`)에
  올려두고 `prune_operational_data(*, days=90, dry_run=False)`가 순서대로
  돈다(`core/retention.py:66-79`). 한 대상이 예외를 던져도 `try/except`로
  격리해 나머지 대상은 계속 처리한다 — DB 트랜잭션 격리가 아니라 대상 간
  오케스트레이션 격리다(대상마다 자기 완결적인 단일 delete 문 하나).
- 관리 명령 `core/management/commands/prune_operational_data.py`는
  `prune_operational_data`를 감싸는 얇은 껍데기다. `--days`(기본 90),
  `--dry-run` 옵션을 받고, 대상별로 `{key}: count={count} deleted={deleted}`
  줄을 표준출력에 남긴다. 실패한 대상이 있으면 그 줄에
  `error={예외 클래스명}`을 덧붙이고, 실패 건수가 1 이상이면
  `CommandError`로 0이 아닌 종료 코드로 끝난다(`accounts/management/commands/purge_deleted_accounts.py`와
  같은 관례 `[코드]`).

## DB 크기 요약(대시보드 저장소 패널)

- `core/db_stats.py database_size_summary()`(`core/db_stats.py:44-62`)는
  Postgres 전용 쿼리 2회로 전체 크기(`pg_database_size(current_database())`)와
  `public` 스키마 상위 5개 테이블(`pg_total_relation_size`, `ORDER BY 2 DESC
  LIMIT 5`)을 읽는다.
- `connection.vendor != "postgresql"`이거나 쿼리가 `DatabaseError`를
  던지면 `None`을 돌려준다 — 대시보드가 500으로 죽지 않도록 보호하기
  위해서다(`core/db_stats.py:44-53`).
- 라벨은 `format_bytes`(`core/db_stats.py:26-32`)가 만든다: 1,048,576바이트
  미만은 KB, 1,073,741,824바이트 미만은 MB, 그 이상은 GB, 소수 1자리,
  단위 앞 공백 없음(예: `13.8MB`).
- **삭제 후 공간은 즉시 반환되지 않는다.** Postgres는 `DELETE`로 지운
  행의 물리적 공간을 `VACUUM`(또는 autovacuum)이 돌기 전까지 테이블에
  보류 상태로 남긴다. `prune_operational_data`를 실행해도
  `database_size_summary()`가 보여주는 크기는 그 순간 바로 줄지 않을 수
  있다(로컬 실측: 정리 후에도 크기 수치가 즉시 감소하지 않음, 아래
  Evidence).

## 스케줄 권고

- 두 명령(`purge_deleted_accounts`, `prune_operational_data`) 모두 **Render
  스케줄러**에 등록하는 것을 권고한다. Render는 스케줄된 잡을 대상 이미지의
  `ENTRYPOINT`를 우회해 지정한 명령만 실행하는 방식으로 지원한다 — 웹
  서비스와 같은 이미지·env를 공유하면서도 `docker/entrypoint.sh`가 항상
  `exec gunicorn ...`으로 끝나는 문제(운영 런북 §7.1 참고)를 피할 수 있다.
- **GitHub Actions로 대체하는 것은 권고하지 않는다.** 두 명령 모두 운영 DB에
  쓰기 권한을 가진 `DATABASE_URL`이 있어야 실행되는데, GitHub Actions에
  이 자격증명을 시크릿으로 등록하면 운영 DB 접근 권한이 배포 플랫폼
  바깥의 외부 CI 러너로 노출된다. 배포 플랫폼(Render) 안에서 도는
  스케줄러는 이미 그 플랫폼이 쥔 자격증명 범위를 벗어나지 않는다.
- 권장 주기: **일 1회**. 두 정리 함수 모두 하루 단위 지연에 민감하지 않다
  (세션·로그·오류 묶음은 이미 보존 기간을 넘긴 행만 대상이라, 더 자주
  돌린다고 새 정리 대상이 더 빨리 생기지 않는다).
- 첫 등록 후 반드시 `--dry-run`으로 수동 1회 실행해 대상별 건수 출력을
  확인한다(운영 런북 §7.2 참고).

## 이연

- 대량 삭제 배치(청크 분할): 지금은 대상별 단일 `DELETE` 문이다. 실제 락
  지연이 실측되면 배치로 바꾸되, 그 시점에 트리거(지연 수치)를 명시한다.
- `SourceDiscoveryRun`/`SourceCandidate` 보존 정리: 저장소 패널 실측에서
  상위 용량을 차지하는 것이 확인되면 착수한다.
- `AccessFailureLog` 활성화 및 그에 따른 실패 시도 장기 감사 로그: 보안
  범위의 별도 트랙이다 — 이 트랙은 정리 로직만 갖추고 활성화하지 않는다.
- 스케줄러 실제 등록: 사용자 액션(Render 스케줄러 비용 확인 포함,
  `docs/deploy-runbook.md` §6 참고).

## Evidence

로컬 실 DB 실측(`track37-evidence.md`, 2026-09-18) `[실측]`:

- `--dry-run`: 세션 266건 / `access_logs` 0건 / `access_failure_logs` 0건
  / `error_groups` 0건, 종료 코드 0.
- 실제 실행: 세션 294 → 28(활성 세션 28건은 그대로 유지), 재실행
  `--dry-run`은 세션 0건(정리 완료 확인), 실행 후 스태프 로그인 세션은
  살아 있어 대시보드가 정상 동작했다.
- `database_size_summary()`: 전체 13.8MB, 상위 테이블
  `drafts_eventdraft` 368.0KB · `events_event` 312.0KB ·
  `core_errorgroup` 304.0KB · `django_session` 280.0KB ·
  `axes_accesslog` 256.0KB.
