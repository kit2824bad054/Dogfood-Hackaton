"""
Role-based permission classes for Django REST Framework (DRF).

This module provides reusable permissions for DRF API views and viewsets
across all phases of the Dogfood Platform.
"""

from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    """
    DRF permission class that grants access if the user has one of `allowed_roles`.

    View classes specify `allowed_roles` as a list or tuple of role strings.

    Usage Example:

        from rest_framework import viewsets
        from apps.accounts.permissions import HasRole

        class EventViewSet(viewsets.ModelViewSet):
            permission_classes = [HasRole]
            allowed_roles = ['organizer', 'admin']
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        allowed_roles = getattr(view, 'allowed_roles', None)
        if not allowed_roles:
            return True

        if isinstance(allowed_roles, str):
            allowed_roles = [allowed_roles]

        user_role = getattr(request.user, 'role', None)
        if user_role in allowed_roles:
            return True

        if request.user.is_superuser and ('admin' in allowed_roles or user_role in allowed_roles):
            return True

        return False
