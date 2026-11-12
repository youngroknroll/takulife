# 트랙 15: 백엔드 구조 정리 + 빈 PATCH 결함 수정 (2026-08-29)

> 배경: 사용자 요청 "Tidy First·Clean Code·Clean Architecture 기준 백엔드
> 검토 및 개선". DAR 3건 병렬 검토(archive / staff·accounts·core /
> drafts·events, 2026-08-29) 결과: 의존 방향·경계는 계약 테스트 37건이
> 이미 강제, 뷰→서비스 위임 관례 일관 — 교과서식 계층 도입은 3개 리뷰
> 모두 과설계로 기각. 실행 대상은 국소 정리 6건 + 행동 결함 1건.
> 기반 실측(AST 스캔): 백엔드 11,696줄/117파일, >50줄 함수 19개(최장
> submit_candidate 203줄), 중첩 >4단 2개.
> 사용자 범위 승인(2026-08-29): 6건+1건 전부, 빈 PATCH는 400 거부 방향.

## 승인 범위

**T1~T6 구조 정리 (전부 행동 불변, Tidy First — 정리당 커밋 1개)**
- T1 archive/services.py: create/update_collection_item의 수량 불변식 검증
  7줄 중복(350-357·466-473) → 모듈 비공개 함수 추출.
- T2 staff/views/events.py: create(247-260)/edit(331-344) 예외→필드에러
  매핑 6절 중복 → 공유 함수 추출(문자열 보존 — 기존 테스트가 단언).
  toggle_publish의 유사 매핑(플래시 채널)은 통합 금지(DAR F2 판정).
- T3 drafts/candidate_validation.py: submit_candidate의 _save_failed_candidate
  호출부 12곳 보일러플레이트(고유 FailureStage 8종 — DAR의 "8회"는 종류
  수와의 혼동으로 판명 [실측], 코치 전수 교체 승인) →
  run_id/lease_token/cleaned 바인딩 클로저.
  **주의**: fetch_html 등 모듈 전역 이름 참조 유지(테스트 monkeypatch 대상).
- T4 drafts/fetching.py: fetch_html 응답 판독부(content-type·크기 상한
  청크 누적·디코딩) 추출로 중첩 6→4단. **SRR 게이트**: SSRF·TOCTOU 방어
  (IP 고정·매 홉 재검증)가 추출로 약화되지 않는지 diff 검토 Approve 필수.
- T5 archive/services.py: complete_visit_with_record의 경쟁 삽입 1회 재시도
  블록(631-663) → _ensure_visited_status류 추출.
- T6 events/querysets.py: order_for_public_listing 분기 본문 추출.

**S1 행동 결함 수정 (TDD Red→Green)**
- archive/views.py:382 UserEventStatusDetailView: status 없는 PATCH가
  무조건 serializer.save() 폴백으로 서비스 계층 우회(updated_at만 조용히
  갱신, 활동 로그 누락, 주석 의도 위반, 테스트 미보호 [실측]) →
  **400 거부**(사용자 결정). 구현 전 프론트 호출부에 빈 PATCH 전송 경로가
  없는지 실측 확인 — 있으면 보고 후 재결정.

## 배제 (범위 밖·기각)

- 유스케이스/리포지토리/검증 파이프라인 객체·atomic+감사로그 공용
  데코레이터·FetchSession 클래스화·setattr 루프화·파일 분할 — DAR 기각.
- CollectionItem 검증의 model.clean() 완전 이동(행동 변경, 이연 트리거 기록).
- staff 콘솔 Form/serializer 도입 — 이연(트리거: create/edit에 교차검증
  필드 추가 시. 위치: staff/views/events·drafts·home_categories 동시).

## 수용 기준

1. T1~T6 각각 개별 커밋 + 대상 테스트 슬라이스 초록, 최종 전체 회귀 초록
   (행동 불변 증명 — 새 테스트 없음이 정상, Tidy First).
2. 재측정 [실측]: submit_candidate 줄 수 감소, fetch_html 중첩 6→4,
   수량 검증·예외 매핑 중복 0.
   - **정정(2026-08-29 구현 후 재측정)**: fetch_html 중첩은 6단 잔존 —
     "6→4" 예상은 판독 경로만 추적한 오예측이었고, 리다이렉트 분기
     (if is_redirect→if not location)가 독립적으로 6단에 도달한다.
     승인된 추출(판독부)은 완료(함수 71→59줄, 판독 경로 중첩 해소).
     4단 달성은 스트림 본문 재구성 = SRR 재검토 필요한 추가 범위.
     **사용자 결정(2026-08-29): 현재 상태 수용** — 리다이렉트 분기 추출은
     이연(트리거: 이 함수를 다음에 수정할 때 같은 트랙에서 SRR 게이트로).
3. T4는 SRR Approve 없이는 머지 불가.
4. S1: Red(현재 빈 PATCH가 200) → Green(400 + 무기록). 프론트 빈 PATCH
   경로 부재 실측.
5. 전체 회귀 초록(기준 2325 [실측 2026-08-29], 착수 시 재측정).

## Activated Roles

- Domain Architecture Reviewer(검토 완료 — 발견·기각 근거 산출),
  Backend TDD Coach(리팩터 허용 범위·S1 계약), Backend & Integration
  Engineer(구현), Security & Resilience Reviewer(T4 한정),
  Quality Verification Lead(최종).
- Not Activated: PSO(사용자 직접 범위 결정), WED·BIR·FIE(프론트 무변경 —
  S1의 프론트 호출부 확인은 실측이지 편집 아님), DOR(배포 무관), AI AA.

## Domain Boundary / Coupling

- 모든 정리는 파일 내 추출 — 도메인 간 이동 없음, 의존 방향 무변경.
- S1은 archive 소유 API의 입력 계약 강화(서비스 우회 폴백 제거).
- 기록: staff→archive 결합은 관계 매니저 경유라 import 가드가 못 본다
  (승인된 방향, DAR F6) — 향후 리뷰어 오독 방지용.

## 파일

- archive/services.py(T1·T5), staff/views/events.py(T2),
  drafts/candidate_validation.py(T3), drafts/fetching.py(T4),
  events/querysets.py(T6), archive/views.py 또는 serializers.py(S1),
  tests/archive/(S1 신규 테스트)

## Test List

| ID | 시나리오 | 경계 |
|---|---|---|
| S1 | 상태_없는_PATCH는_거부되고_아무것도_기록하지_않는다 (400 + updated_at 불변 + 활동 로그 0건) | web |
| T1~T6 | 신규 테스트 없음 — 기존 슬라이스 초록 유지가 행동 불변 증거 | — |

## 검증 커맨드

- 정리별: `uv run pytest -q tests/<대상 도메인>/` 슬라이스
- S1: Red→Green 타깃 실행 → `uv run pytest -q tests/archive/`
- 최종: `uv run pytest -q` + AST 재스캔(기준 2 수치)
- 프론트 확인: `rg` static/js에서 해당 PATCH 호출부 페이로드 실측

## Deferred

- staff 콘솔 Form/serializer(트리거 위 기록), CollectionItem.clean() 이동,
  queries.py 검색 Q객체 공용화 기각 유지, events order 전략 계층 기각 유지.

---

