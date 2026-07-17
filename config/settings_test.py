"""Test-only Django settings — never load this from a production entry point.

Loads the production settings module (`config.settings`) unchanged and
overrides only the password hasher, for test speed: the real PBKDF2 hasher
costs ~0.38s per hash (measured), which dominates suites that create many
throwaway users. MD5 is safe here because every password this settings
module ever hashes is a test-generated throwaway value, never a real user
credential — production password storage is untouched (config/settings.py
keeps Django's default PBKDF2 hasher stack).

CACHES is intentionally NOT overridden here — the DatabaseCache contract
(config/settings.py) must be exercised the same way in tests as in
production.

manage.py, config/wsgi.py, config/asgi.py, and CI/deploy configuration must
keep referencing `config.settings`, never this module — enforced by
tests/core/test_test_settings_boundary.py (TS-INF-01, TS-INF-02).
"""
from config.settings import *  # noqa: F401,F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
