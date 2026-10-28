# takulife

서브컬처 팬이 공식 행사를 찾고, 다녀온 경험을 기록하고, 보유·구함·교환 의사가 있는 굿즈를 아카이빙하는 컬렉션 중심 웹 서비스다. 2026-08-31부터 https://takulife.kr 에서 운영 중이고, 코드는 https://github.com/youngroknroll/takulife 에 있다.

공식 행사 정보는 여러 채널에 흩어져 있고, 찾은 뒤에도 그것이 공식 정보인지 사용자가 다시 확인해야 한다. 방문 경험과 소장품은 행사와 연결되지 않은 채 따로 쌓인다. 이 세 가지를 하나의 흐름으로 묶으려고 만들었다.

만드는 동안 해결한 기술 문제는 네 가지다. 업로드 응답이 유실된 뒤 재시도하면 같은 사진이 두 번 저장되는 문제, 방문 완료 처리에서 상태 행이 동시에 생성되면 500이 나는 문제, 화면 조립 코드 때문에 앱끼리 순환 의존이 생긴 문제, 테스트 스위트가 313.81초 걸려 한 테스트씩 Red-Green을 도는 작업 방식이 성립하지 않던 문제다. 각 사례의 판단 과정은 4절에 적었다.

| 항목 | 내용 |
|---|---|
| 개발 기간 | 2026-05-20 첫 커밋 ~ 진행 중(2026-10-27 기준 160일, 커밋 1,807개 `[실측 git 2026-10-28]`) |
| 참여 형태 | 1인 프로젝트. 기획·도메인 설계·백엔드·프론트엔드·CI·배포를 혼자 수행했다 |
| 기술 스택 | Python 3.13, Django 5.2, Django REST Framework, PostgreSQL, Docker, Gunicorn, GitHub Actions, Render, Supabase, Cloudflare R2 |
| 배포 상태 | `https://takulife.kr/api/health/` 200 응답 `[실측 curl 2026-10-28]` |

실제 사용자 수와 요청량은 측정하지 않았다. 이 문서의 수치는 단위와 측정 시점을 함께 적었다. `[코드]`는 저장소에서 읽은 값이고 `[실측 날짜]`는 그 날짜에 실행해 얻은 값이다. 작성 기준은 2026-10-29 `main`(`ce27ac2c`)이다.

## 1. 핵심 성과

| 문제 | 결과 |
|---|---|
| 업로드 응답이 유실된 뒤 재시도하면 같은 사진이 두 번 저장됐다 | `(visit_record, client_token)` 유일 제약과 부모 행 잠금으로 재시도가 기존 행을 돌려준다. 브라우저에서 응답을 버리고 재시도해 사진이 4장→5장(6장 아님)이 되는 것을 확인했다 `[코드 커밋 bff9c353]` |
| 방문 완료 처리에서 상태 행이 동시에 생성되면 500이 났다 | 자기 소유 `UserEventStatus` 행을 잠그고 중복 시 1회 재조회하며, 뷰는 409로 응답한다. 별도 스레드·별도 DB 커넥션으로 경쟁 삽입을 재현한 테스트(RACE-02)가 있다 `[코드]` |
| 화면 조립 코드가 `core`에 있어 앱 간 순환 의존이 생겼다 | 잎 앱 `web`으로 옮겨 `core` 팬아웃 21→0, 순환 3쌍→0 `[실측 2026-08-02]`. 경계 테스트 39건, 뮤테이션 왕복 26회 전부 Red `[코드]` |
| 테스트 스위트 313.81초로 Red-Green 루프가 성립하지 않았다 | 같은 스위트에서 313.81초→약 30초 `[코드 커밋 37260451, 2026-07-18]`. 개선 중 allauth가 성공한 로그인도 rate limit에 세는 결함을 발견해 회귀 테스트를 추가했다 |

## 2. 해결하려는 문제와 핵심 흐름

흩어진 행사 정보, 공식 여부 재확인, 행사와 끊긴 방문·소장 기록을 다음 네 흐름으로 묶는다.

1. 비회원도 검수를 통과한 공식 행사만 목록·달력·상세에서 본다.
2. 회원은 찜·방문 예정·방문 완료를 관리하고, 방문 기록과 사진(기록당 5장)을 남긴다.
3. 회원은 굿즈를 보유·구함·교환 가능 수량으로 등록한다. 행사·방문 기록 연결은 선택이며, 행사가 사라져도 소장품은 남는다.
4. 운영자는 수집처 관리, 초안 검수·게시, 계정 운영을 하고 모든 조작이 감사 로그에 남는다.

설계 방향을 정한 제품 판단이 두 가지 있다. 행사 정보를 공개하려면 반드시 관리자 검수를 거쳐야 하고, 자동 추출 결과는 후보값일 뿐이다. 컬렉션은 행사 방문 없이도 등록할 수 있다. 교환 매칭·결제·배송·커뮤니티 피드는 범위 밖이다. [제품 결정과 실행 순서](CLAUDE.md)

## 3. 기술 구성과 요청 흐름

| 영역 | 선택 | 이유 |
|---|---|---|
| 백엔드 | Python 3.13, Django 5.2, DRF | 인증·ORM·마이그레이션·어드민이 내장돼 1인 개발에서 도메인 설계에 집중할 수 있다. 관리자 검수 파이프라인이 핵심이라 SSR과 세션 인증 조합이 맞았다 |
| DB | PostgreSQL(로컬은 SQLite 폴백) | 조건부 `UniqueConstraint`·`CheckConstraint`·`select_for_update`로 정합성을 DB에서 강제하는 것이 설계의 축이다 |
| 인증 | django-allauth, django-axes | 이메일 인증, Google 로그인, 5회 실패 시 1시간 IP 잠금을 직접 구현하지 않았다 |
| 공유 캐시 | PostgreSQL `DatabaseCache` | 요청 제한·로그인 잠금 카운터를 Gunicorn 워커 간에 공유해야 했고, Redis를 추가하지 않고 DB를 썼다 |
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

화면과 API가 모두 서버 내부의 서비스·조회 함수를 직접 부르므로 서버가 자기 HTTP API를 다시 호출하는 흐름은 없다. 수집처 탐색과 행사 텍스트 번역은 서버가 DB에 작업을 두고 로컬 러너가 임대·실행·제출하는 방식이며, 서버는 LLM을 직접 호출하지 않는다. Django 앱은 `accounts`·`events`·`drafts`·`archive`·`staff`·`web`·`core` 7개다. 앱별 책임·데이터 모델·동시성 처리 전체는 [시스템 구성 개요](docs/BE/architecture-overview.md)에 있다.

## 4. 핵심 문제 해결 사례

### 4-1. 사진 업로드 재시도가 중복을 만들지 않게

방문 기록 수정 화면은 업로드에 실패한 사진을 큐 맨 앞에 남겨 두고 저장 버튼을 다시 연다. 사용자가 다시 저장하면 같은 `File` 객체가 다시 전송된다. 서버가 사진을 이미 커밋했는데 응답만 유실된 경우, 이 재전송이 같은 사진을 두 행으로 저장했다. `VisitRecord`와 `CollectionItem`은 이미 `client_token`으로 재전송을 걸러내고 있었지만 `VisitRecordPhoto`에는 그 키가 없었다.

처음에는 외부 코드 검토가 지목한 작성 화면부터 봤다. 그런데 코드를 따라가 보니 작성 화면은 업로드가 실패하면 재전송 채널 자체가 없었다. 실제로 재전송이 일어나는 곳은 수정 화면의 큐뿐이었고, 적용 범위를 거기로 좁혔다.

토큰을 언제 발급할지도 정해야 했다. 업로드 직전에 발급하면 재시도마다 새 토큰이 생겨 아무것도 막지 못한다. 그래서 파일을 고른 시점에 발급해 큐 항목에 보관했다. 재시도는 같은 큐 항목을 다시 보내므로 같은 토큰이 실린다.

해결은 DB와 서비스 두 계층으로 나눴다. DB에는 `(visit_record, client_token)` `UniqueConstraint`를 두어 서비스 코드를 우회하는 경로까지 막는다. 키 범위를 `(user, client_token)`이 아니라 방문 기록 단위로 둔 것은 사진이 방문 기록의 하위 행이고, 한 사용자가 여러 기록에 여러 사진을 올리기 때문이다. 서비스는 부모 방문 기록 행을 `select_for_update`로 잠근 뒤 재전송 조회, 상한 검사, 저장 순으로 실행한다. 행 잠금은 사진이 4장일 때 동시 요청 두 건이 모두 4장으로 보고 저장하는 경합을 막고, 같은 토큰의 동시 요청은 락에서 기다렸다가 커밋된 행을 보게 한다. 그래도 유일 제약에 걸리면 `IntegrityError`를 atomic 블록 밖에서 잡아 재조회한다. PostgreSQL은 세이브포인트를 롤백하기 전까지 같은 트랜잭션의 추가 문장을 거부하므로 블록 안에서 재조회하면 안 된다.

검사 순서는 서비스 코드를 읽다가 바로잡았다. 형제 함수 `create_visit_record`의 패턴을 그대로 옮기면 기록당 5장 상한 검사가 재전송 조회보다 먼저 실행된다. 그러면 5번째 사진을 저장한 요청의 재전송이 기존 행 대신 "상한 초과"로 거부된다. 멱등 키가 꼭 필요한 경우를 그 순서가 깨뜨리고 있었다. 상한 검사가 어차피 개수를 세느라 같은 락을 잡으므로, 락 안에서 재전송을 먼저 조회해도 추가 비용은 없다.

테스트는 `tests/archive/test_archive_services.py`에 있다. `select_for_update` 호출을 스파이로 확인하는 테스트, 토큰 없는 6번째 업로드 거부, 5번째 사진 재전송이 상한 초과가 아니라 기존 행을 돌려주는지, 서로 다른 기록에 같은 토큰을 써도 각각 저장되는지를 본다. 브라우저에서는 fetch를 가로채 서버가 커밋한 뒤 응답을 버리고 재시도했고, 사진 수가 4장에서 5장이 됐다(커밋 `bff9c353`, 2026-07-28).

검증 범위에는 한계가 있다. 락 테스트는 호출 여부만 확인하고, 별도 커넥션 두 개로 실제 경쟁을 재현한 테스트는 방문 완료 처리에만 있다. 이 계약은 PostgreSQL에서만 성립하고 SQLite는 `select_for_update`를 무시하므로 테스트는 PostgreSQL로 실행한다. 이미지 저장이 락 안에서 일어나므로 저장소가 느리면 같은 기록의 다른 업로드가 그만큼 기다린다. 작성 화면에는 재시도 채널이 없어 토큰을 적용하지 않았다. [상세](docs/BE/visit-photo-idempotency.md), [방문 완료 동시성](docs/BE/visit-completion-concurrency.md)

### 4-2. 화면 조립을 `core`에서 떼어내 순환 의존을 없앴다

홈이나 아카이브 같은 화면은 여러 도메인의 데이터를 한 페이지에 조립한다. 이 뷰들이 공유 커널 앱인 `core`에 있었다. 조립 코드는 모든 도메인을 알아야 하므로 `core`가 도메인 앱을 21곳에서 임포트했고, 도메인 앱은 설정 헬퍼·오류·로깅 때문에 다시 `core`를 임포트한다. 앱 간 순환 임포트가 3쌍 생겼고, 새 화면을 만들 때마다 의존이 늘었다.

문제는 커널과 프레젠테이션 조립이 한 앱에 있다는 점이었다. 커널은 어떤 도메인도 몰라야 하고, 조립은 모든 도메인을 알아야 한다. 두 책임을 한 앱에 둘 수는 없다.

그래서 2026-08-02 새 앱 `web`을 만들어 프레젠테이션 뷰 7파일을 옮겼다. `web`은 모든 앱을 임포트하지만 어떤 앱도 `web`을 임포트하지 않는 잎이다. `core`에는 설정 헬퍼·오류·로깅·분석·러너 토큰 인증과 `api_root`·`robots_txt`·`health` 같은 커널 관심사만 남겼다. `archive`와 `drafts`는 서로를 임포트할 수 없으므로 개인 항목을 공식 제보로 잇는 교차 도메인 쓰기는 `web/promotion.py` 한 곳으로 제한했다.

의존 방향은 문서에만 적어 두면 지켜지지 않는다. `tests/core/test_architecture_boundaries.py`가 파일시스템을 순회해 정적 import와 `importlib.import_module`·`__import__`까지 스캔한다. 처음에는 검사 대상 모듈을 손으로 적은 목록으로 관리했다. 그런데 목록에 없는 모듈 22건에 금지 임포트를 넣어 봤더니 전부 통과했다. 목록을 손으로 유지하는 한 같은 누락이 반복될 것이라 보고 파일시스템 스캔으로 바꿨고, 스캔 대상이 0개면 조용히 통과하지 않고 실패하게 했다.

테스트가 위반을 실제로 잡는지는 금지 임포트를 일부러 넣어 확인했다. 전환 후 뮤테이션 왕복 26회가 전부 Red였다. 이동 자체는 뷰 7파일이 바이트 단위로 동일하고 라우트 175건의 순회 순서가 바뀌지 않았음을 확인했다. `core` 팬아웃은 21→0, 순환은 3쌍→0이 됐다 `[실측 2026-08-02]`. 경계 테스트는 39건이다 `[실측 rg 2026-10-28]`.

이 가드는 import를 통한 결합만 본다. 변수나 f-string 인자를 쓰는 동적 임포트, 시그널처럼 import 없는 결합은 잡지 못한다. `web/views` 안의 서브모듈 단방향 규칙(`collection`은 `archive`를 임포트하지 않고 `_helpers`는 어떤 형제도 임포트하지 않는다)은 처음에 문서로만 지키다가 2026-10-29 별도 계약 테스트 `tests/core/test_web_views_package_boundaries.py`로 옮겼다. 이 테스트도 패키지 퍼사드를 거친 임포트와 동적 임포트는 잡지 못한다. [web/views 계약](docs/BE/web-views-package.md), [계약 가드 범위](docs/BE/contract-guards.md)

### 4-3. 테스트 스위트 313.81초를 같은 날 약 30초로

2026-07-17 기준 백엔드 스위트(테스트 함수 1,481개 정적 카운트)가 313.81초 걸렸다. 테스트 하나를 Red로 만들고 Green으로 바꾸는 작업을 반복하는 방식인데, 확인 한 번에 그만큼 기다려야 하니 루프가 성립하지 않았다.

실행 시간을 나눠 보니 세 가지가 겹쳐 있었다. 사용자 픽스처가 테스트마다 운영 강도의 PBKDF2 해시를 수행했는데 1회에 약 0.38초였다. 임시 사용자를 많이 만드는 테스트에서는 이것이 시간의 대부분이었다. `tests/conftest.py`의 캐시 초기화 픽스처가 autouse라 DB를 쓰지 않는 테스트까지 매번 캐시 테이블을 비웠다. 빠른 단위 테스트와 느린 통합 테스트가 한 덩어리라 일부만 골라 돌릴 수단도 없었다.

병렬 실행(pytest-xdist)도 검토했지만 뒤로 미뤘다. 원인이 불필요한 작업량이라 작업량을 먼저 줄이는 것이 맞았고, 병렬화는 DB 격리 비용이 따로 들며 숨은 결함을 더 가릴 수 있다.

`config/settings_test.py`를 만들어 운영 설정을 그대로 불러온 뒤 `PASSWORD_HASHERS`만 MD5로 덮어썼다. `CACHES`는 일부러 덮어쓰지 않았다. rate limit과 로그인 잠금 카운터가 `DatabaseCache`에 있으므로 테스트도 운영과 같은 계약 위에서 돌아야 한다. 테스트 설정이 운영으로 새지 않도록 `manage.py`·`config/wsgi.py`·CI·Docker가 이 설정을 참조하지 못하게 계약 테스트로 고정하고 `.dockerignore`로 이미지에서 뺐다. 캐시 초기화 픽스처는 autouse를 해제했고, `make_user`의 기본 비밀번호를 unusable로 바꿔 인증과 무관한 테스트가 해시 비용을 내지 않게 했다. `unit`·`domain`·`web`·`contract`·`slow`·`e2e` 여섯 marker를 `--strict-markers`로 등록해 계층을 나눴다.

같은 스위트에서 313.81초가 약 30초로, e2e는 129.17초가 약 76초로 줄었다(커밋 `37260451` 본문, 2026-07-18).

더 중요한 것은 이 과정에서 드러난 결함이다. 전역 캐시 초기화를 없애자 e2e의 연속 로그인 시나리오가 429로 실패했다. django-allauth 기본 로그인 rate limit이 성공한 로그인까지 세고 있었고, 매 테스트 캐시를 비우던 픽스처가 그 동작을 가려 왔다. 운영 설정은 그대로 두고 `tests/e2e/conftest.py`에 캐시 격리 픽스처를 두어 해소했으며, 이 동작을 고정하는 회귀 테스트를 `tests/auth/test_auth_rate_limit.py`에 추가했다.

개선 효과는 2026-07-18의 같은 스위트 비교만 유효하다. 스위트는 그 뒤 4,284개로 늘어 2026-10-28에는 149.07초였다 `[실측 2026-10-28]`. 그래서 2차로 다시 쟀는데, 가장 느린 단일 테스트가 2.07초이고 픽스처·DB 셋업 비용도 작아 시간이 테스트 본문에 고르게 퍼져 있었다. 이번에는 줄일 작업량이 남지 않아 병렬 실행만 남았다. pytest-xdist 4워커로 돌리면 53.87초이고 전 테스트가 병렬에서도 통과했다 `[실측 2026-10-28, 8코어]`. 다만 새 테스트 패키지 도입은 별도 승인이 필요해 아직 반영하지 않았다. [상세](docs/BE/test-suite-speed.md)

## 5. 배포·운영 및 검증

| 항목 | 내용 |
|---|---|
| 배포 경로 | `main` 푸시 CI 성공 → 워크플로가 `main → production` PR 자동 생성 → 사람이 머지 → Render가 `production` 브랜치를 배포 |
| 실행 | Docker 멀티스테이지(uv) + Gunicorn 워커 3(`WEB_CONCURRENCY`), 워커 타임아웃 120초(`GUNICORN_TIMEOUT`, 2026-10-29 추가), 기동 시 migrate → CSS 번들 → collectstatic |
| DB·저장소 | Supabase PostgreSQL(Session pooler 경유), Cloudflare R2에 서명 URL로 미디어 제공 |
| CI | `test`(PostgreSQL 서비스 + `check --deploy`), `e2e`(관측, non-blocking), `audit`(pip-audit), `docker`(이미지 실기동 후 `/api/health/` 폴링) |
| 보안 | HSTS·secure 쿠키를 env로 전환, `TRUSTED_PROXY_COUNT`로 프록시 뒤 실제 IP 판별, 스로틀 12스코프, 공개 쓰기 API는 `/api/client-errors/` 하나 |
| 상태 확인 | `/api/health/`가 DB 연결 실패 시 503, 처리되지 않은 500과 프론트 오류를 지문으로 묶어 대시보드에 표시 |
| 테스트 | 백엔드 4,297 passed / 152.02초 `[실측 2026-10-29, main ce27ac2c]`, e2e 10 passed `[실측 2026-10-27]`. 테스트 작성 뒤 코드를 깨서 Red를 확인하는 뮤테이션 절차를 상시 적용한다 |

운영하면서 찾아 고친 문제도 있다. 2026-09-27 보안 검토에서는 스태프가 입력한 `official_url`에 `javascript:` 스킴이 저장돼 공개 상세에서 실행될 수 있는 저장형 XSS(F1)와, allauth의 IP 기준 rate limit이 프록시 뒤에서 모든 사용자를 한 버킷으로 묶는 문제(F2)를 찾았다. http(s)만 허용하는 스킴 검증과 `ALLAUTH_TRUSTED_PROXY_COUNT` 배선으로 수정했다(PR #388, 2026-10-04). [검토 기록](docs/BE/security-review-2026-09-27.md)

2026-09-14 DB 락·트랜잭션 검수에서는 세이브포인트 누락, 삭제 뷰 잠금 순서, PATCH 원자성 등 결함 7건을 찾아 고쳤다(트랙 32). 2026-10-28에는 로컬에서 Gunicorn 워커 3개를 띄워 rate limit 카운터가 워커 사이에서 실제로 공유되는지 확인했고, 로컬 DB를 `pg_dump`로 반출해 복원하는 리허설을 했다. Supabase 무료 티어는 DB 활동이 7일 없으면 일시정지되고, Render 무료 Postgres는 30일에 만료된다. 이런 비용 제약 아래에서 Supabase를 고른 판단은 [배포 런북](docs/deploy-runbook.md)에 있다.

현재 제한 사항은 중요도순으로 다음과 같다.

1. SMTP가 설정되지 않아 콘솔 이메일 백엔드가 동작한다. 신규 가입 인증 메일이 실제로 발송되지 않으므로 실사용자 유입 전 단계다.
2. Supabase 무료 티어에는 자동 백업이 없다. `pg_dump` 반출 절차는 런북에 있고 로컬 덤프·복원 리허설(2026-10-28)은 했지만, 운영 DB를 대상으로 한 리허설 기록은 없다.
3. 멀티워커 rate limit 공유는 로컬 3워커 실측(2026-10-28)으로만 확인했고, 프로덕션 통합 환경에서는 재지 않았다.
4. 로컬 러너의 launchd 자동 시작 템플릿은 있지만 설치는 운영자 액션이고, 정기 수집 스케줄러는 없다.
5. 다국어 UI(ko/en/ja/zh-hans) 번역은 사람 검수 없이 AI 검수만 거쳤다.

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
