"""core.db_stats 검증 (트랙 37 S2 대시보드 저장소 패널, prompt_plan.md 트랙 37 S2 참고).
"""
from django.db import OperationalError, connection

import pytest

from core.db_stats import database_size_summary, format_bytes


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor != "postgresql", reason="Postgres 전용 저장소 크기 계약")
def test_postgres에서_database_size_summary는_전체_바이트와_상위_5개_테이블을_돌려준다():
    # RT-10
    summary = database_size_summary()

    assert isinstance(summary, dict)
    assert isinstance(summary["total_bytes"], int)
    assert summary["total_bytes"] > 0
    assert isinstance(summary["total_label"], str)
    assert 1 <= len(summary["tables"]) <= 5
    sizes = [table["bytes"] for table in summary["tables"]]
    assert sizes == sorted(sizes, reverse=True)
    for table in summary["tables"]:
        assert isinstance(table["name"], str)
        assert isinstance(table["bytes"], int)
        assert isinstance(table["label"], str)


@pytest.mark.unit
@pytest.mark.django_db
def test_postgres가_아니면_저장소_요약은_None이고_쿼리가_없다(monkeypatch, django_assert_num_queries):
    # RT-11
    monkeypatch.setattr(connection, "vendor", "sqlite")

    with django_assert_num_queries(0):
        summary = database_size_summary()

    assert summary is None


@pytest.mark.domain
@pytest.mark.django_db
def test_크기_쿼리가_예외를_내면_저장소_요약은_None이다(monkeypatch):
    # RT-12
    monkeypatch.setattr(connection, "vendor", "postgresql")

    def flaky_fetch_sizes():
        raise OperationalError("boom")

    monkeypatch.setattr("core.db_stats._fetch_sizes", flaky_fetch_sizes)

    assert database_size_summary() is None


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.skipif(connection.vendor != "postgresql", reason="Postgres 전용 저장소 크기 계약")
def test_database_size_summary는_쿼리_2회_이하로_끝난다(django_assert_max_num_queries):
    # RT-13
    with django_assert_max_num_queries(2):
        database_size_summary()


@pytest.mark.unit
@pytest.mark.parametrize(
    "num_bytes, expected",
    [
        (1023, "1.0KB"),
        (1_048_575, "1024.0KB"),
        (1_048_576, "1.0MB"),
        (1_073_741_823, "1024.0MB"),
        (1_073_741_824, "1.0GB"),
        (12_345_678, "11.8MB"),
    ],
)
def test_format_bytes_경계값(num_bytes, expected):
    # RT-14
    assert format_bytes(num_bytes) == expected
