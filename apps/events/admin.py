"""Django Admin configuration for events, tracks, and prizes."""

from django.contrib import admin
from .models import Event, Track, Prize


class TrackInline(admin.TabularInline):
    model = Track
    extra = 1


class PrizeInline(admin.TabularInline):
    model = Prize
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'status',
        'start_date',
        'end_date',
        'registration_deadline',
        'submission_deadline',
        'created_by',
        'gallery_enabled',
    )
    list_filter = ('status', 'gallery_enabled', 'start_date')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [TrackInline, PrizeInline]


@admin.register(Track)
class TrackAdmin(admin.ModelAdmin):
    list_display = ('name', 'event')
    list_filter = ('event',)
    search_fields = ('name', 'description')


@admin.register(Prize)
class PrizeAdmin(admin.ModelAdmin):
    list_display = ('title', 'rank', 'description', 'event')
    list_filter = ('event', 'rank')
    search_fields = ('title', 'description')
