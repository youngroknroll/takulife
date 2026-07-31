from allauth.account.signals import password_changed, password_reset, password_set
from django.contrib import messages
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from . import services


@receiver(user_logged_in)
def cancel_pending_deletion_on_login(sender, request, user, **kwargs):
    """10일 유예 기간 중 로그인에 성공하면 그 자체가 취소다 — 로그인이
    이미 소유자를 재인증하므로 별도 확인 단계가 필요 없다. allauth
    어댑터 훅이 아니라 표준 Django 인증 신호를 쓰므로 소셜 로그인을
    포함한 모든 로그인 백엔드에서 동작한다.
    """
    cancelled = services.cancel_deletion(user)
    if cancelled and request is not None:
        messages.success(request, "탈퇴 예약이 취소되었습니다.")


@receiver([password_changed, password_set, password_reset])
def _on_password_event(sender, request, user, **kwargs):
    """allauth의 비밀번호 관련 세 신호 중 무엇이 와도
    password_changed_at을 기록한다. 하나의 수신자가 password_changed(변경
    폼), password_set(소셜/무비밀번호 계정의 최초 설정), password_reset
    (이메일 링크·코드 방식 재설정 모두 이 신호로 모인다)을 함께 처리한다.
    실제 쓰기는 전부 accounts.services.record_password_change에서 일어나고
    이 핸들러는 얇게 유지한다.
    """
    services.record_password_change(user)
