# accounts/decorators.py  ← CREATE this file
from functools import wraps
from django.shortcuts import redirect
from accounts.models import User

def must_have_changed_password(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.must_change_password:
            return redirect("change_password")      # ← centralized check
        return view_func(request, *args, **kwargs)
    return wrapper

def role_required(role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.role != role:
                return redirect("landing_page")     # ← wrong role → landing page
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator