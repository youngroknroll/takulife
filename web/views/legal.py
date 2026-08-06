"""이용약관·개인정보처리방침 등 정적 법적 페이지 뷰."""
from django.shortcuts import render


def legal_privacy(request):
    return render(request, "core/legal/privacy.html")


def legal_terms(request):
    return render(request, "core/legal/terms.html")
