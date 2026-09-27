"""
Django Admin configuration for project submissions.
"""

from django.contrib import admin
from .models import Submission


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('title', 'team', 'event', 'track', 'status', 'submitted_at', 'created_at')
    list_filter = ('status', 'event', 'track')
    search_fields = ('title', 'description', 'team__name', 'repo_url')
    readonly_fields = ('event', 'submitted_at', 'created_at', 'updated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('team', 'event', 'track')
