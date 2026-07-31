"""2단계 인증 백엔드 테스트:
- archive API의 권한·IDOR
- 인증 경계(비로그인, CSRF)
- 회원가입(정상, 취약 비밀번호, 이메일 중복, django-allauth를 통한 이메일
  인증 필수화)
- HTML archive 뷰의 @login_required 리다이렉트
"""
import re

import pytest
from django.test import Client
from rest_framework.test import APIClient

pytestmark = pytest.mark.web


# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

def _create_status(client, event, status_value="planned"):
    """현재 로그인된 클라이언트로 UserEventStatus를 만들고 id를 돌려준다."""
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": status_value},
        content_type="application/json",
    )
    assert response.status_code == 201, response.json()
    return response.json()["id"]


# ---------------------------------------------------------------------------
# 권한 / IDOR
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_다른_사용자의_일정_상태를_PATCH하면_404로_숨겨진다(client, make_user, make_event):
    """다른 사용자의 자원이 존재한다는 사실 자체를 숨기기 위해 403이 아니라
    404를 돌려준다."""
    user_a = make_user(username="idor-user-a")
    user_b = make_user(username="idor-user-b")
    event = make_event()

    client.force_login(user_a)
    status_id = _create_status(client, event)

    client.force_login(user_b)
    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_다른_사용자의_일정_상태를_DELETE하면_404로_숨겨진다(client, make_user, make_event):
    """다른 사용자의 자원이 존재한다는 사실 자체를 숨기기 위해 403이 아니라
    404를 돌려준다."""
    user_a = make_user(username="idor-del-a")
    user_b = make_user(username="idor-del-b")
    event = make_event()

    client.force_login(user_a)
    status_id = _create_status(client, event)

    client.force_login(user_b)
    response = client.delete(f"/api/user-event-statuses/{status_id}/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_일정_상태_목록_조회는_다른_사용자의_기록을_포함하지_않는다(client, make_user, make_event):
    user_a = make_user(username="list-user-a")
    user_b = make_user(username="list-user-b")
    event = make_event()

    client.force_login(user_a)
    _create_status(client, event, "planned")

    client.force_login(user_b)
    response = client.get("/api/user-event-statuses/")

    assert response.status_code == 200
    assert response.json()["count"] == 0


@pytest.mark.django_db
def test_일정_상태_생성_시_user_필드를_지정해도_소유자는_요청자로_고정된다(client, make_user, make_event):
    """POST 본문으로 user 필드를 보내도 소유자를 덮어쓸 수 없다 — 소유자는
    항상 인증된 요청자다."""
    user_a = make_user(username="post-user-a")
    user_b = make_user(username="post-user-b")
    event = make_event()

    client.force_login(user_a)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned", "user": user_b.id},
        content_type="application/json",
    )

    assert response.status_code == 201
    # 생성된 상태는 user_b가 아니라 user_a의 것이다
    status_id = response.json()["id"]
    client.force_login(user_a)
    own_response = client.get(f"/api/user-event-statuses/{status_id}/")
    assert own_response.status_code == 200

    client.force_login(user_b)
    other_response = client.get(f"/api/user-event-statuses/{status_id}/")
    assert other_response.status_code == 404


@pytest.mark.django_db
def test_일정_상태_수정_시_event_필드_변경_요청은_무시된다(client, make_user, make_event):
    """다른 event id로 PATCH해도 조용히 무시된다(event는 수정 시 읽기
    전용이다)."""
    user = make_user(username="patch-event-user")
    event = make_event(title="Original Event")
    other_event = make_event(title="Other Event")

    client.force_login(user)
    status_id = _create_status(client, event)

    response = client.patch(
        f"/api/user-event-statuses/{status_id}/",
        {"event": other_event.id, "status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 200
    # event는 그대로 유지돼야 한다
    assert response.json()["event"] == event.id
    assert response.json()["status"] == "visited"


# ---------------------------------------------------------------------------
# 인증 경계
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_비로그인_사용자의_일정_상태_API_조회는_403으로_거부된다():
    """DRF SessionAuthentication 기본값에 따라 비로그인 GET은 403이다."""
    client = Client()
    response = client.get("/api/user-event-statuses/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_비로그인_사용자의_일정_상태_API_생성_요청은_403으로_거부된다(make_event):
    """DRF SessionAuthentication 기본값에 따라 비로그인 POST도 403이다."""
    event = make_event()
    client = Client()
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_CSRF_토큰_없이_일정_상태를_생성하면_403으로_거부된다(make_user, make_event):
    """SessionAuthentication은 위험한(unsafe) 메서드에 CSRF를 강제하므로,
    로그인한 상태여도 CSRF 헤더 없는 POST는 403이다.

    APIClient는 기본적으로 CSRF를 우회하므로 enforce_csrf_checks=True로
    명시적으로 CSRF 검사를 켠다.
    """
    user = make_user(username="csrf-test-user")
    event = make_event()

    api_client = APIClient(enforce_csrf_checks=True)
    api_client.force_login(user)

    response = api_client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_CSRF_토큰과_함께_일정_상태를_생성하면_201로_성공한다(client, make_user, make_event):
    """세션과 CSRF가 정상이면 인증된 POST는 성공한다.

    Django 테스트 클라이언트는 force_login과 테스트 클라이언트 미들웨어가
    활성화돼 있으면 CSRF를 자동으로 처리한다(테스트 클라이언트의
    enforce_csrf_checks 기본값은 False라, 쿠키를 쓰는 실제 JS 동작을
    그대로 흉내낸다).
    """
    user = make_user(username="csrf-pass-user")
    event = make_event()

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# 회원가입(django-allauth: 이메일을 식별자로, 인증 필수)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_회원가입_페이지에_접근하면_가입_폼이_렌더링된다(client):
    response = client.get("/accounts/signup/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_회원가입_직후에는_이메일_인증_전이라_로그인_상태가_되지_않는다(client, django_user_model, valid_password):
    response = client.post(
        "/accounts/signup/",
        {
            "email": "newuser@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )
    # 앱으로 바로 들어가지 않고 "이메일을 확인하세요" 페이지로 리다이렉트된다.
    assert response.status_code == 302
    assert django_user_model.objects.filter(email="newuser@example.com").exists()

    # 아직 인증되지 않아 보호된 페이지는 로그인으로 튕긴다.
    archive_response = client.get("/archive/")
    assert archive_response.status_code == 302
    assert "/accounts/login/" in archive_response["Location"]


@pytest.mark.django_db
def test_이메일_인증_링크를_클릭하면_로그인_상태가_된다(client, django_user_model, mailoutbox, valid_password):
    client.post(
        "/accounts/signup/",
        {
            "email": "confirmme@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )
    assert len(mailoutbox) == 1
    match = re.search(r"http://\S+(/accounts/confirm-email/\S+/)", mailoutbox[0].body)
    assert match, mailoutbox[0].body

    response = client.post(match.group(1), follow=True)
    assert response.status_code == 200

    archive_response = client.get("/archive/")
    assert archive_response.status_code == 200


@pytest.mark.django_db
def test_취약한_비밀번호로_가입하면_거부되고_계정이_생성되지_않는다(client, django_user_model):
    """AUTH_PASSWORD_VALIDATORS가 숫자로만 이뤄진 흔한 비밀번호를 거부한다."""
    response = client.post(
        "/accounts/signup/",
        {
            "email": "weakpwduser@example.com",
            "password1": "12345678",
            "password2": "12345678",
            "terms_agreed": "on",
        },
    )
    # 리다이렉트가 아니라 오류와 함께 폼을 다시 렌더해야 한다
    assert response.status_code == 200
    assert not django_user_model.objects.filter(email="weakpwduser@example.com").exists()


@pytest.mark.django_db
def test_이미_가입된_이메일로_다시_가입해도_중복_계정이_생성되지_않는다(client, django_user_model, mailoutbox, valid_password):
    """django-allauth 기본값 ACCOUNT_PREVENT_ENUMERATION=True는 신규 가입과
    똑같은 리다이렉트로 응답한다(응답만 보고 어느 이메일이 가입돼 있는지
    알아낼 수 없도록) — 대신 새 계정을 만들지 않고 기존 계정에 메일로
    알린다.
    """
    django_user_model.objects.create_user(email="existinguser@example.com", password=valid_password)

    response = client.post(
        "/accounts/signup/",
        {
            "email": "existinguser@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )
    assert response.status_code == 302
    assert django_user_model.objects.filter(email="existinguser@example.com").count() == 1
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["existinguser@example.com"]


# ---------------------------------------------------------------------------
# @login_required 리다이렉트
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_비로그인_사용자가_아카이브에_접근하면_next_파라미터와_함께_로그인_페이지로_리다이렉트된다(client):
    response = client.get("/archive/")
    assert response.status_code == 302
    assert response["Location"] == "/accounts/login/?next=/archive/"


@pytest.mark.django_db
def test_비로그인_사용자가_나의_일정_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    response = client.get("/archive/statuses/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_비로그인_사용자가_다녀온_기록_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    response = client.get("/archive/visits/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_로그인_사용자는_아카이브_페이지에_접근할_수_있다(client, make_user):
    user = make_user(username="archive-viewer")
    client.force_login(user)
    response = client.get("/archive/")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 로그인 <-> 가입 링크 사이의 next 보존
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_next_파라미터가_있는_로그인_페이지의_가입_링크는_next를_유지한다(client):
    response = client.get("/accounts/login/?next=/archive/")
    assert response.status_code == 200
    assert b'href="/accounts/signup/?next=%2Farchive%2F"' in response.content


@pytest.mark.django_db
def test_next_파라미터가_있는_가입_페이지의_로그인_링크는_next를_유지한다(client):
    response = client.get("/accounts/signup/?next=/archive/")
    assert response.status_code == 200
    assert b'href="/accounts/login/?next=%2Farchive%2F"' in response.content


@pytest.mark.django_db
def test_next_파라미터가_없는_로그인_페이지의_가입_링크는_next_없이_생성된다(client):
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert b'href="/accounts/signup/"' in response.content
