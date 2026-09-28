from django.contrib import admin
from apps.community.models import AuditLog, Comment, EventRegistration, Vote


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ['user', 'event', 'registered_at']
    list_filter = ['event']
    search_fields = ['user__username', 'event__name']


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'submission', 'value', 'created_at', 'updated_at']
    list_filter = ['value', 'submission__event']
    search_fields = ['user__username', 'submission__title']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'submission', 'created_at', 'is_hidden', 'is_flagged_duplicate']
    list_filter = ['is_hidden', 'is_flagged_duplicate', 'submission__event']
    search_fields = ['user__username', 'submission__title', 'body']
    actions = ['hide_comments', 'unhide_comments']

    def hide_comments(self, request, queryset):
        queryset.update(is_hidden=True)
    hide_comments.short_description = "Hide selected comments"

    def unhide_comments(self, request, queryset):
        queryset.update(is_hidden=False)
    unhide_comments.short_description = "Unhide selected comments"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'action', 'user', 'target_submission']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__username', 'target_submission__title']
    readonly_fields = ['timestamp', 'user', 'action', 'target_submission', 'metadata']
