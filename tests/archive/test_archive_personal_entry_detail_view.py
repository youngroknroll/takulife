"""비공식 장소(PersonalEntry) 읽기 전용 상세 페이지 테스트
(web.views, URL 이름 "archive-personal-entry-detail-page").

이 페이지는 PersonalEntry의 제목과, 별도로 `resp.context["is_submitted"]`를 통해
현재 공식 제보 상태를 보여준다. 소유자 범위로 제한되어 타인의 요청은 404, 비로그인
요청은 로그인 페이지로 리다이렉트된다.
"""
from datetime import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from archive.models import PersonalEntry, UserEventStatus
from core.vocab import archive_status_label

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchivePersonalEntryDetailView:
    def test_본인_소유_비공식_장소의_상세_페이지를_열면_200과_함께_제목이_표시된다(
        self, user_client, make_entry
    ):
        # PD-1
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="숨겨진 골목 소품샵")

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.status_code == 200
        assert "숨겨진 골목 소품샵".encode() in resp.content

    def test_타인_소유_비공식_장소의_상세_페이지에_접근하면_404가_반환된다(
        self, make_user, user_client, make_entry
    ):
        # PD-2
        owner = make_user()
        entry = make_entry(owner, kind=PersonalEntry.Kind.PLACE, title="소유자 전용 비공식 장소")
        attacker, client = user_client()

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.status_code == 404

    def test_비로그인_사용자가_비공식_장소_상세_페이지를_열면_로그인_페이지로_리다이렉트된다(
        self, make_user, make_entry
    ):
        # PD-3
        entry = make_entry(
            make_user(), kind=PersonalEntry.Kind.PLACE, title="비로그인 접근 비공식 장소"
        )

        resp = Client().get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url

    def test_상세_페이지를_직접_열면_비동기_컨트롤을_위한_CSRF_쿠키가_설정된다(
        self, user_client, make_entry
    ):
        """PD-11: 이 상세 페이지는 찜·상태·제보·삭제 4종의 비동기 컨트롤을 갖는다. 작성 시점에
        이미 통과하는 회귀 가드이지 Red-Green 시나리오가 아니다 — 뷰에 ``@ensure_csrf_cookie``가
        없어도 로그인 상태에서는 쿠키가 설정된다. 실제 출처는 이 뷰가 아니라
        `_topbar.html`의 로그아웃 폼 `{% csrf_token %}`(인증 사용자에게만 렌더되는 분기)이며,
        `base.html` 상속 경로를 통해 인증된 모든 페이지가 이를 우연히 물려받는다. 즉 이 페이지의
        비동기 컨트롤은 다른 파일(토파바)에 의존하고, 이 테스트가 그 결합을 잇는 유일한 가드다
        — 로그아웃이 fetch로 바뀌는 등 토파바가 변경되면 이 페이지의 컨트롤이 조용히 깨진다.
        이런 이유로 `@ensure_csrf_cookie`는 의도적으로 붙이지 않았다: 없어도 결함이 아니고,
        붙여도 실패하는 테스트로 증명할 수 없다(토파바가 이미 쿠키를 설정하므로 제거 뮤테이션이
        걸리지 않는다).

        user_client의 Client()는 force_login만 수행하고(HTTP 요청 없이 세션 쿠키만 심는다)
        어떤 요청도 아직 보내지 않았으므로 이 GET 이전엔 CSRF 쿠키가 없다. 또한
        `resp.cookies`는 이 응답이 새로 설정한 쿠키만 담으므로, 이전 요청에서 심어졌을 쿠키와
        섞일 걱정 없이 "이 상세 페이지가 쿠키를 설정했는가"만 검증한다.
        """
        # PD-11
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="CSRF 쿠키 확인용 장소")
        assert "csrftoken" not in client.cookies

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert "csrftoken" in resp.cookies


@pytest.mark.django_db
class TestArchivePersonalEntryDetailPromotionStatus:
    @pytest.mark.parametrize(
        ("promotion_status", "expected_is_submitted"),
        [
            (PersonalEntry.PromotionStatus.NONE, False),
            (PersonalEntry.PromotionStatus.SUBMITTED, True),
        ],
        ids=["미제보", "제보됨"],
    )
    def test_상황에서_공식_제보_상태를_열람하면_현재_제보_완료_여부가_그대로_표시된다(
        self, user_client, make_entry, promotion_status, expected_is_submitted
    ):
        # PD-8
        user, client = user_client()
        entry = make_entry(
            user,
            kind=PersonalEntry.Kind.PLACE,
            title="제보 상태 확인용 장소",
            promotion_status=promotion_status,
        )

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.context["is_submitted"] is expected_is_submitted


@pytest.mark.django_db
class TestArchivePersonalEntryDetailRecordInfo:
    def test_등록일과_마지막_수정일이_서로_다르면_각각_올바른_라벨에_표시된다(
        self, user_client, make_entry
    ):
        # PD-6
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="기록 정보 확인용 장소")
        PersonalEntry.objects.filter(pk=entry.pk).update(
            created_at=timezone.make_aware(datetime(2026, 3, 5)),
            updated_at=timezone.make_aware(datetime(2026, 6, 18)),
        )

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        entry.refresh_from_db()
        record_info_rows = resp.context["record_info_rows"]
        rows_by_label = {row["label"]: row["value"] for row in record_info_rows}
        assert rows_by_label["등록일"] == entry.created_at
        assert rows_by_label["마지막 수정"] == entry.updated_at


@pytest.mark.django_db
class TestArchivePersonalEntryDetailInterestAndStatus:
    """두 케이스의 Given이 크게 다르다: 있는 케이스는 "대상 항목의 id로 정확히 조회하는가"를
    증명하기 위한 미끼(다른 PersonalEntry에 걸린 다른 찜·다른 상태)가 필요하고, 없는 케이스는
    항목 하나만 있으면 된다. 파라미터화로 두 Given을 하나의 표에 욱여넣으면 미끼의 존재
    이유가 표 뒤로 숨어버려 DAMP를 해친다고 판단해 별도 테스트로 분리했다.

    미끼 하나로는 부족하다: 미끼가 대상보다 나중에 생성되면 정렬 없는 쿼리의 순회가 우연히
    대상을 먼저 내놓아, 조회 키(entry.id)를 무시하고 아무 값이나 집는 구현도 통과한다(뮤테이션
    테스트로 실측). PD-7b는 같은 사용자의 두 항목을 모두 조회해 각자 자기 값만 보이는지
    확인함으로써 쿼리 순회 순서와 무관하게 키-무시 구현을 잡는다.
    """

    def test_본인의_찜과_상태가_있으면_그_현재값이_상세_페이지_컨텍스트에_반영된다(
        self, user_client, make_entry, make_interest, make_status
    ):
        # PD-7 (있는 케이스)
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="찜과 상태 확인용 장소")
        decoy_entry = make_entry(
            user, kind=PersonalEntry.Kind.PLACE, title="미끼 비공식 장소"
        )
        # 미끼: 다른 항목에 다른 찜·다른 상태를 먼저 걸어, 뷰가 딕셔너리의 아무 값이나
        # 집어도 통과하지 않도록 만든다.
        make_interest(user, personal_entry=decoy_entry)
        make_status(user, personal_entry=decoy_entry, status=UserEventStatus.Status.VISITED)
        interest = make_interest(user, personal_entry=entry)
        status = make_status(user, personal_entry=entry, status=UserEventStatus.Status.PLANNED)

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.context["interest_id"] == interest.pk
        assert resp.context["status_slug"] == UserEventStatus.Status.PLANNED
        assert resp.context["status_id"] == status.pk

    def test_본인의_찜과_상태가_없으면_찜_id는_없고_상태_슬러그는_빈_값으로_반영된다(
        self, user_client, make_entry
    ):
        # PD-7 (없는 케이스)
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="찜과 상태 미보유 장소")

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.context["interest_id"] is None
        assert resp.context["status_slug"] == ""

    def test_같은_사용자의_서로_다른_항목_각각의_상세는_자기_항목의_찜과_상태만_보여준다(
        self, user_client, make_entry, make_interest, make_status
    ):
        """PD-7b: 조회 키(entry.id)를 무시하고 맵의 아무 값이나 집는 구현은 두 항목 중 최소
        하나에서 반드시 틀린다는 사실을, 쿼리 순회 순서에 기대지 않고 증명한다. PD-7의
        "있는 케이스"는 대상 항목 하나만 검증했는데, 그 대상을 미끼보다 먼저 만들었더니
        우연히 정렬되지 않은 쿼리의 첫 값이 대상과 일치해 `next(iter(map.values()))`
        같은 키-무시 구현도 통과시켰다(뮤테이션 테스트로 실측). 두 항목의 상세를 모두
        요청해 각자 자기 값만 보이는지 확인하면, 두 항목이 같은 딕셔너리를 조회하므로
        "첫 값"이 무엇이든 둘 중 하나는 반드시 어긋난다 — 정렬 순서와 무관하다.
        """
        user, client = user_client()
        entry_a = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="항목 A")
        entry_b = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="항목 B")
        interest_a = make_interest(user, personal_entry=entry_a)
        interest_b = make_interest(user, personal_entry=entry_b)
        status_a = make_status(user, personal_entry=entry_a, status=UserEventStatus.Status.PLANNED)
        status_b = make_status(user, personal_entry=entry_b, status=UserEventStatus.Status.VISITED)

        resp_a = client.get(reverse("archive-personal-entry-detail-page", args=[entry_a.pk]))
        resp_b = client.get(reverse("archive-personal-entry-detail-page", args=[entry_b.pk]))

        assert resp_a.context["interest_id"] == interest_a.pk
        assert resp_a.context["status_slug"] == UserEventStatus.Status.PLANNED
        assert resp_a.context["status_id"] == status_a.pk
        assert resp_b.context["interest_id"] == interest_b.pk
        assert resp_b.context["status_slug"] == UserEventStatus.Status.VISITED
        assert resp_b.context["status_id"] == status_b.pk


@pytest.mark.django_db
class TestArchivePersonalEntryDetailVisitRecords:
    def test_대상_장소에_연결된_방문_기록의_목록과_개수가_컨텍스트에_반영된다(
        self, user_client, make_entry, make_visit
    ):
        """PD-9b: 미끼로 같은 사용자가 소유한 다른 PersonalEntry에 연결된 방문 기록을 하나
        추가한다. 뷰가 list_visit_records_for_personal_entry(entry) 대신
        list_user_visit_records(user)처럼 사용자 전체 방문 기록을 넘기면 개수가 2가 아니라
        3이 되어 실패한다 — 순회 순서가 아니라 개수로 잡으므로 정렬과 무관하게 유효하다.
        """
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="방문 기록 확인용 장소")
        decoy_entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="미끼 장소")
        make_visit(user, personal_entry=decoy_entry, visited_on=datetime(2026, 1, 1).date())
        visit_1 = make_visit(user, personal_entry=entry, visited_on=datetime(2026, 2, 1).date())
        visit_2 = make_visit(user, personal_entry=entry, visited_on=datetime(2026, 3, 1).date())

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        visit_records = resp.context["visit_records"]
        assert len(visit_records) == 2
        assert resp.context["visit_records_count"] == 2
        assert {record.pk for record in visit_records} == {visit_1.pk, visit_2.pk}

    def test_연결된_방문_기록이_없으면_목록은_빈_상태로_표시된다(
        self, user_client, make_entry
    ):
        # PD-10
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="방문 기록 없는 장소")

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.context["visit_records"] == []
        assert resp.context["visit_records_count"] == 0


@pytest.mark.django_db
class TestArchivePersonalEntryDetailStatusLabel:
    """PD-12: 목록 뷰(archive_personal_entries)는 이미 어휘 정본
    archive_status_label()로 status_label/planned_label을 계산해 넘긴다
    (web/views/archive.py:487-488). 상세 뷰가 같은 문구를 템플릿 안에
    if/elif로 하드코딩하면, vocab을 고칠 때 목록은 따라가고 상세는
    안 따라가는 드리프트가 생긴다. 두 케이스의 Given 차이는 상태 유무뿐이므로
    파라미터화한다.
    """

    @pytest.mark.parametrize(
        "status",
        [UserEventStatus.Status.VISITED, None],
        ids=["상태가_있음", "상태가_없음"],
    )
    def test_상황에서_상태_필의_라벨이_어휘_정본에서_계산되어_전달된다(
        self, user_client, make_entry, make_status, status
    ):
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="상태 라벨 확인용 장소")
        if status is not None:
            make_status(user, personal_entry=entry, status=status)

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        expected_status_label = archive_status_label(status) if status else ""
        assert resp.context["status_label"] == expected_status_label
        assert resp.context["planned_label"] == archive_status_label("planned")
