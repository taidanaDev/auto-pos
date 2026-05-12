from django.urls import path
from . import views

urlpatterns = [
    path("generate/", views.generate_pos, name="generate_pos"),
    path("plans/", views.my_pos_plans, name="my_pos_plans"),
    path("plans/<int:pos_plan_id>/", views.generated_pos_detail, name="generated_pos_detail"),
]