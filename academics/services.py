from decimal import Decimal

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
    }