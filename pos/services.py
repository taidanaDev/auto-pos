from django.db import transaction
from django.db.models import Case, When, IntegerField, Value
from django.contrib.auth import get_user_model

from academics.models import CurriculumCourse, StudentCourseRecord
from .models import POSPlan, POSPlanItem

User = get_user_model()


def get_ordered_curriculum_courses(curriculum):
    """
    Returns curriculum courses in correct academic order:
    year level → term order → display order.
    """
    return (
        CurriculumCourse.objects.select_related("course", "curriculum")
        .filter(curriculum=curriculum)
        .annotate(
            pos_term_order=Case(
                When(term="first_sem", then=1),
                When(term="second_sem", then=2),
                When(term="midterm", then=3),
                default=Value(99),  
                output_field=IntegerField(),
            )
        )
        .order_by("year_level", "pos_term_order", "display_order")
    )


def get_passed_course_ids(student):
    # Returns course IDs the student has already passed

    return set(
        StudentCourseRecord.objects.filter(
            student=student,
            status=StudentCourseRecord.RecordStatus.PASSED,
            is_credit_earned=True,
        ).values_list("course_id", flat=True)
    )


def get_failed_course_ids(student, passed_course_ids=None):
    # Returns course IDs the student has failed and still not re-passed.
    failed = set(
        StudentCourseRecord.objects.filter(
            student=student,
            status=StudentCourseRecord.RecordStatus.FAILED,
        ).values_list("course_id", flat=True)
    )

    if passed_course_ids:
        # A student may have FAILED then later PASSED the same course.
        # Passed status always wins — do not re-included in the plan.
        failed -= passed_course_ids

    return failed


def generate_basic_pos_plan(student, generated_by=None):
    """
    Generates a basic draft POS plan for the student.

    LOGIC.RULES:
      - EXCLUDE courses the student has passed (credit earned).
      - INCLUDE courses the student has failed (and not yet re-passed).
      - INCLUDE courses the student has not yet taken at all.
    """

    if not getattr(student, "curriculum", None):
        raise ValueError(
            f"Student {student.id} has no curriculum assigned. "
            "A POS plan cannot be generated without a curriculum."
        )

    if generated_by is not None and not isinstance(generated_by, User):
        raise TypeError(
            f"generated_by must be a User instance, got {type(generated_by).__name__}."
        )
    

    curriculum_courses = get_ordered_curriculum_courses(student.curriculum)
    passed_course_ids = get_passed_course_ids(student)
    failed_course_ids = get_failed_course_ids(student, passed_course_ids)

    with transaction.atomic():

        POSPlan.objects.select_for_update().filter(
            student=student,
            is_current=True,
        ).update(is_current=False)

        pos_plan = POSPlan.objects.create(
            student=student,
            generated_by=generated_by,
            status=POSPlan.PlanStatus.DRAFT,
            is_current=True,
            notes="Basic generated POS plan. Completed courses are excluded.",
        )

        items_to_create = []
        display_counter = 1

        for curriculum_course in curriculum_courses:
            course = curriculum_course.course

            # Skip courses the student has already passed.
            if course.id in passed_course_ids:
                continue

            is_failed = course.id in failed_course_ids

            items_to_create.append(
                POSPlanItem(
                    pos_plan=pos_plan,
                    course=course,
                    planned_year_level=curriculum_course.year_level,
                    planned_term=curriculum_course.term,
                    display_order=display_counter,
                    is_auto_assigned=True,
                    is_manually_adjusted=False,
                    is_completed=False,
                    notes="Retake failed course" if is_failed else "Remaining course",
                )
            )
            display_counter += 1

        POSPlanItem.objects.bulk_create(items_to_create)

    return pos_plan
