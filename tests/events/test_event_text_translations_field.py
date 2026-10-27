"""Event.text_translations 필드의 기본값 계약 — DB가 필요한 모델 테스트."""
import pytest
from django.db import connection

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_새_이벤트의_번역_저장소는_빈_dict로_시작한다(make_event):
    event = make_event(title="기본값 확인용")
    event.refresh_from_db()

    assert event.text_translations == {}


@pytest.mark.django_db
def test_이벤트_번역_저장소_열의_DB_기본값은_빈_JSON_객체다():
    # 구 코드의 INSERT가 열을 생략해도 NOT NULL 위반이 나지 않도록 DB 기본값이 필요하다.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_schema = current_schema() "
            "AND table_name = 'events_event' AND column_name = 'text_translations'"
        )
        (column_default,) = cursor.fetchone()

    assert column_default == "'{}'::jsonb"
