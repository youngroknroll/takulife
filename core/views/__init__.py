"""core 뷰 패키지. system.py의 인프라 엔드포인트만 재노출한다."""
from .system import api_root, health

__all__ = ["api_root", "health"]
