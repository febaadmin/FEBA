from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("users/", views.UserListCreateView.as_view(), name="user_list"),
    path("users/<int:pk>/", views.UserDetailView.as_view(), name="user_detail"),
    path("users/<int:pk>/toggle-active/", views.ToggleUserActiveView.as_view(), name="toggle_active"),
    path("recipients/", views.MessageRecipientsView.as_view(), name="recipients"),
    path("avatar/", views.AvatarUploadView.as_view(), name="avatar"),
]
