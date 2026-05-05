import functools
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect

from accounts.models import User
from .forms import ManualStudentRegistrationForm
from .models import Student


def admin_required(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")

        if request.user.role != User.Role.ADMIN:
            messages.error(request, "You are not allowed to access this page.")
            return redirect("student_dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper

@admin_required
def student_registration(request):
    if request.method == "POST":
        form = ManualStudentRegistrationForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data


            safe_last_name = re.sub(r"[^a-z0-9]", "", data["last_name"].lower())
            temporary_password = f"{data['sr_code']}{safe_last_name}"


            with transaction.atomic():
                student_user = User.objects.create_user(
                    email=data["email"],
                    password=temporary_password,
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    role=User.Role.STUDENT,
                    must_change_password=True,
                    is_active=True
                )

                Student.objects.create(
                    user=student_user,
                    sr_code=data["sr_code"],
                    curriculum=data["curriculum"],
                    year_level=int(data["section_code"][0]),
                    current_semester=int(data["section_code"][1]),
                    section_code=data["section_code"],
                    status=data["status"]
                )

            messages.success(
                request,
                f"Student registered successfully. Temporary password: {temporary_password}"
            )

            return redirect("student_registration")

    else:
        form = ManualStudentRegistrationForm()

    return render(request, "academics/student_registration.html", {
        "form": form,
    })


@admin_required
def student_list(request):
    students = Student.objects.select_related(
        "user",
        "curriculum",
        "curriculum__program"
    ).order_by("year_level", "section_code", "user__last_name")

    return render(request, "academics/student_list.html", {
        "students": students
    })
