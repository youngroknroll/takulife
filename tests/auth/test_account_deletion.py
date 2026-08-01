"""계정 삭제 요청(web.views.account.delete_account — 계정설정 에디토리얼
계획 B5에 따라 accounts.views에서 이곳으로 옮겼다. GET 컨텍스트가 이제
archive 카운트를 읽는데 accounts는 archive를 임포트하면 안 되기 때문이다.
비밀번호 잠금 보안 규칙 자체는 여전히 accounts.services가 소유한다).

GET /accounts/delete/는 비밀번호 재확인 폼을 렌더한다(로그인 필요). POST는
현재 비밀번호를 검증한 뒤 accounts.services.request_deletion으로 10일
유예기간 삭제 요청을 기록한다(.docs/plans/2026-07-20-deletion-grace-period-plan.md
참고) — 여기서 계정을 바로 지우지는 않는다. 실제 하드 삭제와 그것이
유발하는 archive 데이터·미디어 연쇄 삭제(archive/models.py,
archive/signals.py 참고)는 accounts.services.execute_pending_deletions에서
일어나며, 이 파일이 아니라 tests/auth/test_account_deletion_purge.py에서
검증한다.
"""
import logging
import time as real_time
from datetime import datetime, timedelta, timezone as dt_timezone

import django.core.cache.backends.base as cache_base
import django.core.cache.backends.db as cache_db
import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone

from accounts import services
from accounts.models import User
from accounts.services import delete_attempts_cache_key
from accounts.signals import cancel_pending_deletion_on_login
from archive.models import (
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)
from events.models import Event

DELETE_URL = "/accounts/delete/"


class _FakeClock:
    """`time` 모듈을 대신하는, 제어 가능한 가짜 시계.

    캐시 백엔드 모듈 두 곳에만 주입한다(세션·로깅 등이 함께 쓰는 프로세스
    전역 `time` 모듈은 건드리지 않는다) — 잠금 창을 빨리 감아도 요청
    사이클이 의존하는 다른 어떤 것에도 새어 나가지 않도록 하기 위해서다.
    """

    def __init__(self, start):
        self._now = start

    def time(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds


@pytest.fixture
def cache_clock(monkeypatch):
    """테스트가 잠들지 않고도 캐시 백엔드가 아는 "지금"을 빨리 감을 수 있게
    한다.

    기본 캐시 백엔드가 LocMemCache에서 DatabaseCache로 바뀌면서
    (config/settings.py CACHES) "지금"을 두 군데에서 따로 읽는다:
    `BaseCache.get_backend_timeout`(base.py)은 만료 시각을 원시
    `time.time() + timeout` epoch 값으로 계산하고, `DatabaseCache.get`/
    `_base_set`(db.py)은 그 만료 시각을 `django.utils.timezone.now()`와
    비교한다 — db.py는 이걸 `from django.utils.timezone import now as
    tz_now`로 임포트해서, import 시점에 함수 객체를 자기 네임스페이스에
    바인딩해 둔다. `django.utils.timezone.now` 자체를 패치해도 db.py에
    이미 바인딩된 `tz_now` 참조에는 닿지 않으므로, `base.py`의 `time` 모듈
    참조와 db.py의 `tz_now` 이름을 둘 다 여기서 같은 가짜 시계로 패치해야
    빨리 감기 아래에서도 만료 설정과 만료 확인이 서로 어긋나지 않는다.

    accounts.services 자신의 고정 창 잠금(is_delete_locked /
    register_failed_delete_attempt)도 `time.time()`을 직접 읽는다(캐시
    백엔드의 TTL을 믿지 않고 자체 마감 시각을 저장한다 — accounts/services.py
    참고), 그래서 그 모듈의 `time` 참조도 함께 패치한다.
    """
    clock = _FakeClock(real_time.time())
    monkeypatch.setattr(cache_base, "time", clock)
    monkeypatch.setattr(
        cache_db,
        "tz_now",
        lambda: datetime.fromtimestamp(
            clock.time(), tz=dt_timezone.utc if settings.USE_TZ else None
        ),
    )
    monkeypatch.setattr(services, "time", clock)
    return clock


@pytest.mark.django_db
@pytest.mark.web
def test_비로그인_사용자가_계정_삭제_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    response = client.get(DELETE_URL)

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
@pytest.mark.web
def test_스태프가_계정_삭제_페이지에_접근하면_403으로_거부된다(client, make_user, valid_password):
    """스태프는 자기 탈퇴가 화면에서 숨겨져 있지만(헤더 링크 없음, §계정
    메뉴 명세) 뷰도 서버 쪽에서 이를 강제해야 한다 — 스태프 계정은 항상
    Django 관리자로만 지우고, 셀프서비스로는 지울 수 없다."""
    staff = make_user(password=valid_password, is_staff=True)
    client.force_login(staff)

    response = client.get(DELETE_URL)

    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.web
def test_스태프의_계정_삭제_요청은_403으로_거부되고_계정이_유지된다(client, make_user, valid_password):
    staff = make_user(password=valid_password, is_staff=True)
    client.force_login(staff)

    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 403
    assert User.objects.filter(pk=staff.pk).exists()


@pytest.mark.django_db
@pytest.mark.web
def test_스태프의_잘못된_비밀번호_요청은_잠금_카운터를_증가시키지_않는다(
    client, make_user, valid_password
):
    """검사 순서 회귀 가드: is_staff 검사는 잠금 카운터보다 먼저 실행돼야
    한다 — 안 그러면 (역할만으로 이미 막힌) 스태프 계정도 반복 POST마다
    _register_failed_delete_attempt를 계속 태워, 어차피 거부될 요청에
    쓸데없는 부작용을 남긴다."""
    staff = make_user(password=valid_password, is_staff=True)
    client.force_login(staff)

    for _ in range(5):
        response = client.post(DELETE_URL, {"password": "definitely-wrong"})
        assert response.status_code == 403

    assert cache.get(delete_attempts_cache_key(staff)) is None


@pytest.mark.django_db
@pytest.mark.web
def test_로그인_사용자가_계정_삭제_페이지에_접근하면_확인_폼이_렌더링된다(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.get(DELETE_URL)

    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.web
def test_잘못된_비밀번호로_계정_삭제를_요청하면_계정이_삭제되지_않는다(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.post(DELETE_URL, {"password": "definitely-wrong"})

    assert response.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
@pytest.mark.slow
def test_다섯_번_잘못된_비밀번호_시도_후에는_올바른_비밀번호도_잠긴다(
    client, make_user, valid_password
):
    """세션을 탈취한 공격자도 비밀번호 검사를 무한정 무차별 대입할 수 없다:
    5번 실패하면 6번째 POST는 (맞는) 비밀번호조차 검사하지 않고 거부되고,
    계정은 살아남는다."""
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(5):
        response = client.post(DELETE_URL, {"password": "definitely-wrong"})
        assert response.status_code == 200

    locked_response = client.post(DELETE_URL, {"password": valid_password})

    assert locked_response.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
@pytest.mark.slow
def test_다섯_번_잘못된_비밀번호_시도_시_잠금_경고가_사용자와_횟수를_포함해_정확히_1회_기록된다(
    client, make_user, valid_password, caplog
):
    """잠금 WARNING은 세션 탈취 무차별 대입 시도가 남기는 유일하게 관측
    가능한 신호다(LOG-01/LOG-02, .docs/plans/2026-07-19-logging-coverage-plan.md
    §4): 시도 예산이 소진되는 순간 정확히 1회만 발생해야 하고, 사용자 pk와
    시도 횟수를 담아야 하며, 비밀번호·세션 키·클라이언트 IP는 절대 새면 안
    된다 — 이미 잠긴 뒤의 추가 실패는 경고를 더 추가하면 안 된다."""
    caplog.set_level(logging.WARNING, logger="accounts.services")
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(5):
        response = client.post(DELETE_URL, {"password": "definitely-wrong"})
        assert response.status_code == 200

    warnings = [record for record in caplog.records if record.name == "accounts.services"]
    assert len(warnings) == 1
    message = warnings[0].getMessage()
    assert str(user.pk) in message
    assert "5" in message
    assert "definitely-wrong" not in message
    session_key = client.session.session_key
    assert session_key is not None
    assert session_key not in message
    assert "127.0.0.1" not in message

    for _ in range(3):
        locked_response = client.post(DELETE_URL, {"password": "definitely-wrong"})
        assert locked_response.status_code == 200

    warnings_after_lockout = [
        record for record in caplog.records if record.name == "accounts.services"
    ]
    assert len(warnings_after_lockout) == 1


@pytest.mark.django_db
@pytest.mark.slow
def test_잠금_상태에서_요청하면_잠시_후_다시_시도하라는_오류가_표시된다(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(5):
        client.post(DELETE_URL, {"password": "definitely-wrong"})

    locked_response = client.post(DELETE_URL, {"password": valid_password})

    body = locked_response.content.decode("utf-8", "ignore")
    assert "잠시 후 다시 시도" in body


@pytest.mark.django_db
@pytest.mark.slow
def test_잠금_후_15분이_지나면_올바른_비밀번호로_다시_탈퇴를_예약할_수_있다(
    client, make_user, valid_password, cache_clock
):
    """잠금은 영구 차단이 아니라 정확히 15분짜리 고정 창이다 — 지나면 맞는
    비밀번호로 다시 탈퇴를 예약할 수 있다(.docs/plans/2026-07-20-deletion-grace-period-plan.md
    DEL-10 참고)."""
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(5):
        client.post(DELETE_URL, {"password": "definitely-wrong"})
    still_locked = client.post(DELETE_URL, {"password": valid_password})
    assert still_locked.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()

    # 15분 창을 막 지난 시점
    cache_clock.advance(60 * 15 + 1)

    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert User.objects.filter(pk=user.pk).exists()
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
@pytest.mark.slow
def test_잠금_창은_이후_실패로_연장되지_않고_최초_실패_시점_기준으로_고정된다(
    client, make_user, valid_password, cache_clock
):
    """고정 창 설계에 대한 회귀 가드: `cache.add` + `incr`가 언젠가 매 쓰기마다
    TTL을 새로고침하는 `cache.get`/`cache.set` 패턴으로 바뀌면, 실패가 생길
    때마다 잠금 창이 계속 밀려나 반복 실패로 계정이 무기한 잠길 수 있다.

    5번의 실패를 나눠서 마지막 4번이 *원래* 창의 끝 근처에 떨어지게 한 뒤,
    (TTL이 새로고침됐다면 아직 안 끝났을) 원래 창 끝을 막 지나서 맞는
    비밀번호가 이미 통하는지 확인한다 — 나중 실패들이 첫 실패가 세운
    창을 연장하지 않았음을 증명한다.
    """
    user = make_user(password=valid_password)
    client.force_login(user)

    # 실패 1, t=0
    client.post(DELETE_URL, {"password": "definitely-wrong"})

    # 원래 창 끝 근처
    cache_clock.advance(60 * 14 + 50)
    # 실패 2~5; 슬라이딩 창이라면 여기서 새로고침될 것
    for _ in range(4):
        client.post(DELETE_URL, {"password": "definitely-wrong"})
    still_locked = client.post(DELETE_URL, {"password": valid_password})
    assert still_locked.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()

    # 이제 *원래* 15분 창을 막 지난 시점
    cache_clock.advance(20)

    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert User.objects.filter(pk=user.pk).exists()
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
@pytest.mark.slow
def test_다섯_번_미만_실패_후_올바른_비밀번호는_탈퇴를_예약한다(
    client, make_user, valid_password
):
    """잠금 문턱 아래에서는 이후의 맞는 비밀번호가 여전히 통해야 한다 —
    비밀번호 검사가 성공하고 나면 실패 카운터가 다음 탈퇴 세션으로 넘어가
    누적되면 안 된다."""
    user = make_user(password=valid_password)
    client.force_login(user)

    for _ in range(3):
        response = client.post(DELETE_URL, {"password": "definitely-wrong"})
        assert response.status_code == 200

    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert User.objects.filter(pk=user.pk).exists()
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
@pytest.mark.slow
def test_한_사용자의_잠금은_다른_사용자의_계정_탈퇴_예약을_막지_않는다(client, make_user, valid_password):
    """한 사용자의 시도 예산 소진이 다른 사용자를 잠그면 안 된다."""
    attacker = make_user(password=valid_password)
    victim = make_user(password=valid_password)

    client.force_login(attacker)
    for _ in range(5):
        client.post(DELETE_URL, {"password": "definitely-wrong"})
    locked_response = client.post(DELETE_URL, {"password": valid_password})
    assert locked_response.status_code == 200
    assert User.objects.filter(pk=attacker.pk).exists()

    client.force_login(victim)
    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert User.objects.filter(pk=victim.pk).exists()
    victim.refresh_from_db()
    assert victim.deletion_requested_at is not None


@pytest.mark.django_db
@pytest.mark.web
def test_계정_삭제_직후_기존_세션으로는_보호된_페이지에_접근할_수_없다(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    client.post(DELETE_URL, {"password": valid_password})

    # 브라우저는 여전히 옛 세션 쿠키를 갖고 있지만 서버 쪽 세션은 이미
    # 비워졌다 — 보호된 페이지는 로그인으로 튕겨야 한다.
    response = client.get("/archive/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
@pytest.mark.web
def test_삭제된_계정으로는_다시_로그인할_수_없다(client, make_user, valid_password):
    """DEL-11: 삭제 요청 POST 하나만으로는 더이상 계정이 지워지지 않는다
    (10일 유예기간) — 그래서 이 테스트는 로그인을 시도하기 전에
    execute_pending_deletions로 유예기간을 지나게 만들어, 기존에 지키던
    "삭제된 계정은 다시 로그인할 수 없다" 동작이 새 정책에서도 여전히
    검증되도록 한다(.docs/plans/2026-07-20-deletion-grace-period-plan.md 참고)."""
    user = make_user(email="leaving@example.com", password=valid_password)
    client.force_login(user)
    client.post(DELETE_URL, {"password": valid_password})
    User.objects.filter(pk=user.pk).update(
        deletion_requested_at=timezone.now() - timedelta(days=10, hours=1)
    )
    services.execute_pending_deletions()

    login_response = client.post(
        "/accounts/login/",
        {"login": "leaving@example.com", "password": valid_password},
    )

    # 인증되지 않고 폼이 다시 렌더됨
    assert login_response.status_code == 200
    archive_response = client.get("/archive/")
    assert archive_response.status_code == 302
    assert "/accounts/login/" in archive_response["Location"]


@pytest.mark.django_db
@pytest.mark.web
def test_올바른_비밀번호로_탈퇴를_요청하면_계정은_유지되고_삭제_예약_시각이_기록된다(
    client, make_user, valid_password
):
    """DEL-01(10일 유예기간): 맞는 비밀번호로 삭제를 요청해도 더이상 계정이
    즉시 하드 삭제되지 않는다 — 계정은 살아남아야 하고, 요청은
    `deletion_requested_at`으로 대기 중 삭제로 기록된다
    (.docs/plans/2026-07-20-deletion-grace-period-plan.md 참고)."""
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert User.objects.filter(pk=user.pk).exists()
    user.refresh_from_db()
    assert user.deletion_requested_at is not None


@pytest.mark.django_db
@pytest.mark.web
def test_탈퇴를_요청하면_다른_기기의_세션도_함께_종료된다(client, make_user, valid_password):
    """DEL-02(10일 유예기간): 탈취됐거나 그냥 로그아웃을 깜빡한 다른 기기의
    세션도 남은 10일 동안 살아남으면 안 된다 — 요청을 보낸 세션만이 아니라
    그 사용자의 모든 세션이 무효화된다(.docs/plans/2026-07-20-deletion-grace-period-plan.md
    참고)."""
    user = make_user(password=valid_password)
    client_a = client
    client_b = Client()
    client_a.force_login(user)
    client_b.force_login(user)

    response = client_a.post(DELETE_URL, {"password": valid_password})
    assert response.status_code == 302

    other_device_response = client_b.get("/archive/")

    assert other_device_response.status_code == 302
    assert "/accounts/login/" in other_device_response["Location"]


@pytest.mark.django_db
@pytest.mark.web
def test_유예_기간_중_다시_로그인하면_탈퇴_예약이_취소되고_안내_메시지가_표시된다(
    client, make_verified_user, valid_password
):
    """DEL-03: 10일 유예기간 중 다시 로그인하는 것 자체가 취소다 — 로그인
    성공이 이미 재인증이므로 별도 확인 단계가 필요 없다
    (.docs/plans/2026-07-20-deletion-grace-period-plan.md 참고). 전용
    픽스처 뒤에 숨기지 않고 accounts.services.request_deletion을 직접
    호출해 대기 중 요청을 준비하므로, 전제 조건이 테스트 본문에 그대로
    드러난다."""
    user = make_verified_user()
    services.request_deletion(user)
    assert user.deletion_requested_at is not None

    response = client.post(
        "/accounts/login/",
        {"login": user.email, "password": valid_password},
        follow=True,
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.deletion_requested_at is None
    messages_text = " ".join(str(message) for message in response.context["messages"])
    assert "취소" in messages_text


@pytest.mark.django_db
@pytest.mark.web
def test_삭제_예약이_없는_사용자가_로그인하면_아무_안내도_표시되지_않는다(
    client, make_verified_user, valid_password
):
    """DEL-04: 대기 중 삭제가 없는 평범한 로그인은 아무 일도 없어야 한다 —
    `cancel_deletion`의 rowcount가 0이면, 로그인-취소-삭제 시그널이 실제로
    일어나지 않은 취소 메시지를 보여주면 안 된다
    (.docs/plans/2026-07-20-deletion-grace-period-plan.md 참고)."""
    user = make_verified_user()
    assert user.deletion_requested_at is None

    response = client.post(
        "/accounts/login/",
        {"login": user.email, "password": valid_password},
        follow=True,
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.deletion_requested_at is None
    messages_text = " ".join(str(message) for message in response.context["messages"])
    assert "취소" not in messages_text


@pytest.mark.django_db
@pytest.mark.web
def test_로그인_시그널이_발화하면_로그인_경로와_무관하게_탈퇴_예약이_취소된다(make_verified_user):
    """DEL-05: 이 리시버 자체의 계약은 경로 독립적이고 request가 없어도
    되는 취소다. `user_logged_in`을 보내지 않고 `cancel_pending_deletion_on_login`을
    직접 호출해 검증한다(같은 시그널의 django-axes 자체 리시버는 진짜
    `request`가 필요해 `request=None`이면 AttributeError를 던지는데, 이건
    이 리시버와 무관한 환경 특성이라 여기서 검증할 대상이 아니다). 시그널
    자체의 배선은 이미 DEL-03의 웹 로그인 경로가 증명한다. `request=None`은
    request가 없을 때의 가드를 검증한다: messages 백엔드를 쓸 수 없으므로
    리시버는 예외를 던지지 말고 알림을 건너뛰어야 한다
    (.docs/plans/2026-07-20-deletion-grace-period-plan.md 참고)."""
    user = make_verified_user()
    services.request_deletion(user)
    assert user.deletion_requested_at is not None

    cancel_pending_deletion_on_login(sender=type(user), request=None, user=user)

    user.refresh_from_db()
    assert user.deletion_requested_at is None


# ---------------------------------------------------------------------------
# 삭제 대상 6종 컨텍스트 (AS-9/AS-10, account-settings-editorial 계획서 B5)
#
# tests/archive/conftest.py의 make_visit/make_entry/make_collection_item/
# make_interest/make_status 팩토리는 tests/auth/ 디렉터리에서 보이지 않으므로
# (conftest.py는 디렉터리 스코프), tests/core/test_mypage_view.py와 같은
# 패턴으로 archive 모델을 직접 생성한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.web
def test_로그인_사용자가_계정_삭제_페이지에_접근하면_삭제_대상_6종이_본인_데이터만_정확히_집계된다(
    client, make_user, png_bytes, valid_password
):
    """6종을 서로 다른 건수로 만든다 — 전부 같은 수면 순서 뒤바뀜 결함을 못
    잡는다(계획서 픽스처 함정 4번). 컬렉션 굿즈는 quantity=0(미보유) 행도
    섞어 total_count가 보유 외 행도 포함함을 전제로 한다(계획서 픽스처
    함정 3번)."""
    user = make_user(password=valid_password)
    other = make_user(password=valid_password)
    event1 = Event.objects.create(title="관심 행사 1")
    event2 = Event.objects.create(title="관심 행사 2")

    # 찜한 행사 = 2건
    EventInterest.objects.create(user=user, event=event1)
    EventInterest.objects.create(user=user, event=event2)

    # 나의 일정 = 1건
    UserEventStatus.objects.create(
        user=user, event=event1, status=UserEventStatus.Status.PLANNED
    )

    # 다녀온 기록 = 3건
    visit1 = VisitRecord.objects.create(user=user, event=event1, visited_on="2026-01-01")
    visit2 = VisitRecord.objects.create(user=user, event=event2, visited_on="2026-01-02")
    VisitRecord.objects.create(user=user, event=event1, visited_on="2026-01-03")

    # 기록 사진 = 4장
    for photo_index in range(2):
        VisitRecordPhoto.objects.create(
            visit_record=visit1,
            image=SimpleUploadedFile(f"v1-{photo_index}.png", png_bytes(), content_type="image/png"),
        )
    for photo_index in range(2):
        VisitRecordPhoto.objects.create(
            visit_record=visit2,
            image=SimpleUploadedFile(f"v2-{photo_index}.png", png_bytes(), content_type="image/png"),
        )

    # 컬렉션 굿즈 = 5건 (보유 4 + 원함 전용/미보유 1)
    for goods_index in range(4):
        CollectionItem.objects.create(user=user, name=f"보유 굿즈 {goods_index}", quantity=1)
    CollectionItem.objects.create(
        user=user, name="원함 전용 굿즈", quantity=0, is_wanted=True
    )

    # 직접 등록 항목 = 6건
    for entry_index in range(6):
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title=f"직접 등록 {entry_index}"
        )

    # 타 사용자 데이터 — 절대 집계되면 안 된다
    EventInterest.objects.create(user=other, event=event1)
    UserEventStatus.objects.create(
        user=other, event=event1, status=UserEventStatus.Status.PLANNED
    )
    VisitRecord.objects.create(user=other, event=event1, visited_on="2026-02-01")
    CollectionItem.objects.create(user=other, name="남의 굿즈")
    PersonalEntry.objects.create(
        user=other, kind=PersonalEntry.Kind.PLACE, title="남의 항목"
    )

    client.force_login(user)

    response = client.get(DELETE_URL)

    targets = response.context["delete_targets"]
    assert [(t["label"], t["count"], t["unit"]) for t in targets] == [
        ("찜한 행사", 2, "건"),
        ("나의 일정", 1, "건"),
        ("다녀온 기록", 3, "건"),
        ("기록 사진", 4, "장"),
        ("컬렉션 굿즈", 5, "건"),
        ("직접 등록 항목", 6, "건"),
    ]


@pytest.mark.django_db
@pytest.mark.web
def test_삭제_대상_데이터가_없는_사용자의_삭제_페이지_카운트는_6종_모두_0이다(
    client, make_user, valid_password
):
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.get(DELETE_URL)

    targets = response.context["delete_targets"]
    assert len(targets) == 6
    assert [t["count"] for t in targets] == [0, 0, 0, 0, 0, 0]


# ---------------------------------------------------------------------------
# delete_targets 회귀 가드 (AS-14/AS-15, H1 — 브라우저 실측으로 드러난 결함:
# POST 실패 경로(비밀번호 오류/락아웃)가 delete_targets 없이 렌더돼 사용자가
# 탈퇴 판단 근거를 잃었다). GET에서 관찰한 실제 값과 비교한다 — 키 존재만
# 확인하면 빈 리스트도 통과하는 무력한 가드가 된다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.web
def test_탈퇴_화면에서_비밀번호를_틀려도_삭제_대상_카운트는_그대로_보인다(
    client, make_user, png_bytes, valid_password
):
    user = make_user(password=valid_password)
    event1 = Event.objects.create(title="오류경로 관심 행사 1")
    event2 = Event.objects.create(title="오류경로 관심 행사 2")

    # 찜한 행사 = 2건
    EventInterest.objects.create(user=user, event=event1)
    EventInterest.objects.create(user=user, event=event2)

    # 나의 일정 = 1건
    UserEventStatus.objects.create(
        user=user, event=event1, status=UserEventStatus.Status.PLANNED
    )

    # 다녀온 기록 = 3건
    visit1 = VisitRecord.objects.create(user=user, event=event1, visited_on="2026-01-01")
    visit2 = VisitRecord.objects.create(user=user, event=event2, visited_on="2026-01-02")
    VisitRecord.objects.create(user=user, event=event1, visited_on="2026-01-03")

    # 기록 사진 = 4장
    for photo_index in range(2):
        VisitRecordPhoto.objects.create(
            visit_record=visit1,
            image=SimpleUploadedFile(
                f"err-v1-{photo_index}.png", png_bytes(), content_type="image/png"
            ),
        )
    for photo_index in range(2):
        VisitRecordPhoto.objects.create(
            visit_record=visit2,
            image=SimpleUploadedFile(
                f"err-v2-{photo_index}.png", png_bytes(), content_type="image/png"
            ),
        )

    # 컬렉션 굿즈 = 5건
    for goods_index in range(4):
        CollectionItem.objects.create(user=user, name=f"오류경로 굿즈 {goods_index}", quantity=1)
    CollectionItem.objects.create(
        user=user, name="오류경로 원함 전용 굿즈", quantity=0, is_wanted=True
    )

    # 직접 등록 항목 = 6건
    for entry_index in range(6):
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title=f"오류경로 직접 등록 {entry_index}"
        )

    client.force_login(user)
    get_response = client.get(DELETE_URL)
    expected_targets = get_response.context["delete_targets"]
    assert [t["count"] for t in expected_targets] == [2, 1, 3, 4, 5, 6]  # 서로 다른 건수 확인

    post_response = client.post(DELETE_URL, {"password": "definitely-wrong"})

    assert post_response.status_code == 200
    assert post_response.context["delete_targets"] == expected_targets


@pytest.mark.django_db
@pytest.mark.web
def test_비밀번호_잠금_상태의_탈퇴_화면에서도_삭제_대상_카운트가_보인다(
    client, make_user, png_bytes, valid_password
):
    user = make_user(password=valid_password)
    event1 = Event.objects.create(title="잠금경로 관심 행사 1")
    event2 = Event.objects.create(title="잠금경로 관심 행사 2")
    event3 = Event.objects.create(title="잠금경로 관심 행사 3")

    # 찜한 행사 = 3건
    EventInterest.objects.create(user=user, event=event1)
    EventInterest.objects.create(user=user, event=event2)
    EventInterest.objects.create(user=user, event=event3)

    # 나의 일정 = 1건
    UserEventStatus.objects.create(
        user=user, event=event1, status=UserEventStatus.Status.PLANNED
    )

    # 다녀온 기록 = 2건
    visit1 = VisitRecord.objects.create(user=user, event=event1, visited_on="2026-01-01")
    VisitRecord.objects.create(user=user, event=event2, visited_on="2026-01-02")

    # 기록 사진 = 5장
    for photo_index in range(5):
        VisitRecordPhoto.objects.create(
            visit_record=visit1,
            image=SimpleUploadedFile(
                f"lock-{photo_index}.png", png_bytes(), content_type="image/png"
            ),
        )

    # 컬렉션 굿즈 = 4건
    for goods_index in range(4):
        CollectionItem.objects.create(user=user, name=f"잠금경로 굿즈 {goods_index}", quantity=1)

    # 직접 등록 항목 = 6건
    for entry_index in range(6):
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title=f"잠금경로 직접 등록 {entry_index}"
        )

    client.force_login(user)
    get_response = client.get(DELETE_URL)
    expected_targets = get_response.context["delete_targets"]
    assert [t["count"] for t in expected_targets] == [3, 1, 2, 5, 4, 6]  # 서로 다른 건수 확인

    for _ in range(5):
        client.post(DELETE_URL, {"password": "definitely-wrong"})
    locked_response = client.post(DELETE_URL, {"password": valid_password})

    assert locked_response.status_code == 200
    assert locked_response.context["delete_targets"] == expected_targets
