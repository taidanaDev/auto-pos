import functools

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import DatabaseError
from django.db.models import Case, When, IntegerField, Value
from django.shortcuts import render, redirect, get_object_or_404

from accounts.models import User
from academics.models import Student
from .models import POSPlan
from .services import generate_rearranged_pos_plan
from .pdf import build_pos_pdf_context, generate_pos_pdf_response

def student_required(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.role != User.Role.STUDENT:
            messages.error(request, "You are not allowed to access this page.")
            return redirect("admin_dashboard")
        return view_func(request, *args, **kwargs)
    return wrapper


def with_student_profile(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            messages.error(request, "Student profile not found.")
            return redirect("student_dashboard")
        return view_func(request, student, *args, **kwargs)
    return wrapper


@student_required
@login_required
@with_student_profile
def generate_pos(request, student):
    """
    GET  — confirmation page before generating a new POS plan.
    POST — triggers plan generation and redirects to the detail view.
    """
    if request.method == "POST":
        try:
            pos_plan = generate_rearranged_pos_plan(
                student=student,
                generated_by=request.user,
            )
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("student_dashboard")
        except DatabaseError:
            messages.error(request, "A database error occurred. Please try again.")
            return redirect("student_dashboard")

        messages.success(request, "Rearranged POS plan generated successfully.")
        return redirect("generated_pos_detail", pos_plan_id=pos_plan.id)

    return render(request, "pos/generate_pos_confirm.html", {"student": student})


@student_required
@login_required
@with_student_profile
def generated_pos_detail(request, student, pos_plan_id):
    # Displays a single POSPlan with its items sorted by year → term → display order.

    pos_plan = get_object_or_404(POSPlan, id=pos_plan_id, student=student)

    items = (
        pos_plan.items
        .annotate(
            term_order=Case(
                When(planned_term="first_sem", then=1),
                When(planned_term="second_sem", then=2),
                When(planned_term="midterm", then=3),
                default=Value(99),
                output_field=IntegerField(),
            )
        )
        .order_by("planned_year_level", "term_order", "display_order")
    )

    return render(request, "pos/generated_pos.html", {
        "student": student,
        "pos_plan": pos_plan,
        "items": items,
    })


@student_required
@login_required
@with_student_profile
def my_pos_plans(request, student):
    # Lists all POS plans for the student, most recent first.
  
    pos_plans = (
        POSPlan.objects.filter(student=student)
        .select_related("generated_by")
        .order_by("-created_at")
    )

    return render(request, "pos/my_pos_plans.html", {
        "student": student,
        "pos_plans": pos_plans,
    })

@student_required
@login_required
@with_student_profile
def pos_pdf_preview(request, student, pos_plan_id):
    pos_plan = get_object_or_404(
        POSPlan,
        id=pos_plan_id,
        student=student
    )

    return render(
        request,
        "pos/pos_pdf_preview.html",
        build_pos_pdf_context(student, pos_plan),
    )


@student_required
@login_required
@with_student_profile
def pos_pdf_download(request, student, pos_plan_id):
    pos_plan = get_object_or_404(
        POSPlan,
        id=pos_plan_id,
        student=student
    )

    try:
        return generate_pos_pdf_response(request, student, pos_plan)
    except RuntimeError as exc:
        messages.error(request, str(exc))
        return redirect("pos_pdf_preview", pos_plan_id=pos_plan.id)
