from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .forms import EmailLoginForm, FirstLoginPasswordChangeForm
from .models import User

def login_view(request, role=None):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    # Validate role parameter
    valid_roles = [User.Role.ADMIN, User.Role.STUDENT]
    if role and role not in valid_roles:
        return redirect("login")

    if request.method == "POST":
        form = EmailLoginForm(request.POST, expected_role=role)

        if form.is_valid():
            user = form.cleaned_data["user"]
            login(request, user)

            if user.must_change_password:
                return redirect("change_password")

            return redirect_user_by_role(user)

    else:
        form = EmailLoginForm(expected_role=role)

    return render(request, "accounts/login.html", {
        "form": form,
        "role": role
    })


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("landing_page")


@login_required
def change_password_view(request):
    user = request.user

    if not user.must_change_password:
        messages.info(request, "You do not need to change your password.")
        return redirect_user_by_role(user)

    if request.method == "POST":
        form = FirstLoginPasswordChangeForm(request.POST)

        if form.is_valid():
            new_password = form.cleaned_data["new_password"]

            user.set_password(new_password)
            user.must_change_password = False
            user.save()
            logout(request)
            messages.success(request, "Password changed successfully. Please log in again.")

            return redirect("login")

    else:
        form = FirstLoginPasswordChangeForm()

    return render(request, "accounts/change_password.html", {
        "form": form
    })


def redirect_user_by_role(user):
    if not user.is_authenticated:
        return redirect("login")

    if user.must_change_password:
        return redirect("change_password")

    if user.role == User.Role.ADMIN:
        return redirect("admin_dashboard")

    if user.role == User.Role.STUDENT:
        return redirect("student_dashboard")

    return redirect("landing_page")
