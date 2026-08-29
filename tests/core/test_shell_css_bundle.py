"""bundle_shell_css 커맨드가 셸 CSS를 템플릿 로드 순서 그대로 이어붙이는지 계약으로 고정한다."""
import re
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# base.html이 <link>로 로드하는 순서 그대로 나열한다 — 번들이 이 순서를 어기면
# CSS 캐스케이드(우선순위)가 깨진다.
_SHELL_CSS_RELATIVE_PATHS = (
    "css/tokens.css",
    "css/base.css",
    "css/objects/interaction.css",
    "css/objects/layout.css",
    "css/components/site-chrome.css",
    "css/components/category.css",
    "css/components/controls.css",
    "css/components/button.css",
    "css/components/cards.css",
    "css/components/pager.css",
    "css/components/search.css",
    "css/components/text.css",
    "css/components/nav.css",
    "css/components/modal.css",
    "css/components/confirm-modal.css",
    "css/components/toast.css",
)


@pytest.mark.contract
def test_번들_커맨드가_셸_스타일을_템플릿_순서대로_병합한다(tmp_path):
    expected_paths = [PROJECT_ROOT / "static" / rel_path for rel_path in _SHELL_CSS_RELATIVE_PATHS]
    expected_bytes = b"\n".join(path.read_bytes() for path in expected_paths)

    output_path = tmp_path / "shell.css"
    call_command("bundle_shell_css", output=str(output_path))

    assert output_path.read_bytes() == expected_bytes


@pytest.mark.contract
def test_번들_대상_소스에_url_참조가_있으면_커맨드가_실패하고_산출물을_쓰지_않는다(tmp_path):
    템플릿_경로 = tmp_path / "base.html"
    템플릿_경로.write_text("{% static 'css/broken.css' %}")
    정적_루트 = tmp_path / "static"
    (정적_루트 / "css").mkdir(parents=True)
    (정적_루트 / "css" / "broken.css").write_text(".x{background:url(../img/x.png)}")
    출력_경로 = tmp_path / "shell.css"

    with pytest.raises(CommandError):
        call_command(
            "bundle_shell_css",
            output=str(출력_경로),
            template=str(템플릿_경로),
            static_root=str(정적_루트),
        )
    assert not 출력_경로.exists()


@pytest.mark.contract
def test_번들_커맨드는_자신의_산출_경로를_소스로_포함하지_않는다(tmp_path):
    정적_루트 = tmp_path / "static"
    (정적_루트 / "css" / "dist").mkdir(parents=True)
    (정적_루트 / "css" / "a.css").write_text(".a{color:red}")
    템플릿_경로 = tmp_path / "base.html"
    템플릿_경로.write_text(
        "{% static 'css/a.css' %}{% static 'css/dist/shell.css' %}"
    )
    출력_경로 = 정적_루트 / "css" / "dist" / "shell.css"

    call_command(
        "bundle_shell_css",
        output=str(출력_경로),
        template=str(템플릿_경로),
        static_root=str(정적_루트),
    )

    assert 출력_경로.read_bytes() == (정적_루트 / "css" / "a.css").read_bytes()


@pytest.mark.web
@pytest.mark.django_db
def test_디버그가_켜지면_기존_개별_스타일이_순서대로_렌더된다(client, settings):
    # 특성화 핀: 번들 분기가 들어가도 개발 모드에서는 개별 링크가 그대로 유지되는지 고정한다.
    settings.DEBUG = True

    resp = client.get("/")

    content = resp.content.decode()
    hrefs = re.findall(r'<link rel="stylesheet" href="([^"]+)"', content)

    shell_indexes = [hrefs.index(f"/static/{rel_path}") for rel_path in _SHELL_CSS_RELATIVE_PATHS]
    assert shell_indexes == sorted(shell_indexes)
    assert not any(href.endswith("css/dist/shell.css") for href in hrefs)


@pytest.mark.web
@pytest.mark.django_db
def test_디버그가_꺼지면_셸_스타일은_번들_하나로_렌더된다(client, settings):
    settings.DEBUG = False

    resp = client.get("/")

    content = resp.content.decode()
    hrefs = re.findall(r'<link rel="stylesheet" href="([^"]+)"', content)

    assert hrefs.count("/static/css/dist/shell.css") == 1
    assert not any(
        href in [f"/static/{rel_path}" for rel_path in _SHELL_CSS_RELATIVE_PATHS]
        for href in hrefs
    )
    assert "/static/fonts/pretendard/pretendardvariable-dynamic-subset.css" in hrefs
