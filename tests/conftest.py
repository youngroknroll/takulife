"""공용 pytest 픽스처 — 객체를 만들어 주는 팩토리들.

픽스처가 객체가 아니라 함수를 돌려주므로 각 테스트가 필요한 값만 직접 넘긴다.
고정된 공용 객체를 쓰면 테스트가 무엇을 검증하는지 픽스처가 몰래 바꾼다.
"""
import io
import secrets
import string

import PIL.Image
import pytest
from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.db.utils import Error as DjangoDatabaseError
from django.test import Client

from drafts.models import DraftSource, EventDraft
from events.models import Event


@pytest.fixture
def clear_cache(db):
    """호출 횟수 제한 상태를 테스트 사이에서 끊는다. 캐시에 쌓인 횟수를 직접
    읽거나 단언하는 테스트만 이 픽스처를 요청하면 된다.

    모든 테스트에 자동 적용하지 않는 이유는, 캐시가 DB에 저장돼 있어
    `django_db` 테스트의 트랜잭션이 캐시 쓰기까지 되돌려 주기 때문이다.
    대부분은 그냥 두어도 서로 간섭하지 않는다.

    `db` 픽스처에 의존하는 것은 캐시 비우기 자체가 DB 연결을 쓰기 때문이다.

    마무리 단계의 비우기를 예외로 감싼 이유: DB 장애를 일부러 흉내 내는
    테스트가 그 흉내를 끝까지 유지한 채 이 픽스처의 마무리로 들어온다.
    캐시 정리는 검증 대상이 아니므로, 여기서 난 DB 오류가 그 테스트를
    엉뚱하게 실패시키면 안 된다.
    """
    cache.clear()
    yield
    try:
        cache.clear()
    except DjangoDatabaseError:
        pass


@pytest.fixture
def make_event(db):
    def _make(**kwargs):
        defaults = {"title": "Test Event", "publish_status": Event.PublishStatus.PUBLISHED}
        return Event.objects.create(**{**defaults, **kwargs})

    return _make


@pytest.fixture
def make_draft_event(make_event):
    def _make(**kwargs):
        return make_event(**{"publish_status": Event.PublishStatus.DRAFT, **kwargs})

    return _make


@pytest.fixture
def make_user(db, django_user_model):
    def _make(email=None, password=None, **kwargs):
        email = email or f"user_{secrets.token_hex(4)}@example.com"
        # 비밀번호를 안 넘기면 로그인 불가 상태로 만든다 — 해시 계산이 없어
        # 빠르고, 대부분의 테스트는 비밀번호로 로그인하지 않는다. 실제 로그인이
        # 필요한 테스트만 자기 비밀번호를 넘긴다.
        return django_user_model.objects.create_user(
            email=email, password=password, **kwargs
        )

    return _make


@pytest.fixture
def user_client(make_user):
    """(user, force_login된 Client) 팩토리 — 파일마다 복제되던 _login 헬퍼를 대체."""
    def _make(user=None, **user_kwargs):
        user = user or make_user(**user_kwargs)
        client = Client()
        client.force_login(user)
        return user, client

    return _make


@pytest.fixture
def staff_client(user_client):
    """(staff_user, force_login된 Client) 팩토리. is_superuser 등은 kwargs로 통과."""
    def _make(**user_kwargs):
        return user_client(is_staff=True, **user_kwargs)

    return _make


@pytest.fixture
def png_bytes():
    def _make(width=10, height=10, color=(255, 0, 0)):
        buf = io.BytesIO()
        PIL.Image.new("RGB", (width, height), color=color).save(buf, format="PNG")
        return buf.getvalue()

    return _make


@pytest.fixture
def make_draft(db):
    def _make(source_url=None, **kwargs):
        # source_url은 유일해야 해서 값을 안 주면 만들어 넣는다.
        # 빈 문자열을 일부러 넘긴 경우는 그대로 두려고 None만 검사한다.
        if source_url is None:
            source_url = f"https://example.com/{secrets.token_hex(4)}"
        return EventDraft.objects.create(source_url=source_url, **kwargs)

    return _make


@pytest.fixture
def make_source(db):
    def _make(**overrides):
        defaults = {
            "name": "Test Source",
            "url": "https://example.com/feed.xml",
            "source_type": DraftSource.SourceType.RSS,
            "enabled": True,
        }
        return DraftSource.objects.create(**{**defaults, **overrides})

    return _make


@pytest.fixture
def fail_if_called():
    """불리면 테스트를 실패시키는 대역. 어떤 경로가 아예 실행되지 않음을
    확인할 때 그 자리에 끼워 넣는다."""
    def _fn(*args, **kwargs):
        raise AssertionError("this collaborator must not be called")

    return _fn


@pytest.fixture(scope="session")
def valid_password():
    """`secrets`로 실행 시점에 조립하는 일회용 비밀번호(대문자+소문자+숫자+
    무작위 꼬리를 보장). 소스에 비밀번호 리터럴이 없으니 시크릿 스캐너가
    걸릴 게 없고, 무작위 접미사와 무관하게 조합 자체가
    AUTH_PASSWORD_VALIDATORS를 만족한다.

    세션 스코프: axes/rate-limit 테스트는 한 테스트 안에서 같은 비밀번호를
    여러 요청에 걸쳐 제출하는데, 값 자체의 무작위성은 검증 대상이 아니므로
    생성된 비밀번호 하나를 실행 전체에서 공유해도 된다. 순수 문자열
    생성만 하고 `db`는 쓰지 않는다 — 함수 스코프 픽스처는 세션 스코프
    픽스처가 의존할 수 없기 때문이다.
    """
    return (
        secrets.choice(string.ascii_uppercase)
        + secrets.choice(string.ascii_lowercase)
        + secrets.choice(string.digits)
        + secrets.token_urlsafe(16)
    )


@pytest.fixture
def make_verified_user(db, django_user_model, valid_password):
    def _make(email=None, password=None, **kwargs):
        email = email or f"user_{secrets.token_hex(4)}@example.com"
        password = password or valid_password
        user = django_user_model.objects.create_user(email=email, password=password, **kwargs)
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        return user

    return _make
