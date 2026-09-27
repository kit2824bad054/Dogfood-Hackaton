"""
Access control decorators for Dogfood Platform.

This module provides the reusable `@role_required(*allowed_roles)` decorator
used across all phases (accounts, events, teams, submissions, gallery) to enforce
role-based access control (RBAC) on Django views.
"""

from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def role_required(*allowed_roles):
    """
    Decorator for views that enforces role-based access control.

    Allowed roles can be passed as positional arguments or an iterable.
    Valid platform roles: 'participant', 'judge', 'organizer', 'admin'.

    Behavior:
    1. Unauthenticated users are redirected to the login page (via `redirect_to_login`).
    2. Authenticated users whose `role` matches one of `allowed_roles` are granted access.
    3. Superusers (`request.user.is_superuser`) automatically satisfy any role check or 'admin'.
    4. Authenticated users without an allowed role are rejected with HTTP 403 Forbidden
       (raises `django.core.exceptions.PermissionDenied`).

    Usage Examples:

        # Example 1: Function-based view with single role
        from apps.accounts.decorators import role_required

        @role_required('organizer')
        def create_event(request):
            ...

        # Example 2: Multiple allowed roles
        @role_required('organizer', 'admin')
        def manage_event(request, event_id):
            ...

        # Example 3: Class-based view (CBV)
        from django.utils.decorators import method_decorator
        from django.views import View

        @method_decorator(role_required('judge', 'admin'), name='dispatch')
        class ScoringView(View):
            ...
    """
    # Normalize allowed roles into a set of strings
    roles = set()
    for arg in allowed_roles:
        if isinstance(arg, (list, tuple, set)):
            roles.update(arg)
        else:
            roles.add(str(arg))

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Check authentication first
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())

            # Check if user role matches, or if user is superuser
            user_role = getattr(request.user, 'role', None)
            if user_role in roles or (request.user.is_superuser and ('admin' in roles or user_role in roles)):
                return view_func(request, *args, **kwargs)

            # Access denied -> raise 403
            raise PermissionDenied(
                f"Access denied. User role '{user_role}' is not in allowed roles: {sorted(list(roles))}."
            )

        return _wrapped_view

    return decorator
