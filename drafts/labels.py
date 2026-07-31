"""드래프트 검토 상태 라벨의 단일 출처.

EventDraft.ReviewStatus의 choices 라벨은 영어라(모델 변경은 마이그레이션을
유발해 이 저장소가 어휘 가드 트랙에서 이미 기각한 방식이다), 화면에 쓰는
한국어 라벨은 여기 앱 상수로 따로 둔다. 키는 ReviewStatus.values와 일치해야
한다.
"""

REVIEW_STATUS_LABELS: dict[str, str] = {
    "pending": "검토 대기",
    "approved": "승인됨",
    "rejected": "반려됨",
}
