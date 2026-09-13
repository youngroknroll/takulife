"""스태프 카테고리 관리 화면 권한 게이트 — 트랙 27 11단계.

Red 기대: `staff/urls.py`에 `category-*` 이름이 아직 없어 reverse()가
NoReverseMatch로 실패한다(G-01~G-03). G-04는 `staff/views/categories.py`
파일 자체가 없어 `Path.read_text()`가 FileNotFoundError로 실패한다.
"""
import ast
from pathlib import Path

from django.urls import reverse

import pytest

from core.models import Category

pytestmark = pytest.mark.web

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATEGORIES_VIEW_FILE = PROJECT_ROOT / "staff" / "views" / "categories.py"
REQUIRED_DECORATOR = "superuser_console_required"


def _category_urls(pk):
    return {
        "list": reverse("staff:category-list"),
        "create": reverse("staff:category-create"),
        "edit": reverse("staff:category-edit", args=[pk]),
        "set-active": reverse("staff:category-set-active", args=[pk]),
    }


def _request(client, url_key, url):
    if url_key == "set-active":
        return client.post(url, {"enabled": "1"})
    return client.get(url)


# G-01 익명 -----------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("url_key", ["list", "create", "edit", "set-active"])
def test_익명_사용자가_접근하면_로그인으로_리다이렉트된다(client, url_key):
    """G-01"""
    url = _category_urls(1)[url_key]

    resp = _request(client, url_key, url)

    assert resp.status_code == 302
    assert resp.url.startswith("/accounts/login/")


# G-02 슈퍼유저 아닌 사용자 ----------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("url_key", ["list", "create", "edit", "set-active"])
@pytest.mark.parametrize(
    "actor_kwargs",
    [
        pytest.param({"is_staff": False}, id="일반_사용자"),
        pytest.param({"is_staff": True}, id="슈퍼유저_아닌_스태프"),
    ],
)
def test_슈퍼유저가_아닌_사용자는_403을_응답한다(user_client, url_key, actor_kwargs):
    """G-02"""
    _, client = user_client(**actor_kwargs)
    url = _category_urls(1)[url_key]

    resp = _request(client, url_key, url)

    assert resp.status_code == 403


# G-03 슈퍼유저 정상 접근 ------------------------------------------------------


@pytest.mark.django_db
def test_슈퍼유저는_4개_화면_모두_정상_접근한다(staff_client):
    """G-03"""
    target = Category.objects.first()
    _, client = staff_client(is_superuser=True)
    urls = _category_urls(target.pk)

    assert client.get(urls["list"]).status_code == 200
    assert client.get(urls["create"]).status_code == 200
    assert client.get(urls["edit"]).status_code == 200
    # confirmed 없는 POST는 확인 화면(200)을 보여준다 — 403/404가 아니라는
    # 사실만으로 "정상 접근"이 확인된다.
    assert client.post(urls["set-active"], {"enabled": "0"}).status_code == 200


# G-04 데코레이터 AST 계약 -----------------------------------------------------


def _decorator_names(func_node):
    names = []
    for dec in func_node.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Attribute):
            names.append(target.attr)
    return names


def _undecorated_top_level_functions(path, decorator_name=REQUIRED_DECORATOR):
    tree = ast.parse(path.read_text())
    return [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and decorator_name not in _decorator_names(node)
    ]


def test_categories_뷰_모듈의_모든_최상위_함수는_superuser_console_required로_감싸여_있다():
    """G-04"""
    missing = _undecorated_top_level_functions(CATEGORIES_VIEW_FILE)

    assert not missing, missing


def test_데코레이터_없는_가짜_함수를_심으면_가드가_잡아낸다(tmp_path):
    """G-04 자기 검증 — 가드 자체가 실제로 작동하는지 확인한다."""
    fake_module = tmp_path / "fake_categories.py"
    fake_module.write_text(
        "from staff.permissions import superuser_console_required\n\n"
        "@superuser_console_required\n"
        "def guarded(request):\n"
        "    pass\n\n"
        "\n"
        "def unguarded(request):\n"
        "    pass\n"
    )

    missing = _undecorated_top_level_functions(fake_module)

    assert missing == ["unguarded"]
