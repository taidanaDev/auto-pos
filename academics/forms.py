import re

from django import forms
from django.core.exceptions import ValidationError

from accounts.models import User
from .models import Student, Curriculum

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
        if not email.endswith(f"@{GSUITE_DOMAIN}"):
            raise ValidationError(f"Only institutional G-Suite emails (@{GSUITE_DOMAIN}) are allowed.")

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
