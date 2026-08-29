"""templates/base.html이 로드하는 셸 CSS를 등장 순서 그대로 이어붙여 파일로 쓴다."""
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# {% static 'css/...' %} 형태에서 css/ 로 시작하는 경로만 등장 순서대로 뽑는다.
_STATIC_CSS_TAG_RE = re.compile(r"\{%\s*static\s+['\"](css/[^'\"]+)['\"]\s*%\}")

# 이 커맨드가 만드는 산출물 자신의 정적 경로 — 템플릿이 배포용 번들 링크를
# 미리 갖고 있어도 이 경로는 소스가 아니다.
BUNDLE_RELATIVE_PATH = "css/dist/shell.css"


class Command(BaseCommand):
    help = "base.html의 셸 CSS 링크를 로드 순서대로 병합해 --output 경로에 쓴다."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True, help="병합 결과를 쓸 파일 경로")
        parser.add_argument("--template", default=None, help="기본값 templates/base.html")
        parser.add_argument("--static-root", default=None, help="기본값 static/")

    def handle(self, *args, **options):
        base_dir = Path(settings.BASE_DIR)
        template_path = Path(options["template"]) if options["template"] else base_dir / "templates" / "base.html"
        static_root = Path(options["static_root"]) if options["static_root"] else base_dir / "static"
        if not template_path.exists():
            raise CommandError(f"템플릿을 찾을 수 없다: {template_path}")

        template_text = template_path.read_text()
        relative_css_paths = _STATIC_CSS_TAG_RE.findall(template_text)

        output_path = Path(options["output"])

        chunks = []
        for relative_path in relative_css_paths:
            if relative_path == BUNDLE_RELATIVE_PATH:
                # 템플릿의 번들 자기 참조는 구조적으로 소스가 아니다.
                continue
            css_path = static_root / relative_path
            if not css_path.exists():
                raise CommandError(f"셸 CSS 파일을 찾을 수 없다: {css_path}")
            content = css_path.read_bytes()
            if b"url(" in content:
                # url(...) 상대 경로는 병합 후 위치가 달라져 깨지므로 병합 대상에서 금지한다.
                raise CommandError(f"병합 시 상대 경로가 깨지는 url() 참조가 있다: {css_path}")
            chunks.append(content)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\n".join(chunks))
