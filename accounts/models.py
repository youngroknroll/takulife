from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    username = models.CharField(max_length=150, blank=True, null=True, unique=False)
    email = models.EmailField(unique=True)
    # accounts.forms.SignupForm.custom_signup가 가입 시 한 번만 설정한다 —
    # 이 시각은 가입 당시 약관/개인정보처리방침에 사용자가 명시적으로
    # 동의했다는 증적이다. 이 폼을 거치지 않은 계정(createsuperuser, 기존
    # 행)은 null이다.
    terms_agreed_at = models.DateTimeField(null=True, blank=True)
    # 사용자가 탈퇴를 확정하면 accounts.services.request_deletion이 설정한다.
    # null이 아니면 accounts.management.commands.purge_deleted_accounts를
    # 기다리는 10일 유예 기간 중이라는 뜻이며, 유예 기간 중 다시 로그인하면
    # 신청이 취소된다.
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    # accounts.services.record_password_change가 설정하며, allauth의
    # password_changed/password_set/password_reset 신호에 연결돼 있다
    # (accounts.signals 참고). 이 세 흐름을 한 번도 거치지 않은 계정은
    # null이다 — 가입 시 set_password 호출은 "변경"이 아니라 최초
    # 자격 증명이므로 기록하지 않는 게 맞다. 알려진 한계: allauth를
    # 거치지 않은 비밀번호 변경(예: `manage.py changepassword`)은 이
    # 필드를 갱신하지 않는다 — 그 경로에서는 allauth 신호가 발생하지 않는다.
    password_changed_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()
