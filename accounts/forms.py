from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your email"
        })
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your password"
        })
    )

    def __init__(self, *args, expected_role=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.expected_role = expected_role

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
              # NOTE: Add rate limiting in the view (e.g. django-axes or django-ratelimit) to prevent brute-force attacks   
            user = authenticate(
                username=email,
                password=password
            )

            if user is None:
                raise forms.ValidationError("Invalid email or password.")

            if not user.is_active:
                raise forms.ValidationError("This account is inactive.")

            # If a specific role was expected, validate it matches
            if self.expected_role and user.role != self.expected_role:
                raise forms.ValidationError(
                    f"This account is not registered as a {self.expected_role.capitalize()}. "
                    f"Please use the {user.role.capitalize()} login instead."
                )

            cleaned_data["user"] = user

        return cleaned_data


class FirstLoginPasswordChangeForm(forms.Form):
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Enter new password"
        }),
        min_length=8
    )

    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-control",
            "placeholder": "Confirm new password"
        }),
        min_length=8
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password:
            if new_password != confirm_password:
                self.add_error("confirm_password", "Passwords do not match.")

            try:
                validate_password(new_password)
            except DjangoValidationError as e:
                self.add_error("new_password", e.messages)

        return cleaned_data