"""번역 대기 큐의 건수와 언어별 격리 수를 보고하는 읽기 전용 명령이다.
집계 로직은 전부 events.translation_queue.queue_report가 갖고 있고,
이 명령은 그 결과를 줄 단위로 출력만 한다.
"""

from django.core.management.base import BaseCommand

from events.translation_queue import queue_report


class Command(BaseCommand):
    help = "번역 대기 큐의 건수와 언어별 격리 수를 보고하는 읽기 전용 명령이다."

    def handle(self, *args, **options):
        report = queue_report()
        for key, value in report.items():
            self.stdout.write(f"{key}={value}")
