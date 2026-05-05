from django.contrib import admin
from .models import (
    Department,
    Program,
    Curriculum,
    Student,
    Course,
    CurriculumCourse,
    CourseRequirement,
    StudentCourseRecord,
)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("department_code", "department_name")
    search_fields = ("department_code", "department_name")


@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("program_code", "program_name", "department")
    search_fields = ("program_code", "program_name")
    list_filter = ("department",)


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = (
        "curriculum_code",
        "curriculum_name",
        "program",
        "academic_year_label",
        "total_units",
        "is_active",
    )
    search_fields = ("curriculum_code", "curriculum_name")
    list_filter = ("program", "is_active")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "sr_code",
        "full_name",
        "curriculum",
        "year_level",
        "current_semester",
        "section_code",
        "status",
    )
    search_fields = (
        "sr_code",
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    list_filter = ("year_level", "current_semester", "status", "curriculum")
    autocomplete_fields = ("user", "curriculum")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("course_code", "course_title", "units", "is_elective")
    search_fields = ("course_code", "course_title")
    list_filter = ("is_elective",)


@admin.register(CurriculumCourse)
class CurriculumCourseAdmin(admin.ModelAdmin):
    list_display = (
        "curriculum",
        "course",
        "year_level",
        "term",
        "display_order",
        "is_required",
        "standing_requirement",
    )
    search_fields = ("course__course_code", "course__course_title")
    list_filter = ("curriculum", "year_level", "term", "is_required")


@admin.register(CourseRequirement)
class CourseRequirementAdmin(admin.ModelAdmin):
    list_display = ("course", "required_course", "requirement_type")
    search_fields = ("course__course_code", "required_course__course_code")
    list_filter = ("requirement_type",)


@admin.register(StudentCourseRecord)
class StudentCourseRecordAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "course",
        "school_year",
        "term",
        "grade_value",
        "status",
        "is_credit_earned",
    )
    search_fields = ("student__sr_code", "course__course_code")
    list_filter = ("school_year", "term", "status", "is_credit_earned")
    readonly_fields = ("status", "is_credit_earned")
    list_per_page = 25