# 셸 CSS 전송 — 기술 기록

기준일: 2026-08-29 · 트랙 14
대상: `core/management/commands/bundle_shell_css.py`, `templates/base.html`,
`core/context_processors.py`, `docker/entrypoint.sh`,
`tests/core/test_shell_css_bundle.py`, `tests/core/test_static_reference_guard.py`

이 문서는 **가드레일만** 담는다. 다음 작업자가 모르면 같은 실수를 반복할 것들이다.

## 현재 구성

공개 셸(`templates/base.html`)이 로드하는 셸 CSS 16개를, 운영에서는
`bundle_shell_css` 커맨드가 `css/dist/shell.css` 1개로 병합해 서빙한다.
번들 파일은 빌드 산출물이라 **저장소에 커밋하지 않는다**
(`.gitignore` `static/css/dist/`). `DEBUG=true`(로컬 개발)에서는
`shell_css_bundled` 컨텍스트 프로세서(`core/context_processors.py`)가
거짓을 반환해 템플릿이 개별 16개 링크로 되돌아간다 — 템플릿은 DEBUG를
직접 보지 않고 이 플래그만 본다.

렌더 차단 요청 수는 홈 페이지 기준 20개 → 5개로 줄었다`[실측 2026-08-29]`.

## C1 번들 순서 = base.html else 분기 링크 순서(캐스케이드) — 둘 다 갱신

번들은 `templates/base.html`의 `{% if shell_css_bundled %}...{% else %}`
분기에 나열된 개별 `<link>` 순서를 그대로 따른다. CSS는 캐스케이드(뒤에
오는 규칙이 우선)라 순서가 바뀌면 스타일 결과가 달라진다.
`tests/core/test_shell_css_bundle.py`의 계약 테스트가 번들 산출물과
소스 파일들을 바이트 단위로 이어붙인 값을 비교해 이 순서를 고정한다.

**가드레일**: 셸 CSS 파일을 추가·제거·순서 변경할 때는 `base.html`의
else 분기와 테스트 상수 `_SHELL_CSS_RELATIVE_PATHS`를 **함께** 갱신해야
한다. 한쪽만 고치면 계약 테스트가 즉시 실패한다.

## C2 셸 소스에 `url(` 참조 금지 — 병합 시 상대 경로가 깨진다

병합은 여러 디렉터리의 CSS를 한 파일로 이어붙이므로, 원본이 상대 경로로
쓴 `url(...)` 참조(배경 이미지 등)는 병합 후 위치가 달라져 깨진다.
`bundle_shell_css` 커맨드는 각 소스 파일에서 `url(` 문자열을 발견하면
즉시 `CommandError`를 내고 배포를 중단시킨다(산출물은 쓰지 않는다).

**가드레일**: `url()`이 필요한 스타일은 셸 번들 대상 CSS에 넣지 말고
페이지 전용 CSS 등 번들 밖에 두거나, 번들 설계 자체를 재검토해야 한다.

## C3 entrypoint 순서 — bundle_shell_css는 collectstatic **이전**에

`docker/entrypoint.sh`는 `collectstatic` 직전에
`manage.py bundle_shell_css --output static/css/dist/shell.css`를 실행한다.
번들 파일이 먼저 존재해야 whitenoise 매니페스트가 그 파일의 해시를
포함시킬 수 있기 때문이다. `set -e`가 이미 있어 번들 실패 시 그 종료
코드(`[실측]` 1)로 컨테이너 기동이 gunicorn 도달 전에 중단된다 — 별도
예외 처리는 불필요하다.

**가드레일**: 로컬에서 `DEBUG=false`로 실측용 서버를 띄울 때도 이 순서
(bundle_shell_css → collectstatic)를 그대로 지켜야 한다. 순서를 지키지
않으면 매니페스트에 번들 엔트리가 없어 첫 요청이 500으로 응답한다
(`docs/FE/font-delivery.md` F3와 같은 계열의 실패 양상).

## C4 정적 참조 가드의 예외는 `BUNDLE_RELATIVE_PATH` 정확히 1개만

`tests/core/test_static_reference_guard.py`는 템플릿이 `{% static %}`으로
가리키는 모든 정적 파일이 실제로 존재하는지 본다. `css/dist/shell.css`는
빌드 시점에만 생기므로 이 가드에서 유일하게 예외 처리한다 —
`bundle_shell_css.BUNDLE_RELATIVE_PATH` 상수와 정확히 일치하는 경로 1개만
건너뛴다.

**가드레일**: 이 예외를 목록으로 넓히지 말 것. 다른 빌드 산출물이 생기면
그 자체가 별도 검토 대상이지, 같은 예외 목록에 얹을 대상이 아니다.

## 캐시 트레이드오프

셸 CSS 1개만 바뀌어도 번들 전체를 다시 받아야 한다(개별 파일 캐싱 대비
세분화 손실). 종전 16개 파일의 gzip 합계는 27,185B`[실측 2026-08-29]`,
번들은 원본 67,401B·gzip 18,908B`[실측 2026-08-29]` — 병합이 오히려 압축
효율을 높여 전송량도 준다. 셸 CSS는 어차피 모든 페이지가 항상 같은 세트를
함께 로드하므로 세분화 손실은 수용 가능하다고 판단했다(WED 판정).

## 검증 근거

전체 회귀 2323 passed. 계약 테스트(`tests/core/test_shell_css_bundle.py`)로
Red→Green 확인, 정적 참조 가드(`tests/core/test_static_reference_guard.py`)
회귀 통과 확인.
