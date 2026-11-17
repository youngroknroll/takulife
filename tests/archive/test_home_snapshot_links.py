"""홈 '내 컬렉션 현황' 패널의 '기록 대기' 행에 걸린 링크가 맞는 주소를 가리키는지
검증한다."""

import html
from html.parser import HTMLParser
import re

import pytest

pytestmark = [pytest.mark.django_db, pytest.mark.web]


class _기록_대기_행_링크_수집기(HTMLParser):
    """`li.snapshot-record-row`마다 안의 `a`들의 (공백 정리한 텍스트, href)를 모은다."""

    def __init__(self):
        super().__init__()
        self.행들 = []
        self._li_깊이 = 0
        self._행_깊이 = None
        self._href = None
        self._텍스트 = []

    def handle_starttag(self, tag, attrs):
        속성 = dict(attrs)
        if tag == "li":
            self._li_깊이 += 1
            클래스 = (속성.get("class") or "").split()
            if self._행_깊이 is None and "snapshot-record-row" in 클래스:
                self._행_깊이 = self._li_깊이
                self.행들.append([])
        elif tag == "a" and self._행_깊이 is not None:
            self._href = html.unescape(속성.get("href") or "")
            self._텍스트 = []

    def handle_data(self, data):
        if self._href is not None:
            self._텍스트.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.행들[-1].append((" ".join("".join(self._텍스트).split()), self._href))
            self._href = None
        elif tag == "li":
            if self._행_깊이 == self._li_깊이:
                self._행_깊이 = None
            self._li_깊이 -= 1


def _기록_대기_행_링크들(본문):
    수집기 = _기록_대기_행_링크_수집기()
    수집기.feed(본문)
    return 수집기.행들


def test_기록_대기_공식_행사_행의_제목은_그_행사_상세_주소로_연결된다(
    user_client, make_user, make_event, make_status
):
    user, client = user_client()
    행사 = make_event(title="링크 행사")
    make_status(user, 행사, status="visited")
    남의_행사 = make_event(title="남의 행사")
    make_status(make_user(), 남의_행사, status="visited")

    resp = client.get("/")

    assert resp.status_code == 200
    링크들 = [링크 for 행 in _기록_대기_행_링크들(resp.content.decode()) for 링크 in 행]
    assert ("링크 행사", f"/events/{행사.id}/") in 링크들
    assert all(href != f"/events/{남의_행사.id}/" for _, href in 링크들)


def test_기록_대기_직접_등록_항목_행의_제목은_그_항목_상세_주소로_연결된다(
    user_client, make_user, make_entry, make_status
):
    user, client = user_client()
    make_entry(user, title="먼저 만든 항목")
    항목 = make_entry(user, title="내 방문지")
    make_status(user, personal_entry=항목, status="visited")
    남의_사용자 = make_user()
    남의_항목 = make_entry(남의_사용자, title="남의 방문지")
    make_status(남의_사용자, personal_entry=남의_항목, status="visited")

    resp = client.get("/")

    assert resp.status_code == 200
    링크들 = [링크 for 행 in _기록_대기_행_링크들(resp.content.decode()) for 링크 in 행]
    assert ("내 방문지", f"/archive/personal/{항목.id}/") in 링크들
    assert all(href != f"/archive/personal/{남의_항목.id}/" for _, href in 링크들)


def test_기록_대기_비공개_행사_행은_제목이_링크가_아니고_기록_링크만_남는다(
    user_client, make_draft_event, make_status
):
    user, client = user_client()
    행사 = make_draft_event(title="비공개 행사")
    make_status(user, 행사, status="visited")

    resp = client.get("/")

    assert resp.status_code == 200
    본문 = resp.content.decode()
    행들 = _기록_대기_행_링크들(본문)
    assert len(행들) == 1
    assert [href for _, href in 행들[0]] == [f"/archive/visits/new/?subject=event:{행사.id}"]
    assert "비공개 행사" in 본문


@pytest.mark.parametrize(
    "종류",
    [
        pytest.param("event", id="공식_행사"),
        pytest.param("personal", id="직접_등록"),
    ],
)
def test_기록_대기_행의_기록_링크는_제목이_링크가_돼도_그_대상의_기록_작성_주소를_가리킨다(
    user_client, make_event, make_entry, make_status, 종류
):
    user, client = user_client()
    if 종류 == "event":
        대상 = make_event(title="기록 행사")
        make_status(user, 대상, status="visited")
    else:
        make_entry(user, title="먼저 만든 항목")
        대상 = make_entry(user, title="기록 항목")
        make_status(user, personal_entry=대상, status="visited")

    resp = client.get("/")

    행들 = _기록_대기_행_링크들(resp.content.decode())
    assert len(행들) == 1
    기록_주소들 = [href for _, href in 행들[0] if href.startswith("/archive/visits/new/?subject=")]
    assert 기록_주소들 == [f"/archive/visits/new/?subject={종류}:{대상.id}"]


class _전체_링크_수집기(HTMLParser):
    """페이지의 `a`마다 (href, 공백 정리한 텍스트, 안의 img 수)를 모은다."""

    def __init__(self):
        super().__init__()
        self.링크들 = []
        self._href = None
        self._텍스트 = []
        self._img_수 = 0

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = html.unescape(dict(attrs).get("href") or "")
            self._텍스트 = []
            self._img_수 = 0
        elif tag == "img" and self._href is not None:
            self._img_수 += 1

    def handle_data(self, data):
        if self._href is not None:
            self._텍스트.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.링크들.append((self._href, " ".join("".join(self._텍스트).split()), self._img_수))
            self._href = None


def _전체_링크들(본문):
    수집기 = _전체_링크_수집기()
    수집기.feed(본문)
    return 수집기.링크들


def test_홈의_최근_등록한_굿즈_카드는_본인_굿즈의_상세_주소로만_연결된다(
    user_client, make_user, make_collection_item
):
    user, client = user_client()
    굿즈 = make_collection_item(user, name="내 굿즈")
    make_collection_item(make_user(), name="남의 굿즈")

    resp = client.get("/")

    assert resp.status_code == 200
    링크들 = _전체_링크들(resp.content.decode())
    굿즈_주소들 = [href for href, _, _ in 링크들 if re.match(r"/collection/\d+/", href)]
    assert 굿즈_주소들 == [f"/collection/{굿즈.id}/"]


def test_최근_등록한_굿즈_카드의_사진과_이름은_같은_링크_안에_있다(
    user_client, make_collection_item
):
    user, client = user_client()
    굿즈 = make_collection_item(user, name="사진 굿즈", image="collection_items/sample.png")

    resp = client.get("/")

    assert resp.status_code == 200
    상세_링크들 = [
        링크 for 링크 in _전체_링크들(resp.content.decode()) if 링크[0] == f"/collection/{굿즈.id}/"
    ]
    assert len(상세_링크들) == 1
    _, 텍스트, img_수 = 상세_링크들[0]
    assert 텍스트 == "사진 굿즈"
    assert img_수 == 1


class _기록_링크_이름_수집기(HTMLParser):
    """행(`li.snapshot-record-row`)마다 기록 링크의 id·aria-labelledby와 제목 요소의 id를,
    문서 전체의 모든 id 값을 모은다."""

    def __init__(self):
        super().__init__()
        self.행들 = []
        self.모든_id = []
        self._li_깊이 = 0
        self._행_깊이 = None

    def handle_starttag(self, tag, attrs):
        속성 = dict(attrs)
        if 속성.get("id") is not None:
            self.모든_id.append(속성["id"])
        if tag == "li":
            self._li_깊이 += 1
            if self._행_깊이 is None and "snapshot-record-row" in (속성.get("class") or "").split():
                self._행_깊이 = self._li_깊이
                self.행들.append({"링크들": [], "제목_id": None})
        elif self._행_깊이 is not None:
            행 = self.행들[-1]
            if tag == "a" and html.unescape(속성.get("href") or "").startswith(
                "/archive/visits/new/?subject="
            ):
                행["링크들"].append(
                    {"id": 속성.get("id"), "aria-labelledby": 속성.get("aria-labelledby")}
                )
            if "snapshot-record-title" in (속성.get("class") or "").split():
                행["제목_id"] = 속성.get("id")

    def handle_endtag(self, tag):
        if tag == "li":
            if self._행_깊이 == self._li_깊이:
                self._행_깊이 = None
            self._li_깊이 -= 1


def test_기록_대기_행의_기록_링크는_행마다_유일한_id로_자기_행의_제목을_이름으로_가리킨다(
    user_client, make_event, make_entry, make_status
):
    user, client = user_client()
    행사 = make_event(title="번호 행사")
    make_status(user, 행사, status="visited")
    항목 = make_entry(user, id=행사.id, title="같은 번호 항목")
    make_status(user, personal_entry=항목, status="visited")

    resp = client.get("/")

    수집기 = _기록_링크_이름_수집기()
    수집기.feed(resp.content.decode())
    assert len(수집기.행들) == 2
    토큰들 = []
    for 행 in 수집기.행들:
        assert len(행["링크들"]) == 1
        링크 = 행["링크들"][0]
        assert 링크["aria-labelledby"] is not None
        분리 = 링크["aria-labelledby"].split()
        assert len(분리) == 2
        링크_토큰, 제목_토큰 = 분리
        assert 링크_토큰 == 링크["id"]
        assert 제목_토큰 == 행["제목_id"]
        토큰들 += [링크_토큰, 제목_토큰]
    assert len(set(토큰들)) == 4
    assert all(수집기.모든_id.count(토큰) == 1 for 토큰 in 토큰들)
