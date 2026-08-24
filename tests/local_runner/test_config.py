"""local_runner.config 단위 테스트 — 서버 URL 스킴/루프백 검증.

허용 케이스(파라미터 2)는 현재 load_config가 스킴 검증을 전혀 하지 않으므로
이미 통과(회귀 고정용)이고, 거부 케이스(파라미터 1)가 이번 트랙의 Red다.
"""
import pytest

from local_runner.config import load_config


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "server_url",
    [
        pytest.param("http://runner.example.com", id="비루프백_http"),
        pytest.param("http://8.8.8.8:8000", id="공인IP_http"),
        pytest.param("ftp://127.0.0.1:8000", id="허용외_스킴"),
        pytest.param(
            "http://127.0.0.1.evil.example.com:8000", id="루프백_접두_가장"
        ),
        pytest.param("http://192.168.1.1", id="사설IP_http"),
        pytest.param("", id="빈_문자열"),
        pytest.param("127.0.0.1:8000", id="스킴_없음"),
    ],
)
def test_비루프백_또는_허용_외_스킴의_서버_URL은_기동을_거부한다(
    monkeypatch, server_url
):
    monkeypatch.setenv("TAKULIFE_SERVER_URL", server_url)
    monkeypatch.setenv("TAKULIFE_RUNNER_TOKEN", "test-token")

    with pytest.raises(RuntimeError):
        load_config()


@pytest.mark.parametrize(
    "server_url",
    [
        pytest.param("https://runner.example.com", id="https_비루프백"),
        pytest.param("http://127.0.0.1:8000", id="http_루프백_IP"),
        pytest.param("http://localhost:8000", id="http_localhost"),
        pytest.param("http://[::1]:8000", id="http_IPv6_루프백"),
        pytest.param("http://127.5.5.5:8000", id="루프백_대역_경계"),
        pytest.param("HTTP://127.0.0.1:8000", id="스킴_대문자"),
        pytest.param("http://LOCALHOST:8000", id="호스트_대문자"),
    ],
)
def test_루프백_http와_모든_https_서버_URL은_그대로_허용된다(
    monkeypatch, server_url
):
    monkeypatch.setenv("TAKULIFE_SERVER_URL", server_url)
    monkeypatch.setenv("TAKULIFE_RUNNER_TOKEN", "test-token")

    config = load_config()

    assert config.server_url == server_url


def test_서버_URL_환경변수가_미설정이면_기본_루프백_주소로_허용된다(monkeypatch):
    monkeypatch.delenv("TAKULIFE_SERVER_URL", raising=False)
    monkeypatch.setenv("TAKULIFE_RUNNER_TOKEN", "test-token")

    config = load_config()

    assert config.server_url == "http://127.0.0.1:8000"
