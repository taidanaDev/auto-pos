import re
import pandas as pd

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Course, CurriculumCourse, CourseRequirement

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from docx import Document
except ImportError:
    Document = None


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
TERM_ALIASES = {
    "first_sem": "first_sem",
    "first sem": "first_sem",
    "first semester": "first_sem",
    "1st sem": "first_sem",
    "1st semester": "first_sem",
    "second_sem": "second_sem",
    "second sem": "second_sem",
    "second semester": "second_sem",
    "2nd sem": "second_sem",
    "2nd semester": "second_sem",
    "midterm": "midterm",
    "mid term": "midterm",
    "summer": "midterm",
}
YEAR_ALIASES = {
    "first": 1,
    "1st": 1,
    "second": 2,
    "2nd": 2,
    "third": 3,
    "3rd": 3,
    "fourth": 4,
    "4th": 4,
    "fifth": 5,
    "5th": 5,
}


def parse_boolean(value):
    if pd.isna(value):
        return False, None

    value = str(value).strip().lower()

    if value in ["true", "1", "yes", "y", "required"]:
        return True, None

    if value in ["false", "0", "no", "n", "", "not required"]:
        return False, None

    return False, "Must be true/false, yes/no, or 1/0."


def clean_text(value):
    if pd.isna(value):
        return ""

    return str(value).strip()

def normalize_spaces(value):
    if value is None:
        return ""

    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_column_name(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


def normalize_course_code(value):
    value = normalize_spaces(value).upper()
    match = re.search(r"\b([A-Z]{2,5})\s*([0-9]{3})\b", value)

    if not match:
        return value

    return f"{match.group(1)} {match.group(2)}"


def parse_positive_int(value):
    if pd.isna(value):
        return None

    value = clean_text(value)
    if not value:
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not number.is_integer():
        return None

    return int(number)


def normalize_term(value):
    value = clean_text(value).lower().replace("-", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return TERM_ALIASES.get(value, value)


def infer_year_level(text):
    text = normalize_spaces(text).lower()

    for alias, year_level in YEAR_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\s+year\b", text):
            return year_level

    match = re.search(r"\b([1-9])(?:st|nd|rd|th)?\s+year\b", text)
    if match:
        return int(match.group(1))

    return None


def infer_term(text):
    normalized = normalize_spaces(text).lower().replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()

    for alias, term in TERM_ALIASES.items():
        if alias in normalized:
            return term

    return ""


def extract_course_code_from_text(text):
    """
    Finds course codes like:
    MATH 401
    CpE 404
    ENGG 401
    GEd 101
    SCI 403
    """
    pattern = r"\b[A-Za-z]{2,5}\s?\d{3}\b"
    match = re.search(pattern, text)

    if match:
        return normalize_course_code(match.group(0))

    return ""
def read_curriculum_file(uploaded_file):
    file_name = uploaded_file.name.lower()

    try:
        if file_name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)

        elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
            df = pd.read_excel(uploaded_file)

        elif file_name.endswith(".docx"):
            df = extract_rows_from_docx(uploaded_file)

        elif file_name.endswith(".pdf"):
            df = extract_rows_from_pdf(uploaded_file)

        else:
            raise ValidationError(
                "Unsupported file type. Please upload CSV, Excel, DOCX, or text-based PDF file."
            )
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(
            "The uploaded curriculum file could not be read. Please check the file format and try again."
        ) from exc

    df.columns = [normalize_column_name(column) for column in df.columns]

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

        course_code = normalize_course_code(row["course_code"])
        course_title = clean_text(row["course_title"])
        term = normalize_term(row["term"])

        units = parse_positive_int(row["units"])
        year_level = parse_positive_int(row["year_level"])
        display_order = parse_positive_int(row["display_order"])
        is_required, is_required_error = parse_boolean(row["is_required"])
        is_elective, is_elective_error = parse_boolean(row["is_elective"])
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

        if is_required_error:
            row_errors.append(f"Is required: {is_required_error}")

        if is_elective_error:
            row_errors.append(f"Is elective: {is_elective_error}")

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

def validate_preview_rows(preview_rows):
    """
    Validates edited preview rows before saving.
    This is used after the admin edits the preview table.
    """

    validated_rows = []
    errors = []

    for index, row in enumerate(preview_rows):
        row_number = row.get("row_number", index + 1)

        course_code = normalize_course_code(row.get("course_code"))
        course_title = clean_text(row.get("course_title"))
        term = normalize_term(row.get("term"))

        units = parse_positive_int(row.get("units"))
        year_level = parse_positive_int(row.get("year_level"))
        display_order = parse_positive_int(row.get("display_order"))
        is_required, is_required_error = parse_boolean(row.get("is_required"))
        is_elective, is_elective_error = parse_boolean(row.get("is_elective"))
        prerequisites = clean_text(row.get("prerequisites"))
        corequisites = clean_text(row.get("corequisites"))
        standing_requirement = clean_text(row.get("standing_requirement"))

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

        if is_required_error:
            row_errors.append(f"Is required: {is_required_error}")

        if is_elective_error:
            row_errors.append(f"Is elective: {is_elective_error}")

        cleaned_row = {
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
        }

        validated_rows.append(cleaned_row)

        if row_errors:
            errors.append({
                "row_number": row_number,
                "errors": row_errors,
            })

    return validated_rows, errors

def split_requirement_codes(value):
    if not value:
        return []

    return [
        normalize_course_code(item)
        for item in re.split(r"[;,\n]+", value)
        if normalize_course_code(item)
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

    CourseRequirement.objects.filter(
        course__in=course_map.values(),
        requirement_type__in=[
            CourseRequirement.RequirementType.PREREQUISITE,
            CourseRequirement.RequirementType.COREQUISITE,
        ],
    ).delete()

    for row in preview_rows:
        course = course_map.get(row["course_code"])

        prerequisite_codes = split_requirement_codes(row["prerequisites"])
        corequisite_codes = split_requirement_codes(row["corequisites"])

        for prerequisite_code in prerequisite_codes:
            if prerequisite_code == row["course_code"]:
                missing_requirement_courses.append(
                    f"{row['course_code']} prerequisite skipped: course cannot require itself"
                )
                continue

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
            if corequisite_code == row["course_code"]:
                missing_requirement_courses.append(
                    f"{row['course_code']} corequisite skipped: course cannot require itself"
                )
                continue

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

def extract_rows_from_docx(uploaded_file):
    """
    Extracts curriculum-like rows from DOCX tables.

    Expected table columns may include:
    Course Code, Course Title, Units, Year Level, Term, etc.

    This is best-effort extraction. Admin can edit rows in preview.
    """

    if Document is None:
        raise ValidationError("DOCX extraction is unavailable because python-docx is not installed.")

    try:
        document = Document(uploaded_file)
    except Exception as exc:
        raise ValidationError("The DOCX file could not be read. Please upload a valid DOCX file.") from exc

    extracted_rows = []
    current_year_level = None
    current_term = ""

    for table in document.tables:
        for row in table.rows:
            cells = [
                normalize_spaces(cell.text)
                for cell in row.cells
            ]

            if not cells or len(cells) < 3:
                continue

            row_text = " ".join(cells)
            inferred_year_level = infer_year_level(row_text)
            inferred_term = infer_term(row_text)

            if inferred_year_level:
                current_year_level = inferred_year_level

            if inferred_term:
                current_term = inferred_term

            course_code = extract_course_code_from_text(row_text)

            if not course_code:
                continue

            # Best-effort assumptions:
            # cell 0 = course code
            # cell 1 = course title
            # one of the later cells = units
            possible_units = None

            for cell in reversed(cells):
                parsed_units = parse_positive_int(cell)
                if parsed_units:
                    possible_units = parsed_units
                    break

            course_title = ""

            if len(cells) > 1:
                course_title = cells[1]

            if course_title == course_code or not course_title:
                course_title = row_text.replace(course_code, "").strip()

            extracted_rows.append({
                "course_code": course_code,
                "course_title": course_title,
                "units": possible_units,
                "year_level": current_year_level,
                "term": current_term,
                "display_order": len(extracted_rows) + 1,
                "is_required": True,
                "prerequisites": "",
                "corequisites": "",
                "standing_requirement": "",
                "is_elective": False,
            })

    if not extracted_rows:
        raise ValidationError("No curriculum table rows were extracted from the DOCX file.")

    return pd.DataFrame(extracted_rows)


def extract_pdf_text_rows(text, extracted_rows, current_year_level=None, current_term=""):
    for line in text.splitlines():
        line = normalize_spaces(line)
        if not line:
            continue

        inferred_year_level = infer_year_level(line)
        inferred_term = infer_term(line)

        if inferred_year_level:
            current_year_level = inferred_year_level

        if inferred_term:
            current_term = inferred_term

        course_code = extract_course_code_from_text(line)
        if not course_code:
            continue

        possible_units = None
        tokens = line.split()

        for token in reversed(tokens):
            parsed_units = parse_positive_int(token)
            if parsed_units:
                possible_units = parsed_units
                break

        title_text = line.replace(course_code, "", 1)
        if possible_units:
            title_text = re.sub(rf"\b{possible_units}\b\s*$", "", title_text).strip()

        extracted_rows.append({
            "course_code": course_code,
            "course_title": title_text,
            "units": possible_units,
            "year_level": current_year_level,
            "term": current_term,
            "display_order": len(extracted_rows) + 1,
            "is_required": True,
            "prerequisites": "",
            "corequisites": "",
            "standing_requirement": "",
            "is_elective": False,
        })

    return current_year_level, current_term

def extract_rows_from_pdf(uploaded_file):
    """
    Extracts curriculum-like rows from text-based PDF tables.
    This is best-effort extraction and works best on selectable-text PDFs.
    """

    extracted_rows = []
    selectable_text_found = False
    current_year_level = None
    current_term = ""

    if pdfplumber is None:
        raise ValidationError("PDF extraction is unavailable because pdfplumber is not installed.")

    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    selectable_text_found = True

                tables = page.extract_tables()

                for table in tables:
                    for row in table:
                        if not row:
                            continue

                        cells = [
                            normalize_spaces(cell)
                            for cell in row
                            if cell is not None
                        ]

                        if len(cells) < 3:
                            continue

                        row_text = " ".join(cells)
                        inferred_year_level = infer_year_level(row_text)
                        inferred_term = infer_term(row_text)

                        if inferred_year_level:
                            current_year_level = inferred_year_level

                        if inferred_term:
                            current_term = inferred_term

                        course_code = extract_course_code_from_text(row_text)

                        if not course_code:
                            continue

                        possible_units = None

                        for cell in reversed(cells):
                            parsed_units = parse_positive_int(cell)
                            if parsed_units:
                                possible_units = parsed_units
                                break

                        course_title = ""

                        if len(cells) > 1:
                            course_title = cells[1]

                        if course_title == course_code or not course_title:
                            course_title = row_text.replace(course_code, "").strip()

                        extracted_rows.append({
                            "course_code": course_code,
                            "course_title": course_title,
                            "units": possible_units,
                            "year_level": current_year_level,
                            "term": current_term,
                            "display_order": len(extracted_rows) + 1,
                            "is_required": True,
                            "prerequisites": "",
                            "corequisites": "",
                            "standing_requirement": "",
                            "is_elective": False,
                        })

                if not extracted_rows and page_text.strip():
                    current_year_level, current_term = extract_pdf_text_rows(
                        page_text,
                        extracted_rows,
                        current_year_level=current_year_level,
                        current_term=current_term,
                    )
    except Exception as exc:
        raise ValidationError("The PDF file could not be read. Please upload a valid text-based PDF file.") from exc

    if not extracted_rows:
        if not selectable_text_found:
            raise ValidationError(
                "No selectable text was found in the PDF. Scanned or image-based PDFs cannot be extracted."
            )

        raise ValidationError(
            "No curriculum rows were extracted from the text-based PDF. Please review the PDF format and try again."
        )

    return pd.DataFrame(extracted_rows)
