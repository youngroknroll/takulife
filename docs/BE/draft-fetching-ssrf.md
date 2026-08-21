# 드래프트 fetch SSRF 방어 — IP 핀닝(F6)

**Current fact.** 드래프트 파이프라인의 모든 외부 fetch(자동 수집,
스태프 수동 생성 API, robots.txt)는 `drafts/fetching.py`의 `fetch_html`
단일 지점을 경유한다. `fetch_html`은 `drafts/url_safety.py`의
`validate_fetch_url`이 검증한 IP로 직접 연결(IP 핀닝)하고, `Host` 헤더와
(https일 때) `sni_hostname` 확장으로 원래 호스트명을 유지한다.
`DRAFT_DISCOVERY_ENABLED`(env 기반, 기본 `false`)가 자동 수집과 스태프
수동 생성 두 진입 경로를 함께 게이트한다.

**Decision.** TOCTOU(검증 시점과 연결 시점의 DNS 응답이 달라지는
DNS 리바인딩) 차단 방식으로 httpx의 IP-연결 패턴(IP로 치환한 연결 URL +
`Host` 헤더 + `sni_hostname` 확장)을 채택했다(2026-08-20). httpx는 DNS
조회 자체를 가로챌 훅을 제공하지 않아, "리졸버가 반환한 소켓에 그대로
연결"하는 방식 대신 `validate_fetch_url`이 반환한 IP 문자열을 연결
URL의 호스트로 직접 치환하는 방식을 택했다.

**Guardrail.**

1. `tests/drafts/test_draft_fetching_ip_pinning.py`와
   `test_draft_fetching_redirect_revalidation.py`에
   `stub_validate_fetch_url=True`를 도입하면 안 된다 — 스텁하면 핀닝·매
   홉 재검증 트립와이어가 전부 무력화된다.
2. `fetch_html`을 우회하는 새 네트워크 경로를 추가할 때는 같은 IP
   핀닝(검증 IP로 연결 + Host 헤더 + sni_hostname)을 거치는지 확인한다.
3. 테스트 스위트는 `config/settings_test.py`가
   `DRAFT_DISCOVERY_ENABLED = False`로 고정하므로 실크롤링이 테스트 중
   켜질 수 없다 — 이 위치 계약(wildcard import 뒤에 있어야 함)은
   `tests/core/test_test_settings_boundary.py`가 강제한다.
4. 리다이렉트 홉 계산(`urljoin`)은 항상 논리(호스트명) URL 기준이다 —
   IP로 치환한 연결용 URL을 `current_url`에 대입하지 말 것.

**Known gap.**

- NAT64(`64:ff9b::/96`) 미차단 — 배포망에 NAT64가 있는지 확인 필요.
- 리졸버가 빈 리스트를 반환하면 `IndexError`가 난다 — fail-closed로
  정합시키는 작업 미완.
- IPv6(AAAA) 핀닝 경로의 계약 테스트 부재.
- `test_draft_fetching_redirect_revalidation.py`의 모듈 docstring이
  "IP 고정 대신 매 홉 재검증"이라 서술하지만, 현재 구현은 IP 핀닝과
  매 홉 재검증을 **함께** 수행한다 — 다음 접촉 시 docstring을 갱신할 것.

**Evidence.** 계약 테스트 12건 Green(`tests/drafts/test_url_safety.py`,
`test_draft_fetching_ip_pinning.py`, `test_draft_fetching_redirect_revalidation.py`
합산) `[실측 2026-08-20]`. 전체 `uv run pytest -q` 2167 passed
`[실측 2026-08-20]`. 실제 외부 사이트 수집에서 핀닝 IP로의 TLS 200
(`verify=True`) 응답 `[실측 2026-08-20]`.
