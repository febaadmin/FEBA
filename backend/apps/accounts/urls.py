from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import entity_views, views

urlpatterns = [
    # Contexte d'entité (multi-entités) — résolu côté serveur uniquement.
    path("entity-context/", entity_views.EntityContextView.as_view(), name="entity_context"),
    path("entity-context/switch/", entity_views.EntitySwitchView.as_view(), name="entity_switch"),
    path("entity-context/log/", entity_views.EntitySwitchLogView.as_view(), name="entity_switch_log"),
    path("entity-context/memberships/", entity_views.MyMembershipsView.as_view(), name="my_memberships"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("me/", views.MeView.as_view(), name="me"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("users/", views.UserListCreateView.as_view(), name="user_list"),
    path("users/<int:pk>/", views.UserDetailView.as_view(), name="user_detail"),
    path("users/<int:pk>/toggle-active/", views.ToggleUserActiveView.as_view(), name="toggle_active"),
    path("users/<int:pk>/reset-password/", views.AdminResetPasswordView.as_view(), name="admin_reset_password"),
    path("recipients/", views.MessageRecipientsView.as_view(), name="recipients"),
    path("avatar/", views.AvatarUploadView.as_view(), name="avatar"),
]
