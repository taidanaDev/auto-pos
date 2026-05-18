import re
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Course, CurriculumCourse, StudentCourseRecord

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

VALID_GRADES = {Decimal("1.00") + Decimal("0.25") * i for i in range(17)}


def normalize_spaces(value):
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_course_code(value):
    value = normalize_spaces(value).upper()
    match = re.search(r"\b([A-Z]{2,5})\s*([0-9]{3})\b", value)

    if not match:
        return value

    return f"{match.group(1)} {match.group(2)}"


def parse_grade_value(value):
    value = normalize_spaces(value)
    if not value:
        return None, "Grade is required."

    try:
        grade = Decimal(value)
    except InvalidOperation:
        return None, "Grade must be a number."

    grade = grade.quantize(Decimal("0.01"))

    if grade < Decimal("1.00") or grade > Decimal("5.00"):
        return None, "Grade must be between 1.00 and 5.00."

    if grade not in VALID_GRADES:
        return None, "Grade must be in 0.25 increments."

    return grade, None


def get_curriculum_course_map(student):
    return {
        normalize_course_code(course_code): course_code
        for course_code in CurriculumCourse.objects.filter(
            curriculum=student.curriculum
        ).values_list("course__course_code", flat=True)
    }


def extract_text_from_grade_file(uploaded_file):
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".pdf"):
        return extract_text_from_pdf(uploaded_file)

    if file_name.endswith((".jpg", ".jpeg", ".png")):
        return extract_text_from_image(uploaded_file)

    raise ValidationError("Unsupported file type. Please upload PDF, JPG, JPEG, or PNG.")


def extract_text_from_pdf(uploaded_file):
    if pdfplumber is None:
        raise ValidationError("PDF extraction is unavailable because pdfplumber is not installed.")

    extracted_text = ""

    try:
        uploaded_file.seek(0)
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                extracted_text += page_text + "\n"
    except Exception as exc:
        raise ValidationError("The PDF file could not be read. Please upload a valid text-based PDF.") from exc

    if not extracted_text.strip():
        raise ValidationError("No readable text found in the PDF. It may be scanned or image-based.")

    return extracted_text


def extract_text_from_image(uploaded_file):
    if Image is None or ImageOps is None:
        raise ValidationError("Image extraction is unavailable because Pillow is not installed.")

    if pytesseract is None:
        raise ValidationError("OCR is unavailable because pytesseract is not installed.")

    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image.verify()

        uploaded_file.seek(0)
        with Image.open(uploaded_file) as image:
            image = ImageOps.exif_transpose(image).convert("L")
            text = pytesseract.image_to_string(image)
    except ValidationError:
        raise
    except pytesseract.TesseractNotFoundError as exc:
        raise ValidationError("OCR failed because the Tesseract executable is not installed or configured.") from exc
    except Exception as exc:
        raise ValidationError("OCR failed. Please upload a readable JPG, JPEG, or PNG grade file.") from exc

    if not text.strip():
        raise ValidationError("No readable text found in the image.")

    return text


def parse_grade_rows_from_text(text, student):
    """
    Best-effort parser:
    Looks for course codes and grade values near them.

    Example accepted patterns:
    MATH 401 Differential Calculus 2.50
    CpE 404 Programming Logic and Design 5.00
    """

    curriculum_course_map = get_curriculum_course_map(student)
    curriculum_course_codes = set(curriculum_course_map.values())

    lines = text.splitlines()
    preview_rows = []

    grade_pattern = r"\b([1-5]\.\d{1,2})\b"
    course_code_pattern = r"\b[A-Za-z]{2,5}\s?\d{3}\b"

    for line_number, line in enumerate(lines, start=1):
        clean_line = normalize_spaces(line)

        if not clean_line:
            continue

        course_match = re.search(course_code_pattern, clean_line)

        if not course_match:
            continue

        course_code = normalize_course_code(course_match.group(0))
        matched_course_code = curriculum_course_map.get(course_code)

        if not matched_course_code:
            continue

        grade_matches = re.findall(grade_pattern, clean_line)

        grade_value = ""

        if grade_matches:
            possible_grades = [
                grade for grade in grade_matches
                if parse_grade_value(grade)[1] is None
            ]

            if possible_grades:
                grade_value = possible_grades[-1]

        course = Course.objects.filter(course_code=matched_course_code).first()

        preview_rows.append({
            "line_number": line_number,
            "course_code": matched_course_code,
            "course_title": course.course_title if course else "",
            "grade_value": grade_value,
            "remarks": "Extracted from uploaded grade file",
            "errors": [],
        })

    if not preview_rows:
        raise ValidationError("No matching course grades were extracted from the uploaded file.")

    return validate_grade_preview_rows(preview_rows, student)


def validate_grade_preview_rows(preview_rows, student):
    validated_rows = []
    errors = []

    valid_course_map = get_curriculum_course_map(student)
    valid_course_codes = set(valid_course_map.values())

    for index, row in enumerate(preview_rows):
        line_number = row.get("line_number", index + 1)
        course_code = normalize_course_code(row.get("course_code", ""))
        course_code = valid_course_map.get(course_code, course_code)
        grade_value = normalize_spaces(row.get("grade_value", ""))
        remarks = normalize_spaces(row.get("remarks", ""))[:100]

        row_errors = []

        if not course_code:
            row_errors.append("Course code is required.")

        if course_code not in valid_course_codes:
            row_errors.append("Course code is not part of your curriculum.")

        grade_decimal, grade_error = parse_grade_value(grade_value)
        if grade_error:
            row_errors.append(grade_error)

        course = Course.objects.filter(course_code=course_code).first()

        validated_row = {
            "line_number": line_number,
            "course_code": course_code,
            "course_title": course.course_title if course else "",
            "grade_value": f"{grade_decimal:.2f}" if grade_decimal is not None else grade_value,
            "remarks": remarks,
            "errors": row_errors,
        }

        validated_rows.append(validated_row)

        if row_errors:
            errors.append({
                "line_number": line_number,
                "errors": row_errors,
            })

    return validated_rows, errors


@transaction.atomic
def save_grade_rows(student, school_year, preview_rows):
    saved_count = 0
    updated_count = 0

    for row in preview_rows:
        course = Course.objects.filter(
            course_code=row["course_code"]
        ).first()

        if not course:
            continue

        curriculum_course = CurriculumCourse.objects.filter(
            curriculum=student.curriculum,
            course=course
        ).first()

        if not curriculum_course:
            continue

        grade_decimal, grade_error = parse_grade_value(row["grade_value"])
        if grade_error:
            continue

        _, created = StudentCourseRecord.objects.update_or_create(
            student=student,
            course=course,
            school_year=school_year,
            term=curriculum_course.term,
            defaults={
                "grade_value": grade_decimal,
                "remarks": row["remarks"][:100],
                "status": "",
            }
        )

        if created:
            saved_count += 1
        else:
            updated_count += 1

    return {
        "saved_count": saved_count,
        "updated_count": updated_count,
    }
