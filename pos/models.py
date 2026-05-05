from django.db import models
from django.conf import settings
from academics.models import Student, Course, StudentCourseRecord, CurriculumCourse
from django.db import transaction
from django.db.models import Q

class POSPlan(models.Model):
    class PlanStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        MANUALLY_ADJUSTED = "manually_adjusted", "Manually Adjusted"
        EXPORTED = "exported", "Exported"

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="pos_plans"
    )

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_pos_plans"
    )

    status = models.CharField(
        max_length=30,
        choices=PlanStatus.choices,
        default=PlanStatus.DRAFT
    )

    is_current = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(is_current=True),
                name="unique_current_pos_plan_per_student"
            )
        ]
    def mark_as_current(self):
        with transaction.atomic():
            POSPlan.objects.filter(student=self.student).update(is_current=False)
            self.is_current = True
            self.save()

    def __str__(self):
        return f"POS Plan for {self.student.sr_code}"
    
class POSPlanItem(models.Model):
    pos_plan = models.ForeignKey(
        POSPlan,
        on_delete=models.CASCADE,
        related_name="items"
    )

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="pos_plan_items"
    )

    planned_year_level = models.PositiveIntegerField()
    planned_term = models.CharField(
        max_length=20,
        choices=CurriculumCourse.Term.choices
    )
    display_order = models.PositiveIntegerField()
    is_auto_assigned = models.BooleanField(default=True)
    is_manually_adjusted = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)

    linked_record = models.ForeignKey(
        StudentCourseRecord,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="linked_pos_plan_items"
    )

    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["planned_year_level", "display_order"]
        unique_together = ["pos_plan", "course"]

    def __str__(self):
        return f"{self.pos_plan.student.sr_code} - {self.course.course_code}"