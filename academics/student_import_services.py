import pandas as pd

from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.models import User
from .models import Student, Curriculum


REQUIRED_STUDENT_COLUMNS = [
    "sr_code",
    "first_name",
    "last_name",
    "email",
    "curriculum_code",
    "section_code",
    "status",
]

VALID_STUDENT_STATUS = ["regular", "irregular"]


def clean_text(value):
    if pd.isna(value):
        return ""

    return str(value).strip()


def read_student_import_file(uploaded_file):
    file_name = uploaded_file.name.lower()

    if file_name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)

    elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
        df = pd.read_excel(uploaded_file)

    else:
        raise ValidationError("Unsupported file type. Please upload CSV or Excel file.")

    df.columns = [str(column).strip().lower() for column in df.columns]

    missing_columns = [
        column for column in REQUIRED_STUDENT_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValidationError(
            f"Missing required columns: {', '.join(missing_columns)}"
        )

    return df


def validate_section_code(section_code):
    if not section_code:
        return "Section code is required."

    if len(section_code) != 4:
        return "Section code must be exactly 4 digits."

    if not section_code.isdigit():
        return "Section code must contain digits only."

    if section_code[0] not in "1234567":
        return "First digit must be the year level."

    if section_code[1] not in "123":
        return "Second digit must be the term: 1, 2, or 3."

    if section_code[2] != "0":
        return "Third digit must be 0."

    if section_code[3] == "0":
        return "Fourth digit must be the section number, starting from 1."

    return None


def generate_temporary_password(sr_code, last_name):
    cleaned_last_name = last_name.lower().replace(" ", "")
    return f"{sr_code}{cleaned_last_name}"


def validate_student_import_rows(df):
    preview_rows = []
    errors = []

    seen_sr_codes = set()
    seen_emails = set()

    for index, row in df.iterrows():
        row_number = index + 2

        sr_code = clean_text(row["sr_code"])
        first_name = clean_text(row["first_name"])
        last_name = clean_text(row["last_name"])
        email = clean_text(row["email"]).lower()
        curriculum_code = clean_text(row["curriculum_code"])
        section_code = clean_text(row["section_code"])
        status = clean_text(row["status"]).lower()

        row_errors = []

        if not sr_code:
            row_errors.append("SR-Code is required.")

        if not first_name:
            row_errors.append("First name is required.")

        if not last_name:
            row_errors.append("Last name is required.")

        if not email:
            row_errors.append("Email is required.")

        if not curriculum_code:
            row_errors.append("Curriculum code is required.")

        if status not in VALID_STUDENT_STATUS:
            row_errors.append("Status must be regular or irregular.")

        section_error = validate_section_code(section_code)
        if section_error:
            row_errors.append(section_error)

        if sr_code in seen_sr_codes:
            row_errors.append("Duplicate SR-Code inside uploaded file.")

        if email in seen_emails:
            row_errors.append("Duplicate email inside uploaded file.")

        seen_sr_codes.add(sr_code)
        seen_emails.add(email)

        if Student.objects.filter(sr_code=sr_code).exists():
            row_errors.append("SR-Code already exists in the system.")

        if User.objects.filter(email=email).exists():
            row_errors.append("Email already exists in the system.")

        curriculum = Curriculum.objects.filter(
            curriculum_code=curriculum_code
        ).first()

        if not curriculum:
            row_errors.append("Curriculum code does not exist.")

        temporary_password = generate_temporary_password(sr_code, last_name)

        preview_row = {
            "row_number": row_number,
            "sr_code": sr_code,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "curriculum_code": curriculum_code,
            "section_code": section_code,
            "status": status,
            "temporary_password": temporary_password,
            "errors": row_errors,
        }

        preview_rows.append(preview_row)

        if row_errors:
            errors.append({
                "row_number": row_number,
                "errors": row_errors,
            })

    return preview_rows, errors


def validate_student_preview_rows(preview_rows):
    validated_rows = []
    errors = []

    seen_sr_codes = set()
    seen_emails = set()

    for index, row in enumerate(preview_rows):
        row_number = row.get("row_number", index + 1)

        sr_code = str(row.get("sr_code", "")).strip()
        first_name = str(row.get("first_name", "")).strip()
        last_name = str(row.get("last_name", "")).strip()
        email = str(row.get("email", "")).strip().lower()
        curriculum_code = str(row.get("curriculum_code", "")).strip()
        section_code = str(row.get("section_code", "")).strip()
        status = str(row.get("status", "")).strip().lower()

        row_errors = []

        if not sr_code:
            row_errors.append("SR-Code is required.")

        if not first_name:
            row_errors.append("First name is required.")

        if not last_name:
            row_errors.append("Last name is required.")

        if not email:
            row_errors.append("Email is required.")

        if not curriculum_code:
            row_errors.append("Curriculum code is required.")

        if status not in VALID_STUDENT_STATUS:
            row_errors.append("Status must be regular or irregular.")

        section_error = validate_section_code(section_code)
        if section_error:
            row_errors.append(section_error)

        if sr_code in seen_sr_codes:
            row_errors.append("Duplicate SR-Code inside preview rows.")

        if email in seen_emails:
            row_errors.append("Duplicate email inside preview rows.")

        seen_sr_codes.add(sr_code)
        seen_emails.add(email)

        if Student.objects.filter(sr_code=sr_code).exists():
            row_errors.append("SR-Code already exists in the system.")

        if User.objects.filter(email=email).exists():
            row_errors.append("Email already exists in the system.")

        curriculum = Curriculum.objects.filter(
            curriculum_code=curriculum_code
        ).first()

        if not curriculum:
            row_errors.append("Curriculum code does not exist.")

        temporary_password = generate_temporary_password(sr_code, last_name)

        validated_row = {
            "row_number": row_number,
            "sr_code": sr_code,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "curriculum_code": curriculum_code,
            "section_code": section_code,
            "status": status,
            "temporary_password": temporary_password,
            "errors": row_errors,
        }

        validated_rows.append(validated_row)

        if row_errors:
            errors.append({
                "row_number": row_number,
                "errors": row_errors,
            })

    return validated_rows, errors


@transaction.atomic
def save_student_import_rows(preview_rows):
    created_users = 0
    created_students = 0

    for row in preview_rows:
        curriculum = Curriculum.objects.get(
            curriculum_code=row["curriculum_code"]
        )

        temporary_password = generate_temporary_password(
            row["sr_code"],
            row["last_name"]
        )

        student_user = User.objects.create_user(
            email=row["email"],
            password=temporary_password,
            first_name=row["first_name"],
            last_name=row["last_name"],
            role=User.Role.STUDENT,
            must_change_password=True,
            is_active=True
        )

        created_users += 1

        Student.objects.create(
            user=student_user,
            sr_code=row["sr_code"],
            curriculum=curriculum,
            year_level=int(row["section_code"][0]),
            current_semester=int(row["section_code"][1]),
            section_code=row["section_code"],
            status=row["status"]
        )

        created_students += 1

    return {
        "created_users": created_users,
        "created_students": created_students,
    }