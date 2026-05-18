from django.urls import path
from . import views

urlpatterns = [
    # Student registration
    path("students/register/", views.student_registration, name="student_registration"),
    path("students/", views.student_list, name="student_list"),

    # Curriculum
    path("curricula/", views.curriculum_list, name="curriculum_list"),
    path("curricula/add/", views.curriculum_create, name="curriculum_create"),
    path("curricula/upload/", views.curriculum_upload, name="curriculum_upload"),
    path("curricula/upload/confirm/", views.curriculum_upload_confirm, name="curriculum_upload_confirm"),

    # Courses
    path("courses/", views.course_list, name="course_list"),
    path("courses/add/", views.course_create, name="course_create"),

    # Curriculum courses
    path("curriculum-courses/", views.curriculum_course_list, name="curriculum_course_list"),
    path("curriculum-courses/add/", views.curriculum_course_create, name="curriculum_course_create"),

    # Course requirements
    path("course-requirements/", views.course_requirement_list, name="course_requirement_list"),
    path("course-requirements/add/", views.course_requirement_create, name="course_requirement_create"),

    # Students grade input
    path("students/my-grades/input/", views.input_grades, name="input_grades"),
    path("students/my-grades/records/", views.my_course_records, name="my_course_records"),
    
    # Student academic progress
    path("my-progress/", views.academic_progress, name="academic_progress"),
]