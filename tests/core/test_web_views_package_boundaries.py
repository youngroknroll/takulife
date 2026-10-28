import ast
from pathlib import Path

import pytest

from tests.core.test_architecture_boundaries import PROJECT_ROOT


pytestmark = pytest.mark.contract


def _sibling_view_imports(path: Path, root: Path) -> set[str]:
    """파일이 `web.views.<형제>`로 해석되는 임포트의 형제 짧은 이름 집합을 돌려준다.

    정적 임포트문만 보며 동적 임포트(importlib 등)는 보지 않는다.
    """
    package_parts = path.relative_to(root).parent.parts
    tree = ast.parse(path.read_text(encoding="utf-8"))
    candidates: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            candidates.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0:
                base_parts = package_parts[: len(package_parts) - (node.level - 1)]
                base = ".".join(base_parts)
                prefix = f"{base}.{node.module}" if node.module else base
            else:
                prefix = node.module or ""
            if node.module:
                candidates.append(prefix)
            candidates.extend(f"{prefix}.{alias.name}" for alias in node.names)
    siblings: set[str] = set()
    for candidate in candidates:
        segments = candidate.split(".")
        if candidate.startswith("web.views.") and len(segments) >= 3:
            siblings.add(segments[2])
    return siblings


@pytest.mark.parametrize(
    "source",
    [
        "from .archive import _collection_item_row",
        "from . import archive",
        "from ..views import archive",
        "from web.views.archive import _collection_item_row",
        "import web.views.archive",
        "from web.views import archive",
    ],
    ids=[
        "상대_from_모듈",
        "상대_from_점만",
        "상위_상대_from",
        "절대_from_모듈",
        "절대_import",
        "절대_from_패키지_별칭",
    ],
)
def test_형제_임포트_스캐너는_형제_뷰_모듈_임포트_형태를_모두_탐지한다(tmp_path, source):
    """상대·절대 임포트 여섯 가지 형태가 모두 형제 모듈 archive로 탐지되는지 확인한다."""
    target = tmp_path / "web" / "views" / "collection.py"
    target.parent.mkdir(parents=True)
    target.write_text(source + "\n", encoding="utf-8")

    result = _sibling_view_imports(target, tmp_path)

    assert "archive" in result


def test_형제_임포트_스캐너는_같은_이름의_도메인_앱_임포트를_형제로_오탐하지_않는다(tmp_path):
    """최상위 archive 앱 임포트는 형제 뷰가 아니므로 `_helpers`만 탐지되어야 한다."""
    target = tmp_path / "web" / "views" / "collection.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "from archive.models import CollectionItem\n"
        "from archive.queries import x\n"
        "from ._helpers import y\n",
        encoding="utf-8",
    )

    assert _sibling_view_imports(target, tmp_path) == {"_helpers"}


def test_실제_아카이브_뷰_모듈의_컬렉션_단방향_임포트가_스캐너에_보인다():
    """archive.py가 collection.py와 _helpers.py를 임포트하는 것을 스캐너가 본다."""
    result = _sibling_view_imports(PROJECT_ROOT / "web" / "views" / "archive.py", PROJECT_ROOT)

    assert {"collection", "_helpers"} <= result


def test_컬렉션_뷰_모듈은_아카이브_뷰_모듈을_임포트하지_않는다():
    """collection.py → archive.py 역방향 임포트를 금지한다."""
    result = _sibling_view_imports(PROJECT_ROOT / "web" / "views" / "collection.py", PROJECT_ROOT)

    assert "archive" not in result


def test_뷰_공용_헬퍼_모듈은_형제_뷰_모듈을_임포트하지_않는다():
    """_helpers.py는 형제를 임포트하지 않는 리프여야 한다."""
    result = _sibling_view_imports(PROJECT_ROOT / "web" / "views" / "_helpers.py", PROJECT_ROOT)

    assert result == set()
