"""드래프트 검토 상태 라벨을 템플릿에서 쓰기 위한 필터.

core/templatetags/에 두지 않는 이유: core 공용 모듈 경계 가드가 core/를
예외 없는 기본 거부로 둔다 — drafts.labels를 끌어오는 필터가 도메인 앱을
임포트하므로 core/에 두면 항상 위반이라 drafts/templatetags/에 둔다.
"""

from django import template

from drafts.labels import REVIEW_STATUS_LABELS

register = template.Library()


@register.filter
def review_status_label(review_status):
    """검토 상태 slug를 한국어 라벨로 바꾼다. 알 수 없는 값은 그대로 돌려준다."""
    return REVIEW_STATUS_LABELS.get(review_status, review_status)
