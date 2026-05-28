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
        sr_code = self.cleaned_data["sr_code"].strip()

        if not re.match(r"^\d{2}-\d{5}$", sr_code):
            raise ValidationError("SR-Code must follow the format YY-NNNNN, e.g. 23-00001.")

        if Student.objects.filter(sr_code=sr_code).exists():
            raise ValidationError("This SR-Code is already registered.")

        return sr_code

    def clean_first_name(self):
        first_name = self.cleaned_data["first_name"].strip()

        if not first_name:
            raise ValidationError("First name cannot be empty.")

        if not any(char.isalnum() for char in first_name):
            raise ValidationError("First name must contain at least one letter.")

        if len(first_name) < 2:
            raise ValidationError("First name must be at least 2 characters long.")

        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data["last_name"].strip()

        if not last_name:
            raise ValidationError("Last name cannot be empty.")

        if not any(char.isalnum() for char in last_name):
            raise ValidationError("Last name must contain at least one letter or number.")

        if len(last_name) < 2:
            raise ValidationError("Last name must be at least 2 characters long.")

        return last_name

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
        section_code = self.cleaned_data["section_code"].strip()

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
                "min": "1",
                "placeholder": "Example: 183"
            }),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_curriculum_code(self):
        curriculum_code = self.cleaned_data.get("curriculum_code", "").strip()

        if not curriculum_code:
            raise ValidationError("Curriculum code cannot be empty.")

        if not any(char.isalnum() for char in curriculum_code):
            raise ValidationError("Curriculum code must contain at least one letter or number.")

        return curriculum_code

    def clean_curriculum_name(self):
        curriculum_name = self.cleaned_data.get("curriculum_name", "").strip()

        if not curriculum_name:
            raise ValidationError("Curriculum name cannot be empty.")

        if not any(char.isalnum() for char in curriculum_name):
            raise ValidationError("Curriculum name must contain at least one letter or number.")

        if len(curriculum_name) < 5:
            raise ValidationError("Curriculum name must be at least 5 characters long.")

        return curriculum_name

    def clean_academic_year_label(self):
        academic_year_label = self.cleaned_data.get("academic_year_label", "").strip()

        if not academic_year_label:
            raise ValidationError("Academic year label cannot be empty.")

        if not any(char.isalnum() for char in academic_year_label):
            raise ValidationError("Academic year label must contain at least one letter or number.")

        return academic_year_label

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

    def clean_course_code(self):
        course_code = self.cleaned_data.get("course_code", "").strip()

        if not course_code:
            raise ValidationError("Course code cannot be empty.")

        if not any(char.isalnum() for char in course_code):
            raise ValidationError("Course code must contain at least one letter or number.")

        return course_code

    def clean_course_title(self):
        course_title = self.cleaned_data.get("course_title", "").strip()

        if not course_title:
            raise ValidationError("Course title cannot be empty.")

        if not any(char.isalnum() for char in course_title):
            raise ValidationError("Course title must contain at least one letter")

        if len(course_title) < 3:
            raise ValidationError("Course title must be at least 3 characters long.")

        return course_title

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
        if year_level is None:
            raise ValidationError("Year level is required.")

        if year_level < 1 or year_level > 9:
            raise ValidationError("Year level must be from 1 to 9.")

        return year_level

    def clean_standing_requirement(self):
        standing_requirement = (self.cleaned_data.get("standing_requirement") or "").strip()

        if not standing_requirement:
            return standing_requirement  # optional field

        if not any(char.isalnum() for char in standing_requirement):
            raise ValidationError("Standing requirement must contain at least one letter")

        if len(standing_requirement) < 3:
            raise ValidationError("Standing requirement must be at least 3 characters long.")

        return standing_requirement

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
        remarks = self.cleaned_data.get("remarks", "").strip()
        
        if remarks and not any(char.isalnum() for char in remarks):
            raise ValidationError("Remarks must contain at least one letter")

        return remarks

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

        if uploaded_file.size == 0:
            raise ValidationError("File cannot be empty.")

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

        if uploaded_file.size == 0:
            raise ValidationError("File cannot be empty.")

        return uploaded_file
    
class StudentImportForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={
            "class": "form-control",
            "accept": ".csv,.xlsx,.xls"
        }),
        help_text="Upload a CSV or Excel file containing student registration records."
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        file_name = uploaded_file.name.lower()

        allowed_extensions = {".csv", ".xlsx", ".xls"}
        if not any(file_name.endswith(extension) for extension in allowed_extensions):
            raise ValidationError("Unsupported file type. Upload CSV or Excel (.xlsx, .xls) files only.")

        if uploaded_file.size > 10 * 1024 * 1024:
            raise ValidationError("File size must not exceed 10 MB.")

        if uploaded_file.size == 0:
            raise ValidationError("File cannot be empty.")

        return uploaded_file
