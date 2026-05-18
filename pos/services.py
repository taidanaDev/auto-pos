import re
from collections import OrderedDict, defaultdict

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Case, IntegerField, Sum, Value, When

from academics.models import CourseRequirement, CurriculumCourse, StudentCourseRecord
from .models import POSPlan, POSPlanItem

User = get_user_model()

TERM_ORDER = {
    "first_sem": 1,
    "second_sem": 2,
    "midterm": 3,
}
TERM_SEQUENCE = ["first_sem", "second_sem", "midterm"]
DEFAULT_UNIT_LIMITS = {
    "first_sem": 25,
    "second_sem": 25,
    "midterm": 9,
}


def get_all_unit_limits(curriculum):
    rows = (
        CurriculumCourse.objects
        .filter(curriculum=curriculum, is_required=True)
        .values("year_level", "term")
        .annotate(total_units=Sum("course__units"))
    )
    return {(row["year_level"], row["term"]): row["total_units"] for row in rows}


def get_unit_limit_for_planning_slot(unit_limit_map, planned_year_level, term):
    exact = unit_limit_map.get((planned_year_level, term))
    if exact:
        return exact

    same_term_entries = [
        (year_level, units)
        for (year_level, mapped_term), units in unit_limit_map.items()
        if mapped_term == term and units > 0
    ]
    if same_term_entries:
        _, fallback_units = max(same_term_entries, key=lambda entry: entry[0])
        return fallback_units

    return DEFAULT_UNIT_LIMITS.get(term, 25)


def get_ordered_curriculum_courses(curriculum):
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
    return set(
        StudentCourseRecord.objects.filter(
            student=student,
            status=StudentCourseRecord.RecordStatus.PASSED,
            is_credit_earned=True,
        ).values_list("course_id", flat=True)
    )


def get_failed_course_ids(student, passed_course_ids=None):
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

    rows = CourseRequirement.objects.filter(course_id__in=course_ids).values(
        "course_id",
        "required_course_id",
        "requirement_type",
    )
    for row in rows:
        if row["requirement_type"] == CourseRequirement.RequirementType.PREREQUISITE:
            prerequisite_map[row["course_id"]].add(row["required_course_id"])
        elif row["requirement_type"] == CourseRequirement.RequirementType.COREQUISITE:
            corequisite_map[row["course_id"]].add(row["required_course_id"])

    return prerequisite_map, corequisite_map


def get_min_standing_year(curriculum_course):
    requirement = curriculum_course.standing_requirement
    if not requirement:
        return None

    requirement = requirement.lower().strip()

    if re.search(r"\b(4th|4)\b", requirement):
        return 4
    if re.search(r"\b(3rd|3)\b", requirement):
        return 3
    if re.search(r"\b(2nd|2)\b", requirement):
        return 2

    return None


def slot_sort_key(year_level, term):
    return (year_level, TERM_ORDER.get(term, 99))


def next_same_term_after(term, minimum_slot):
    min_year, min_term_order = minimum_slot
    year = min_year
    if TERM_ORDER.get(term, 99) <= min_term_order:
        year += 1
    return (year, term)


def iter_future_slots_after(slot, max_year_level):
    year_level, term = slot
    start_order = TERM_ORDER.get(term, 99)

    for year in range(year_level, max_year_level + 1):
        for future_term in TERM_SEQUENCE:
            if year == year_level and TERM_ORDER[future_term] <= start_order:
                continue
            yield (year, future_term)


def course_has_hard_requirements(course_id, prerequisite_map, corequisite_map):
    return bool(prerequisite_map.get(course_id) or corequisite_map.get(course_id))


def find_next_fitting_slot(
    course_id,
    current_slot,
    planned_slots,
    course_map,
    unit_limit_map,
    max_year_level,
):
    course_units = course_map[course_id].course.units
    official_term = course_map[course_id].term
    units_by_slot = defaultdict(int)

    for planned_course_id, slot in planned_slots.items():
        if planned_course_id == course_id:
            continue
        units_by_slot[slot] += course_map[planned_course_id].course.units

    if official_term in {"first_sem", "midterm"}:
        same_term_slot = next_same_term_after(
            official_term,
            slot_sort_key(*current_slot),
        )
        same_term_limit = get_unit_limit_for_planning_slot(
            unit_limit_map,
            same_term_slot[0],
            same_term_slot[1],
        )
        if units_by_slot[same_term_slot] + course_units <= same_term_limit:
            return same_term_slot

    for future_slot in iter_future_slots_after(current_slot, max_year_level):
        if official_term != "midterm" and future_slot[1] == "midterm":
            continue

        limit = get_unit_limit_for_planning_slot(
            unit_limit_map,
            future_slot[0],
            future_slot[1],
        )
        if units_by_slot[future_slot] + course_units <= limit:
            return future_slot

    return next_same_term_after(
        official_term,
        slot_sort_key(*current_slot),
    )


def get_latest_failed_record_map(student, failed_course_ids):
    failed_records = (
        StudentCourseRecord.objects
        .filter(
            student=student,
            course_id__in=failed_course_ids,
            status=StudentCourseRecord.RecordStatus.FAILED,
        )
        .order_by("course_id", "-created_at")
    )

    latest_failed_records = {}
    for record in failed_records:
        if record.course_id not in latest_failed_records:
            latest_failed_records[record.course_id] = record

    return latest_failed_records


def get_latest_graded_record_map(student, course_ids):
    records = (
        StudentCourseRecord.objects
        .filter(
            student=student,
            course_id__in=course_ids,
            grade_value__isnull=False,
        )
        .order_by("course_id", "-created_at")
    )

    latest_records = {}
    for record in records:
        if record.course_id not in latest_records:
            latest_records[record.course_id] = record

    return latest_records


def get_latest_record_map(student, course_ids):
    records = (
        StudentCourseRecord.objects
        .filter(student=student, course_id__in=course_ids)
        .order_by("course_id", "-created_at")
    )

    latest_records = {}
    for record in records:
        if record.course_id not in latest_records:
            latest_records[record.course_id] = record

    return latest_records


def get_original_graded_curriculum_items(student):
    curriculum_courses = list(get_ordered_curriculum_courses(student.curriculum))
    course_ids = [item.course_id for item in curriculum_courses]
    latest_records = get_latest_graded_record_map(student, course_ids)

    original_items = []
    for curriculum_course in curriculum_courses:
        record = latest_records.get(curriculum_course.course_id)
        if not record:
            continue

        original_items.append({
            "curriculum_course": curriculum_course,
            "course": curriculum_course.course,
            "record": record,
            "is_completed": (
                record.status == StudentCourseRecord.RecordStatus.PASSED
                and record.is_credit_earned
            ),
            "is_failed": record.status == StudentCourseRecord.RecordStatus.FAILED,
        })

    return original_items


def build_complete_pos_display_items(student, pos_plan):
    curriculum_courses = list(get_ordered_curriculum_courses(student.curriculum))
    course_ids = [item.course_id for item in curriculum_courses]
    latest_records = get_latest_record_map(student, course_ids)
    moved_items = {
        item.course_id: item
        for item in pos_plan.items.select_related("course", "linked_record").all()
    }

    moved_out_orders_by_slot = defaultdict(list)
    for curriculum_course in curriculum_courses:
        moved_item = moved_items.get(curriculum_course.course_id)
        record = latest_records.get(curriculum_course.course_id)
        is_failed = (
            record
            and record.status == StudentCourseRecord.RecordStatus.FAILED
        )
        has_grade = record and record.grade_value is not None
        original_slot = (curriculum_course.year_level, curriculum_course.term)

        if (
            moved_item
            and not is_failed
            and not has_grade
            and (moved_item.planned_year_level, moved_item.planned_term) != original_slot
        ):
            moved_out_orders_by_slot[original_slot].append(curriculum_course.display_order)

    for orders in moved_out_orders_by_slot.values():
        orders.sort()

    moved_in_count_by_slot = defaultdict(int)
    grouped_items = OrderedDict()

    def append_row(year_level, term, row):
        key = (year_level, term)
        grouped_items.setdefault(key, [])
        grouped_items[key].append(row)

    for curriculum_course in curriculum_courses:
        course = curriculum_course.course
        record = latest_records.get(course.id)
        moved_item = moved_items.get(course.id)
        is_failed = (
            record
            and record.status == StudentCourseRecord.RecordStatus.FAILED
        )
        has_grade = record and record.grade_value is not None

        if moved_item and not is_failed and not has_grade:
            continue

        append_row(
            curriculum_course.year_level,
            curriculum_course.term,
            {
                "course_code": course.course_code,
                "course_title": course.course_title,
                "units": course.units,
                "course": course,
                "grade": record.grade_value if has_grade else "",
                "status": record.status if record else "",
                "is_completed": bool(record and record.is_credit_earned),
                "is_failed": bool(is_failed),
                "notes": "Original failed attempt" if is_failed else "",
                "source": "original",
                "sort_order": curriculum_course.display_order * 10,
            },
        )

    for item in pos_plan.items.select_related("course", "linked_record").order_by(
        "planned_year_level",
        "planned_term",
        "display_order",
    ):
        target_slot = (item.planned_year_level, item.planned_term)
        target_orders = moved_out_orders_by_slot.get(target_slot, [])
        moved_in_index = moved_in_count_by_slot[target_slot]

        if moved_in_index < len(target_orders):
            sort_order = target_orders[moved_in_index] * 10 - 1
        else:
            sort_order = item.display_order * 10 + 1000

        moved_in_count_by_slot[target_slot] += 1

        append_row(
            item.planned_year_level,
            item.planned_term,
            {
                "course_code": item.course.course_code,
                "course_title": item.course.course_title,
                "units": item.course.units,
                "course": item.course,
                "grade": "",
                "status": "",
                "is_completed": item.is_completed,
                "is_failed": False,
                "notes": item.notes or "",
                "source": "rearranged",
                "sort_order": sort_order,
            },
        )

    sorted_groups = OrderedDict()
    for key, rows in sorted(
        grouped_items.items(),
        key=lambda grouped: slot_sort_key(grouped[0][0], grouped[0][1]),
    ):
        sorted_groups[key] = sorted(
            rows,
            key=lambda row: (row.get("sort_order", 9999), row["course_code"]),
        )

    return sorted_groups


def generate_rearranged_pos_plan(student, generated_by=None):
    passed_course_ids = get_passed_course_ids(student)
    failed_course_ids = get_failed_course_ids(student, passed_course_ids)
    latest_failed_records = get_latest_failed_record_map(student, failed_course_ids)
    curriculum_courses = list(get_ordered_curriculum_courses(student.curriculum))

    if not curriculum_courses:
        raise ValueError(
            f"No CurriculumCourse records found for curriculum "
            f"{student.curriculum_id}. Cannot generate a POS plan."
        )

    course_map = {item.course_id: item for item in curriculum_courses}
    course_ids = [item.course_id for item in curriculum_courses]
    prerequisite_map, corequisite_map = _build_requirement_maps(course_ids)
    unit_limit_map = get_all_unit_limits(student.curriculum)
    max_curriculum_year = max(item.year_level for item in curriculum_courses)
    planned_slots = {}
    active_course_ids = []

    for curriculum_course in curriculum_courses:
        course_id = curriculum_course.course_id
        if course_id in passed_course_ids:
            continue

        active_course_ids.append(course_id)
        if course_id in failed_course_ids:
            planned_slots[course_id] = (
                curriculum_course.year_level + 1,
                curriculum_course.term,
            )
        else:
            planned_slots[course_id] = (
                curriculum_course.year_level,
                curriculum_course.term,
            )

    for _ in range(50):
        changed = False

        for course_id in active_course_ids:
            curriculum_course = course_map[course_id]
            year_level, term = planned_slots[course_id]

            min_standing_year = get_min_standing_year(curriculum_course)
            if min_standing_year and year_level < min_standing_year:
                year_level = min_standing_year
                changed = True

            for prereq_id in prerequisite_map.get(course_id, set()):
                if prereq_id in passed_course_ids:
                    continue

                prereq_slot = planned_slots.get(prereq_id)
                if prereq_slot and slot_sort_key(*prereq_slot) >= slot_sort_key(year_level, term):
                    year_level, term = next_same_term_after(
                        term,
                        slot_sort_key(*prereq_slot),
                    )
                    changed = True

            for coreq_id in corequisite_map.get(course_id, set()):
                if coreq_id in passed_course_ids:
                    continue

                coreq_slot = planned_slots.get(coreq_id)
                if coreq_slot and coreq_slot != (year_level, term):
                    if slot_sort_key(*coreq_slot) > slot_sort_key(year_level, term):
                        year_level, term = coreq_slot
                        changed = True

            if planned_slots[course_id] != (year_level, term):
                planned_slots[course_id] = (year_level, term)

        units_by_slot = defaultdict(int)
        courses_by_slot = defaultdict(list)
        for course_id in active_course_ids:
            slot = planned_slots[course_id]
            units_by_slot[slot] += course_map[course_id].course.units
            courses_by_slot[slot].append(course_id)

        for slot, total_units in list(units_by_slot.items()):
            limit = get_unit_limit_for_planning_slot(unit_limit_map, slot[0], slot[1])
            while total_units > limit and courses_by_slot[slot]:
                excess_units = total_units - limit
                movable_course_ids = [
                    course_id
                    for course_id in courses_by_slot[slot]
                    if course_id not in failed_course_ids
                ]
                if not movable_course_ids:
                    break

                candidates = sorted(
                    movable_course_ids,
                    key=lambda course_id: (
                        planned_slots[course_id] == (
                            course_map[course_id].year_level,
                            course_map[course_id].term,
                        ),
                        not course_has_hard_requirements(
                            course_id,
                            prerequisite_map,
                            corequisite_map,
                        ),
                        course_map[course_id].course.units >= excess_units,
                        course_map[course_id].course.units,
                        course_map[course_id].display_order,
                    ),
                    reverse=True,
                )
                course_to_move = candidates[0]

                if course_has_hard_requirements(
                    course_to_move,
                    prerequisite_map,
                    corequisite_map,
                ):
                    new_slot = next_same_term_after(
                        course_map[course_to_move].term,
                        slot_sort_key(*slot),
                    )
                else:
                    new_slot = find_next_fitting_slot(
                        course_to_move,
                        slot,
                        planned_slots,
                        course_map,
                        unit_limit_map,
                        max_curriculum_year + 3,
                    )

                planned_slots[course_to_move] = new_slot
                total_units -= course_map[course_to_move].course.units
                courses_by_slot[slot].remove(course_to_move)
                changed = True

        if not changed:
            break

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

        for curriculum_course in curriculum_courses:
            course = curriculum_course.course
            is_failed_retake = course.id in failed_course_ids

            if course.id in passed_course_ids:
                continue

            planned_slot = planned_slots.get(course.id)
            if not planned_slot:
                continue

            original_slot = (curriculum_course.year_level, curriculum_course.term)
            if not is_failed_retake and planned_slot == original_slot:
                continue

            POSPlanItem.objects.create(
                pos_plan=pos_plan,
                course=course,
                planned_year_level=planned_slot[0],
                planned_term=planned_slot[1],
                display_order=display_counter,
                is_auto_assigned=True,
                is_manually_adjusted=False,
                is_completed=False,
                linked_record=latest_failed_records.get(course.id),
                notes=(
                    "Retake failed course"
                    if is_failed_retake
                    else "Moved due to prerequisite, standing, or unit-limit adjustment"
                ),
            )

            display_counter += 1

            if planned_slot[0] > max_curriculum_year:
                overflow_course_codes.append(course.course_code)

        if overflow_course_codes:
            pos_plan.notes += (
                f"\n\nCourses placed beyond curriculum year {max_curriculum_year}:\n"
                + "\n".join(overflow_course_codes)
            )
            pos_plan.save()

    return pos_plan
