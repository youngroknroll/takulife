# Event Operations Criteria

행사 등록·검수 운영 기준. 2026-07-14 0단계 배포 기반 계획서(이하 "0단계
계획서" — 원문서는 2026-08-29 문서 정리로 삭제) T8, 기획서 §14 행사 공급 절을
기준으로, 실제 드래프트
검수 화면·모델 필드와 대조해 작성. 서버의 행사 필드 LLM 추출과 자동 승인은
비용·품질 정책상 비활성 상태다. 개인 맥의 로컬 에이전트가 새 수집처만 찾는
별도 목표 계약은 승인됐지만 아직 구현되지 않았다(아래 §4).

## 1. 주간 운영 목표

**초기 제안, 실측 후 조정** — 아래 수치는 검증된 실측치가 아니라 초기 서울·
수도권 기준의 제안값이다. 첫 4주 운영 후 실제 유입·전환 데이터로 재조정한다.

- **주간 신규 등록 5건 이상**: 매주 최소 5건의 새 행사(`events.Event`,
  `official_url` 유일)를 신규 검수·공개.
- **유효 재고 15건 이상**: 임의 시점에 종료되지 않은(`end_date` 경과 전, 또는
  `end_date` 미상이면 `start_date` 기준) 공개 행사가 상시 15건 이상 유지.
- **핵심 카테고리 커버리지**: `Event.category`(자유 텍스트, `events/models.py:12`)
  기준 주요 서브컬처 카테고리(전시·팝업·오프라인 이벤트 등, 최종 분류는
  스태프 콘솔 운영 중 확정)에서 매주 최소 1건씩은 신규 등록되도록 우선순위를
  둔다. 특정 카테고리가 2주 이상 공백이면 해당 카테고리 소스를 우선 조사한다.

이 수치는 목표치이지 하드 게이트가 아니다. 미달 시 원인(소스 부족·검수
지연·품질 미달 반려 다수 등)을 파악해 다음 절차에 반영한다.

## 2. 행사 데이터 필수 품질 기준

검수 화면(`drafts/serializers.py`의 `EventDraftSerializer`)이 노출하는 필드
기준. 실제 공개(`drafts/services.py:approve_draft`)는 `create_published_event`를
호출하며, 아래 중 **필수(하드 게이트)** 항목이 비어 있으면 승인 자체가
서비스 레이어에서 예외로 거부된다.

| 필드 | 드래프트 필드 | 공개 시 매핑 | 게이트 |
|---|---|---|---|
| 공식 URL | `source_url` | `official_url`(`events.Event`, unique) | **필수** — 비어 있으면 `DraftPublicationMissingOfficialUrlError`. 중복 URL은 `DraftPublicationDuplicateError` |
| 제목 | `extracted_title`(비면 `raw_title` 폴백) | `title` | **필수** — 결과적으로 빈 제목이면 `DraftPublicationTitleError` |
| 기간 | `extracted_start_date`/`extracted_end_date` | `start_date`/`end_date` | 권장 — 모델상 `null=True, blank=True`라 시스템이 강제하지 않음. 검수자가 원문에서 기간을 확인하지 못했다면 반려하거나 보류하는 것을 운영 기준으로 삼는다 |
| 장소 | `extracted_location_name`, `extracted_region` | `location_name`, `region` | 권장 — 위와 동일하게 시스템 비강제, 운영 기준으로 확인 |
| 작품 | `extracted_work_title` | `work_title` | 권장 |
| 카테고리 | `extracted_category` | `category` | 권장 — §1 커버리지 집계 기준이 되므로 가능한 채운다 |
| 요약 | `extracted_summary` | `summary` | 선택 |

검수자는 시스템이 강제하지 않는 "권장" 항목도 **기간·장소가 비어 있으면
원칙적으로 승인하지 않는다** — 이용자에게 노출되는 최소 정보 기준으로 운영
기준을 시스템 게이트보다 보수적으로 잡는다.

## 3. 재검수 주기

- **만료 행사 처리**: `end_date`(또는 기간 미상 시 `start_date`) 경과 행사는
  주 1회 스태프 콘솔에서 확인해 상태를 정리한다(비공개 전환 여부는 스태프
  콘솔 운영 절차에 따름 — 이 문서는 등록·검수 기준만 다룬다).
- **일정 변경 감지 시 재검수**: 이미 공개된 행사의 원문 소스(`official_url`)가
  기간·장소를 변경했다고 확인되면, 해당 행사를 재검수 대상으로 표시하고
  변경사항을 반영한다. 0단계에서는 이 감지가 수동(운영자가 소스를 재방문해
  확인)이며, 자동 변경 감지는 범위 밖이다.

## 4. LLM 사용 경계

### 4.1 서버 행사 필드 추출

- 초안 파이프라인은 `create_draft_from_url`에서
  `settings.DRAFT_LLM_EXTRACTION_ENABLED`(`config/settings.py`, 현재
  **`False`로 고정**)가 켜진 경우에만 LLM 추출(`extract_event_fields_llm`)을
  사용하고, 꺼져 있으면 휴리스틱 추출로 폴백한다(`drafts/services.py`).
- 이 플래그는 **비용 정책(유료 LLM API 사용 불가, 2026-07-04 확정)에 따라
  현재 OFF로 유지**되며, 0단계 계획서 §10(범위 밖)에도 "LLM 추출 프로덕션
  활성화(비용 정책상 OFF 유지)"로 명시돼 있다.
- LLM이 켜지더라도 **후보(초안) 생성까지만** 수행한다. 승인(`approve_draft`)은
  항상 스태프의 명시적 조작이며, 자동 승인 경로는 존재하지 않는다 —
  `EventDraft.ReviewStatus`는 `pending`/`approved`/`rejected` 3상태이고
  전이는 스태프 액션(`drafts/services.py`의 승인/반려 함수)으로만 발생한다.

### 4.2 로컬 에이전트 수집처 탐색

- 2026-08-20 승인된 목표 계약이며, `local_runner/` 패키지와 서버 러너 경계가
  PR #299·#301로 머지됐다(2026-08-24 main 기준 구현 완료).
- 개인 맥이 켜져 있을 때만 로컬 Claude Code 러너가 새 수집처와 표본 행사
  URL을 제안한다(현재 구현은 Claude Code 어댑터 1개). 행사 제목·날짜·장소·
  요약은 모델이 채우지 않는다.
- 서버가 후보를 URL 안전성, `robots.txt`, 콘텐츠 유형·크기, 목록 파싱과 규칙
  기반 canary로 다시 검증한다. 통과한 소스만 활성화하고 기존
  `discover_drafts`가 `EventDraft(PENDING)`을 만든다.
- 로컬 러너는 프로덕션 DB 자격을 갖지 않고 서버를 폴링하는 아웃바운드 연결만
  사용한다. PaaS에 LLM API 키나 에이전트 런타임을 추가하지 않는다.
- 공식성의 완전 자동 판정은 불가능하므로 모든 결과는 계속 관리자 검수 전
  `PENDING`에 머문다. 자동 게시에는 이 경계를 재사용할 수 없다.
- 상세 목표 계약과 보안·실패 처리는
  `docs/BE/draft-source-agent-discovery.md`가 소유한다.

## 5. 측정

- **행동 이벤트**: PR-0e(0단계 계획서 §8)가 도입한 `core.analytics`가
  `event_list_viewed`, `event_searched`, `event_detail_viewed`,
  `event_interested`, `event_planned`, `event_marked_visited` 등 13종을
  기록한다(`core/models.py`의 `AnalyticsEvent.EventName`). 행사 공급이 실제 발견·
  관심으로 이어지는지는 이 이벤트들(특히 `event_list_viewed`,
  `event_detail_viewed`, `event_interested`)의 주간 추이로 판단한다.
- **스태프 대시보드 집계**: `staff/views/__init__.py`의 `dashboard` 뷰가
  `core.analytics.distinct_user_key_count_since`/`event_name_counts_since`로
  주간 활성 사용자 수·이벤트별 카운트를 집계해 노출한다(`weekly_active_user_count`,
  `weekly_event_count`). §1의 주간 목표 달성 여부와 별개로, 이 집계로 공급된
  행사가 실제로 소비되고 있는지 함께 확인한다.
- 개인정보 원칙(후기·메모·사진 URL·이메일 미저장, 가명 사용자 키)은
  `core/analytics.py`의 `FORBIDDEN_CONTEXT_KEYS`·`pseudonymous_user_key`로
  이미 강제되며, 이 문서의 운영 기준은 그 위에서 동작한다 — 별도의 예외를
  두지 않는다.
