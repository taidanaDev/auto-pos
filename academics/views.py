import functools
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect

from accounts.models import User
from .forms import (
    ManualStudentRegistrationForm,
    CurriculumForm,
    CourseForm,
    CurriculumCourseForm,
    CourseRequirementForm,
)
from .models import (
    Student,
    Curriculum,
    Course,
    CurriculumCourse,
    CourseRequirement,
)


def admin_required(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        if request.user.role != User.Role.ADMIN:
            messages.error(request, "You are not allowed to access this page.")
            return redirect("student_dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper

@admin_required
def student_registration(request):
    if request.method == "POST":
        form = ManualStudentRegistrationForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data


            safe_last_name = re.sub(r"[^a-z0-9]", "", data["last_name"].lower())
            temporary_password = f"{data['sr_code']}{safe_last_name}"


            with transaction.atomic():
                student_user = User.objects.create_user(
                    email=data["email"],
                    password=temporary_password,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    role=User.Role.STUDENT,
                    must_change_password=True,
                    is_active=True
                )

                Student.objects.create(
                    user=student_user,
                    sr_code=data["sr_code"],
                    curriculum=data["curriculum"],
                    year_level=int(data["section_code"][0]),
                    current_semester=int(data["section_code"][1]),
                    section_code=data["section_code"],
                    status=data["status"]
                )

            messages.success(
                request,
                f"Student registered successfully. Temporary password: {temporary_password}"
            )

            return redirect("student_registration")

    else:
        form = ManualStudentRegistrationForm()

    return render(request, "academics/student_registration.html", {
        "form": form,
    })


@admin_required
def student_list(request):
    students = Student.objects.select_related(
        "user",
        "curriculum",
        "curriculum__program"
    ).order_by("year_level", "section_code", "user__last_name")

    return render(request, "academics/student_list.html", {
        "students": students
    })

@login_required
@admin_required
def curriculum_list(request):
    curricula = Curriculum.objects.select_related(
        "program",
        "program__department"
    ).order_by("program__program_code", "curriculum_code")

    return render(request, "academics/curriculum_list.html", {
        "curricula": curricula
    })

@login_required
@admin_required
def curriculum_create(request):
    if request.method == "POST":
        form = CurriculumForm(request.POST)

        if form.is_valid():
            curriculum = form.save(commit=False)
            curriculum.created_by = request.user
            curriculum.save()

            messages.success(request, "Curriculum added successfully.")
            return redirect("curriculum_list")

    else:
        form = CurriculumForm()

    return render(request, "academics/curriculum_form.html", {
        "form": form,
        "page_title": "Add Curriculum"
    })

@login_required
@admin_required
def course_list(request):
    courses = Course.objects.all().order_by("course_code")

    return render(request, "academics/course_list.html", {
        "courses": courses
    })

@login_required
@admin_required
def course_create(request):
    if request.method == "POST":
        form = CourseForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Course added successfully.")
            return redirect("course_list")

    else:
        form = CourseForm()

    return render(request, "academics/course_form.html", {
        "form": form,
        "page_title": "Add Course"
    })

@login_required
@admin_required
def curriculum_course_list(request):
    curriculum_courses = CurriculumCourse.objects.select_related(
        "curriculum",
        "course"
    ).order_by("curriculum__curriculum_code", "year_level", "term", "display_order")

    return render(request, "academics/curriculum_course_list.html", {
        "curriculum_courses": curriculum_courses
    })

@login_required
@admin_required
def curriculum_course_create(request):
    if request.method == "POST":
        form = CurriculumCourseForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Course assigned to curriculum successfully.")
            return redirect("curriculum_course_list")

    else:
        form = CurriculumCourseForm()

    return render(request, "academics/curriculum_course_form.html", {
        "form": form,
        "page_title": "Add Curriculum Course"
    })

@login_required
@admin_required
def course_requirement_list(request):
    requirements = CourseRequirement.objects.select_related(
        "course",
        "required_course"
    ).order_by("course__course_code", "requirement_type")

    return render(request, "academics/course_requirement_list.html", {
        "requirements": requirements
    })

@login_required
@admin_required
def course_requirement_create(request):
    if request.method == "POST":
        form = CourseRequirementForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Course requirement added successfully.")
            return redirect("course_requirement_list")

    else:
        form = CourseRequirementForm()

    return render(request, "academics/course_requirement_form.html", {
        "form": form,
        "page_title": "Add Course Requirement"
    })