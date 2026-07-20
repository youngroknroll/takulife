"""Management command: purge_deleted_accounts

Thin shell around accounts.services.execute_pending_deletions — no business
logic here (the 10-day grace period, the per-row transaction/locking, and
the cancel-race guard all live in the service; see
.docs/plans/2026-07-20-deletion-grace-period-plan.md). Regular scheduling
(cron/etc.) is a deployment/runbook concern, not this command.
"""
from django.core.management.base import BaseCommand, CommandError

from accounts.services import execute_pending_deletions


class Command(BaseCommand):
    help = "Hard-delete every account whose 10-day deletion grace period has elapsed."

    def handle(self, *args, **options):
        summary = execute_pending_deletions()
        deleted_count = len(summary["deleted"])
        failed_count = len(summary["failed"])
        self.stdout.write(f"삭제 {deleted_count}건 / 실패 {failed_count}건")

        if failed_count:
            raise CommandError(f"purge_deleted_accounts: {failed_count}건 에러 발생 — 위 로그 참고")
