# `web/views` 패키지 계약

**Current fact.** `core/views/` 패키지(뷰 7모듈)는 2026-08-02
`web` 앱의 `web/views/` 패키지로 옮겨졌다(C4, 프레젠테이션 계층 분리 트랙).
`core/views/`는 더 이상 없다 — `core/views.py`는 `api_root`·`health`만 남은
단일 모듈로 남았다.

| 모듈 | 담는 것 |
|---|---|
| `__init__.py` (51줄 `[실측, wc -l]`) | **순수 재노출만.** 뷰 로직 0줄 |
| `_helpers.py` (178줄 `[실측]`) | 둘 이상의 그룹이 쓰는 범용 헬퍼 7개 |
| `events.py` (456줄 `[실측]`) | `home`, `event_list`, `event_calendar`, `event_detail` |
| `archive.py` (682줄 `[실측]`) | 상태·방문·직접등록·찜 뷰 9개 |
| `activity.py` (413줄 `[실측]`) | `activity_calendar` + 활동 전용 헬퍼·상수 |
| `collection.py` (427줄 `[실측]`) | 컬렉션 뷰 4개 + 카드 표시 헬퍼 + `SERIES_INK_*` |
| `account.py` (214줄 `[실측]`) | `mypage`, `delete_account` |
| `legal.py` (10줄 `[실측]`) | 법적 페이지 2개(`legal_privacy`, `legal_terms`) |

⚠️ `api_root`·`health`는 이 패키지에 없다. `system.py`는 이번 이동으로 사라지고
그 안의 법적 페이지 2개만 `legal.py`로 옮겨졌다 — `api_root`·`health`는 애초에
프레젠테이션 조립이 아니라 커널 관심사라 `core/views.py`에 그대로 남았다.

## Guardrail — 새 뷰를 추가할 때

1. **`__init__.py`에 뷰를 쓰지 마라.** 소유 모듈에 쓰고 `__init__.py`에는
   이름만 추가한다. `__all__`에도 넣어야 URL 모듈이 찾는다.
2. **`import *`를 쓰지 마라.** 서브모듈의 module-level 이름이 패키지
   네임스페이스에 얹히면, 테스트의 몽키패치가 "성공"하고 "통과"하지만
   실행 경로에는 닿지 않는 **조용한 무효화**가 생긴다. 명시 import만.
   ⚠️ **이 규칙만 자동 테스트가 있다** —
   `tests/core/test_architecture_boundaries.py`의
   `test_web_디렉터리_아래_모듈은_import_별표를_쓰지_않는다`. 아래 3·4번은
   **미강제** — 코드로만 지켜지고 기계 가드는 없다.
3. **`archive.py` → `collection.py`는 단방향이다.** 방문 상세가 굿즈 카드
   헬퍼(`_collection_item_row`, `_series_ink_classes`)를 쓴다.
   **`collection.py`에서 `archive.py`를 임포트하면 순환이 된다.**
   공유가 필요하면 `_helpers.py`로 올려라 — 그 파일은 어떤 형제도
   임포트하지 않는 리프여야 한다.
4. **로거는 모듈마다 `logging.getLogger(__name__)`으로 새로 만든다.**
   다른 모듈의 `logger`를 임포트하지 마라 —
   `tests/core/test_error_logging_policy.py`가 모듈명 생성만 허용한다.
5. **`web`은 리프다.** 어떤 앱도 `web`을 임포트하면 안 된다
   (`test_web은_리프다_어떤_앱도_web을_임포트하지_않는다`). `web → staff`도
   금지다(`test_web_모듈은_스태프_모듈을_임포트하지_않는다`) — 이 둘은 자동
   테스트로 강제된다.

## Known gap — 정리하지 않은 것

`__init__.py`가 아니라 **각 서브모듈**의 import 중 일부는 이제 안 쓰일 수 있다.
이동을 순수 이동으로 유지하려고 **의도적으로 정리하지 않았다.** 정리할 때는
`tests/events/test_home_view.py` 등이 `web.views.events.timezone.localdate`를
몽키패치한다는 점을 먼저 확인하라 — 그 이름이 사라지면 패치가 깨진다.

## Evidence — 행위 불변을 무엇으로 증명했나

### PR #251(E1, `core/views.py` → `core/views/` 패키지 분할) — 기존 기록, 보존

테스트 통과만으로는 부족하다고 판단해 세 겹으로 쟀다.

- 옮긴 함수 **50개 전부**를 이전 리비전에서 AST로 떠서 **문자 단위 대조**.
  복붙 중 주석·공백이 사라져도 테스트는 초록일 수 있다.
- **169개 라우트**의 (패턴, url name, 함수명) 완전 일치. 모듈 경로는 바뀌는 게
  정상이므로 비교에서 제외했다.
- `config/urls.py`가 **한 글자도 바뀌지 않음** — 재노출 계약이 성립한다는
  가장 직접적인 증거다. 앞으로도 이 파일이 바뀌면 `__init__.py`에 구멍이 있다는 뜻이다.

분할 순서는 `git mv core/views.py core/views/__init__.py`로 **패키지를 먼저 만든 뒤**
하나씩 빼내는 방식이었다. 파일과 패키지는 공존할 수 없고 Python이 패키지를
우선하므로, 이 순서라야 매 단계가 초록으로 유지된다.

### C4(`core/views/` → `web/views/`, 2026-08-02) — 이번 이동의 증거

- `core` 팬아웃(도메인 앱 임포트 수) **21 → 0** `[실측]`, 앱 간 순환 임포트 쌍
  **3 → 0**(완전 DAG) `[실측]`.
- 전체 회귀 **2155 → 2158 passed** `[실측]`(허용 목록 관련 메타 테스트 3건 삭제
  + 중복 R7 1건 삭제, 새 경계 가드 9건 추가).
- 뷰 7파일 **R100**(바이트 단위 동일) `[실측]`, 이동한 심볼 51개 문자 단위 일치
  `[실측]`, 라우트 **175건**이 순회 순서까지 무변경 `[실측]`, `templates/` diff
  **0바이트** `[실측]`.
- 뮤테이션 **M1~M11 전부 Red** `[실측]`.
