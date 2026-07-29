# Deploy Runbook

takulife 프로덕션 배포 절차. `.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md`(이하
"0단계 계획서") §3~§8 결정과 PR-0a~0e를 코드로 확인하며 작성. 운영 중 장애
대응·잠금 해제 등 일상 운영 절차는 중복 기술하지 않고
`docs/operations-runbook.md`를 참조한다.

호스팅은 PaaS로 확정됐지만(0단계 계획서 §4) 세부 플랫폼(Fly/Railway/Render 등,
T2)은 이 문서 작성 시점에 미확정이다. 아래 절차는 Docker 이미지 + env 계약
기준으로 호스팅 중립적으로 작성했고, 플랫폼별 조작(release-phase 명령 등록
방법 등)은 실제 선정 후 이 문서에 이어서 채운다.

## 1. 사전 조건

- **T1 도메인**: `takulife.kr`/`.com` 등록 완료 (사용자 액션, 이 트랙 선행 조건)
- **T2 PaaS 계정**: 관리형 컨테이너 + 관리형 Postgres 프로비저닝 완료
- **R2(또는 B2) 버킷**: object storage 생성, 액세스 키 발급
- **필수 env 전체 표** (전부 `.env.example` 및 `config/settings.py` 배선 확인,
  변수명은 정확히 일치해야 함)

| 변수 | 필수 여부 | 배선 근거 | 비고 |
|---|---|---|---|
| `SECRET_KEY` | 필수 | config/settings.py:26-40 (`load_secret_key`) | `DEBUG=false`에서 미설정이면 기동 자체가 하드 페일 |
| `DEBUG` | 필수(`false`로 명시) | config/settings.py:57-60 | 미설정 시 기본값 `true` — 프로덕션에서 반드시 명시적으로 `false` |
| `ALLOWED_HOSTS` | 필수 | config/settings.py:78-99 (`load_allowed_hosts`, `guard_debug_allowed_hosts`) | 쉼표 구분 호스트명. `*` 금지(Host 헤더 검사 무력화) |
| `CSRF_TRUSTED_ORIGINS` | 필수 | config/settings.py:105-108 | `https://` 스킴 포함 필수, 맨 호스트명은 매치되지 않음 |
| `SECURE_SSL` | 필수(`true`) — ③④와 함께 | config/settings.py:114, 476-483 | X-Forwarded-Proto 신뢰 전제(§2·아래 체크리스트 ③) |
| `SECURE_COOKIES` | 필수(`true`) — `SECURE_SSL`과 동시 | config/settings.py:470-475 | `SECURE_SSL`과 독립 변수지만 프로덕션에선 항상 동시 설정 |
| `DATABASE_URL` | 필수 | config/settings.py:49-66 | `postgresql://` 스킴만 허용(비-Postgres 스킴 거부), 관리형 PG는 `?sslmode=require` 권장 |
| `MEDIA_STORAGE_BUCKET` | 필수(PaaS 배포 시) | config/settings.py:173-211 | 5종 all-or-nothing(아래) — PaaS 파일시스템은 휘발성이라 미설정 시 미디어 유실 |
| `MEDIA_STORAGE_ACCESS_KEY_ID` | 필수(위와 세트) | 〃 | |
| `MEDIA_STORAGE_SECRET_ACCESS_KEY` | 필수(위와 세트) | 〃 | |
| `MEDIA_STORAGE_ENDPOINT_URL` | 필수(위와 세트) | 〃 | R2: `https://<account-id>.r2.cloudflarestorage.com` |
| `MEDIA_STORAGE_REGION` | 선택 | 〃 | 미설정 시 기본값 `auto`(R2 관례) |
| `TRUSTED_PROXY_COUNT` | 필수(PaaS 배포 시) | config/settings.py:127-138, 466-467 | 실제 프록시 홉 수. 상세 위험은 `docs/operations-runbook.md` §4 참조 |
| `RUN_DB_MIGRATIONS` | 조건부 | docker/entrypoint.sh:4-9, `.env.example` | 단일 인스턴스=`true`(기본값). 2+ 레플리카/롤링 배포=`false` |
| `EMAIL_HOST` 등 5종 | **보류(0단계 계획서 §3·§6)** | config/settings.py:488-500 | 미설정 유지 → 콘솔 백엔드로 우선 배포. 신규 가입 이메일 인증·비밀번호 재설정이 실제로 동작하지 않음(가입 mandatory 이메일 인증 특성상). SMTP 재결정 전까지 실사용자 유입 금지 |
| `SUPPORT_EMAIL` | 필수(T5, launch 전) | config/settings.py:505 | `*.example` placeholder를 실주소로 교체 |
| `DEFAULT_FROM_EMAIL` | 필수(T5, launch 전) | config/settings.py:500 | 〃 |
| `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` | 선택 | `.env.example` | 빈 값이면 "Google로 계속하기" 버튼이 숨김 처리(비활성 아님) |
| `ANTHROPIC_API_KEY` | 사용 안 함 | `.env.example` | LLM 초안 자동화는 비용 정책상 OFF 유지(`DRAFT_LLM_EXTRACTION_ENABLED = False`, config/settings.py:245). 설정하지 않는다 |

## 2. 첫 배포 절차

1. **Docker 이미지 빌드**: `Dockerfile`(멀티스테이지, uv 기반 builder → 슬림
   runtime)로 빌드. 호스팅 중립적이라 플랫폼별 조작 없이 그대로 사용 가능.
2. **PaaS에 배포**: 위 필수 env 전체를 플랫폼의 시크릿/env 관리 기능에 등록 후
   컨테이너 배포.
3. **migrate 전략** (`docker/entrypoint.sh`):
   - **단일 인스턴스**: `RUN_DB_MIGRATIONS`를 설정하지 않거나 `true`로 두면
     entrypoint가 컨테이너 기동마다 `manage.py migrate --noinput`을 자동 실행.
   - **레플리카 2개 이상 또는 롤링 배포**: 앱 인스턴스에는
     `RUN_DB_MIGRATIONS=false`를 설정해 동시 DDL 충돌을 피하고, 대신 PaaS의
     release-phase(배포 전 1회 실행되는 훅, 플랫폼별 명칭 상이)에서
     `uv run python manage.py migrate` 를 한 번만 실행한다.
4. **collectstatic**: entrypoint가 migrate 직후 `manage.py collectstatic --noinput`을
   자동 실행(docker/entrypoint.sh:11) — 별도 수동 절차 불필요.
5. **헬스체크 연결**: `/api/health/`(`core/urls.py:10`, `core/views.py:728-735`)는
   무인증 200을 반환하되 **`connection.ensure_connection()`으로 DB 접속을
   확인**하고, 실패 시 503을 반환한다. PaaS의 **liveness**(실패 시 컨테이너
   재시작) 프로브로 이 엔드포인트를 그대로 쓰면, DB 자체 장애 시 앱은 멀쩡한데도
   재시작 루프에 빠질 수 있다 — 아래 체크리스트 ⑥ 참조. readiness(트래픽 라우팅
   여부만 결정) 프로브로 쓰는 것이 더 안전하다.

## 3. 필수 pre-launch 체크리스트 (0단계 계획서 T7 행, PR-0a/0b/0d/0e 게이트 승계)

첫 트래픽을 받기 **전** 반드시 아래 10개 항목을 순서대로 확인한다. 하나라도
미확인 상태로 첫 배포를 진행하지 않는다.

1. **DEBUG 독립 확인**: `DEBUG=false`가 다른 env 설정과 무관하게 실제로
   반영됐는지 직접 확인한다(예: 존재하지 않는 URL 접근 시 디버그 트레이스백이
   아니라 커스텀 404가 뜨는지). 다른 env가 맞다고 DEBUG도 맞다고 가정하지 않는다.
2. **`check --deploy` 하드 게이트**: 첫 트래픽 전에
   `uv run python manage.py check --deploy`를 프로덕션 동등 env로 실행해
   경고 0(CI의 허용 예외는 W021 HSTS preload 하나뿐 — `.github/workflows/ci.yml`
   참조)을 확인한다. CI에서 이미 매 PR 게이트로 돌지만, 실제 프로덕션 env 값으로
   재확인한다.
3. **X-Forwarded-Proto strip 확인 후 SECURE_SSL**: 선정 PaaS 라우터가 인바운드
   요청의 클라이언트발 `X-Forwarded-Proto`를 제거/덮어쓰는지 확인한 **후에만**
   `SECURE_SSL=true`를 켠다. 확인 없이 켜면 라우터가 헤더를 그대로 통과시킬 때
   클라이언트가 헤더를 위조해 HTTPS 검사를 우회할 수 있다(`.env.example`의
   `SECURE_SSL` 주석 경고).
4. **SECURE_SSL과 SECURE_COOKIES 동시 설정**: 두 변수는 서로 독립이지만
   프로덕션 HTTPS 배포에서는 항상 함께 켠다(하나만 켜면 세션/CSRF 쿠키가 평문
   HTTP로 새거나, HTTPS 강제 리다이렉트 없이 쿠키만 secure라 로그인이 깨질 수
   있음).
5. **멀티레플리카 migrate**: 레플리카 2개 이상 또는 롤링 배포라면 §2-3의
   `RUN_DB_MIGRATIONS=false` + release-phase 전략을 실제로 적용했는지 재확인한다.
6. **헬스 프로브 의미 인지**: `/api/health/`를 liveness로 쓰는 경우, DB 장애가
   재시작 루프로 이어질 수 있음을 인지하고 재시작 임계치·백오프를 보수적으로
   설정한다(§2-5).
7. **R2 실왕복 확인**: object storage로 실제 파일을 업로드하고 다시 다운로드해
   왕복 동작을 확인한다(0단계 계획서 §9-b/미검증 항목, PR-0b에서 로컬 스모크만
   수행됨 — 실제 R2 엔드포인트 왕복은 첫 배포에서 최초 검증).
8. **TRUSTED_PROXY_COUNT 홉 실측**: 선정 PaaS의 실제 프록시 홉 수를 확인한 후
   `TRUSTED_PROXY_COUNT`를 설정하고, 스테이징에서 위조 `X-Forwarded-For`가
   무영향임을 검증한다. **과대설정은 과소설정보다 위험하다** — 과대설정(또는
   passthrough 프록시를 신뢰 홉으로 오산정)은 스푸핑 우회로 이어지는 반면,
   과소설정은 `REMOTE_ADDR` 폴백으로 안전이 저하될 뿐 새 취약점을 열지 않는다.
   상세 절차·nginx 예시·curl 검증 방법은 `docs/operations-runbook.md` §4 참조.
9. **멀티워커 rate limit 실측**: gunicorn 멀티워커(`WEB_CONCURRENCY`,
   기본 3 — docker/entrypoint.sh:14) 환경에서 `ACCOUNT_RATE_LIMITS`
   (`docs/operations-runbook.md` §2)가 워커 간 실제로 공유되는지 확인한다.
   `CACHES`가 `DatabaseCache`(config/settings.py:336-344)로 배선돼 구조적으로는
   공유되지만, 통합 환경에서의 실측은 아직 없다(0단계 계획서 §9-b).
10. **DB 백업에 django_cache 포함 인지**: `DatabaseCache`는 `django_cache`
    테이블(config/settings.py:344, core 마이그레이션으로 생성)에 rate limit
    카운터를 저장한다. DB 백업/복구 시 이 테이블도 함께 복원되므로, 복구
    직후 rate limit·락아웃 카운터가 백업 시점 상태로 되돌아간다는 점을
    인지한다(예: 복구 직전 잠긴 IP가 복구 후에도 잠긴 채로 복원될 수 있음).

## 4. 백업·복구 (T6)

- **DB**: 관리형 Postgres 스냅샷(플랫폼 자동 기능) + **주기적 `pg_dump`
  오프사이트 반출**(스냅샷은 같은 플랫폼 장애 시 함께 소실될 수 있어 병행,
  0단계 계획서 §4).
- **미디어(R2)**: 버킷 버저닝을 켜거나, `rclone`으로 별도 오프사이트 저장소에
  주기 복제.
- **복구 리허설 절차** (launch 게이트 2 "미디어 영속 저장과 백업 복구 절차
  확인"의 필수 구성 요소, 0단계 계획서 §1):
  1. 백업 스냅샷/`pg_dump`와 R2 백업으로부터 **빈 스테이징 환경**을 복원.
  2. 복원된 환경에서 가입(또는 기존 계정 로그인) 스모크.
  3. 이미지 업로드 스모크 — 업로드한 파일이 R2에 실제로 남는지 확인.
  4. 기존 데이터(이벤트·아카이브 항목) 조회 스모크 — 복원 데이터가 읽히는지
     확인.
  5. 실패 지점이 있으면 백업 절차를 수정하고 리허설을 반복한다.
- **게이트 상태**: 이 리허설을 **최소 1회 완료하기 전까지는** 0단계 완료
  정의의 게이트 2(계획서 §1)를 충족한 것으로 보지 않는다. 리허설 완료 여부와
  일시를 이 절 하단에 기록한다.

| 리허설 회차 | 일시 | 결과 | 비고 |
|---|---|---|---|
| — | 미실시 | — | 첫 배포 이후 기록 예정 |

## 5. 롤백

- **이전 이미지 재배포**: PaaS의 이전 배포 버전으로 즉시 되돌린다(이미지가
  호스팅 중립이라 플랫폼 기본 롤백 기능을 그대로 사용 가능).
- **마이그레이션 역방향 판단 기준**: 롤백 대상 배포가 새 마이그레이션을
  포함했다면, 그 마이그레이션이 되돌릴 수 있는 스키마 변경(컬럼 추가 등)인지
  확인 후 `manage.py migrate <app> <이전 마이그레이션 이름>`으로 역방향
  마이그레이션을 실행할지 판단한다. 데이터 손실 가능성이 있는 역방향
  마이그레이션(컬럼 삭제 등)은 실행 전 반드시 백업을 재확인한다.
- **장애 시 점검 순서**: 헬스(`/api/health/` 응답 상태) → 애플리케이션 로그
  (`LOGGING`, config/settings.py 콘솔 구조화 로그) → DB(연결·쿼리 지연) →
  스토리지(R2 접근 가능 여부).

## 6. 미검증 항목 (첫 배포에서 채울 것)

| 항목 | 상태 | 채울 시점 |
|---|---|---|
| R2 실 업로드/다운로드 왕복 | 미검증(로컬 스모크만 완료) | 첫 배포 직후(§3 체크리스트 ⑦) |
| 선정 PaaS의 실제 프록시 홉 수 | 미확정(T2 플랫폼 미선정) | T2 확정 후, 첫 배포 전(§3 체크리스트 ⑧) |
| 멀티워커 환경에서 rate limit 공유 실측 | 미검증(구조 논증만 존재) | 첫 배포 직후(§3 체크리스트 ⑨) |
