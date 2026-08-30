"""templates/base.html — favicon + meta description + 오픈그래프 태그.

공용 head(templates/base.html)에 원래 favicon도 meta description/오픈그래프
태그도 없어서, 링크를 공유하면 미리보기에 URL만 덩그러니 나왔다. 모든
페이지가 templates/base.html을 상속해 이 태그들을 자동으로 얻으므로, 홈
페이지 응답으로 스모크 테스트한다.
"""
from datetime import date

import pytest
from django.template.defaultfilters import truncatechars
from django.utils.html import escape

from core.vocab import CATEGORY_LABELS

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_홈_페이지는_favicon_링크를_포함한다(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert '<link rel="icon"' in resp.content.decode()


@pytest.mark.django_db
def test_홈_페이지는_meta_description을_포함한다(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert '<meta name="description"' in resp.content.decode()


@pytest.mark.django_db
def test_홈_페이지는_오픈그래프_태그를_포함한다(client):
    resp = client.get("/")

    content = resp.content.decode()
    assert 'property="og:title"' in content
    assert 'property="og:description"' in content
    assert 'property="og:type"' in content


@pytest.mark.django_db
def test_행사_상세_페이지의_og_title은_행사_제목을_포함한다(client, make_event):
    event = make_event(title="공개 행사 오픈")
    resp = client.get(f"/events/{event.id}/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert '<meta property="og:title" content="공개 행사 오픈 — takulife">' in content


@pytest.mark.django_db
def test_개인정보처리방침_페이지는_기본_og_title을_페이지_전용_제목으로_재정의한다(client):
    resp = client.get("/legal/privacy/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert '<meta property="og:title" content="개인정보처리방침 — takulife">' in content


@pytest.mark.django_db
def test_행사_상세_페이지의_og_title은_특수문자를_이스케이프한다(client, make_event):
    title = '<script>alert("x")</script> & 굿즈전'
    event = make_event(title=title)
    expected = escape(f"{truncatechars(title, 20)} — takulife")

    resp = client.get(f"/events/{event.id}/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert "<script>alert" not in content
    assert f'<meta property="og:title" content="{expected}">' in content


@pytest.mark.django_db
def test_비공개_아카이브_페이지는_기본_og_title을_유지한다(client, make_user):
    client.force_login(make_user())
    resp = client.get("/archive/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert '<meta property="og:title" content="takulife">' in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "event_kwargs, unique_segment_builder",
    [
        (dict(title="공개 행사 오픈"), lambda e: e.title),
        (dict(title="1부", work_title="원피스"), lambda e: f"{e.work_title} · {e.title}"),
        (dict(title="아주긴행사제목이스무자를훌쩍넘어가는경우를시험한다"), lambda e: e.title),
    ],
    ids=[
        "행사명만_있으면_제목_뒤에_takulife가_붙는다",
        "작품명이_있으면_작품명_다음에_행사명이_온다",
        "긴_제목은_20자에서_말줄임되고_접미사는_보존된다",
    ],
)
def test_행사_상세_페이지는_행사명이_들어간_메타_제목을_조립한다(
    client, make_event, event_kwargs, unique_segment_builder
):
    event = make_event(**event_kwargs)
    expected = f"{truncatechars(unique_segment_builder(event), 20)} — takulife"

    resp = client.get(f"/events/{event.id}/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert f"<title>{expected}</title>" in content
    assert f'<meta property="og:title" content="{expected}">' in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "event_kwargs, expected_builder",
    [
        (
            dict(summary="굿즈 판매 부스 운영"),
            lambda: truncatechars("굿즈 판매 부스 운영", 100),
        ),
        (
            dict(
                summary="   ",
                category="popup_store",
                location_name="코엑스",
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 3),
            ),
            lambda: truncatechars(
                f"{CATEGORY_LABELS['popup_store']} · 코엑스 · 2026-03-01 ~ 2026-03-03",
                100,
            ),
        ),
        (
            dict(summary="", category="", location_name="", start_date=None, end_date=None),
            lambda: (
                "팝업스토어 · 콜라보 카페 · 극장 특전 · 굿즈 예약 · "
                "전시를 검색하고, 방문 상태와 기록을 보관하세요."
            ),
        ),
    ],
    ids=[
        "요약이_있으면_요약을_그대로_쓴다",
        "요약이_없으면_카테고리_장소_기간을_조합한다",
        "요약과_카테고리_장소_기간이_모두_없으면_기본_문구로_폴백한다",
    ],
)
def test_행사_상세_페이지는_요약_우선순위로_description을_조립한다(
    client, make_event, event_kwargs, expected_builder
):
    event = make_event(**event_kwargs)
    expected = expected_builder()

    resp = client.get(f"/events/{event.id}/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert f'<meta name="description" content="{expected}">' in content
    assert f'<meta property="og:description" content="{expected}">' in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path, expected",
    [
        ("/events/", "이벤트 목록 — takulife"),
        ("/events/calendar/", "이벤트 달력 — takulife"),
    ],
    ids=["이벤트_목록_페이지", "이벤트_달력_페이지"],
)
def test_공개_페이지_title은_서로_다르고_접미사가_통일돼_있다(client, path, expected):
    resp = client.get(path)

    content = resp.content.decode()
    assert resp.status_code == 200
    assert f"<title>{expected}</title>" in content
    assert f'<meta property="og:title" content="{expected}">' in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path, expected",
    [
        ("/", "http://testserver/"),
        ("/events/?q=원피스", "http://testserver/events/"),
    ],
    ids=["쿼리스트링_없는_페이지", "쿼리스트링_있는_페이지는_제외된다"],
)
def test_페이지는_쿼리스트링_없는_canonical과_og_url을_포함한다(client, path, expected):
    resp = client.get(path)

    content = resp.content.decode()
    assert resp.status_code == 200
    assert f'<link rel="canonical" href="{expected}">' in content
    assert f'<meta property="og:url" content="{expected}">' in content


@pytest.mark.django_db
def test_페이지_응답은_og_image_태그를_포함하지_않는다(client):
    resp = client.get("/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert 'property="og:image"' not in content


@pytest.mark.contract
@pytest.mark.django_db
@pytest.mark.parametrize(
    "path, user_kwargs",
    [
        ("/archive/", {}),
        ("/mypage/", {}),
        ("/archive/visits/", {}),
        ("/archive/calendar/", {}),
        ("/staff/dashboard/", {"is_staff": True}),
    ],
    ids=["아카이브_홈", "마이페이지", "다녀온_기록_목록", "활동_달력", "스태프_대시보드"],
)
def test_비공개_페이지_응답은_noindex_로봇_지시를_포함한다(client, make_user, path, user_kwargs):
    user = make_user(**user_kwargs)
    client.force_login(user)

    resp = client.get(path)

    content = resp.content.decode()
    assert resp.status_code == 200
    assert 'name="robots" content="noindex, nofollow"' in content


@pytest.mark.web
@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    ["/", "/events/", "/events/calendar/", "/legal/privacy/", "/legal/terms/"],
    ids=["홈", "이벤트_목록", "이벤트_달력", "개인정보처리방침", "이용약관"],
)
def test_공개_페이지_응답은_noindex_로봇_지시를_포함하지_않는다(client, path):
    resp = client.get(path)

    content = resp.content.decode()
    assert resp.status_code == 200
    assert 'name="robots"' not in content


@pytest.mark.web
@pytest.mark.django_db
def test_행사_상세_페이지_응답은_noindex_로봇_지시를_포함하지_않는다(client, make_event):
    event = make_event(title="공개 행사")

    resp = client.get(f"/events/{event.id}/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert 'name="robots"' not in content
