"""POST /api/client-errors/ — 프론트 오류 보고 수집(트랙 36 S5, EG-16~).

계획 승인 범위: 인증 없음, 정상 페이로드는 항상 204(정보 비노출), 허용된
키만 사용, ErrorGroup에 source="frontend"로 한 행을 남긴다.
"""
import json

import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_정상_페이로드는_204를_받고_프론트_오류_묶음_한_행이_생긴다(client):
    from core.models import ErrorGroup

    payload = {
        "message": "TypeError: x is undefined",
        "name": "TypeError",
        "script": "/static/js/pages/home.js",
        "line": 12,
        "col": 5,
    }

    resp = client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )

    assert resp.status_code == 204
    group = ErrorGroup.objects.get()
    assert group.source == ErrorGroup.Source.FRONTEND
    assert group.error_type == "js:TypeError"
    assert group.location == "/static/js/pages/home.js:12"


_VALID_PAYLOAD = {
    "message": "TypeError: x is undefined",
    "name": "TypeError",
    "script": "/static/js/pages/home.js",
    "line": 12,
    "col": 5,
}


def _다른_출처_요청(client):
    return client.post(
        "/api/client-errors/",
        data=json.dumps(_VALID_PAYLOAD),
        content_type="application/json",
        HTTP_ORIGIN="https://evil.example",
    )


def _origin_없이_다른_referer(client):
    return client.post(
        "/api/client-errors/",
        data=json.dumps(_VALID_PAYLOAD),
        content_type="application/json",
        HTTP_REFERER="https://evil.example/page",
    )


def _origin도_referer도_없음(client):
    return client.post(
        "/api/client-errors/",
        data=json.dumps(_VALID_PAYLOAD),
        content_type="application/json",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "make_request",
    [_다른_출처_요청, _origin_없이_다른_referer, _origin도_referer도_없음],
    ids=["다른_Origin", "Origin없음_Referer다른출처", "둘_다_없음"],
)
def test_같은_출처가_아니면_204만_주고_기록하지_않는다(client, make_request):
    from core.models import ErrorGroup

    resp = make_request(client)

    assert resp.status_code == 204
    assert ErrorGroup.objects.count() == 0


def _본문_4KB_초과(client):
    oversized_message = "x" * 5000
    payload = {**_VALID_PAYLOAD, "message": oversized_message}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _JSON이_아님(client):
    return client.post(
        "/api/client-errors/",
        data="not json",
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _비UTF8_바이트(client):
    return client.post(
        "/api/client-errors/",
        data=b"\xff\xfe",
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _허용_외_키(client):
    payload = {"message": "x", "cookie": "y"}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _최상위가_리스트(client):
    return client.post(
        "/api/client-errors/",
        data=json.dumps([_VALID_PAYLOAD]),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _message가_숫자(client):
    payload = {**_VALID_PAYLOAD, "message": 123}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _line이_문자열(client):
    payload = {**_VALID_PAYLOAD, "line": "12"}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _line이_불리언(client):
    payload = {**_VALID_PAYLOAD, "line": True}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _script_누락(client):
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "script"}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _line_누락(client):
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "line"}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _message_누락(client):
    payload = {k: v for k, v in _VALID_PAYLOAD.items() if k != "message"}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _name이_숫자(client):
    # 타입 검사가 없으면 error_type이 "js:123"으로 그대로 기록돼 버린다 —
    # sanitize_message처럼 예외로 걸러지지 않고 str(name)이 조용히 성공한다.
    payload = {**_VALID_PAYLOAD, "name": 123}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


def _script가_숫자(client):
    payload = {**_VALID_PAYLOAD, "script": 7}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "make_request",
    [
        _본문_4KB_초과,
        _JSON이_아님,
        _비UTF8_바이트,
        _허용_외_키,
        _최상위가_리스트,
        _message가_숫자,
        _line이_문자열,
        _line이_불리언,
        _script_누락,
        _line_누락,
        _message_누락,
        _name이_숫자,
        _script가_숫자,
    ],
    ids=[
        "4KB초과",
        "JSON아님",
        "비UTF8",
        "허용외키",
        "최상위리스트",
        "message가_숫자",
        "line이_문자열",
        "line이_불리언",
        "script_누락",
        "line_누락",
        "message_누락",
        "name이_숫자",
        "script가_숫자",
    ],
)
def test_형식이_어긋난_요청은_204만_주고_기록도_500도_없다(client, make_request):
    from core.models import ErrorGroup

    resp = make_request(client)

    assert resp.status_code == 204
    assert ErrorGroup.objects.count() == 0


def _post_valid(client, **overrides):
    payload = {**_VALID_PAYLOAD, **overrides}
    return client.post(
        "/api/client-errors/",
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_ORIGIN="http://testserver",
    )


@pytest.mark.contract
@pytest.mark.django_db
def test_전역_스로틀을_넘으면_204만_주고_기록은_상한까지만_늘어난다(client, clear_cache, monkeypatch):
    """ScopedRateThrottle은 요청마다 `self.rate = self.THROTTLE_RATES[self.scope]`로
    매번 클래스 딕셔너리를 다시 읽으므로(rest_framework/throttling.py),
    인스턴스 rate 속성이 아니라 클래스 THROTTLE_RATES 딕셔너리 항목을
    monkeypatch.setitem으로 주입하는 편이 실제 결정 경로와 맞는다."""
    from core.client_error_views import GlobalClientErrorThrottle
    from core.models import ErrorGroup

    monkeypatch.setitem(GlobalClientErrorThrottle.THROTTLE_RATES, "client_error_report", "2/hour")

    for _ in range(3):
        resp = _post_valid(client)
        assert resp.status_code == 204

    assert ErrorGroup.objects.get().count == 2


@pytest.mark.django_db
def test_새_묶음은_시간당_상한을_넘으면_더_생기지_않지만_기존_묶음_갱신은_막지_않는다(
    client, clear_cache, monkeypatch
):
    """NEW_GROUP_HOURLY_LIMIT(기본 20)를 테스트 규모로 낮춰, 서로 다른
    지문 3개 중 상한을 넘는 세 번째는 새 행을 만들지 않고, 기존 지문
    재보고는 상한과 무관하게 count만 늘어남을 확인한다."""
    import core.client_error_views as client_error_views_module
    from core.models import ErrorGroup

    monkeypatch.setattr(client_error_views_module, "NEW_GROUP_HOURLY_LIMIT", 2)

    for script in ["/static/js/a.js", "/static/js/b.js", "/static/js/c.js"]:
        resp = _post_valid(client, script=script)
        assert resp.status_code == 204

    assert ErrorGroup.objects.count() == 2

    resp = _post_valid(client, script="/static/js/a.js")

    assert resp.status_code == 204
    assert ErrorGroup.objects.filter(location__startswith="/static/js/a.js").get().count == 2


@pytest.mark.django_db
def test_name에_개행이_있어도_204를_받고_저장된_error_type에_개행이_없다(client):
    from core.models import ErrorGroup

    resp = _post_valid(client, name="Type\nError")

    assert resp.status_code == 204
    group = ErrorGroup.objects.get()
    assert "\n" not in group.error_type


@pytest.mark.django_db
def test_본문이_업로드_상한을_넘으면_204만_주고_기록하지_않는다(client, settings):
    """DATA_UPLOAD_MAX_MEMORY_SIZE를 페이로드보다 작게 낮추면
    request.body 접근에서 Django가 RequestDataTooBig을 던진다 —
    "항상 204" 계약이 이 경로에서도 지켜지는지 확인한다."""
    from core.models import ErrorGroup

    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 100

    resp = _post_valid(client)

    assert resp.status_code == 204
    assert ErrorGroup.objects.count() == 0


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw_path, expected",
    [
        ("/events/12/", "/events/:id/"),
        (
            "/archive/items/3f2b1c9e-8d7a-4b6c-9e1f-2a3b4c5d6e7f/",
            "/archive/items/:id/",
        ),
        ("/static/js/pages/home.js", "/static/js/pages/home.js"),
        ("/static/js/pages/home.js?v=3#x", "/static/js/pages/home.js"),
    ],
    ids=["숫자_세그먼트", "UUID_세그먼트", "정적파일_그대로", "쿼리_제거"],
)
def test_경로_정규화는_숫자와_UUID_세그먼트를_id로_바꾸고_쿼리를_지운다(raw_path, expected):
    """normalize_path는 아직 core.client_error_views에 없다 — 이 임포트
    자체가 Red(ImportError)다."""
    from core.client_error_views import normalize_path

    assert normalize_path(raw_path) == expected
