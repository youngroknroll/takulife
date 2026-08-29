# 웹폰트 전송 — 기술 기록

기준일: 2026-08-29 · 트랙 13
대상: `static/fonts/pretendard/`, `templates/base.html`, `templates/staff/base_staff.html`

이 문서는 **가드레일만** 담는다. 다음 작업자가 모르면 같은 실수를 반복할 것들이다.

## 현재 구성

Pretendard v1.3.9 공식 dynamic-subset을 자체 호스팅한다.
`static/fonts/pretendard/`에 폰트 CSS 1개 + woff2 청크 92개가 있고, 청크는
`unicode-range`로 지연 로드된다. 스태프 셸(`templates/staff/base_staff.html`)은
tokens → 폰트 CSS → base 순으로 그대로다. 공개 셸(`templates/base.html`)은
트랙 14(셸 CSS 번들, `docs/FE/css-delivery.md`)에서 폰트 CSS 링크가 셸
스타일 분기(`{% if shell_css_bundled %}...{% endif %}`) **뒤**로 이동했다 —
폰트 CSS는 `@font-face`만 담아 다른 셀렉터를 참조하지 않으므로 로드 순서가
바뀌어도 적용 결과는 무관하다`[코드]`.

`[실측]` 첫 방문 전송량 343,780B / 13청크(실제 쓰이는 문자 범위만). 종전
단일 woff2 방식은 2,057,688B 전량 전송이었다.

## F1 벤더 CSS의 family 명은 수정된 산출물이다

Pretendard 공식 배포 CSS는 `font-family: 'Pretendard Variable'`을 쓴다.
이 저장소는 사이트 폰트 스택('Pretendard')과 맞추려고 **family 명만**
'Pretendard'로 치환했다(치환 사실은 파일 상단 주석에 남아 있다). 그 외
`src`·`unicode-range`·`font-weight` 등은 벤더 원본 그대로다.

**가드레일**: 폰트 버전을 올릴 때 새 dynamic-subset 산출물을 같은 상대
구조로 놓고 이 family 치환을 다시 적용해야 한다. 치환을 빠뜨리면 CSS는
유효하게 로드되지만 `font-family: 'Pretendard'`를 참조하는 사이트 전체가
아무 오류 없이 조용히 시스템 폰트로 폴백한다.

## F2 `url()` 상대 경로는 whitenoise가 재작성한다 — 손대지 말 것

폰트 CSS 안의 `url()`은 상대 경로 그대로 커밋돼 있다. `collectstatic` 시
whitenoise 매니페스트가 해시를 붙여 재작성한다. 경로를 절대 경로나 다른
형태로 고치면 매니페스트 재작성 규칙과 어긋나 정적 파일 조회가 깨질 수
있다.

## F3 매니페스트에는 있는데 파일이 없으면 500이 난다

`[실측]` 청크 파일이 매니페스트 엔트리와 어긋나면 whitenoise가 해당 요청에
500을 낸다. 화면에서는 해당 유니코드 범위의 글자만 폴백 폰트로 렌더되고
콘솔에 오류 1건이 뜨는 형태로 나타난다 — 페이지 전체가 깨지지 않아
알아채기 쉽지 않다. **폰트 관련 500을 만나면 먼저 `collectstatic` 재실행부터
의심한다.**

## F4 same-origin preload도 crossorigin이 필요하다

폰트에 `<link rel="preload">` 힌트를 추가하려면 `as="font"`와 함께
`crossorigin` 속성이 필수다(same-origin이어도 스펙상 요구됨). 빠뜨리면
브라우저가 캐시를 공유하지 못해 같은 리소스를 이중 요청한다.

## F5 공개 셸 preload 13청크 — 3페이지 교집합, 임의 확장 금지

공개 셸(`templates/base.html`)이 preload하는 청크 목록의 정본은
`core/context_processors.py`의 `FONT_PRELOAD_CHUNKS` 상수이며, 템플릿은
이 상수를 `{% for %}` 루프로 반복해 `<link rel="preload">`를 렌더한다.
현재 subset.78·79·81~91 총 13개다`[실측 2026-08-29]`. 이 목록은 공개
3페이지(홈/행사 목록/행사 상세)가 실제로 쓰는 유니코드 범위의
**교집합**이며, 행사 상세에서만 쓰이는 subset.70은 의도적으로 제외했다 —
상세 전용 문자를 모든 페이지에서 preload하면 홈·목록에서는 쓰이지 않는
청크를 매번 선제 다운로드하게 된다. F4의 `crossorigin`·`as="font"`·
`type="font/woff2"` 3속성은 이 상수를 렌더하는 템플릿 루프 안에서 13개
각각에 그대로 적용해야 한다.

**가드레일**: 목록 갱신은 `FONT_PRELOAD_CHUNKS` 상수 한 곳만 고치면
된다(템플릿은 손댈 필요 없음). 페이지 문자 구성이 크게 바뀌면(새 언어
추가, 대량 텍스트 개편 등) 교집합을 다시 측정하고 이 상수를 갱신해야
한다. 브라우저 콘솔에 "The resource ... was preloaded but not used"
경고가 뜨면 목록이 낡았다는 신호다.

## 이월

- 데스크탑 콜드 로드 CLS 0.02(`[실측]`)는 `font-display: swap`의 리플로
  구조상 발생하는 값으로 수용했다. 계획 문서의 목표치 0.01은 실측 전
  추정이었으므로 정정한다. `size-adjust` 디스크립터 튜닝으로 더 낮출 여지는
  있으나 이번 트랙 범위 밖 — 후속 후보로만 남긴다.

## 검증 근거

전체 회귀 2311 passed. 스태프 콘솔에서 폰트 청크 13/13 요청이 200으로
응답함을 네트워크 패널로 확인(`[실측]`).

트랙 14(셸 CSS 번들 + F5 preload 목록 확정) 이후 재측정: 모바일(Slow 4G ·
CPU 4x 스로틀) 콜드 로드 FCP·LCP 중앙값이 3,100ms → 2,672ms(3회 측정
`[실측 2026-08-29]`)로, 종속 요청 체인 중 가장 긴 체인이 1,192ms → 638ms로
줄었다. woff2 청크가 CSS를 거치지 않고 문서에서 직접 `<link rel="preload">`로
로드되도록 체인 한 단계가 줄어든 결과다.
