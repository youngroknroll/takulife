from django.urls import path

from .views import CollectionItemListCreateView


urlpatterns = [
    path("", CollectionItemListCreateView.as_view(), name="collection-item-list-create"),
]
