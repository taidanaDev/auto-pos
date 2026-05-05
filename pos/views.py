from django.shortcuts import render
# views.py
from django.db.models import Case, When, IntegerField
from pos.models import POSPlan, POSPlanItem

class POSPlanDetailView(RetrieveAPIView):  # or whatever view you have
    def get_queryset(self):
        plan_id = self.kwargs["pk"]

        # ✅ ADD the annotated query here
        return POSPlanItem.objects.filter(
            pos_plan_id=plan_id
        ).annotate(
            term_order=Case(
                When(planned_term="first_sem", then=1),
                When(planned_term="second_sem", then=2),
                When(planned_term="midterm", then=3),
                output_field=IntegerField()
            )
        ).order_by("planned_year_level", "term_order", "display_order")