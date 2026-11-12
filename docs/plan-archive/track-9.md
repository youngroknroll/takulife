# 트랙 9: main→production 자동 배포 PR 워크플로 (2026-08-25)

> 배경: Render 배포를 `production` 브랜치 추종으로 전환하기로 결정.
> `production` 브랜치는 origin/main(`38567ca`)에서 생성·푸시 완료 `[실측:
> git ls-remote — main·production 동일 커밋]`. Render 대시보드의 추종 브랜치
> 변경(Settings → Build & Deploy → Branch)은 사용자 액션.
> 사용자 지시: "main의 PR 머지까지는 기존대로 진행하고, 머지 후 자동으로
> production행 main의 deploy PR이 생기게 할 것."
> 제약 실측: 저장소 Actions 설정 `can_approve_pull_request_reviews=false`
> `[실측: GET /actions/permissions/workflow]` — 이 상태로는 워크플로의
> GITHUB_TOKEN이 PR을 생성할 수 없어 설정 변경이 범위에 포함된다.

## 승인 범위

1. **`.github/workflows/deploy-pr.yml` 신설** — 트리거는
   `workflow_run`(workflows: ["CI"], types: [completed], branches: [main]).
   잡 게이트 `if: conclusion == 'success' && workflow_run.event == 'push' &&
   workflow_run.head_branch == 'main'` — **main이 브랜치 보호 없이도**
   `[실측: GET /branches/main/protection → 404 Branch not protected]`
   "CI 초록을 통과한 main"에서만 deploy PR이 생기는 것을 워크플로 자체가
   보장한다(DOR 차단 조건 1 해소). 로직: ①열린 main→production PR이 있으면
   종료(푸시가 기존 PR을 자동 갱신) ②`compare/production...main`의
   `ahead_by`가 0이면 종료 ③아니면 `gh pr create --base production --head
   main`. 토큰 권한은 `contents: read` + `pull-requests: write`로 최소화.
   concurrency 그룹으로 연속 실행 직렬화(cancel 없음). PR 제목·본문은 고정
   문자열/셸 변수만 — `run:` 블록에 `${{ github.event.* }}` 등 컨텍스트
   직접 보간 금지(SRR 완화 조건 2).
2. **저장소 Actions 설정 변경** — `PUT /actions/permissions/workflow`로
   `can_approve_pull_request_reviews=true`(Actions의 PR 생성 허용).
   `default_workflow_permissions=read`는 유지. **적용 순서: 트랙 PR의 main
   머지 이전에 PUT 실행**(첫 트리거가 권한 오류로 실패하지 않도록 — DOR
   차단 조건 2). 이 토글은 deploy-pr.yml 한정이 아니라 **저장소 전역
   설정**이며, 향후 main/production에 필수 승인 브랜치 보호를 도입하는
   시점에 재검토한다(SRR 완화 조건 1 — 런북에도 기록).
3. **`docs/deploy-runbook.md` 갱신** — 다음을 기록(DOR 차단 조건 3):
   (a) 배포 흐름: main 머지→CI 성공→자동 deploy PR→사람이 머지→Render 배포
   (b) 전환 순서: 워크플로+설정 머지→설정 GET 재확인→main→production 1회
   왕복 실증→Render 대시보드를 production 추종으로 전환
   (c) 자동 생성 실패 시 수동 fallback: `gh pr create --base production
   --head main`
   (d) deploy PR에는 CI 체크가 붙지 않는 것이 정상이며(GITHUB_TOKEN 생성
   PR은 워크플로 미트리거), 검증 근거는 main 커밋의 체크 상태
   (e) can_approve_pull_request_reviews 전역 설정 사실과 재검토 트리거
   (f) production에는 직접 push 금지(PR 경유만), 실패 감시는 Actions 탭과
   실패 메일.

## 배제 (범위 밖)

- render.yaml(Blueprint) 도입 — 추종 브랜치 정본은 Render 대시보드 유지.
- main·production 브랜치 보호 규칙 도입(공개 저장소라 무료 가용 `[실측:
  visibility PUBLIC]` — 도입 시 위 전역 설정 재검토와 묶어 별도 트랙).
- deploy PR 자동 머지, PAT 사용.
- deploy PR 위에서 CI 재실행 — workflow_run 게이트가 "main CI 성공 후에만
  생성"을 이미 보장하고, GITHUB_TOKEN이 만든 PR은 워크플로를 트리거하지
  않는다(생성 직후 체크 공백은 정상 — 런북 (d)로 안내).

## 수용 기준

- deploy-pr.yml이 YAML로 유효하고 permissions가 위 2개 스코프뿐이다.
- `run:` 블록 어디에도 `${{ github.event.* }}`·`${{ github.head_ref }}`류
  직접 보간이 없다.
- 설정 PUT 후 GET 재조회로 `can_approve_pull_request_reviews=true` +
  `default_workflow_permissions=read` 확인(머지 전 완료).
- 이 트랙 PR의 main 머지가 첫 실전 트리거 — 머지 후 CI 성공 시점에
  `gh pr list --base production`으로 deploy PR 자동 생성을 실측한다.
- 열린 deploy PR이 있는 상태의 재푸시에서 중복 PR을 만들지 않는다(로직
  검토 + 이후 머지에서 실측).
- 검토 역할 2인 판정: 조건부 승인 — 위 조건 반영으로 충족(구현 YAML은
  구현 후 재확인 항목).

## Activated Roles

- Deployment & Operations Reviewer — 워크플로·배포 흐름 설계 검토.
- Security & Resilience Reviewer — 토큰 권한·저장소 설정 완화 검토.
- Backend & Integration Engineer — 워크플로 파일·런북 구현.
- Quality Verification Lead — 증거-수용기준 매핑.

Not Activated: Backend TDD Coach(백엔드 로직 없음 — 자동 테스트는 백엔드
전용 정책이고 워크플로 YAML은 pytest 표면이 없음), 그 외 역할 해당 없음.

## Domain Boundary / Coupling

앱 코드 무접촉. `.github/workflows/` 신규 파일 하나로 ci.yml과 독립.
저장소 설정 변경은 GITHUB_TOKEN 기본 권한(read)을 바꾸지 않는다.

## 검증 커맨드

- `python3 -c "import yaml, ...safe_load"` — YAML 구문.
- `gh api repos/.../actions/permissions/workflow` — 설정 사전/사후.
- 머지 후: `gh pr list --base production --state open` — deploy PR 실측.

## Deferred

- render.yaml Blueprint 전환 여부(서비스 관리 방식 변경 — 별도 결정).
- main·production 브랜치 보호 규칙 도입 + can_approve_pull_request_reviews
  재검토(묶어서 별도 트랙).
- deploy-pr 실패의 알림 채널 연동(현재는 Actions 실패 메일로 충분).

## 롤백

deploy-pr.yml 삭제 + `can_approve_pull_request_reviews=false` 복원 +
열린 deploy PR 수동 close. Render는 대시보드에서 main 추종으로 되돌림.
