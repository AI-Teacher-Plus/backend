from django.urls import path
from .views import IndexDocumentView, SearchView

urlpatterns = [
    path("index/", IndexDocumentView.as_view()),
    path("search/", SearchView.as_view()),
]
