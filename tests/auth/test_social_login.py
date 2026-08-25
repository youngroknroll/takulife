"""구글 소셜 로그인(allauth socialaccount).

구글을 상대로 한 완전한 OAuth 왕복은 CI에서 돌릴 수 없다(외부 서비스,
실제 자격증명 필요) — 그래서 이 테스트들은 그것 없이도 검증 가능한 것만
다룬다:
- 구글 provider가 등록돼 있고 인증 페이지에 버튼이 렌더되는지,
- 계정 연결 정책(공급자가 인증한 이메일이 기존 로컬 계정과 일치하는 구글
  로그인은 그 계정으로 로그인된다)이, 모킹한 ``SocialLogin``으로 allauth의
  ``complete_social_login``을 구동해 실제로 동작하는지.

실제 구글 왕복은 localhost에서 수동으로 검증한다.
"""
import pytest

GOOGLE_LOGIN_PATH = "/accounts/google/login/"

_CONFIGURED_GOOGLE_PROVIDER = {
    "google": {
        "APPS": [{"client_id": "test-client-id", "secret": "test-secret", "key": ""}],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

_UNCONFIGURED_GOOGLE_PROVIDER = {
    "google": {
        "APPS": [{"client_id": "", "secret": "", "key": ""}],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}


@pytest.mark.web
@pytest.mark.django_db
def test_구글_로그인이_설정되어_있으면_로그인_페이지에_구글_버튼이_노출된다(client, settings):
    """자격증명이 있으면 로그인 페이지가 구글 로그인 흐름으로 연결된다."""
    settings.SOCIALACCOUNT_PROVIDERS = _CONFIGURED_GOOGLE_PROVIDER
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert GOOGLE_LOGIN_PATH in response.content.decode("utf-8", "ignore")


@pytest.mark.web
@pytest.mark.django_db
def test_구글_로그인이_설정되어_있으면_회원가입_페이지에_구글_버튼이_노출된다(client, settings):
    """자격증명이 있으면 회원가입 페이지도 구글을 제공한다."""
    settings.SOCIALACCOUNT_PROVIDERS = _CONFIGURED_GOOGLE_PROVIDER
    response = client.get("/accounts/signup/")
    assert response.status_code == 200
    assert GOOGLE_LOGIN_PATH in response.content.decode("utf-8", "ignore")


@pytest.mark.web
@pytest.mark.django_db
def test_구글_로그인이_미설정이면_로그인_페이지에_구글_버튼이_노출되지_않는다(client, settings):
    """client_id가 비어 있으면 죽은 링크를 보여주는 대신 버튼을 숨긴다."""
    settings.SOCIALACCOUNT_PROVIDERS = _UNCONFIGURED_GOOGLE_PROVIDER
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert GOOGLE_LOGIN_PATH not in response.content.decode("utf-8", "ignore")


@pytest.mark.web
@pytest.mark.django_db
def test_구글_로그인이_미설정이면_회원가입_페이지에_구글_버튼이_노출되지_않는다(client, settings):
    """client_id가 비어 있으면 죽은 링크를 보여주는 대신 버튼을 숨긴다."""
    settings.SOCIALACCOUNT_PROVIDERS = _UNCONFIGURED_GOOGLE_PROVIDER
    response = client.get("/accounts/signup/")
    assert response.status_code == 200
    assert GOOGLE_LOGIN_PATH not in response.content.decode("utf-8", "ignore")


@pytest.mark.contract
def test_구글_provider_설정은_email_scope를_요청한다(settings):
    """구글은 email scope를 요청하도록 설정돼 있다 — 이게 없으면 allauth가
    연결 정책이 의존하는 인증된 주소를 얻을 수 없다."""
    google = settings.SOCIALACCOUNT_PROVIDERS["google"]
    assert "email" in google["SCOPE"]


@pytest.mark.contract
def test_구글_이메일_인증_계정연결_정책_설정이_활성화되어_있다(settings):
    """공급자가 인증한 이메일이 기존 로컬 계정과 일치하는 구글 로그인은 그
    계정으로 로그인(및 연결)돼야 한다 — 승인된 정책이다. 조용히 꺼지지
    않도록 여기서 가드한다. 구글이 전적으로 신뢰하는 공급자이기 때문에만
    안전한 정책이며, 다른 공급자를 추가하면 다시 검토해야 한다.

    (종단 OAuth 왕복, 자동 연결, 인증된 이메일 건너뛰기는 localhost에서
    수동으로 검증한다 — 그 흐름은 allauth가 소유하고 있어 프로세스 내에서
    재구성하면 내부 구현에 취약하게 결합된다.)"""
    assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION is True
    assert settings.SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT is True


@pytest.mark.contract
def test_SOCIALACCOUNT_FORMS는_SocialSignupForm을_가리키고_AUTO_SIGNUP은_비활성화되어_있다(settings):
    """둘 중 하나만 풀려도 약관 동의 없는 소셜 가입 경로가 다시 열린다(B2) —
    조용히 꺼지지 않도록 여기서 가드한다."""
    assert settings.SOCIALACCOUNT_FORMS["signup"] == "accounts.forms.SocialSignupForm"
    assert settings.SOCIALACCOUNT_AUTO_SIGNUP is False
