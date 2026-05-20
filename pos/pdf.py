from django.template.loader import render_to_string
from django.http import HttpResponse
from collections import OrderedDict

from academics.models import CourseRequirement, CurriculumCourse, StudentCourseRecord
from .services import build_complete_pos_display_items


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
    """
    Build PDF context with auto-arranged courses using the same logic
    as the display views. This applies intelligent rearrangement based on
    prerequisites, unit limits, and course completion status.
    """
    program = student.curriculum.program
    department = program.department

    # Use the auto-arrange display logic for PDF generation
    grouped_items = build_complete_pos_display_items(student, pos_plan)

    # Convert display items to PDF format with requirement text
    pdf_grouped_items = OrderedDict()
    
    for key, courses in grouped_items.items():
        pdf_grouped_items[key] = []
        for course_item in courses:
            course = course_item["course"]
            
            # Get requirement text for the course
            requirements = CourseRequirement.objects.select_related(
                "required_course"
            ).filter(
                course=course
            )
            
            requirement_texts = []
            for requirement in requirements:
                label = "Pre" if requirement.requirement_type == "prerequisite" else "Co"
                requirement_texts.append(
                    f"{label}: {requirement.required_course.course_code}"
                )
            
            pdf_grouped_items[key].append({
                "course_code": course_item["course_code"],
                "course_title": course_item["course_title"],
                "units": course_item["units"],
                "requirement_text": " / ".join(requirement_texts),
                "grade": course_item["grade"],
                "notes": course_item["notes"],
                "is_rearranged": course_item["source"] == "rearranged",
            })

    return {
        "student": student,
        "student_display_name": f"{student.user.first_name} {student.user.last_name}",
        "pos_plan": pos_plan,
        "evaluation_program_title": get_evaluation_program_title(program.program_name),
        "department_name": department.department_name,
        "academic_year": student.curriculum.academic_year_label or "",
        "grouped_items": pdf_grouped_items,
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
