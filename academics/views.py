import functools
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect
from django.db.models import Case, When, IntegerField

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
    StudentCourseRecord,
)

# ---------------------------------------------------------------------------
# Valid grade values: 1.00 to 5.00 in 0.25 increments
# ---------------------------------------------------------------------------
VALID_GRADES = {Decimal("1.00") + Decimal("0.25") * i for i in range(17)}


# ---------------------------------------------------------------------------
# Access-control decorators
# ---------------------------------------------------------------------------

def admin_required(view_func):
    """Allow only authenticated ADMIN users."""
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        if request.user.role != User.Role.ADMIN:
            messages.error(request, "You are not allowed to access this page.")
            return redirect("student_dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


def student_required(view_func):
    """Allow only authenticated STUDENT users."""
    # FIX 1: Added @functools.wraps — without it the wrapper loses the
    # original function name/docstring, breaking Django's view introspection.
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        if request.user.role != User.Role.STUDENT:
            messages.error(request, "You are not allowed to access this page.")
            return redirect("admin_dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Admin views
# FIX 2: Removed redundant @login_required from all admin views.
#         admin_required already checks is_authenticated, so stacking
#         @login_required on top is unnecessary and misleading.
# ---------------------------------------------------------------------------

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
                    is_active=True,
                )

                Student.objects.create(
                    user=student_user,
                    sr_code=data["sr_code"],
                    curriculum=data["curriculum"],
                    year_level=int(data["section_code"][0]),
                    current_semester=int(data["section_code"][1]),
                    section_code=data["section_code"],
                    status=data["status"],
                )

            messages.success(
                request,
                f"Student registered successfully. Temporary password: {temporary_password}",
            )
            return redirect("student_registration")

    else:
        form = ManualStudentRegistrationForm()

    return render(request, "academics/student_registration.html", {"form": form})


@admin_required
def student_list(request):
    students = Student.objects.select_related(
        "user",
        "curriculum",
        "curriculum__program",
    ).order_by("year_level", "section_code", "user__last_name")

    return render(request, "academics/student_list.html", {"students": students})


@admin_required
def curriculum_list(request):
    curricula = Curriculum.objects.select_related(
        "program",
        "program__department",
    ).order_by("program__program_code", "curriculum_code")

    return render(request, "academics/curriculum_list.html", {"curricula": curricula})


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
        "page_title": "Add Curriculum",
    })


@admin_required
def course_list(request):
    courses = Course.objects.all().order_by("course_code")
    return render(request, "academics/course_list.html", {"courses": courses})


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
        "page_title": "Add Course",
    })


@admin_required
def curriculum_course_list(request):
    curriculum_courses = CurriculumCourse.objects.select_related(
        "curriculum",
        "course",
    ).order_by("curriculum__curriculum_code", "year_level", "term", "display_order")

    return render(request, "academics/curriculum_course_list.html", {
        "curriculum_courses": curriculum_courses,
    })


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
        "page_title": "Add Curriculum Course",
    })


@admin_required
def course_requirement_list(request):
    requirements = CourseRequirement.objects.select_related(
        "course",
        "required_course",
    ).order_by("course__course_code", "requirement_type")

    return render(request, "academics/course_requirement_list.html", {
        "requirements": requirements,
    })


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
        "page_title": "Add Course Requirement",
    })


# ---------------------------------------------------------------------------
# Student views
# ---------------------------------------------------------------------------

@student_required
def input_grades(request):
    # Guard: ensure the logged-in user has a student profile.
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect("student_dashboard")

    # All courses in the student's assigned curriculum.
    curriculum_courses = CurriculumCourse.objects.select_related(
        "course",
        "curriculum"
    ).filter(
        curriculum=student.curriculum
    ).annotate(
        term_order=Case(
            When(term="first_sem", then=1),
            When(term="second_sem", then=2),
            When(term="midterm", then=3),
            output_field=IntegerField()
        )
    ).order_by(
        "year_level",
        "term_order",
        "display_order"
    )
    # Pre-load existing records into a dict keyed by course_id for O(1) lookup.
    existing_records = StudentCourseRecord.objects.filter(
        student=student,
    ).select_related("course")

    record_map = {record.course_id: record for record in existing_records}

    if request.method == "POST":
        school_year = request.POST.get("school_year", "").strip()

        # ----------------------------------------------------------------
        # FIX 8: Validate school_year format — any string previously passed.
        # ----------------------------------------------------------------
        if not school_year:
            messages.error(request, "School year is required.")
            return render(request, "academics/input_grades.html", {
                "student": student,
                "curriculum_courses": curriculum_courses,
                "record_map": record_map,
                "post_data": request.POST,
            })

        if not re.match(r"^\d{4}-\d{4}$", school_year):
            messages.error(
                request,
                "School year must follow the format YYYY-YYYY (e.g. 2024-2025).",
            )
            # FIX 6: Re-render instead of redirect to preserve entered data.
            return render(request, "academics/input_grades.html", {
                "student": student,
                "curriculum_courses": curriculum_courses,
                "record_map": record_map,
                "post_data": request.POST,
            })

        # ----------------------------------------------------------------
        # FIX 7: Wrap the entire save loop in transaction.atomic() so a
        # mid-loop failure does not leave a partial write in the database.
        # ----------------------------------------------------------------
        try:
            with transaction.atomic():
                for curriculum_course in curriculum_courses:
                    course = curriculum_course.course
                    grade_raw = request.POST.get(f"grade_{course.id}", "").strip()
                    remarks = request.POST.get(f"remarks_{course.id}", "").strip()

                    # Skip courses where no grade was entered.
                    if grade_raw == "":
                        continue

                    # FIX 3: Use Decimal instead of float to avoid
                    # floating-point imprecision on grade comparisons/storage.
                    try:
                        grade_value = Decimal(grade_raw)
                    except InvalidOperation:
                        messages.error(
                            request,
                            f"Invalid grade for {course.course_code}.",
                        )
                        return render(request, "academics/input_grades.html", {
                            "student": student,
                            "curriculum_courses": curriculum_courses,
                            "record_map": record_map,
                            "post_data": request.POST,
                        })

                    # Range check: 1.00 – 5.00.
                    if grade_value < Decimal("1.00") or grade_value > Decimal("5.00"):
                        messages.error(
                            request,
                            f"Grade for {course.course_code} must be between 1.00 and 5.00.",
                        )
                        return render(request, "academics/input_grades.html", {
                            "student": student,
                            "curriculum_courses": curriculum_courses,
                            "record_map": record_map,
                            "post_data": request.POST,
                        })

                    # FIX 4: Enforce 0.25 increment server-side.
                    # The HTML step attribute is a browser hint only and can be bypassed.
                    if grade_value not in VALID_GRADES:
                        messages.error(
                            request,
                            f"Grade for {course.course_code} must be in 0.25 increments "
                            f"(e.g. 1.00, 1.25, 1.50).",
                        )
                        return render(request, "academics/input_grades.html", {
                            "student": student,
                            "curriculum_courses": curriculum_courses,
                            "record_map": record_map,
                            "post_data": request.POST,
                        })

                    # FIX 5: Set status based on grade instead of always
                    # defaulting to IN_PROGRESS.
                    if grade_value <= Decimal("3.00"):
                        status = StudentCourseRecord.RecordStatus.PASSED
                    else:
                        status = StudentCourseRecord.RecordStatus.FAILED

                    StudentCourseRecord.objects.update_or_create(
                        student=student,
                        course=course,
                        school_year=school_year,
                        term=curriculum_course.term,
                        defaults={
                            "grade_value": grade_value,
                            "remarks": remarks,
                            "status": status,
                        },
                    )

        except Exception:
            messages.error(
                request,
                "An unexpected error occurred while saving grades. Please try again.",
            )
            return render(request, "academics/input_grades.html", {
                "student": student,
                "curriculum_courses": curriculum_courses,
                "record_map": record_map,
                "post_data": request.POST,
            })

        messages.success(request, "Grades saved successfully.")
        return redirect("my_course_records")

    # GET: render the blank/pre-filled grade input form.
    return render(request, "academics/input_grades.html", {
        "student": student,
        "curriculum_courses": curriculum_courses,
        "record_map": record_map,
    })


@student_required
def my_course_records(request):
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect("student_dashboard")

    records = StudentCourseRecord.objects.select_related(
        "course",
    ).filter(
        student=student,
    ).order_by("school_year", "term", "course__course_code")

    return render(request, "academics/my_course_records.html", {
        "student": student,
        "records": records,
    })
