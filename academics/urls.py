from django.urls import path
from . import views

urlpatterns = [
    path("students/register/", views.student_registration, name="student_registration"),
    path("students/", views.student_list, name="student_list"),
]