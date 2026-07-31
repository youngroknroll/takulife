"""관리 명령: purge_deleted_accounts

accounts.services.execute_pending_deletions를 감싸는 얇은 껍데기 —
10일 유예 기간, 행 단위 트랜잭션/잠금, 취소 경쟁 방지는 전부 서비스
쪽에 있고 여기엔 비즈니스 로직이 없다. 정기 실행(cron 등)은 이 명령이
아니라 배포/운영 문서가 다룰 몫이다.
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
