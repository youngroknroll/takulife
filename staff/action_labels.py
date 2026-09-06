"""StaffActionLog.action 코드의 한국어 표시 라벨.

get_action_display()를 쓰지 않는 이유는 staff/views/__init__.py의 기존
주석과 같다 — 모델의 영어 choice 라벨을 그대로 노출하지 않기 위해서다.
대시보드(staff/views/__init__.py)와 감사 로그 화면(staff/views/audit_log.py)이
같은 라벨을 공유하도록 여기로 뺐다.
"""

ACTION_LABELS = {
    "approve": "승인",
    "reject": "반려",
    "home_categories": "홈 카테고리 변경",
    "event_update": "이벤트 수정",
    "event_create": "이벤트 생성",
    "event_unpublish": "게시 내리기",
    "event_republish": "재게시",
    "event_delete": "이벤트 삭제",
    "event_verify": "검증 완료",
    "draft_discover": "드래프트 수집 실행",
    "source_discover": "수집처 탐색",
    "staff_grant": "검수 권한 부여",
    "staff_revoke": "검수 권한 해제",
    "user_deactivate": "계정 비활성화",
    "user_reactivate": "계정 재활성화",
}
