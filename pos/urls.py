from django.urls import path
from . import views

urlpatterns = [
    path("generate/", views.generate_pos, name="generate_pos"),
    path("plans/", views.my_pos_plans, name="my_pos_plans"),
    path("plans/<int:pos_plan_id>/", views.generated_pos_detail, name="generated_pos_detail"),
    path("plans/<int:pos_plan_id>/preview-pdf/", views.pos_pdf_preview, name="pos_pdf_preview"),
    path("plans/<int:pos_plan_id>/download-pdf/", views.pos_pdf_download, name="pos_pdf_download"),
]