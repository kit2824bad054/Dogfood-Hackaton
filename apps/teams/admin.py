"""Django Admin configuration for teams and memberships."""

from django.contrib import admin
from .models import Team, TeamMembership


class TeamMembershipInline(admin.TabularInline):
    model = TeamMembership
    extra = 1
    readonly_fields = ('joined_at',)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'event', 'invite_code', 'created_by', 'member_count', 'max_members', 'created_at')
    list_filter = ('event', 'created_at')
    search_fields = ('name', 'invite_code', 'created_by__username', 'event__name')
    readonly_fields = ('invite_code', 'created_at')
    inlines = [TeamMembershipInline]


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ('team', 'user', 'get_event', 'joined_at')
    list_filter = ('team__event', 'joined_at')
    search_fields = ('user__username', 'team__name', 'team__event__name')

    def get_event(self, obj):
        return obj.team.event.name
    get_event.short_description = 'Event'
