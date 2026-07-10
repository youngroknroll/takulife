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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()
