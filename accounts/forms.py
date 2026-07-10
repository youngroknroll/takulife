from allauth.account.forms import SignupForm as AllauthSignupForm
from django.forms import BooleanField
from django.utils import timezone
from django.utils.safestring import mark_safe


# Plain string hrefs (not reverse()/{% url %}): the /legal/ routes are added
# in a later frontend commit, so a named-URL lookup here would fail today.
# See .docs/plans/2026-07-10-legal-pages-plan.md §4-4.
_TERMS_AGREEMENT_LABEL = mark_safe(
    '<a href="/legal/terms/" target="_blank" rel="noopener">이용약관</a> 및 '
    '<a href="/legal/privacy/" target="_blank" rel="noopener">개인정보처리방침</a>에 동의합니다.'
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
