"""템플릿이 {% static %}으로 가리키는 정적 파일이 실제로 있는지 본다.

파일을 옮기고 참조를 안 고치면 화면은 200으로 뜨고 스크립트만 404가 난다.
Django 테스트는 정적 파일을 받아오지 않아 전체 통과 상태에서도 그대로 살아남는다
— 실제로 스태프 JS를 js/staff/로 옮겼을 때 2111건이 초록인 채 404가 났다.
"""
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders

from core.context_processors import FONT_PRELOAD_CHUNKS
from core.management.commands.bundle_shell_css import BUNDLE_RELATIVE_PATH

pytestmark = pytest.mark.unit

# {% static 'a/b.css' %} 형태의 리터럴만 본다. 변수로 조립한 경로는 정적으로 알 수 없다.
STATIC_LITERAL = re.compile(r"""\{%\s*static\s+(['"])(?P<path>[^'"]+)\1""")


def _template_files():
    roots = [Path(d) for entry in settings.TEMPLATES for d in entry.get("DIRS", [])]
    roots.append(Path(settings.BASE_DIR) / "templates")
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.html"):
            if path not in seen:
                seen.add(path)
                yield path


def test_템플릿이_참조하는_정적_파일은_모두_존재한다():
    missing = []
    for template in _template_files():
        text = template.read_text(encoding="utf-8")
        for match in STATIC_LITERAL.finditer(text):
            ref = match.group("path")
            if ref == BUNDLE_RELATIVE_PATH:
                continue  # 배포 시점(entrypoint)에 bundle_shell_css가 생성 — docs/FE/css-delivery.md 가드레일
            if finders.find(ref) is None:
                rel = template.relative_to(settings.BASE_DIR)
                missing.append(f"{rel}: {ref}")

    assert missing == [], "존재하지 않는 정적 파일을 참조한다:\n" + "\n".join(missing)


def test_가드가_실제로_찾을_수_있는_경로를_검사하고_있다():
    """참조를 하나도 못 모으면 위 테스트는 아무것도 검증하지 않고 통과한다."""
    refs = [
        match.group("path")
        for template in _template_files()
        for match in STATIC_LITERAL.finditer(template.read_text(encoding="utf-8"))
    ]

    assert len(refs) > 20, len(refs)
    assert finders.find(refs[0]) is not None


def test_폰트_preload_상수의_경로가_모두_정적_파일로_존재한다():
    missing = [chunk for chunk in FONT_PRELOAD_CHUNKS if finders.find(chunk) is None]

    assert missing == [], missing
