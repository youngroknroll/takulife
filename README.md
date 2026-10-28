# takulife

서브컬처 팬이 공식 행사를 찾고, 다녀온 경험을 기록하고, 보유·구함·교환 의사가 있는 굿즈를 아카이빙하는 컬렉션 중심 웹 서비스다.

| 항목 | 내용 |
|---|---|
| 개발 기간 | 2026-05-20 첫 커밋 ~ 진행 중(2026-10-27 기준 160일, 커밋 1,807개 `[실측 git 2026-10-28]`) |
| 참여 형태 | 1인 프로젝트. 기획·도메인 설계·백엔드·프론트엔드·CI·배포를 혼자 수행했다 |
| 배포 상태 | 2026-08-31부터 운영 중. `https://takulife.kr/api/health/` 200 응답 `[실측 curl 2026-10-28]` |
| 서비스 URL | https://takulife.kr |
| 기술 스택 | Python 3.13, Django 5.2, Django REST Framework, PostgreSQL, Docker, Gunicorn, GitHub Actions, Render, Supabase, Cloudflare R2 |
| 저장소 | https://github.com/youngroknroll/takulife |

실제 사용자 수·요청량은 측정하지 않았다. 이 문서의 수치는 전부 단위와 측정 시점을 함께 적었고, `[코드]`는 저장소에서 읽은 값, `[실측 날짜]`는 그 날짜에 실행해 얻은 값이다. 작성 기준은 2026-10-28 `main`(`b175ce69`)이다.

## 1. 핵심 성과

| 문제 | 해결 방법 | 검증 결과 |
|---|---|---|
| 응답 유실 뒤 재시도가 같은 사진을 두 번 저장 | `(visit_record, client_token)` 유일 제약 + 부모 행 `select_for_update` + 재전송 조회를 상한 검사보다 먼저 실행 | 락 스파이·상한·"5번째 사진 재전송" 테스트, 브라우저에서 응답을 버리고 재시도해 4장→5장(6장 아님) 확인 `[코드 커밋 bff9c353]` |
| 방문 완료 처리에서 상태 행이 동시에 생성되면 500 | 자기 소유 `UserEventStatus` 행 잠금, 중복 시 1회 재조회, 뷰는 409 | 별도 스레드·별도 DB 커넥션으로 실제 경쟁 삽입을 재현한 테스트(RACE-02) `[코드]` |
| 화면 조립 때문에 앱끼리 순환 의존 | 잎(leaf) 앱 `web` 분리, 교차 도메인 쓰기는 `web/promotion.py` 한 곳으로 제한, AST 스캔 경계 테스트 | `core` 팬아웃 21→0, 순환 3쌍→0 `[실측 2026-08-02]`, 경계 테스트 39건·뮤테이션 왕복 26회 전부 Red `[코드]` |
| 테스트 스위트 313.81초로 Red-Green 루프 불가 | 테스트 전용 해셔 설정, autouse 픽스처 제거, 6계층 marker | 같은 스위트 313.81초→약 30초 `[코드 커밋 37260451, 2026-07-18]`. 개선 중 allauth가 성공 로그인도 rate limit에 세는 숨은 결함 발견·회귀 테스트 추가 |

## 2. 해결하려는 문제와 핵심 흐름

공식 행사 정보는 여러 채널에 흩어져 있고, 찾은 뒤에도 그것이 공식 정보인지 사용자가 다시 확인해야 한다. 방문 경험과 소장품은 행사와 연결되지 않은 채 흩어진다. takulife는 이 세 가지를 하나의 흐름으로 묶는다.

1. 비회원도 검수를 통과한 공식 행사만 목록·달력·상세에서 본다.
2. 회원은 찜·방문 예정·방문 완료를 관리하고, 방문 기록과 사진(기록당 5장)을 남긴다.
3. 회원은 굿즈를 보유·구함·교환 가능 수량으로 등록한다. 행사·방문 기록 연결은 선택이며, 행사가 사라져도 소장품은 남는다.
4. 운영자는 수집처 관리, 초안 검수·게시, 계정 운영을 하고 모든 조작이 감사 로그에 남는다.

구조를 결정한 제품 판단 두 가지가 있다. 행사 정보 공개에는 반드시 관리자 검수가 필요하고(추출 결과는 후보값일 뿐), 컬렉션은 행사 방문 없이도 등록할 수 있다. 교환 매칭·결제·배송·커뮤니티 피드는 범위 밖이다. [제품 결정과 실행 순서](CLAUDE.md)

## 3. 기술 구성과 요청 흐름

| 영역 | 선택 | 이유 |
|---|---|---|
| 백엔드 | Python 3.13, Django 5.2, DRF | 인증·ORM·마이그레이션·어드민이 내장돼 1인 개발에서 도메인 설계에 집중할 수 있고, 관리자 검수 파이프라인이 핵심이라 SSR과 세션 인증 조합이 맞았다 |
| DB | PostgreSQL(로컬은 SQLite 폴백) | 조건부 `UniqueConstraint`·`CheckConstraint`·`select_for_update`로 정합성을 DB에서 강제하는 것이 설계의 축이다 |
| 인증 | django-allauth, django-axes | 이메일 인증, Google 로그인, 5회 실패 시 1시간 IP 잠금을 직접 구현하지 않았다 |
| 공유 캐시 | PostgreSQL `DatabaseCache` | 요청 제한·로그인 잠금 카운터를 Gunicorn 워커 간에 공유하기 위해 Redis 없이 DB를 썼다 |
| 프런트엔드 | 순수 CSS(OOCSS/BEM), 바닐라 JS | SSR 중심이라 빌드 체인 없이 유지비를 낮췄다 |
| 테스트 | pytest, pytest-playwright | 백엔드 테스트가 기본이고 여정 e2e 10건은 `-m e2e`로만 실행한다 |
| 인프라 | Docker, GitHub Actions, Render, Supabase, Cloudflare R2 | CI에서 빌드한 이미지를 실제로 기동해 `/api/health/`를 폴링하는 스모크를 돌린다 |
| 패키징 | uv | lockfile 기반 재현 환경, 빠른 CI 설치 |

```mermaid
flowchart TD
    B["사용자 브라우저"] --> G["Gunicorn · Django"]
    G --> W["web · 소비자 SSR 화면"]
    G --> ST["staff · 운영자 콘솔"]
    G --> A["events · archive · drafts · DRF API"]
    W --> S["서비스 · 조회 함수"]
    ST --> S
    A --> S
    S --> D[("PostgreSQL")]
    S --> M["미디어 저장소(Cloudflare R2)"]
    R["로컬 러너(개인 Mac)"] -- "작업 임대 · 후보 제출 · 번역 제출" --> A
```

화면과 API가 모두 서버 내부의 서비스·조회 함수를 직접 부르므로 서버가 자기 HTTP API를 다시 호출하는 흐름은 없다. 수집처 탐색과 행사 텍스트 번역은 서버가 DB에 작업을 두고 로컬 러너가 임대·실행·제출하는 방식이며, 서버는 LLM을 직접 호출하지 않는다. Django 앱은 `accounts`·`events`·`drafts`·`archive`·`staff`·`web`·`core` 7개이고, 앱별 책임·데이터 모델·동시성 처리 전체는 [시스템 구성 개요](docs/BE/architecture-overview.md)에 있다.

## 4. 핵심 문제 해결 사례

### 4-1. 사진 업로드 재시도가 중복을 만들지 않게

**문제.** 방문 기록 수정 화면은 실패한 업로드를 큐에 남겨 재전송한다. 서버가 커밋한 뒤 응답만 유실되면 같은 사진이 두 행으로 저장됐다.

**원인.** 외부 코드 검토는 작성 화면을 지목했지만, 코드를 따라가니 작성 화면에는 재전송 채널이 없었고 실제 경로는 수정 화면의 큐였다. 또 형제 함수의 패턴을 그대로 옮기면 상한 검사(기록당 5장)가 재전송 조회보다 먼저 실행돼, 5번째 사진을 저장한 요청의 재전송이 기존 행 대신 "상한 초과"로 거부되는 결함이 생긴다는 것을 서비스 코드를 읽다가 발견했다.

**해결.** `(visit_record, client_token)` `UniqueConstraint`를 DB에 두고, 서비스는 부모 방문 기록 행을 `select_for_update`로 잠근 뒤 재전송 조회 → 상한 검사 → 저장 순으로 실행한다. 어차피 상한 검사가 모든 호출을 같은 락 안으로 모으므로 락 안 조회는 추가 비용이 없다. `IntegrityError`는 atomic 블록 밖에서 잡아 재조회한다(PostgreSQL은 세이브포인트 롤백 전까지 같은 트랜잭션의 추가 문장을 거부한다). 토큰은 업로드 직전이 아니라 파일 선택 시점에 발급해야 재시도가 같은 토큰을 싣는다.

**검증.** 락 스파이, 상한, 5번째 사진 재전송, 범위 경계 테스트가 `tests/archive/test_archive_services.py`에 있다. 브라우저에서 fetch를 가로채 커밋 후 응답을 버리고 재시도해 사진이 4장에서 5장이 되는 것을 확인했다(커밋 `bff9c353`, 2026-07-28).

**한계.** 작성 화면에는 재시도 채널이 없어 토큰을 적용하지 않았다. 락 테스트는 호출 여부를 스파이로 확인하며, 두 커넥션 경쟁 재현은 방문 완료 처리에만 있다. 이미지 저장이 락 안에서 일어나 저장소 지연이 같은 기록의 다른 업로드를 대기시킨다. [상세](docs/BE/visit-photo-idempotency.md), [방문 완료 동시성](docs/BE/visit-completion-concurrency.md)

### 4-2. 앱 간 순환 의존을 잎 앱 분리와 AST 가드로 제거

**문제.** 홈·아카이브처럼 여러 도메인을 조합하는 화면 뷰가 `core`에 있어 `core`가 도메인 앱 21곳을 임포트했고, 앱 간 순환 임포트가 3쌍 있었다. 새 화면을 만들 때마다 의존이 늘었다.

**원인.** 공유 커널(`core`)과 프레젠테이션 조립이 같은 앱에 있었다. 조립 코드는 모든 도메인을 알아야 하고, 커널은 어떤 도메인도 몰라야 하므로 한 앱에 둘 수 없다.

**해결.** 프레젠테이션 조립을 새 앱 `web`으로 옮겨 어떤 앱도 임포트하지 않는 잎으로 만들고, `core`는 도메인 앱을 임포트하지 않게 했다. `archive`와 `drafts`는 서로를 임포트할 수 없으므로 개인 항목을 공식 제보로 잇는 교차 도메인 쓰기는 `web/promotion.py` 한 곳으로 제한했다. 경계는 문서가 아니라 `tests/core/test_architecture_boundaries.py`가 지킨다. 손유지 목록 대신 파일시스템을 직접 순회해 정적 import와 `importlib.import_module`·`__import__`까지 스캔하고, 스캔 대상이 0개면 공허하게 통과하지 않고 실패한다.

**검증.** `core` 팬아웃 21→0, 순환 3쌍→0, 이동한 뷰 7파일 바이트 동일, 라우트 175건 순회 순서 무변경 `[실측 2026-08-02]`. 손유지 목록을 버린 이유는 목록에 없는 모듈 22건에 금지 임포트를 주입했을 때 전부 통과했기 때문이며, 전환 후 뮤테이션 왕복 26회가 전부 Red였다. 경계 테스트는 39건이다 `[실측 rg 2026-10-28]`.

**한계.** 비-리터럴 인자 동적 임포트, 시그널 같은 import 없는 결합은 잡지 못한다. `web/views` 서브모듈 단방향 규칙(`collection`은 `archive`를 임포트하지 않고 `_helpers`는 잎)은 별도 계약 테스트로 강제하며, 패키지 퍼사드 임포트와 동적 임포트는 잡지 못한다. [web/views 계약](docs/BE/web-views-package.md), [계약 가드 범위](docs/BE/contract-guards.md)

### 4-3. 테스트 스위트 313.81초를 같은 날 약 30초로

**문제.** 2026-07-17 기준 백엔드 스위트(테스트 함수 1,481개 정적 카운트)가 313.81초 걸려 한 테스트씩 Red-Green을 도는 작업 방식이 성립하지 않았다.

**원인.** 사용자 픽스처가 테스트마다 운영 강도 PBKDF2 해시(1회 약 0.38초)를 수행했고, `tests/conftest.py`의 캐시 초기화 픽스처가 autouse라 모든 테스트에 걸려 있었으며, 빠른 단위 테스트와 느린 통합 테스트가 한 덩어리였다.

**해결.** `config/settings_test.py`가 운영 설정을 그대로 불러온 뒤 `PASSWORD_HASHERS`만 MD5로 덮어쓴다. `CACHES`는 일부러 덮어쓰지 않아 `DatabaseCache` 계약을 운영과 동일하게 유지하고, 운영 진입점이 테스트 설정을 참조하지 못하게 계약 테스트와 `.dockerignore`로 막았다. autouse를 해제하고 `unit`·`domain`·`web`·`contract`·`slow`·`e2e` marker를 `--strict-markers`로 등록했다. 병렬화(pytest-xdist)는 원인이 작업량이라 뒤로 미뤘다.

**검증.** 같은 스위트에서 313.81초→약 30초, e2e 129.17초→약 76초(커밋 `37260451` 본문, 2026-07-18). 더 중요한 발견은 autouse 제거로 드러난 결함이다. django-allauth 기본 로그인 rate limit이 성공한 로그인까지 세어 연속 로그인이 429로 실패했고, 전역 픽스처가 이를 가리고 있었다. 운영 설정은 두고 e2e 캐시 격리 픽스처와 회귀 테스트(`tests/auth/test_auth_rate_limit.py`)로 고정했다.

**한계.** 현재 스위트는 4,284개로 늘어 152.46초다 `[실측 2026-10-27]`. 개선 효과는 2026-07-18의 같은 스위트 비교만 유효하고, 2차 개선은 착수하지 않았다. [상세](docs/BE/test-suite-speed.md)

## 5. 배포·운영 및 검증

| 항목 | 내용 |
|---|---|
| 배포 경로 | `main` 푸시 CI 성공 → 워크플로가 `main → production` PR 자동 생성 → 사람이 머지 → Render가 `production` 브랜치를 배포 |
| 실행 | Docker 멀티스테이지(uv) + Gunicorn 워커 3(`WEB_CONCURRENCY`), 기동 시 migrate → CSS 번들 → collectstatic |
| DB·저장소 | Supabase PostgreSQL(Session pooler 경유), Cloudflare R2에 서명 URL로 미디어 제공 |
| CI | `test`(PostgreSQL 서비스 + `check --deploy`), `e2e`(관측, non-blocking), `audit`(pip-audit), `docker`(이미지 실기동 후 `/api/health/` 폴링) |
| 보안 | HSTS·secure 쿠키를 env로 전환, `TRUSTED_PROXY_COUNT`로 프록시 뒤 실제 IP 판별, 스로틀 12스코프, 공개 쓰기 API는 `/api/client-errors/` 하나 |
| 상태 확인 | `/api/health/`가 DB 연결 실패 시 503, 처리되지 않은 500과 프론트 오류를 지문으로 묶어 대시보드에 표시 |
| 테스트 | 백엔드 4,284 passed / 152.46초, e2e 10 passed `[실측 2026-10-27]`. 테스트 작성 뒤 코드를 깨서 Red를 확인하는 뮤테이션 절차를 상시 적용한다 |

운영 환경에서 확인된 문제와 조치:

- **2026-09-27 보안 검토**에서 스태프가 입력한 `official_url`에 `javascript:` 스킴이 저장돼 공개 상세에서 실행될 수 있는 저장형 XSS(F1)와, allauth의 IP 기준 rate limit이 프록시 뒤에서 모든 사용자가 한 버킷을 공유하는 문제(F2)를 찾았다. http(s)만 허용하는 스킴 검증과 `ALLAUTH_TRUSTED_PROXY_COUNT` 배선으로 수정했다(PR #388, 2026-10-04). [검토 기록](docs/BE/security-review-2026-09-27.md)
- **2026-09-14 DB 락·트랜잭션 검수**에서 세이브포인트 누락, 삭제 뷰 잠금 순서, PATCH 원자성 등 결함 7건을 찾아 고쳤다(트랙 32).
- **Supabase 무료 티어 DB 활동 7일 부재 시 일시정지**, Render 무료 Postgres의 30일 만료를 피하기 위한 Supabase 선택 등 비용 제약 아래의 판단은 [배포 런북](docs/deploy-runbook.md)에 있다.

알려진 한계:

- SMTP 미설정으로 콘솔 이메일 백엔드가 동작한다. 신규 가입 인증 메일이 실제 발송되지 않아 실사용자 유입 전 단계다.
- Supabase 무료 티어에는 자동 백업이 없다. `pg_dump` 반출 절차는 런북에 있지만 로컬 덤프·복원 리허설(2026-10-28)만 있고 운영 DB 리허설 기록은 없다.
- 멀티워커 rate limit 공유는 로컬 3워커 실측으로 확인했고(2026-10-28), 프로덕션 통합 환경 실측은 없다.
- 로컬 러너 launchd 자동 시작 템플릿은 있으나 설치는 운영자 액션이고 정기 수집 스케줄러는 없다.
- 다국어 UI(ko/en/ja/zh-hans) 번역은 사람 검수 없이 AI 검수만 거쳤다.

## 6. 실행 방법

```bash
cp .env.example .env          # 실제 비밀값은 .env에만 두고 커밋하지 않는다
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
uv run pytest -q              # 백엔드 테스트(e2e 제외)
uv run pytest -q -m e2e tests/e2e   # 여정 e2e(Playwright, 별도 실행)
```

`DATABASE_URL`을 비우면 SQLite로 폴백한다. PostgreSQL은 `docker compose up -d db` 후 `.env`에 `DATABASE_URL=postgresql://taku:taku@localhost:5432/taku`를 설정한다(로컬 개발용 자격 증명). `EMAIL_HOST`를 비우면 인증 메일이 터미널에 출력된다. 번역 카탈로그를 쓰려면 GNU gettext 설치 후 `uv run django-admin compilemessages --ignore .venv`를 한 번 실행한다.

## 7. 상세 문서

| 주제 | 문서 |
|---|---|
| 시스템 구성·데이터 모델·동시성·비동기 처리 | [docs/BE/architecture-overview.md](docs/BE/architecture-overview.md) |
| 사진 업로드 멱등성·동시성 | [docs/BE/visit-photo-idempotency.md](docs/BE/visit-photo-idempotency.md) |
| 방문 완료 동시성 계약(두 커넥션 경쟁 재현) | [docs/BE/visit-completion-concurrency.md](docs/BE/visit-completion-concurrency.md) |
| 앱 의존 방향·계약 가드 범위 | [docs/BE/web-views-package.md](docs/BE/web-views-package.md), [docs/BE/contract-guards.md](docs/BE/contract-guards.md) |
| 테스트 실행시간 개선 | [docs/BE/test-suite-speed.md](docs/BE/test-suite-speed.md) |
| 배포·운영 | [docs/deploy-runbook.md](docs/deploy-runbook.md), [docs/operations-runbook.md](docs/operations-runbook.md) |
| 보안 검토 | [docs/BE/security-review-2026-09-27.md](docs/BE/security-review-2026-09-27.md), [docs/BE/draft-fetching-ssrf.md](docs/BE/draft-fetching-ssrf.md) |
| 수집처 탐색·검수 생명주기 | [docs/BE/draft-source-agent-discovery.md](docs/BE/draft-source-agent-discovery.md), [docs/BE/draft-review-lifecycle.md](docs/BE/draft-review-lifecycle.md) |
| 다국어·OpenAPI·오류 묶음·보존 정리 | [docs/BE/i18n.md](docs/BE/i18n.md), [docs/BE/openapi-schema.md](docs/BE/openapi-schema.md), [docs/BE/error-groups.md](docs/BE/error-groups.md), [docs/BE/data-retention.md](docs/BE/data-retention.md) |
| 백로그·머지 이력 | [docs/backlog.md](docs/backlog.md), [docs/pr-log.md](docs/pr-log.md) |
