from django.urls import path
from .views import IndexDocumentView, SearchView, ChatView, ChatSSEView

urlpatterns = [
    path("index/", IndexDocumentView.as_view()),
    path("search/", SearchView.as_view()),
    path('chat/', ChatView.as_view(), name='ai_chat'),
    path('chat/stream/', ChatSSEView.as_view(), name='ai_chat_stream'),
]
