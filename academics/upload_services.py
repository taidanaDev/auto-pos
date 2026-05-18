import pandas as pd

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Course, CurriculumCourse, CourseRequirement


REQUIRED_COLUMNS = [
    "course_code",
    "course_title",
    "units",
    "year_level",
    "term",
    "display_order",
    "is_required",
    "prerequisites",
    "corequisites",
    "standing_requirement",
    "is_elective",
]


VALID_TERMS = ["first_sem", "second_sem", "midterm"]


def parse_boolean(value):
    if pd.isna(value):
        return False

    value = str(value).strip().lower()

    if value in ["true", "1", "yes", "y"]:
        return True

    if value in ["false", "0", "no", "n", ""]:
        return False

    return False


def clean_text(value):
    if pd.isna(value):
        return ""

    return str(value).strip()


def read_curriculum_file(uploaded_file):
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)

    elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
        df = pd.read_excel(uploaded_file)

    else:
        raise ValidationError("Unsupported file type. Please upload CSV or Excel file.")

    df.columns = [str(column).strip().lower() for column in df.columns]

    missing_columns = [
        column for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValidationError(
            f"Missing required columns: {', '.join(missing_columns)}"
        )

    return df


def validate_curriculum_rows(df):
    preview_rows = []
    errors = []

    for index, row in df.iterrows():
        row_number = index + 2

        course_code = clean_text(row["course_code"])
        course_title = clean_text(row["course_title"])
        term = clean_text(row["term"])

        try:
            units = int(row["units"])
        except Exception:
            units = None

        try:
            year_level = int(row["year_level"])
        except Exception:
            year_level = None

        try:
            display_order = int(row["display_order"])
        except Exception:
            display_order = None

        is_required = parse_boolean(row["is_required"])
        is_elective = parse_boolean(row["is_elective"])
        prerequisites = clean_text(row["prerequisites"])
        corequisites = clean_text(row["corequisites"])
        standing_requirement = clean_text(row["standing_requirement"])

        row_errors = []

        if not course_code:
            row_errors.append("Course code is required.")

        if not course_title:
            row_errors.append("Course title is required.")

        if units is None or units <= 0:
            row_errors.append("Units must be a positive number.")

        if year_level is None or year_level <= 0:
            row_errors.append("Year level must be a positive number.")

        if term not in VALID_TERMS:
            row_errors.append("Term must be first_sem, second_sem, or midterm.")

        if display_order is None or display_order <= 0:
            row_errors.append("Display order must be a positive number.")

        preview_rows.append({
            "row_number": row_number,
            "course_code": course_code,
            "course_title": course_title,
            "units": units,
            "year_level": year_level,
            "term": term,
            "display_order": display_order,
            "is_required": is_required,
            "prerequisites": prerequisites,
            "corequisites": corequisites,
            "standing_requirement": standing_requirement,
            "is_elective": is_elective,
            "errors": row_errors,
        })

        if row_errors:
            errors.append({
                "row_number": row_number,
                "errors": row_errors,
            })

    return preview_rows, errors


def split_requirement_codes(value):
    if not value:
        return []

    return [
        item.strip()
        for item in value.split(";")
        if item.strip()
    ]


@transaction.atomic
def save_curriculum_rows(curriculum, preview_rows):
    created_courses = 0
    updated_courses = 0
    created_curriculum_courses = 0
    created_requirements = 0
    missing_requirement_courses = []

    course_map = {}

    for row in preview_rows:
        course, created = Course.objects.update_or_create(
            course_code=row["course_code"],
            defaults={
                "course_title": row["course_title"],
                "units": row["units"],
                "is_elective": row["is_elective"],
            }
        )

        course_map[row["course_code"]] = course

        if created:
            created_courses += 1
        else:
            updated_courses += 1

        _, curriculum_course_created = CurriculumCourse.objects.update_or_create(
            curriculum=curriculum,
            course=course,
            defaults={
                "year_level": row["year_level"],
                "term": row["term"],
                "display_order": row["display_order"],
                "is_required": row["is_required"],
                "standing_requirement": row["standing_requirement"],
            }
        )

        if curriculum_course_created:
            created_curriculum_courses += 1

    for row in preview_rows:
        course = course_map.get(row["course_code"])

        prerequisite_codes = split_requirement_codes(row["prerequisites"])
        corequisite_codes = split_requirement_codes(row["corequisites"])

        for prerequisite_code in prerequisite_codes:
            required_course = Course.objects.filter(
                course_code=prerequisite_code
            ).first()

            if not required_course:
                missing_requirement_courses.append(
                    f"{row['course_code']} prerequisite missing: {prerequisite_code}"
                )
                continue

            _, created = CourseRequirement.objects.get_or_create(
                course=course,
                required_course=required_course,
                requirement_type=CourseRequirement.RequirementType.PREREQUISITE
            )

            if created:
                created_requirements += 1

        for corequisite_code in corequisite_codes:
            required_course = Course.objects.filter(
                course_code=corequisite_code
            ).first()

            if not required_course:
                missing_requirement_courses.append(
                    f"{row['course_code']} corequisite missing: {corequisite_code}"
                )
                continue

            _, created = CourseRequirement.objects.get_or_create(
                course=course,
                required_course=required_course,
                requirement_type=CourseRequirement.RequirementType.COREQUISITE
            )

            if created:
                created_requirements += 1

    return {
        "created_courses": created_courses,
        "updated_courses": updated_courses,
        "created_curriculum_courses": created_curriculum_courses,
        "created_requirements": created_requirements,
        "missing_requirement_courses": missing_requirement_courses,
    }