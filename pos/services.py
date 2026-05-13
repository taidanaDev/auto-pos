import re
from collections import defaultdict

from django.db import transaction
from django.db.models import Case, When, IntegerField, Value
from django.contrib.auth import get_user_model

from academics.models import CurriculumCourse, StudentCourseRecord, CourseRequirement
from academics.services import calculate_year_standing
from .models import POSPlan, POSPlanItem

User = get_user_model()

TERM_ORDER = {
    "first_sem": 1,
    "second_sem": 2,
    "midterm": 3,
}
TERM_SEQUENCE = ["first_sem", "second_sem", "midterm"]
UNIT_LIMITS = {
    "first_sem": 25,
    "second_sem": 25,
    "midterm": 9,
}

def get_ordered_curriculum_courses(curriculum):
    """
    Returns curriculum courses in correct academic order:
    year level → term order → display order.
    Only required courses are included.
    """
    return (
        CurriculumCourse.objects.select_related("course", "curriculum")
        .filter(curriculum=curriculum, is_required=True)
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
    """Returns course IDs the student has already passed with credit earned."""
    return set(
        StudentCourseRecord.objects.filter(
            student=student,
            status=StudentCourseRecord.RecordStatus.PASSED,
            is_credit_earned=True,
        ).values_list("course_id", flat=True)
    )


def get_failed_course_ids(student, passed_course_ids=None):
    """
    Returns course IDs the student has failed and has NOT since re-passed.
    Pass passed_course_ids to subtract them (passed status always wins).
    """
    failed = set(
        StudentCourseRecord.objects.filter(
            student=student,
            status=StudentCourseRecord.RecordStatus.FAILED,
        ).values_list("course_id", flat=True)
    )

    if passed_course_ids is not None:
        failed -= passed_course_ids

    return failed


def _build_requirement_maps(course_ids):
    prerequisite_map = defaultdict(set)
    corequisite_map = defaultdict(set)

    rows = (
        CourseRequirement.objects.filter(course_id__in=course_ids)
        .values("course_id", "required_course_id", "requirement_type")
    )
    for row in rows:
        if row["requirement_type"] == CourseRequirement.RequirementType.PREREQUISITE:
            prerequisite_map[row["course_id"]].add(row["required_course_id"])
        elif row["requirement_type"] == CourseRequirement.RequirementType.COREQUISITE:
            corequisite_map[row["course_id"]].add(row["required_course_id"])

    return prerequisite_map, corequisite_map


def standing_requirement_is_met(curriculum_course, student_year_standing):
    """
    Returns True if the student's calculated year standing satisfies the
    standing requirement attached to the curriculum course.
    """
    requirement = curriculum_course.standing_requirement
    if not requirement:
        return True  # No requirement → always met

    requirement = requirement.lower().strip()

    if re.search(r'\b(2nd|2)\b', requirement):
        return student_year_standing >= 2
    if re.search(r'\b(3rd|3)\b', requirement):
        return student_year_standing >= 3
    if re.search(r'\b(4th|4)\b', requirement):
        return student_year_standing >= 4

    return True  # Unrecognised format → assume met

def build_remaining_course_list(student, passed_course_ids, failed_course_ids):
    """
    Returns curriculum courses not yet completed, in priority order:
      1. Failed courses (retry first — student must retake these)
      2. Not-yet-taken courses (curriculum order)
    """
    curriculum_courses = list(get_ordered_curriculum_courses(student.curriculum))

    failed_courses = []
    regular_remaining_courses = []

    for curriculum_course in curriculum_courses:
        course_id = curriculum_course.course_id

        if course_id in passed_course_ids:
            continue  # Credit already earned — never re-plan

        if course_id in failed_course_ids:
            failed_courses.append(curriculum_course)
        else:
            regular_remaining_courses.append(curriculum_course)

    return failed_courses + regular_remaining_courses


def get_next_terms_from_students(student, max_extra_years=3):
    """
    Generates an ordered list of planning slots starting from the student's
    current year and semester.
    """
    start_year = student.year_level
    start_semester = student.current_semester  # expected: 1, 2, or 3

    semester_to_term = {
        1: "first_sem",
        2: "second_sem",
        3: "midterm",
    }

    start_term = semester_to_term.get(start_semester)
    if start_term is None:
        raise ValueError(
            f"Student {student.id} has an invalid current_semester value: "
            f"{start_semester!r}. Expected 1, 2, or 3."
        )

    start_term_order = TERM_ORDER[start_term]

    max_curriculum_year = (
        CurriculumCourse.objects.filter(curriculum=student.curriculum)
        .order_by("-year_level")
        .values_list("year_level", flat=True)
        .first()
    ) or start_year

    max_planning_year = max_curriculum_year + max_extra_years

    planning_slots = []
    for year in range(start_year, max_planning_year + 1):
        for term in TERM_SEQUENCE:
            term_order = TERM_ORDER[term]
            if year == start_year and term_order < start_term_order:
                continue  # Skip terms already past for the starting year
            planning_slots.append({
                "year_level": year,
                "term": term,
                "unit_limit": UNIT_LIMITS[term],
                "current_units": 0,
                "courses": [],
                "beyond_curriculum": year > max_curriculum_year,
            })

    return planning_slots, max_curriculum_year


def course_is_offered_in_term(curriculum_course, term):
    """Returns True if the course's official term matches the slot's term."""
    return curriculum_course.term == term


def can_add_course_to_slot(curriculum_course, slot):
    """
    Returns True when:
      - The course is offered in the slot's term, AND
      - Adding it will not push the slot over its unit limit.
    """
    course = curriculum_course.course

    if not course_is_offered_in_term(curriculum_course, slot["term"]):
        return False

    if slot["current_units"] + course.units > slot["unit_limit"]:
        return False

    return True

def generate_rearranged_pos_plan(student, generated_by=None):
    """
    Generates a rearranged POS plan enforcing the following academic rules:

    Exclusion
    - Courses the student has already passed (with credit) are excluded.

    Priority
    - Failed courses are scheduled before not-yet-taken courses.

    Prerequisites
    - ALL prerequisites must appear in passed_course_ids.
    - Failed courses do NOT satisfy prerequisites.

    Co-requisites
    - Each corequisite must be either already passed OR placed in the same
      planning slot as the course being scheduled.

    Standing requirement
    - Evaluated against the student's calculated 75%-threshold year standing.

    Term availability
    - Courses are only placed in their official offering term.

    Unit limits
    - first_sem: 25 units, second_sem: 25 units, midterm: 9 units.
    """

    # Pre-fetch all shared data before the transaction
    passed_course_ids = get_passed_course_ids(student)
    failed_course_ids = get_failed_course_ids(student, passed_course_ids)
    remaining_courses = build_remaining_course_list(
        student, passed_course_ids, failed_course_ids
    )

    student_year_standing = calculate_year_standing(student)
    planning_slots, max_curriculum_year = get_next_terms_from_students(student)

    remaining_course_ids = [cc.course_id for cc in remaining_courses]
    prerequisite_map, corequisite_map = _build_requirement_maps(remaining_course_ids)

    placed_course_ids = set()
    blocked_courses = []
    overflow_course_codes = []

    with transaction.atomic():
        POSPlan.objects.filter(student=student, is_current=True).update(is_current=False)

        pos_plan = POSPlan.objects.create(
            student=student,
            generated_by=generated_by,
            status=POSPlan.PlanStatus.DRAFT,
            is_current=True,
            notes="Rearranged POS plan with prerequisite, standing, and unit-limit checks.",
        )

        display_counter = 1

        for curriculum_course in remaining_courses:
            course = curriculum_course.course

            if course.id in placed_course_ids:
                continue 

            if not standing_requirement_is_met(curriculum_course, student_year_standing):
                blocked_courses.append(
                    f"{course.course_code}: standing requirement not met"
                )
                continue

            # Prerequisite check 
            prereq_ids = prerequisite_map.get(course.id, set())
            if not prereq_ids.issubset(passed_course_ids):
                blocked_courses.append(
                    f"{course.course_code}: prerequisites not completed"
                )
                continue

            # Corequisite IDs
            corequisite_ids = corequisite_map.get(course.id, set())

            placed = False

            for slot in planning_slots:
                if not can_add_course_to_slot(curriculum_course, slot):
                    continue

                slot_course_ids = {item["course"].id for item in slot["courses"]}

                # Every corequisite must be passed already OR in this same slot
                corequisites_met = all(
                    coreq_id in passed_course_ids or coreq_id in slot_course_ids
                    for coreq_id in corequisite_ids
                )
                if not corequisites_met:
                    continue

                POSPlanItem.objects.create(
                    pos_plan=pos_plan,
                    course=course,
                    planned_year_level=slot["year_level"],
                    planned_term=slot["term"],
                    display_order=display_counter,
                    is_auto_assigned=True,
                    is_manually_adjusted=False,
                    is_completed=False,
                    notes="Auto-rearranged by system",
                )

                slot["courses"].append({
                    "course": course,
                    "curriculum_course": curriculum_course,
                })
                slot["current_units"] += course.units
                placed_course_ids.add(course.id)
                display_counter += 1
                placed = True

                if slot["beyond_curriculum"]:
                    overflow_course_codes.append(course.course_code)

                break  # Course placed — move to next course

            if not placed:
                blocked_courses.append(
                    f"{course.course_code}: no available slot found"
                )
                
        extra_notes = []
        if blocked_courses:
            extra_notes.append("Blocked courses:\n" + "\n".join(blocked_courses))
        if overflow_course_codes:
            extra_notes.append(
                f"Courses placed beyond curriculum year {max_curriculum_year}:\n"
                + "\n".join(overflow_course_codes)
            )
        if extra_notes:
            pos_plan.notes += "\n\n" + "\n\n".join(extra_notes)
            pos_plan.save()

    return pos_plan
