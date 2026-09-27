"""Admin registration and customization for accounts."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom UserAdmin exposing the role field in list displays, filters,
    and editing forms to facilitate user role management directly in Django Admin.
    """
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    # Add 'role' field to the main user editing fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Platform Role Management', {
            'fields': ('role',),
            'description': 'Assign or modify the platform role (Participant, Judge, Organizer, Admin).'
        }),
    )

    # Add 'role' field to the creation fieldsets
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Platform Role Management', {
            'fields': ('role',),
            'description': 'Specify the platform role for this new user.'
        }),
    )
