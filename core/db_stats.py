"""대시보드 저장소 패널이 쓰는 DB 용량 조회.

Postgres 전용 쿼리라 다른 엔진이거나 쿼리가 실패하면 대시보드가 죽지
않도록 None을 돌려준다(core.retention과 별개, 트랙 37 S2).
"""
import logging

from django.db import DatabaseError, connection

logger = logging.getLogger(__name__)

_KB_THRESHOLD = 1_048_576
_MB_THRESHOLD = 1_073_741_824

_TOTAL_SIZE_SQL = "SELECT pg_database_size(current_database())"
_TABLE_SIZE_SQL = """
    SELECT c.relname, pg_total_relation_size(c.oid)
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r'
    ORDER BY 2 DESC
    LIMIT 5
"""


def format_bytes(num_bytes):
    """바이트 수를 KB/MB/GB 문자열로 표시한다(소수 1자리, 단위 앞 공백 없음)."""
    if num_bytes < _KB_THRESHOLD:
        return f"{num_bytes / 1024:.1f}KB"
    if num_bytes < _MB_THRESHOLD:
        return f"{num_bytes / 1_048_576:.1f}MB"
    return f"{num_bytes / 1_073_741_824:.1f}GB"


def _fetch_sizes():
    with connection.cursor() as cursor:
        cursor.execute(_TOTAL_SIZE_SQL)
        (total,) = cursor.fetchone()
        cursor.execute(_TABLE_SIZE_SQL)
        rows = cursor.fetchall()
    return total, rows


def database_size_summary():
    """Postgres가 아니거나 쿼리가 실패하면 None(대시보드 보호)."""
    if connection.vendor != "postgresql":
        return None

    try:
        total, rows = _fetch_sizes()
    except DatabaseError:
        logger.warning("database size query failed")
        return None

    return {
        "total_bytes": total,
        "total_label": format_bytes(total),
        "tables": [
            {"name": name, "bytes": size, "label": format_bytes(size)}
            for name, size in rows
        ],
    }
