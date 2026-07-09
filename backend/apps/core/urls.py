from django.urls import path
from .platform_views import (
    TenantListCreateView, TenantDetailView,
    TenantSuspendView, TenantReactivateView,
    PlatformStatsView,
)

urlpatterns = [
    path('platform/schools/', TenantListCreateView.as_view(), name='platform-schools-list'),
    path('platform/schools/<slug:slug>/', TenantDetailView.as_view(), name='platform-school-detail'),
    path('platform/schools/<slug:slug>/suspend/', TenantSuspendView.as_view(), name='platform-school-suspend'),
    path('platform/schools/<slug:slug>/reactivate/', TenantReactivateView.as_view(), name='platform-school-reactivate'),
    path('platform/stats/', PlatformStatsView.as_view(), name='platform-stats'),
]
