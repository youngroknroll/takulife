from django.conf import settings


def project_name(request):
    """모든 템플릿 컨텍스트에 제품 이름을 넣는다.

    각 뷰가 렌더 컨텍스트에 ``"project_name"``을 따로 하드코딩하지 않게 한다.
    """
    return {"project_name": "takulife"}


def google_oauth_configured(request):
    """Google OAuth client_id가 설정돼 있는지 여부. 템플릿이 동작하지 않는
    버튼을 보여주는 대신 구글 로그인 버튼을 숨길 수 있게 한다.
    """
    apps = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APPS", [])
    client_id = apps[0].get("client_id", "") if apps else ""
    return {"google_oauth_configured": bool(client_id)}


def support_email(request):
    """모든 템플릿 컨텍스트에 연락처 주소(법적 고지 페이지, 푸터)를 넣어
    각 뷰가 ``"support_email"``을 따로 하드코딩하지 않게 한다.
    """
    return {"support_email": settings.SUPPORT_EMAIL}


def email_delivery_enabled(request):
    """메일이 실제로 발송되는 백엔드인지 여부. 콘솔 백엔드(SMTP 미설정)에서
    템플릿이 '인증 메일을 보냈습니다' 같은 거짓 약속을 하지 않게 한다.
    """
    return {
        "email_delivery_enabled": not settings.EMAIL_BACKEND.endswith(
            "console.EmailBackend"
        )
    }


def shell_css_bundled(request):
    """운영에서만 셸 CSS를 병합해 쓰도록, 템플릿이 DEBUG를 직접 보지 않고
    이 플래그만 보면 되게 한다.
    """
    return {"shell_css_bundled": not settings.DEBUG}
