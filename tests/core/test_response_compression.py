"""응답 GZip 압축(트랙 13-B) 계약: 미들웨어 순서와 협상 동작을 검증한다.
BREACH 완화는 Django 내장 GZipMiddleware가 이미 제공한다 — 응답마다 무작위
패딩을 넣고 200바이트 미만 응답은 압축을 건너뛰므로, 압축 바이트 길이나
본문 내용을 직접 비교하는 단언은 비결정적이라 쓰지 않는다."""
import importlib

import pytest


@pytest.mark.contract
def test_GZip_미들웨어는_SecurityMiddleware_다음_WhiteNoise_미들웨어_바로_앞에_등록된다():
    settings_module = importlib.import_module("config.settings")

    middleware = settings_module.MIDDLEWARE
    security_index = middleware.index("django.middleware.security.SecurityMiddleware")

    assert middleware[security_index + 1] == "django.middleware.gzip.GZipMiddleware"
    assert middleware[security_index + 2] == "whitenoise.middleware.WhiteNoiseMiddleware"


@pytest.mark.web
@pytest.mark.django_db
def test_gzip을_지원하는_요청은_충분히_큰_HTML_응답을_압축해서_받는다(client):
    response = client.get("/", HTTP_ACCEPT_ENCODING="gzip")

    assert response.status_code == 200
    assert response["Content-Encoding"] == "gzip"
    assert "Accept-Encoding" in response["Vary"]


@pytest.mark.web
@pytest.mark.django_db
def test_gzip을_지원하지_않는_요청은_압축되지_않은_원본_응답을_받는다(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Content-Encoding" not in response
