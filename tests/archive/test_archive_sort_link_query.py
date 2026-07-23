"""정렬 링크 꼬리의 sort 중복 키 결함 고정 (활동 페이지 에디토리얼 v3 §I, BIR HIGH 동반 항목).

`_archive_status_context`의 기존 `pager_query`/`search_suffix`는 `sort`를 싣는다
(페이지네이션·검색 시 정렬을 유지해야 하므로 맞는 설계). 하지만 `<details>` 정렬
메뉴의 링크는 `?sort=<새값>`으로 시작하므로, 여기에 그 꼬리를 그대로 붙이면
`?sort=NEW&status=...&sort=OLD`처럼 `sort`가 중복되고 Django `QueryDict.get()`은
마지막 값을 반환해 새 정렬이 무시된다. 정렬 링크 전용 꼬리는 status/q만 담고
sort와 page는 제외해야 한다(page 제외 = 정렬 변경 시 1페이지로 자동 리셋).
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_정렬_링크_꼬리가_status와_q를_보존한다(user_client, make_event, make_status):
    user, client = user_client()
    event = make_event(title="카페 이벤트")
    make_status(user, event=event, status="visited")

    resp = client.get("/archive/statuses/?status=visited&q=카페")

    assert resp.status_code == 200
    sort_query = resp.context["sort_query"]
    assert "status=visited" in sort_query
    assert "q=%EC%B9%B4%ED%8E%98" in sort_query


@pytest.mark.django_db
def test_정렬_링크_꼬리는_sort를_포함하지_않는다(user_client, make_event, make_status):
    user, client = user_client()
    event = make_event(title="행사")
    make_status(user, event=event, status="planned")

    resp = client.get("/archive/statuses/?sort=created_at")

    assert resp.status_code == 200
    sort_query = resp.context["sort_query"]
    assert "sort=" not in sort_query


@pytest.mark.django_db
def test_정렬_링크_꼬리는_page를_포함하지_않는다(user_client, make_event, make_status):
    user, client = user_client()
    event = make_event(title="행사")
    make_status(user, event=event, status="planned")

    resp = client.get("/archive/statuses/?page=3")

    assert resp.status_code == 200
    sort_query = resp.context["sort_query"]
    assert "page=" not in sort_query
