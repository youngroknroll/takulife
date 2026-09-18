"""core.models.ErrorGroup / core.error_groups.sanitize_message 검증
(트랙 36 오류 묶음 기록, prompt_plan.md 트랙 36 S1·S2 참고).
"""
import logging
import sys
from datetime import timedelta
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, connection, transaction
from django.utils import timezone

import pytest

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_오류_묶음은_허용되지_않은_출처면_유효성_검증에_실패한다():
    from core.models import ErrorGroup

    group = ErrorGroup(
        source="unknown",
        fingerprint="a" * 64,
        error_type="X",
        location="Y",
        message_sample="Z",
    )

    with pytest.raises(ValidationError):
        group.full_clean()


@pytest.mark.django_db
def test_오류_묶음은_같은_지문으로_두_번_생성하면_무결성_오류가_난다():
    from core.models import ErrorGroup

    fingerprint = "b" * 64
    ErrorGroup.objects.create(
        source=ErrorGroup.Source.BACKEND,
        fingerprint=fingerprint,
        error_type="ValueError",
        location="POST /events/",
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ErrorGroup.objects.create(
                source=ErrorGroup.Source.BACKEND,
                fingerprint=fingerprint,
                error_type="ValueError",
                location="POST /events/",
            )


def _설정된_시크릿_키(settings, monkeypatch):
    settings.SECRET_KEY = "s3cr3t-value-xyz"
    return settings.SECRET_KEY


def _설정된_앤트로픽_키(settings, monkeypatch):
    settings.ANTHROPIC_API_KEY = "anthropic-secret-value"
    return settings.ANTHROPIC_API_KEY


def _설정된_러너_토큰(settings, monkeypatch):
    settings.DRAFT_DISCOVERY_RUNNER_TOKEN = "runner-secret-value"
    return settings.DRAFT_DISCOVERY_RUNNER_TOKEN


def _설정된_DB_비밀번호(settings, monkeypatch):
    # settings.DATABASES 전체를 덮어쓰면 Django가
    # "Overriding setting DATABASES can lead to unexpected behavior" 경고를
    # 낸다 — 딕셔너리 항목 하나만 몽키패치한다.
    monkeypatch.setitem(settings.DATABASES["default"], "PASSWORD", "db-secret-value")
    return "db-secret-value"


@pytest.mark.unit
def test_오류_메시지_정제는_제어문자를_없애고_이메일을_가리고_URL_쿼리를_지우고_500자로_자른다():
    from core.error_groups import sanitize_message

    raw = (
        "line1\r\nline2\x07 contact test.user@example.com or visit "
        "https://example.com/path?token=abc&x=1#frag" + ("!" * 500)
    )

    result = sanitize_message(raw)

    assert "\r" not in result and "\n" not in result and "\x07" not in result
    assert "test.user@example.com" not in result
    assert "[email]" in result
    assert "https://example.com/path" in result
    assert "?token=" not in result and "#frag" not in result
    assert len(result) <= 500


@pytest.mark.unit
def test_오류_메시지_정제는_지울_것이_없어도_500자를_넘으면_정확히_500자로_자른다():
    from core.error_groups import sanitize_message

    result = sanitize_message("x" * 600)

    assert len(result) == 500


@pytest.mark.unit
@pytest.mark.parametrize(
    "apply_secret",
    [_설정된_시크릿_키, _설정된_앤트로픽_키, _설정된_러너_토큰, _설정된_DB_비밀번호],
    ids=["SECRET_KEY", "ANTHROPIC_API_KEY", "DRAFT_DISCOVERY_RUNNER_TOKEN", "DB_PASSWORD"],
)
def test_오류_메시지_정제는_설정된_시크릿_값이_섞이면_메시지_전체를_비운다(settings, monkeypatch, apply_secret):
    from core.error_groups import sanitize_message

    secret_value = apply_secret(settings, monkeypatch)
    message = f"failed with token {secret_value} while processing request"

    assert sanitize_message(message) == ""


@pytest.mark.unit
def test_오류_메시지_정제는_시크릿_값이_빈_문자열이면_모든_메시지를_비우지_않는다(settings):
    from core.error_groups import sanitize_message

    settings.DRAFT_DISCOVERY_RUNNER_TOKEN = ""

    assert sanitize_message("아무 메시지나 온다") != ""


@pytest.mark.django_db
def test_오류_기록은_새_지문이면_한_행을_생성하고_count가_1이다():
    from core.error_groups import record_error
    from core.models import ErrorGroup

    record_error(source="backend", error_type="KeyError", location="GET /x/", message="boom")

    group = ErrorGroup.objects.get()
    assert group.count == 1
    assert group.last_seen >= group.first_seen


@pytest.mark.django_db
def test_오류_기록은_같은_지문이면_한_행에서_count를_늘리고_최신_메시지와_last_seen을_갱신한다():
    from core.error_groups import record_error
    from core.models import ErrorGroup

    record_error(source="backend", error_type="KeyError", location="GET /x/", message="boom")
    first = ErrorGroup.objects.get()

    record_error(source="backend", error_type="KeyError", location="GET /x/", message="boom again")

    assert ErrorGroup.objects.count() == 1
    group = ErrorGroup.objects.get()
    assert group.count == 2
    assert group.message_sample == "boom again"
    assert group.last_seen >= first.last_seen


@pytest.mark.django_db
def test_오류_기록_저장이_실패해도_예외를_전파하지_않고_경고_로그를_한_줄_남긴다(monkeypatch, caplog):
    from core.error_groups import record_error
    from core.models import ErrorGroup

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated persistence outage")

    monkeypatch.setattr(ErrorGroup.objects, "filter", _boom)

    with caplog.at_level(logging.WARNING, logger="core.error_groups"):
        record_error(
            source="backend",
            error_type="KeyError",
            location="GET /x/",
            message="boom\nwith newline",
        )

    assert ErrorGroup.objects.count() == 0
    warning_records = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warning_records) == 1
    logged_message = warning_records[0].getMessage()
    assert logged_message.startswith("error-group record failed")
    assert "\n" not in logged_message


@pytest.mark.django_db
def test_오류_기록은_깨진_트랜잭션_안에서_호출해도_예외를_전파하지_않는다():
    from core.error_groups import record_error
    from core.models import ErrorGroup

    fingerprint = "c" * 64

    with transaction.atomic():
        ErrorGroup.objects.create(
            source=ErrorGroup.Source.BACKEND,
            fingerprint=fingerprint,
            error_type="ValueError",
            location="POST /events/",
        )
        try:
            ErrorGroup.objects.create(
                source=ErrorGroup.Source.BACKEND,
                fingerprint=fingerprint,
                error_type="ValueError",
                location="POST /events/",
            )
        except IntegrityError:
            pass

        # 세이브포인트 없이 여기서 IntegrityError를 잡았으므로(PostgreSQL)
        # 이 트랜잭션은 이미 깨져 있다 — 이 상태에서도 record_error는
        # 예외를 전파하면 안 된다.
        record_error(
            source="backend",
            error_type="OtherError",
            location="GET /y/",
            message="boom",
        )


@pytest.mark.django_db
def test_오류_기록_내부_DB_오류가_호출자의_같은_트랜잭션을_깨뜨리지_않는다(monkeypatch):
    from core.error_groups import record_error
    from core.models import ErrorGroup

    def _abort_transaction_with_real_db_error(*args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1/0")
        return ErrorGroup.objects.none()  # 도달하지 않음 — 위 execute가 먼저 실패한다

    with transaction.atomic():
        monkeypatch.setattr(ErrorGroup.objects, "filter", _abort_transaction_with_real_db_error)

        record_error(source="backend", error_type="KeyError", location="GET /x/", message="boom")

        # 세이브포인트가 record_error 내부 DB 오류를 이 함수 하나로
        # 격리했다면, 같은 atomic 블록 안에서도 다른 조회가 예외 없이
        # 실행되어야 한다 — 세이브포인트가 없으면 이 줄이
        # TransactionManagementError로 실패한다.
        assert ErrorGroup.objects.count() == 0


@pytest.mark.django_db
def test_오류_기록은_생성_직전_동시에_같은_지문이_생겨도_count에_반영된다(monkeypatch, caplog):
    from core.error_groups import record_error
    from core.models import ErrorGroup

    original_filter = ErrorGroup.objects.filter
    original_create = ErrorGroup.objects.create
    state = {"first_filter_seen": False}

    def _filter_with_concurrent_insert_on_first_call(*args, **kwargs):
        if not state["first_filter_seen"]:
            state["first_filter_seen"] = True
            # 실제 경합처럼, 다른 트랜잭션이 이미 커밋해 둔 행을 흉내
            # 낸다 — record_error의 세이브포인트 밖(그 이전)에서 원래
            # create로 직접 만들어야, 나중에 IntegrityError가 나도 이
            # 행이 롤백으로 사라지지 않는다.
            original_create(
                source="backend",
                fingerprint=kwargs["fingerprint"],
                error_type="KeyError",
                location="GET /x/",
                message_sample="",
                count=1,
            )
            return ErrorGroup.objects.none()
        return original_filter(*args, **kwargs)

    monkeypatch.setattr(ErrorGroup.objects, "filter", _filter_with_concurrent_insert_on_first_call)

    with caplog.at_level(logging.WARNING, logger="core.error_groups"):
        record_error(source="backend", error_type="KeyError", location="GET /x/", message="boom")

    assert ErrorGroup.objects.count() == 1
    group = ErrorGroup.objects.get()
    assert group.count == 2
    warning_records = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert warning_records == []


@pytest.mark.django_db
def test_오류_기록은_출처별_상한을_넘으면_그_출처의_최고령_행만_지운다(monkeypatch):
    import core.error_groups as error_groups_module
    from core.error_groups import record_error
    from core.models import ErrorGroup

    # SOURCE_GROUP_LIMIT(기본 250, 승인 범위 S2)를 테스트 규모로 낮춘다.
    monkeypatch.setattr(error_groups_module, "SOURCE_GROUP_LIMIT", 3)

    now = timezone.now()
    record_error(source="backend", error_type="Existing", location="GET /existing/", message="기존 오류")
    anchor = ErrorGroup.objects.get(location="GET /existing/")

    oldest, newer = ErrorGroup.objects.bulk_create(
        [
            ErrorGroup(
                source=ErrorGroup.Source.BACKEND,
                fingerprint="backend-filler-oldest".ljust(64, "0"),
                error_type="Filler",
                location="GET /filler-oldest/",
                message_sample="",
                first_seen=now - timedelta(minutes=10),
                last_seen=now - timedelta(minutes=10),
                count=1,
            ),
            ErrorGroup(
                source=ErrorGroup.Source.BACKEND,
                fingerprint="backend-filler-newer".ljust(64, "0"),
                error_type="Filler",
                location="GET /filler-newer/",
                message_sample="",
                first_seen=now - timedelta(minutes=5),
                last_seen=now - timedelta(minutes=5),
                count=1,
            ),
        ]
    )

    assert ErrorGroup.objects.filter(source=ErrorGroup.Source.BACKEND).count() == 3

    record_error(source="backend", error_type="New", location="GET /new/", message="새 오류")

    backend_groups = ErrorGroup.objects.filter(source=ErrorGroup.Source.BACKEND)
    assert backend_groups.count() == 3
    assert not backend_groups.filter(fingerprint=oldest.fingerprint).exists()
    assert backend_groups.filter(location="GET /new/").exists()
    assert backend_groups.filter(fingerprint=newer.fingerprint).exists()
    assert backend_groups.filter(fingerprint=anchor.fingerprint).exists()

    # 기존 지문 갱신(count 증가)은 새 행을 만들지 않으므로 상한 삭제를
    # 일으키지 않는다.
    record_error(source="backend", error_type="Existing", location="GET /existing/", message="기존 오류 다시")

    assert ErrorGroup.objects.filter(source=ErrorGroup.Source.BACKEND).count() == 3


@pytest.mark.django_db
def test_오류_기록의_출처별_상한은_다른_출처_행에_영향을_주지_않는다(monkeypatch):
    import core.error_groups as error_groups_module
    from core.error_groups import record_error
    from core.models import ErrorGroup

    monkeypatch.setattr(error_groups_module, "SOURCE_GROUP_LIMIT", 3, raising=False)

    now = timezone.now()
    # backend 행을 frontend 행보다 더 오래되게 시딩한다 — 상한 삭제가
    # 출처를 무시하고 "전체 최고령"을 지운다면 이 backend 행이 지워져야
    # 정상인데, 그러면 안 된다(출처별 상한이므로).
    backend_rows = ErrorGroup.objects.bulk_create(
        [
            ErrorGroup(
                source=ErrorGroup.Source.BACKEND,
                fingerprint=f"backend-existing-{i}".ljust(64, "0"),
                error_type="Existing",
                location=f"GET /backend-{i}/",
                message_sample="",
                first_seen=now - timedelta(minutes=60 - i),
                last_seen=now - timedelta(minutes=60 - i),
                count=1,
            )
            for i in range(2)
        ]
    )
    oldest_frontend, *_rest = ErrorGroup.objects.bulk_create(
        [
            ErrorGroup(
                source=ErrorGroup.Source.FRONTEND,
                fingerprint=f"frontend-existing-{i}".ljust(64, "0"),
                error_type="Existing",
                location=f"GET /frontend-{i}/",
                message_sample="",
                first_seen=now - timedelta(minutes=10 - i),
                last_seen=now - timedelta(minutes=10 - i),
                count=1,
            )
            for i in range(3)
        ]
    )

    record_error(source="frontend", error_type="New", location="GET /frontend-new/", message="새 오류")

    backend_groups = ErrorGroup.objects.filter(source=ErrorGroup.Source.BACKEND)
    frontend_groups = ErrorGroup.objects.filter(source=ErrorGroup.Source.FRONTEND)
    assert backend_groups.count() == 2
    assert {row.fingerprint for row in backend_rows} == set(
        backend_groups.values_list("fingerprint", flat=True)
    )
    assert frontend_groups.count() == 3
    assert not frontend_groups.filter(fingerprint=oldest_frontend.fingerprint).exists()
    assert frontend_groups.filter(location="GET /frontend-new/").exists()


def _record_without_exc_info():
    return logging.LogRecord(
        "django.request", logging.ERROR, __file__, 1,
        "Internal Server Error: %s", ("/x/",), None,
    )


def _record_with_exc_info(exc, *, request=None):
    try:
        raise exc
    except type(exc):
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        "django.request", logging.ERROR, __file__, 1,
        "Internal Server Error: %s", ("/x/",), exc_info,
    )
    if request is not None:
        record.request = request
    return record


@pytest.mark.django_db
def test_오류_묶음_핸들러는_exc_info_없는_레코드를_무시한다():
    from core.logging import ErrorGroupHandler
    from core.models import ErrorGroup

    ErrorGroupHandler().emit(_record_without_exc_info())

    assert ErrorGroup.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "resolver_match, expected_location",
    [
        (SimpleNamespace(route="api/items/<int:pk>/"), "GET api/items/<int:pk>/"),
        (None, "GET unresolved"),
    ],
    ids=["resolved", "unresolved"],
)
def test_오류_묶음_핸들러는_예외_레코드에서_error_type과_location을_뽑는다(
    resolver_match, expected_location
):
    from core.logging import ErrorGroupHandler
    from core.models import ErrorGroup

    fake_request = SimpleNamespace(method="GET", resolver_match=resolver_match)
    record = _record_with_exc_info(KeyError("k"), request=fake_request)

    ErrorGroupHandler().emit(record)

    group = ErrorGroup.objects.get()
    assert group.error_type == "KeyError"
    assert group.location == expected_location
    assert group.source == ErrorGroup.Source.BACKEND


@pytest.mark.django_db
def test_오류_묶음_핸들러는_DB_오류면_record_error를_부르지_않는다(monkeypatch):
    from core.logging import ErrorGroupHandler

    # fail_if_called를 쓰면 핸들러가 예외를 삼키는 결함(제거됨)에서도 통과해
    # 버려서 방어가 되지 않는다 — 실제 호출 여부를 직접 기록해 확인한다.
    calls = []
    monkeypatch.setattr("core.error_groups.record_error", lambda **kwargs: calls.append(kwargs))
    fake_request = SimpleNamespace(method="GET", resolver_match=None)
    record = _record_with_exc_info(OperationalError("db down"), request=fake_request)

    ErrorGroupHandler().emit(record)

    assert calls == []


@pytest.mark.contract
def test_뷰가_처리되지_않은_예외를_던지면_500_응답과_함께_오류_묶음이_한_행_생긴다(client, monkeypatch, db):
    """tests/core/test_error_pages.py:25-51과 같은 방식으로 실제 뷰 예외를
    흉내낸다 — settings.LOGGING에 ErrorGroupHandler를 아직 배선하지 않았으므로
    이 테스트는 지금 0 == 1로 실패해야 정상이다(S3 배선 전 예상 Red)."""
    from core.models import ErrorGroup

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated view failure")

    monkeypatch.setattr("web.views.events.list_published_events", _boom)
    client.raise_request_exception = False

    resp = client.get("/")

    assert resp.status_code == 500
    assert ErrorGroup.objects.count() == 1
    assert ErrorGroup.objects.get().error_type == "RuntimeError"
