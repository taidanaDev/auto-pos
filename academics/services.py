import math

from .models import CurriculumCourse, StudentCourseRecord


def get_student_academic_progress(student):
    curriculum_courses = CurriculumCourse.objects.select_related(
        "course"
    ).filter(
        curriculum=student.curriculum
    )

    course_ids_in_curriculum = [
        item.course_id for item in curriculum_courses
    ]

    records = StudentCourseRecord.objects.select_related(
        "course"
    ).filter(
        student=student,
        course_id__in=course_ids_in_curriculum
    )

    passed_records = records.filter(
        status=StudentCourseRecord.RecordStatus.PASSED,
        is_credit_earned=True
    )

    failed_records = records.filter(
        status=StudentCourseRecord.RecordStatus.FAILED
    )

    passed_course_ids = set(
        passed_records.values_list("course_id", flat=True)
    )

    failed_course_ids = set(
        failed_records.values_list("course_id", flat=True)
    )

    completed_courses = []
    failed_courses = []
    remaining_courses = []

    earned_units = 0

    for record in passed_records:
        completed_courses.append(record)
        earned_units += record.course.units

    for record in failed_records:
        failed_courses.append(record)

    for curriculum_course in curriculum_courses:
        course_id = curriculum_course.course_id

        if course_id not in passed_course_ids:
            remaining_courses.append(curriculum_course)

    total_units = student.curriculum.total_units or sum(
        item.course.units for item in curriculum_courses
    )

    remaining_units = total_units - earned_units

    if total_units > 0:
        progress_percentage = round((earned_units / total_units) * 100, 2)
    else:
        progress_percentage = 0

    year_standing = calculate_year_standing(student)
    year_standing_breakdown = get_year_standing_breakdown(student)

    return {
        "total_units": total_units,
        "earned_units": earned_units,
        "remaining_units": remaining_units,
        "progress_percentage": progress_percentage,
        "completed_courses": completed_courses,
        "failed_courses": failed_courses,
        "remaining_courses": remaining_courses,
        "completed_count": len(completed_courses),
        "failed_count": len(failed_courses),
        "remaining_count": len(remaining_courses),
        "year_standing": year_standing,
        "year_standing_breakdown": year_standing_breakdown,
    }

def calculate_year_standing(student):
    current_standing = 1

    year_levels = list(
        CurriculumCourse.objects.filter(
            curriculum=student.curriculum,
            is_required=True
        ).values_list(
            "year_level",
            flat=True
        ).distinct().order_by("year_level")
    )

    taken_course_ids = set(
        StudentCourseRecord.objects.filter(
            student=student
        ).values_list("course_id", flat=True)
    )

    for year_level in year_levels:
        required_courses = CurriculumCourse.objects.filter(
            curriculum=student.curriculum,
            year_level=year_level,
            is_required=True
        )

        total_required_count = required_courses.count()

        if total_required_count == 0:
            continue

        required_taken_count = required_courses.filter(
            course_id__in=taken_course_ids
        ).count()

        minimum_required_count = math.ceil(total_required_count * 0.75)

        if required_taken_count >= minimum_required_count:
            current_standing = year_level + 1
        else:
            break

    max_year_level = max(year_levels) if year_levels else 1

    if current_standing > max_year_level:
        current_standing = max_year_level

    return current_standing
def get_year_standing_breakdown(student):
    """
    Returns year-level standing details for display and debugging.
    """

    breakdown = []

    curriculum_years = CurriculumCourse.objects.filter(
        curriculum=student.curriculum,
        is_required=True
    ).values_list(
        "year_level",
        flat=True
    ).distinct().order_by("year_level")

    taken_course_ids = set(
        StudentCourseRecord.objects.filter(
            student=student
        ).values_list("course_id", flat=True)
    )

    for year_level in curriculum_years:
        required_courses = CurriculumCourse.objects.filter(
            curriculum=student.curriculum,
            year_level=year_level,
            is_required=True
        )

        total_required_count = required_courses.count()
        taken_count = required_courses.filter(
            course_id__in=taken_course_ids
        ).count()

        minimum_required_count = math.ceil(total_required_count * 0.75)

        qualifies = taken_count >= minimum_required_count

        breakdown.append({
            "year_level": year_level,
            "total_required_count": total_required_count,
            "taken_count": taken_count,
            "minimum_required_count": minimum_required_count,
            "qualifies": qualifies,
        })

        if not qualifies:
            break

    return breakdown