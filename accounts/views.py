from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required
def delete_account(request):
    """Password-reconfirmed account deletion.

    GET renders the confirmation form. POST verifies the current password
    before deleting the account; owned archive rows and their media files
    cascade via each model's on_delete=CASCADE FK plus the archive.signals
    post_delete cleanup (see archive/models.py, archive/signals.py) — this
    view does not re-implement that cleanup. The session is flushed right
    after the delete so the browser's existing cookie can never keep
    authenticating the now-gone account.
    """
    if request.method == "POST":
        password = request.POST.get("password", "")
        if not request.user.check_password(password):
            return render(
                request,
                "account/delete_account.html",
                {"field_errors": {"password": "비밀번호가 올바르지 않습니다."}},
            )

        user = request.user
        user.delete()
        logout(request)
        messages.success(request, "회원 탈퇴가 완료되었습니다.")
        return redirect("home")

    return render(request, "account/delete_account.html", {"field_errors": {}})
