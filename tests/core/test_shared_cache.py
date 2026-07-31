"""공유 캐시: DatabaseCache 테이블 프로비저닝
(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8).

Django 테스트 러너는 *테스트* 데이터베이스용 DatabaseCache 테이블을
자동으로 만들어 주므로(django/db/backends/base/creation.py), 이 테스트
하나만으로는 프로덕션/개발 데이터베이스에 "django_cache" 테이블이 실제로
생기는지 증명할 수 없다 — 그건 core 마이그레이션(RunPython
createcachetable)이 할 일이다. 그래도 이 테스트는 실제 ORM/DB 연결을 거친
캐시 왕복을 지켜서, 나중에 백엔드가 바뀌어 이게 깨지면 잡아낸다.
"""
import pytest
from django.core.cache import cache

pytestmark = pytest.mark.contract


@pytest.mark.django_db
def test_공유_캐시는_저장한_값을_그대로_조회할_수_있다():
    cache.set("pr-0e-shared-cache-key", "shared-value", timeout=60)

    assert cache.get("pr-0e-shared-cache-key") == "shared-value"
