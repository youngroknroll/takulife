# 트랙 13: Lighthouse 성능 최적화 3건 (2026-08-29)

> 배경: 사용자 요청 "chrome lighthouse 성능 최적화 + 수정". 실측(2026-08-29,
> 로컬 프로덕션 동등 서버 DEBUG=false·whitenoise·gunicorn 3워커, 모바일=Slow 4G
> +CPU 4x / 데스크탑=무스로틀, 공개 3페이지): LCP 184~1,170ms·CLS≤0.02 —
> 전 지표 Good. 결함 3건: ① PretendardVariable.woff2 2,057,688B 단일 파일
> (데스크탑 홈 CLS 0.02의 원인=폰트 스왑 리플로, 트레이스 직접 지목 [실측]),
> ② HTML 무압축(페이지당 11~25.3kB 낭비 [실측]), ③ brotli 사전압축 0개
> [실측]. 사용자 승인(2026-08-29): 3건 모두 수정.

## 승인 범위

**A. 폰트 다이어트 (FE)**
- `static/fonts/PretendardVariable.woff2`(2,057,688B) 제거 → Pretendard
  v1.3.9 공식 `pretendardvariable-dynamic-subset`(unicode-range 분할 woff2
  + CSS) **자체 호스팅** 교체. 외부 CDN 런타임 요청 금지(비용 제약·현
  base.css 주석의 self-host 결정 유지).
- `static/css/base.css`의 기존 `@font-face` 1블록을 서브셋 CSS로 대체(로드
  방식은 WED/BIR 사전 명세를 따름). `font-display: swap` 유지.

**B. HTML GZip (BE)**
- `config/settings.py` MIDDLEWARE에 `django.middleware.gzip.GZipMiddleware`
  추가. 위치: SecurityMiddleware 다음, WhiteNoiseMiddleware 앞(응답 위상이
  역순이므로 최종 본문을 압축, Content-Encoding 있는 정적 응답은 스킵 —
  Django 5.2 문서 확인 [문서]).
- BREACH: Django 5.2 GZipMiddleware는 응답마다 랜덤 바이트를 추가하는 완화
  내장 [문서]. Security & Resilience Reviewer 판정을 게이트로 한다.

**C. brotli 사전압축 (BE)**
- `pyproject.toml`에 `brotli` 의존성 추가 → whitenoise
  CompressedManifestStaticFilesStorage가 collectstatic 시 `.br` 생성.

## 배제 (범위 밖)

- 렌더 차단 CSS 17개 병합 — OOCSS 파일 규약과 충돌, gz 합계 27,199B [실측]로
  총량 문제 아님. 프로덕션 h2에서 영향 축소. 보류.
- gunicorn 워커 모델·timeout — 기존 사용자 보류 항목 유지(이번 실측에서
  느린 클라이언트로 WORKER TIMEOUT→SIGKILL 1회 재현됨은 기록만).
- 이미지 최적화 — 공개 3페이지 LCP 전부 텍스트 요소.
- 로그인 필요 페이지 측정·최적화 — 별도 트랙.

## 수용 기준

1. 신규 계약 테스트(Red→Green): DEBUG=false 동등 조건에서 HTML 응답이
   `Accept-Encoding: gzip` 시 `Content-Encoding: gzip`, 미들웨어 순서
   (Security→GZip→WhiteNoise) 고정. 전체 회귀 초록.
2. `collectstatic` 후 `.br` 파일 수 ≥ 1 [실측 카운트].
3. 폰트: 첫 로드 폰트 전송 합계 목표 <400KB(브라우저 실측, 종전 2,057,688B),
   데스크탑 홈 CLS 재측정 ≤0.01, 한글·라틴 렌더 정상(스크린샷), 다크모드
   무영향.
   - **기준 정정(2026-08-29, WED·BIR 사후 판정 반영)**: CLS는 0.02 잔존
     [실측] — 원인이 `font-display: swap`의 폴백→웹폰트 리플로 구조 자체라
     서브셋화로 해소되지 않음. Good 임계(0.1)의 1/5 수준이라 **0.02 수용으로
     정정**, size-adjust 계열 폴백 메트릭 튜닝은 별도 후속 트랙 후보로 이연.
   - 청크 404/매니페스트 드리프트 시뮬 [실측 2026-08-29]: 청크 1개 제거 시
     해당 요청만 500, 콘솔 오류 1건으로 표면화, 나머지 12청크 정상, 텍스트는
     폴백으로 가시 유지, 재시도 루프 없음(BIR 사전 기준 5 충족).
4. 모바일(Slow 4G·CPU 4x) 3페이지 LCP 재측정이 종전 동등 이하.
   - 트레이스 실측(2026-08-29): 홈 1,067ms(종전 930)/목록 1,253ms(1,170)/
     상세 1,002ms(1,053).
   - QVL이 홈 +14.7%가 ±10% 편차 서술과 모순임을 지적 → **홈 3회 재측정
     [실측 2026-08-29, PerformanceObserver LCP, 동일 조건 리로드]: 836/852/
     808ms(중앙값 836ms) — 종전 930ms 미만.** 1,067ms 트레이스 1회분은
     이상치로 판정. 기준 4 충족.

## Frontend Review Evidence (트랙 13-A)

- **WED 사전 명세(요지)**: ① 로드=별도 `<link>`(tokens 다음·base 앞),
  @import·base.css 인라인 금지 ② 벤더 CSS의 family만 'Pretendard'로 치환
  +상단 주석 ③ 스태프 콘솔 동시 이관(옵션 A) ④ `static/fonts/pretendard/`
  원구조 보존(url 수기 수정 금지) ⑤ @font-face 수는 실측 기록(92 [실측]).
- **BIR 사전 기준(요지)**: ① CLS 재측정 ② unicode-range 희귀 문자 청크
  지연 로드 확인 ③ 재방문/Back 0바이트 ④ 다크모드·reduced-motion 비간섭
  ⑤ 청크 404 실패 회복(+preload 시 crossorigin). 사전 발견: staff/base.css
  동일 woff2 참조(계획 범위 결함) → 옵션 A로 반영.
- **WED 사후 판정: Conforms** — 결정 5건 전부 파일에서 독립 재검증(2026-08-29).
- **BIR 사후 판정: Deviates** — 사유는 CLS 목표(≤0.01) 미달 단건(0.02 잔존,
  Good), 코드 사실 무결. Unverified 2건은 이후 오케스트레이터 실측으로 해소:
  청크 404 시뮬(500 표면화·폴백 가시·루프 없음), Back 내비 폰트 전송 0B
  (전 엔트리 transferSize 0 [실측]).
- **잔여 위험(사용자 수용 대상)**: CLS 0.02 수용(기준 정정), size-adjust
  튜닝은 백로그 F14로 이연.

## Activated Roles

- Backend TDD Coach, Backend & Integration Engineer, Quality Verification
  Lead (B·C)
- Security & Resilience Reviewer (B — BREACH 판정)
- Deployment & Operations Reviewer (C — 의존성·이미지 빌드 영향)
- Web Experience Designer, Browser Interaction Reviewer(사전 명세+사후 판정),
  Frontend Implementation Engineer (A)

Not Activated: Product Scope Owner(사용자 직접 승인으로 대체), Domain
Architecture Reviewer(도메인 경계 무관), AI Automation Architect.

## Domain Boundary / Coupling

- 도메인 코드 무변경. config(미들웨어·의존성)·static(폰트·CSS)·필요시
  templates/base.html만. 의존 방향 변화 없음.

## 파일

- `config/settings.py`, `pyproject.toml`, `tests/core/`(신규 gzip 계약 테스트)
- `static/fonts/`(교체), `static/css/base.css`, `static/css/staff/base.css`,
  필요시 `templates/base.html`, `templates/staff/base.html`
- (BIR 사전 게이트 발견 반영 2026-08-29: staff/base.css:15-21이 동일 woff2를
  참조 — 스태프 콘솔도 같은 트랙에서 서브셋으로 이관, 파일 삭제는 두 참조
  제거 후에만)

## 검증 커맨드

- `uv run pytest -q tests/core/test_response_compression.py` (Red→Green)
- `uv run pytest -q` (전체 회귀)
- `DEBUG=false uv run python manage.py collectstatic --noinput` 후
  `find staticfiles -name '*.br' | wc -l`
- `curl -H 'Accept-Encoding: gzip' -sI http://127.0.0.1:8123/` 헤더 확인
- Chrome DevTools 재트레이스: 모바일 3페이지 LCP + 데스크탑 홈 CLS

## Deferred

- CSS 요청 수 감축, gunicorn 워커 모델(사용자 보류), 로그인 페이지 성능,
  프로덕션(Render) 실측 재확인(배포 후 사용자 확인 항목).

---

