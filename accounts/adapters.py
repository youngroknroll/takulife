from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    """save_user는 INSERT를 커밋한 뒤에야 custom_signup을 부르므로,
    nickname은 super() 호출 전에 미리 실어 둬야 첫 저장에 함께 들어간다."""

    def save_user(self, request, user, form, commit=True):
        user.nickname = form.cleaned_data["nickname"]
        return super().save_user(request, user, form, commit=commit)
