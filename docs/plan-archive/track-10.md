# 트랙 10: 테스트 시크릿 리터럴 제거 + 스캐너 가드 (2026-08-25)

> 배경: GitGuardian이 테스트 파일의 비밀번호로 PR 실패를 낸다는 사용자
> 보고. 실측: 최근 PR 27건 중 체크 실패는 PR #275뿐("1 secret uncovered")
> 이고 현재 열린 PR #315는 통과 — 다만 잔존 리터럴이 있는 한 그 라인을
> 건드리는 커밋마다 재탐지될 수 있고, 대시보드 인시던트도 남는다.
> 기존 규약: `tests/conftest.py` `valid_password`(secrets 런타임 조립,
> 독스트링에 명시) + ci.yml 저엔트로피 런타임 생성(PR #173). 그러나
> 규약이 조언 산문뿐이라 PR #275에서 또 어겨졌다(스태프 트랙 메모리에
> "저장소가 이미 푼 문제를 다시 만들었다"로 기록). CLAUDE.md 원칙:
> 결정적 제약은 산문이 아니라 가드로.
> 잔존 리터럴 실측(테스트 트리 전수 grep):
> ① `tests/drafts/test_draft_source_admin.py:11` `password="Aa1!strongpassword"`
>   — force_login만 쓰므로 비밀번호 자체가 불필요.
> ② `tests/core/test_settings_env.py` 49·65·78·89·100행 —
>   `postgresql://taku:taku@…` 형태의 자격증명 포함 URI 리터럴 5건
>   (GitGuardian URI-credential 탐지 유형).
> 범위 밖 확인: ci.yml `DATABASE_URL`·`POSTGRES_PASSWORD: taku`·
> docker-compose는 PR #280에서 위험 없음 판단으로 존치한 기존 결정 유지.

## 승인 범위

1. `tests/drafts/test_draft_source_admin.py` — `password=None`으로 전환
   (force_login은 사용 가능 비밀번호 불요, 저장소 기존 관례 문구와 일치).
2. `tests/core/test_settings_env.py` — 자격증명 URI 5건을 런타임 조립로
   전환: 비밀번호를 변수로 두고 f-string으로 URI를 조립, 단언은 그 변수와
   대조. 인코딩 복원 테스트(78행)는 인코딩된 조각을 변수로 분리해 동작
   검증 의미(%40→@, %23→#)를 유지. **검증 의미·테스트명·시나리오는
   변경하지 않는다.**
3. **가드 테스트 신설**(tests/core/, 기존 가드 테스트 관례를 따름) —
   tests/ 트리 소스에서 ①비밀번호류 kwarg/할당(`password=`)에 8자 이상
   문자열 리터럴 ②`://user:pass@` 자격증명 포함 URI 리터럴을 금지.
   기존 가짜 토큰 관례("runner-secret" 등, GitGuardian 통과 이력)는
   범위에서 제외해 오탐을 만들지 않는다. Red-Green: 가드를 먼저 작성해
   현행 리터럴 6건으로 Red 실측 → 1·2 수정 후 Green 실측.
4. 규약 문서화: `docs/BE/` 가드 문서(contract-guards.md)에 테스트 시크릿
   가드 항목 추가(무엇을 왜 막는지 + valid_password/런타임 조립 관례).

## 수용 기준

- 가드 테스트가 수정 전 트리에서 6건을 Red로 잡는다(실측).
- 수정 후 가드 Green + 변경 파일 대상 테스트 Green + 백엔드 전체 회귀
  Green(기준 2294 passed [실측 2026-08-25 트랙 8], 착수 시 재측정).
- tests/ 트리에 자격증명 URI·비밀번호 리터럴 grep 0건.
- 검증 의미 보존: test_settings_env의 각 테스트가 검증하던 파싱 동작이
  동일하게 단언된다(뮤테이션이 아닌 코드 검토로 확인).

## Activated Roles

- Backend TDD Coach — 가드 테스트 설계·Red-Green 체크포인트 검토.
- Backend & Integration Engineer — 구현.
- Quality Verification Lead — 증거 매핑.

Not Activated: Security & Resilience Reviewer(리터럴 제거는 위험 감소
방향 단순 변경, 새 신뢰 경계 없음), 그 외 역할 해당 없음. pytest 실행과
판정은 오케스트레이터 단독(에이전트는 편집만).

## 트랙 내 결함 발견 및 수정 (PR #316 GitGuardian 실측)

1차 구현 푸시 후 GitGuardian이 **5건 재탐지**(체크 fail) — 탐지기 실지형이
가드 설계 가정과 달랐다 `[실측: PR #316 체크런 output]`:
- `db_password = "taku"` 할당 4건(test_settings_env.py) — GG Generic
  Password는 **이름에 password가 포함되면(정확 일치 불요) 4자 값도** 잡는다.
- 가드 캐너리 문자열 안 `password = 'abcdefgh'` 1건 — GG는 원시 텍스트
  스캔이라 **문자열 상수 내부도** 잡는다(AST 문맥 무관).
- 반면 URL 경로 상수(`PASSWORD_CHANGE_URL = "/accounts/…"`)와 dict 폼
  데이터(`{"password": "definitely-wrong"}`)는 역사적으로 미탐지(수십 PR
  통과) — 가드가 이를 오탐하면 안 된다.

수정(같은 트랙 즉시 해소, 표준 규약):
1. 가드 패턴① 확장: 이름이 password를 **포함**(대소문자 무시)하는
   할당/kwarg + 4자 이상 문자열 상수. 예외: `/`로 시작(URL 경로).
   경계 테스트 8/7자 → 4/3자로 교체.
2. test_settings_env.py: `db_password = "taku"` 4건 → `secrets` 런타임
   생성으로 전환(리터럴 자체 소멸 — valid_password와 같은 철학).
   PASSWORD 단언은 생성값 변수와 대조(파싱 왕복 검증 의미 불변).
3. 가드 캐너리·단위 픽스처 문자열: 원시 텍스트에 `password=…'값'`·완전한
   자격증명 URI가 연속으로 남지 않게 조각 결합(.format/연결)으로 조립.
   기록된 픽스처 파일 내용 자체는 동일(가드 검출력 불변).
4. contract-guards.md 항목을 실측 지형으로 갱신.
5. **브랜치 히스토리 재작성**: GG는 PR의 커밋별 패치를 스캔하므로 수정
   커밋을 얹어도 기존 커밋의 탐지 라인이 남아 체크가 계속 fail —
   soft reset 후 클린 재커밋 + force-with-lease(이 브랜치는 PR #316
   전용, 공유 작업자 없음).

## Deferred

- GitGuardian 대시보드의 기존 인시던트 resolved 처리(사용자 액션,
  히스토리 잔존 리터럴은 재작성하지 않음).
- ci.yml·docker-compose의 로컬 전용 `taku` 자격증명(기존 존치 결정 유지).

---

