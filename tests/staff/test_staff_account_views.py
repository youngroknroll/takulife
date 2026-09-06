"""스태프 계정 운영 화면(/staff/accounts/) — 트랙 19 H1 수직 슬라이스.

조작 주체는 슈퍼유저 한정이라 관문은 `staff_console_required` 위에
`is_superuser` 검사를 더한다(승인 범위 1번). 상태 변경은 토글이 아니라
목표 상태 지정(`enabled` "1"/"0")이고, 서버 렌더 2단계 확인
(`confirmed=yes`) 뒤에야 실제로 바뀐다(2단계 확인 패턴은
tests/staff/test_staff_event_publish_delete_views.py의 삭제 흐름과 같다).
"""
from urllib.parse import urlencode

from django.db import IntegrityError, connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

import pytest

from accounts import services
from staff.models import StaffActionLog
from staff.views.accounts import STAFF_ACCOUNT_LISTING_PAGE_SIZE

pytestmark = pytest.mark.web


def _list_url():
    return "/staff/accounts/"


def _detail_url(user):
    return f"/staff/accounts/{user.pk}/"


def _set_staff_url(user):
    return f"/staff/accounts/{user.pk}/staff/"


def _set_active_url(user):
    return f"/staff/accounts/{user.pk}/active/"


# T1 목록 관문 ----------------------------------------------------------


@pytest.mark.django_db
def test_익명_사용자가_계정_목록에_접근하면_로그인_페이지로_리다이렉트된다(client):
    resp = client.get(_list_url())

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next={_list_url()}"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "actor_kwargs",
    [
        pytest.param({"is_staff": False}, id="일반_사용자"),
        pytest.param({"is_staff": True}, id="슈퍼유저_아닌_스태프"),
    ],
)
def test_슈퍼유저가_아닌_사용자가_계정_목록에_접근하면_403을_응답한다(user_client, actor_kwargs):
    _, client = user_client(**actor_kwargs)

    resp = client.get(_list_url())

    assert resp.status_code == 403


# T2 목록 -----------------------------------------------------------------


@pytest.mark.django_db
def test_슈퍼유저가_계정_목록에_접근하면_200과_함께_대상_행을_본다(staff_client, make_user):
    target = make_user(email="listed-target-account@example.com")
    _, client = staff_client(is_superuser=True)

    resp = client.get(_list_url())

    assert resp.status_code == 200
    row_ids = [row["id"] for row in resp.context["account_rows"]]
    assert target.pk in row_ids


@pytest.mark.django_db
def test_계정_목록_화면은_q_검색어와_일치하는_사용자만_보여준다(staff_client, make_user):
    make_user(email="unrelated-list-account@example.com")
    target = make_user(email="beta-list-search-match@example.com")
    _, client = staff_client(is_superuser=True)

    resp = client.get(f"{_list_url()}?q=list-search-match")

    assert resp.status_code == 200
    row_ids = [row["id"] for row in resp.context["account_rows"]]
    assert row_ids == [target.pk]
    assert resp.context["search"] == "list-search-match"


@pytest.mark.django_db
def test_계정_목록은_페이지당_STAFF_ACCOUNT_LISTING_PAGE_SIZE건으로_나뉜다(staff_client, make_user):
    for i in range(STAFF_ACCOUNT_LISTING_PAGE_SIZE + 1):
        make_user(email=f"page-account-{i}@example.com")
    _, client = staff_client(is_superuser=True)

    resp = client.get(_list_url())

    assert resp.status_code == 200
    page_obj = resp.context["page_obj"]
    assert page_obj.paginator.count >= STAFF_ACCOUNT_LISTING_PAGE_SIZE + 1
    assert len(page_obj.object_list) == STAFF_ACCOUNT_LISTING_PAGE_SIZE


@pytest.mark.django_db
def test_계정_목록_페이저_쿼리는_검색어를_URL_인코딩한다(staff_client):
    _, client = staff_client(is_superuser=True)

    resp = client.get("/staff/accounts/", {"q": "a b&c"})

    assert resp.status_code == 200
    assert resp.context["pager_query"] == "&" + urlencode([("q", "a b&c")])


# T3 상세 -----------------------------------------------------------------


@pytest.mark.django_db
def test_슈퍼유저가_아닌_사용자가_계정_상세에_접근하면_403을_응답한다(staff_client, make_user):
    target = make_user()
    _, client = staff_client()  # 슈퍼유저 아님

    resp = client.get(_detail_url(target))

    assert resp.status_code == 403


@pytest.mark.django_db
def test_탈퇴_신청이_없는_대상의_상세_컨텍스트에는_유예_예정일이_없다(staff_client, make_user):
    target = make_user()
    _, client = staff_client(is_superuser=True)

    resp = client.get(_detail_url(target))

    assert resp.status_code == 200
    assert resp.context["deletion_scheduled_for"] is None


@pytest.mark.django_db
def test_탈퇴_유예_중인_대상의_상세_컨텍스트_유예_예정일은_신청_시각에_10일을_더한_값이다(staff_client, make_user):
    target = make_user()
    services.request_deletion(target)
    target.refresh_from_db()
    _, client = staff_client(is_superuser=True)

    resp = client.get(_detail_url(target))

    assert resp.status_code == 200
    assert resp.context["deletion_scheduled_for"] == (
        target.deletion_requested_at + services.DELETION_GRACE_PERIOD
    )


@pytest.mark.django_db
def test_is_protected는_대상이_슈퍼유저면_참이고_아니면_거짓이다(staff_client, make_user):
    protected_target = make_user(is_staff=True, is_superuser=True)
    normal_target = make_user()
    _, client = staff_client(is_superuser=True)

    protected_resp = client.get(_detail_url(protected_target))
    normal_resp = client.get(_detail_url(normal_target))

    assert protected_resp.context["is_protected"] is True
    assert normal_resp.context["is_protected"] is False


# T6 상태 변경 관문 ----------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_fn",
    [
        pytest.param(_set_staff_url, id="staff"),
        pytest.param(_set_active_url, id="active"),
    ],
)
def test_익명_사용자가_상태_변경을_요청하면_로그인_페이지로_리다이렉트된다(client, make_user, url_fn):
    target = make_user()

    resp = client.post(url_fn(target))

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next={url_fn(target)}"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_fn",
    [
        pytest.param(_set_staff_url, id="staff"),
        pytest.param(_set_active_url, id="active"),
    ],
)
@pytest.mark.parametrize(
    "actor_kwargs",
    [
        pytest.param({"is_staff": False}, id="일반_사용자"),
        pytest.param({"is_staff": True}, id="슈퍼유저_아닌_스태프"),
    ],
)
def test_슈퍼유저가_아닌_사용자가_상태_변경을_요청하면_403을_응답한다(
    user_client, make_user, url_fn, actor_kwargs
):
    target = make_user()
    _, client = user_client(**actor_kwargs)

    resp = client.post(url_fn(target), {"enabled": "1"})

    assert resp.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_fn, flag_attr",
    [
        pytest.param(_set_staff_url, "is_staff", id="staff"),
        pytest.param(_set_active_url, "is_active", id="active"),
    ],
)
def test_상태_변경_경로에_GET으로_접근하면_405를_응답하고_대상을_바꾸지_않는다(
    staff_client, make_user, url_fn, flag_attr
):
    target = make_user(is_staff=False, is_active=True)
    before = getattr(target, flag_attr)
    _, client = staff_client(is_superuser=True)

    resp = client.get(url_fn(target))

    assert resp.status_code == 405
    target.refresh_from_db()
    assert getattr(target, flag_attr) == before


# T7 확인 화면 --------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_fn, flag_attr",
    [
        pytest.param(_set_staff_url, "is_staff", id="staff"),
        pytest.param(_set_active_url, "is_active", id="active"),
    ],
)
def test_confirmed_없이_상태_변경_POST하면_확인_화면을_보여주고_대상을_바꾸지_않는다(
    staff_client, make_user, url_fn, flag_attr
):
    target = make_user(is_staff=False, is_active=True)
    before = getattr(target, flag_attr)
    _, client = staff_client(is_superuser=True)

    resp = client.post(url_fn(target), {"enabled": "1"})

    assert resp.status_code == 200
    target.refresh_from_db()
    assert getattr(target, flag_attr) == before
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_fn, flag_attr",
    [
        pytest.param(_set_staff_url, "is_staff", id="staff"),
        pytest.param(_set_active_url, "is_active", id="active"),
    ],
)
@pytest.mark.parametrize(
    "post_data",
    [
        pytest.param({}, id="누락"),
        pytest.param({"enabled": ""}, id="빈_값"),
        pytest.param({"enabled": "true"}, id="true"),
        pytest.param({"enabled": "2"}, id="2"),
    ],
)
def test_enabled가_1_또는_0이_아니면_400을_응답하고_대상을_바꾸지_않고_로그를_남기지_않는다(
    staff_client, make_user, url_fn, flag_attr, post_data
):
    target = make_user(is_staff=False, is_active=True)
    before = getattr(target, flag_attr)
    _, client = staff_client(is_superuser=True)

    resp = client.post(url_fn(target), {**post_data, "confirmed": "yes"})

    assert resp.status_code == 400
    target.refresh_from_db()
    assert getattr(target, flag_attr) == before
    assert StaffActionLog.objects.count() == 0


# T8 확인 POST --------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_fn, target_kwargs, enabled, expected_action, flag_attr, expected_after",
    [
        pytest.param(
            _set_staff_url, {"is_staff": False}, "1", "staff_grant", "is_staff", True, id="grant"
        ),
        pytest.param(
            _set_staff_url, {"is_staff": True}, "0", "staff_revoke", "is_staff", False, id="revoke"
        ),
        pytest.param(
            _set_active_url,
            {"is_active": True},
            "0",
            "user_deactivate",
            "is_active",
            False,
            id="deactivate",
        ),
        pytest.param(
            _set_active_url,
            {"is_active": False},
            "1",
            "user_reactivate",
            "is_active",
            True,
            id="reactivate",
        ),
    ],
)
def test_confirmed_yes로_상태_변경_POST하면_대상이_바뀌고_감사_로그가_남고_성공_메시지와_함께_상세로_리다이렉트된다(
    staff_client, make_user, url_fn, target_kwargs, enabled, expected_action, flag_attr, expected_after
):
    target = make_user(**target_kwargs)
    staff, client = staff_client(is_superuser=True)

    resp = client.post(url_fn(target), {"enabled": enabled, "confirmed": "yes"}, follow=True)

    assert resp.status_code == 200
    assert resp.redirect_chain[0][0] == _detail_url(target)
    target.refresh_from_db()
    assert getattr(target, flag_attr) == expected_after
    log = StaffActionLog.objects.get(target_user=target)
    assert log.action == expected_action
    assert log.actor_id == staff.id
    messages_text = " ".join(str(m) for m in resp.context["messages"])
    assert messages_text


@pytest.mark.contract
@pytest.mark.django_db
def test_상태_변경_확인_POST는_대상_행을_잠그고_처리한다(staff_client, make_user):
    """F9와 같은 경쟁 위험: 목표 상태 지정이라도 읽고-바꾸는 흐름은 잠그지
    않으면 동시 요청이 경쟁한다(test_게시_토글은_대상_행을_잠그고_읽는다 선례)."""
    target = make_user(is_staff=False)
    _, client = staff_client(is_superuser=True)

    with CaptureQueriesContext(connection) as ctx:
        resp = client.post(_set_staff_url(target), {"enabled": "1", "confirmed": "yes"})

    assert resp.status_code == 302
    locking_queries = [q for q in ctx.captured_queries if "FOR UPDATE" in q["sql"].upper()]
    assert locking_queries, ctx.captured_queries


@pytest.mark.contract
@pytest.mark.django_db
def test_감사_로그_저장이_실패하면_상태_변경도_롤백된다(staff_client, make_user, monkeypatch):
    target = make_user(is_staff=False)
    _, client = staff_client(is_superuser=True)

    def fail_log_create(*args, **kwargs):
        raise IntegrityError("simulated log write failure")

    monkeypatch.setattr("staff.views.accounts.StaffActionLog.objects.create", fail_log_create)
    client.raise_request_exception = False

    resp = client.post(_set_staff_url(target), {"enabled": "1", "confirmed": "yes"})

    assert resp.status_code == 500
    target.refresh_from_db()
    assert target.is_staff is False
    assert StaffActionLog.objects.count() == 0


# T9 무변경 경로 -------------------------------------------------------------


@pytest.mark.django_db
def test_타인_슈퍼유저_대상에_확인_상태_변경_POST를_보내면_변경없이_오류_메시지를_보여주고_로그를_남기지_않는다(
    staff_client, make_user
):
    target = make_user(is_staff=True, is_superuser=True)
    _, client = staff_client(is_superuser=True)

    resp = client.post(_set_staff_url(target), {"enabled": "0", "confirmed": "yes"}, follow=True)

    assert resp.status_code == 200
    target.refresh_from_db()
    assert target.is_staff is True
    assert StaffActionLog.objects.count() == 0
    messages_text = " ".join(str(m) for m in resp.context["messages"])
    assert messages_text


@pytest.mark.django_db
def test_본인_계정에_확인_상태_변경_POST를_보내면_변경없이_오류_메시지를_보여주고_로그를_남기지_않는다(staff_client):
    staff, client = staff_client(is_superuser=True)

    resp = client.post(_set_staff_url(staff), {"enabled": "0", "confirmed": "yes"}, follow=True)

    assert resp.status_code == 200
    staff.refresh_from_db()
    assert staff.is_staff is True
    assert StaffActionLog.objects.count() == 0
    messages_text = " ".join(str(m) for m in resp.context["messages"])
    assert messages_text


@pytest.mark.django_db
def test_이미_목표_상태인_대상에_확인_상태_변경_POST를_보내면_변경없이_안내_메시지를_보여주고_로그를_남기지_않는다(
    staff_client, make_user
):
    target = make_user(is_staff=True)
    _, client = staff_client(is_superuser=True)

    resp = client.post(_set_staff_url(target), {"enabled": "1", "confirmed": "yes"}, follow=True)

    assert resp.status_code == 200
    target.refresh_from_db()
    assert target.is_staff is True
    assert StaffActionLog.objects.count() == 0
    messages_text = " ".join(str(m) for m in resp.context["messages"])
    assert messages_text


# T10 세션 무효 -------------------------------------------------------------


@pytest.mark.django_db
def test_비활성화된_대상의_기존_세션은_다음_요청에서_익명으로_처리된다(staff_client, make_user):
    target = make_user(is_active=True)
    target_client = Client()
    target_client.force_login(target)
    assert target_client.get("/mypage/").status_code == 200

    _, superuser_client = staff_client(is_superuser=True)
    resp = superuser_client.post(_set_active_url(target), {"enabled": "0", "confirmed": "yes"})
    assert resp.status_code == 302

    resp = target_client.get("/mypage/")

    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]


# T14 사이드바 --------------------------------------------------------------


@pytest.mark.django_db
def test_슈퍼유저의_콘솔_화면_본문에는_계정_링크가_있다(staff_client):
    _, client = staff_client(is_superuser=True)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert "/staff/accounts/" in resp.content.decode()


@pytest.mark.django_db
def test_슈퍼유저가_아닌_스태프의_콘솔_화면_본문에는_계정_링크가_없다(staff_client):
    _, client = staff_client()  # 슈퍼유저 아님

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert "/staff/accounts/" not in resp.content.decode()
