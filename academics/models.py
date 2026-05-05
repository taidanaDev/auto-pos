from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db.models import Case, When, IntegerField


PASSING_GRADE = 3.00

def full_name(self):
    return f"{self.user.first_name} {self.user.last_name}"
full_name.short_description = "Full Name"

class Department(models.Model):
    department_code = models.CharField(max_length=20, unique=True)
    department_name = models.CharField(max_length=150)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.department_code


class Program(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="programs"
    )
    program_code = models.CharField(max_length=20, unique=True)
    program_name = models.CharField(max_length=150)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.program_code


class Curriculum(models.Model):
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="curricula"
    )
    curriculum_code = models.CharField(max_length=50, unique=True)
    curriculum_name = models.CharField(max_length=150)
    academic_year_label = models.CharField(max_length=50, blank=True, null=True)
    total_units = models.PositiveIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_curricula"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.curriculum_code


class Student(models.Model):
    class Status(models.TextChoices):
        REGULAR = "regular", "Regular"
        IRREGULAR = "irregular", "Irregular"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_profile"
    )

    sr_code = models.CharField(max_length=30, unique=True)

    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.PROTECT,
        related_name="students"
    )

    year_level = models.PositiveIntegerField()
    current_semester = models.PositiveIntegerField()

    section_code = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                regex=r'^[1-9][1-3]0[1-9]$',
                message=(
                    "Section code must be 4 digits: "
                    "[year_level][term(1-3)][0][section_number], e.g. 3201."
                )
            )
        ]
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REGULAR
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.section_code:
            if len(self.section_code) != 4:
                raise ValidationError("Section code must be exactly 4 digits.")

            if self.section_code[2] != "0":
                raise ValidationError("The third digit of section code must be 0.")

    def save(self, *args, **kwargs):
        if self.section_code and len(self.section_code) == 4:
            self.year_level = int(self.section_code[0])
            self.current_semester = int(self.section_code[1])

        super().save(*args, **kwargs)

    @property
    def section_term(self):
        term_map = {
            "1": "first_sem",
            "2": "second_sem",
            "3": "midterm"
        }
        return term_map.get(self.section_code[1])

    @property
    def section_number(self):
        return int(self.section_code[3])

    def full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"

    def __str__(self):
        return f"{self.sr_code} - {self.full_name()}"


class Course(models.Model):
    course_code = models.CharField(max_length=30, unique=True)
    course_title = models.CharField(max_length=200)
    units = models.PositiveIntegerField()
    is_elective = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.course_code

class CurriculumCourseQuerySet(models.QuerySet):
    def ordered_by_pos_sequence(self):
        return self.annotate(
            term_order=Case(
                When(term="first_sem", then=1),
                When(term="second_sem", then=2),
                When(term="midterm", then=3),
                output_field=IntegerField()
            )
        ).order_by("year_level", "term_order", "display_order")

class CurriculumCourse(models.Model):
    class Term(models.TextChoices):
        FIRST_SEM = "first_sem", "First Semester"
        SECOND_SEM = "second_sem", "Second Semester"
        MIDTERM = "midterm", "Midterm"

    TERM_ORDER = {
        "first_sem": 1,
        "second_sem": 2,
        "midterm": 3
    }

    objects = CurriculumCourseQuerySet.as_manager()

    curriculum = models.ForeignKey(
        Curriculum,
        on_delete=models.CASCADE,
        related_name="curriculum_courses"
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="curriculum_courses"
    )

    year_level = models.PositiveIntegerField()

    term = models.CharField(
        max_length=20,
        choices=Term.choices
    )

    display_order = models.PositiveIntegerField()
    is_required = models.BooleanField(default=True)

    standing_requirement = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    class Meta:
        ordering = ["year_level", "display_order"]
        unique_together = ["curriculum", "course"]

    @property
    def term_order(self):
        return self.TERM_ORDER.get(self.term, 99)

    def __str__(self):
        return f"{self.curriculum.curriculum_code} - {self.course.course_code}"


class CourseRequirement(models.Model):
    class RequirementType(models.TextChoices):
        PREREQUISITE = "prerequisite", "Prerequisite"
        COREQUISITE = "corequisite", "Corequisite"

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="requirements"
    )

    required_course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="required_for"
    )

    requirement_type = models.CharField(
        max_length=20,
        choices=RequirementType.choices
    )

    class Meta:
        unique_together = ["course", "required_course", "requirement_type"]

    def clean(self):
        if self.course == self.required_course:
            raise ValidationError("A course cannot require itself.")

    def __str__(self):
        return f"{self.course.course_code} requires {self.required_course.course_code}"


class StudentCourseRecord(models.Model):
    class RecordStatus(models.TextChoices):
        PASSED = "passed", "Passed"
        FAILED = "failed", "Failed"
        IN_PROGRESS = "in_progress", "In Progress"
        DROPPED = "dropped", "Dropped"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="course_records"
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="student_records"
    )

    school_year = models.CharField(max_length=20)

    term = models.CharField(
        max_length=20,
        choices=CurriculumCourse.Term.choices
    )

    grade_value = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=RecordStatus.choices,
        blank=True
    )

    is_credit_earned = models.BooleanField(default=False)

    remarks = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["student", "course", "school_year", "term"]

    def evaluate_grade(self):
        if self.status == self.RecordStatus.DROPPED:
            self.is_credit_earned = False
            return

        if self.grade_value is None:
            self.status = self.RecordStatus.IN_PROGRESS
            self.is_credit_earned = False

        elif self.grade_value <= PASSING_GRADE:
            self.status = self.RecordStatus.PASSED
            self.is_credit_earned = True

        else:
            self.status = self.RecordStatus.FAILED
            self.is_credit_earned = False

    def save(self, *args, **kwargs):
        self.evaluate_grade()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.sr_code} - {self.course.course_code}"