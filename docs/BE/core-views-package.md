# `core/views` 패키지 계약

**Current fact.** `core/views.py`(2189줄, 최상위 함수 50개)는 2026-07-30에
`core/views/` 패키지로 분할됐다(PR #251, main `5c2012c`). 이 파일은 더 이상 없다.

| 모듈 | 담는 것 |
|---|---|
| `__init__.py` (48줄) | **순수 재노출만.** 뷰 로직 0줄 |
| `_helpers.py` (179줄) | 둘 이상의 그룹이 쓰는 범용 헬퍼 7개 |
| `events.py` (461줄) | `home`, `event_list`, `event_calendar`, `event_detail` |
| `archive.py` (639줄) | 상태·방문·직접등록·찜 뷰 9개 |
| `activity.py` (432줄) | `activity_calendar` + 활동 전용 헬퍼·상수 |
| `collection.py` (429줄) | 컬렉션 뷰 4개 + 카드 표시 헬퍼 + `SERIES_INK_*` |
| `account.py` (104줄) | `mypage` |
| `system.py` (27줄) | 법적 페이지 2개 + `api_root` + `health` |

## Guardrail — 새 뷰를 추가할 때

1. **`__init__.py`에 뷰를 쓰지 마라.** 소유 모듈에 쓰고 `__init__.py`에는
   이름만 추가한다. `__all__`에도 넣어야 URL 모듈이 찾는다.
2. **`import *`를 쓰지 마라.** 서브모듈의 module-level 이름이 패키지
   네임스페이스에 얹히면, 테스트의 몽키패치가 "성공"하고 "통과"하지만
   실행 경로에는 닿지 않는 **조용한 무효화**가 생긴다. 명시 import만.
3. **`archive.py` → `collection.py`는 단방향이다.** 방문 상세가 굿즈 카드
   헬퍼(`_collection_item_row`, `_series_ink_classes`)를 쓴다.
   **`collection.py`에서 `archive.py`를 임포트하면 순환이 된다.**
   공유가 필요하면 `_helpers.py`로 올려라 — 그 파일은 어떤 형제도
   임포트하지 않는 리프여야 한다.
4. **로거는 모듈마다 `logging.getLogger(__name__)`으로 새로 만든다.**
   다른 모듈의 `logger`를 임포트하지 마라 —
   `tests/core/test_error_logging_policy.py`가 모듈명 생성만 허용한다.

## Known gap — 정리하지 않은 것

`__init__.py`가 아니라 **각 서브모듈**의 import 중 일부는 이제 안 쓰일 수 있다.
분할을 순수 이동으로 유지하려고 **의도적으로 정리하지 않았다.** 정리할 때는
`tests/events/test_home_view.py` 등이 `core.views.events.timezone.localdate`를
몽키패치한다는 점을 먼저 확인하라 — 그 이름이 사라지면 패치가 깨진다.

## Evidence — 행위 불변을 무엇으로 증명했나

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
