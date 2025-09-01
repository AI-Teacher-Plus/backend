from django.urls import path
from .views import LoginView, RefreshView, LogoutView, UserContextView, UserListCreateView, UserDetailView


urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('refresh/', RefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('users/', UserListCreateView.as_view(), name='user_list_create'),
    path('users/<uuid:pk>/', UserDetailView.as_view(), name='user_detail'),
    path('user-context/', UserContextView.as_view(), name='user_context')
]
