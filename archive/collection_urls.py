from django.urls import path

from .views import CollectionItemDetailView, CollectionItemListCreateView


urlpatterns = [
    path("", CollectionItemListCreateView.as_view(), name="collection-item-list-create"),
    path("<int:pk>/", CollectionItemDetailView.as_view(), name="collection-item-detail"),
]
