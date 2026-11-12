# 트랙 14: 렌더 차단 요청·네트워크 종속 트리 개선 (2026-08-29)

> 배경: 사용자 요청 "Lighthouse 렌더링 차단 요청 + 네트워크 종속 항목 트리
> 개선". 재측정(2026-08-29, 프로덕션 동등 서버 DEBUG=false·gunicorn 3워커·
> whitenoise·HTTP/1.1, 로그인 상태 홈):
> - 렌더 차단 CSS 20개(셸 17+페이지 3), gz 합계 58,029B / br 45,716B [실측]
>   — 트랙 13의 "gz 27,199B"는 폰트 CSS 분리·페이지 CSS 추가 전 수치라 무효.
> - 두 인사이트 모두 DevTools 엔진 추정 절감 0ms [실측](정보성 항목).
> - 최장 체인 HTML→폰트 CSS→woff2 청크 13개 3단. 모바일(Slow 4G·CPU 4x)
>   청크 완료 ~1,192ms·LCP 1,214ms / 데스크탑 무스로틀 170ms·LCP 219ms —
>   두 조건 모두 LCP가 폰트 스왑 리페인트 직후 [실측 상관, 인과는 사후 검증].
> - 사용자 범위 결정(2026-08-29): preload + CSS 감축 둘 다 진행.

## 승인 범위

**A. 폰트 청크 preload (FE)**
- `templates/base.html` 헤드, 테마 인라인 스크립트 뒤·tokens.css 링크 앞에
  `<link rel="preload" as="font" type="font/woff2" crossorigin>` 추가.
  crossorigin 필수는 docs/FE/font-delivery.md F4 가드레일.
- 대상: 공개 3페이지(홈/이벤트 목록/이벤트 상세) 교집합 청크만
  [실측 2026-08-29]: subset.78·79·81~91 = 13개. 상세 전용 subset.70은 제외
  (교집합 기준 — 개수 상한이 아니라 공통 사용 여부가 기준, WED 명세).

**B. 셸 CSS 병합 (FE+BE)**
- 관리 커맨드(신규): base.html DEBUG 분기의 폰트 CSS 제외 셸 16개
  (tokens→toast)를 **템플릿 순서 그대로, 파일 경계 개행 구분, 재정렬·minify
  없이** 병합해 `static/css/dist/shell.css` 생성. 산출물은 미커밋
  (.gitignore 등록). 커맨드는 base.html에서 링크 순서를 파싱하고, 소스
  누락·url( 발견 시 CommandError로 비정상 종료.
- 템플릿 분기: DEBUG=true → 기존 16링크 그대로 / DEBUG=false → 번들 1링크.
  분기 플래그는 core/context_processors.py의 기존 불리언 노출 패턴
  (email_delivery_enabled 등)으로 신설, settings 직접 참조 금지.
- `docker/entrypoint.sh`: collectstatic(9행) 이전에 커맨드 실행. `set -e`로
  실패 시 gunicorn 도달 전 기동 중단(F3의 "요청 시 500"보다 앞선 배포 단계
  표면화 — BIR 기준 4).
- 소스 CSS 파일 무변경(OOCSS 파일 규약 유지). 페이지별 extra_css 병합 제외.

## 배제 (범위 밖)

- 스태프 셸(base_staff.html — 스타일시트 5개뿐 [코드]) 번들·preload.
- 페이지별 CSS 병합, 폰트 CSS 인라인, django-compressor 등 신규 의존성.
- size-adjust 폴백 메트릭 튜닝(백로그 F14 유지).

## 수용 기준

1. 계약 테스트 Red→Green + 전체 회귀 초록. Test List 참조.
2. 렌더 차단 요청 인사이트 목록 20건 → ≤5건 [실측].
3. 네트워크 종속 트리: preload된 청크가 문서 직속 depth로 이동(폰트 CSS 뒤
   3단 체인에서 제외) [실측].
4. 모바일(Slow 4G·CPU 4x) 홈 FCP·LCP **전/후 각 3회** 측정(트랙 13 교훈:
   단일 트레이스 판정 금지): LCP 중앙값 개선 또는 유지. FCP 회귀 판정은
   임의 목표치 대신 전(before) 3회 산포 폭 초과 여부(BIR 기준 2).
5. preload 청크: 콘솔 "preloaded but not used" 경고 0건, Network에서 청크별
   요청 정확히 1회(crossorigin 누락 이중 다운로드 없음), 3속성 전부 존재.
6. 시각 무회귀: 다크모드 토글 스팟체크, 모달·토스트 표시 화면 스크린샷
   비교, Back 내비 캐시 재사용(전송 0B 근접).
7. 번들 소스 1개 임시 제거 시뮬: 커맨드 비정상 종료로 entrypoint가 gunicorn
   도달 전 중단 [실측].
8. 결정 규칙: 기준 4 실패(LCP 미개선 그리고 FCP 회귀) 시 preload 목록 축소
   또는 A 철회를 보고하고 사용자 판단을 받는다.

## Frontend Review Evidence (트랙 14)

- **리뷰 깊이: High** — BIR 판정(전역 셸 cross-page + entrypoint 기동 실패
  모드). WED는 Standard 판정, 상위 깊이 채택.
- **WED 사전 명세(요지)**: ① preload 위치=테마 스크립트 뒤·tokens 앞, F4
  3속성 ② 교집합 청크만(대역폭 경쟁 보수 대응, 교집합=13개면 그대로 13개)
  ③ 분기 마크업 debug 16링크/번들 1링크, 컨텍스트 프로세서 관례 준수
  ④ 병합=원문 순서 연결, 파일 경계 개행 1개 이상, 재정렬·셀렉터 통합 금지
  ⑤ 캐시 단위 16→1 수용(셸은 항상 동세트 로드, 배포당 동시 변경 흔함 —
  트레이드오프 기록) ⑥ 다크모드는 data-theme 기반·prefers-color-scheme
  0건이라 병합 영향 경로 없음 ⑦ 검증=3페이지 스크린샷.
- **BIR 사전 기준(요지)**: ① 청크 요청 1회·경고 0건 ② FCP 회귀=전 3회 산포
  폭 초과(새 임의 ms 목표 금지) ③ 순서 뒤집힘은 DEBUG=false에서만 재현되는
  조용한 회귀 — 계약 테스트 필수 ④ 커맨드 실패=배포 단계 중단(F3 개선)
  ⑤ 캐시·다크모드·reduced-motion 비간섭 ⑥ preload·템플릿 DEBUG 분기 모두
  저장소 최초 도입(grep 0건) — 이번 규율이 향후 기준선.
- **WED 사후 판정: Conforms** — 사전 명세 7건 파일 독립 재검증(2026-08-29).
  폰트 CSS 링크의 분기 뒤 이동은 @font-face 전용 파일(경합 @font-face 0건
  [코드]) 근거로 합리적 재량 판정. 스크린샷 4장 시각 회귀 없음.
- **BIR 사후 판정: Conforms** — 기준 ①~⑥ 합치, file:line 재검증. 런타임
  실측치(콘솔 0건·요청 1회·전체 회귀 수·transferSize 0)는 오케스트레이터
  실측을 코드 정합성으로 교차 확인(리뷰 세션 도구 제약으로 직접 재실행은
  아님을 병기). reduced-motion 실측 캡처는 없음(정적 추론 — 바이트 연결이라
  개입 경로 없음).
- **증거 공백 해소**: 라이트 모드 홈 캡처 추가(after-home-light.png,
  data-theme="light" 확인 후 촬영) — 라이트 팔레트·웹폰트·레이아웃 정상.
- **잔여 관찰(차단 아님)**: after 콜드 3회 산포 524ms(before 52ms) — 개선
  판정에는 영향 없음(after 최악 2,700ms < before 최선 3,096ms), 원인 규명은
  후속 후보로만 기록.

### 구현 결과 실측 (2026-08-29)

- 기준 1 ✅ S1·S1b·S2(계약)·S3a(unit)·S3b(web) Red→Green, S4 특성화 핀
  유지. 전체 회귀 **2323 passed** [실측]. 도중 회귀 3건(자기 참조 파싱,
  정적 참조 가드, 다중행 주석 가드) 발견 즉시 수정 후 초록.
- 기준 2 ✅ 렌더 차단 20건 → **5건**(번들+폰트 CSS+페이지 3) [실측].
- 기준 3 ✅ woff2 청크가 최장 체인에서 제거(문서 직속 preload). 최장 체인
  모바일 1,192→**638ms**, 데스크탑 170→**63ms** [실측].
- 기준 4 ✅ 모바일 콜드(ignoreCache) 3회 중앙값: FCP·LCP **3,100→2,672ms**
  (-428ms) [실측]. 회귀 판정 규칙 발동 불요(개선). CLS 데스크탑 0.02→0.01,
  모바일 0.00.
- 기준 5 ✅ 콘솔 preload 경고 0건, 폰트 요청 13건 각 1회(중복 없음)·전부
  200, 3속성 전부 존재 [실측].
- 기준 6 ✅ 라이트/다크 캡처 정상, 3페이지 스크린샷 회귀 없음, Back 내비
  폰트 13건 transferSize 0 [실측].
- 기준 7 ✅ toast.css 제거 시뮬: CommandError·종료 코드 1 → set -e로
  gunicorn 도달 전 중단 [실측]. 파일 원복 확인.
- 기준 8 — 발동 없음(개선).
- 번들 압축 부수 효과: 셸 16개 gz 합계 27,185B → 번들 gz 18,908B [실측].
### 추가분: preload 리터럴 13줄 → 상수+루프 (2026-08-29 사용자 승인)

- 배경: 사용자 지적 "반복 코드를 인젝션하는 방법은 어떤가" → 컨텍스트
  프로세서 상수 방식 승인. 근거: F4 3속성이 마크업 1곳으로 구조적 강제,
  목록 갱신=상수 한 곳.
- 상쇄 조건: 정적 참조 가드는 리터럴 {% static %}만 검사 → 변수화로 빠지는
  13경로를 **S5a**(FONT_PRELOAD_CHUNKS 전 경로 finders 실존, 가드 파일에
  배치)가 대체. **S5b**(프로세서 그대로-노출, unit)로 기존 프로세서 검증
  관례 유지. 둘 다 ImportError Red→Green [실측].
- 렌더 등가 [실측]: 전/후 preload 태그 시퀀스 diff 무차이(DEBUG 양쪽 13개,
  차단 링크 5/20 불변). 전체 회귀 **2325 passed**(2323+신규 2).
- 리뷰(깊이 Light): WED Conforms(위치·교집합 13개 유지, 시각 산출 없음이라
  렌더 diff로 충분) / BIR Conforms(반복 누락 위험 종결 판정).
- 잔여 관찰(차단 아님): ① 상수 값이 교집합과 어긋나게 편집돼도 자동 가드
  없음(주석·리뷰 의존) ② 향후 다른 변수형 {% static %} 도입 시 그때마다
  개별 실존 가드 필요(리터럴 가드는 구조적으로 못 봄).
- **QVL 완료 판정(2026-08-29): 완료 가능** — 8건 전부 passed, Failed 0.
  Unverified로 병기: 프로덕션(Render h2) 재측정(배포 후 사용자 확인),
  FCP 콜드 산포 확대 원인, reduced-motion 실측 캡처(정적 추론만).
  로컬 실측은 HTTP/1.1 — h2 운영에서는 요청 수 감축 효과가 더 작게
  나타날 수 있음을 병기.

## Activated Roles

- Web Experience Designer, Browser Interaction Reviewer(사전 완료·사후 예정),
  Frontend Implementation Engineer(base.html·분기 마크업)
- Backend TDD Coach + Backend & Integration Engineer(관리 커맨드·컨텍스트
  프로세서·계약 테스트·entrypoint)
- Deployment & Operations Reviewer(entrypoint 변경·기동 실패 모드)
- Quality Verification Lead(최종 증거 매트릭스)

Not Activated: Product Scope Owner(사용자 직접 범위 결정 2026-08-29), Domain
Architecture Reviewer(도메인 경계 무관), Security & Resilience Reviewer(신뢰
경계 무변경), AI Automation Architect(무관).

## Domain Boundary / Coupling

도메인 코드 무변경. core(커맨드·컨텍스트 프로세서)·config(프로세서 등록
1행)·templates·docker·tests/core만. 의존 방향 변화 없음. 커맨드↔템플릿
결합은 base.html 파싱 + 명시 경로 목록 대조 계약 테스트로 표면화.

## 파일

- `templates/base.html`, `core/context_processors.py`,
  `config/settings.py`(프로세서 등록 1행),
  `core/management/commands/`(신규 커맨드 + `__init__.py`),
  `docker/entrypoint.sh`, `.gitignore`(산출물 1행),
  `tests/core/test_shell_css_bundle.py`(신규)
- 문서: `docs/FE/css-delivery.md`(신규 가드레일), `docs/FE/font-delivery.md`
  (preload 가드레일 추가), `docs/deploy-runbook.md`(기동 순서),
  `docs/backlog.md`(해당 시)

## Test List (contract/web, Backend TDD Coach 주도)

| ID | 시나리오 | 경계 |
|---|---|---|
| S1 | 번들_커맨드가_셸_스타일을_템플릿_순서대로_병합한다 — 산출 바이트 == base.html 분기에서 파싱한 16경로(명시 목록과도 대조) 원문의 개행 구분 연결 | contract |
| S2 | 번들_대상_소스에_url_참조가_생기면_커맨드가_실패한다 — 상대 경로 재작성 불가 구조 보호(현재 0건 [실측]). 위반 주입은 --template/--static-root 옵션(기본값=프로덕션 경로)으로, 실 파일 오염 금지 | contract |
| S1b | 번들_커맨드는_자신의_산출_경로를_소스로_포함하지_않는다 — S3의 else 분기 링크가 정규식에 걸리는 자기 참조 차단(--output resolve 비교, S3 직전 Red-Green) | contract |
| S3a | DEBUG가_꺼지면_shell_css_bundled가_참을_반환한다 — 컨텍스트 프로세서 순수 함수(코치 분할: 더 낮은 경계 우선) | unit |
| S3b | 디버그가_꺼지면_셸_스타일은_번들_하나로_렌더된다 — 프로세서 등록+템플릿 분기 | web |
| S4 | 디버그가_켜지면_기존_개별_스타일이_순서대로_렌더된다 — **특성화 핀**(현행 통과가 정상, Red-Green 아님·분기 도입 후 회귀 가드) | web |

## 검증 커맨드

- `uv run pytest -q tests/core/test_shell_css_bundle.py` (Red→Green)
- `uv run pytest -q` (전체 회귀)
- 커맨드 실행 → `DEBUG=false ... collectstatic` → gunicorn 8123 기동 →
  DevTools 재트레이스(모바일 전/후 각 3회 + 데스크탑), 인사이트 2종 재분석,
  콘솔·Network 확인, 3페이지 스크린샷
- 번들 소스 1개 임시 제거 → 커맨드 비정상 종료 확인(수용 기준 7)

## Deferred

- 스태프 셸 번들·preload(동형 문제, 효과 소규모), 페이지 CSS 통합,
  size-adjust(백로그 F14), preload 규율의 이미지/스크립트 확대 적용.

---

