from django.template.loader import render_to_string
from django.http import HttpResponse

from academics.models import CourseRequirement, CurriculumCourse, StudentCourseRecord


PROGRAM_TITLE_PREFIXES = (
    "Bachelor of Science in ",
)


def get_evaluation_program_title(program_name):
    for prefix in PROGRAM_TITLE_PREFIXES:
        if program_name.lower().startswith(prefix.lower()):
            return program_name[len(prefix):].strip()

    return program_name


def get_course_requirement_text(course):
    requirements = CourseRequirement.objects.select_related(
        "required_course"
    ).filter(
        course=course
    )

    if not requirements.exists():
        return ""

    requirement_texts = []

    for requirement in requirements:
        label = "Pre" if requirement.requirement_type == "prerequisite" else "Co"
        requirement_texts.append(
            f"{label}: {requirement.required_course.course_code}"
        )

    return " / ".join(requirement_texts)


def get_student_grade_for_course(student, course):
    record = StudentCourseRecord.objects.filter(
        student=student,
        course=course
    ).order_by("-created_at").first()

    if not record:
        return ""

    if record.grade_value is None:
        return ""

    return record.grade_value


def build_pos_pdf_context(student, pos_plan):
    program = student.curriculum.program
    department = program.department

    curriculum_courses = list(
        CurriculumCourse.objects.select_related("course").filter(
            curriculum=student.curriculum,
        ).ordered_by_pos_sequence()
    )

    course_ids = [item.course_id for item in curriculum_courses]

    latest_records = {}
    records = StudentCourseRecord.objects.filter(
        student=student,
        course_id__in=course_ids,
    ).order_by("course_id", "-created_at")

    for record in records:
        if record.course_id not in latest_records:
            latest_records[record.course_id] = record

    requirements = CourseRequirement.objects.select_related(
        "required_course"
    ).filter(
        course_id__in=course_ids
    )

    requirement_map = {}
    for requirement in requirements:
        label = "Pre" if requirement.requirement_type == "prerequisite" else "Co"
        requirement_map.setdefault(requirement.course_id, []).append(
            f"{label}: {requirement.required_course.course_code}"
        )

    grouped_items = {}

    for curriculum_course in curriculum_courses:
        course = curriculum_course.course
        key = (curriculum_course.year_level, curriculum_course.term)

        if key not in grouped_items:
            grouped_items[key] = []

        record = latest_records.get(course.id)

        grouped_items[key].append({
            "course_code": course.course_code,
            "course_title": course.course_title,
            "units": course.units,
            "requirement_text": " / ".join(requirement_map.get(course.id, [])),
            "grade": record.grade_value if record and record.grade_value is not None else "",
            "notes": "",
        })

    return {
        "student": student,
        "pos_plan": pos_plan,
        "evaluation_program_title": get_evaluation_program_title(program.program_name),
        "department_name": department.department_name,
        "academic_year": student.curriculum.academic_year_label or "",
        "grouped_items": grouped_items,
    }


def generate_pos_pdf_response(request, student, pos_plan):
    context = build_pos_pdf_context(student, pos_plan)

    html_string = render_to_string(
        "pos/pdf/pos_pdf_template.html",
        context,
        request=request
    )

    try:
        from weasyprint import HTML
    except OSError as exc:
        raise RuntimeError(
            "WeasyPrint cannot load its required GTK/Pango libraries. "
            "Install the Windows GTK runtime or run PDF generation in an "
            "environment with WeasyPrint native dependencies available."
        ) from exc

    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    filename = f"POS_{student.sr_code}.pdf"

    response = HttpResponse(pdf_file, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    return response
