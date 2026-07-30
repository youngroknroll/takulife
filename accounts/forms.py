from allauth.account.forms import AddEmailForm
from allauth.account.forms import SignupForm as AllauthSignupForm
from django import forms
from django.forms import BooleanField, CharField, PasswordInput
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.safestring import mark_safe


# reverse_lazy: the /legal/ routes (legal-terms-page / legal-privacy-page,
# core/views.py) now exist, so the label follows them by name instead of a
# hardcoded path — a future route rename can't silently leave a dead link
# here. Lazy (not reverse()) because this module can be imported before the
# URLconf is guaranteed to be resolved (e.g. ACCOUNT_FORMS import_string).
_TERMS_AGREEMENT_LABEL = mark_safe(
    '<a href="{terms}" target="_blank" rel="noopener">이용약관</a> 및 '
    '<a href="{privacy}" target="_blank" rel="noopener">개인정보처리방침</a>에 동의합니다.'.format(
        terms=reverse_lazy("legal-terms-page"),
        privacy=reverse_lazy("legal-privacy-page"),
    )
)


class SignupForm(AllauthSignupForm):
    """Adds a mandatory terms/privacy-policy agreement checkbox to allauth's
    signup form (registered via settings.ACCOUNT_FORMS)."""

    terms_agreed = BooleanField(
        required=True,
        label=_TERMS_AGREEMENT_LABEL,
        error_messages={
            "required": "이용약관 및 개인정보처리방침에 동의해야 가입할 수 있습니다."
        },
    )

    def custom_signup(self, request, user):
        # allauth's hook for persisting extra signup-form fields onto the
        # new user (called right after adapter.save_user). Records *when*
        # agreement happened as the evidence trail — see accounts.models.User.
        super().custom_signup(request, user)
        user.terms_agreed_at = timezone.now()
        user.save(update_fields=["terms_agreed_at"])


class EmailChangeForm(AddEmailForm):
    """Adds a current-password re-check to allauth's add-email form
    (registered via settings.ACCOUNT_FORMS["add_email"]).

    The check lives in clean(), not save(): allauth's EmailView.form_valid
    only calls add_email()/save() when is_valid() is True, so failing
    validation here is what actually stops the email-change side effect.
    self.user is set by AddEmailForm's own base class (allauth UserForm).
    """

    current_password = CharField(widget=PasswordInput, label="현재 비밀번호")

    def clean_current_password(self):
        current_password = self.cleaned_data["current_password"]
        if not self.user.check_password(current_password):
            raise forms.ValidationError("비밀번호가 올바르지 않습니다.")
        return current_password
