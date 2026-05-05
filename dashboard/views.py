from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.decorators import must_have_changed_password, role_required
from accounts.models import User


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
    return render(request, "dashboard/student_dashboard.html")
