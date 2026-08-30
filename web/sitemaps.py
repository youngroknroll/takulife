"""검색엔진에 노출할 URL 목록의 정본이다."""
from django.contrib.sitemaps import Sitemap
from django.contrib.sites.requests import RequestSite
from django.template.response import TemplateResponse
from django.urls import reverse

from events.models import Event


class EventSitemap(Sitemap):
    def items(self):
        return Event.objects.published().order_by("pk")

    def location(self, obj):
        return reverse("event-detail-page", args=[obj.id])


class StaticPageSitemap(Sitemap):
    # 정적 공개 페이지 화이트리스트다.
    def items(self):
        return [
            "home",
            "event-list-page",
            "event-calendar-page",
            "legal-privacy-page",
            "legal-terms-page",
        ]

    def location(self, name):
        return reverse(name)


def sitemap(request, sitemaps):
    # DB Site.domain(기본 example.com)을 참조하지 않고 요청 Host를 그대로 쓴다.
    site = RequestSite(request)
    urls = []
    for section in sitemaps.values():
        instance = section() if callable(section) else section
        urls.extend(instance.get_urls(page=1, site=site, protocol=request.scheme))
    return TemplateResponse(
        request, "sitemap.xml", {"urlset": urls}, content_type="application/xml"
    )
