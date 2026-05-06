from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect  # FIX 1: Added redirect

from accounts.decorators import must_have_changed_password, role_required
from accounts.models import User
from academics.models import Student
from academics.services import get_student_academic_progress


def landing_page(request):
    return render(request, "dashboard/landing_page.html")


@login_required
@must_have_changed_password
@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    return render(request, "dashboard/admin_dashboard.html")


@login_required
@must_have_changed_password
@role_required(User.Role.STUDENT)
def student_dashboard(request):
    student = None
    progress_data = None

    try:
        student = request.user.student_profile
        progress_data = get_student_academic_progress(student)
    except Student.DoesNotExist:
        pass  # student and progress_data remain None

    return render(request, "dashboard/student_dashboard.html", {
        "student": student,
        "progress": progress_data,
    })