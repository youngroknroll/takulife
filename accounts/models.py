from django.contrib.auth.models import AbstractUser
from django.db import models

from .managers import UserManager


class User(AbstractUser):
    username = models.CharField(max_length=150, blank=True, null=True, unique=False)
    email = models.EmailField(unique=True)
    # Set once at signup by accounts.forms.SignupForm.custom_signup — the
    # timestamp is the evidence trail that the user explicitly agreed to the
    # terms/privacy policy in effect at signup time. Null for any account
    # created outside that form (e.g. createsuperuser, pre-existing rows).
    terms_agreed_at = models.DateTimeField(null=True, blank=True)
    # Set by accounts.services.request_deletion when the user confirms
    # self-deletion. Non-null means the account is in the 10-day grace
    # period awaiting accounts.management.commands.purge_deleted_accounts;
    # logging back in during the grace period cancels the request (see
    # .docs/plans/2026-07-20-deletion-grace-period-plan.md).
    deletion_requested_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()
