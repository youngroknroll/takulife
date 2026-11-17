"""내 활동 화면이 새로 만든 카테고리의 공식 행사를 슬러그가 아니라 카테고리
라벨로 보여주는지 검증한다(트랙 59 확장)."""

from datetime import date
from html.parser import HTMLParser

from django.db import connection
from django.test.utils import CaptureQueriesContext
import pytest

from core.models import Category

pytestmark = [pytest.mark.django_db, pytest.mark.web]

_글자_없는_태그 = {"script", "style", "title"}


class _텍스트_노드_수집기(HTMLParser):
    """스크립트·스타일·title을 뺀 텍스트 노드를 공백을 정리해 모은다."""

    def __init__(self):
        super().__init__()
        self.노드들 = []
        self._건너뛰는_깊이 = 0

    def handle_starttag(self, tag, attrs):
        if tag in _글자_없는_태그:
            self._건너뛰는_깊이 += 1

    def handle_endtag(self, tag):
        if tag in _글자_없는_태그:
            self._건너뛰는_깊이 -= 1

    def handle_data(self, data):
        text = " ".join(data.split())
        if text and self._건너뛰는_깊이 == 0:
            self.노드들.append(text)


def _텍스트_노드(html):
    수집기 = _텍스트_노드_수집기()
    수집기.feed(html)
    return 수집기.노드들


@pytest.mark.parametrize(
    "경로",
    [
        pytest.param("/archive/", id="기록장"),
        pytest.param("/archive/statuses/", id="나의_일정"),
        pytest.param("/archive/visits/", id="방문_목록"),
        pytest.param("/archive/visits/{방문_id}/", id="방문_상세"),
        pytest.param("/archive/visits/{방문_id}/edit/", id="방문_수정"),
        pytest.param("/archive/interests/", id="찜_목록"),
        pytest.param("/", id="로그인_홈_기록_대기"),
    ],
)
def test_새_카테고리_행사를_담은_활동_화면은_슬러그가_아니라_카테고리_라벨을_보여준다(
    user_client, make_event, make_status, make_visit, make_interest, 경로
):
    user, client = user_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    행사_a = make_event(title="방문 완료 행사", category="night_market")
    행사_b = make_event(title="방문 기록 행사", category="night_market")
    행사_c = make_event(title="찜 행사", category="night_market")
    make_status(user, 행사_a, status="visited")
    방문 = make_visit(user, event=행사_b, visited_on=date(2026, 11, 1))
    make_interest(user, 행사_c)

    resp = client.get(경로.format(방문_id=방문.id))

    assert resp.status_code == 200
    노드들 = _텍스트_노드(resp.content.decode())
    assert "나이트 마켓" in 노드들
    assert "night_market" not in 노드들


@pytest.mark.parametrize(
    "경로",
    [
        pytest.param("/archive/", id="기록장"),
        pytest.param("/archive/statuses/", id="나의_일정"),
    ],
)
def test_새_카테고리_행이_많아져도_상태_목록의_쿼리_수는_행_수에_비례하지_않는다(
    user_client, make_event, make_status, 경로
):
    user, client = user_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    for 번호 in range(2):
        행사 = make_event(title=f"적은 행 {번호}", category="night_market")
        make_status(user, 행사, status="visited")
    with CaptureQueriesContext(connection) as 적은_행_쿼리:
        client.get(경로)

    Category.objects.create(slug="flea_market", label="벼룩 마켓")
    Category.objects.create(slug="book_market", label="책 마켓")
    for 번호, 슬러그 in enumerate(["night_market", "flea_market", "book_market"]):
        행사 = make_event(title=f"많은 행 {번호}", category=슬러그)
        make_status(user, 행사, status="visited")
    with CaptureQueriesContext(connection) as 많은_행_쿼리:
        client.get(경로)

    assert len(많은_행_쿼리) == len(적은_행_쿼리)


def test_방문_목록의_카테고리_칩은_새_카테고리를_슬러그가_아니라_카테고리_라벨로_보여준다(
    user_client, make_event, make_visit
):
    user, client = user_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    새_행사 = make_event(title="새 카테고리 행사", category="night_market")
    고정_행사 = make_event(title="고정 카테고리 행사", category="popup_store")
    make_visit(user, event=새_행사, visited_on=date(2026, 11, 1))
    make_visit(user, event=고정_행사, visited_on=date(2026, 11, 2))

    resp = client.get("/archive/visits/")

    칩들 = resp.context["category_chips"]
    assert "나이트 마켓" in [칩["label"] for 칩 in 칩들]
    assert "night_market" not in [칩["label"] for 칩 in 칩들]
    assert "night_market" not in [칩["token"] for 칩 in 칩들]
    assert "나이트 마켓" in [칩["token"] for 칩 in 칩들]


def test_방문_목록은_새_카테고리_칩의_필터를_걸면_그_카테고리_방문만_보여준다(
    user_client, make_event, make_visit
):
    user, client = user_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    새_행사 = make_event(title="새 카테고리 행사", category="night_market")
    고정_행사 = make_event(title="고정 카테고리 행사", category="popup_store")
    make_visit(user, event=새_행사, visited_on=date(2026, 11, 1))
    make_visit(user, event=고정_행사, visited_on=date(2026, 11, 2))

    resp = client.get("/archive/visits/", {"filter": "cat:나이트 마켓"})

    assert resp.context["selected_filter"] == "cat:나이트 마켓"
    assert resp.context["page_obj"].paginator.count == 1
    assert [row["subject"]["title"] for row in resp.context["visit_rows"]] == ["새 카테고리 행사"]


def test_새_카테고리_행이_많아져도_방문_목록의_쿼리_수는_행_수에_비례하지_않는다(
    user_client, make_event, make_visit
):
    user, client = user_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    for 번호 in range(2):
        행사 = make_event(title=f"적은 행 {번호}", category="night_market")
        make_visit(user, event=행사, visited_on=date(2026, 11, 1 + 번호))
    with CaptureQueriesContext(connection) as 적은_행_쿼리:
        client.get("/archive/visits/")

    Category.objects.create(slug="flea_market", label="벼룩 마켓")
    Category.objects.create(slug="book_market", label="책 마켓")
    for 번호, 슬러그 in enumerate(["night_market", "flea_market", "book_market"]):
        행사 = make_event(title=f"많은 행 {번호}", category=슬러그)
        make_visit(user, event=행사, visited_on=date(2026, 11, 10 + 번호))
    with CaptureQueriesContext(connection) as 많은_행_쿼리:
        client.get("/archive/visits/")

    assert len(많은_행_쿼리) == len(적은_행_쿼리)


def test_새_카테고리_행이_많아져도_찜_목록의_쿼리_수는_행_수에_비례하지_않는다(
    user_client, make_event, make_interest
):
    user, client = user_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    for 번호 in range(2):
        행사 = make_event(title=f"적은 행 {번호}", category="night_market")
        make_interest(user, 행사)
    with CaptureQueriesContext(connection) as 적은_행_쿼리:
        client.get("/archive/interests/")

    Category.objects.create(slug="flea_market", label="벼룩 마켓")
    Category.objects.create(slug="book_market", label="책 마켓")
    for 번호, 슬러그 in enumerate(["night_market", "flea_market", "book_market"]):
        행사 = make_event(title=f"많은 행 {번호}", category=슬러그)
        make_interest(user, 행사)
    with CaptureQueriesContext(connection) as 많은_행_쿼리:
        client.get("/archive/interests/")

    assert len(많은_행_쿼리) == len(적은_행_쿼리)


def test_새_카테고리_행이_많아져도_홈_기록_대기의_쿼리_수는_행_수에_비례하지_않는다(
    user_client, make_event, make_status
):
    user, client = user_client()
    Category.objects.create(slug="night_market", label="나이트 마켓")
    for 번호 in range(2):
        행사 = make_event(title=f"적은 행 {번호}", category="night_market")
        make_status(user, 행사, status="visited")
    # 첫 요청에만 나가는 일회성 쿼리(홈 설정 행 생성 등)를 먼저 소진한다.
    client.get("/")
    with CaptureQueriesContext(connection) as 적은_행_쿼리:
        client.get("/")

    Category.objects.create(slug="flea_market", label="벼룩 마켓")
    Category.objects.create(slug="book_market", label="책 마켓")
    for 번호, 슬러그 in enumerate(["night_market", "flea_market", "book_market"]):
        행사 = make_event(title=f"많은 행 {번호}", category=슬러그)
        make_status(user, 행사, status="visited")
    with CaptureQueriesContext(connection) as 많은_행_쿼리:
        client.get("/")

    assert len(많은_행_쿼리) == len(적은_행_쿼리)
