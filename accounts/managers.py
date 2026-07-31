from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        # normalize_email()은 도메인만 소문자로 바꾼다 — 진입 경로와
        # 무관하게(예: manage.py createsuperuser는 공개 가입 경로의 allauth
        # 소문자 변환을 거치지 않는다) 이메일이 신뢰할 수 있는 고유 식별자로
        # 남도록 주소 전체를 소문자로 바꾼다.
        email = self.normalize_email(email.lower())
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self._create_user(email, password, **extra_fields)
