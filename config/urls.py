from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from accounts import views as accounts_views
from core import views as core_views
from web import views as web_views
from web.promotion_views import PromotePersonalEntryView


urlpatterns = [
    path("robots.txt", core_views.robots_txt, name="robots-txt"),
    path("", web_views.home, name="home"),
    path("events/", web_views.event_list, name="event-list-page"),
    path("events/calendar/", web_views.event_calendar, name="event-calendar-page"),
    path("events/<int:event_id>/", web_views.event_detail, name="event-detail-page"),
    path("archive/", web_views.archive, name="archive-page"),
    path(
        "archive/statuses/",
        web_views.archive_statuses,
        name="archive-statuses-page",
    ),
    path(
        "archive/visits/new/",
        web_views.archive_visit_create,
        name="archive-visit-create-page",
    ),
    path(
        "archive/visits/<int:record_id>/edit/",
        web_views.archive_visit_edit,
        name="archive-visit-edit-page",
    ),
    path(
        "archive/visits/<int:record_id>/",
        web_views.archive_visit_detail,
        name="archive-visit-detail-page",
    ),
    path("archive/visits/", web_views.archive_visits, name="archive-visits-page"),
    path("archive/calendar/", web_views.activity_calendar, name="archive-calendar-page"),
    path(
        "collection/new/",
        web_views.archive_collection_item_create,
        name="collection-create-page",
    ),
    path(
        "collection/<int:item_id>/edit/",
        web_views.archive_collection_item_edit,
        name="collection-edit-page",
    ),
    path(
        "collection/<int:item_id>/",
        web_views.archive_collection_item_detail,
        name="collection-detail-page",
    ),
    path(
        "collection/",
        web_views.archive_collection_items,
        name="collection-page",
    ),
    # 옛 컬렉션 URL. 위의 최상위 /collection/ 경로로 옮겨졌다. 북마크·링크가
    # 옛 경로를 여전히 가리킬 수 있어 쿼리스트링을 보존하는 임시(302) 리디렉션이다.
    path(
        "archive/collection/new/",
        RedirectView.as_view(
            url="/collection/new/", query_string=True, permanent=False
        ),
        name="archive-collection-create-page",
    ),
    path(
        "archive/collection/<int:item_id>/edit/",
        RedirectView.as_view(
            url="/collection/%(item_id)s/edit/", query_string=True, permanent=False
        ),
        name="archive-collection-edit-page",
    ),
    path(
        "archive/collection/",
        RedirectView.as_view(url="/collection/", query_string=True, permanent=False),
        name="archive-collection-page",
    ),
    path(
        "archive/personal/new/",
        web_views.archive_personal_entry_create,
        name="archive-personal-entry-create-page",
    ),
    # <int:entry_id>를 목록 경로보다 앞에 둬 위 컬렉션 블록과 순서를 맞춘다
    # (new/ -> <int:id>/edit/ -> <int:id>/ -> 목록). int 변환기는 "new"나
    # "edit"와 절대 매치되지 않으므로 이 순서가 동작에 영향을 주진 않지만,
    # 패턴 일관성을 위해 유지한다.
    path(
        "archive/personal/<int:entry_id>/edit/",
        web_views.archive_personal_entry_edit,
        name="archive-personal-entry-edit-page",
    ),
    path(
        "archive/personal/<int:entry_id>/",
        web_views.archive_personal_entry_detail,
        name="archive-personal-entry-detail-page",
    ),
    path(
        "archive/personal/",
        web_views.archive_personal_entries,
        name="archive-personal-entries-page",
    ),
    # 옛 비공식 목록 URL, /archive/personal/로 이름이 바뀌었다. 북마크·링크가
    # 옛 경로를 여전히 가리킬 수 있어 영구(301) 리디렉션으로 둔다.
    path(
        "archive/items/",
        RedirectView.as_view(url="/archive/personal/", permanent=True),
        name="archive-personal-entries-legacy-redirect",
    ),
    path("archive/interests/", web_views.archive_interests, name="archive-interests"),
    path("mypage/", web_views.mypage, name="mypage-page"),
    path("legal/privacy/", web_views.legal_privacy, name="legal-privacy-page"),
    path("legal/terms/", web_views.legal_terms, name="legal-terms-page"),
    # 옛 드래프트 검토 URL, 스태프 콘솔(/staff/drafts/…) 아래로 옮겨졌다.
    # 브라우저·북마크가 옛 링크를 여전히 가질 수 있어 ?next= 쿼리스트링을
    # 보존하는 임시(302) 리디렉션이다.
    path(
        "event-drafts/",
        RedirectView.as_view(url="/staff/drafts/", query_string=True, permanent=False),
        name="event-drafts-page",
    ),
    path(
        "event-drafts/<int:draft_id>/",
        RedirectView.as_view(
            url="/staff/drafts/%(draft_id)s/", query_string=True, permanent=False
        ),
        name="event-draft-detail-page",
    ),
    path("staff/", include("staff.urls")),
    # allauth include보다 먼저 등록해 이 명시적 경로들이 항상 먼저 매치되게
    # 한다(현재 allauth 자체 urlconf엔 "delete/"/"settings/" 패턴이 없지만,
    # 나중에 조용히 충돌하는 일을 막아둔다). delete_account는 accounts.views가
    # 아니라 web.views에 있다 — GET이 archive 카운트가 필요한데 accounts는
    # archive를 임포트할 수 없기 때문(경계 가드).
    path("accounts/delete/", web_views.delete_account, name="account-delete-page"),
    path(
        "accounts/delete/done/",
        accounts_views.delete_account_done,
        name="account-delete-done-page",
    ),
    path(
        "accounts/settings/",
        accounts_views.account_settings,
        name="account-settings-page",
    ),
    path("accounts/", include("allauth.urls")),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/events/", include("events.urls")),
    path("api/event-drafts/", include("drafts.urls")),
    path("api/user-event-statuses/", include("archive.urls")),
    path("api/visit-records/", include("archive.visit_urls")),
    path("api/event-interests/", include("archive.interest_urls")),
    path("api/collection-items/", include("archive.collection_urls")),
    path(
        "api/personal-entries/<int:pk>/promote/",
        PromotePersonalEntryView.as_view(),
        name="personal-entry-promote",
    ),
    path("api/personal-entries/", include("archive.personal_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
