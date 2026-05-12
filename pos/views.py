import functools

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from accounts.models import User
from academics.models import Student
from .models import POSPlan
from .services import generate_basic_pos_plan


def student_required(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != User.Role.STUDENT:
            messages.error(request, "You are not allowed to access this page.")
            return redirect("admin_dashboard")
        return view_func(request, *args, **kwargs)
    return wrapper


def get_student_or_redirect(request):
    try:
        return request.user.student_profile, None
    except Student.DoesNotExist:
        messages.error(request, "Student profile not found.")
        return None, redirect("student_dashboard")


@login_required
@student_required
def generate_pos(request):
    student, err = get_student_or_redirect(request)
    if err:
        return err

    if request.method == "POST":
        try:
            pos_plan = generate_basic_pos_plan(student=student, generated_by=request.user)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("student_dashboard")
        messages.success(request, "Basic POS plan generated successfully.")
        return redirect("generated_pos_detail", pos_plan_id=pos_plan.id)

    return render(request, "pos/generate_pos_confirm.html", {"student": student})


@login_required
@student_required
def generated_pos_detail(request, pos_plan_id):
    student, err = get_student_or_redirect(request)
    if err:
        return err

    pos_plan = get_object_or_404(POSPlan, id=pos_plan_id, student=student)
    items = (
        pos_plan.items.select_related("course")
        .order_by("planned_year_level", "planned_term", "display_order")
    )

    return render(request, "pos/generated_pos.html", {
        "student": student,
        "pos_plan": pos_plan,
        "items": items,
    })


@login_required
@student_required
def my_pos_plans(request):
    student, err = get_student_or_redirect(request)
    if err:
        return err

    pos_plans = (
        POSPlan.objects.filter(student=student)
        .select_related("generated_by")
        .prefetch_related("items")
        .order_by("-created_at")
    )

    return render(request, "pos/my_pos_plans.html", {
        "student": student,
        "pos_plans": pos_plans,
    })