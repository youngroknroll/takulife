# Deploy Runbook

takulife 프로덕션 배포 절차. 2026-07-14 0단계 배포 기반 계획서(이하
"0단계 계획서" — 원문서는 2026-08-29 문서 정리로 삭제, 저장소에 남아 있지 않다)
§3~§8 결정과 PR-0a~0e를 코드로 확인하며 작성. 운영 중 장애
대응·잠금 해제 등 일상 운영 절차는 중복 기술하지 않고
`docs/operations-runbook.md`를 참조한다.

호스팅은 PaaS로 확정됐지만(0단계 계획서 §4) 세부 플랫폼(Fly/Railway/Render 등,
T2)은 이 문서 작성 시점에 미확정이다. 아래 절차는 Docker 이미지 + env 계약
기준으로 호스팅 중립적으로 작성했고, 플랫폼별 조작(release-phase 명령 등록
방법 등)은 실제 선정 후 이 문서에 이어서 채운다(이후 Render로 확정됨 — §7).

## 1. 사전 조건

- **T1 도메인**: `takulife.kr`/`.com` 등록 완료 (사용자 액션, 이 트랙 선행 조건)
- **T2 PaaS 계정**: 관리형 컨테이너(Render) 프로비저닝 완료
- **DB(Supabase 무료 티어)**: Supabase 프로젝트 생성 완료. 리전은 Render 웹
  서비스(Singapore)와 가까운 Southeast Asia(Singapore)로 만든다. Render 무료
  Postgres는 생성 30일 뒤 만료돼 유예 14일 후 데이터째 삭제되므로(Render 공식
  문서 기준, 2026-08-26 확인) 사용하지 않는다 — 2026-08-26 결정. 접속 주소는
  반드시 **Session pooler**를 쓴다: Direct connection은 IPv6 전용이라 Render에서
  접속할 수 없고, Transaction pooler는 Django의 prepared statement와 호환되지
  않는다. 무료 티어는 7일간 DB 활동이 없으면 일시정지된다(데이터 보존) —
  재개는 Supabase 대시보드의 Restore 버튼.
- **R2(또는 B2) 버킷**: object storage 생성, 액세스 키 발급
- **필수 env 전체 표** (전부 `.env.example` 및 `config/settings.py` 배선 확인,
  변수명은 정확히 일치해야 함)

| 변수 | 필수 여부 | 배선 근거 | 비고 |
|---|---|---|---|
| `SECRET_KEY` | 필수 | config/settings.py `load_secret_key` | `DEBUG=false`에서 미설정이면 기동 자체가 하드 페일 |
| `DEBUG` | 필수(`false`로 명시) | config/settings.py `load_debug` | 미설정 시 기본값 `true` — 프로덕션에서 반드시 명시적으로 `false` |
| `ALLOWED_HOSTS` | 필수 | config/settings.py `load_allowed_hosts`, `guard_debug_allowed_hosts` | 쉼표 구분 호스트명. `*` 금지(Host 헤더 검사 무력화) |
| `CSRF_TRUSTED_ORIGINS` | 필수 | config/settings.py `load_csrf_trusted_origins` | `https://` 스킴 포함 필수, 맨 호스트명은 매치되지 않음 |
| `SECURE_SSL` | 필수(`true`) — ③④와 함께 | config/settings.py `load_secure_ssl`, `build_secure_ssl_settings` | X-Forwarded-Proto 신뢰 전제(§3 체크리스트 ③) |
| `SECURE_COOKIES` | 필수(`true`) — `SECURE_SSL`과 동시 | config/settings.py `_secure_cookies` 대입부 | `SECURE_SSL`과 독립 변수지만 프로덕션에선 항상 동시 설정 |
| `DATABASE_URL` | 필수 | config/settings.py `load_database_config` | `postgresql://` 스킴만 허용(비-Postgres 스킴 거부), 관리형 PG는 `?sslmode=require` 권장. Supabase는 Session pooler 주소 + `?sslmode=require`(§1 DB 항목) |
| `MEDIA_STORAGE_BUCKET` | 필수(PaaS 배포 시) | config/settings.py `load_media_storage_config` | 5종 all-or-nothing(아래) — PaaS 파일시스템은 휘발성이라 미설정 시 미디어 유실 |
| `MEDIA_STORAGE_ACCESS_KEY_ID` | 필수(위와 세트) | 〃 | |
| `MEDIA_STORAGE_SECRET_ACCESS_KEY` | 필수(위와 세트) | 〃 | |
| `MEDIA_STORAGE_ENDPOINT_URL` | 필수(위와 세트) | 〃 | R2: `https://<account-id>.r2.cloudflarestorage.com` |
| `MEDIA_STORAGE_REGION` | 선택 | 〃 | 미설정 시 기본값 `auto`(R2 관례) |
| `TRUSTED_PROXY_COUNT` | 필수(PaaS 배포 시) | config/settings.py `load_trusted_proxy_count`, `build_axes_client_ip_callable` | 실제 프록시 홉 수. allauth 레이트리밋 `ip` 범위도 이 값을 공유(`ALLAUTH_TRUSTED_PROXY_COUNT`) — 과대설정 시 axes는 조용히 REMOTE_ADDR로 폴백하지만 allauth는 500. 상세 위험은 `docs/operations-runbook.md` §4 참조 |
| `RUN_DB_MIGRATIONS` | 조건부 | docker/entrypoint.sh:4-9, `.env.example` | 단일 인스턴스=`true`(기본값). 2+ 레플리카/롤링 배포=`false` |
| `EMAIL_HOST` 등 5종 | **보류(0단계 계획서 §3·§6)** | config/settings.py `EMAIL_HOST` 대입부 | 미설정 유지 → 콘솔 백엔드로 우선 배포. 신규 가입 이메일 인증·비밀번호 재설정이 실제로 동작하지 않음(가입 mandatory 이메일 인증 특성상). SMTP 재결정 전까지 실사용자 유입 금지 |
| `SUPPORT_EMAIL` | 필수(T5, launch 전) | config/settings.py `SUPPORT_EMAIL` 대입부 | `*.example` placeholder를 실주소로 교체 |
| `DEFAULT_FROM_EMAIL` | 필수(T5, launch 전) | config/settings.py `DEFAULT_FROM_EMAIL` 대입부 | 〃 |
| `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` | 선택 | `.env.example` | 빈 값이면 "Google로 계속하기" 버튼이 숨김 처리(비활성 아님). 소셜 가입은 `SocialSignupForm`의 약관 동의 필드를 거친다(`config/settings.py` `SOCIALACCOUNT_FORMS`·`SOCIALACCOUNT_AUTO_SIGNUP=False`, backlog B2 해결=트랙 11) |
| `ANTHROPIC_API_KEY` | 사용 안 함 | config/settings.py `DRAFT_LLM_EXTRACTION_ENABLED` 대입부 | LLM 초안 자동화는 비용 정책상 OFF 유지. 설정하지 않는다 |
| `DRAFT_DISCOVERY_ENABLED` | 선택(기본값 유지) | config/settings.py `load_draft_discovery_enabled` 대입부 | 기본값 `false`(수집 꺼짐) 유지, 수집을 켤 때만 `true`로 설정. env 변경은 모듈 임포트 시점에 1회만 평가되므로 **프로세스 재시작 후에만 반영**된다 |
| `DRAFT_DISCOVERY_RUNNER_TOKEN` | 수집을 켤 때 필수 | config/settings.py `DRAFT_DISCOVERY_RUNNER_TOKEN = _get_env(...)` 대입부 `[실측 rg config/settings.py]` | 러너 요청 헤더 `X-Runner-Token`과 상수 시간 비교(`core/runner_auth.py` `IsDiscoveryRunner`). 미설정(빈 값)이면 러너 API 전부 403. 회전 절차는 `docs/operations-runbook.md` §8.x 참조 |
| `GOOGLE_SITE_VERIFICATION` | 선택 | config/settings.py `GOOGLE_SITE_VERIFICATION = _get_env(...)` | 서치콘솔 HTML 태그 토큰 |
| `GA_MEASUREMENT_ID` | 선택 | config/settings.py `GA_MEASUREMENT_ID = _get_env(...)` | `G-…` 형식의 GA4 측정 ID |
| `DRAFT_FETCH_CONTACT` | 선택 | config/settings.py `load_draft_fetch_contact` | 크롤러 UA 연락처(`docs/operations-runbook.md` §8 참조) |
| `PORT` | 선택 | `docker/entrypoint.sh` `--bind` | 기본값 `8000` |
| `GUNICORN_TIMEOUT` | 선택 | `docker/entrypoint.sh` `--timeout`, `.env.example` | 워커 타임아웃(초). 기본값 `120` `[코드 docker/entrypoint.sh]`. `0`은 타임아웃 해제라 금지 |
| `WEB_CONCURRENCY` | 선택 | `docker/entrypoint.sh` `--workers` | 워커 수. 기본값 `3` `[코드 docker/entrypoint.sh]` |

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
4. **collectstatic**: entrypoint가 migrate 직후 `manage.py bundle_shell_css --output
   static/css/dist/shell.css`(셸 CSS 16개 병합, 트랙 14)를 실행하고 이어서
   `manage.py collectstatic --noinput`을 자동 실행(docker/entrypoint.sh:9-11) —
   별도 수동 절차 불필요. `set -e`라 번들 실패는 기동을 그대로 중단시킨다
   (`docs/FE/css-delivery.md` C2·C3 참고).
5. **헬스체크 연결**: `/api/health/`(`core/urls.py`, `core/views.py`의 `health()`)는
   무인증 200을 반환하되 **`connection.ensure_connection()`으로 DB 접속을
   확인**하고, 실패 시 503을 반환한다. PaaS의 **liveness**(실패 시 컨테이너
   재시작) 프로브로 이 엔드포인트를 그대로 쓰면, DB 자체 장애 시 앱은 멀쩡한데도
   재시작 루프에 빠질 수 있다 — 아래 체크리스트 ⑥ 참조. readiness(트래픽 라우팅
   여부만 결정) 프로브로 쓰는 것이 더 안전하다.

## 3. 필수 pre-launch 체크리스트 (0단계 계획서 T7 행, PR-0a/0b/0d/0e 게이트 승계)

첫 트래픽을 받기 **전** 반드시 아래 19개 항목을 순서대로 확인한다. 하나라도
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
   - **⑦-2. 버킷 퍼블릭 액세스 차단 확인**: R2 대시보드에서 해당 버킷의
     "Public access"가 기본값(비활성)인지 확인하고, r2.dev 서브도메인이나
     커스텀 도메인이 서명 없이 연결돼 있지 않은지 점검한다.
     `querystring_auth`가 이미 `True`로 고정돼(config/settings.py
     `load_media_storage_config`) 애플리케이션이 생성하는 URL은 서명 만료
     전까지만 유효하지만, 이 확인은 "서명 없이도 접근 가능한 별도 경로"가
     열려 있지 않은지를 보는 것이다. 실행 가능한 검증: 실제 업로드된
     오브젝트 키로 `curl -I "https://<account-id>.r2.cloudflarestorage.com/<bucket>/<key>"`
     (서명 쿼리스트링 없이)를 호출해 200이 아니라 403/AccessDenied가
     반환되는지 확인한다. 200이 반환되면 버킷이 의도치 않게 공개 상태다.
8. **TRUSTED_PROXY_COUNT 홉 실측**: 선정 PaaS의 실제 프록시 홉 수를 확인한 후
   `TRUSTED_PROXY_COUNT`를 설정하고, 스테이징에서 위조 `X-Forwarded-For`가
   무영향임을 검증한다. **과대설정은 과소설정보다 위험하다** — 과대설정(또는
   passthrough 프록시를 신뢰 홉으로 오산정)은 스푸핑 우회로 이어지는 반면,
   과소설정은 `REMOTE_ADDR` 폴백으로 안전이 저하될 뿐 새 취약점을 열지 않는다.
   상세 절차·nginx 예시·curl 검증 방법은 `docs/operations-runbook.md` §4 참조.
   추가로 스테이징에서 allauth 4경로(signup·login_failed·reset_password·
   manage_email)가 위조 `X-Forwarded-For`로도 500이 나지 않고, IP A에서
   잘못된 로그인 10회 뒤 IP B의 첫 로그인이 429가 아님을 확인한다.
9. **멀티워커 rate limit 실측**: gunicorn 멀티워커(`WEB_CONCURRENCY`,
   기본 3 — docker/entrypoint.sh:15) 환경에서 `ACCOUNT_RATE_LIMITS`
   (`docs/operations-runbook.md` §2)가 워커 간 실제로 공유되는지 확인한다.
   `CACHES`가 `DatabaseCache`(config/settings.py `CACHES`)로 배선돼 구조적으로는
   공유되지만, 통합 환경에서의 실측은 아직 없다(0단계 계획서 §9-b).

   **로컬 실측(2026-10-28)**: 조건 = gunicorn 26.0.0 `--workers 3`, 로컬
   PostgreSQL 14.19, 스크래치 DB `taku_ratelimit_smoke`(`DatabaseCache` 그대로),
   순차 curl `[실측 2026-10-28]`.

   | 시험 | 결과 | 판정 |
   |---|---|---|
   | DRF `discovery_runner` 60/minute (`POST /api/discovery/runner/heartbeat/`) | 62회 순차(22:03:28~22:03:32 KST, 4초) → 1~60번 204, 61·62번 429. 1~60번 워커 PID별 처리 15/22/23건. 첫 429를 낸 워커는 1~60번 중 22건만 처리 `[실측 2026-10-28]` | 카운터가 워커 간 합산됨 — **공유 확인** |
   | 대조군: 저장소 밖 스크래치 설정으로 `CACHES`를 `LocMemCache`로 바꿔 같은 시험 | 62회 전부 204, PID별 12/25/25건 → 워커별 개별 카운트라 어느 워커도 60에 못 미쳐 429 없음 `[실측 2026-10-28]` | 이 시험이 공유 여부를 구별한다는 증거 |
   | allauth `signup` (`5/m/ip,30/h/ip`) | CSRF 쿠키·토큰 포함 빈 폼 POST 7회 → 1~3번 200(폼 오류), 4~7번 429. 통과 3건은 한 워커(PID 28162)가 처리했고 429 4건 중 3건은 다른 두 워커가 냈다 `[실측 2026-10-28]` | **공유 확인**. 한도 5 대비 4번째부터 제한된 이유는 미확인(allauth 소비 방식 차이로 추정, 별도 확인 항목) |

   재현 명령 요지(토큰 값 제외): 스크래치 DB 생성 → env 명시 기동
   `uv run gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 3
   --access-logformat '%(p)s %(s)s %({x-seq}i)s %(U)s'` →
   `for i in $(seq 1 62); do curl -X POST -H "X-Runner-Token: …" -H "X-Seq: $i"
   …/api/discovery/runner/heartbeat/; done` → 액세스 로그 PID 집계. 끝나면
   스크래치 DB 삭제.
   **한계**: 프로덕션(Render 컨테이너 + Supabase Session pooler) 통합 환경은
   미검증. 컬링(`MAX_ENTRIES=10000`, 운영 `django_cache` 행 수) 확인은 아래에
   그대로 남는다.
   **컬링으로 인한 카운터 조기 소멸도 별도로 확인한다**: `DatabaseCache`는
   `MAX_ENTRIES`(현재 10000 — config/settings.py `CACHES`)를 넘으면 만료 전
   항목까지 `cache_key` 알파벳 순으로 최대 1/3을 강제 삭제한다(LRU·FIFO가
   아니다 — Django `db.py` `_cull`). 실측 시 `SELECT COUNT(*) FROM
   django_cache;`로 실제 행 수가 예상 사용자 규모에서 10000에 근접하지
   않는지 함께 확인하고, 근접한다면 카운터가 TTL 만료 전에 조기 삭제돼
   레이트리밋·계정 삭제 잠금이 의도보다 일찍 풀릴 수 있음을 인지한다.
10. **DB 백업에 django_cache 포함 인지**: `DatabaseCache`는 `django_cache`
    테이블(config/settings.py `CACHES` `MAX_ENTRIES`, core 마이그레이션으로 생성)에 rate limit
    카운터를 저장한다. DB 백업/복구 시 이 테이블도 함께 복원되므로, 복구
    직후 rate limit·락아웃 카운터가 백업 시점 상태로 되돌아간다는 점을
    인지한다(예: 복구 직전 잠긴 IP가 복구 후에도 잠긴 채로 복원될 수 있음).
    `MAX_ENTRIES=10000`으로 행 수 상한이 고정돼 있어 이 테이블이 백업
    시간·용량에 미치는 영향은 무시할 수 있다.
11. **탈퇴 파기 정기 실행 등록**: <!-- uv-run-exempt: 런타임 이미지엔 uv가 없다(Dockerfile:3-4) — PaaS 스케줄러가 컨테이너 안에서 이 명령을 직접 실행한다 --> `python manage.py purge_deleted_accounts`
    (`accounts/management/commands/purge_deleted_accounts.py`)를 선정 PaaS의
    스케줄러(크론/스케줄드 잡 등, 플랫폼별 명칭 상이)에 등록하고, **수동 1회
    실행으로 파기 요약 출력을 확인한다.** 두 가지를 반드시 지킨다:
    (a) **`uv run`을 붙이지 않는다** — 런타임 이미지에는 `uv`가 없어
    (`Dockerfile:3-4`, builder 스테이지 전용) `uv run`으로 등록하면 컨테이너
    안에서 `uv: not found`로 조용히 실패한다. `docker/entrypoint.sh:5,11`도 같은
    이유로 `uv run` 없이 실행한다. (b) **스케줄러 등록 시 이미지의
    ENTRYPOINT를 반드시 우회한다** — `docker/entrypoint.sh`는 전달된 인자를
    읽지 않고 항상 `exec gunicorn ...`으로 끝나므로(`Dockerfile`의 `ENTRYPOINT`,
    `docker/entrypoint.sh`의 `exec gunicorn`), 명령 문자열만 "실행할 커맨드"로 등록하면 그 문자열이
    ENTRYPOINT 인자로 조용히 버려지고 **파기는 한 건도 안 되는데 gunicorn
    웹서버가 대신 뜬 채 계속 살아 있는다** — 종료도 안 하므로 아래 실패
    알림에도 걸리지 않는다. 선정 PaaS가 제공하는 ENTRYPOINT 우회 방식(명칭은
    플랫폼별로 다름)으로 등록했는지, 그리고 등록 직후 수동 실행한 표준출력에
    `삭제 N건 / 실패 M건`이 실제로 찍히는지 확인한다. 상세는
    `docs/operations-runbook.md` §7.1 참조.
    이 명령은 코드 작성 시점부터 정상 동작하지만, **정기 실행을 스스로
    예약하지 않는다** — 명령 docstring도 "정기 스케줄링은 배포/런북의
    책임"이라고 명시한다. `/accounts/delete/done/` 화면은 사용자에게 유예
    기간이 지나면 계정이 파기된다고 명시적으로 안내하므로(유예 기간 값의
    진실 원천은 `accounts/services.py:25`의 `DELETION_GRACE_PERIOD = timedelta(days=10)`),
    이 등록이 누락되면 그 안내가 지켜지지 않고 유예 기간이 지난 개인정보가
    무기한 잔존한다. 명령은 실패 시(개별 후보 삭제 중 에러 발생) 0이 아닌
    종료 코드로 끝나므로(`CommandError`, 실패 건수와 함께), 스케줄러에
    **실패 알림(0이 아닌 종료 코드 감지)을 반드시 연결**한다. 실행 주기 권고와
    상세 절차는 `docs/operations-runbook.md` §7 참조.
12. **robots.txt 크롤링 허용 확인**: robots 해제(SEO 트랙 16)는 **SMTP
    게이트와 분리**됐다(2026-08-29 사용자 결정) — SMTP 미설정 상태로도
    크롤링 허용이 배포된다. 코드 수정은 이미 완료됐다(`core/views.py`의
    robots 뷰가 비제품 4경로(`/admin/`, `/api/`, `/accounts/`, `/staff/`)만
    차단하고 Sitemap 위치를 안내한다). **알려진 상태**: 검색으로 유입된
    방문자는 가입 인증 메일 미동작(SMTP 보류) 동안 가입을 완료할 수
    없다 — 이는 수용된 상태이며 SMTP 활성화(별도 항목)가 해소 조건이다.
    배포 후 확인 항목: `curl https://<host>/robots.txt`로 `Disallow` 4경로와
    `Sitemap:` 라인을 확인하고, `curl https://<host>/sitemap.xml`이 200을
    반환하는지 확인한다(도메인은 요청 Host를 따르므로 별도 설정 불필요 —
    `RequestSite`). **한글 브랜드명 확인(트랙 28, 라이브 `<title>`은 `타쿠라이프 takulife — 굿즈 컬렉션·서브컬처 이벤트 기록` `[실측 curl -s https://takulife.kr/ 2026-10-27]`)**:
    홈은 SSR이라 curl로 충분 —
    `curl -s https://<host>/ | grep -o '<title>[^<]*</title>'`가 `타쿠라이프`로
    시작하고, `curl -s https://<host>/ | grep -c '"@type": "WebSite"'`가 1인지
    확인한다.
13. **API 문서 정적 자산 실서빙 확인**: `DEBUG=false` + `collectstatic` 완료
    후 `/api/docs/`를 브라우저로 열어 Swagger UI 렌더와 sidecar 정적 자산
    (`swagger-ui-bundle.js` 등) 200 응답을 확인한다. `collectstatic` 성공은
    참조 파일의 존재만 보장하고 실서빙 내용까지 보장하지 않는다.
14. **정적 자산 브로틀리 프록시 전달 확인**: 첫 배포 후
    `curl -H "Accept-Encoding: br" -I "https://<host>/static/css/<해시>.css"`로
    Render 프록시가 `br`을 전달해 `Content-Encoding: br`이 오는지 확인하고
    결과를 이 문서에 기록한다(트랙 13-C에서 brotli 사전압축으로 `.br` 파일
    488개를 생성해뒀지만, 2026-08-29 시점 Render의 `Accept-Encoding` 전달
    여부는 미검증). `br`이 오지 않고 `gzip`만 와도 장애는 아니다 — whitenoise가
    가진 것 중 최선을 고르므로 무해하게 무용할 뿐이다.
    **확인 결과 `[실측 2026-08-31]`**: `https://takulife.kr/static/css/dist/shell.763817b51953.css`에
    `Accept-Encoding: br` 요청 시 `HTTP/2 200` + `content-encoding: br` 응답 —
    Render 프록시가 br을 전달한다. 같은 날 §3-12 배포 후 확인도 완료:
    robots.txt 200(Disallow 4경로 + `Sitemap: https://takulife.kr/sitemap.xml`),
    sitemap.xml 200(공개 행사 미존재 상태라 정적 5페이지만 수록 — 정합).
15. **닉네임 배포 확인(트랙 29)**: `curl -s https://<host>/accounts/signup/ | grep -c 'name="nickname"'`
    → `1`(가입 폼에 닉네임 입력칸이 렌더되는지). `psql "$DATABASE_URL" -c
    "SELECT count(*) FROM accounts_user WHERE nickname IS NULL;"` → `0`(0006
    백필+NOT NULL 전환이 전 회원에 적용됐는지, `docs/BE/account-identity.md`
    (d) 참고).
    > 항목 16·17·19의 `uv run …`은 컨테이너 셸이 아니라 **로컬 맥 저장소에서
    > 운영 `DATABASE_URL`을 환경에 넣고** 실행한다 — 런타임 이미지에는 `uv`가
    > 없다 `[코드 Dockerfile:3-4]`.
16. **배포 전 공식 URL 스킴 확인(트랙 40, F1)**: 아래 명령으로 운영 DB에서
    http(s)가 아니거나 호스트가 없는 `official_url` 행 수를 확인한다.
    ```bash
    uv run python manage.py shell -c "from urllib.parse import urlsplit; from events.models import Event; print(sum(1 for u in Event.objects.exclude(official_url__isnull=True).exclude(official_url='').values_list('official_url', flat=True) if urlsplit(u.strip()).scheme not in ('http','https') or not urlsplit(u.strip()).netloc))"
    ```
    0이 아니면 스태프 수정 화면에서 고친 뒤 배포한다 — **배포 전 차단 항목**.
    이유 두 가지: 검증기는 생성·수정·재게시 시점에만 걸려 이미 게시된 값은
    공개 상세 링크에 그대로 렌더되고(XSS가 코드 배포만으로 닫히지 않는다),
    배포 후에는 그 값을 그대로 둔 재게시·수정 저장이 스킴·호스트 검사로 거부된다.
17. **배포 전 memo 최대 길이 확인(트랙 40, F3a)**: 아래 명령으로 기존 행의
    memo 최대 길이를 확인한다.
    ```bash
    uv run python manage.py shell -c "from django.db.models import Max; from django.db.models.functions import Length; from archive.models import PersonalEntry, CollectionItem; print(PersonalEntry.objects.aggregate(m=Max(Length('memo'))), CollectionItem.objects.aggregate(m=Max(Length('memo'))))"
    ```
    2,000자 `[코드 archive/models.py MEMO_MAX_LENGTH]`를 넘는 행은 조회·삭제는
    되지만, memo를 포함한 수정 요청은 배포 후 400이 된다.
18. **다국어(트랙 43-1) 배포 확인**:
    - `curl -s -H "Accept-Language: en" https://<host>/ | grep -o '<html lang="[^"]*"'`가
      `lang="en"`이고, 헤더 없이 호출하면 `lang="ko"`인지 확인한다.
    - `curl -sI -H "Accept-Language: en" https://<host>/ | grep -i '^vary:'`에
      `Accept-Language`가 포함되는지 확인한다.
    - `/jsi18n/`이 200이고 본문에 `django.gettext` 정의가 포함되는지
      `curl -s https://<host>/jsi18n/ | grep -c 'django.gettext ='`가 1 이상인지
      확인한다.
    - 언어 쿠키 속성: 먼저 `curl -sc /tmp/jar https://<host>/ -o /dev/null`로
      csrftoken 쿠키를 받고, `TOKEN=$(awk '/csrftoken/ {print $7}' /tmp/jar)`로
      값을 꺼낸 뒤 `curl -si -b /tmp/jar -H "X-CSRFToken: $TOKEN" -H "Referer:
      https://<host>/" -d "language=ja&next=/" https://<host>/i18n/setlang/ |
      grep -i '^set-cookie: django_language'`에 `HttpOnly`·`SameSite=Lax`
      (그리고 `SECURE_COOKIES=true` 배포라면 `Secure`)가 있는지 확인한다.
    - **번역 검수 게이트(2026-10-21 사용자 지시로 변경)**: 번역 검수는 사람이
      아니라 번역가와 별개인 AI 검수자가 한다. deploy PR을 머지하기 전에
      `docs/BE/i18n.md`의 "AI 검수 기록"이 현재 카탈로그 기준으로 쓰여 있고
      카탈로그 가드(`tests/core/test_i18n_catalog_completeness.py`)가 통과하는지
      확인한다. 원어민 사람이 읽은 적은 없다는 점은 위험으로 남아 있다.
19. **행사 콘텐츠 번역(트랙 44-1) 배포 확인**:
    - 마이그레이션 `events.0008_event_text_translations`가 적용됐는지 배포
      로그로 확인한다.
    - 0009 적용 확인: `psql "$DATABASE_URL" -c "\d events_event"`에서
      `text_translations`의 default가 `'{}'::jsonb`인지 확인한다.
    - `curl -s -o /dev/null -w '%{http_code}' -X POST
      https://<host>/api/translation/runner/pending/`가 토큰 없이 `403`인지
      확인한다.
    - 공개 API가 번역 저장소를 노출하지 않는지
      `curl -s https://<host>/api/events/ | grep -c text_translations`가
      `0`인지 확인한다.
    - 로컬 맥에서 운영 `DATABASE_URL`로 `uv run python manage.py report_translation_queue`를 실행해
      `published` 값이 게시 이벤트 수와 같은지 확인하고, 러너를 새 코드로
      재시작한 뒤 `pending`이 줄어드는지, 러너 로그에 `translation step
      failed` 경고가 반복되지 않는지 확인한다. 번역은 러너가 켜져 있는
      동안만 채워지고 꺼져 있으면 한국어 원문이 그대로 보인다(44-2부터
      화면에 영향).
    - Render 환경 변수는 새로 필요 없다 — 번역 러너 API는 기존
      `DRAFT_DISCOVERY_RUNNER_TOKEN`을 공유한다.

## 4. 백업·복구 (T6)

- **DB**: Supabase **무료 티어에는 자동 백업이 없다**(자동 일일 스냅샷은 Pro
  플랜부터 — Supabase 문서 기준, 2026-08-26 확인). 따라서 **주기적 `pg_dump`
  오프사이트 반출이 유일한 백업 수단**이며, 첫 배포 직후부터 반드시 가동한다.
  0단계 계획서 §4의 "스냅샷 + 반출 병행"은 유료 플랜 전환 후에만 성립한다.
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
| 로컬 사전 리허설 | 2026-10-28 | 통과(아래 수치) | 게이트 2 미충족 — 운영 Supabase·R2·가입·업로드 스모크 아님 |
| 운영 리허설 | 미실시 | — | 자격 증명 필요(사용자) |

**로컬 사전 리허설(2026-10-28)**: 명령 순서는 다음과 같다.

1. `pg_dump -h localhost -d taku -Fc --no-owner --no-privileges -f taku.dump`
2. `CREATE DATABASE taku_restore_rehearsal`
3. `pg_restore --no-owner --no-privileges --exit-on-error` (복원 DB 대상)
4. 테이블별 `count(*)` 쿼리를 `\gexec`로 원본·복원 양쪽에서 실행해 diff
5. 복원 DB로 `manage.py check`·`migrate --check`
6. 복원 DB·덤프 삭제

결과 `[실측 2026-10-28]`: pg_dump/psql 14.19, 서버 14.19 로컬, 덤프 243,865바이트,
테이블 40개·행 1,452건(public 스키마 BASE TABLE 합) diff 0건, `check` 0 issues,
`migrate --check` 종료 코드 0, `django_cache` 54행이 덤프에 포함됨(§3-10 인지
사항 확인).

클라이언트 `pg_dump` 14.19와 운영 Supabase 서버 버전이 다르면 덤프가 거부될 수 있으므로 운영 리허설 전에 서버 버전(`SELECT version()`)에 맞는 클라이언트를 쓴다.

## 5. 롤백

- **이전 이미지 재배포**: PaaS의 이전 배포 버전으로 즉시 되돌린다(이미지가
  호스팅 중립이라 플랫폼 기본 롤백 기능을 그대로 사용 가능).
- **마이그레이션 역방향 판단 기준**: 롤백 대상 배포가 새 마이그레이션을
  포함했다면, 그 마이그레이션이 되돌릴 수 있는 스키마 변경(컬럼 추가 등)인지
  확인 후 `manage.py migrate <app> <이전 마이그레이션 이름>`으로 역방향
  마이그레이션을 실행할지 판단한다. 데이터 손실 가능성이 있는 역방향
  마이그레이션(컬럼 삭제 등)은 실행 전 반드시 백업을 재확인한다.
- **gunicorn 타임아웃(트랙 46) 롤백**: `GUNICORN_TIMEOUT=30`으로 env를 바꾸고 재기동하면 이전 동작(gunicorn 기본 30초 `[코드 gunicorn/config.py]`)이다.
- **장애 시 점검 순서**: 헬스(`/api/health/` 응답 상태) → 애플리케이션 로그
  (`LOGGING`, config/settings.py 콘솔 구조화 로그) → DB(연결·쿼리 지연) →
  스토리지(R2 접근 가능 여부).
- **닉네임 마이그레이션(`accounts.0006_user_nickname`) 실패 시**: entrypoint의
  `set -e`가 신규 컨테이너 기동 자체를 막으므로 구 컨테이너가 그대로
  서비스를 계속한다(`docker/entrypoint.sh`). **`migrate accounts 0005`로
  역적용하지 않는다** — 백필된 `nickname` 값이 소실된다. 실패 원인을 코드로
  고친 뒤 재배포한다.
- **다국어(트랙 43-1) 롤백**: `LocaleMiddleware`·`LANGUAGES`·`LOCALE_PATHS`·
  `i18n` 컨텍스트 프로세서·`LANGUAGE_CODE`·`LANGUAGE_COOKIE_*` 설정 diff를
  **하나의 커밋**으로 되돌린다. 일부만 되돌리면 `<html lang>`이 `ko`가
  아닌 값으로 남는 코스메틱 회귀가 생긴다. 마이그레이션 역적용은 없고,
  `locale/` 아래 `.po` 잔존은 무해하다.
- **행사 콘텐츠 번역(트랙 44-1) 롤백**: 마이그레이션
  `events.0009_event_text_translations_db_default`가 `text_translations`에 DB
  기본값 `'{}'::jsonb`를 두므로 코드만 이전 이미지로 되돌려도 구 코드의
  INSERT(열을 모르는 쿼리)가 NOT NULL 위반으로 깨지지 않는다 — 게시가
  유지된다. 0009 **이전** 상태(0008만 적용)로 돌아가는 경우에만 기본값이
  없으니 `psql "$DATABASE_URL" -c "ALTER TABLE events_event ALTER COLUMN
  text_translations SET DEFAULT '{}'::jsonb;"`를 먼저 실행한다(없으면 구
  코드의 이벤트 게시가 IntegrityError로 실패하고 "공식 URL 중복"으로
  오진된다). **마이그레이션 `events.0008_event_text_translations`를
  역적용(`migrate events 0007`)하면 `text_translations` 열이 삭제되어 번역
  데이터가 전량 사라진다** — 역적용은 번역을 러너로 다시 만드는 비용을
  감수할 때만 한다.

## 6. 미검증 항목 (첫 배포에서 채울 것)

| 항목 | 상태 | 채울 시점 |
|---|---|---|
| R2 실 업로드/다운로드 왕복 | 미검증(로컬 스모크만 완료) | 첫 배포 직후(§3 체크리스트 ⑦) |
| 선정 PaaS의 실제 프록시 홉 수 | Render 확정(§7). 홉 수 실측 완료 여부는 §3 ⑧ 기준 | T2 확정 후, 첫 배포 전(§3 체크리스트 ⑧) |
| 멀티워커 환경에서 rate limit 공유 실측 | 로컬 PG에서 워커 3개 실측 완료(2026-10-28, §3-9). 프로덕션(Render) 통합 환경은 미검증 | 첫 배포 직후(§3 체크리스트 ⑨) |
| 탈퇴 파기(`purge_deleted_accounts`) 정기 실행 등록 | 미등록(플랫폼은 §7에서 Render로 확정 — Render 스케줄러에 ENTRYPOINT 우회로 등록 필요, 비용 확인 포함) | 첫 배포 전(§3 체크리스트 ⑪) |
| 운영 로그 정리(`prune_operational_data`, 트랙 37) 정기 실행 등록 | 미등록(Render 스케줄러에 ENTRYPOINT 우회로 등록 필요, 비용 확인 포함 — `docs/operations-runbook.md` §7.2·`docs/BE/data-retention.md` 참고) | 첫 배포 전 |

## 7. 배포 브랜치와 deploy PR 흐름

호스팅 플랫폼은 Render로 확정했다(위 §1 서두의 "미확정" 서술은 T2 결정 당시
기준이며, 이후 Render로 확정 — production 브랜치 추종 전환이 이 확정을
전제로 한다).

- **흐름**: main에 PR 머지 → CI 성공 → `.github/workflows/deploy-pr.yml`이
  main→production PR을 자동 생성 → 사람이 그 PR을 머지 → Render가 추종하는
  production 브랜치가 갱신되며 배포가 시작된다.
- **최초 전환 순서**: ① 워크플로 파일과 저장소 Actions 설정(아래 참조)을
  main에 머지 ② `gh api repos/<repo>/actions/permissions/workflow`로 설정이
  실제로 반영됐는지 재확인 ③ main→production 왕복을 1회 실증(머지 후 deploy
  PR이 자동 생성되고 정상 머지되는지 확인) ④ Render 대시보드
  (Settings → Build & Deploy → Branch)에서 추종 브랜치를 production으로
  전환.
- **자동 생성 실패 시 수동 fallback**: `gh pr create --base production --head
  main`으로 직접 생성한다.
- **main 직접 커밋의 lint 통과**: main 직접 커밋도 `uv run ruff check . && uv run ruff format --check .`를
  통과해야 한다(`.claude/hooks/git-commit-style-guard.sh`가 로컬에서 막는다). main CI가 lint로
  실패하면 `.github/workflows/deploy-pr.yml`의 `workflow_run.conclusion == 'success'` 조건 때문에
  deploy PR이 자동 생성되지 않는다. 수정 커밋으로 main CI를 다시 초록으로 만든 뒤 자동 생성을
  기다리거나 위 수동 절차를 쓴다.
- **deploy PR에 CI 체크가 없는 것은 정상**이다 — `.github/workflows/ci.yml`의
  `pull_request` 트리거가 `branches-ignore: [production]`으로 production을
  향하는 PR을 건너뛰기 때문이다(트랙 42, 2026-10-20). 그 전에는
  "GITHUB_TOKEN으로 만든 PR은 워크플로가 돌지 않는다"고 적었지만 사실이
  아니었다: GitHub은 그런 PR에 승인 대기 실행(잡 0개)을 만들었고, 승인 없이
  머지되면 실패 기록으로 남았다. 또 사람이 main에 머지할 때마다 열린 deploy
  PR에서 main CI가 한 번 더 돌았다. 검증 근거는 이 PR에 포함된 main 커밋들이
  main push CI를 이미 통과했다는 사실이다.
- **`can_approve_pull_request_reviews=true`**는 이 워크플로가 PR을 생성할 수
  있도록 저장소 전역에서 켠 설정이며, deploy-pr.yml 한정이 아니다. 향후
  main/production에 필수 승인 브랜치 보호를 도입하는 시점에 이 설정을
  재검토한다. `[실측 gh api repos/youngroknroll/takulife/actions/permissions/workflow 2026-10-27: true]`
- **production에는 직접 push하지 않는다** — 항상 deploy PR을 경유한다.
  실패 감시는 GitHub Actions 탭의 워크플로 실행 이력과 실패 시 GitHub이
  보내는 알림 메일로 한다. production을 향하는 PR도 자동 생성된 deploy
  PR(head=main)만 쓴다. 이 PR에는 CI가 돌지 않으므로 긴급 수정도 main에
  먼저 머지한다.
