"""관리 명령: prune_operational_data

core.retention.prune_operational_data를 감싸는 얇은 껍데기 — 대상별 집계와
삭제 로직은 전부 그 함수에 있다.
"""
from django.core.management.base import BaseCommand, CommandError

from core.retention import prune_operational_data


class Command(BaseCommand):
    help = "Delete stale operational data such as expired sessions."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        try:
            results = prune_operational_data(days=options["days"], dry_run=dry_run)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if dry_run:
            self.stdout.write("dry-run")

        failed_count = 0
        for key, result in results.items():
            line = f"{key}: count={result['count']} deleted={result['deleted']}"
            if result["error"]:
                line += f" error={result['error']}"
                failed_count += 1
            self.stdout.write(line)

        if failed_count:
            raise CommandError(f"prune_operational_data: {failed_count}개 대상 실패 — 위 로그 참고")
