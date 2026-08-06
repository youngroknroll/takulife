# 직접 등록(PersonalEntry) API 계약

**Current fact.** `PersonalEntryDetailView`는 2026-07-30부터 `PATCH`를 받는다
(PR #251). 그 전에는 `RetrieveDestroyAPIView`라 **수정 경로가 아예 없었다.**

```
GET    /api/personal-entries/<pk>/   조회
PATCH  /api/personal-entries/<pk>/   부분 수정   ← 신설
DELETE /api/personal-entries/<pk>/   삭제
PUT                                  미허용
```

## Decision — PUT을 뺀 이유

`http_method_names = ["get", "patch", "delete", "head", "options"]`로 막았다.
전체 교체가 허용되면 부분 수정이 **언급하지 않은 필드를 비운다.** 같은 파일의
`CollectionItemDetailView`가 이미 같은 이유로 같은 패턴을 쓴다.

## Guardrail — `client_token`을 다시 열지 마라

PATCH를 여는 순간 **멱등 키가 함께 열렸다.** `client_token`은 모델에서
`editable=False`지만 `PersonalEntrySerializer`가 **명시 선언**해 그 설정을 덮는다.
실측했다 — PATCH 페이로드의 토큰이 저장값을 그대로 덮어썼다.

그러면 PR #246이 막았던 **재시도 중복 생성이 다시 열린다**: 토큰이 바뀐 뒤
원래 요청이 replay되면 유니크 제약에 걸리지 않는다.

`PersonalEntryUpdateSerializer`가 `client_token = None` + `Meta.fields` 제외로
**구조적으로** 막는다(`CollectionItemUpdateSerializer`와 동일 방식).
**수정 직렬화기에 필드를 추가할 때 이 배제를 깨뜨리지 마라.**

생성(POST)은 영향이 없다 — `PersonalEntryListCreateView`가 여전히
`PersonalEntrySerializer`를 직접 쓴다.

## Known gap — 사용자는 아직 이 API에 도달할 수 없다

**수정 화면이 없다.** 라우트 자체가 없고, 목록 행의 액션은 찜·일정·`＋ 기록`·
공식 제보·삭제 다섯 개뿐이다. 작성(`/archive/personal/new/`)과 목록만 존재한다.

따라서 이 항목이 존재하는 이유인 **데이터 소실 경로는 실질적으로 아직 열려 있다** —
장소명 오타를 고치려면 삭제뿐이고, `personal_entry` FK가 `EventInterest`·
`UserEventStatus`·`VisitRecord` 세 곳에서 `CASCADE`라 그 장소에 딸린 방문 기록과
사진이 함께 사라진다. (삭제 경고 문구는 정확히 있다 —
`static/js/pages/personal_entries.js`.)

화면은 신규 페이지라 프론트 이중 게이트 대상이고, **시안 재작업 중이라
새 시안 이후로 미뤘다**(2026-07-30 사용자 결정). 지금 지으면 두 번 짓는다.

## 공식 제보와의 관계 — 제약 없음

제보(`web/promotion.py`)는 제출 시점에 `title`·`category`·`work_title`·
`location_name`·`region`·`memo`를 **드래프트로 복사한다.** 따라서 제보 후 항목을
수정해도 검수 중인 드래프트와 어긋나지 않는다. 이 방향으로 PATCH를 제한할 이유가 없다.
