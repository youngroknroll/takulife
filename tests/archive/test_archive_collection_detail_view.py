"""읽기 전용 굿즈 상세 페이지(core.views, `archive_collection_item_detail`,
URL 이름 "collection-detail-page", 라우트 `/collection/<int:item_id>/`) 테스트.

이 페이지는 소유자 범위다: 소유자가 아니면 404, 비로그인이면 로그인으로
리다이렉트된다. CollectionItem 하나의 이름·이미지와 파생 메타 헤드라인
블록(수량/교환 가능 수량/획득일/획득 경로/연결된 방문 기록)을 보여주며,
각 행은 값이 비어 있으면 조건부로 생략된다.
"""
import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveCollectionDetailViewAuth:
    def test_본인_소유_굿즈의_상세_페이지를_열면_200과_함께_이름이_표시된다(
        self, user_client, make_collection_item
    ):
        # CD-1
        user, client = user_client()
        item = make_collection_item(user, name="유메 아크릴 스탠드")

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))

        assert resp.status_code == 200
        assert "유메 아크릴 스탠드".encode() in resp.content

    def test_타인_소유_굿즈의_상세_페이지에_접근하면_404가_반환된다(
        self, make_user, user_client, make_collection_item
    ):
        # CD-2
        owner = make_user()
        item = make_collection_item(owner, name="소유자 전용 굿즈")
        attacker, client = user_client()

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))

        assert resp.status_code == 404

    def test_비로그인_사용자가_굿즈_상세_페이지를_열면_로그인_페이지로_리다이렉트된다(
        self, make_user, make_collection_item
    ):
        # CD-3
        item = make_collection_item(make_user(), name="비로그인 접근 굿즈")

        resp = Client().get(reverse("collection-detail-page", args=[item.pk]))

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchiveCollectionDetailQuantityRow:
    def test_수량이_있으면_수량_행에_개수가_표시된다(self, user_client, make_collection_item):
        # CD-4
        user, client = user_client()
        item = make_collection_item(user, name="수량표시굿즈", quantity=3)

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))

        assert "3개".encode() in resp.content

    def test_수량이_0이면_수량_행이_표시되지_않는다(self, user_client, make_collection_item):
        # CD-5
        user, client = user_client()
        item = make_collection_item(user, name="민트 아크릴 키링", quantity=0)

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))

        assert "0개".encode() not in resp.content


@pytest.mark.django_db
class TestArchiveCollectionDetailTradeableRow:
    def test_교환_가능_수량이_있으면_교환_배너에_개수가_표시된다(
        self, user_client, make_collection_item
    ):
        # CD-6
        user, client = user_client()
        item = make_collection_item(
            user, name="교환가능굿즈", quantity=2, tradeable_quantity=1
        )

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))
        content = resp.content

        assert "교환 가능".encode() in content
        assert "1개".encode() in content

    def test_교환_가능_수량이_0이면_교환_배너가_표시되지_않는다(
        self, user_client, make_collection_item
    ):
        # CD-7
        user, client = user_client()
        item = make_collection_item(
            user, name="코발트 배지 세트", quantity=2, tradeable_quantity=0
        )

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))

        assert "교환 가능".encode() not in resp.content


@pytest.mark.django_db
class TestArchiveCollectionDetailAcquiredOnRow:
    def test_획득일이_있으면_획득일_행에_날짜가_표시된다(self, user_client, make_collection_item):
        # CD-8
        user, client = user_client()
        item = make_collection_item(
            user, name="획득일있음굿즈", acquired_on="2026-03-01"
        )

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))

        assert "2026.03.01".encode() in resp.content

    def test_획득일이_없으면_획득일_행이_표시되지_않는다(self, user_client, make_collection_item):
        # CD-9
        user, client = user_client()
        item = make_collection_item(user, name="라벤더 스티커 시트", acquired_on=None)

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))

        assert "획득일".encode() not in resp.content


@pytest.mark.django_db
class TestArchiveCollectionDetailAcquisitionSourceRow:
    def test_획득_경로가_있으면_획득_경로_행에_값이_표시된다(
        self, user_client, make_collection_item
    ):
        # CD-10
        user, client = user_client()
        item = make_collection_item(
            user, name="획득경로있음굿즈", acquisition_source="트위터 나눔"
        )

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))

        assert "트위터 나눔".encode() in resp.content

    def test_획득_경로가_없으면_획득_경로_행이_표시되지_않는다(
        self, user_client, make_collection_item
    ):
        # CD-11
        user, client = user_client()
        item = make_collection_item(user, name="피치 클리어 파일", acquisition_source="")

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))

        assert "획득 경로".encode() not in resp.content


@pytest.mark.django_db
class TestArchiveCollectionDetailVisitRecordRow:
    """CD-12: 연결된 방문 행의 제목은 방문의 Event 제목을 우선하고, Event가
    없으면 PersonalEntry 제목으로 대체한다 — collection_edit.html:115의 기존
    분기와 동일하다. 두 대상 모두 정상 생성 경로(make_visit/make_event/make_entry)
    로 만들어, visit_record FK가 실제 동일 소유자 링크이며 수작업으로 연결한
    타인 소유 픽스처가 아니게 한다."""

    @pytest.mark.parametrize(
        "subject_kind",
        ["공식_행사", "비공식_장소"],
    )
    def test_연결된_방문_기록이_있으면_방문_상세로_연결되는_링크가_표시된다(
        self, user_client, make_event, make_entry, make_visit, make_collection_item, subject_kind
    ):
        user, client = user_client()
        if subject_kind == "공식_행사":
            event = make_event(title="연결된 공식 행사")
            record = make_visit(user, event=event, visited_on="2026-04-10")
            expected_title = "연결된 공식 행사"
        else:
            entry = make_entry(user, title="연결된 비공식 장소")
            record = make_visit(user, personal_entry=entry, visited_on="2026-04-10")
            expected_title = "연결된 비공식 장소"
        item = make_collection_item(user, name="방문연결굿즈", visit_record=record)

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))
        content = resp.content

        assert f"/archive/visits/{record.pk}/".encode() in content
        assert expected_title.encode() in content
        assert "변경 불가".encode() in content

    def test_연결된_방문_기록이_없으면_해당_행이_표시되지_않는다(
        self, user_client, make_collection_item
    ):
        # CD-13
        user, client = user_client()
        item = make_collection_item(user, name="세이지 미니 지갑", visit_record=None)

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))

        assert "/archive/visits/".encode() not in resp.content


@pytest.mark.django_db
class TestArchiveCollectionDetailSeriesInkConsistency:
    def test_같은_작품의_색_버킷은_목록과_상세에서_동일하다(
        self, user_client, make_collection_item
    ):
        # CD-14: 서로 다른 work_title 두 개를 순서대로 등록한다 — 상세 페이지가
        # (목록과 컬렉션 전체 팔레트를 공유하지 않고) 자체 단일 아이템 팔레트를
        # 다시 계산해도 버킷이 하나뿐이라 우연히 통과하는 일이 없도록 하기 위함.
        user, client = user_client()
        first = make_collection_item(user, name="A1", work_title="작품 A")
        second = make_collection_item(user, name="B1", work_title="작품 B")

        list_resp = client.get("/collection/")
        list_classes = {
            row["item"].pk: row["series_ink_class"] for row in list_resp.context["item_rows"]
        }

        for item in (first, second):
            detail_resp = client.get(reverse("collection-detail-page", args=[item.pk]))
            assert detail_resp.context["row"]["series_ink_class"] == list_classes[item.pk]


@pytest.mark.django_db
class TestArchiveCollectionDetailMetaHeadlineEmptyState:
    def test_메타_다섯_행이_모두_비어있으면_헤어라인_블록이_렌더되지_않는다(
        self, user_client, make_collection_item
    ):
        # CD-15
        user, client = user_client()
        item = make_collection_item(
            user,
            name="차콜 아크릴 스탠드",
            quantity=0,
            tradeable_quantity=0,
            acquired_on=None,
            acquisition_source="",
            visit_record=None,
        )

        resp = client.get(reverse("collection-detail-page", args=[item.pk]))
        content = resp.content

        assert "0개".encode() not in content
        assert "교환 가능".encode() not in content
        assert "획득일".encode() not in content
        assert "획득 경로".encode() not in content
        assert "/archive/visits/".encode() not in content
        # 위 라벨 부재 단언만으로는 `{% if meta_rows %}` 래퍼가 제거돼도(즉
        # 5행이 전부 비어 <dl>만 테두리로 남는 회귀) 잡히지 않는다 — `{% for %}`가
        # 0회 돌면 라벨은 어차피 안 나오기 때문이다. `<dl` 개봉 태그 자체의
        # 부재를 단언해야 그 회귀가 빨개진다. 이 페이지엔 메타 블록 외에
        # 다른 `<dl>`이 없으므로(base.html·collection_detail.html 전수 확인)
        # 태그명만 보는 이 단언은 마크업 결합이 과하지 않다.
        assert b"<dl" not in content
