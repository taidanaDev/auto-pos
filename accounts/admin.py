from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    model = User
    list_display = (
        "email",
        "first_name",
        "last_name",
        "role",
        "is_active",
        "must_change_password",
        "is_staff",
    )
    list_filter = (
        "role",
        "is_active",
        "must_change_password",
        "is_staff",
    )
    search_fields = (
        "email",
        "first_name",
        "last_name",
    )
    ordering = ("email",)

    readonly_fields = ("last_login", "created_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal Information", {"fields": ("first_name", "last_name")}),
        ("Auto-POS Role", {"fields": ("role", "must_change_password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important Dates", {"fields": ("last_login", "created_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "first_name",
                "last_name",
                "role",
                "password1",
                "password2",
                "is_staff",
                "is_superuser",
                "is_active",
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change and obj.role == User.Role.STUDENT:
            obj.must_change_password = True

        super().save_model(request, obj, form, change)
