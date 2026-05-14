from django.template.loader import render_to_string
from django.http import HttpResponse

from academics.models import CourseRequirement, StudentCourseRecord


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
    items = pos_plan.items.select_related("course").all().order_by(
        "planned_year_level",
        "planned_term",
        "display_order"
    )

    grouped_items = {}

    for item in items:
        key = (item.planned_year_level, item.planned_term)

        if key not in grouped_items:
            grouped_items[key] = []

        grouped_items[key].append({
            "course_code": item.course.course_code,
            "course_title": item.course.course_title,
            "units": item.course.units,
            "requirement_text": get_course_requirement_text(item.course),
            "grade": get_student_grade_for_course(student, item.course),
            "notes": item.notes,
        })

    return {
        "student": student,
        "pos_plan": pos_plan,
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
