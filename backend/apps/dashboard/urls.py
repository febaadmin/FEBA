from django.urls import path
from . import views

urlpatterns = [
    path("admin/", views.AdminDashboardView.as_view(), name="admin-dashboard"),
    path("teacher/", views.TeacherDashboardView.as_view(), name="teacher-dashboard"),
    path("parent/", views.ParentDashboardView.as_view(), name="parent-dashboard"),
    path("student/", views.StudentDashboardView.as_view(), name="student-dashboard"),
]