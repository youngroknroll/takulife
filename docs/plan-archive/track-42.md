# 트랙 42: production 대상 PR에서 CI `pull_request` 실행 제외 (2026-10-20) [v1 — DOR·TDD 코치·QVL 사전 검토 통합: DOR 같은 유형 결함 2건(deploy-pr.yml PR 본문 문장, 런북 production PR 규칙) 범위 편입, 코치 계약 핀 CI42-1, QVL AC2 전제조건·AC5 추가. 오케스트레이터가 DOR·코치 인용 줄을 소스로 재확인 [실측 sed·grep]]

> **출처**: 사용자 지시(2026-10-20) "소음을 없애는 방향으로 수정" — deploy PR(main→production)에 잡 0개 failure CI 실행이 남는 패턴.
> **기준선**: origin/main `5ef5fdde`(PR #392 머지) [실측 git]. 브랜치 `ci/skip-production-pr-ci`를 main에서 만든다.

## 실측 사실 (2026-10-20, 오케스트레이터)

- 원인: GitHub 문서 "Triggering a workflow" — `GITHUB_TOKEN`으로 만든·갱신한 PR의 `pull_request`(opened/synchronize/reopened)는 **승인 대기(approval-required)** 실행을 만든다 [문서 docs.github.com, context7]. #393 생성 직후 CI 실행 39416537865가 actor `github-actions[bot]`, 잡 0개, conclusion `action_required`로 생겼다 [실측 gh api]. 승인 없이 PR이 머지되면 failure로 남는다고 추정한다(과거 2건 형태 일치) [실측 gh api, 해석은 추정]. **정정(같은 날, 사후 DOR 잔여 지적 후 실측)**: 봇 failure 13건 전부 실행 updated_at과 해당 deploy PR closedAt 차이가 1초 이하 [실측 gh api run·pr 대조] — 추정이 아니라 측정된 사실로 확정. 위 "추정" 문장은 측정 전 기록으로 남긴다.
- 규모: `gh api "repos/youngroknroll/takulife/actions/workflows/ci.yml/runs?event=pull_request&branch=main" --paginate` → deploy PR에서 생긴 CI 실행 52건(2026-08-25~2026-10-20). 봇 actor: failure 13건·action_required 1건·success 3건. 사용자 actor: success 27건·cancelled 7건·failure 1건 [실측]. 사용자 actor 실행은 main 머지로 열린 deploy PR이 synchronize된 것으로, production 머지 결과 트리가 main과 같아 main push CI를 중복 실행한다 [실측 git: production의 고유 커밋은 deploy 머지 커밋뿐].
- 필터 기준: `on.pull_request.branches-ignore`는 PR이 **향하는(base)** 브랜치의 ref 이름과 맞춘다 [문서 docs.github.com workflow-syntax]. 필터로 건너뛴 워크플로의 체크는 Pending으로 남아 "필수 체크"가 있으면 머지를 막는다 [문서] — main·production 모두 브랜치 보호 404·룰셋 0개라 해당 없음 [실측 gh api].
- 선례: `tests/core/test_ci_command_policy.py`가 ci.yml 본문을 읽어 단언하는 계약 핀이다 [실측 rg].

## 승인 범위 (PR 1개)

1. `.github/workflows/ci.yml` `on.pull_request`에 `branches-ignore: [production]` + 이유를 적은 짧은 한국어 주석. `push: branches: [main]`은 그대로.
2. `docs/deploy-runbook.md` §7 "deploy PR에 CI 체크가 없는 것은 정상" 문단을 사실(승인 대기 실행이 생기던 것, 이제 필터로 생기지 않음, 검증 근거는 main push CI)로 정정.
3. 계약 핀 CI42-1(코치): 새 파일 `tests/core/test_ci_trigger_policy.py`, `test_CI_워크플로가_production을_향한_PR에서는_pull_request_트리거를_건너뛴다`. ci.yml 본문을 문자열로 잘라 `on.pull_request` 블록에 `branches-ignore`·`production`이 있는지 단언(선례 `tests/core/test_ci_command_policy.py`와 같은 방식). PyYAML은 drf-spectacular 전이 의존성일 뿐이라 쓰지 않는다 [실측 uv.lock]. 기대 Red: 현재 `pull_request:` 아래 키가 없어 AssertionError. 한계: 텍스트 계약만 증명하고 GitHub 서버 동작은 AC1·AC2가 증명한다.
4. (DOR, 같은 유형 결함) `.github/workflows/deploy-pr.yml` `gh pr create --body`의 "GITHUB_TOKEN으로 생성한 PR은 워크플로를 트리거하지 않으며" 문장을 사실대로 고친다. 새 deploy PR부터 반영된다.
5. (DOR, 같은 유형 결함) 런북 §7 "production에는 직접 push하지 않는다" 항목에 "production을 향하는 PR도 자동 생성 deploy PR(head=main)만 쓴다, 긴급 수정도 main을 먼저 거친다"를 명시 — 필터 뒤에는 production 대상 PR에 CI가 돌지 않기 때문이다.

## 제외 (사유)

- `branches: [main]`: 스택 PR(베이스가 기능 브랜치, 트랙 32 #363~#369 선례)의 CI까지 꺼진다.
- PAT·GitHub App 토큰으로 deploy PR 생성: main에서 통과한 CI의 중복 실행이 되살아난다.
- 이미 생긴 #393의 승인 대기 실행 39416537865: 정리 수단이 승인(=중복 실행)뿐이라 그대로 둔다. #393 머지 시 failure 기록이 마지막으로 남을 수 있다.
- (v0에 있던 "`deploy-pr.yml` 본문 비변경"은 DOR 검토로 철회 — 범위 4로 편입.)
- 두 번째 핀("push는 main")은 이미 Green이라 쓰지 않는다(코치).

## 수용 기준

- AC1: 이 트랙 PR(base=main)의 `pull_request` CI가 PR #392와 같은 잡 4개로 정상 실행된다(필터가 main 대상 PR을 막지 않음) [실측 gh run view 39412226313 잡 4개].
- AC2: 머지 후 main push CI 성공, 그리고 사용자 머지로 main이 움직여 #393이 synchronize될 때 #393에 새 CI `pull_request` 실행이 생기지 않는다(`gh api .../runs?event=pull_request&branch=main -q '.workflow_runs[0].id'`가 39416537865 그대로). **전제조건(QVL)**: 머지 직전 `gh pr view 393 --json state`가 OPEN이어야 한다 — #393이 먼저 닫히면 "새 실행 없음"은 아무것도 증명하지 않는다. 머지 직전 브랜치 보호·룰셋 0건도 재측정(DOR).
- AC3: `uvx --from actionlint-py actionlint` 0건.
- AC4: CI42-1 단독 실행 Red(AssertionError) → ci.yml 수정 후 Green → `uv run pytest -q` 전체 통과.
- AC5(QVL): 런북 §7과 deploy-pr.yml 본문에 "트리거하지 않는다" 주장이 남지 않는다(`rg -n "트리거하지 않" docs/deploy-runbook.md .github/workflows/deploy-pr.yml` 0건), 새 문장이 실측 사실(승인 대기 실행·필터)과 맞는다.
- 미검증으로 남는 것: 스택 PR(베이스가 기능 브랜치) CI 유지는 필터가 production만 제외한다는 구조로만 판단한다 [코드], 이번 트랙에 스택 PR이 없어 실측하지 않는다.

## 역할

- Activated: Deployment & Operations Reviewer(CI/CD 소유), Backend TDD Coach(ci.yml 계약 핀 판단), Backend & Integration Engineer(구현·문서), Quality Verification Lead(AC↔증거).
- Not Activated: PSO(제품 범위 무관), DAR(도메인 경계 무관), SRR(권한·토큰 무변경), WED·BIR·FIE(프론트 무관), AIA(무관).

## 검증

`uvx --from actionlint-py actionlint`, (테스트 추가 시) 대상 테스트 Red→Green 후 `uv run pytest -q`, PR CI 잡 확인(AC1), 머지 후 gh api 실행 목록(AC2).

## Deferred

- 없음(발견 시 같은 트랙에서 처리).

## 사후 기록 (2026-10-20, 오케스트레이터 — PR #394 오픈, 머지 승인 대기)

- 커밋: `36657b03` ci.yml 필터 + 핀 CI42-1, `75b6696a` deploy-pr.yml 본문, `0c3a621a` 런북 §7. 구현은 BIE, pytest·판정은 오케스트레이터.
- TDD: 대상 테스트 Red(AssertionError "pull_request 트리거에 branches-ignore 조건이 없다") → Green(1 passed). 변이 5종 전부 실패 판정 [실측 헬퍼 직접 호출, 파일 무변경].
- 회귀: `uv run pytest -q` → 3212 passed / 10 deselected / 98.15초 [실측]. actionlint 0건, deploy 스크립트 `bash -n` 통과, AC5 `rg` 0건 [실측].
- 사후 DOR: Conforms with residual — 잔여(런북 "실패로 남았다" 단정)는 봇 failure 13건 실측으로 해소, 문구 유지.
- 남은 것: AC1(PR CI 잡 확인), 머지 승인(사용자), AC2(머지 직전 #393 OPEN·브랜치 보호 재측정, 머지 후 최신 pull_request 실행 id 불변).
- **머지 (2026-10-21, 사용자 "머지 승인")**: 머지 직전 재측정 — PR #394 체크 5개 pass·CLEAN(AC1 충족, CI 실행 39419818186 잡 4개 pass), #393 OPEN head `5ef5fdde`, main·production 브랜치 보호 없음·룰셋 0개, 기준 최신 pull_request 실행 id 39416537865 [실측 gh]. 07:43:37Z merge commit `c139fa05`.
- **AC2 관찰(머지 직후)**: #393 head가 `c139fa05`로 이동(synchronize 발생)했는데 그 커밋의 실행은 CI push 39564017183 하나뿐, 최신 pull_request 실행 id 39416537865 불변 [실측 gh]. 대조: 수정 전 사람 머지 시 deploy PR 실행은 머지 6초 뒤 생성됐다(2026-09-20 실행 35514500839, #387 머지 13:46:44Z) [실측 gh]. main push CI 완료 후 최종 확인은 아래에 덧붙인다.
- **AC2 최종(2026-10-21)**: main push CI 완료 후에도 #393 OPEN head `c139fa05`, 최신 pull_request 실행 id 39416537865 불변, 머지 커밋의 실행은 CI push 39564017183과 Deploy PR workflow_run(skipped)뿐 [실측 gh] — **필터 동작 확인**. 단 main push CI 자체는 failure: 의존성 감사 잡이 새 어드바이저리로 실패(certifi 2026.5.20 PYSEC-2026-4320 → 2026.10.19, pillow 12.3.0 GHSA 8건 → 13.0.0) [실측 gh run view --log-failed]. 나머지 잡 3개 success. 이 트랙 변경과 무관하다 — uv.lock 마지막 변경은 `230c92f2`(PR #390), 하루 전 PR #394 CI의 같은 잡은 success [실측 git·gh]. pillow는 직접 의존성(`pyproject.toml:22`)이고 `events/image_validation.py`·archive `ImageField` 업로드 경로에서 쓴다 [실측 rg] → 다른 종류의 작업(메이저 상향, 보안 민감)이라 별도 트랙으로 분리, 사용자 결정.

---

