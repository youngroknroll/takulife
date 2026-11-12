# 트랙 18: 하네스 — 오케스트레이터 계약·리뷰 선행 보고·어댑터 정비·숫자 태그 훅 (2026-09-03)

> 배경: 사용자 지적 "검토마다 찾아지는 오류가 너무 많다 — 하네스 설계를
> 검토하자". 진단: 이번 세션 오류 9건 [실측, 세션 기록] 중 8건이
> 오케스트레이터(메인 세션) 1차 산출물이고 리뷰 역할이 전부 잡았다. 원인은
> 확인 가능한 사실을 확인하지 않고 서술한 것이며, AGENTS.md 1,123행
> [실측 `wc -l`]에 11개 역할 계약은 있지만 오케스트레이터 계약은 없다
> [코드 `rg orchestrat` 5건 전부 다른 의미]. 같은 패턴이 메모리 4개
> 트랙 기록과 AGENTS.md "Numbers In Documents" 절에 반복된다.
> Claude Code 2.1.259 스펙 확인 [문서 code.claude.com/docs/en/sub-agents.md]:
> `model` ID 직접 지정·`effort` 필드 유효, `MultiEdit` 도구 미존재(스폰
> 실패는 재현 안 됨 — 조용히 무시됨 [실측 스폰 1회]), 검토 역할 도구
> Read·Grep·Glob 3개 확인 [실측 스폰 1회].
> 사용자 승인(2026-09-03): 제안 1·2·3·5 진행, 4(역할 메모리)는 미승인.

## 승인 범위

1. **AGENTS.md `## Orchestrator Contract` 절 신설**(Prime Directives 바로
   뒤). 규칙: 부정 주장은 저장소 전수 `rg` 출력 없이 쓰지 않는다 / 채팅
   보고·브리프의 숫자도 Numbers 규칙(단위·출처 태그·재현 명령) 적용 /
   산술은 도구로 계산 / 경로·테스트 위치는 존재 확인 후 기재 / 권고 전
   `prompt_plan.md` Deferred·메모리의 사용자 보류 기록 검색 / 서브에이전트의
   사실 주장(파일:줄)은 채택 전 재확인, 리뷰어 간 불일치는 실측으로 판정.
   "Numbers In Documents" 절에 채팅 보고·브리프 적용 문장 1줄 추가.
2. **리뷰 선행 보고**(같은 절): 검토가 필요한 판정·계획은 활성 리뷰
   역할을 먼저 돌리고 통합본만 사용자에게 보고한다. 1차 판정 단독 보고
   금지. CLAUDE.md Working Method에 1줄 참조 추가(200행 한도 유지 [문서
   CLAUDE.md 서두]).
3. **어댑터 11개 정비**(`.claude/agents/` [실측 `ls` 11파일]): 구현 역할
   2개 [코드 `tools:`에 Bash 있는 파일] `tools:`에서
   `MultiEdit` 제거 / "Read `AGENTS.md`" 전체 읽기를 역할별 필요 절 목록으로
   교체 / 반복 브리프 지시를 본문으로 이관 — 보고는 한국어·비유 금지·
   숫자는 단위+출처 태그, 브리프의 사실 주장은 미검증으로 취급해 소스로
   재확인, 검토 역할은 Bash 없음을 명시(테스트 결과 주장 금지), 구현
   역할은 pytest 실행 금지(실행·판정은 오케스트레이터 단독)와 진행 파일
   규약(`/tmp/claude-progress/<슬러그>`).
5. **숫자 태그 훅** `.claude/hooks/plan-number-tag-guard.sh`(PreToolUse,
   matcher `Edit|Write`, 대상 `prompt_plan.md`만): 새로 들어가는 텍스트의
   단락(빈 줄 구분 블록) 안에 "2 이상 정수 + 수량 단위(건·개·회·행·줄·
   쿼리·초·ms·B·바이트·명·토큰·%·배·곳·번·파일·워커·스레드·연결)"가
   있는데 같은 단락에 `[실측]`/`[코드]`/`[계산]`/`[문서]`/`[대시보드]`
   태그가 없으면 exit 2로 차단하고 위반 줄을 stderr로 돌려준다. 0·1은
   면제(설계 서술 "1회"). `.claude/settings.json`에 등록. 기존 훅 3개
   [실측 `ls .claude/hooks`]와 같은 python3 heredoc 형식.

## 배제 (범위 밖)

- 제안 4 역할별 `memory: project` 도입(미승인, 별도 결정).
- 훅의 `docs/*.md` 확장(Numbers 규칙은 문서 전반에 구속이지만 이번엔
  `prompt_plan.md`만 — 실사용 후 확장 판단).
- Bash `cp`/heredoc으로 `prompt_plan.md`를 통째로 바꾸는 우회 차단(이번
  세션 트랙 17 v1·v2 작성이 이 경로였다 — 알려진 공백으로 기록, 훅은
  Edit/Write 도구만 본다).
- AGENTS.md 본문 슬림화·재구성(절 지정 읽기로 대체).

## 수용 기준

- AGENTS.md 신설 절이 승인 범위 1·2의 규칙을 전부 담고, 다른 절은 Numbers
  1줄·CLAUDE.md 1줄 외 무변경(`git diff --stat`).
- 어댑터 11개 프론트매터 유효(name/description/tools/model/effort/color),
  `MultiEdit` 0건(`rg MultiEdit .claude/agents` 빈 출력), 각 파일이 필요
  절 목록과 이관 지시를 포함. 스폰 확인 1회(도구 목록 자가 보고).
- 훅: 샘플 페이로드로 차단 케이스(태그 없는 "26쿼리")·허용 케이스(태그
  있음 / 0·1 / 다른 파일 / 단위 없는 숫자 / 파싱 불가 JSON) 각각 exit 코드
  실측. settings.json이 유효 JSON.
- 회귀: `uv run pytest -q` 0 failures(주석 언어 가드 등 기존 가드 통과).
- 리뷰: DOR(훅·settings)·QVL(수용 기준 매핑) 검토 후 통합 보고.

## Activated Roles

- Backend & Integration Engineer ×2(병렬: A=AGENTS.md·CLAUDE.md·어댑터,
  B=훅·settings) — 문서·설정 구현.
- Deployment & Operations Reviewer — 훅 동작·settings 등록 검토.
- Quality Verification Lead — 수용 기준-증거 매핑.

Not Activated: 코치(백엔드 로직 없음, 훅은 기존 3개와 같이 pytest 대상
아님 — 정책 "자동 테스트=백엔드 로직만"), DAR·SRR·PSO·프론트·AI 역할
(해당 없음).

## 검증 커맨드

- `rg -n "MultiEdit" .claude/agents/` → 빈 출력
- `for f in .claude/agents/*.md; do sed -n '1,/^---$/p' $f; done` → 프론트매터
- `printf '%s' '<json>' | .claude/hooks/plan-number-tag-guard.sh; echo $?` ×6 케이스
- `python3 -c "import json;json.load(open('.claude/settings.json'))"`
- `uv run pytest -q`

## Deferred

- 역할 메모리(제안 4) / 훅 `docs/` 확장 / Bash 우회 차단.

## 롤백

훅은 settings.json 항목 삭제로 즉시 해제. 문서·어댑터는 커밋 revert.

---

