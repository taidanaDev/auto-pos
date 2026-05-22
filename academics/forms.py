from decimal import Decimal
import re

from django import forms
from django.core.exceptions import ValidationError

from accounts.models import User
from .models import (
    Curriculum,
    Student,
    Course,
    CurriculumCourse,
    CourseRequirement,
)

GSUITE_DOMAIN = "g.batstate-u.edu.ph"


class ManualStudentRegistrationForm(forms.Form):
    sr_code = forms.CharField(
        max_length=30,
        label="SR-Code",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Example: 23-00001"
        })
    )

    first_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter first name"
        })
    )

    last_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter last name"
        })
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Enter G-Suite email"
        })
    )

    curriculum = forms.ModelChoiceField(
        queryset=Curriculum.objects.none(),
        widget=forms.Select(attrs={
            "class": "form-select"
        })
    )

    section_code = forms.CharField(
        max_length=4,
        min_length=4,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Example: 3201"
        }),
        help_text="Format: [year][term][0][section], e.g. 3201 = 3rd year, 2nd semester, section 1."
    )

    status = forms.ChoiceField(
        choices=Student.Status.choices,
        widget=forms.Select(attrs={
            "class": "form-select"
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["curriculum"].queryset = Curriculum.objects.filter(is_active=True)

    def clean_sr_code(self):
        sr_code = self.cleaned_data["sr_code"]

        if not re.match(r"^\d{2}-\d{5}$", sr_code):
            raise ValidationError("SR-Code must follow the format YY-NNNNN, e.g. 23-00001.")

        if Student.objects.filter(sr_code=sr_code).exists():
            raise ValidationError("This SR-Code is already registered.")

        return sr_code

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        sr_code = self.cleaned_data.get("sr_code", "").lower()

        # Validate email format: sr_code@g.batstate-u.edu.ph
        if not email.endswith(f"@{GSUITE_DOMAIN}"):
            raise ValidationError(f"Only institutional G-Suite emails (@{GSUITE_DOMAIN}) are allowed.")

        # Extract email username (part before @)
        email_username = email.split("@")[0]

        # Check if email username matches SR-Code
        if sr_code and email_username != sr_code:
            raise ValidationError(
                f"Email must follow the format: {sr_code}@{GSUITE_DOMAIN}. "
                f"You entered: {email}"
            )

        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")

        return email

    def clean_section_code(self):
        section_code = self.cleaned_data["section_code"]

        if len(section_code) != 4:
            raise ValidationError("Section code must be exactly 4 digits.")

        if not section_code.isdigit():
            raise ValidationError("Section code must contain digits only.")

        if section_code[0] not in "1234":
            raise ValidationError("First digit must be the year level: 1, 2, 3, or 4.")

        if section_code[1] not in "123":
            raise ValidationError("Second digit must be the term: 1, 2, or 3.")

        if section_code[2] != "0":
            raise ValidationError("Third digit must be 0.")

        if section_code[3] == "0":
            raise ValidationError("Fourth digit must be the section number, starting from 1.")

        return section_code


class CurriculumForm(forms.ModelForm):
    class Meta:
        model = Curriculum
        fields = [
            "program",
            "curriculum_code",
            "curriculum_name",
            "academic_year_label",
            "total_units",
            "is_active",
        ]

        widgets = {
            "program": forms.Select(attrs={"class": "form-select"}),
            "curriculum_code": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Example: BSCpE-2018"
            }),
            "curriculum_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Example: Bachelor of Science in Computer Engineering Curriculum"
            }),
            "academic_year_label": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Example: AY 2018-2019"
            }),
            "total_units": forms.NumberInput(attrs={
                "class": "form-control",
                # FIX #2: Added min HTML attribute as a UX hint.
                # Server-side enforcement is in clean_total_units() below.
                "min": "1",
                "placeholder": "Example: 183"
            }),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    # FIX #2: Added server-side range validation for total_units.
    # The widget's min attribute is a browser hint only and can be bypassed —
    # this ensures the value is always validated on the server.
    def clean_total_units(self):
        total_units = self.cleaned_data.get("total_units")

        if total_units is None:
            raise ValidationError("Total units is required.")

        if total_units < 1:
            raise ValidationError("Total units must be at least 1.")

        if total_units > 300:
            raise ValidationError("Total units must not exceed 300.")

        return total_units


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "course_code",
            "course_title",
            "units",
            "is_elective",
        ]

        widgets = {
            "course_code": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Example: MATH 401"
            }),
            "course_title": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Example: Differential Calculus"
            }),
            "units": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
                "max": "12",
                "placeholder": "Example: 3"
            }),
            "is_elective": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_units(self):
        units = self.cleaned_data.get("units")

        if units is None:
            raise ValidationError("Units is required.")

        if units < 1 or units > 12:
            raise ValidationError("Units must be between 1 and 12.")

        return units


class CurriculumCourseForm(forms.ModelForm):
    class Meta:
        model = CurriculumCourse
        fields = [
            "curriculum",
            "course",
            "year_level",
            "term",
            "display_order",
            "is_required",
            "standing_requirement",
        ]

        widgets = {
            "curriculum": forms.Select(attrs={"class": "form-select"}),
            "course": forms.Select(attrs={"class": "form-select"}),
            "year_level": forms.NumberInput(attrs={
                "class": "form-control",
                # Added min/max as UX hints; server-side check is in clean_year_level().
                "min": "1",
                "max": "4",
                "placeholder": "Example: 1"
            }),
            "term": forms.Select(attrs={"class": "form-select"}),
            "display_order": forms.NumberInput(attrs={
                "class": "form-control",
                "placeholder": "Example: 1"
            }),
            "is_required": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "standing_requirement": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Example: 2nd Year Standing"
            }),
        }

    def clean_year_level(self):
        year_level = self.cleaned_data.get("year_level")

        # FIX #4: Added None guard before comparison. Previously, an empty
        # submission caused a "NoneType < int" TypeError at runtime instead
        # of a clean validation error being shown to the user.
        if year_level is None:
            raise ValidationError("Year level is required.")

        if year_level < 1 or year_level > 9:
            raise ValidationError("Year level must be from 1 to 9.")

        return year_level

    def clean(self):
        cleaned_data = super().clean()
        curriculum = cleaned_data.get("curriculum")
        course = cleaned_data.get("course")

        if curriculum and course:

            qs = CurriculumCourse.objects.filter(
                curriculum=curriculum,
                course=course,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError(
                    "This course is already assigned to the selected curriculum."
                )

        return cleaned_data


class CourseRequirementForm(forms.ModelForm):
    class Meta:
        model = CourseRequirement
        fields = [
            "course",
            "required_course",
            "requirement_type",
        ]

        widgets = {
            "course": forms.Select(attrs={"class": "form-select"}),
            "required_course": forms.Select(attrs={"class": "form-select"}),
            "requirement_type": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        course = cleaned_data.get("course")
        required_course = cleaned_data.get("required_course")

        if course and required_course:
            if course == required_course:
                raise ValidationError("A course cannot require itself.")

            qs = CourseRequirement.objects.filter(
                course=course,
                required_course=required_course,
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError(
                    "This requirement already exists for the selected course."
                )

        return cleaned_data

class StudentGradeForm(forms.Form):
    grade_value = forms.DecimalField(
        required=False,
        max_digits=4,
        decimal_places=2,
        min_value=1.00,
        max_value=5.00,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "step": "0.25",
            "min": "1.00",
            "max": "5.00",
            "placeholder": "Example: 2.50"
        })
    )

    remarks = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Optional remarks"
        })
    )

    def clean_grade_value(self):
        grade = self.cleaned_data.get("grade_value")

        if grade is None:
            return grade  # optional field, skip
        valid_grades = {
            Decimal("1.00") + Decimal("0.25") * i for i in range(17)
        }

        if grade not in valid_grades:
            raise forms.ValidationError(
                "Grade must be in 0.25 increments (e.g. 1.00, 1.25, 1.50)."
            )

        return grade
    def clean_remarks(self):
        remarks = self.cleaned_data.get("remarks", "")
        return remarks.strip()

class CurriculumUploadForm(forms.Form):
    ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".docx", ".pdf"}
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024

    curriculum = forms.ModelChoiceField(
        queryset=Curriculum.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            "class": "form-select"
        })
    )

    file = forms.FileField(
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".csv,.xlsx,.xls,.docx,.pdf"
        }),
        help_text="Upload a CSV, Excel, DOCX, or text-based PDF curriculum file."
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        file_name = uploaded_file.name.lower()

        if not any(file_name.endswith(extension) for extension in self.ALLOWED_EXTENSIONS):
            raise ValidationError("Unsupported file type. Upload CSV, Excel, DOCX, or text-based PDF.")

        if uploaded_file.size > self.MAX_UPLOAD_SIZE:
            raise ValidationError("File size must not exceed 10 MB.")

        return uploaded_file

class GradeUploadForm(forms.Form):
    ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
    MAX_UPLOAD_SIZE = 10 * 1024 * 1024

    school_year = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Example: 2025-2026"
        })
    )

    file = forms.FileField(
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".pdf,.jpg,.jpeg,.png"
        }),
        help_text="Upload a PDF, JPG, JPEG, or PNG grade file."
    )

    def clean_school_year(self):
        school_year = self.cleaned_data["school_year"].strip()

        if not re.match(r"^\d{4}-\d{4}$", school_year):
            raise ValidationError("School year must follow the format YYYY-YYYY.")

        start_year, end_year = [int(part) for part in school_year.split("-")]
        if end_year != start_year + 1:
            raise ValidationError("School year must cover one academic year, e.g. 2025-2026.")

        return school_year

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        file_name = uploaded_file.name.lower()

        if not any(file_name.endswith(extension) for extension in self.ALLOWED_EXTENSIONS):
            raise ValidationError("Unsupported file type. Upload PDF, JPG, JPEG, or PNG.")

        if uploaded_file.size > self.MAX_UPLOAD_SIZE:
            raise ValidationError("File size must not exceed 10 MB.")

        return uploaded_file
    
class StudentImportForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".csv,.xlsx,.xls"
        }),
        help_text="Upload a CSV or Excel file containing student registration records."
    )
