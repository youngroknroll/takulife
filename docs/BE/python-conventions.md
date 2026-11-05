# Python 코드 컨벤션

기준선은 [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)이고,
충돌하면 이 저장소 규칙이 이긴다(사용자 결정 2026-10-29). 이 문서가 규칙의 정본이다.
`AGENTS.md` "Python Style Guide"는 이 문서를 가리키는 포인터이고, 측정과 이력은
`docs/BE/python-style.md`에 있다. 규칙은 도구가 강제하는 것과 리뷰가 지키는 것으로 나뉜다.

## 도구가 강제하는 규칙

설정은 `pyproject.toml`의 `[tool.ruff]`이고, 활성 규칙 집합은 `E4,E7,E9,E501,W,F,I,B006,TID252`이다
[코드 pyproject.toml].

| 규칙 | ruff 코드 | 설정 위치 |
|---|---|---|
| 줄 길이 100칸(한글 1자 = 2칸) | `E501` | `[tool.ruff] line-length = 100` |
| `ruff format` 서식 | (`format --check`) | `[tool.ruff]` |
| 임포트 정렬: 전체 모듈 경로 사전순, 대소문자 무시, `import`·`from` 혼합 | `I` | `[tool.ruff.lint.isort]` `force-sort-within-sections`, `case-sensitive = false` |
| 절대 임포트만 | `TID252` | `[tool.ruff.lint.flake8-tidy-imports]` `ban-relative-imports = "all"` |
| 미사용 임포트·변수 금지 | `F401`·`F841` | `select`의 `F` |
| 와일드카드 임포트 금지(예외는 `config/settings_test.py` 1곳) | `F403` | `select`의 `F` |
| 가변 기본 인자 금지 | `B006` | `select`의 `B006` |
| 제외: `migrations/` 전체, `tests/**`의 `E501` | — | `extend-exclude`, `per-file-ignores` |

람다 대입 금지(`E731`)는 `select`의 `E7`에 포함돼 도구가 잡는다(`f = lambda x: x`에 E731 보고 [실측 2026-10-30 ruff 0.15.22]). `E4,E7,E9`는 임포트 위치·문장
형태·구문 오류 묶음이다 [코드 pyproject.toml].

### 줄 길이와 서식

```python
# 나쁜 예: 한 줄이 100칸을 넘는다
result = build_report(owner=request.user, period_start=start, period_end=end, include_hidden=False)

# 좋은 예: ruff format이 만드는 모양
result = build_report(
    owner=request.user,
    period_start=start,
    period_end=end,
    include_hidden=False,
)
```

서식은 손으로 맞추지 않고 `ruff format` 출력을 따른다. 한글은 2칸이므로 한글 주석은 영문보다 일찍
100칸에 닿는다.

### 임포트 정렬·절대 임포트

```python
# 나쁜 예
from .models import Event
# 좋은 예
from events.models import Event
```

### 미사용 임포트·변수

```python
# 나쁜 예: 쓰지 않는 임포트와 변수
import os
saved = save_event(event)

# 좋은 예: 호출은 남기고 대입만 지운다
save_event(event)
```

### 와일드카드 임포트

```python
# 나쁜 예
from archive.models import *
# 좋은 예
from archive.models import CollectionItem
```

예외는 `config/settings_test.py`의 `from config.settings import *  # noqa: F401,F403` 한 곳이다.
덮어쓰기 순서는 계약 테스트 `tests/core/test_test_settings_boundary.py`가 고정한다.

### 가변 기본 인자

```python
# 나쁜 예: 호출마다 같은 리스트를 공유한다
def collect(item, bucket=[]): ...
# 좋은 예
def collect(item, bucket=None):
    bucket = [] if bucket is None else bucket
```

### 람다 대입

```python
# 나쁜 예
is_owned = lambda item: item.owned_quantity > 0
# 좋은 예
def is_owned(item):
    return item.owned_quantity > 0
```

## 임포트

항상 절대 경로로 가져온다. 아래는 `drafts/runner_views.py`의 앞부분이다. 정렬 기준은 표준 라이브러리,
서드파티, 저장소 모듈 순으로 묶고, 묶음 안에서는 전체 모듈 경로 사전순이다.

```python
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response

from core.categories import category_slugs
from core.errors import error_response
from core.runner_auth import RunnerAPIView
from core.vocab import REGION
```

**재노출 금지.** 이름은 정의한 모듈에서 가져온다. `# noqa: F401` 재노출로 다른 경로를 열지 않는다
(2026-10-30 `LeaseInvalidError`·`RunnerTokenThrottle` 사례를 제거했다). 허용되는 `# noqa: F401`은
부수효과 임포트(`apps.py` `ready()`의 `signals`)와 `config/settings_test.py` 와일드카드뿐이며
한국어 사유를 단다.

```python
# 나쁜 예: 다른 모듈이 이 경로로 가져다 쓰게 열어 둔다
from core.runner_auth import RunnerAPIView, RunnerTokenThrottle  # noqa: F401

# 좋은 예: 정의한 모듈에서 직접 가져온다 (테스트도 마찬가지)
from core.runner_auth import RunnerTokenThrottle
```

`__init__.py`의 공개 API 재노출(`staff/views`·`web/views`)은 URLconf가 `views.이름`으로 참조하는
관용이라 예외이다. 뷰 계층 테스트 파일(`*_view(s).py`·`*_api.py`, 또는 `client` 계열 픽스처를 쓰는
파일)은 services/queries 모듈을 직접 가져오지 않는다 — 뷰가 쓰는 이름은 뷰 모듈에서 가져온다
(경계 가드 `tests/core/test_architecture_boundaries.py`의
`test_api_view_계층_테스트_파일은_서비스_쿼리_계층을_임포트하지_않는다`). 이것은 `# noqa` 재노출이
아니라 뷰가 실제로 쓰는 이름이다.

함수 안 지연 임포트는 순환 임포트를 피할 때만 쓰고 절대 경로로 쓴다.

## 이름

| 대상 | 규칙 | 예 |
|---|---|---|
| 함수·변수 | `snake_case` | `record_heartbeat` |
| 클래스 | `CapWords` | `CollectionItem` |
| 상수 | `UPPER_SNAKE_CASE` | `MAX_CANDIDATES_PER_RUN` |
| 예외 클래스 | `Error` 접미 | `CandidateLimitExceededError` |

- 예외 클래스 이름은 2026-10-30 `SubmissionRejectedError`로 통일했고 예외가 없다.
- Django 관용(`User = get_user_model()`)은 허용한다.
- 테스트 이름은 한국어 행동 중심이다(`AGENTS.md` "Test Authoring Policy").

```python
class SubmissionRejectedError(Exception): ...   # 좋은 예
class SubmissionRejected(Exception): ...        # 나쁜 예: Error 접미 없음
```

## 주석과 docstring

규칙의 정본은 `AGENTS.md` "Code Comment Policy"이다. 요지는 세 가지이다.

- 주석은 짧은 한국어 1~2줄로 쓴다.
- 코드를 말로 옮기지 않고, 비개발자가 읽을 수 있는 말로 이유를 쓴다.
- 코드가 이해되지 않으면 주석 대신 코드를 고친다.

Google식 `Args:`/`Returns:`/`Raises:` 절과 영어 docstring은 쓰지 않는다. 위치 표시는
`TODO(<scope>)`이며 `FIXME`는 쓰지 않는다.

```python
# 나쁜 예: 코드 번역
# 사용자가 로그인했는지 확인한다.
if request.user.is_authenticated:

# 좋은 예: 이유
# 수집 기록은 소유자만 볼 수 있어 다른 사람에게 노출되지 않는다.
if item.owner_id == request.user.id:
```

## 예외·오류 처리

- bare `except:`는 금지한다.
- 예상된 도메인 실패는 HTTP 경계에서 번역한다. 상세는 `AGENTS.md` "Error Handling And Logging".
- 예외 클래스 이름은 `Error`로 끝낸다.

```python
# 나쁜 예
try:
    submit(draft)
except:
    pass

# 좋은 예
try:
    submit(draft)
except SubmissionRejectedError:
    return error_response(...)
```

## Google 가이드에서 채택하지 않은 것

| Google 항목 | 미채택 이유 |
|---|---|
| docstring `Args:`/`Returns:`/`Raises:` 절, 영어 docstring | Code Comment Policy가 한국어 1~2줄을 요구한다 |
| 패키지·모듈만 임포트 | Django/DRF는 이름 임포트가 관용이고, 몽키패치 대상과 AST 경계 테스트가 이름 임포트에 의존한다 |
| 타입 힌트 의무화 | 현재 규칙에 없고 도입 이득을 측정하지 않았다 |
| pylint 전용 검사 | ruff로 대체하고 나머지는 리뷰로 지킨다 |
| 80칸 | 100칸이 변경량이 가장 작다(측정은 `docs/BE/python-style.md` "줄 길이 결정") |

## 도구 실행

- 검사: `uv run ruff check .`, `uv run ruff format --check .`
- 고치기: `uv run ruff format <파일>`, `uv run ruff check --fix <파일>`. 자동 수정은 `F401`·`I001`
  같은 안전한 규칙만 쓰고, 결과를 `git diff`로 확인한다.
- CI 잡 "Lint and format (PR gate)"가 두 검사를 돌린다. 계약 테스트
  `tests/core/test_lint_gate_contract.py`가 설정 약화를 막는다.

## 훅이 강제하는 것

- `.claude/hooks/python-style-guard.sh` (PostToolUse `Edit|Write`): 저장소 안 `.py`를 편집하면
  그 파일에 ruff 두 명령을 돌려 위반을 즉시 알린다. 파일은 고치지 않는다.
- `.claude/hooks/git-commit-style-guard.sh` (PreToolUse `Bash`): `git commit` 때 스테이지된
  `.py`와 같은 명령의 `git add`·`git commit <경로>`에 적힌 `.py`에 위반이 있으면 커밋을 막는다
  (`git add x.py && git commit`처럼 한 명령에 묶어도 검사한다).

둘 다 ruff가 없으면 경고만 하고 통과한다. 알려진 공백은 `AGENTS.md` "Harness Enforcement (hooks)" 표에 있다.

## 규칙을 바꿀 때

- `pyproject.toml`, 계약 테스트, 이 문서, `AGENTS.md` 포인터를 같은 커밋에서 바꾼다.
- 포맷 전용 커밋은 `.git-blame-ignore-revs`에 추가한다.
- ruff 상향은 `docs/BE/python-style.md` "ruff 상향 절차"를 따른다.
