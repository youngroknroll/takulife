"""/archive/visits/ 서버 사이드 필터/검색/페이지네이션 테스트.

- filter=unofficial 은 직접 등록 항목 방문만 남긴다. 공식 행 유출은 금지되며,
  요약 카드(total_count/memo_count)는 필터와 무관하게 전체 기록 기준으로
  집계된다.
- filter=cat:<라벨> 은 공식 기록(카테고리 코드)과 비공식 기록(PersonalEntry에
  저장된 원시 라벨)을 OR로 매칭한다.
- 알 수 없는 필터 값("cat:", "cat:<미등록 라벨>" 포함)은 필터 없음으로
  대체되고, 응답은 항상 200(500 금지)이다.
- categories 와 has_unofficial 은 현재 페이지가 아니라 전체 기록에서 도출된다
  — 페이지네이션 때문에 필터 칩이 사라지면 안 된다.
- pager_query 는 페이지 링크에 filter 와 q 를 동시에 유지한다.
"""

from html.parser import HTMLParser
from urllib.parse import quote

import pytest

from archive.models import PersonalEntry

pytestmark = pytest.mark.web


def _make_official_visits(
    user,
    make_event,
    make_visit,
    count,
    *,
    category="popup_store",
    with_memo=False,
    date_prefix="2026-05",
):
    for i in range(count):
        ev = make_event(title=f"공식{i:02d}", category=category)
        make_visit(
            user,
            event=ev,
            visited_on=f"{date_prefix}-{i + 1:02d}",
            short_review="좋았어요" if with_memo else "",
        )


def _make_unofficial_visits(
    user,
    make_entry,
    make_visit,
    count,
    *,
    category="팝업스토어",
    with_memo=False,
    date_prefix="2026-06",
):
    for i in range(count):
        entry = make_entry(
            user, kind=PersonalEntry.Kind.PLACE, title=f"비공식{i:02d}", category=category
        )
        make_visit(
            user,
            personal_entry=entry,
            visited_on=f"{date_prefix}-{i + 1:02d}",
            short_review="좋았어요" if with_memo else "",
        )


# ---------------------------------------------------------------------------
# filter=unofficial 케이스
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUnofficialFilter:
    """filter=unofficial 은 비공식(personal_entry) 기록만 남긴다."""

    def test_비공식_필터를_적용하면_첫_페이지에_다섯_건까지_표시된다(
        self, user_client, make_event, make_visit, make_entry
    ):
        user, client = user_client()
        _make_unofficial_visits(user, make_entry, make_visit, 7)
        _make_official_visits(user, make_event, make_visit, 3)

        resp = client.get("/archive/visits/?filter=unofficial")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 7
        assert len(page_obj.object_list) == 5

    def test_비공식_필터_적용_중_두_번째_페이지를_조회하면_남은_두_건이_표시된다(
        self, user_client, make_event, make_visit, make_entry
    ):
        user, client = user_client()
        _make_unofficial_visits(user, make_entry, make_visit, 7)
        _make_official_visits(user, make_event, make_visit, 3)

        resp = client.get("/archive/visits/?filter=unofficial&page=2")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.number == 2
        assert len(page_obj.object_list) == 2

    def test_비공식_필터를_적용하면_공식_행사_방문_기록은_포함되지_않는다(
        self, user_client, make_event, make_visit, make_entry
    ):
        user, client = user_client()
        _make_unofficial_visits(user, make_entry, make_visit, 3)
        _make_official_visits(user, make_event, make_visit, 2)

        resp = client.get("/archive/visits/?filter=unofficial")

        visit_rows = resp.context["visit_rows"]
        for row in visit_rows:
            assert row["subject"]["is_official"] is False

    def test_비공식_필터가_적용되어도_요약_건수는_전체_기록_기준으로_집계된다(
        self, user_client, make_event, make_visit, make_entry
    ):
        """total_count 와 memo_count 는 필터와 무관하게 항상 전체 기록을 집계한다."""
        user, client = user_client()
        _make_unofficial_visits(user, make_entry, make_visit, 7, with_memo=True)
        _make_official_visits(user, make_event, make_visit, 3, with_memo=True)

        resp = client.get("/archive/visits/?filter=unofficial")

        assert resp.context["total_count"] == 10
        assert resp.context["memo_count"] == 10

    def test_비공식_필터로_조회하면_선택된_필터_값이_unofficial로_표시된다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/?filter=unofficial")

        assert resp.context["selected_filter"] == "unofficial"

    def test_필터_없이_조회하면_선택된_필터_값이_빈_문자열이다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/")

        assert resp.context["selected_filter"] == ""


# ---------------------------------------------------------------------------
# filter=cat:<라벨> 케이스
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCategoryFilter:
    """filter=cat:<라벨> 은 공식(코드 기준)과 비공식(라벨 기준)을 OR로 매칭한다."""

    def test_카테고리_필터는_같은_라벨의_공식_행사와_비공식_기록을_모두_포함한다(
        self, user_client, make_event, make_visit, make_entry
    ):
        user, client = user_client()
        # popup_store 공식 행사 2건 → CATEGORY_LABELS["popup_store"] = "팝업스토어"
        _make_official_visits(user, make_event, make_visit, 2, category="popup_store")
        # 같은 라벨("팝업스토어")의 비공식 기록 2건
        _make_unofficial_visits(user, make_entry, make_visit, 2, category="팝업스토어")
        # 다른 카테고리 1건 — 결과에 포함되면 안 됨
        other_ev = make_event(title="콜라보 행사", category="collaboration_cafe")
        make_visit(user, event=other_ev, visited_on="2026-03-01")

        resp = client.get("/archive/visits/?filter=cat:팝업스토어")

        assert resp.status_code == 200
        assert resp.context["page_obj"].paginator.count == 4

    def test_카테고리_필터를_적용하면_다른_카테고리_기록은_제외된다(
        self, user_client, make_event, make_visit
    ):
        user, client = user_client()
        _make_official_visits(user, make_event, make_visit, 3, category="popup_store")
        other_ev = make_event(title="콜라보", category="collaboration_cafe")
        make_visit(user, event=other_ev, visited_on="2026-04-01")

        resp = client.get("/archive/visits/?filter=cat:팝업스토어")

        visit_rows = resp.context["visit_rows"]
        for row in visit_rows:
            label = row["subject"]["category_label"]
            assert label == "팝업스토어"

    def test_카테고리_필터로_조회하면_선택된_필터_값이_cat_라벨로_표시된다(
        self, user_client, make_event, make_visit
    ):
        user, client = user_client()
        ev = make_event(title="팝업 행사", category="popup_store")
        make_visit(user, event=ev, visited_on="2026-06-01")

        resp = client.get("/archive/visits/?filter=cat:팝업스토어")

        assert resp.context["selected_filter"] == "cat:팝업스토어"


# ---------------------------------------------------------------------------
# 잘못된 필터 값 → 대체 처리(200, 필터 없음)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBadFilterFallback:
    """알 수 없는 필터 값은 500을 내지 않고 조용히 필터 없음으로 대체된다."""

    def test_알_수_없는_필터_값으로_조회하면_필터_없이_전체가_표시된다(
        self, user_client, make_event, make_visit
    ):
        user, client = user_client()
        _make_official_visits(user, make_event, make_visit, 3)

        resp = client.get("/archive/visits/?filter=nonexistent")

        assert resp.status_code == 200
        assert resp.context["selected_filter"] == ""
        assert resp.context["page_obj"].paginator.count == 3

    def test_카테고리_라벨_없이_cat_필터를_적용하면_필터가_무시된다(
        self, user_client, make_event, make_visit
    ):
        user, client = user_client()
        _make_official_visits(user, make_event, make_visit, 2)

        resp = client.get("/archive/visits/?filter=cat:")

        assert resp.status_code == 200
        assert resp.context["selected_filter"] == ""
        assert resp.context["page_obj"].paginator.count == 2

    def test_존재하지_않는_카테고리_라벨로_필터링하면_필터가_무시된다(
        self, user_client, make_event, make_visit
    ):
        """사용자 본인 데이터에서 도출된 화이트리스트에 없는 cat: 라벨은 필터가 무시된다."""
        user, client = user_client()
        ev = make_event(title="팝업", category="popup_store")
        make_visit(user, event=ev, visited_on="2026-06-01")

        resp = client.get("/archive/visits/?filter=cat:없는라벨")

        assert resp.status_code == 200
        assert resp.context["selected_filter"] == ""
        assert resp.context["page_obj"].paginator.count == 1


# ---------------------------------------------------------------------------
# categories 와 has_unofficial 은 현재 페이지가 아니라 전체 데이터에서 도출
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCategoriesFromFullData:
    """categories 칩 목록과 has_unofficial 은 전체 기록을 반영해야 한다."""

    def test_두_번째_페이지에만_있는_카테고리도_카테고리_목록에_표시된다(
        self, user_client, make_event, make_visit
    ):
        user, client = user_client()
        # 팝업 기록 5건(최신) — 1페이지를 채움
        for i in range(5):
            ev = make_event(title=f"팝업{i}", category="popup_store")
            make_visit(user, event=ev, visited_on=f"2026-06-{i + 1:02d}")
        # 콜라보 카페 기록 1건(과거) — 2페이지에 위치
        ev2 = make_event(title="콜라보 행사", category="collaboration_cafe")
        make_visit(user, event=ev2, visited_on="2026-05-01")

        resp = client.get("/archive/visits/")

        chips = resp.context["category_chips"]
        tokens = [chip["token"] for chip in chips]
        labels = [chip["label"] for chip in chips]
        assert "팝업스토어" in tokens
        assert "팝업스토어" in labels
        assert "콜라보 카페" in tokens  # 이전 페이지별 로직이었다면 누락됐을 항목
        assert "콜라보 카페" in labels

    def test_비공식_기록이_두_번째_페이지에_있어도_비공식_보유_여부는_참으로_표시된다(
        self, user_client, make_event, make_visit, make_entry
    ):
        user, client = user_client()
        # 공식 기록 5건(최신) → 1페이지를 채움
        for i in range(5):
            ev = make_event(title=f"공식{i}", category="popup_store")
            make_visit(user, event=ev, visited_on=f"2026-06-{i + 1:02d}")
        # 비공식 기록 1건(과거) → 2페이지에 위치
        entry = make_entry(
            user, kind=PersonalEntry.Kind.PLACE, title="비공식 카페", category="카페"
        )
        make_visit(user, personal_entry=entry, visited_on="2026-05-01")

        resp = client.get("/archive/visits/")

        assert resp.context["has_unofficial"] is True

    def test_공식_행사_방문_기록이_있으면_공식_보유_여부가_참으로_표시된다(
        self, user_client, make_event, make_visit
    ):
        user, client = user_client()
        ev = make_event(title="공식 행사")
        make_visit(user, event=ev, visited_on="2026-06-01")

        resp = client.get("/archive/visits/")

        assert resp.context["has_official"] is True

    def test_비공식_기록만_있으면_공식_보유_여부가_거짓으로_표시된다(
        self, user_client, make_visit, make_entry
    ):
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="비공식")
        make_visit(user, personal_entry=entry, visited_on="2026-06-01")

        resp = client.get("/archive/visits/")

        assert resp.context["has_official"] is False


# ---------------------------------------------------------------------------
# pager_query 는 filter 와 q 를 함께 유지한다
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVisitsPagerQuery:
    """pager_query 는 filter 와 q 값을 실어 페이지네이션에서 유실되지 않게 한다."""

    def test_비공식_필터_적용_중_페이지네이션_링크에_필터_값이_유지된다(
        self, user_client, make_visit, make_entry
    ):
        user, client = user_client()
        _make_unofficial_visits(user, make_entry, make_visit, 7)  # 2쪽 분량

        resp = client.get("/archive/visits/?filter=unofficial")

        pager_query = resp.context["pager_query"]
        assert "filter=unofficial" in pager_query
        assert b"page=2" in resp.content  # 페이저가 2페이지 링크를 렌더링함

    def test_필터와_검색어를_함께_적용하면_페이지네이션_링크에_둘_다_유지된다(
        self, user_client, make_visit, make_entry
    ):
        user, client = user_client()
        _make_unofficial_visits(user, make_entry, make_visit, 7)

        resp = client.get("/archive/visits/?filter=unofficial&q=abc")

        assert resp.status_code == 200
        pager_query = resp.context["pager_query"]
        assert "filter=unofficial" in pager_query
        assert "q=abc" in pager_query

    def test_필터와_검색어가_모두_없으면_페이지네이션_쿼리는_비어있다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/")

        assert resp.context["pager_query"] == ""

    def test_검색어만_있으면_페이지네이션_쿼리에_검색어만_포함된다(
        self, user_client, make_visit, make_entry
    ):
        user, client = user_client()
        _make_unofficial_visits(user, make_entry, make_visit, 7)

        resp = client.get("/archive/visits/?q=비공식")

        pager_query = resp.context["pager_query"]
        assert "q=" in pager_query
        assert "filter" not in pager_query

    def test_오래된순_정렬_적용_중_페이지네이션_링크에_정렬_값이_유지된다(
        self, user_client, make_event, make_visit
    ):
        user, client = user_client()
        _make_official_visits(user, make_event, make_visit, 7)  # 2쪽 분량

        resp = client.get("/archive/visits/?sort=oldest")

        assert resp.status_code == 200
        pager_query = resp.context["pager_query"]
        assert "sort=oldest" in pager_query
        assert b"page=2" in resp.content  # 페이저가 2페이지 링크를 렌더링함

    def test_필터와_오래된순_정렬을_함께_적용하면_필터_링크에도_정렬_값이_유지된다(
        self, user_client, make_event, make_visit, make_entry
    ):
        user, client = user_client()
        _make_unofficial_visits(user, make_entry, make_visit, 3)
        _make_official_visits(user, make_event, make_visit, 2)

        resp = client.get("/archive/visits/?filter=unofficial&sort=oldest")

        assert resp.status_code == 200
        assert "sort=oldest" in resp.context["search_suffix"]


# ---------------------------------------------------------------------------
# 트랙 43-2 C-12·C-13: 카테고리 칩은 표시만 번역되고 토큰은 한국어 원문이다
# ---------------------------------------------------------------------------

_POPUP_TOKEN = quote("팝업스토어")


class _ChipCollector(HTMLParser):
    """`.chips` 안의 `<a class="chip">`를 (href, aria-current, 텍스트, lang 범위)로 모은다."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._depth = 0
        self._chip = None
        self.chips = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and "chips" in (attrs.get("class") or "").split():
            self._depth = 1
        elif self._depth and tag == "div":
            self._depth += 1
        elif self._depth and tag == "a" and "chip" in (attrs.get("class") or "").split():
            self._chip = {
                "href": attrs.get("href"),
                "current": attrs.get("aria-current"),
                "lang": attrs.get("lang"),
                "text": "",
            }

    def handle_endtag(self, tag):
        if tag == "a" and self._chip is not None:
            self._chip["text"] = " ".join(self._chip["text"].split())
            self.chips.append(self._chip)
            self._chip = None
        elif tag == "div" and self._depth:
            self._depth -= 1

    def handle_data(self, data):
        if self._chip is not None:
            self._chip["text"] += data


def _category_chips(resp):
    collector = _ChipCollector()
    collector.feed(resp.content.decode())
    return [c for c in collector.chips if c["href"].startswith("?filter=cat:")]


@pytest.mark.django_db
class TestCategoryChipTranslation:
    # C-12 — Red 예측: 영어 칩 텍스트가 지금은 한국어 라벨이라 Red.
    def test_영어_방문_기록_칩은_번역_라벨이고_링크는_한국어_원문_토큰이다(
        self, user_client, make_event, make_visit
    ):
        user, client = user_client()
        make_visit(
            user,
            event=make_event(title="팝업 행사", category="popup_store"),
            visited_on="2026-05-01",
        )
        make_visit(
            user,
            event=make_event(title="콜라보 행사", category="collaboration_cafe"),
            visited_on="2026-05-02",
        )

        chips = _category_chips(client.get("/archive/visits/", HTTP_ACCEPT_LANGUAGE="en"))

        popup = [c for c in chips if c["text"] == "Pop-up store"]
        assert len(popup) == 1
        assert popup[0]["href"] == f"?filter=cat:{_POPUP_TOKEN}"
        assert popup[0]["lang"] is None

    # C-12 토큰 왕복 — Red 예측: 칩 텍스트 단언 때문에 Red(필터링 자체는 지금도 동작).
    def test_영어_칩_링크를_그대로_요청하면_필터가_적용되고_칩이_현재_칩이다(
        self, user_client, make_event, make_visit
    ):
        user, client = user_client()
        make_visit(
            user,
            event=make_event(title="팝업 행사", category="popup_store"),
            visited_on="2026-05-01",
        )
        make_visit(
            user,
            event=make_event(title="콜라보 행사", category="collaboration_cafe"),
            visited_on="2026-05-02",
        )
        first = _category_chips(client.get("/archive/visits/", HTTP_ACCEPT_LANGUAGE="en"))
        href = [c for c in first if c["text"] == "Pop-up store"][0]["href"]

        resp = client.get(f"/archive/visits/{href}", HTTP_ACCEPT_LANGUAGE="en")

        assert resp.status_code == 200
        assert resp.context["page_obj"].paginator.count == 1
        current = [c["text"] for c in _category_chips(resp) if c["current"] == "page"]
        assert current == ["Pop-up store"]

    # C-13 — Red 예측: en은 칩 텍스트가 한국어라 Red, ko는 Green.
    @pytest.mark.parametrize(
        "headers, label", [({}, "팝업스토어"), ({"HTTP_ACCEPT_LANGUAGE": "en"}, "Pop-up store")]
    )
    def test_공식과_개인_팝업스토어_기록은_칩_하나로_합쳐져_네_건이_나온다(
        self, user_client, make_event, make_visit, make_entry, headers, label
    ):
        user, client = user_client()
        _make_official_visits(user, make_event, make_visit, 2, category="popup_store")
        _make_unofficial_visits(user, make_entry, make_visit, 2, category="팝업스토어")

        chips = _category_chips(client.get("/archive/visits/", **headers))
        filtered = client.get(f"/archive/visits/?filter=cat:{_POPUP_TOKEN}", **headers)

        assert [(c["text"], c["href"]) for c in chips] == [(label, f"?filter=cat:{_POPUP_TOKEN}")]
        assert filtered.context["page_obj"].paginator.count == 4


class _RecordCatCollector(HTMLParser):
    """`.record-row-cat` 요소마다 (텍스트, 요소와 조상에 lang 속성이 있는지)를 모은다."""

    _VOID = frozenset(
        "br hr img input link meta source wbr area base col embed param track".split()
    )

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._stack = []
        self._open = None
        self.found = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in self._VOID:
            return
        self._stack.append((tag, attrs.get("lang")))
        if "record-row-cat" in (attrs.get("class") or "").split():
            marked = any(lang is not None for t, lang in self._stack if t != "html")
            self._open = {"depth": len(self._stack), "text": "", "marked": marked}

    def handle_endtag(self, tag):
        if self._open is not None and len(self._stack) == self._open["depth"]:
            self._open["text"] = " ".join(self._open["text"].split())
            self.found.append(self._open)
            self._open = None
        if self._stack and self._stack[-1][0] == tag:
            self._stack.pop()

    def handle_data(self, data):
        if self._open is not None:
            self._open["text"] += data


@pytest.mark.django_db
class TestVisitRowCategoryTranslation:
    # 변이: `_archive_results_visits.html`의 `.record-row-cat`에 `lang="ko"`를 다시 넣으면
    # 영어 단언이 Red, 한국어 단언은 lang 속성이 새로 붙으면 Red.
    @pytest.mark.parametrize(
        "headers, label", [({}, "팝업스토어"), ({"HTTP_ACCEPT_LANGUAGE": "en"}, "Pop-up store")]
    )
    def test_방문_행의_카테고리는_번역_라벨이고_lang_표시가_없다(
        self, user_client, make_event, make_visit, headers, label
    ):
        user, client = user_client()
        make_visit(
            user,
            event=make_event(title="팝업 행사", category="popup_store"),
            visited_on="2026-05-01",
        )

        collector = _RecordCatCollector()
        collector.feed(client.get("/archive/visits/", **headers).content.decode())

        assert [(c["text"], c["marked"]) for c in collector.found] == [(label, False)]
