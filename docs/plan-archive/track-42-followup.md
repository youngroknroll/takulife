# 트랙 42 후속: 의존성 감사 복구 — main 직접 커밋 (2026-10-21) [v0]

> **출처**: 사용자 지시(2026-10-21) "pr을 새로 생성하지말고 문제점을 고치도록. pr이 너무 많이 생김으로 복잡해진다". 워크플로 예외(새 PR 없이 main 직접 커밋·푸시)는 이 지시가 승인이다.
> **기준선**: main `c139fa05`, push CI 39564017183에서 의존성 감사 잡만 failure [실측 gh].

- 범위: `pyproject.toml` pillow 하한을 `>=13.0.0`으로(선례 `5fd4f8b3` "Raise dependency security floors"), `uv.lock`에서 pillow 13.0.0 이상·certifi 2026.10.19 이상으로 상향. 코드 변경은 Pillow 13 호환 문제가 테스트로 드러날 때만.
- 근거: pillow 12.3.0 GHSA 8건, certifi 2026.5.20 PYSEC-2026-4320 [실측 gh run view --log-failed]. pillow는 업로드 검증(`events/image_validation.py`, archive ImageField)에 쓰인다 [실측 rg].
- 검증: 로컬 `uvx --python 3.12 pip-audit==2.9.0 -r <export> --no-deps --strict --disable-pip` 0건, `uv run pytest -q` 전체, 이미지 검증 테스트, e2e, `manage.py check`·`makemigrations --check`. 푸시 후 main push CI 4잡 success.
- 롤백: 해당 커밋 revert 1회.
- **실행 (2026-10-21)**: `uv add "pillow>=13.0.0"` + `uv lock --upgrade-package certifi` → 잠금에서 바뀐 패키지는 pillow 12.3.0→13.0.0, certifi 2026.5.20→2026.10.19 둘뿐 [실측 git diff uv.lock]. 로컬 pip-audit "No known vulnerabilities found" exit 0, 이미지 관련 테스트(PIL DeprecationWarning을 오류로) 211 passed, `uv run pytest -q` 3212 passed / 10 deselected / 99.87초, check 0건, makemigrations 변화 없음 [실측]. 로컬 e2e는 Playwright 브라우저 실행 파일 부재로 10건 setup error(환경 문제, 잠금에서 playwright 무변경) — CI e2e 잡으로 대신 확인. 커밋 `07b7186e`를 main에 직접 푸시(PR 없음). main push CI 결과는 아래에 덧붙인다.
- **main push CI (2026-10-21)**: 실행 39565641127 success — 테스트·의존성 감사·Docker 빌드·e2e 4잡 모두 success. Deploy PR workflow_run 39565827847 success(열린 #393을 갱신만 함). #393 head `07b7186e`로 이동, 새 pull_request 실행 없음(최신 id 39416537865 불변) — 트랙 42 필터 두 번째 확인. 열린 PR은 #393 하나 [실측 gh]. **종결.**

---

