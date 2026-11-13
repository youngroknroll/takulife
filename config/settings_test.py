"""테스트 전용 Django 설정 — 운영 진입점에서는 절대 로드하지 마라.

운영 설정 모듈(`config.settings`)을 그대로 불러오고 비밀번호 해셔와
드래프트 자동 수집 게이트를 덮어쓴다. 실제 PBKDF2 해셔는 1회당 약
0.38초(실측) 걸려 임시 사용자를 많이 만드는 테스트에서 시간을 대부분
잡아먹는다. 이 설정이 해싱하는 비밀번호는 전부 테스트용 임시 값이라
MD5여도 안전하며, 운영 비밀번호 저장 방식(기본 PBKDF2 해셔)은
config/settings.py에서 그대로 유지된다.

CACHES의 default(DatabaseCache)는 여기서 덮지 않는다 — 그 계약은 테스트와
운영에서 동일하게 실행돼야 한다. public만 DummyCache로 덮는다.

manage.py, config/wsgi.py, config/asgi.py, CI/배포 설정은 계속
`config.settings`만 참조해야 하며 이 모듈을 참조하면 안 된다 —
tests/core/test_test_settings_boundary.py(TS-INF-01, TS-INF-02)가 강제한다.
"""

from config.settings import *  # noqa: F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
# 개발자 로컬 .env에 DRAFT_DISCOVERY_ENABLED=true가 있어도 테스트 스위트에서
# 실제 외부 크롤링(discover_drafts)이 실수로 켜지지 않게 강제로 끈다.
DRAFT_DISCOVERY_ENABLED = False
# public 캐시를 테스트마다 비워 두지 않으면 앞 테스트의 행사 목록이 뒤
# 테스트에 남으므로 기본은 꺼 두고, 캐시를 검증하는 테스트만 켠다.
CACHES = {**CACHES, "public": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}  # noqa: F405
