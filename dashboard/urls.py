from django.urls import path
from . import views

urlpatterns = [
    path("", views.landing_page, name="landing_page"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("student-dashboard/", views.student_dashboard, name="student_dashboard"),
]