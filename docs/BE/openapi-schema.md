# OpenAPI 스키마·문서 엔드포인트

`/api/schema/`(drf-spectacular)·`/api/docs/`(Swagger UI) 배선의 핸드오프 필수
사실만 적는다. 작업 일지가 아니다 — 상세 경위는 `docs/pr-log.md`.

## 공개 결정

`/api/schema/`·`/api/docs/`는 전체 공개(무인증·무스로틀)로 배선했다 —
2026-08-16 사용자 결정. 스태프 전용 drafts API(`AdminEventDraft*`)의 존재·경로
구조가 스키마에 드러나는 것은 **수용된 잔여 위험**이다 — 실제 데이터는 여전히
`IsAdminUser` 뒤에 있고, 노출되는 건 엔드포인트 형태뿐이다.

## 가드레일 1 — `extend_schema_view` 키는 HTTP 핸들러명이다

이 저장소의 뷰는 전부 `ListCreateAPIView`·`RetrieveUpdateDestroyAPIView` 등
**`GenericAPIView` 계열**이지 `ViewSet`이 아니다. `extend_schema_view`의 키는
`list`/`create`/`retrieve`/`partial_update`/`destroy` 같은 ViewSet 액션명이
아니라 **`get`/`post`/`patch`/`delete`** 여야 한다.

⚠️ **틀린 키는 조용히 무시된다.** `spectacular --validate`도 경고하지 않는다
— 실제로 이 저장소에서 28곳 전부가 이 결함으로 조용히 무시됐고, Swagger UI에
`태그 없음`이 아니라 **URL에서 파생한 태그**(`collection-items` 등)로 떨어지는
형태로만 드러났다(브라우저 실측 전까지 자동 테스트가 못 잡음). 각 뷰가 실제로
노출하는 핸들러는 `http_method_names`를 확인해서 맞춰야 한다(예: `put` 미노출
뷰에 `put` 키를 넣지 않는다).

회귀 가드: `tests/core/test_openapi_schema.py`의
`test_공개_스키마의_모든_operation은_선언된_태그만_사용한다` — 선언된 태그
집합은 `settings.SPECTACULAR_SETTINGS["TAGS"]`에서 동적으로 파생하므로, 새
태그를 추가할 땐 `TAGS`에 선언만 하면 통과한다(하드코딩 없음).

## 가드레일 2 — 스키마 생성은 `get_queryset()`을 실행한다

drf-spectacular의 내성 검사는 뷰의 `get_queryset()`을 실제로 호출한다. 그
안에 부작용(분석 이벤트 기록 등)이 있으면 스키마를 생성할 때마다 그 부작용이
실행된다 — `events/views.py`의 `PublicEventListView`가 실제로 이 결함을 냈다
(스키마 생성 1회당 `AnalyticsEvent` 1행 커밋).

수정 패턴(선례): `getattr(self, "swagger_fake_view", False)` — 이 속성은
drf-spectacular가 내성 검사용 뷰 인스턴스에만 세팅한다. 부작용 호출을 이
가드로 감싸고, 쿼리셋 계산 자체는 조기 반환 없이 그대로 실경로를 태운다.

계약: 스키마 생성은 `AnalyticsEvent`를 기록하지 않는다
(`tests/core/test_openapi_schema.py::test_스키마_생성은_분석_이벤트를_기록하지_않는다`,
`django_db` 마커 필수 — `record_event`의 best-effort `except`가 마커 없이는
차단 예외를 삼켜 커밋 여부를 검증할 수 없다).

## 가드레일 3 — 공개 스키마는 `/api/` 프리픽스만

`config/openapi.py`의 `preprocess_exclude_non_api_paths`(`PREPROCESSING_HOOKS`)가
`/api/`로 시작하지 않는 엔드포인트를 스키마에서 제외한다 — 도입 당시
`/staff/drafts/bulk-approve/` 등 스태프 콘솔 DRF 뷰 4개가 공개 스키마에
새고 있었다(실측).

이 훅은 경로 문자열만 보므로 **새 비-`/api/` DRF 뷰는 자동으로 제외되고, 새
`/api/` 뷰는 자동으로 포함된다** — 훅을 다시 손댈 필요가 없다. 경로 완전성
계약(`test_스키마_생성시_등록된_API_경로가_모두_포함된다`)이 urlconf에서 직접
경로를 파생해 새 `/api/` 라우트 누락을 잡고, 프리픽스 계약
(`test_공개_스키마의_모든_경로는_api_프리픽스로_시작한다`)이 반대 방향(비공개
경로 유입)을 잡는다.

## 정적 자산 — Swagger UI는 sidecar 자체 서빙

`SWAGGER_UI_DIST`/`SWAGGER_UI_FAVICON_HREF`를 `"SIDECAR"`로 설정해
`drf_spectacular_sidecar` 패키지가 번들한 정적 자산을 쓴다 — 외부 CDN
요청 0건(비용·오프라인 규약). `collectstatic` 경유로 서빙되며, whitenoise
manifest 경로는 CI의 컨테이너 부팅 스모크(F3, `docker` 잡)가 이미 검증한다.

⚠️ **`collectstatic` 성공은 참조 파일의 존재만 보장하고 실서빙 내용까지
보장하지 않는다** — 배포 전 체크리스트에 `/api/docs/` 브라우저 확인 항목을
추가했다(`docs/deploy-runbook.md` §3-13).

## 미적용(의도) — `/api/schema/` 스로틀·캐시 없음

`/api/schema/`에는 별도 스로틀·캐시를 걸지 않았다 — 기존 익명 GET
엔드포인트(예: `/api/events/`)와 동일한 무스로틀 기준선으로 판정했다(보안
검토, 배포 차단 아님). 스키마 생성 비용이 실트래픽에서 문제로 드러나기 전까지
`docs/backlog.md` F 절에 유보 항목으로만 남긴다.

## Evidence

- 계약 테스트 6건: `tests/core/test_openapi_schema.py`.
- 전체 회귀: `uv run pytest -q` → **2155 passed** `[실측 2026-08-16]`.
- `uv run python manage.py spectacular --validate --fail-on-warn` → 통과(경고 0).
- 브라우저 실측: 37개 operation 전부 선언된 5개 태그(`core`/`events`/`drafts`/
  `archive`/`collection`) 소속, 한국어 `summary` 표시, Swagger UI 콘솔 오류 0건,
  외부 네트워크 요청 0건(sidecar 자체 서빙 확인).
