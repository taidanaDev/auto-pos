from django.contrib import admin
from .models import POSPlan, POSPlanItem

class POSPlanItemInline(admin.TabularInline):
    model = POSPlanItem
    extra = 0
    show_change_link = True
    fields = (          # ← ADD
        "course",
        "planned_year_level",
        "planned_term",
        "display_order",
        "is_completed",
    )
    readonly_fields = ("is_auto_assigned", "is_manually_adjusted", "linked_record")

@admin.register(POSPlan)
class POSPlanAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "generated_by",
        "status",
        "is_current",
        "created_at",
    )
    search_fields = ("student__sr_code", "student__user__last_name")
    list_filter = ("status", "is_current")
    readonly_fields = ("is_current", "created_at", "updated_at")
    inlines = [POSPlanItemInline]
    autocomplete_fields = ("student", "generated_by")


@admin.register(POSPlanItem)
class POSPlanItemAdmin(admin.ModelAdmin):
    list_display = (
        "pos_plan",
        "course",
        "planned_year_level",
        "planned_term",
        "display_order",
        "is_auto_assigned",
        "is_manually_adjusted",
        "is_completed",
    )
    search_fields = ("pos_plan__student__sr_code", "course__course_code")
    list_filter = (
        "planned_year_level",
        "planned_term",
        "is_auto_assigned",
        "is_manually_adjusted",
        "is_completed",
    )
    list_per_page = 25
    autocomplete_fields = ("pos_plan", "course", "linked_record")