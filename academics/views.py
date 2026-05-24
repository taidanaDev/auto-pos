import functools
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect
from django.db.models import Case, When, IntegerField
from django.core.exceptions import ValidationError
from django.http import JsonResponse

from accounts.models import User
from .forms import (
    CurriculumUploadForm,
    ManualStudentRegistrationForm,
    CurriculumForm,
    CourseForm,
    CurriculumCourseForm,
    CourseRequirementForm,
    GradeUploadForm,
    StudentImportForm,
)
from .models import (
    Student,
    Curriculum,
    Course,
    CurriculumCourse,
    CourseRequirement,
    StudentCourseRecord,
)
from .upload_services import (
    read_curriculum_file,
    validate_curriculum_rows,
    save_curriculum_rows,
    validate_preview_rows,
)
from .grade_upload_services import (
    extract_text_from_grade_file,
    parse_grade_rows_from_text,
    validate_grade_preview_rows,
    save_grade_rows,
)
from .email_service import send_student_account_welcome_email_async
from .services import get_student_academic_progress
from .student_import_services import (
    read_student_import_file,
    validate_student_import_rows,
    validate_student_preview_rows,
    save_student_import_rows,
)

# Valid grade values: 1.00 to 5.00 in 0.25 increments

VALID_GRADES = {Decimal("1.00") + Decimal("0.25") * i for i in range(17)}



# Access-control decorators
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
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        if request.user.role != User.Role.STUDENT:
            messages.error(request, "You are not allowed to access this page.")
            return redirect("admin_dashboard")

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
                
            send_student_account_welcome_email_async(
                student_user,
                data["sr_code"],
                temporary_password
            )

            messages.success(
                request,
                "Student registered successfully.",
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


# Student views
@student_required
def input_grades(request):
    # Guard: ensure the logged-in user has a student profile.
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect("student_dashboard")

    # All courses in the student's assigned curriculum.
    curriculum_courses = list(CurriculumCourse.objects.select_related(
        "course",
        "curriculum"
    ).filter(
        curriculum=student.curriculum
    ).annotate(
        pos_term_order=Case(
            When(term="first_sem", then=1),
            When(term="second_sem", then=2),
            When(term="midterm", then=3),
            output_field=IntegerField()
        )
    ).order_by(
        "year_level",
        "pos_term_order",
        "display_order"
    ))
    # Pre-load existing records into a dict keyed by course_id for O(1) lookup.
    existing_records = StudentCourseRecord.objects.filter(
        student=student,
    ).select_related("course").order_by("course_id", "-created_at")

    record_map = {}
    passed_course_ids = set()
    for record in existing_records:
        if record.course_id not in record_map:
            record_map[record.course_id] = record

        if (
            record.status == StudentCourseRecord.RecordStatus.PASSED
            and record.is_credit_earned
        ):
            passed_course_ids.add(record.course_id)

    for curriculum_course in curriculum_courses:
        record = record_map.get(curriculum_course.course_id)
        curriculum_course.input_record = record
        curriculum_course.input_is_locked = curriculum_course.course_id in passed_course_ids
        curriculum_course.input_is_failed = bool(
            record
            and record.status == StudentCourseRecord.RecordStatus.FAILED
        )

    base_context = {
        "student": student,
        "curriculum_courses": curriculum_courses,
        "record_map": record_map,
        "passed_course_ids": passed_course_ids,
    }

    if request.method == "POST":
        school_year = request.POST.get("school_year", "").strip()
        if not school_year:
            messages.error(request, "School year is required.")
            return render(request, "academics/input_grades.html", {
                **base_context,
                "post_data": request.POST,
            })

        if not re.match(r"^\d{4}-\d{4}$", school_year):
            messages.error(
                request,
                "School year must follow the format YYYY-YYYY (e.g. 2024-2025).",
            )
            return render(request, "academics/input_grades.html", {
                **base_context,
                "post_data": request.POST,
            })

        locked_submissions = [
            curriculum_course.course.course_code
            for curriculum_course in curriculum_courses
            if (
                curriculum_course.course_id in passed_course_ids
                and request.POST.get(
                    f"grade_{curriculum_course.course_id}",
                    "",
                ).strip()
            )
        ]
        if locked_submissions:
            messages.error(
                request,
                "Passed courses cannot be re-input: "
                + ", ".join(locked_submissions),
            )
            return render(request, "academics/input_grades.html", {
                **base_context,
                "post_data": request.POST,
            })

        try:
            with transaction.atomic():
                for curriculum_course in curriculum_courses:
                    course = curriculum_course.course
                    grade_raw = request.POST.get(f"grade_{course.id}", "").strip()
                    remarks = request.POST.get(f"remarks_{course.id}", "").strip()

                    # Skip courses where no grade was entered.
                    if grade_raw == "":
                        continue

                    if course.id in passed_course_ids:
                        messages.error(
                            request,
                            f"{course.course_code} already has a passing grade and cannot be re-input.",
                        )
                        return render(request, "academics/input_grades.html", {
                            **base_context,
                            "post_data": request.POST,
                        })

                    try:
                        grade_value = Decimal(grade_raw)
                    except InvalidOperation:
                        messages.error(
                            request,
                            f"Invalid grade for {course.course_code}.",
                        )
                        return render(request, "academics/input_grades.html", {
                            **base_context,
                            "post_data": request.POST,
                        })

                    # Range check: 1.00 – 5.00.
                    if grade_value < Decimal("1.00") or grade_value > Decimal("5.00"):
                        messages.error(
                            request,
                            f"Grade for {course.course_code} must be between 1.00 and 5.00.",
                        )
                        return render(request, "academics/input_grades.html", {
                            **base_context,
                            "post_data": request.POST,
                        })

                    if grade_value not in VALID_GRADES:
                        messages.error(
                            request,
                            f"Grade for {course.course_code} must be in 0.25 increments "
                            f"(e.g. 1.00, 1.25, 1.50).",
                        )
                        return render(request, "academics/input_grades.html", {
                            **base_context,
                            "post_data": request.POST,
                        })

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
                **base_context,
                "post_data": request.POST,
            })

        messages.success(request, "Grades saved successfully.")
        return redirect("my_course_records")

    # GET: render the blank/pre-filled grade input form.
    return render(request, "academics/input_grades.html", base_context)


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

@student_required
def academic_progress(request):
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect("student_dashboard")

    progress_data = get_student_academic_progress(student)

    return render(request, "academics/academic_progress.html", {
        "student": student,
        "progress": progress_data,
    })

@admin_required
def curriculum_upload(request):
    if request.method == "POST":
        form = CurriculumUploadForm(request.POST, request.FILES)

        if form.is_valid():
            curriculum = form.cleaned_data["curriculum"]
            uploaded_file = form.cleaned_data["file"]

            try:
                df = read_curriculum_file(uploaded_file)
                preview_rows, errors = validate_curriculum_rows(df)

                request.session["curriculum_upload_preview"] = preview_rows
                request.session["curriculum_upload_curriculum_id"] = curriculum.id

                return render(request, "academics/curriculum_upload_preview.html", {
                    "curriculum": curriculum,
                    "preview_rows": preview_rows,
                    "errors": errors,
                    "has_errors": bool(errors),
                })

            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
                return redirect("curriculum_upload")

    else:
        form = CurriculumUploadForm()

    return render(request, "academics/curriculum_upload.html", {
        "form": form
    })

@admin_required
def curriculum_upload_confirm(request):
    if request.method != "POST":
        return redirect("curriculum_upload")

    curriculum_id = request.session.get("curriculum_upload_curriculum_id")
    session_preview_rows = request.session.get("curriculum_upload_preview")

    try:
        row_count = int(request.POST.get("row_count", 0))
    except ValueError:
        messages.error(request, "Invalid upload preview data.")
        return redirect("curriculum_upload")

    if not curriculum_id or not session_preview_rows:
        messages.error(request, "No curriculum upload preview found.")
        return redirect("curriculum_upload")

    if row_count != len(session_preview_rows):
        messages.error(request, "Upload preview data does not match the active session.")
        return redirect("curriculum_upload")

    curriculum = Curriculum.objects.filter(id=curriculum_id).first()

    if not curriculum:
        messages.error(request, "Selected curriculum was not found.")
        return redirect("curriculum_upload")

    edited_rows = []

    for index in range(row_count):
        edited_rows.append({
            "row_number": request.POST.get(f"row_number_{index}", index + 1),
            "course_code": request.POST.get(f"course_code_{index}", ""),
            "course_title": request.POST.get(f"course_title_{index}", ""),
            "units": request.POST.get(f"units_{index}", ""),
            "year_level": request.POST.get(f"year_level_{index}", ""),
            "term": request.POST.get(f"term_{index}", ""),
            "display_order": request.POST.get(f"display_order_{index}", ""),
            "is_required": request.POST.get(f"is_required_{index}", ""),
            "prerequisites": request.POST.get(f"prerequisites_{index}", ""),
            "corequisites": request.POST.get(f"corequisites_{index}", ""),
            "standing_requirement": request.POST.get(f"standing_requirement_{index}", ""),
            "is_elective": request.POST.get(f"is_elective_{index}", ""),
        })

    preview_rows, errors = validate_preview_rows(edited_rows)

    if errors:
        messages.error(request, "Some edited rows still have errors. Please fix them before saving.")

        return render(request, "academics/curriculum_upload_preview.html", {
            "curriculum": curriculum,
            "preview_rows": preview_rows,
            "errors": errors,
            "has_errors": True,
        })

    result = save_curriculum_rows(curriculum, preview_rows)

    request.session.pop("curriculum_upload_preview", None)
    request.session.pop("curriculum_upload_curriculum_id", None)

    messages.success(
        request,
        (
            "Curriculum upload saved successfully. "
            f"Created courses: {result['created_courses']}. "
            f"Updated courses: {result['updated_courses']}. "
            f"Curriculum courses added: {result['created_curriculum_courses']}. "
            f"Requirements added: {result['created_requirements']}."
        )
    )

    if result["missing_requirement_courses"]:
        messages.warning(
            request,
            "Some requirements were skipped because required courses were missing."
        )

    return redirect("curriculum_course_list")

@student_required
def grade_upload(request):
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect("student_dashboard")

    if request.method == "POST":
        form = GradeUploadForm(request.POST, request.FILES)

        if form.is_valid():
            school_year = form.cleaned_data["school_year"]
            uploaded_file = form.cleaned_data["file"]

            try:
                extracted_text = extract_text_from_grade_file(uploaded_file)
                preview_rows, errors = parse_grade_rows_from_text(extracted_text, student)

                request.session["grade_upload_preview"] = preview_rows
                request.session["grade_upload_school_year"] = school_year

                return render(request, "academics/grade_upload_preview.html", {
                    "student": student,
                    "school_year": school_year,
                    "preview_rows": preview_rows,
                    "errors": errors,
                    "has_errors": bool(errors),
                })

            except ValidationError as error:
                messages.error(request, error.message)
                return redirect("grade_upload")

    else:
        form = GradeUploadForm()

    return render(request, "academics/grade_upload.html", {
        "form": form,
        "student": student,
    })

@student_required
def grade_upload_confirm(request):
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return redirect("student_dashboard")

    if request.method != "POST":
        return redirect("grade_upload")

    school_year = request.session.get("grade_upload_school_year")
    row_count = int(request.POST.get("row_count", 0))

    if not school_year:
        messages.error(request, "No grade upload preview found.")
        return redirect("grade_upload")

    edited_rows = []

    for index in range(row_count):
        edited_rows.append({
            "line_number": request.POST.get(f"line_number_{index}", index + 1),
            "course_code": request.POST.get(f"course_code_{index}", ""),
            "grade_value": request.POST.get(f"grade_value_{index}", ""),
            "remarks": request.POST.get(f"remarks_{index}", ""),
        })

    preview_rows, errors = validate_grade_preview_rows(edited_rows, student)

    if errors:
        messages.error(request, "Some rows still have errors. Please fix them before saving.")

        return render(request, "academics/grade_upload_preview.html", {
            "student": student,
            "school_year": school_year,
            "preview_rows": preview_rows,
            "errors": errors,
            "has_errors": True,
        })

    result = save_grade_rows(student, school_year, preview_rows)

    request.session.pop("grade_upload_preview", None)
    request.session.pop("grade_upload_school_year", None)

    messages.success(
        request,
        (
            "Grade upload saved successfully. "
            f"New records: {result['saved_count']}. "
            f"Updated records: {result['updated_count']}."
        )
    )

    return redirect("my_course_records")

@admin_required
def student_import(request):
    if request.method == "POST":
        form = StudentImportForm(request.POST, request.FILES)

        if form.is_valid():
            uploaded_file = form.cleaned_data["file"]

            try:
                df = read_student_import_file(uploaded_file)
                preview_rows, errors = validate_student_import_rows(df)

                request.session["student_import_preview"] = preview_rows

                return render(request, "academics/student_import_preview.html", {
                    "preview_rows": preview_rows,
                    "errors": errors,
                    "has_errors": bool(errors),
                })

            except ValidationError as error:
                messages.error(request, error.message)
                return redirect("student_import")

    else:
        form = StudentImportForm()

    return render(request, "academics/student_import.html", {
        "form": form
    })

@admin_required
def student_import_confirm(request):
    if request.method != "POST":
        return redirect("student_import")

    row_count = int(request.POST.get("row_count", 0))

    edited_rows = []

    for index in range(row_count):
        edited_rows.append({
            "row_number": request.POST.get(f"row_number_{index}", index + 1),
            "sr_code": request.POST.get(f"sr_code_{index}", ""),
            "first_name": request.POST.get(f"first_name_{index}", ""),
            "last_name": request.POST.get(f"last_name_{index}", ""),
            "email": request.POST.get(f"email_{index}", ""),
            "curriculum_code": request.POST.get(f"curriculum_code_{index}", ""),
            "section_code": request.POST.get(f"section_code_{index}", ""),
            "status": request.POST.get(f"status_{index}", ""),
        })

    preview_rows, errors = validate_student_preview_rows(edited_rows)

    if errors:
        messages.error(request, "Some rows still have errors. Please fix them before saving.")

        return render(request, "academics/student_import_preview.html", {
            "preview_rows": preview_rows,
            "errors": errors,
            "has_errors": True,
        })

    result = save_student_import_rows(preview_rows)

    request.session.pop("student_import_preview", None)

    messages.success(
        request,
        (
            "Student import saved successfully. "
            f"User accounts created: {result['created_users']}. "
            f"Student profiles created: {result['created_students']}."
        )
    )

    return redirect("student_list")
